"""Portable project bundles with collected samples and relative references."""
from app.layout import SOUNDS,GROUP_BASE,MASTER,PREVIEW,CLICK,ZONE_BASE,bus_targets
import copy
import hashlib
import json
from pathlib import Path
import shutil
from app.storage import save_json


def sample_references(project):
    for group in project['groups']:
        for track in group['pads']:
            if track.get('sample'):yield track,'sample'
            if track.get('slice_source',{}).get('sample'):yield track['slice_source'],'sample'
            for zone in track.get('zones',[]):
                if zone.get('sample'):yield zone,'sample'


def resolve_assets(project,base):
    for obj,key in sample_references(project):
        path=Path(obj[key]);obj[key]=str(path if path.is_absolute() else (Path(base)/path).resolve())
    for target in [project]+project['groups']+[pad for g in project['groups'] for pad in g['pads']]:
        for plugin in target.get('plugins',[]):
            if plugin.get('state'):
                path=Path(plugin['state']);plugin['state']=str(path if path.is_absolute() else (Path(base)/path).resolve())
    return project


def collect_project(project,folder):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True);samples=folder/'samples';samples.mkdir(exist_ok=True)
    result=copy.deepcopy(project);copied={}
    # Verify sources before publishing the project manifest.
    for obj,key in sample_references(result):
        source=Path(obj[key]).resolve()
        if source not in copied:
            digest=hashlib.sha256()
            with source.open('rb') as stream:
                for chunk in iter(lambda:stream.read(1024*1024),b''):digest.update(chunk)
            name=source.stem[:40]+'-'+digest.hexdigest()[:16]+source.suffix
            target=samples/name
            if not target.exists():shutil.copy2(source,target)
            copied[source]=str(target.relative_to(folder))
        obj[key]=copied[source]
    for bus,target in bus_targets(result).items():
        for index,plugin in enumerate(target.get('plugins',[])):
            if plugin.get('state') and Path(plugin['state']).is_file():
                destination=folder/'plugins'/f'{bus}-{index}';shutil.copytree(Path(plugin['state']).parent,destination,dirs_exist_ok=True)
                plugin['state']=str((destination/'state.ttl').relative_to(folder))
    manifest=folder/'Project.json';save_json(manifest,result);return manifest


def relative_assets(project,base):
    result=copy.deepcopy(project);base=Path(base).resolve()
    for obj,key in sample_references(result):
        path=Path(obj[key]).resolve()
        if path.is_relative_to(base):obj[key]=str(path.relative_to(base))
    for target in [result]+result['groups']+[pad for g in result['groups'] for pad in g['pads']]:
        for plugin in target.get('plugins',[]):
            if plugin.get('state'):
                path=Path(plugin['state']).resolve()
                if path.is_relative_to(base):plugin['state']=str(path.relative_to(base))
    return result
