"""Display-only sample cursors, measured by the native audio thread.

One visible sample is watched at 30 Hz. No file reads, PCM work or speculative
wall-clock playback are performed here. Stale replies expire automatically.
"""
import math
import time
from app.layout import PREVIEW,SAMPLE_SLOTS,ZONE_BASE

WAVE_PAGES=('SAMPLE EDIT','CHOP','ZONE','STRETCH','SAMPLING','PAD','CHANNEL','SAMPLER','BROWSE')


def visible_path(app):
    if app.page not in WAVE_PAGES:return None
    if app.page=='BROWSE':
        selected=app.browser.selected()
        if selected is None:return None
        return app.browser_decoded.get(str(selected),str(selected))
    if app.page=='ZONE':return (app.zone() or {}).get('sample')
    if app.page in ('PAD','CHANNEL','SAMPLER') and app.control_level!=2:return None
    return app.track().get('sample')


def position(app,path,now=None):
    state=getattr(app,'wave_playback',None)
    if not state or not path or str(path)!=state.get('path'):return None
    now=time.monotonic() if now is None else now
    if now-state['stamp']>.2:return None
    return state['frame']


class WavePlayback:
    def __init__(self):
        self.key=None;self.token=0;self.next_poll=0;self.path=None;self.mapping=None

    def update(self,app,audio,now):
        if now<self.next_poll:return
        self.next_poll=now+1/30
        path=visible_path(app);slot=None;signature=None;mapping=None;bus=app.group*16+app.pad
        preview=getattr(audio,'wave_preview',None)
        # Stretch audition uses a temporary sample, mapped back to its source.
        if app.page=='STRETCH' and path and preview and preview[0]==str(path):
            slot=PREVIEW;signature=preview;mapping=preview[1:]
        elif path:
            # Only this Sound's 128 zones and shared preview can be relevant.
            for candidate in (PREVIEW,bus,*range(ZONE_BASE+bus*128,ZONE_BASE+(bus+1)*128)):
                signature_candidate=audio.loaded.get(candidate)
                if signature_candidate and signature_candidate[0]==str(path):
                    slot=candidate;signature=signature_candidate;break
        key=(bus,str(path) if path else None,slot,signature)
        if key!=self.key:
            self.key=key;self.token+=1;self.path=str(path) if path else None;self.mapping=mapping
            app.wave_playback=None
            audio.command(f'wave_watch {self.token if slot is not None else 0} {bus} {slot if slot is not None else SAMPLE_SLOTS}')
        if slot is not None:audio.command('wave_status')
        elif getattr(app,'wave_playback',None):app.wave_playback=None

    def receive(self,app,event,now):
        if event.get('kind')!='wave_position':return False
        if event.get('token')!=self.token:return True
        point=event.get('frame')
        if event.get('active') and isinstance(point,(int,float)) and math.isfinite(point):
            if self.mapping:
                first,last,rendered_first,rendered_last=self.mapping
                point=first+(point-rendered_first)*(last-first)/max(1,rendered_last-rendered_first)
            app.wave_playback=dict(path=self.path,frame=point,stamp=now)
        else:app.wave_playback=None
        return True
