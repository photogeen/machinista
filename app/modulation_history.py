"""Point-sized modulation edits sharing recording Take/Step Undo history."""
import copy
from app.project_snapshot import project_snapshot

class ModulationHistory:
    def history_snapshot(self):
        result=project_snapshot(self.project)
        for descriptor,value in getattr(self,'automation_bases',{}).items():
            try:self.automation_set(descriptor,value,result,False)
            except (KeyError,IndexError):pass
        return result

    def remember_modulation(self):
        self.modulation_rotating=False
        try:
            context=(self.group,self.pattern)
            if self.modulation_anchor is not None and self.undo and self.undo[-1] is self.modulation_anchor and self.modulation_context==context:
                self.recording_undo=self.modulation_anchor
            elif not self.recording:self.reset_recording_take()
            self.remember_recording_note()
            self.modulation_anchor=self.recording_undo;self.modulation_context=context
        finally:self.modulation_rotating=True

    def finish_modulation_take(self):
        self.modulation_anchor=None;self.modulation_context=None
        if not self.recording:self.reset_recording_take()

    def modulation_change(self,group,name,tick,descriptor,before,after):
        anchor=self.recording_undo
        if anchor is None:return
        meta=self.recording_history.setdefault(id(anchor),{'changes':[],'position':0})
        changes=meta['changes'];del changes[meta['position']:]
        key=(group,name,tick,descriptor)
        if changes and changes[-1].get('automation')==key:changes[-1]['after']=copy.deepcopy(after)
        else:changes.append(dict(automation=key,before=copy.deepcopy(before),after=copy.deepcopy(after)))
        meta['position']=len(changes)

    def write_modulation_change(self,project,change,forward):
        group,name,tick,descriptor=change['automation'];state=change['after' if forward else 'before']
        lanes=project.setdefault('master_automation',{}) if group==-1 else project['groups'][group].setdefault('automation',{})
        lane=lanes.setdefault(name,dict(copy.deepcopy(state['metadata']),points={}))
        lane.update(copy.deepcopy(state['metadata']))
        if state['present']:lane['points'][tick]=copy.deepcopy(state['point'])
        else:lane['points'].pop(tick,None)
        if not state['exists'] and not lane['points']:lanes.pop(name,None)
        self.automation_set(descriptor,state['base_value'],project,False)

    def apply_modulation_change(self,change,forward):
        descriptor=change['automation'][3]
        self.write_modulation_change(self.project,change,forward)
        self.automation_bases.pop(descriptor,None);self.automation_written.discard(descriptor);self.automation_cache=None
        self.automation_set(descriptor,self.automation_value(descriptor))
        self.revision+=1;self.dirty=True
