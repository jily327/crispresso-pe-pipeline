"""Fail-closed leaf comparison; each waived difference needs exact values/evidence.

No wildcard or recursive drop-all-provenance option. Review waivers independently.
"""
import argparse,json
from common import read,digest
MISSING={'__audit_missing__':True}
def differences(a,b,path=''):
    if type(a) is not type(b):return [{'pointer':path,'left':a,'right':b}]
    if isinstance(a,dict):
        result=[]
        for k in sorted(set(a)|set(b)):
            p=path+'/'+k.replace('~','~0').replace('/','~1')
            if k not in a or k not in b:result.append({'pointer':p,'left':a.get(k,MISSING),'right':b.get(k,MISSING)})
            else:result+=differences(a[k],b[k],p)
        return result
    if isinstance(a,list):
        if len(a)!=len(b):return [{'pointer':path,'left':a,'right':b}]
        return [d for i,(x,y) in enumerate(zip(a,b)) for d in differences(x,y,path+'/'+str(i))]
    return [] if a==b else [{'pointer':path,'left':a,'right':b}]
def compare(a,b,waivers=()):
    diff=differences(a,b);indexed={w['pointer']:w for w in waivers}
    if len(indexed)!=len(waivers):raise ValueError('duplicate waiver')
    used=set();unexplained=[]
    for d in diff:
        w=indexed.get(d['pointer'])
        if w and w.get('reason') and w.get('evidence') and w.get('left_sha256')==digest(d['left']) and w.get('right_sha256')==digest(d['right']):used.add(d['pointer'])
        else:unexplained.append(d)
    if used!=set(indexed):raise ValueError('unused or invalid waiver')
    return {'differences':diff,'unexplained':unexplained,'waivers_used':sorted(used)}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('left');p.add_argument('right');p.add_argument('--waivers');a=p.parse_args()
    result=compare(read(a.left),read(a.right),read(a.waivers) if a.waivers else [])
    print(json.dumps(result,indent=2));raise SystemExit(bool(result['unexplained']))
