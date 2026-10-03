"""Read-only comparison; credentials and raw errors stay in process memory."""
from __future__ import annotations
import argparse
import ctypes as C
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

from scripts.postgres_backup import BackupError, Connection, TARGETS, connection_error, tool, versions

READ_ONLY_SQL = """BEGIN READ ONLY; SELECT json_build_object(
 'database',current_database(), 'database_oid',(SELECT oid FROM pg_database WHERE datname=current_database()),
 'server_addr',inet_server_addr()::text, 'server_port',inet_server_port(),
 'server_version_num',current_setting('server_version_num'),
 'read_only',current_setting('transaction_read_only'),
 'ssl',(SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()))"""
ENV_KEYS = {'host':'PGHOST','port':'PGPORT','dbname':'PGDATABASE','user':'PGUSER','password':'PGPASSWORD',
 'sslmode':'PGSSLMODE','sslrootcert':'PGSSLROOTCERT','sslcert':'PGSSLCERT','sslkey':'PGSSLKEY',
 'sslcrl':'PGSSLCRL','channel_binding':'PGCHANNELBINDING','options':'PGOPTIONS',
 'connect_timeout':'PGCONNECT_TIMEOUT','target_session_attrs':'PGTARGETSESSIONATTRS',
 'application_name':'PGAPPNAME'}
OPTION_ENUMS = {'sslmode':{'disable','allow','prefer','require','verify-ca','verify-full'},
 'channel_binding':{'disable','prefer','require'},
 'target_session_attrs':{'any','read-write','read-only','primary','standby','prefer-standby'}}

def option_shape(env):
    # Enum values are public configuration; invalid values may contain secrets.
    result={}
    for key,allowed in OPTION_ENUMS.items():
        value=env.get(ENV_KEYS[key])
        if value is not None:
            result[key]={'recognized':value in allowed,'value':value if value in allowed else 'INVALID_NOT_PRINTED',
                'has_whitespace':any(c.isspace() for c in value),
                'has_quote':any(c in value for c in "\"'"), 'has_assignment_separator':'=' in value}
    return result

class ConninfoOption(C.Structure):
    _fields_ = [(name,C.c_char_p) for name in ('keyword','envvar','compiled','val','label','dispchar')] + [('dispsize',C.c_int)]

class Libpq:
    def __init__(self):
        executable = Path(shutil.which('psql') or '').resolve()
        if sys.platform == 'darwin':
            paths = list(executable.parent.parent.glob('lib/**/libpq*.dylib'))
            if not paths: raise BackupError('CLIENT_LIBPQ_UNAVAILABLE')
            path = str(sorted(paths, key=lambda p:len(str(p)))[0])
        else:
            linked = tool(['ldd',str(executable)],code='CLIENT_LIBPQ_UNAVAILABLE')
            match = re.search(r'libpq\.so[^\s]*\s+=>\s+(\S+)',linked)
            if not match: raise BackupError('CLIENT_LIBPQ_UNAVAILABLE')
            path = match.group(1)
        self.lib = C.CDLL(path)
        signatures = {
            'PQlibVersion':([],C.c_int),
            'PQconninfoParse':([C.c_char_p,C.POINTER(C.c_void_p)],C.POINTER(ConninfoOption)),
            'PQconninfoFree':([C.POINTER(ConninfoOption)],None),
            'PQfreemem':([C.c_void_p],None),
            'PQconnectdbParams':([C.POINTER(C.c_char_p),C.POINTER(C.c_char_p),C.c_int],C.c_void_p),
            'PQstatus':([C.c_void_p],C.c_int), 'PQerrorMessage':([C.c_void_p],C.c_char_p),
            'PQsslInUse':([C.c_void_p],C.c_int),
            'PQexec':([C.c_void_p,C.c_char_p],C.c_void_p),
            'PQresultStatus':([C.c_void_p],C.c_int),
            'PQgetvalue':([C.c_void_p,C.c_int,C.c_int],C.c_char_p),
            'PQclear':([C.c_void_p],None), 'PQfinish':([C.c_void_p],None),
        }
        for name,(args,result) in signatures.items():
            function=getattr(self.lib,name);function.argtypes=args;function.restype=result
        self.version = self.lib.PQlibVersion()

    @staticmethod
    def uri(url):
        return url.replace('postgresql+psycopg://','postgresql://',1).encode()

    def parse(self,url):
        error=C.c_void_p()
        values=self.lib.PQconninfoParse(self.uri(url),C.byref(error))
        if not values:
            reason=connection_error(C.string_at(error).decode(errors='replace')) if error.value else 'CONNECT_URI_INVALID'
            if error.value:self.lib.PQfreemem(error)
            raise BackupError(reason)
        try:
            result={};index=0
            while values[index].keyword:
                item=values[index]
                if item.val is not None:result[item.keyword.decode()]=item.val.decode()
                index+=1
            return result
        finally:self.lib.PQconninfoFree(values)

    def read_only_identity(self,url):
        # Before expanded dbname: default timeout; explicit URI options win.
        keys=(C.c_char_p*3)(b'connect_timeout',b'dbname',None)
        values=(C.c_char_p*3)(b'15',self.uri(url),None)
        connection=self.lib.PQconnectdbParams(keys,values,1)
        if not connection:raise BackupError('CONNECT_FAILED')
        try:
            if self.lib.PQstatus(connection)!=0:
                raise BackupError(connection_error(self.lib.PQerrorMessage(connection).decode(errors='replace')))
            result=self.lib.PQexec(connection,READ_ONLY_SQL.encode())
            if not result:raise BackupError('READ_ONLY_QUERY_FAILED')
            try:
                if self.lib.PQresultStatus(result)!=2:raise BackupError('READ_ONLY_QUERY_FAILED')
                identity=json.loads(self.lib.PQgetvalue(result,0,0))
                identity['client_ssl']=bool(self.lib.PQsslInUse(connection))
                return identity
            finally:self.lib.PQclear(result)
        finally:self.lib.PQfinish(connection)  # Rolls back the read-only transaction.

