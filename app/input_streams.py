"""Fair pipe draining: keep partial and deferred events until the next UI turn."""
import select
import time


def ready_streams(streams,timeout):
    pending=[stream for stream,buffer in streams.items() if b'\n' in buffer]
    ready=select.select(list(streams),[],[],0 if pending else timeout)[0]
    return list(dict.fromkeys(ready+pending)),set(ready)


def bounded_lines(streams,stream,limit=64,budget=.002,clock=time.monotonic):
    deadline=clock()+budget
    for index in range(limit):
        if b'\n' not in streams[stream] or (index and clock()>=deadline):return
        line,streams[stream]=streams[stream].split(b'\n',1)
        yield line
