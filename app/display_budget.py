"""Defer optional LCD work when it would consume the next musical deadline."""
class DisplayBudget:
    def __init__(self):self.cost=.003;self.guard=.001
    def available(self,now,deadline,active):
        if not active:return True
        # External clock has its own predicted edge, not the internal deadline.
        return deadline-now>=self.cost+self.guard
    def measured(self,seconds):
        # Track normal rendering cost; rare stalls decay rather than permanently
        # disabling the display at fast tempos. USB output is handled separately.
        self.cost=max(.001,.8*self.cost+.2*seconds)
