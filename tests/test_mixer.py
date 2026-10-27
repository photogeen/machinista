import array
import copy
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from app.model import Application
from app.layout import GROUP_BASE,MASTER
from app.runtime_audio import RuntimeAudio
from app.live_display import live_state,live_frame
from app.leds import led_report,OFF,DIM,FULL

ROOT=Path(__file__).resolve().parent.parent

class MixerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.a=Application(self.temp.name)
    def tap(self,key):self.a.button(key,True);self.a.button(key,False)
    def test_scope_gain_pan_and_undo_edit_only_selected_bus(self):
        a=self.a;a.page='MIXER';a.group=2;a.pad=9
        for key,level in [('F1',0),('F2',1),('F3',2)]:
            with self.subTest(level=level):
                self.tap(key);self.assertEqual(a.mixer_level,level);self.assertEqual(a.active_softkeys(),{level})
                a.mixer_field=0;before=copy.deepcopy(a.project);old=a.mixer_target().get('gain',100)
                a.rotate(-7);self.assertEqual(a.mixer_target()['gain'],old-7)
                self.tap('ENCODER PUSH');self.assertEqual(a.mixer_field,1)
                a.rotate(-23);self.assertEqual(a.mixer_target()['routing']['pan'],-23)
                a.undo_action();self.assertEqual(a.mixer_target().get('routing',{}).get('pan',0),0)
                a.undo_action();self.assertEqual(a.project,before)
                # Undo restores project objects, so derive the next target afresh.
                target=a.mixer_target()
    def test_sound_group_banks_never_create_project_content(self):
        a=self.a;a.ensure_group_bank(1);a.page='MIXER';before=copy.deepcopy(a.project)
        a.pad=1;self.tap('NAV RIGHT');self.assertEqual(a.pad,9);self.assertEqual(a.mixer_watch(),(8,8))
        self.tap('NAV RIGHT');self.assertEqual(a.pad,15)
        self.tap('NAV LEFT');self.assertEqual(a.pad,7)
        self.tap('F2');self.tap('NAV RIGHT');self.assertEqual(a.group,8)
        self.assertEqual(a.mixer_watch(),(GROUP_BASE+8,8))
        a.actions.clear();a.pad_on(14);a.release_pad(14)
        self.assertEqual(a.group,10);self.assertEqual(a.pattern,a.active_patterns[10]);self.assertEqual(a.actions,[])
        self.tap('F1');self.tap('NAV RIGHT');self.assertEqual(a.mixer_watch(),(MASTER,1))
        self.assertEqual(a.project,before)
    def test_sound_and_master_allow_live_audition(self):
        a=self.a;a.page='MIXER'
        for key in ('F1','F3'):
            self.tap(key);a.actions.clear();a.pad_on(3);a.release_pad(3)
            self.assertTrue(any(kind=='hit' for kind,_ in a.actions))
    def test_peak_hold_reset_master_exchange_and_stale_banks(self):
        a=self.a;a.page='MIXER';r=RuntimeAudio();commands=[];audio=type('Audio',(),{'command':commands.append})()
        r.update(a,audio,10,10)
        r.receive(a,dict(kind='mixer_meter',first=0,levels=[[1.2,.5]]+[[0,0]]*7,master=[1.2,.5]))
        r.receive(a,dict(kind='mixer_meter',first=0,levels=[[.1,.1]]*8,master=[.1,.1]))
        self.assertEqual(a.mixer_peaks[0],(1.2,.5));self.assertEqual(a.mixer_levels[0],(.1,.1))
        self.tap('F2');r.update(a,audio,11,11)
        r.receive(a,dict(kind='mixer_meter',first=0,levels=[[9,9]]*8,master=[9,9]))
        self.assertEqual(a.mixer_levels,{});self.assertEqual(a.mixer_peaks[0],(1.2,.5))
        self.tap('F1');r.update(a,audio,12,12)
        r.receive(a,dict(kind='mixer_meter',first=MASTER,levels=[[.8,.4]],master=[0,0]))
        self.assertEqual(a.mixer_master,(.8,.4));self.assertEqual(a.mixer_peaks[MASTER],(1.2,.5))
        a.button('SHIFT',True);self.assertEqual(a.softkeys(),('-','OUTPUT','RESET'));self.tap('F3');a.button('SHIFT',False)
        self.assertEqual(a.mixer_peaks,{})
        commands.clear();r.update(a,audio,13,13);self.assertIn(f'mixer_watch {MASTER} 1',commands)
        r.receive(a,dict(kind='mixer_meter',first=MASTER,levels=[[.2,.1]],master=[0,0]))
        self.assertEqual(a.mixer_peaks[MASTER],(.2,.1))
        a.page='PAD';self.tap('PLAY');self.assertEqual(a.mixer_peaks,{})
        a.mixer_peaks[0]=(1,1);self.tap('RESTART');self.assertEqual(a.mixer_peaks,{})
    def test_group_leds_use_existing_blue_channels_and_ignore_flash(self):
        import sys
        sys.path.insert(0,str(ROOT/'tools'))
        from mikro_leds import load_pad_channels
        channels=load_pad_channels(ROOT/'captures/mikro-mk1-pad-led-map.json')
        a=self.a;a.page='MIXER';self.tap('F2');a.group=2;a.flash_until[14]=200
        report=led_report(a,channels,100)
        for slot in range(16):self.assertEqual(report[channels[(slot,'orange')]+1],OFF)
        self.assertEqual(report[channels[(14,'blue')]+1],FULL)
        self.assertEqual(report[channels[(13,'blue')]+1],DIM)
    def test_mixer_toggle_returns_to_origin_and_frames_cover_every_scope(self):
        a=self.a;a.page='SAMPLER';a.button('SHIFT',True);self.tap('VIEW');a.button('SHIFT',False)
        self.assertEqual(a.page,'MIXER');frames=[]
        for key in ('F1','F2','F3'):
            self.tap(key);bus,count=a.mixer_watch();a.mixer_levels={bus:(.5,.2)};a.mixer_peaks={bus:(1.1,.7)}
            state=live_state(a);snapshot=copy.deepcopy(state);a.mixer_levels[bus]=(0,0)
            self.assertEqual(state,snapshot);frames.append(live_frame(state));self.assertEqual(len(frames[-1]),8192)
            self.assertLess(len(__import__('pickle').dumps(state)),1024)
        self.assertEqual(len(set(frames)),3)
        a.button('SHIFT',True);self.tap('VIEW');a.button('SHIFT',False);self.assertEqual(a.page,'SAMPLER')

    def test_all_scopes_update_in_display_worker_during_playback(self):
        from app.step_display import StepDisplay
        from app.display_budget import DisplayBudget
        a=self.a;a.page='MIXER';a.playing=True
        budget=DisplayBudget();budget.measured(.1)
        self.assertFalse(budget.available(1,1.002,True))
        worker=StepDisplay();self.addCleanup(worker.close)
        def receive():
            deadline=time.monotonic()+3
            while time.monotonic()<deadline:
                pixels=worker.poll()
                if pixels is not None:return pixels
                time.sleep(.002)
            self.fail('Mixer worker stalled')
        for key in ('F1','F2','F3'):
            self.tap(key);bus,count=a.mixer_watch()
            a.mixer_levels={bus:(.8,.4)};worker.submit(live_state(a));sounding=receive()
            a.mixer_levels={};worker.submit(live_state(a));silent=receive()
            self.assertNotEqual(sounding,silent)



