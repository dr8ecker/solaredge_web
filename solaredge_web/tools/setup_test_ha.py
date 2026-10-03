# Copyright (c) 2026 8ecker.de
"""Onboard a dedicated empty HA test container; never prints generated credentials."""
import argparse
import json
import os
import secrets
import time
from pathlib import Path
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if urlsplit(args.url).hostname != 'seweb-history-ha':
        raise SystemExit('Only the dedicated test container is supported')
    token = None

    def call(path, data=None, *, form=False):
        body = (urlencode(data).encode() if form else json.dumps(data).encode()) if data is not None else None
        headers = {'Content-Type':'application/x-www-form-urlencoded' if form else 'application/json'}
        if token:
            headers['Authorization'] = 'Bearer '+token
        with urlopen(Request(args.url+path, data=body, headers=headers), timeout=10) as response:
            return json.load(response)

    for _ in range(120):
        try:
            call('/api/onboarding')
            break
        except Exception:
            time.sleep(1)
    else:
        raise SystemExit('Dedicated HA did not become ready')
    client = args.url+'/'
    result = call('/api/onboarding/users', {'name':'CI test','username':'sewebtest',
                  'password':secrets.token_urlsafe(32), 'client_id':client, 'language':'de'})
    result = call('/auth/token', {'grant_type':'authorization_code', 'code':result['auth_code'], 'client_id':client}, form=True)
    token = result['access_token']
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result))
    os.chmod(args.output, 0o600)
    for step in ('core_config', 'analytics'):
        call('/api/onboarding/'+step, {})
    call('/api/onboarding/integration', {'client_id':client, 'redirect_uri':client})
    print('Dedicated HA test account ready; token saved privately.')


if __name__ == '__main__':
    main()
