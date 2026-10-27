"""Names from the user's prepared ROM catalog; no emulator/ROM dependency.

Cached on the application thread. Detached display workers receive strings only.
Missing or malformed optional catalogs preserve the normal numeric LV2 controls.
"""
import json
import time
from pathlib import Path

URI='urn:machinista:ports:virtualjv'
_cache={}
_ports_cache={}
SPECS=tuple(json.loads(Path(__file__).with_name('virtualjv_parameters.json').read_text()))
SPEC_BY_SYMBOL={p['symbol']:p for p in SPECS}
PRESET=-1000


def banks(root):
    path=Path(root)/'presets/virtualjv/prepared/catalog.json';key=str(path);now=time.monotonic()
    previous=_cache.get(key)
    if previous and now<previous[0]:return previous[2]
    result={};stamp=None
    try:
        stat=path.stat();stamp=(stat.st_mtime_ns,stat.st_size)
        if previous and stamp==previous[1]:result=previous[2]
        elif stat.st_size<=2*1024**2 and not path.is_symlink():
            data=json.loads(path.read_text())
            for row in data.get('banks',[]):
                if type(row.get('id')) is not int or not 0<=row['id']<=28 or not isinstance(row.get('name'),str):continue
                patches=row.get('patches',[])
                if not isinstance(patches,list) or not 1<=len(patches)<=256 or not all(isinstance(v,str) for v in patches):continue
                result[row['id']]=dict(row,name=row['name'][:128],patches=tuple(v[:128] for v in patches))
            table=path.with_name('catalog.tsv')
            if table.is_file() and not table.is_symlink() and table.stat().st_size<=65536:
                for line in table.read_text().splitlines():
                    values=line.split('\t')
                    if len(values)!=9 or values[0]!='bank':continue
                    index=int(values[1]);asset=Path(values[8]);start=int(values[4])
                    if index not in result or asset.is_absolute() or '..' in asset.parts or not asset.parts or asset.parts[0]!='assets':continue
                    file=path.parent/asset
                    if file.is_symlink() or not file.resolve().is_relative_to(path.parent.resolve()):continue
                    size=file.stat().st_size
                    if 0<=start and start+len(result[index]['patches'])*362<=size<=8388608:result[index]['_table']=(file,start)
    except (OSError,ValueError,TypeError,AttributeError):result={}
    if len(_cache)>8:_cache.clear()
    _cache[key]=(now+1,stamp,result)
    return result


def presets(bank,rhythm=False):
    if not bank:return ()
    if not rhythm:return bank['patches']
    count=bank.get('drums',0)
    if type(count) is not int or not 0<=count<=16:return ()
    names=bank.get('drum_names',())
    return tuple(names[i] if i<len(names) and isinstance(names[i],str) else f'Rhythm {i+1:02}' for i in range(count))


def controls(root,selected,ports):
    if selected.get('uri')!=URI:return ports
    available=banks(root);values=selected.get('controls',{});bank_id=round(values.get('bank',0));program=round(values.get('program',0));rhythm=values.get('rhythm',0)>=.5
    key=(str(root),id(ports),id(available),bank_id,program,rhythm)
    if key in _ports_cache:return _ports_cache[key][2]
    bank=available.get(bank_id);image=None
    try:
        if not rhythm and bank and '_table' in bank and 0<=program<len(bank['patches']):
            file,start=bank['_table']
            with file.open('rb') as stream:stream.seek(start+362*program);image=stream.read(362)
            if len(image)!=362:image=None
    except OSError:pass
    result=[]
    for original in ports:
        port=original;symbol=port['symbol'];spec=SPEC_BY_SYMBOL.get(symbol)
        if symbol in ('bank','program'):
            port=dict(port,choice=True)
            if symbol=='bank':port['choices']=tuple((i,b['name']) for i,b in sorted(available.items()))
            else:port.update(name='PRESET',choices=tuple(enumerate(presets(bank,rhythm))))
        elif spec:
            if rhythm and not spec['kind']:continue
            port=dict(port,min=spec['min'],max=spec['max'],section=spec['section'],tone=spec['tone'],preset_parameter=not spec['kind'])
            if spec.get('choices'):port.update(choice=True,choices=tuple(enumerate(spec['choices'])))
            if symbol=='sustain':port.update(choice=True,choices=((0,'OFF'),(127,'ON')))
            if symbol=='pitch_bend':port['step']=128
            if spec['kind']==0 and image is not None:
                value=(image[spec['compact']]&spec['mask'])>>spec['shift']
                if spec['signed'] and value>=128:value-=256
                port['preset_value']=max(spec['min'],min(spec['max'],value+spec['add']))
            if spec.get('unit'):port['unit']=spec['unit']
        result.append(port)
    if len(_ports_cache)>32:_ports_cache.clear()
    _ports_cache[key]=(ports,available,result)
    return result


def effective(port,value):
    return port.get('preset_value',0) if port.get('preset_parameter') and value<=-999 else value


def reset_edits(selected):
    for param in SPECS:
        selected['controls'][param['symbol']]=param['default']


def names(root,selected):
    if selected and selected.get('uri')=='urn:machinista:ports:virtualjv-multi':
        from app.virtualjv_multi import selected_patch
        return names(root,selected_patch(selected))
    if not selected or selected.get('uri')!=URI:return None
    values=selected.get('controls',{});bank=banks(root).get(round(values.get('bank',0)))
    if not bank:return None
    patches=presets(bank,values.get('rhythm',0)>=.5);index=round(values.get('program',0))
    return bank['name'],patches[index] if 0<=index<len(patches) else f'Preset {index+1}'


def clamp_preset(root,selected):
    values=selected['controls'];bank=banks(root).get(round(values.get('bank',0)))
    choices=presets(bank,values.get('rhythm',0)>=.5)
    if choices:values['program']=max(0,min(len(choices)-1,round(values.get('program',0))))
