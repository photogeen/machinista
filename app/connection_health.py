"""Bound recovery attempts and diagnose blocked UI work without touching audio."""
import json
import os
from pathlib import Path
import tempfile
import sys
import threading
import time
import traceback

class RetryGate:
    def __init__(self):self.key=None;self.next=0;self.delay=1
    def ready(self,key,now):
        if key!=self.key:self.key=key;self.next=0;self.delay=1
        return now>=self.next
    def failed(self,now):self.next=now+self.delay;self.delay=min(8,self.delay*2)
    def reset(self):self.key=None;self.next=0;self.delay=1

def output_stalled(output,now,limit=5):
    started=getattr(output,'busy_since',None)
    return type(started) in (float,int) and now-started>limit

class LoopWatch:
    def __init__(self,limit=3,diagnostics=False):
        self.limit=limit;self.updated=time.monotonic();self.owner=threading.get_ident()
        self.snapshot={};self.path=Path(tempfile.gettempdir())/f'machinista-controller-{os.getuid()}.json' if diagnostics else None
        self.stop=threading.Event();self.warned=False
        self.thread=threading.Thread(target=self.run,name='controller-loop-watch',daemon=True);self.thread.start()
    def tick(self):self.updated=time.monotonic();self.warned=False
    def publish(self,snapshot):self.snapshot=snapshot
    def write_status(self):
        if self.path is None:return
        temporary=None
        try:
            status=dict(self.snapshot,pid=os.getpid(),loop_age=round(max(0,time.monotonic()-self.updated),3))
            with tempfile.NamedTemporaryFile(mode='w',dir=self.path.parent,prefix='.controller-health-',delete=False) as handle:
                temporary=handle.name;json.dump(status,handle)
            os.replace(temporary,self.path)
        except OSError as error:
            if temporary:
                try:os.unlink(temporary)
                except OSError:pass
            print('Controller diagnostic write: '+str(error),flush=True)
    def run(self):
        while not self.stop.wait(1):
            self.write_status()
            if not self.warned and time.monotonic()-self.updated>self.limit:
                self.warned=True
                frame=sys._current_frames().get(self.owner)
                print('Controller loop stalled >3s; audio engine remains independent\n'+''.join(traceback.format_stack(frame,limit=8)),flush=True)
    def close(self):self.stop.set();self.thread.join(timeout=1.5)


class ReaderWatch:
    """Watch reader progress and, for known NI devices, their continuous pad scan."""
    def __init__(self,limit=5,report_limit=None):self.limit=limit;self.report_limit=report_limit;self.stop()
    def stop(self):self.started=self.received=self.produced=None;self.reports=self.rejected=0;self.last_report=None;self.pad_reports=0;self.last_pad_report=None
    def start(self,now):self.stop();self.started=now
    def receive(self,event,now):
        if event.get('kind')!='reader_health':return False
        if any(type(event.get(k)) is not int or event[k]<0 for k in ('reports','rejected','monotonic_ns','last_report_ns','pad_reports','last_pad_report_ns')):raise ValueError('invalid reader heartbeat')
        self.received=now;self.produced=event['monotonic_ns']/1e9
        self.reports=event['reports'];self.rejected=event['rejected'];self.last_report=event['last_report_ns']/1e9 or None
        self.pad_reports=event['pad_reports'];self.last_pad_report=event['last_pad_report_ns']/1e9 or None
        return True
    def expired(self,now):
        if self.started is None:return False
        if self.report_limit is not None and now-(self.last_pad_report if self.last_pad_report is not None else self.started)>self.report_limit:return True
        return now-(self.received if self.received is not None else self.started)>self.limit or (self.produced is not None and now-self.produced>self.limit)
    def summary(self,now):
        return dict(heartbeat_age=None if self.received is None else round(max(0,now-self.received),3),
                    report_age=None if self.last_report is None else round(max(0,now-self.last_report),3),
                    reports=self.reports,rejected=self.rejected,pad_reports=self.pad_reports,
                    pad_report_age=None if self.last_pad_report is None else round(max(0,now-self.last_pad_report),3))


def surface_status(session,now):
    output=session.output;process=session.process
    lags=sorted(getattr(session,'input_lags',()))
    latency=None if not lags else dict(count=len(lags),median=round(lags[len(lags)//2],2),p95=round(lags[min(len(lags)-1,int(len(lags)*.95))],2),maximum=round(lags[-1],2))
    started=getattr(output,'busy_since',None)
    return dict(reader_pid=process.pid if process else None,input_latency_ms=latency,
                reader=session.reader_watch.summary(now),
                output_frames=getattr(output,'frames',0),
                display_timing=getattr(output,'performance',None),
                output_busy=None if type(started) not in (float,int) else round(max(0,now-started),3),
                output_error=str(output.error) if output and output.error else '')
