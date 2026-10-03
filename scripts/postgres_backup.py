"""Independent PostgreSQL backups and explicit isolated restore; stdlib only.

Credentials use libpq environment variables, never CLI arguments. Raw stderr and
connection exceptions are suppressed because they can contain passwords/URLs.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from urllib.parse import parse_qsl, unquote, urlsplit

SUPPORTED_MAJORS = range(14, 19)
TARGETS = {'auth': 'DATABASE_URL', 'design': 'CAPSTONE_DESIGN_DATABASE_URL'}
REQUIRED = {
    'auth': {'users': {'user_id', 'email', 'password_hash'}},
    'design': {
        'accounts': {'account_id', 'participant_id'},
        'orders': {'order_id', 'account_id', 'asset_id', 'effective_at'},
        'trades': {'trade_id', 'order_id', 'account_id', 'execution_price', 'quantity'},
        'holdings_daily': {'account_id', 'date', 'asset_id', 'quantity', 'market_value'},
        'nav_daily': {'account_id', 'date', 'nav', 'cash_balance'},
    },
}

class BackupError(Exception):
    """Only constant error codes are safe for logs."""

def tool(command, env=None, code='TOOL_FAILED'):
    try:
        result = subprocess.run(command, env=env, capture_output=True, text=True, timeout=1800)
    except (OSError, subprocess.TimeoutExpired):
        raise BackupError(code) from None
    if result.returncode:
        raise BackupError(code) from None
    return result.stdout

def host_key(host):
    host = host.lower().rstrip('.')
    if host.endswith('.neon.tech'):
        first, rest = host.split('.', 1)
        host = first.removesuffix('-pooler') + '.' + rest
    return host

class Connection:
    def __init__(self, url):
        if not url:
            raise BackupError('CONFIG_MISSING')
        try:
            parsed = urlsplit(url)
            if parsed.scheme not in ('postgres', 'postgresql', 'postgresql+psycopg'):
                raise ValueError()
            self.host, self.port = parsed.hostname, parsed.port or 5432
            self.database = unquote(parsed.path.lstrip('/'))
            if not self.host or not self.database or not parsed.username or parsed.fragment:
                raise ValueError()
            self.env = {k: v for k, v in os.environ.items() if k in
                        ('PATH','HOME','LANG','LC_ALL','TZ','SYSTEMROOT','TMPDIR','SSL_CERT_FILE')}
            self.env.update(PGHOST=self.host, PGPORT=str(self.port), PGDATABASE=self.database,
                PGUSER=unquote(parsed.username), PGPASSWORD=unquote(parsed.password or ''),
                PGCONNECT_TIMEOUT='15', PGPASSFILE=os.devnull, PGSERVICEFILE=os.devnull)
            allowed = {'sslmode','sslrootcert','sslcert','sslkey','sslcrl','channel_binding',
                'options','connect_timeout','target_session_attrs','application_name'}
            params = dict(parse_qsl(parsed.query, keep_blank_values=True))
            if set(params) - allowed:
                raise ValueError()
            self.env.update({'PG'+k.upper():v for k,v in params.items()})
            self.secrets = [url, parsed.password or '', self.env['PGPASSWORD']]
        except (ValueError, TypeError):
            raise BackupError('CONFIG_INVALID') from None

    @property
    def endpoint(self):
        return host_key(self.host), self.port, self.database

    def query(self, sql, code='QUERY_FAILED'):
        return tool(['psql','--no-password','--no-psqlrc','--tuples-only','--no-align',
            '--set','ON_ERROR_STOP=1','--command',sql], self.env, code).strip()

    def identity(self):
        value = json.loads(self.query("""SELECT json_build_object(
            'database',current_database(), 'database_oid',(SELECT oid FROM pg_database WHERE datname=current_database()),
            'server_addr',inet_server_addr()::text, 'server_port',inet_server_port(),
            'server_version_num',current_setting('server_version_num'))""", 'CONNECT_FAILED'))
        value.update(connection_host=self.host, connection_port=self.port)
        try:
            value['system_identifier'] = self.query('SELECT system_identifier::text FROM pg_control_system()')
        except BackupError:
            value['system_identifier'] = None
        return value

def same_database(a, b):
    if a['database_oid'] != b['database_oid'] or a['database'] != b['database']:
        return False
    backend = (a['server_addr'],a['server_port']) == (b['server_addr'],b['server_port']) and bool(a['server_addr'])
    cluster = bool(a.get('system_identifier')) and a.get('system_identifier') == b.get('system_identifier')
    return bool(backend or cluster)

def versions():
    result = {}
    for program in ('psql','pg_dump','pg_restore'):
        match = re.search(r'PostgreSQL\)?\s+(\d+)', tool([program,'--version'], code='CLIENT_UNAVAILABLE'))
        if not match:
            raise BackupError('CLIENT_VERSION_UNKNOWN')
        result[program] = int(match.group(1))
    if len(set(result.values())) != 1 or result['pg_dump'] not in SUPPORTED_MAJORS:
        raise BackupError('CLIENT_VERSION_UNSUPPORTED_OR_MIXED')
    return result

def check_version(identity, clients, restore=False):
    server, client = int(identity['server_version_num']) // 10000, clients['pg_dump']
    if server not in SUPPORTED_MAJORS or (server < client if restore else server > client):
        raise BackupError('RESTORE_VERSION_INCOMPATIBLE' if restore else 'SERVER_VERSION_INCOMPATIBLE')
    return server

def inspect(connection, target, check_expected=True):
    identity = connection.identity()
    prefix = 'BACKUP_'+target.upper()
    expected_host, expected_db = os.environ.get(prefix+'_HOST',''), os.environ.get(prefix+'_DATABASE','')
    if check_expected and ((expected_host and host_key(expected_host) != host_key(connection.host)) or
            (expected_db and expected_db != identity['database'])):
        raise BackupError('EXPECTED_TARGET_MISMATCH')
    columns = json.loads(connection.query("""SELECT coalesce(json_object_agg(table_name,cols),'{}'::json)
        FROM (SELECT table_name,json_agg(column_name ORDER BY ordinal_position) cols
        FROM information_schema.columns WHERE table_schema='public' GROUP BY table_name) s""", 'SCHEMA_CHECK_FAILED'))
    for table, names in REQUIRED[target].items():
        if table not in columns:
            raise BackupError('REQUIRED_TABLE_MISSING:'+table)
        if not names.issubset(columns[table]):
            raise BackupError('REQUIRED_COLUMNS_MISSING:'+table)
    primary_keys = json.loads(connection.query("""SELECT coalesce(json_agg(c.relname),'[]'::json)
        FROM pg_constraint k JOIN pg_class c ON c.oid=k.conrelid JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname='public' AND k.contype='p'""", 'SCHEMA_CHECK_FAILED'))
    if not set(REQUIRED[target]).issubset(primary_keys):
        raise BackupError('REQUIRED_PRIMARY_KEY_MISSING')
    counts = {t:int(connection.query('SELECT count(*) FROM public."'+t+'"', 'DATA_READ_FAILED')) for t in REQUIRED[target]}
    return dict(identity=identity, expected_target_configured=bool(expected_host and expected_db),
        required_columns={t:sorted(v) for t,v in REQUIRED[target].items()}, row_counts=counts)

def redact(value, secrets):
    if isinstance(value, dict):
        return {k:redact(v,secrets) for k,v in value.items()}
    if isinstance(value, list):
        return [redact(v,secrets) for v in value]
    if isinstance(value, str):
        for secret in sorted(set(s for s in secrets if s), key=len, reverse=True):
            value = value.replace(secret,'[REDACTED]')
    return value

def checksum(path):
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda:source.read(1024*1024),b''):
            digest.update(block)
    return digest.hexdigest()

def backup_one(target, directory, inspection_only=False):
    report = dict(target=target, status='FAILED', restore_verified=False)
    connection = None
    try:
        connection = Connection(os.environ.get(TARGETS[target],''))
        clients, own = versions(), connection.identity()
        report.update(identity=own, clients=clients)
        # A broken peer cannot prevent this independently valid backup.
        try:
            peer = Connection(os.environ.get(TARGETS['design' if target=='auth' else 'auth'],''))
        except BackupError:
            peer = None
        if peer and connection.endpoint == peer.endpoint:
            raise BackupError('SAME_DATABASE_TARGETS')
        if peer:
            try:
                peer_identity = peer.identity()
            except BackupError:
                peer_identity = None
            if peer_identity and same_database(own,peer_identity):
                raise BackupError('SAME_DATABASE_TARGETS')
            report['peer_identity_checked'] = bool(peer_identity)
        else:
            report['peer_identity_checked'] = False
        report['identity_limit'] = 'DNS/proxy aliases or clones may require owner confirmation; schema and identifiers do not prove deployment wiring.'
        check_version(own,clients)
        report.update(inspect(connection,target))
        if inspection_only:
            report['status'] = 'INSPECTED_ONLY'
        else:
            dump = directory/('robo_'+target+'.dump')
            temporary = directory/(dump.name+'.partial')
            try:
                tool(['pg_dump','--no-password','--format=custom','--quote-all-identifiers',
                    '--file',str(temporary)], connection.env, 'DUMP_FAILED')
                toc = tool(['pg_restore','--list',str(temporary)], code='ARCHIVE_TOC_FAILED')
                archived_tables = set(re.findall(r'^\d+; \d+ \d+ TABLE public (\S+) ',toc,re.MULTILINE))
                if not set(REQUIRED[target]).issubset(archived_tables):
                    raise BackupError('ARCHIVE_REQUIRED_TABLE_MISSING')
                temporary.chmod(0o600);temporary.replace(dump)
            finally:
                temporary.unlink(missing_ok=True)
            report.update(status='BACKED_UP', archive=dump.name,
                sha256=checksum(dump), archive_check='TOC_ONLY_NOT_A_RESTORE')
    except BackupError as error:
        report['error'] = str(error)
    except Exception:
        report['error'] = 'INTERNAL_FAILURE'
    safe = redact(report, connection.secrets if connection else [])
    manifest = directory/('robo_'+target+'.json')
    manifest.write_text(json.dumps(safe,indent=2)+'\n');manifest.chmod(0o600)
    return safe

def restore(dump, manifest, destination_url, acknowledged):
    if not acknowledged:
        raise BackupError('ISOLATED_RESTORE_ACK_REQUIRED')
    source = json.loads(manifest.read_text())
    if source.get('status') != 'BACKED_UP' or checksum(dump) != source.get('sha256'):
        raise BackupError('ARCHIVE_CHECKSUM_OR_MANIFEST_INVALID')
    connection = Connection(destination_url)
    if not re.fullmatch(r'robo_restore_[A-Za-z0-9_]+',connection.database):
        raise BackupError('ISOLATED_DESTINATION_NAME_REQUIRED')
    identity = connection.identity()
    if same_database(identity,source['identity']):
        raise BackupError('SOURCE_AND_RESTORE_DESTINATION_MATCH')
    for name in TARGETS.values():
        if os.environ.get(name):
            configured = Connection(os.environ[name])
            if connection.endpoint == configured.endpoint or same_database(identity,configured.identity()):
                raise BackupError('RESTORE_DESTINATION_IS_CONFIGURED_SOURCE')
    clients = versions()
    if clients['pg_restore'] != source['clients']['pg_dump']:
        raise BackupError('RESTORE_CLIENT_MUST_MATCH_DUMP_MAJOR')
    check_version(identity,clients,restore=True)
    count = int(connection.query("""SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname NOT IN ('pg_catalog','information_schema') AND n.nspname NOT LIKE 'pg_toast%'
        AND c.relkind IN ('r','p','v','m','S','f')"""))
    if count:
        raise BackupError('RESTORE_DESTINATION_NOT_EMPTY')
    # No --clean/--create; any SQL error rolls the entire restore back.
    tool(['pg_restore','--no-password','--exit-on-error','--single-transaction','--no-owner','--no-acl',
        '--dbname',connection.database,str(dump)], connection.env, 'RESTORE_FAILED')
    return redact(dict(status='RESTORED',**inspect(connection,source['target'],False)),connection.secrets)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action',required=True)
    backup = sub.add_parser('backup')
    backup.add_argument('--target',choices=['auth','design','all'],default='all')
    backup.add_argument('--output-dir',type=Path,required=True)
    backup.add_argument('--inspection-only',action='store_true')
    recover = sub.add_parser('restore')
    recover.add_argument('--dump',type=Path,required=True)
    recover.add_argument('--manifest',type=Path,required=True)
    recover.add_argument('--acknowledge-isolated',action='store_true')
    args = parser.parse_args()
    if args.action == 'backup':
        args.output_dir.mkdir(parents=True,exist_ok=True);args.output_dir.chmod(0o700)
        if list(args.output_dir.glob('robo_*.dump')) or list(args.output_dir.glob('robo_*.json')):
            print('{"status":"FAILED","error":"USE_FRESH_OUTPUT_DIRECTORY"}');return 1
        targets = TARGETS if args.target=='all' else [args.target]
        reports = [backup_one(t,args.output_dir,args.inspection_only) for t in targets]
        failed = sum(r['status']=='FAILED' for r in reports)
        print(json.dumps({'status':'PARTIAL_SUCCESS' if 0<failed<len(reports) else 'FAILED' if failed else
            'INSPECTED_ONLY' if args.inspection_only else 'SUCCESS',
            'targets':reports},indent=2))
        return int(bool(failed))
    try:
        result = restore(args.dump,args.manifest,os.environ.get('BACKUP_RESTORE_DATABASE_URL',''),args.acknowledge_isolated)
    except BackupError as error:
        result = {'status':'FAILED','error':str(error)}
    except Exception:
        result = {'status':'FAILED','error':'INTERNAL_FAILURE'}
    print(json.dumps(result,indent=2))
    return int(result['status']=='FAILED')

if __name__=='__main__':
    raise SystemExit(main())
