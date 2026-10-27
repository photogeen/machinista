"""Small per-note patches for Step Undo within an independent recording Take."""
import copy
from app.project_snapshot import project_snapshot
from app.polyphony import write_event

class RecordingHistory:
    def init_recording_history(self):self.recording_history={}

    def recording_change(self,key,before,after,merge=False):
        anchor=self.recording_undo
        if anchor is None:return
        meta=self.recording_history.setdefault(id(anchor),{'changes':[],'position':0})
        changes=meta['changes'];position=meta['position']
        del changes[position:]
        if merge:
            for change in reversed(changes):
                if change.get('key')==key:
                    change['after']=copy.deepcopy(after);return
        changes.append({'key':key,'before':copy.deepcopy(before),'after':copy.deepcopy(after)})
        meta['position']=len(changes)

    def apply_recording_change(self,change,forward):
        if 'bundle' in change:
            for item in change['bundle'][::1 if forward else -1]:self.apply_recording_change(item,forward)
            return
        if 'automation' in change:self.apply_modulation_change(change,forward);return
        group,pattern=change['key'][:2];key=change['key'][2:];event=change['after' if forward else 'before']
        if len(key)>2:self.put_event(key,event,group,pattern)
        elif event is None:self.remove_note(*key,group,pattern)
        else:self.put_note(*key,event,group,pattern)
        self.revision+=1;self.dirty=True
        # A released/undone voice must not write a new duration on top of the undo.
        for voices,_,_ in self.live_notes.values():
            for group,pad,note in voices:self.actions.append(('note_off',(group,pad,note)))
        self.live_notes.clear();self.record_live_skip.clear()

    def undo_action(self,redo=False,step=False):
        self.cancel_replace()
        self.erase_targets.clear()
        meta=self.recording_history.get(id(self.undo[-1])) if self.undo else None
        if step:
            if redo and meta and meta['position']<len(meta['changes']):
                self.apply_recording_change(meta['changes'][meta['position']],True);meta['position']+=1
                self.message='STEP REDO';return
            if not redo and meta and meta['position']:
                meta['position']-=1;self.apply_recording_change(meta['changes'][meta['position']],False)
                self.message='STEP UNDO';return
            if not redo and meta and not meta['position']:
                # Already at this take's base: move past its empty boundary.
                future=self.history_snapshot()
                flattened=[item for change in meta['changes'] for item in change.get('bundle',[change])]
                for change in flattened:
                    if 'automation' in change:
                        self.write_modulation_change(future,change,True);continue
                    group,pattern=change['key'][:2];pad,tick=change['key'][2:4];data=future['groups'][group];event=change['after']
                    if len(change['key'])>4:
                        write_event(future,group,pattern,change['key'][2:],event);continue
                    if tick%24:
                        key=f'{pattern}:{pad}:{tick}'
                        if event is None:data['extra_events'].pop(key,None)
                        else:data['extra_events'][key]=copy.deepcopy(event)
                    else:
                        data['patterns'][pattern][pad][tick//24]=event is not None
                        key=f'{pattern}:{pad}:{tick//24}'
                        if event is None:data['events'].pop(key,None)
                        else:data['events'][key]=copy.deepcopy(event)
                self.redo.append(future);pending=copy.deepcopy(meta);pending['position']=len(pending['changes'])
                self.recording_history[id(future)]=pending;self.undo.pop()
                return self.undo_action(step=True)
            if redo and self.redo:
                pending=self.recording_history.get(id(self.redo[-1]))
                if pending and pending['changes']:
                    base=self.history_snapshot();self.redo.pop();self.undo.append(base)
                    meta=copy.deepcopy(pending);meta['position']=0;self.recording_history[id(base)]=meta
                    return self.undo_action(redo=True,step=True)
        source,dest=(self.redo,self.undo) if redo else (self.undo,self.redo)
        if not source:return
        saved=source.pop();saved_meta=self.recording_history.get(id(saved))
        current=self.history_snapshot();dest.append(current)
        if saved_meta:
            transferred=copy.deepcopy(saved_meta)
            if not redo:
                transferred['changes']=transferred['changes'][:transferred['position']]
            self.recording_history[id(current)]=transferred
        self.automation_restore();self.project=saved
        self.scene=min(self.scene,len(self.project['scenes'])-1);self.activate_scene(self.scene);self.pad=min(self.pad,15)
        self.dirty=True;self.revision+=1;self.live_notes.clear();self.reset_recording_take()
        self.poly_cache.clear()
        self.actions.append(('reload',None));self.message=('STEP ' if step else '')+('REDO' if redo else 'UNDO')
