"""Data-only preset-bank management; never changes the current Sound."""
from app.plugin_profiles import profiles,banks,bank_folder,_cache
from app.plugin_bank_import import import_bank,MAX_SIZE

def listing(root):
    return [dict(id=p['id'],name=p['title'],banks=[dict(id=b['id'],name=b['name'],patches=len(b['patches']),canDelete=b['id'] not in ('init','factory')) for b in banks(root,p)]) for p in profiles() if p['provider']=='parameter-bank']

def upload(root,name,identifier,stream,length):
    if not 0<length<=MAX_SIZE:raise ValueError('Maximum 8 MiB per preset bank.')
    p=next((v for v in profiles() if v['id']==identifier and v['provider']=='parameter-bank'),None)
    if not p or not name.lower().endswith(tuple(p.get('extensions',['.fxb','.fxp','.json']))):raise ValueError('Choose a compatible preset bank (Dexed: SYX/JSON; OB-Xd: FXB/FXP/JSON; RaffoSynth: DAT/JSON).')
    data=stream.read(length)
    if len(data)!=length:raise ValueError('Upload incomplete.')
    return import_bank(root,identifier,name,data)

def delete(root,identifier,bank):
    import re
    p=next((v for v in profiles() if v['id']==identifier and v['provider']=='parameter-bank'),None)
    if not p or not isinstance(bank,str) or not re.fullmatch('[0-9a-f]{24}',bank):raise ValueError('Invalid preset bank.')
    path=bank_folder(root,p)/(bank+'.json')
    if path.is_symlink():raise ValueError('Unsafe preset bank.')
    path.unlink();_cache.clear();return dict(ok=True)
