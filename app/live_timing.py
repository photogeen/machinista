"""Bounded live note deadlines, polled before display work by the engine loop.

No sleeps, background audio calls or late catch-up bursts. Releases cancel
pending voices using their exact token before any attack can be emitted.
"""
import heapq
import time

class LiveTiming:
    def __init__(self):self.pending=[];self.serial=0
    def add(self,delay,token,callback):
        if delay<=0:callback();return True
        if len(self.pending)>=4096:return False
        self.serial+=1;heapq.heappush(self.pending,(time.monotonic()+delay,self.serial,token,callback));return True
    def cancel(self,token):
        self.pending=[item for item in self.pending if item[2]!=token];heapq.heapify(self.pending)
    def tick(self,now=None):
        now=time.monotonic() if now is None else now
        while self.pending and self.pending[0][0]<=now:
            deadline,_,_,callback=heapq.heappop(self.pending)
            # After an application stall, discard obsolete attacks, not a burst.
            if now-deadline<=.05:callback()
    def clear(self):self.pending.clear()
