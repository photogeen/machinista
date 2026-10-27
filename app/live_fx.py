"""Built-in, realtime performance effects shared by the supported controllers."""
import time


LIVE_FX = (
    'OFF', 'LP SWEEP', 'HP SWEEP', 'ECHO', 'ROLL 1/4', 'ROLL 1/8',
    'STUTTER', 'REVERSE', 'TAPE STOP', 'BITCRUSH', 'RING MOD', 'PHASER',
    'FLANGER', 'CHORUS', 'PITCH DOWN', 'PITCH UP',
)
LIVE_FX_MODES = ('PUNCH', 'FLEX', 'KNOB')


class LiveEffects:
    """Controller gestures, pattern capture and encoder state for native DSP FX."""

    def init_live_fx(self):
        self.live_fx_mode = 0
        self.live_fx_depth = 100
        self.live_fx_held = {}
        self.live_fx_current = 0
        self.live_fx_pad = 15
        self.live_fx_velocity = 100
        self.live_fx_raw_velocity = 100
        self.live_fx_started = 0.0

    def open_live_fx(self, origin=None):
        self.live_fx_origin=origin or self.page
        self.wave_view_active=self.wave_view_pinned=False
        self.live_fx_held.clear()
        self.live_fx_mode=0
        self.page='LIVE FX'
        self.live_fx_send(0,0,pressed=False)

    def live_fx_off(self, mode=None):
        before=self.live_fx_pack()
        self.live_fx_held.clear()
        if mode is not None:self.live_fx_mode=mode
        self.live_fx_send(0,0,pressed=False)
        self.live_fx_record(before,self.live_fx_pack(0,0))

    def close_live_fx(self):
        self.live_fx_off()
        self.page=getattr(self,'live_fx_origin','PAD')

    def live_fx_pack(self, effect=None, velocity=None):
        effect = self.live_fx_current if effect is None else int(effect)
        velocity = self.live_fx_velocity if velocity is None else int(velocity)
        return max(0,min(2,int(self.live_fx_mode)))*2048+max(0,min(15,effect))*128+max(0,min(127,velocity))

    def live_fx_send(self, effect, velocity=100, mode=None, pressed=True):
        mode = self.live_fx_mode if mode is None else mode
        self.live_fx_current = max(0, min(15, int(effect)))
        self.live_fx_velocity = max(0, min(127, int(velocity)))
        self.actions.append(('live_fx', (mode, self.live_fx_current, self.live_fx_velocity, int(pressed), round(self.project['tempo']))))

    def live_fx_record(self, before, after):
        if not (self.playing and self.recording and self.step >= 0 and not self.count_remaining):
            return
        from app.layout import GROUP_BASE
        descriptor = (GROUP_BASE+self.group, 'fx', -1, 'state')
        old = getattr(self, 'automation_capture', None)
        self.automation_capture = True
        try:
            self.capture_automation(descriptor, before, after)
        finally:
            if old is None:
                try: del self.automation_capture
                except AttributeError: pass
            else: self.automation_capture = old

    def live_fx_manual_override(self):
        # Recorded lanes may resume after release, never erase a held gesture.
        in_view=self.page=='LIVE FX' or self.page=='VIEW NAV' and self.view_entry=='LIVE FX'
        return bool(self.live_fx_held or in_view and self.live_fx_mode in (1,2) and self.live_fx_current)

    def live_fx_pad_pressure(self, slot, velocity, owner=None):
        key=(owner,slot)
        if self.page!='LIVE FX' or self.live_fx_mode!=0 or key not in self.live_fx_held:return False
        row=self.live_fx_held[key]
        self.live_fx_held[key]=(slot,velocity,row[2])
        # The last held effect owns the output; older pads retain their pressure.
        if next(reversed(self.live_fx_held))!=key or slot==15:return True
        level=max(0,min(127,velocity*self.live_fx_depth//100))
        now=time.monotonic()
        if level==self.live_fx_velocity or now-getattr(self,'live_fx_pressure_stamp',0)<.01:return True
        self.live_fx_pressure_stamp=now;before=self.live_fx_pack()
        self.live_fx_raw_velocity=velocity;self.live_fx_send(slot+1,level)
        self.live_fx_record(before,self.live_fx_pack())
        return True

    def live_fx_pad_on(self, slot, velocity, owner=None):
        key = (owner, slot)
        if key in self.live_fx_held:
            return True
        before = self.live_fx_pack()
        self.live_fx_held[key] = (slot, velocity, time.monotonic())
        self.live_fx_pad = slot
        self.live_fx_pressure_stamp=0
        # PO-style dry pad is pad 16; pads 1-15 address the effect palette.
        effect = 0 if slot == 15 else slot+1
        self.live_fx_raw_velocity = velocity
        level = max(0, min(127, velocity*self.live_fx_depth//100))
        if self.live_fx_mode in (1, 2) and effect == 0:
            self.live_fx_send(0, 0, pressed=False)
            self.live_fx_record(before, self.live_fx_pack(0, 0))
            return True
        if self.live_fx_mode == 2 and self.live_fx_current == effect:
            effect = 0
        self.live_fx_send(effect, level, pressed=True)
        self.live_fx_record(before, self.live_fx_pack(effect, level))
        return True

    def live_fx_pad_off(self, slot, owner=None):
        key = (owner, slot)
        if key not in self.live_fx_held:
            return False
        before = self.live_fx_pack()
        self.live_fx_held.pop(key, None)
        if self.live_fx_mode == 0:
            current = list(self.live_fx_held.values())[-1] if self.live_fx_held else None
            held_slot,raw_velocity = current[:2] if current else (0, 0)
            self.live_fx_raw_velocity=raw_velocity
            effect = 0 if not current or held_slot==15 else held_slot+1
            velocity = max(0,min(127,raw_velocity*self.live_fx_depth//100)) if current else 0
            self.live_fx_send(effect, velocity, pressed=bool(current))
            self.live_fx_record(before, self.live_fx_pack(effect, velocity))
        return True

    def live_fx_button(self, name, pressed):
        if name == 'SOLO' and pressed and self.shift:
            if self.page == 'LIVE FX':
                self.close_live_fx()
            else:
                self.open_live_fx()
            return True
        if name=='SOLO' and self.page=='LIVE FX':return True
        if self.page != 'LIVE FX':
            return False
        if name=='VIEW' and not self.shift:return False
        if pressed and name in ('MAIN','BROWSE','SAMPLING','SCENE','PATTERN','PAD MODE','SELECT','GROUP','VIEW','GRID','NOTE REPEAT','DUPLICATE'):
            self.close_live_fx()
            return False
        if pressed and name in ('F1', 'F2', 'F3'):
            self.live_fx_off(int(name[1])-1)
            return True
        if pressed and name in ('PLAY','REC','RESTART'):
            return False
        if pressed and name in ('NAV LEFT', 'NAV RIGHT'):
            self.live_fx_depth = max(0, min(100, self.live_fx_depth+(-5 if name == 'NAV LEFT' else 5)))
            if self.live_fx_current:
                self.live_fx_send(self.live_fx_current, max(0,min(127,self.live_fx_raw_velocity*self.live_fx_depth//100)), pressed=True)
            return True
        if name in ('PLAY', 'REC', 'RESTART', 'SHIFT', 'MUTE'):
            return False
        return True

    def live_fx_rotate(self, delta):
        if self.page != 'LIVE FX':
            return False
        self.live_fx_depth = max(0, min(100, self.live_fx_depth+delta))
        if self.live_fx_current:
            self.live_fx_send(self.live_fx_current, max(0,min(127,self.live_fx_raw_velocity*self.live_fx_depth//100)), pressed=True)
        return True

    def live_fx_view_data(self):
        return {'mode':LIVE_FX_MODES[self.live_fx_mode], 'depth':self.live_fx_depth,
                'effect':LIVE_FX[self.live_fx_current], 'current':self.live_fx_current,
                'effects':LIVE_FX[1:]+('OFF',)}