@unittest.skipUnless((ROOT/'build/audio_engine').exists() and Path('/usr/share/alsa/alsa.conf').exists(),'Linux native build required')
class MixerNativeTests(unittest.TestCase):
    def test_real_group_and_master_post_fader_pan_peaks(self):
        from app.audio import AudioBackend
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);config=root/'alsa.conf'
            config.write_text('</usr/share/alsa/alsa.conf>\n'+f'pcm.fixture {{ type file slave.pcm "null" file "{root / "out.raw"}" format "raw" }}\n')
            a=Application(root);a.track()['gain']=100;a.project['groups'][0]['gain']=50;a.project['gain']=50
            a.project['groups'][0]['routing']={'pan':50}
            commands=[];b=AudioBackend.__new__(AudioBackend);b.command=commands.append
            b.desired=b.recorder=b.capture_pending=b.native_capture=None;b.input_device='-';b.routing_signature=None;b.routing(a.project)
            p=subprocess.Popen([str(ROOT/'build/audio_engine')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=dict(os.environ,ALSA_CONFIG_PATH=str(config)))
            def send(command):p.stdin.write(command+'\n');p.stdin.flush()
            try:
                send(commands[-1]);self.assertEqual(json.loads(p.stdout.readline())['kind'],'routing')
                sample=root/'sample.f32';sample.write_bytes(array.array('f',[.5,.25]*256).tobytes())
                send('load 0 48000 '+json.dumps(str(sample)));send('device "fixture" 48000');self.assertEqual(json.loads(p.stdout.readline())['status'],'ready')
                send(f'mixer_watch {GROUP_BASE} 8');send('hit 0 1 1');time.sleep(.03)
                send(f'mixer_status {GROUP_BASE} 8');event=json.loads(p.stdout.readline())
                self.assertEqual(event['levels'][0],[.125,.125]);self.assertEqual(event['levels'][1],[0,0])
                self.assertEqual(event['master'],[.0625,.0625])
                send(f'mixer_watch {MASTER} 1');send('hit 0 1 1');time.sleep(.03)
                send(f'mixer_status {MASTER} 1');event=json.loads(p.stdout.readline())
                r=RuntimeAudio();a.page='MIXER';a.mixer_level=0;r.watch=(MASTER,1);r.receive(a,event)
                self.assertEqual(a.mixer_master,(.0625,.0625))
                send('quit');_,error=p.communicate(timeout=5);self.assertEqual(p.returncode,0,error)
            finally:
                if p.poll() is None:p.kill();p.communicate()
