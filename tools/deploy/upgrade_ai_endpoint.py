#!/usr/bin/env python3
"""Add the AI endpoint concurrency field to an existing local instance."""
import argparse
from pathlib import Path
import subprocess

SELECT_ENDPOINT = '''SELECT ENDPOINT_ID, ENDPOINT_NAME, AI_MODEL_NAME, SCOPE, URL,
ACCESS_KEY, PROVIDER, REQUEST_MODEL_NAME, PARAMETERS, REQUEST_TRANSFORM_FN,
RESPONSE_TRANSFORM_FN, MAX_CONCURRENCY FROM oceanbase.__all_ai_model_endpoint
WHERE ENDPOINT_ID != -1'''


def upgrade(query):
    columns = query("SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA='oceanbase' AND TABLE_NAME='__all_ai_model_endpoint' AND COLUMN_NAME='max_concurrency'")
    old_setting = query("SELECT VALUE FROM oceanbase.V$OB_PARAMETERS WHERE NAME='enable_sys_table_ddl' LIMIT 1").strip().lower()
    if old_setting not in ('true', 'false', '1', '0'):
        raise RuntimeError('cannot determine enable_sys_table_ddl setting: ' + old_setting)
    try:
        query('ALTER SYSTEM SET enable_sys_table_ddl = true')
        if int(columns.strip()) == 0:
            query('ALTER TABLE oceanbase.__all_ai_model_endpoint ADD COLUMN max_concurrency BIGINT NOT NULL DEFAULT 16')
        query('CREATE OR REPLACE VIEW oceanbase.DBA_OB_AI_MODEL_ENDPOINTS AS ' + SELECT_ENDPOINT)
    finally:
        query('ALTER SYSTEM SET enable_sys_table_ddl = ' + old_setting)
    query('SELECT MAX_CONCURRENCY FROM oceanbase.DBA_OB_AI_MODEL_ENDPOINTS LIMIT 1')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=10000)
    parser.add_argument('--client', default=str(Path(__file__).resolve().parents[2] / 'deps/3rd/u01/obclient/bin/obclient'))
    args = parser.parse_args()
    def query(sql):
        return subprocess.check_output([args.client, '--no-defaults', '--batch', '--raw', '--skip-column-names',
                                        '-h', args.host, '-P', str(args.port), '-uroot', '-e', sql], text=True)
    upgrade(query)
    print('AI endpoint schema upgrade completed; existing rows and settings preserved.')


if __name__ == '__main__':
    main()
