"""MK3 light-contact trigger threshold, separate from velocity scaling.

Firmware reports light hits as PressOn (0x00), not NoteOn (0x10).
The MK3 reader also exposes pressure-only gestures from very light hits.
"""


def trigger_threshold(sensitivity, baseline=20):
    sensitivity=max(25,min(200,int(sensitivity)))
    return max(4,min(120,round(baseline*2**((100-sensitivity)/35))))


class Mk3PadTrigger:
    def __init__(self, baseline=20):
        self.baseline=baseline
        self.contacts=set();self.sounding=set()
        self.pressure_only=set();self.ignore_idle_pressure=set()

    def process(self,event,sensitivity):
        kind=event['kind'];name=event.get('name');threshold=trigger_threshold(sensitivity,self.baseline)
        if kind=='pad_idle_pressure':
            raw=event['raw_value']
            if not raw:
                self.ignore_idle_pressure.discard(name)
                if name in self.pressure_only:
                    self.pressure_only.remove(name)
                    self.sounding.remove(name)
                    return [dict(event,kind='pad_off')]
                return []
            if name in self.sounding or name in self.ignore_idle_pressure:return []
            if self.sounding:
                self.ignore_idle_pressure.add(name)
                return []
            if raw>=trigger_threshold(sensitivity):
                self.sounding.add(name)
                self.pressure_only.add(name)
                return [dict(event,kind='pad_on')]
            return []
        if kind=='pad_contact':
            self.pressure_only.discard(name)
            self.ignore_idle_pressure.discard(name)
            self.contacts.add(name)
            if name not in self.sounding and event['raw_value']>=threshold:
                self.sounding.add(name);return [dict(event,kind='pad_on')]
            return []
        if kind=='pad_on':
            self.pressure_only.discard(name)
            self.ignore_idle_pressure.discard(name)
            if name in self.sounding:return []  # contact promoted to strike
            self.sounding.add(name);return [event]
        if kind=='pad_pressure':
            if name not in self.sounding:
                if name not in self.contacts or event['raw_value']<threshold:return []
                self.sounding.add(name);return [dict(event,kind='pad_on')]
            return [event]
        if kind in ('pad_off','pad_contact_off'):
            self.contacts.discard(name)
            self.pressure_only.discard(name)
            self.ignore_idle_pressure.add(name)
            if name in self.sounding:
                self.sounding.remove(name);return [dict(event,kind='pad_off')]
            return []
        return []
