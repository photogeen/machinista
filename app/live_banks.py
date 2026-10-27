"""Warm banks before live input starts; refresh metadata outside input dispatch."""
from concurrent.futures import ThreadPoolExecutor
from app import plugin_profiles

class LiveBanks:
    def __init__(self,root):
        self.root=root;self.profiles=tuple(p for p in plugin_profiles.profiles() if p['provider']=='parameter-bank')
        # Startup only: no controller or audio callbacks are running yet.
        self.entries={p['id']:plugin_profiles.read_banks(root,p) for p in self.profiles}
        self.future=None;self.next=0;self.closed=False;self.sound_signature=None;self.enabled=set()
        from app.sound_library import worker_priority
        self.worker=ThreadPoolExecutor(max_workers=1,thread_name_prefix='preset-banks',initializer=worker_priority)
        plugin_profiles._live_banks[str(root)]=self
    def scan(self):
        enabled=set(self.enabled)
        previous=self.entries
        entries={p['id']:plugin_profiles.read_banks(self.root,p,previous.get(p['id'])) for p in self.profiles}
        signature=(tuple(sorted(enabled)),tuple((p['id'],entries[p['id']][2]) for p in self.profiles))
        if signature!=self.sound_signature:
            from app.bank_sounds import sync
            sync(self.root,entries,enabled);self.sound_signature=signature
        return entries
    def poll(self,app,now):
        if self.closed:return
        # Preserve the current catalog throughout playback/capture. New banks
        # appear after transport stops, without rebuilding the active instrument.
        busy=any(getattr(app,k,False) for k in ('playing','recording','capture_armed','autosampling','busy'))
        busy=busy or getattr(app,'capture_started',None) is not None
        if busy:return
        if self.future is not None:
            if not self.future.done():return
            future,self.future=self.future,None
            try:self.entries=future.result()
            except Exception as error:print('Preset bank refresh: '+str(error),flush=True)
        if now>=self.next:
            self.next=now+1
            self.enabled={p['uri'] for p in getattr(app,'plugin_catalog',[]) if p.get('supported') and p.get('kind')=='INSTRUMENT'}
            self.future=self.worker.submit(self.scan)
    def close(self):
        self.closed=True
        if plugin_profiles._live_banks.get(str(self.root)) is self:plugin_profiles._live_banks.pop(str(self.root))
        self.worker.shutdown(wait=False,cancel_futures=True)
