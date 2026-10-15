"""Small single-organization API-key RBAC boundary; keys are supplied via environment."""
import hmac
import json
import os


def policy(cfg):
    mode=os.getenv('FRAUD_SECURITY_MODE',cfg['security']['mode'])
    if mode not in {'local','authenticated'}: raise ValueError('Invalid security mode')
    raw=os.getenv(cfg['security']['keys_env'],'{}')
    keys=json.loads(raw)
    if mode=='authenticated' and not keys: raise ValueError('Authenticated mode requires FRAUD_API_KEYS')
    for token,identity in keys.items():
        if len(token)<32 or identity.get('role') not in {'analyst','viewer','scorer'} or not identity.get('actor'):
            raise ValueError('API keys require 32+ characters and a named analyst/viewer/scorer role')
    return mode,keys


def identify(token,keys):
    for secret,identity in keys.items():
        if hmac.compare_digest(token,secret): return identity
    return None


def allowed(role,method,path):
    if role=='analyst': return True
    if role=='scorer': return method=='POST' and path in {'/score','/score/batch','/score/batch/csv'}
    return role=='viewer' and method=='GET'
