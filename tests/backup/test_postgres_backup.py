"""Real dumps/restores in uniquely named, loopback-only disposable databases."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4
import pytest
from scripts.postgres_backup import BackupError, Connection, check_version, host_key, same_database

ROOT = Path(__file__).resolve().parents[2]
AUTH = """
CREATE TABLE users (user_id bigserial PRIMARY KEY, email text NOT NULL UNIQUE,
 password_hash text NOT NULL, CONSTRAINT nonempty_email CHECK (length(email)>0));
CREATE INDEX users_email_lookup ON users(email);
"""
DESIGN = """
CREATE TABLE participants (participant_id text PRIMARY KEY);
CREATE TABLE accounts (account_id text PRIMARY KEY, participant_id text REFERENCES participants);
CREATE TABLE orders (order_id text PRIMARY KEY, account_id text NOT NULL REFERENCES accounts,
 asset_id text NOT NULL, effective_at date NOT NULL, status text NOT NULL DEFAULT 'filled');
CREATE TABLE trades (trade_id bigserial PRIMARY KEY, order_id text NOT NULL REFERENCES orders,
 account_id text NOT NULL REFERENCES accounts, execution_price numeric NOT NULL CHECK (execution_price>0),
 quantity numeric NOT NULL CHECK (quantity>0));
CREATE TABLE holdings_daily (account_id text NOT NULL REFERENCES accounts, date date NOT NULL,
 asset_id text NOT NULL, quantity numeric NOT NULL CHECK (quantity>=0), market_value numeric NOT NULL,
 PRIMARY KEY(account_id,date,asset_id));
CREATE TABLE nav_daily (account_id text NOT NULL REFERENCES accounts, date date NOT NULL,
 nav numeric NOT NULL CHECK (nav>0), cash_balance numeric NOT NULL CHECK(cash_balance>=0),
 PRIMARY KEY(account_id,date));
CREATE FUNCTION preserve_filled_order() RETURNS trigger LANGUAGE plpgsql AS $$
 BEGIN IF OLD.status='filled' THEN RAISE EXCEPTION 'fixture immutable order'; END IF; RETURN NEW; END $$;