def public_identity(identity):
    address={k:identity[k] for k in ('database','database_oid','server_addr','server_port')}
    return {'status':'CONNECTED_READ_ONLY','identity_fingerprint':hashlib.sha256(
        json.dumps(address,sort_keys=True).encode()).hexdigest(),
        'server_major':int(identity['server_version_num'])//10000,
        'read_only':identity['read_only']=='on','backend_ssl':identity['ssl'],
        'client_ssl':identity.get('client_ssl')}

def probe(url,mode):
    try:
        identity=Libpq().read_only_identity(url) if mode=='native' else json.loads(tool([
            'psql','--no-password','--no-psqlrc','--tuples-only','--no-align','--quiet',
            '--set','ON_ERROR_STOP=1','--command',READ_ONLY_SQL],Connection(url).env,'CONNECT_FAILED'))
        return public_identity(identity)
    except BackupError as error:return {'status':'FAILED','error':str(error)}
    except Exception:return {'status':'FAILED','error':'DIAGNOSTIC_INTERNAL_FAILURE'}

def compare(url):
    library=Libpq()
    report={'libpq_version':library.version,'clients':versions(),
        'expected_target_check':'NOT_APPLIED_CONNECTION_DIAGNOSIS_ONLY'}
    report['uri_shape']={'standard_scheme_prefix':url.startswith(('postgresql://','postgres://','postgresql+psycopg://')),
        'leading_whitespace':url!=url.lstrip(),'trailing_whitespace':url!=url.rstrip(),
        'has_control_characters':any(ord(c)<32 or ord(c)==127 for c in url)}
    try:
        converted=Connection(url).env
        report['option_validation']=option_shape(converted)
    except BackupError as error:
        converted=None;report['converted_parse_error']=str(error)
    try:
        native=library.parse(url)
        if converted is not None:
            report['parameter_equivalence']={key:converted.get(ENV_KEYS.get(key,''))==value
                for key,value in native.items()}
    except BackupError as error:report['parameter_parse_error']=str(error)
    # Both children share the same runner, PATH, libpq and original secret.
    # No URL, username or password in argv, output, artifact or exception text.
    env={k:v for k,v in os.environ.items() if k in ('PATH','HOME','LANG','LC_ALL','TZ','TMPDIR','SSL_CERT_FILE')}
    env.update(PGPASSFILE=os.devnull,PGSERVICEFILE=os.devnull,PGCONNECT_TIMEOUT='15',
        LC_ALL='C',ROBO_DIAGNOSTIC_URL=url)
    for mode in ('native','converted'):
        try:
            result=subprocess.run([sys.executable,'-m','scripts.postgres_backup_diagnose','--probe',mode],
                env=env,cwd=Path(__file__).resolve().parents[1],capture_output=True,text=True,timeout=60)
            # libpq may emit notices; capture/discard them, never log them.
            report[mode]=json.loads(result.stdout) if result.returncode==0 else {
                'status':'FAILED','error':'DIAGNOSTIC_SUBPROCESS_FAILED'}
        except subprocess.TimeoutExpired:report[mode]={'status':'FAILED','error':'CONNECT_TIMEOUT'}
        except Exception:report[mode]={'status':'FAILED','error':'DIAGNOSTIC_INTERNAL_FAILURE'}
    report['same_connected_database']=(report['native'].get('status')==report['converted'].get('status')=='CONNECTED_READ_ONLY'
        and report['native']['identity_fingerprint']==report['converted']['identity_fingerprint'])
    return report

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--probe',choices=['native','converted'])
    parser.add_argument('--target',choices=TARGETS,default='design')
    parser.add_argument('--output-dir',type=Path)
    args=parser.parse_args()
    if args.probe:
        print(json.dumps(probe(os.environ.get('ROBO_DIAGNOSTIC_URL',''),args.probe)));return 0
    try:report={'target':args.target,**compare(os.environ.get(TARGETS[args.target],''))}
    except BackupError as error:report={'target':args.target,'error':str(error)}
    except Exception:report={'target':args.target,'error':'DIAGNOSTIC_INTERNAL_FAILURE'}
    if args.output_dir:
        args.output_dir.mkdir(parents=True,exist_ok=True);args.output_dir.chmod(0o700)
        manifest=args.output_dir/f'robo_{args.target}_connection.json'
        manifest.write_text(json.dumps(report,indent=2)+'\n');manifest.chmod(0o600)
    print(json.dumps(report,indent=2))
    return int(not report.get('same_connected_database',False))

if __name__=='__main__':raise SystemExit(main())
