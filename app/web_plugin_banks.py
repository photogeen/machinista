"""Data-only preset-bank management; never changes the current Sound."""
from app.plugin_profiles import profiles,banks,bank_folder,_cache
from app.plugin_bank_import import import_bank,MAX_SIZE

def removable(p,identity):
    return identity!='init' and not (p['id']=='machinista-synth' and (identity=='factory' or identity.startswith('category-')))

def listing(root):
    return [dict(id=p['id'],uri=p['uri'],name=p['title'],banks=[dict(id=b['id'],name=b['name'],patches=len(b['patches']),canDelete=removable(p,b['id'])) for b in banks(root,p)]) for p in profiles() if p['provider']=='parameter-bank']

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
    if not p or not isinstance(bank,str) or not re.fullmatch('[A-Za-z0-9_-]{1,128}',bank) or not removable(p,bank):raise ValueError('Invalid or built-in preset bank.')
    path=bank_folder(root,p)/(bank+'.json')
    if path.is_symlink() or path.parent.is_symlink():raise ValueError('Unsafe preset bank.')
    path.unlink();_cache.clear()
    from app.bank_sounds import remove_snapshots
    remove_snapshots(root,p['uri'],bank)
    return dict(ok=True)
