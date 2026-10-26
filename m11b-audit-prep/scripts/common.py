"""Strict byte/JSON helpers for independent audit tooling, not application code."""
import hashlib,json,math
from pathlib import Path

def strict_json(data):
    def pairs(items):
        out={}
        for k,v in items:
            if k in out:raise ValueError('duplicate JSON key: '+k)
            out[k]=v
        return out
    def bad(x):raise ValueError('nonfinite JSON: '+x)
    def finite(x):
        value=float(x)
        if not math.isfinite(value):raise ValueError('nonfinite number')
        return value
    return json.loads(data,object_pairs_hook=pairs,parse_constant=bad,parse_float=finite)

def read(path):return strict_json(Path(path).read_bytes())
def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False)
def digest(value):return hashlib.sha256(canonical(value).encode()).hexdigest()
def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def fields(rows):
    out={}
    for row in rows:
        if row['name'] in out:raise ValueError('duplicate field')
        out[row['name']]=None if row['value'] is None else strict_json(row['value'])
    return out
