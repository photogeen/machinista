"""Isolate full-size LCD drawing from live input dispatch's Python GIL.

Only immutable snapshots/pixels cross the pipe. Device I/O remains in the
existing output worker. No Application, USB handle or audio object is shared.
"""
import multiprocessing
import os

def _render_worker(pipe,startup,kind="mk2"):
    if kind=="mk3":from app.mk3_display import Mk3Renderer as Mk2Renderer
    else:from app.mk2_display import Mk2Renderer
    try:os.nice(10)
    except OSError:pass
    renderer=Mk2Renderer(startup=startup)
    try:
        while True:
            try:command=pipe.recv()
            except EOFError:break
            if command is None:break
            state,dismiss=command
            if dismiss:renderer.dismiss_boot()
            try:pipe.send((True,renderer.wire_frames(state) if kind=='mk3' else renderer(state),bool(renderer.needs_refresh)))
            except Exception as error:pipe.send((False,str(error),False))
    finally:renderer.close();pipe.close()

class ProcessRenderer:
    def __init__(self,startup=False,kind="mk2"):
        context=multiprocessing.get_context('spawn')
        self.pipe,child=context.Pipe()
        self.process=context.Process(target=_render_worker,args=(child,startup,kind),name='controller-render',daemon=True)
        self.process.start();child.close();self.needs_refresh=startup;self.dismissed=False;self.closed=False
    def dismiss_boot(self):self.dismissed=True
    def __call__(self,state):
        if self.closed or not self.process.is_alive():raise OSError('Controller renderer exited')
        self.pipe.send((state,self.dismissed))
        if not self.pipe.poll(2):raise OSError('Controller renderer timeout')
        success,result,self.needs_refresh=self.pipe.recv()
        if not success:raise OSError('Controller render: '+result)
        return result
    def close(self):
        if self.closed:return
        self.closed=True
        # Session cleanup runs only after its output worker has stopped using
        # this pipe. A stuck renderer cannot hold input/device recovery hostage.
        if self.process.is_alive():self.process.terminate();self.process.join(timeout=.3)
        if self.process.is_alive():self.process.kill();self.process.join(timeout=.3)
        self.pipe.close()
