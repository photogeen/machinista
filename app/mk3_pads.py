"""MK3 light-contact trigger threshold, separate from velocity scaling.

Firmware reports light hits as PressOn (0x00), not NoteOn (0x10).
A contact arms only its own pad; pressure without a contact never starts notes.
"""


def trigger_threshold(sensitivity):
    sensitivity=max(25,min(200,int(sensitivity)))
    return max(4,min(120,round(20*2**((100-sensitivity)/35))))


class Mk3PadTrigger:
    def __init__(self):
        self.contacts=set();self.sounding=set()

    def process(self,event,sensitivity):
        kind=event['kind'];name=event.get('name');threshold=trigger_threshold(sensitivity)
        if kind=='pad_contact':
            self.contacts.add(name)
            if name not in self.sounding and event['raw_value']>=threshold:
                self.sounding.add(name);return [dict(event,kind='pad_on')]
            return []
        if kind=='pad_on':
            if name in self.sounding:return []  # contact promoted to strike
            self.sounding.add(name);return [event]
        if kind=='pad_pressure':
            if name not in self.sounding:
                if name not in self.contacts or event['raw_value']<threshold:return []
                self.sounding.add(name);return [dict(event,kind='pad_on')]
            return [event]
        if kind in ('pad_off','pad_contact_off'):
            self.contacts.discard(name)
            if name in self.sounding:
                self.sounding.remove(name);return [dict(event,kind='pad_off')]
            return []
        return []
