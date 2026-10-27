"""Non-audio plugin catalog refresh; keep disk/scan work outside playback."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json
import os
import time
from app.layout import bus_targets

class PluginRefresh:
    def __init__(self,root,runtime=Path('/run/machinista-lv2')):
        self.root=Path(root);self.runtime=Path(runtime);self.next=0;self.revision=None
        self.executor=ThreadPoolExecutor(max_workers=1,thread_name_prefix='lv2-catalog');self.future=None
    def scan(self):
        import subprocess
        return json.loads(subprocess.check_output(['/usr/bin/nice','-n','15',str(self.root/'build/audio_engine'),'--plugins'],text=True,timeout=15))
    def poll(self,app,audio,now):
        if now<self.next:return
        self.next=now+.5
        if not self.runtime.is_dir():return
        busy=bool(app.playing or app.recording or app.capture_started is not None or app.capture_armed or audio.recorder or getattr(audio,'native_capture',None))
        used=sorted({p['uri'] for target in bus_targets(app.project).values() for p in target.get('plugins',[])})
        try:
            temporary=self.runtime/'in-use.json.tmp'
            temporary.write_text(json.dumps(dict(busy=busy,uris=used,pid=os.getpid())))
            os.replace(temporary,self.runtime/'in-use.json')
            revision=json.loads((self.runtime/'revision.json').read_text())['revision']
        except (OSError,ValueError,KeyError):return
        if self.future is not None and self.future.done() and not busy:
            future,self.future=self.future,None
            try:
                catalog=future.result();app.plugin_catalog=catalog;audio.plugin_metadata=catalog
                app.message='PLUGINS UPDATED'
                temporary=self.runtime/'catalog-applied.json.tmp'
                temporary.write_text(json.dumps(dict(revision=self.revision,uris=[p['uri'] for p in catalog])))
                os.replace(temporary,self.runtime/'catalog-applied.json')
            except Exception:app.message='PLUGIN SCAN FAILED';self.revision=None
        if not busy and self.future is None and revision!=self.revision:
            self.revision=revision;self.future=self.executor.submit(self.scan)
    def close(self):self.executor.shutdown(wait=False,cancel_futures=True)
