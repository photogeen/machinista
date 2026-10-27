"""MIDI transport and 24-PPQ clock conversion to the sequencer's 96 PPQ."""
import collections
import heapq

class MidiClock:
    def __init__(self):
        self.mode='OFF';self.running=False;self.position=0;self.last=None
        self.intervals=collections.deque(maxlen=24);self.period=60/120/24
        self.queue=[];self.dispatched=-1;self.next_output=None;self.output_running=False
    def configure(self,mode):
        if mode!=self.mode:
            self.mode=mode;self.running=False;self.queue.clear();self.last=None
            self.intervals.clear();self.next_output=None;self.output_running=False
    def receive(self,status,data,now,offset=0):
        if self.mode!='IN':return None
        if status==0xf2:
            self.position=(data[0]|data[1]<<7)*24;self.queue.clear();self.dispatched=self.position-1
            return ('locate',self.position)
        if status in (0xfa,0xfb):
            self.running=True;self.queue.clear()
            if status==0xfa:self.position=0;self.dispatched=-1
            return ('start' if status==0xfa else 'continue',self.position)
        if status==0xfc:
            self.running=False;self.queue.clear();return ('stop',self.position)
        if status==0xf8:
            if self.last is not None and .001<=now-self.last<=.25:
                self.intervals.append(now-self.last);self.period=sum(self.intervals)/len(self.intervals)
            self.last=now
            if self.running:
                for sub in range(4):heapq.heappush(self.queue,(now+offset/1000+sub*self.period/4,self.position+sub))
                self.position+=4
            return ('tempo',60/self.period/24)
        return None
    def ticks(self,now):
        if self.mode!='IN':return []
        # No free-running clock after an unplugged or stopped source.
        if self.running and self.last is not None and now-self.last>max(.5,self.period*12):
            self.running=False;self.queue.clear();return []
        result=[]
        while self.queue and self.queue[0][0]<=now:
            deadline,position=heapq.heappop(self.queue)
            if position>self.dispatched:result.append((deadline,position));self.dispatched=position
        return result
    def output(self,now,playing,phase,tempo,offset=0):
        if self.mode!='OUT':return []
        result=[];period=60/tempo/24
        if playing!=self.output_running:
            self.output_running=playing
            if playing:
                if phase<=0:result.append(bytes([0xfa]))
                else:
                    position=min(16383,max(0,phase)//24);result.append(bytes([0xf2,position&127,position>>7]));result.append(bytes([0xfb]))
                self.next_output=now+offset/1000
            else:result.append(bytes([0xfc]));self.next_output=None
        if playing and self.next_output is not None:
            if now-self.next_output>period*2:self.next_output=now
            while self.next_output<=now:
                result.append(bytes([0xf8]));self.next_output+=period
        return result