CREATE TRIGGER immutable_order BEFORE UPDATE ON orders FOR EACH ROW EXECUTE FUNCTION preserve_filled_order();
"""
AUTH_DATA = "INSERT INTO users(email,password_hash) VALUES ('fixture@example.invalid','TEST-ONLY-HASH'); SELECT setval('users_user_id_seq',40,true);"
DESIGN_DATA = """
INSERT INTO participants VALUES ('fixture-p'); INSERT INTO accounts VALUES ('fixture-a','fixture-p');
INSERT INTO orders VALUES ('fixture-o','fixture-a','fixture-asset','2026-10-01','filled');
INSERT INTO trades(order_id,account_id,execution_price,quantity) VALUES ('fixture-o','fixture-a',100,8);
INSERT INTO holdings_daily VALUES ('fixture-a','2026-10-01','fixture-asset',8,800);
INSERT INTO nav_daily VALUES ('fixture-a','2026-10-01',1000,200);
SELECT setval('trades_trade_id_seq',70,true);
"""

class Cluster:
    def __init__(self, url):
        self.url, self.databases, self.roles = url, [], []
        self.admin = Connection(url)
    def db_url(self, name, user=None):
        p = urlsplit(self.url)
        netloc = p.netloc if user is None else user+'@'+p.hostname+':'+str(p.port)
        return urlunsplit((p.scheme,netloc,'/'+name,p.query,''))
    def create(self, prefix='backup_fixture'):
        name = prefix+'_'+uuid4().hex[:12]
        self.admin.query('CREATE DATABASE "'+name+'"')
        self.databases.append(name)
        return self.db_url(name)
    def sources(self, empty=False):
        auth, design = self.create(), self.create()
        Connection(auth).query(AUTH + ('' if empty else AUTH_DATA))
        Connection(design).query(DESIGN + ('' if empty else DESIGN_DATA))
        return auth, design
    def restricted(self, destination):
        # Passwordless trust is local only; CI uses a fixed disposable password.
        role = 'backup_test_role_'+uuid4().hex[:12]
        self.admin.query('CREATE ROLE '+role+" LOGIN PASSWORD 'disposable-ci-only' NOSUPERUSER")
        self.roles.append(role)
        Connection(destination).query('REVOKE CREATE ON SCHEMA public FROM PUBLIC')
        p=urlsplit(destination)
        return urlunsplit((p.scheme,role+':disposable-ci-only@'+p.hostname+':'+str(p.port),p.path,p.query,''))
    def close(self):
        for name in reversed(self.databases):
            self.admin.query('DROP DATABASE "'+name+'" WITH (FORCE)')
        for role in self.roles:
            self.admin.query('DROP ROLE '+role)

@pytest.fixture
def cluster():
    url = os.environ.get('BACKUP_TEST_ADMIN_URL','')
    if not url:
        if os.environ.get('BACKUP_REQUIRE_RESTORE_TESTS')=='1':
            pytest.fail('BACKUP_TEST_ADMIN_URL required; restoration must not be skipped')
        pytest.skip('Disposable PostgreSQL not configured')
    p = urlsplit(url)
    if p.hostname not in ('127.0.0.1','localhost') or p.username!='backup_test' or p.path!='/postgres' or not p.port:
        pytest.fail('Only the explicit loopback disposable backup_test cluster is accepted')
    value = Cluster(url)
    try:yield value
    finally:value.close()


def invoke(action, directory, sources=('', ''), destination='', args=(), extra=None):
    env = {k:v for k,v in os.environ.items() if k not in
        ('DATABASE_URL','CAPSTONE_DESIGN_DATABASE_URL','BACKUP_RESTORE_DATABASE_URL') and not k.startswith('BACKUP_AUTH_') and not k.startswith('BACKUP_DESIGN_')}
    env.update(DATABASE_URL=sources[0],CAPSTONE_DESIGN_DATABASE_URL=sources[1],BACKUP_RESTORE_DATABASE_URL=destination)
    env.update(extra or {})
    command=[sys.executable,str(ROOT/'scripts/postgres_backup.py'),action]
    if action=='backup':command += ['--output-dir',str(directory)]
    else:command += ['--dump',str(directory/'robo_auth.dump'),'--manifest',str(directory/'robo_auth.json'),'--acknowledge-isolated']
    result = subprocess.run(command+list(args),env=env,capture_output=True,text=True)
    assert not result.stderr, 'No raw subprocess errors may leak through CLI'
    return result.returncode,json.loads(result.stdout)


def signature(connection):
    constraints = connection.query("""SELECT json_agg(s ORDER BY table_name,constraint_name) FROM
        (SELECT c.relname table_name,k.conname constraint_name,k.contype,pg_get_constraintdef(k.oid) definition
        FROM pg_constraint k JOIN pg_class c ON c.oid=k.conrelid JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname='public' AND k.contype IN ('p','f','u','c','x')) s""")
    columns = connection.query("""SELECT json_agg(s ORDER BY table_name,ordinal_position) FROM
        (SELECT table_name,ordinal_position,column_name,data_type,is_nullable,column_default
        FROM information_schema.columns WHERE table_schema='public') s""")
    return constraints,columns

@pytest.mark.parametrize('empty',[False,True])
def test_real_dump_restore_data_schema_constraints_triggers_sequences(cluster,tmp_path,empty):
    sources = cluster.sources(empty)
    code, report=invoke('backup',tmp_path,sources)
    assert code==0 and report['status']=='SUCCESS'
    for target,source in zip(('auth','design'),sources):
        destination=cluster.create('robo_restore')
        env={**os.environ,'DATABASE_URL':sources[0],'CAPSTONE_DESIGN_DATABASE_URL':sources[1],
            'BACKUP_RESTORE_DATABASE_URL':destination}
        r=subprocess.run([sys.executable,str(ROOT/'scripts/postgres_backup.py'),'restore','--dump',str(tmp_path/f'robo_{target}.dump'),
            '--manifest',str(tmp_path/f'robo_{target}.json'),'--acknowledge-isolated'],env=env,capture_output=True,text=True)
        assert r.returncode==0,r.stdout
        assert not r.stderr
        recovered=json.loads(r.stdout)
        original=next(t for t in report['targets'] if t['target']==target)
        assert original['restore_verified'] is False and original['archive_check']=='TOC_ONLY_NOT_A_RESTORE'
        assert original['row_counts']==recovered['row_counts']
        a,b=Connection(source),Connection(destination)
        assert signature(a)==signature(b)
        if target=='auth':
            assert a.query('SELECT * FROM users ORDER BY user_id')==b.query('SELECT * FROM users ORDER BY user_id')
            assert a.query('SELECT last_value,is_called FROM users_user_id_seq')==b.query('SELECT last_value,is_called FROM users_user_id_seq')
            assert b.query("INSERT INTO users(email,password_hash) VALUES ('new@example.invalid','TEST-ONLY') RETURNING user_id").splitlines()[0]==('1' if empty else '41')
            with pytest.raises(BackupError):b.query("INSERT INTO users(email,password_hash) VALUES ('new@example.invalid','TEST-ONLY')")
            assert b.query("SELECT count(*) FROM pg_indexes WHERE indexname='users_email_lookup'")=='1'
        else:
            for table in ('accounts','orders','trades','holdings_daily','nav_daily'):
                assert a.query('SELECT * FROM '+table+' ORDER BY 1,2')==b.query('SELECT * FROM '+table+' ORDER BY 1,2')
            assert a.query('SELECT last_value,is_called FROM trades_trade_id_seq')==b.query('SELECT last_value,is_called FROM trades_trade_id_seq')
            assert b.query("SELECT count(*) FROM pg_trigger WHERE tgname='immutable_order'")=='1'
            with pytest.raises(BackupError):b.query("INSERT INTO orders VALUES ('bad','missing-account','asset','2026-10-01','filled')")
            if not empty:
                with pytest.raises(BackupError):b.query("INSERT INTO nav_daily VALUES ('fixture-a','2026-10-02',-1,200)")
                with pytest.raises(BackupError):b.query("UPDATE orders SET asset_id='changed' WHERE order_id='fixture-o'")


def test_missing_setting_preserves_peer_dump_and_fails_overall(cluster,tmp_path):
    auth,design=cluster.sources(empty=True)
    code,report=invoke('backup',tmp_path,('',design))
    assert code==1 and report['status']=='PARTIAL_SUCCESS'
    assert report['targets'][0]['error']=='CONFIG_MISSING'
    assert (tmp_path/'robo_design.dump').exists() and not (tmp_path/'robo_auth.dump').exists()


def test_missing_table_preserves_auth_backup(cluster,tmp_path):
    sources=cluster.sources()
    Connection(sources[1]).query('DROP TABLE nav_daily')
    code,report=invoke('backup',tmp_path,sources)
    assert code==1 and report['status']=='PARTIAL_SUCCESS'
    assert report['targets'][1]['error']=='REQUIRED_TABLE_MISSING:nav_daily'
    assert (tmp_path/'robo_auth.dump').exists() and not (tmp_path/'robo_design.dump').exists()


def test_missing_columns_distinguished_from_empty_tables(cluster,tmp_path):
    sources=cluster.sources(empty=True)
    Connection(sources[0]).query('ALTER TABLE users RENAME password_hash TO wrong_column')
    code,report=invoke('backup',tmp_path,sources)
    assert code==1 and report['targets'][0]['error']=='REQUIRED_COLUMNS_MISSING:users'
    assert report['targets'][1]['status']=='BACKED_UP'


def test_read_only_backup_role_can_inspect_constraints_without_monitor_privilege(cluster,tmp_path):
    sources=cluster.sources(empty=True)
    role='backup_test_readonly_'+uuid4().hex[:12]
    cluster.admin.query('CREATE ROLE '+role+" LOGIN PASSWORD 'disposable-ci-only' NOSUPERUSER")
    cluster.roles.append(role)
    Connection(sources[0]).query('REVOKE EXECUTE ON FUNCTION pg_catalog.pg_control_system() FROM PUBLIC')
    Connection(sources[0]).query('GRANT USAGE ON SCHEMA public TO '+role+'; GRANT SELECT ON ALL TABLES IN SCHEMA public TO '+role+'; GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO '+role)
    p=urlsplit(sources[0])
    readonly=urlunsplit((p.scheme,role+':disposable-ci-only@'+p.hostname+':'+str(p.port),p.path,p.query,''))
    code,report=invoke('backup',tmp_path,(readonly,sources[1]))
    assert code==0 and report['targets'][0]['row_counts']['users']==0
    assert report['targets'][0]['identity']['system_identifier'] is None
    assert (tmp_path/'robo_auth.dump').exists()


def test_connection_failure_never_prints_url_password_or_raw_error(cluster,tmp_path):
    _,design=cluster.sources()
    invalid='postgresql://backup_test:REDACTION_TEST_ONLY_SECRET@127.0.0.1:1/missing?connect_timeout=1'
    code,report=invoke('backup',tmp_path,(invalid,design))
    assert code==1 and report['status']=='PARTIAL_SUCCESS'
    assert report['targets'][0]['error']=='CONNECT_FAILED'
    logged=json.dumps(report)+'\n'+(tmp_path/'robo_auth.json').read_text()
    assert invalid not in logged and 'REDACTION_TEST_ONLY_SECRET' not in logged
    assert (tmp_path/'robo_design.dump').exists()


def test_alias_urls_to_same_database_are_rejected(cluster,tmp_path):
    auth,_=cluster.sources()
    alias=auth.replace('127.0.0.1','localhost')
    code,report=invoke('backup',tmp_path,(auth,alias))
    assert code==1 and all(t['error']=='SAME_DATABASE_TARGETS' for t in report['targets'])
    assert not list(tmp_path.glob('*.dump'))


def test_expected_identity_mismatch_and_inspection_only(cluster,tmp_path):
    sources=cluster.sources(empty=True)
    code,report=invoke('backup',tmp_path,sources,args=['--inspection-only'],extra={'BACKUP_AUTH_DATABASE':'wrong-database'})
    assert code==1 and report['targets'][0]['error']=='EXPECTED_TARGET_MISMATCH'
    assert report['targets'][1]['status']=='INSPECTED_ONLY'
    assert not list(tmp_path.glob('*.dump'))


def test_corrupt_archive_rejected_and_actual_restore_failure_is_fatal(cluster,tmp_path):
    sources=cluster.sources()
    assert invoke('backup',tmp_path,sources)[0]==0
    destination=cluster.create('robo_restore')
    original=(tmp_path/'robo_auth.dump').read_bytes()
    (tmp_path/'robo_auth.dump').write_bytes(b'corrupt archive')
    code,report=invoke('restore',tmp_path,sources,destination)
    assert code==1 and report['error']=='ARCHIVE_CHECKSUM_OR_MANIFEST_INVALID'
    # A damaged archive with a matching manifest reaches the actual restore tool.
    manifest=json.loads((tmp_path/'robo_auth.json').read_text())
    manifest['sha256']=hashlib.sha256(b'corrupt archive').hexdigest()
    (tmp_path/'robo_auth.json').write_text(json.dumps(manifest))
    code,report=invoke('restore',tmp_path,sources,destination)
    assert code==1 and report['error']=='RESTORE_FAILED'
    assert Connection(destination).query("SELECT count(*) FROM information_schema.tables WHERE table_schema='public'")=='0'
    # A valid archive must also fail for a real SQL/permission restore error.
    (tmp_path/'robo_auth.dump').write_bytes(original)
    manifest['sha256']=hashlib.sha256(original).hexdigest()
    (tmp_path/'robo_auth.json').write_text(json.dumps(manifest))
    restricted=cluster.restricted(destination)
    code,report=invoke('restore',tmp_path,sources,restricted)
    assert code==1 and report['error']=='RESTORE_FAILED'
    assert Connection(destination).query("SELECT count(*) FROM information_schema.tables WHERE table_schema='public'")=='0'


def test_nonempty_restore_destination_is_preserved(cluster,tmp_path):
    sources=cluster.sources()
    assert invoke('backup',tmp_path,sources)[0]==0
    destination=cluster.create('robo_restore')
    Connection(destination).query('CREATE TABLE must_keep(id int PRIMARY KEY); INSERT INTO must_keep VALUES (123)')
    code,report=invoke('restore',tmp_path,sources,destination)
    assert code==1 and report['error']=='RESTORE_DESTINATION_NOT_EMPTY'
    assert Connection(destination).query('SELECT id FROM must_keep')=='123'


def test_version_boundaries_and_neon_pooler_alias(monkeypatch):
    clients={'psql':17,'pg_dump':17,'pg_restore':17}
    with pytest.raises(BackupError,match='SERVER_VERSION_INCOMPATIBLE'):check_version({'server_version_num':'180000'},clients)
    with pytest.raises(BackupError,match='RESTORE_VERSION_INCOMPATIBLE'):check_version({'server_version_num':'140019'},clients,True)
    assert check_version({'server_version_num':'170001'},clients)==17
    assert host_key('ep-example-pooler.eu-central-1.aws.neon.tech')==host_key('ep-example.eu-central-1.aws.neon.tech')
    assert Connection('postgres://name:123@localhost:5432/db?sslmode=require').endpoint==Connection('postgresql+psycopg://other:456@localhost/db').endpoint
    mapped=Connection('postgresql://name@localhost/db?channel_binding=require&target_session_attrs=read-write&application_name=backup-fixture&connect_timeout=2').env
    assert mapped['PGCHANNELBINDING']=='require' and mapped['PGTARGETSESSIONATTRS']=='read-write'
    assert mapped['PGAPPNAME']=='backup-fixture' and mapped['PGCONNECT_TIMEOUT']=='2'
    assert not same_database({'database':'a','database_oid':1,'server_addr':'127.0.0.1','server_port':5432},
        {'database':'b','database_oid':2,'server_addr':'127.0.0.1','server_port':5432})
    from types import SimpleNamespace
    from scripts.postgres_backup import tool
    monkeypatch.setattr(subprocess,'run',lambda *a,**k:SimpleNamespace(returncode=1,stdout='',
        stderr='PRIVATE_URL_OR_PASSWORD channel binding required but unavailable'))
    with pytest.raises(BackupError) as failure:
        tool(['psql'],code='CONNECT_FAILED')
    assert str(failure.value)=='CONNECT_CHANNEL_BINDING_FAILED'
