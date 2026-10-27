"""Controller workspaces and connected editors for the headless groovebox."""
from pathlib import Path
import copy
import platform
import random
import time
import wave
from app.storage import save_json, load_json

# NAV only contains workspaces without a direct controller shortcut.
SCREENS = ('SONG', 'PROJECT', 'SYSTEM')


class Workspaces:
    def init_workspaces(self):
        self.group_delete_history={}
        self.nav_index = 0
        self.nav_origin = 'PAD'
        self.bank = 0
        self.event_step = 0
        self.event_field = 0
        self.slice_count = 8
        self.slice_index = 0
        self.project_index = 0
        self.project_choice = 0
        self.song_index = 0
        self.song_playing = False
        self.song_bar = 0;self.song_phase_origin=0
        self.pending_scene = None
        self.option_field = 0
        self.confirmation = None
        self.keyboard_root = 60
        self.chord = 0
        self.arp_on = False
        self.arp_hold = False
        self.arp_notes = set()
        self.track_field = 0
        self.effect_index = 0
        self.project.setdefault('song', [])
        for group in self.project['groups']:
            group.setdefault('events', {})
            for slot, track in enumerate(group['pads']):
                track.setdefault('source', 'SAMPLE')
                track.setdefault('note', 36+slot)
                track.setdefault('channel', 1)

        self.init_timing()
        self.init_recording_history();self.init_recording();self.init_erasing()
        self.init_pattern_editor()
        self.init_project_manager()
        self.init_banks()
        self.init_performance()

    def event(self):
        self.lane()  # Clamp the cursor after switching to a shorter pattern.
        group = self.project['groups'][self.group]
        key = f'{self.pattern}:{self.pad}:{self.event_step}'
        return group['events'].get(key, {'velocity': 100, 'probability': 100})

    def confirm(self, prompt, action, origin=None):
        self.confirmation = (prompt, action, origin or self.page)
        self.page = 'CONFIRM'

    def load_project(self, path):
        from app.model import validate_project
        from app.assets import resolve_assets
        project=validate_project(resolve_assets(load_json(path,{}),path.parent))
        project['file_id']=path.stem
        if self.settings.get('autosave')=='ON':
            from app.autosave import recover
            project,_=recover(self.root,project,path,validate_project)
        # Preserve the active project as a recovery slot before replacement.
        self.save()
        self.project_generation+=1
        self.automation_restore()
        self.project = project
        self.playing = self.recording = False
        self.group = self.pad = self.pattern = self.scene = self.step = 0
        self.active_patterns=[p if p is not None else 0 for p in project['scenes'][0]]
        self.pattern=self.active_patterns[0]
        self.step = -1
        self.undo.clear()
        self.init_workspaces()
        self.init_surface()
        self.init_live_fx();self.live_fx_send(0,0,pressed=False)
        self.init_sampler();self.init_slicing();self.init_navigation();self.init_plugins()
        self.actions.extend([('panic', None), ('reload', None)])
        self.save()
        self.page = 'PROJECT'
        self.message = 'PROJECT LOADED'
        self.request_missing_check(False)

    def apply_chop(self):
        source = copy.deepcopy(self.track())
        if not source['sample'] or source['end']-source['start'] < self.slice_count:
            self.message = 'LOAD A LONGER SAMPLE'
            return
        self.remember()
        size = source['end']-source['start']
        for slot in range(self.slice_count):
            track = copy.deepcopy(source)
            track['start'] = source['start']+size*slot//self.slice_count
            track['end'] = source['start']+size*(slot+1)//self.slice_count
            self.project['groups'][self.group]['pads'][slot] = track
            self.actions.append(('load', (self.group, slot, copy.deepcopy(track))))
        self.page = self.control_home()
        self.pad = 0
        self.message = f'{self.slice_count} SLICES ASSIGNED'

    def select_scene(self, index):
        if index not in self.project['scene_created']:self.remember();self.project['scene_created'].append(index)
        if self.playing:self.pending_scene=index
        else:self.activate_scene(index)

    def workspace_button(self, name):
        if name in ('PLAY', 'REC', 'RESTART', 'MAIN'):
            if name == 'MAIN':
                self.confirmation = None
            return False
        if name == 'NAV':
            if self.page == 'NAVIGATE':
                self.page = self.nav_origin
            else:
                self.nav_origin = self.page
                self.nav_index = SCREENS.index(self.page) if self.page in SCREENS else 0
                self.page = 'NAVIGATE'
            return True
        if self.page == 'CONFIRM':
            if name in ('F1', 'F3'):
                self.page = self.confirmation[2]
                self.confirmation = None
            elif name in ('F2', 'ENTER', 'ENCODER PUSH'):
                _, action, origin = self.confirmation
                self.confirmation = None
                self.page = origin
                action()
            return True
        if self.page == 'NAVIGATE' and name in ('F2', 'ENTER', 'ENCODER PUSH'):
            self.page = SCREENS[self.nav_index]
            return True
        if self.page == 'NAVIGATE' and name in ('F1', 'F3'):
            self.page = self.nav_origin if name == 'F1' else 'PAD'
            return True
        if self.shift and name == 'VIEW':
            if self.page=='MIXER':self.page=getattr(self,'mixer_origin',self.control_home())
            else:self.mixer_origin=self.page;self.page='MIXER'
            return True
        if self.shift and name == 'PAD MODE':
            self.page = 'KEYBOARD'
            return True
        if name == 'NOTE REPEAT' and not self.shift:
            self.page = 'OPTIONS'
            return True
        if name == 'GRID':
            self.page = 'OPTIONS'
            return True
        if name in ('NAV LEFT', 'NAV RIGHT') and self.page in ('EVENT', 'OPTIONS', 'MIDI TRACK'):
            attr, count = {'EVENT': ('event_field', 3), 'OPTIONS': ('option_field', 2),
                           'MIDI TRACK': ('track_field', 3)}[self.page]
            setattr(self, attr, (getattr(self, attr)+(1 if name == 'NAV RIGHT' else -1)) % count)
            return True
        if self.page in ('SAMPLE EDIT', 'CHOP') and name in ('NAV LEFT', 'NAV RIGHT'):
            if self.page == 'SAMPLE EDIT':
                self.sample_field = 0 if name == 'NAV LEFT' else 1
            else:
                self.slice_index = max(0, min(self.slice_count-1, self.slice_index+(1 if name == 'NAV RIGHT' else -1)))
            return True
        if name not in ('F1', 'F2', 'F3', 'ENTER'):
            return False
        if self.page == 'PAD' and name == 'F1':
            self.page = 'MIXER'
            return True
        if self.page == 'SAMPLING' and name == 'F1':
            self.page = 'SAMPLE EDIT'
            return True
        routes = {'PATTERN': ('STEP', 'EVENT', 'LENGTH'),
                  'SCENE': ('SCENE', 'SONG', 'PROJECT'),
                  'GROUP': ('GROUP', 'MIXER', 'MIDI TRACK'),
                  'MIXER': ('MIXER', 'MIDI TRACK', 'PAD'),
                  'SAMPLE EDIT': ('SAMPLING', 'CHOP', 'PROCESS'),
                  'MIDI TRACK': ('MIDI TRACK', 'PAD', 'STEP'),
                  'FX': ('PAD', 'MIXER', 'FX'),
                  'KEYBOARD': ('KEYBOARD', 'CHORD', 'PAD')}
        if self.page in routes and name.startswith('F'):
            self.page = routes[self.page][int(name[1])-1]
            return True
        if self.page == 'CHOP':
            if name == 'F1':
                self.slice_count = 8
                self.slice_index = 0
            elif name == 'F2':
                self.page = 'SAMPLE EDIT'
            elif name in ('F3', 'ENTER'):
                self.confirm(f'REPLACE {self.slice_count} PADS?', self.apply_chop)
            return True
        if self.page == 'STEP' and name in ('F1', 'F2', 'F3'):
            if name == 'F2':
                self.page = 'EVENT'
                self.event_step = min(self.bank*16, len(self.lane())-1)
            else:
                self.bank = max(0, min((len(self.lane())-1)//16, self.bank+(-1 if name == 'F1' else 1)))
            return True
        if self.page == 'EVENT' and name.startswith('F'):
            if name == 'F1':
                self.event_step = (self.event_step-1) % len(self.lane())
            elif name == 'F2':
                self.event_step = (self.event_step+1) % len(self.lane())
            else:
                self.confirm('DELETE THIS EVENT?', self.delete_event)
            return True
        if self.page == 'PROJECT':
            if name == 'F1':
                self.save()
            elif name == 'F2':
                self.page = 'PROJECT LOAD'
                self.project_choice = 0
            elif name == 'F3':
                self.save_as()
            return True
        if self.page == 'PROJECT LOAD':
            files = self.project_files()
            if name in ('F2', 'ENTER') and files:
                path = files[min(self.project_choice, len(files)-1)]
                self.confirm('LOAD OTHER PROJECT?', lambda: self.load_project(path))
            elif name == 'F3':
                self.confirm('START NEW PROJECT?', self.start_new)
            elif name == 'F1':
                self.page = 'PROJECT'
            return True
        if self.page == 'SONG':
            song = self.project['song']
            if name == 'F1':
                if len(song) >= 1024:
                    self.message = 'SONG FULL'
                    return True
                self.remember()
                self.song_automation_remap(self.song_index)
                song.insert(self.song_index, self.scene)
            elif name == 'F2':
                if song:
                    self.song_playing = not self.song_playing
                    self.song_bar = self.song_index;self.song_phase_origin=0
                    self.select_scene(song[self.song_bar])
                    self.playing = self.song_playing
                    self.actions.append(('restart', None))
                    self.step = -1
                    self.clock_phase=-1
            elif name == 'F3' and song:
                self.confirm('REMOVE SONG ENTRY?', self.delete_song_entry)
            return True
        if self.page == 'ARP':
            if name == 'F1':
                self.arp_on = not self.arp_on
                if self.arp_on:
                    self.playing = True
            elif name == 'F2':
                self.arp_hold = not self.arp_hold
                if not self.arp_hold:
                    self.arp_notes.clear()
            elif name == 'F3':
                self.page = 'KEYBOARD'
            return True
        if self.page == 'PROCESS':
            operation = {'F1': 'NORMALIZE', 'F2': 'REVERSE', 'F3': 'TRUNCATE'}.get(name)
            if operation:
                self.confirm(operation+' SAMPLE?', lambda: self.actions.append(('process', operation)))
            return True
        if self.page in ('LENGTH', 'OPTIONS', 'CHORD', 'SYSTEM'):
            if name in ('F3', 'ENTER'):
                self.page = {'LENGTH': 'PATTERN', 'OPTIONS': 'PAD', 'CHORD': 'KEYBOARD', 'SYSTEM': 'PROJECT'}[self.page]
            return True
        return False

    def delete_event(self):
        self.remember()
        self.lane()[self.event_step] = False
        self.message = 'EVENT DELETED'

    def delete_song_entry(self):
        self.remember()
        self.song_automation_remap(self.song_index,True)
        self.project['song'].pop(self.song_index)
        self.song_index = max(0, min(self.song_index, len(self.project['song'])-1))

    def workspace_rotate(self, delta):
        if self.page == 'NAVIGATE':
            self.nav_index = (self.nav_index+delta) % len(SCREENS)
        elif self.page == 'CHOP':
            self.slice_count = max(2, min(16, self.slice_count+delta))
            self.slice_index = min(self.slice_index, self.slice_count-1)
        elif self.page == 'EVENT':
            if self.event_field == 0:
                self.event_step = max(0, min(len(self.lane())-1, self.event_step+delta))
            else:
                self.remember()
                group = self.project['groups'][self.group]
                key = f'{self.pattern}:{self.pad}:{self.event_step}'
                event = group['events'].setdefault(key, {'velocity': 100, 'probability': 100})
                field = 'velocity' if self.event_field == 1 else 'probability'
                event[field] = max(1 if field == 'velocity' else 0, min(127 if field == 'velocity' else 100, event[field]+delta))
        elif self.page=='LENGTH':self.adjust_pattern_length(delta)
        elif self.page == 'PROJECT LOAD':
            self.project_choice = max(0, min(max(0, len(self.project_files())-1), self.project_choice+delta))
        elif self.page == 'SONG':
            self.song_index = max(0, min(max(0, len(self.project['song'])-1), self.song_index+delta))
        elif self.page == 'OPTIONS':
            if self.option_field == 0:
                self.remember()
                self.project['tempo'] = round(max(40, min(240, self.project['tempo']+delta*(.01 if self.shift or self.encoder_held else 1))),2)
            else:
                self.bank = max(0, min((len(self.lane())-1)//16, self.bank+delta))
        elif self.page in ('KEYBOARD', 'CHORD', 'ARP'):
            if self.page in ('KEYBOARD', 'ARP'):
                self.keyboard_root = max(0, min(111, self.keyboard_root+delta))
            else:
                self.chord = (self.chord+delta) % 3
        elif self.page == 'MIDI TRACK':
            self.remember()
            track = self.track()
            if self.track_field == 0:
                track['source'] = 'MIDI' if track['source'] == 'SAMPLE' else 'SAMPLE'
            else:
                field = 'note' if self.track_field == 1 else 'channel'
                track[field] = max(0 if field == 'note' else 1, min(127 if field == 'note' else 16, track[field]+delta))
        elif self.page in ('PROJECT', 'SYSTEM', 'CONFIRM', 'PROCESS', 'FX'):
            pass
        else:
            return False
        return True

    def workspace_display(self):
        from app.ni_display import note_name
        header = f'{self.page} {self.group_name()}:{self.pad+1:02}'
        footer = ''
        if self.page == 'NAVIGATE':
            first = max(0, self.nav_index-1)
            body = [('>' if i == self.nav_index else ' ')+SCREENS[i] for i in range(first, min(first+3, len(SCREENS)))]
        elif self.page == 'SAMPLING':
            if self.capture_started is not None:
                seconds = int(time.monotonic()-self.capture_started)
                body = ['RECORDING', f'{seconds//60:02}:{seconds%60:02}', 'F3 STOP AND ASSIGN']
            else:
                body = [self.audio.name if self.audio and self.audio.capture else 'NO AUDIO INPUT',
                        'INPUT 1/2', '48000 HZ STEREO']
        elif self.page == 'CHOP':
            body = [f'{self.slice_count} EQUAL SLICES', f'SLICE {self.slice_index+1}', 'F3 APPLY TO PADS']
        elif self.page == 'EVENT':
            event = self.event()
            values = [f'STEP {self.event_step+1} {"ON" if self.lane()[self.event_step] else "OFF"}',
                      f'VEL {event["velocity"]}', f'PROB {event["probability"]}%']
            body = [('>' if i == self.event_field else ' ')+v for i, v in enumerate(values)]
        elif self.page == 'LENGTH':
            body = [f'{len(self.lane())//16} BAR', f'{len(self.lane())} STEPS', 'ENC CHANGE LENGTH']
        elif self.page == 'PROJECT':
            body = [self.project['name'], 'UNSAVED' if self.dirty else 'SAVED', f'{len(self.project_files())} PROJECT FILES']
        elif self.page == 'PROJECT LOAD':
            files = self.project_files()
            first = max(0, self.project_choice-1)
            body = [('>' if i == self.project_choice else ' ')+self.project_label(files[i]) for i in range(first, min(first+3, len(files)))] or ['NO SAVED PROJECTS']
        elif self.page == 'SONG':
            song = self.project['song']
            body = [f'{len(song)} SCENES', f'POS {self.song_index+1} SCENE {song[self.song_index]+1}' if song else 'EMPTY ARRANGEMENT', 'PLAY SONG' if self.song_playing else 'STOP SONG']
        elif self.page == 'OPTIONS':
            body = [('>' if self.option_field == 0 else ' ')+f'TEMPO {self.project["tempo"]}',
                    ('>' if self.option_field == 1 else ' ')+f'STEP BANK {self.bank+1}', 'GRID 1/16']
        elif self.page == 'SYSTEM':
            body = ['Machinista', platform.machine().upper(), 'AUDIO READY' if self.audio else 'NO AUDIO DEVICE']
        elif self.page == 'CONFIRM':
            body = [self.confirmation[0], 'F2 YES', 'F1 OR F3 CANCEL']
        elif self.page == 'MIDI TRACK':
            track = self.track()
            body = [('>' if self.track_field == i else ' ')+v for i, v in enumerate(
                [track['source'], f'NOTE {track["note"]}', f'CHANNEL {track["channel"]}'])]
        elif self.page == 'KEYBOARD':
            body = ['ROOT '+note_name(self.keyboard_root), 'PADS CHROMATIC', 'MIDI OUTPUT ONLY']
        elif self.page == 'CHORD':
            body = ['ROOT '+note_name(self.keyboard_root), ('SINGLE', 'MAJOR', 'MINOR')[self.chord], 'ENC CHORD TYPE']
        elif self.page == 'FX':
            body = ['NO FX INSTALLED', 'PLUGIN ENGINE PENDING', 'NO EFFECT APPLIED']
        elif self.page == 'ARP':
            body = [f'ARP {"ON" if self.arp_on else "OFF"} 1/16', note_name(self.keyboard_root)+' HOLD '+('ON' if self.arp_hold else 'OFF'), f'{len(self.arp_notes)} NOTES / MIDI OUT']
        elif self.page == 'PROCESS':
            body = ['CREATE EDITED COPY', 'ORIGINAL KEPT', 'CHOOSE F1 F2 OR F3']
        else:
            return None
        return header, body, self.message or footer

    def workspace_softkeys(self):
        return {'NAVIGATE': ('BACK', 'OPEN', 'HOME'), 'CONFIRM': ('CANCEL', 'YES', 'NO'),
                'PATTERN': ('STEP', 'EVENT', 'LENGTH'), 'SCENE': ('SCENE', 'SONG', 'PROJECT'),
                'GROUP': ('GROUP', 'MIXER', 'MIDI'), 'MIXER': ('VOL', 'MIDI', 'PAD'),
                'SAMPLING': ('EDIT', 'REC', 'STOP'), 'SAMPLE EDIT': ('REC', 'CHOP', 'PROCESS'),
                'CHOP': ('AUTO 8', 'EDIT', 'APPLY'), 'PROCESS': ('NORM', 'REVERSE', 'TRUNC'),
                'STEP': ('BANK-', 'EVENT', 'BANK+'), 'EVENT': ('PREV', 'NEXT', 'DELETE'),
                'LENGTH': ('-', '-', 'BACK'), 'PROJECT': ('SAVE', 'LOAD', 'SAVE AS'),
                'PROJECT LOAD': ('BACK', 'LOAD', 'NEW'), 'SONG': ('INSERT', 'PLAY', 'DELETE'),
                'OPTIONS': ('-', '-', 'BACK'), 'SYSTEM': ('-', '-', 'BACK'),
                'FX': ('PAD', 'MIXER', '-'), 'MIDI TRACK': ('MIDI', 'PAD', 'SEQ'),
                'KEYBOARD': ('ROOT', 'CHORD', 'PAD'), 'CHORD': ('-', '-', 'BACK'), 'ARP': ('ON/OFF', 'HOLD', 'KEYS'),
                'PAD': ('MIX', 'STEP', 'BROWSE')}.get(self.page)
