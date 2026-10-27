"""Keep overlapping MIDI pitches held, then balance every emitted attack."""
class NoteTokens:
    def __init__(self):self.active={};self.attacks={}
    def start(self,key,token):
        self.active.setdefault(key,set()).add(token)
        self.attacks[key]=self.attacks.get(key,0)+1
    def release_count(self,key,token=None):
        if token is not None:
            voices=self.active.get(key)
            if not voices or token not in voices:return 0
            voices.remove(token)
            if voices:return 0
        self.active.pop(key,None)
        return self.attacks.pop(key,1 if token is None else 0)
    def release(self,key,token=None):return bool(self.release_count(key,token))
    def clear(self):self.active.clear();self.attacks.clear()
