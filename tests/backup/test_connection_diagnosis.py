"""Diagnostics never expose credentials or raw error text."""
import json
import pytest
from scripts.postgres_backup import BackupError, Connection, connection_error
from scripts.postgres_backup_diagnose import Libpq, compare, option_shape
from tests.backup.test_postgres_backup import cluster

@pytest.mark.parametrize('message,code',[
    ('PRIVATE invalid channel_binding value: "PRIVATE"','CONNECT_CHANNEL_BINDING_INVALID'),
    ('PRIVATE invalid sslmode value: "PRIVATE"','CONNECT_TLS_MODE_INVALID'),
    ('PRIVATE invalid target_session_attrs value: "PRIVATE"','CONNECT_TARGET_SESSION_INVALID'),
    ('PRIVATE channel binding required but unavailable','CONNECT_CHANNEL_BINDING_FAILED'),
    ('PRIVATE server does not support SSL','CONNECT_TLS_UNAVAILABLE'),
    ('PRIVATE password authentication failed','CONNECT_AUTH_FAILED'),
    ('PRIVATE invalid percent-encoded token','CONNECT_URI_ENCODING_INVALID'),
    ('PRIVATE extra key/value separator "=" in URI query parameter','CONNECT_URI_EXTRA_EQUALS'),
    ('PRIVATE unexpected spaces found','CONNECT_URI_UNENCODED_SPACE'),
    ('PRIVATE missing "=" after','CONNECT_URI_SYNTAX_INVALID'),
    ('PRIVATE could not translate host name','CONNECT_DNS_FAILED'),
    ('PRIVATE timeout expired','CONNECT_TIMEOUT'),
    ('PRIVATE database "PRIVATE" does not exist','CONNECT_DATABASE_MISSING'),
    ('PRIVATE unexpected failure','CONNECT_FAILED'),
])
def test_fixed_error_codes_only(message,code):
    assert connection_error(message)==code
    assert 'PRIVATE' not in connection_error(message)

def test_native_and_converted_use_same_secret_and_read_only_database(cluster,monkeypatch):
    url=cluster.url+'?application_name=backup%20fixture&channel_binding=prefer&target_session_attrs=read-write&connect_timeout=2'
    monkeypatch.setenv('BACKUP_AUTH_DATABASE','deliberately-wrong-unrelated-approval')
    result=compare(url)
    assert result['same_connected_database']
    assert all(result['parameter_equivalence'].values())
    assert result['native']['read_only'] and result['converted']['read_only']
    assert url not in json.dumps(result)
    assert result['expected_target_check']=='NOT_APPLIED_CONNECTION_DIAGNOSIS_ONLY'

def test_native_uri_parser_keeps_literal_plus_and_decodes_percent_once():
    # URI encoding is not HTML form query encoding.
    url='postgresql://fixture:p%2B%2525@localhost/db?application_name=a+b%2Bc%20d&options=-c%20search_path%3Dpublic'
    parsed=Libpq().parse(url)
    assert parsed['password']=='p+%25'
    assert parsed['application_name']=='a+b+c d'
    converted=Connection(url).env
    assert converted['PGAPPNAME']==parsed['application_name']
    assert converted['PGPASSWORD']==parsed['password']
    assert converted['PGOPTIONS']==parsed['options']

@pytest.mark.parametrize('query,code',[
    ('channel_binding=require=PRIVATE','CONFIG_URI_QUERY_SEPARATOR_INVALID'),
    ('application_name=bad%ZZ','CONFIG_URI_ENCODING_INVALID'),
    ('application_name=bad%00','CONFIG_URI_ENCODING_INVALID'),
])
def test_malformed_uri_query_is_rejected_without_logging_value(query,code):
    with pytest.raises(BackupError,match=code):
        Connection('postgresql://fixture:PRIVATE@localhost/db?'+query)

@pytest.mark.parametrize('control',['\n','\r','\t'])
def test_secret_lines_are_not_silently_joined(control):
    url='postgresql://fixture:PRIVATE@localhost/db?channel_binding=require'+control+'OTHER=PRIVATE'
    with pytest.raises(BackupError,match='CONFIG_URI_CONTROL_CHARACTERS'):
        Connection(url)

def test_invalid_security_option_shape_never_prints_its_value():
    result=option_shape({'PGCHANNELBINDING':"require PRIVATE='PRIVATE'",'PGSSLMODE':'require'})
    assert not result['channel_binding']['recognized']
    assert result['channel_binding']['has_quote'] and result['channel_binding']['has_assignment_separator']
    assert result['channel_binding']['has_whitespace']
    assert result['sslmode']['value']=='require'
    assert 'PRIVATE' not in json.dumps(result)
