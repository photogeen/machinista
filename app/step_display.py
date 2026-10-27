"""Small immutable STEP snapshots; LCD drawing runs outside the clock process."""
import multiprocessing
import os
from app.ni_display import rect,label,softkey_label,finish_frame,width


def step_state(app):
    from app.ui_context import pinned,visible_message
    count=app.step_cell_count();unit=app.grid_ticks();velocities={}
    for (row,tick),event in app.notes().items():
        cell=tick//unit
        if row==app.pad and app.bank*16<=cell<min(count,app.bank*16+16):
            velocities[cell-app.bank*16]=max(velocities.get(cell-app.bank*16,0),event['velocity'])
    return dict(keys=app.softkeys(),active=tuple(app.active_softkeys()),
                title=app.transport_title() if app.playing or app.recording or app.count_remaining else 'STEP MODE',
                tempo=app.project['tempo'],position=app.pattern_position(),count=count,bank=app.bank,
                velocities=velocities,playhead=app.step_playhead_x(),
                grid=app.timing()['grid'] if app.timing()['grid_on'] else 'OFF',
                velocity=app.velocity_value,message=visible_message(app),pinned=pinned(app))


def step_frame(state):
    pixels=legacy_step_frame(state)
    from app.fokus import enabled,live
    return live(state,pixels) if enabled() else pixels


def legacy_step_frame(state):
    p=bytearray([1]*8192)
    for i,key in enumerate(state['keys']):
        x=i*43;w=40 if i==2 else 41;active=i in state['active']
        rect(p,x+1,1,w,10,0,active);softkey_label(p,x+1,w,key,1 if active else 0)
    rect(p,1,12,126,11,0);label(p,4,15,state['title'],1,bold=True,max_width=120)
    label(p,3,25,f'{state["tempo"]:.2f}')
    label(p,125-width(state['position'],True),25,state['position'],tabular_digits=True)
    for i in range(16):
        x=2+i*8
        if i%4==0:rect(p,x,36,1,11,0)
        if i in state['velocities']:
            vel=state['velocities'][i];rect(p,x+1,36,6,11,0,False)
            height=max(1,round(vel/127*9));rect(p,x+2,46-height,4,height,0)
    playhead=state['playhead']
    if playhead is not None:
        for y in range(34,50):p[y*128+playhead]^=1
    banks=max(1,(state['count']+15)//16)
    rect(p,1,51,126,4,0,False);rect(p,2+round(state['bank']*124/banks),52,max(1,124//banks),2,0)
    label(p,2,56,f'{state["grid"]} B{state["bank"]+1} V{state["velocity"]}')
    from app.fokus import enabled
    if state['message'] and not enabled():
        rect(p,0,55,128,8,0);label(p,2,56,state['message'],1)
    return bytes(finish_frame(p))


def _render_worker(pipe):
    try:os.nice(10)
    except (AttributeError,OSError):pass
    from app.text_marquee import Marquee,mikro_names
    marquee=Marquee()
    try:
        while True:
            request=pipe.recv()
            if request is None:return
            generation,state=request
            from app.live_display import live_frame
            pixels=mikro_names(marquee,state,live_frame(state))
            pipe.send((generation,pixels))
    except (EOFError,BrokenPipeError):pass
    finally:pipe.close()


class StepDisplay:
    def __init__(self):
        ctx=multiprocessing.get_context('spawn');self.pipe,child=ctx.Pipe()
        self.process=ctx.Process(target=_render_worker,args=(child,),name='step-display',daemon=True)
        self.process.start();child.close();self.busy=False;self.generation=0;self.frames=0
    def submit(self,state):
        if self.busy:return False
        if not self.process.is_alive():raise OSError('STEP display worker exited')
        self.pipe.send((self.generation,state));self.busy=True;return True
    def poll(self):
        if not self.process.is_alive():raise OSError('STEP display worker exited')
        if not self.pipe.poll():return None
        generation,pixels=self.pipe.recv();self.busy=False
        if generation!=self.generation:return None
        self.frames+=1;return pixels
    def invalidate(self):self.generation+=1
    def close(self):
        if self.process.is_alive() and not self.busy:self.pipe.send(None)
        self.process.join(.2)
        if self.process.is_alive():self.process.terminate();self.process.join()
        self.pipe.close()
