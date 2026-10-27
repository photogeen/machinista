import array
import copy
import io
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import time
import unittest
from unittest.mock import patch,Mock
import wave
from app.audio_import import decode_mp3,prepare_mp3,AudioImports
from app.browser import Browser,Source
from app.model import Application
from app.web_server import Library
from app.audio import AudioBackend

@unittest.skipUnless(shutil.which('ffmpeg'),'FFmpeg decoder required')
class Mp3Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixtures=tempfile.TemporaryDirectory();cls.addClassCleanup(cls.fixtures.cleanup)
        root=Path(cls.fixtures.name);source=root/'tone.wav'
        with wave.open(str(source),'wb') as w:
            w.setparams((1,2,44100,0,'NONE','NONE'));w.writeframes(array.array('h',(int(12000*math.sin(i*.03)) for i in range(22050))).tobytes())
        cls.mp3=root/'tone.mp3'
        subprocess.run([shutil.which('ffmpeg'),'-loglevel','error','-y','-i',str(source),'-c:a','libmp3lame',str(cls.mp3)],check=True)
        cls.body=cls.mp3.read_bytes()
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.mp3=self.root/'Loop.MP3';self.mp3.write_bytes(self.body)
    def test_real_decode_cache_and_sampler_pcm_survive_source_removal(self):
        prepared=prepare_mp3(self.mp3,self.root/'cache')
        with wave.open(prepared['sample'],'rb') as w:
            self.assertEqual((w.getnframes(),w.getnchannels(),w.getframerate(),w.getsampwidth()),(22050,1,44100,4))
        self.assertEqual(Path(prepared['_ready_pcm'][1]).stat().st_size,22050*8)
        with patch('app.audio_import.decode_mp3',side_effect=AssertionError('must reuse cache')):
            self.assertEqual(prepare_mp3(self.mp3,self.root/'cache'),prepared)
        self.mp3.unlink()
        self.assertTrue(Path(prepared['sample']).is_file())
        backend=object.__new__(AudioBackend);backend.loaded={};backend.command=Mock();backend.cache=self.root
        with patch('app.audio.convert_sample',side_effect=AssertionError('no conversion on UI thread')):
            backend._load_available_asset(1,prepared)
        self.assertIn('load 1 44100',backend.command.call_args_list[0].args[0])
    def test_upload_converts_mp3_to_wav_and_never_overwrites(self):
        library=Library(self.root,lambda:[]);library.samples.mkdir()
        result=library.upload('sd','','Loop.mp3',io.BytesIO(self.body),len(self.body))
        self.assertEqual(result['saved_name'],'Loop.wav');self.assertIn('MP3',result['converted'])
        with wave.open(str(library.samples/'Loop.wav')) as w:self.assertEqual(w.getnframes(),22050)
        with self.assertRaises(FileExistsError):library.upload('sd','','Loop.mp3',io.BytesIO(self.body),len(self.body))
        self.assertEqual(sorted(p.name for p in library.samples.iterdir()),['Loop.wav'])
    def test_invalid_mp3_leaves_no_files_and_source_unchanged(self):
        library=Library(self.root,lambda:[]);library.samples.mkdir()
        with self.assertRaisesRegex(ValueError,'MP3'):library.upload('sd','','Bad.mp3',io.BytesIO(b'not mp3'),7)
        self.assertEqual(list(library.samples.iterdir()),[]);self.assertEqual(self.mp3.read_bytes(),self.body)
    def test_browser_lists_mp3_on_sd_and_readonly_usb(self):
        sd=self.root/'sd';usb=self.root/'usb';sd.mkdir();usb.mkdir()
        (sd/'Kit.mp3').write_bytes(self.body);(usb/'Loop.MP3').write_bytes(self.body)
        b=Browser(sd);self.assertEqual(b.entries(),[sd/'Kit.mp3'])
        b.refresh([Source('USB',usb,read_only=True)]);b.directory=usb
        self.assertEqual(b.open(),usb/'Loop.MP3')
        self.assertEqual(prepare_mp3(b.open(),self.root/'cache')['end'],22050)
        self.assertEqual(sorted(p.name for p in usb.iterdir()),['Loop.MP3'])
    def test_controller_load_is_deferred_and_targets_original_pad(self):
        a=Application(self.root/'app');sample=a.samples/'Loop.mp3';sample.write_bytes(self.body)
        a.page='BROWSE';a.browser.directory=a.samples;a.actions=[];a.enter()
        self.assertIsNone(a.track()['sample']);self.assertEqual(a.actions[-1][0],'import_mp3')
        source,context=a.actions[-1][1];prepared=prepare_mp3(source,a.root/'cache')
        a.pad=3;self.assertTrue(a.finish_mp3_import(context,prepared))
        self.assertEqual(a.project['groups'][0]['pads'][0]['sample'],prepared['sample'])
        self.assertIsNone(a.track()['sample'])
        self.assertNotIn('_ready_pcm',a.project['groups'][0]['pads'][0])
        self.assertIn('_ready_pcm',a.actions[-1][1][2])
    def test_stale_project_or_changed_pad_never_receives_decode(self):
        a=Application(self.root/'app');sample=a.samples/'Loop.mp3';sample.write_bytes(self.body)
        a.page='BROWSE';a.browser.directory=a.samples;a.enter();source,context=a.actions[-1][1]
        result=prepare_mp3(source,a.root/'cache');a.track()['gain']=35
        self.assertFalse(a.finish_mp3_import(context,result));self.assertIsNone(a.track()['sample'])
        a.enter();source,context=a.actions[-1][1];a.project_generation+=1
        self.assertFalse(a.finish_mp3_import(context,result));self.assertIsNone(a.track()['sample'])
    def test_quick_browse_returns_to_original_mp3(self):
        a=Application(self.root/'app');sample=a.samples/'Loop.mp3';sample.write_bytes(self.body)
        a.page='BROWSE';a.browser.directory=a.samples;a.enter();source,context=a.actions[-1][1]
        result=prepare_mp3(source,a.root/'cache');self.assertTrue(a.finish_mp3_import(context,result))
        a.browser.directory=None;a.quick_browse_sample()
        self.assertEqual(a.browser.selected(),sample.resolve())
    def test_mp3_zone_load_uses_existing_zone_workflow(self):
        a=Application(self.root/'app');sample=a.samples/'Loop.mp3';sample.write_bytes(self.body)
        a.page='BROWSE';a.browser.directory=a.samples;a.zone_browse=True;a.enter()
        source,context=a.actions[-1][1];result=prepare_mp3(source,a.root/'cache')
        self.assertTrue(a.finish_mp3_import(context,result));self.assertEqual(a.page,'ZONE')
        self.assertEqual(a.zone()['sample'],result['sample'])
    def test_prepared_pcm_reaches_zone_after_target_pad_changes(self):
        result=prepare_mp3(self.mp3,self.root/'cache')
        old=self.root/'old.wav'
        with wave.open(str(old),'wb') as w:w.setparams((1,2,44100,0,'NONE','NONE'));w.writeframes(bytes(100))
        old_stamp=old.stat();backend=object.__new__(AudioBackend)
        backend.loaded={0:(str(old.resolve()),old_stamp.st_mtime_ns,old_stamp.st_size)};backend.command=Mock();backend._params=Mock();backend.cache=self.root
        track=dict(sample=str(old),start=0,end=50,zones=[dict(sample=result['sample'],start=0,end=result['end'])],_ready_pcm=result['_ready_pcm'])
        with patch('app.audio.convert_sample',side_effect=AssertionError('zone must use prepared PCM')):backend.load(0,0,track)
        self.assertTrue(any('44100' in c.args[0] and result['_ready_pcm'][1] in c.args[0] for c in backend.command.call_args_list))
    def test_cancellation_and_limits_reject_partial_decodes(self):
        cancel=threading.Event();cancel.set()
        with self.assertRaises(ValueError):prepare_mp3(self.mp3,self.root/'cache',cancel)
        self.assertFalse(any((self.root/'cache').rglob('*.wav')))
        with patch('app.audio_import.MAX_DECODED',1000):
            with self.assertRaisesRegex(ValueError,'too long'):prepare_mp3(self.mp3,self.root/'cache')
    def test_stereo_vbr_48khz_decode(self):
        source=self.root/'stereo.wav';mp3=self.root/'stereo.mp3'
        with wave.open(str(source),'wb') as w:
            w.setparams((2,2,48000,0,'NONE','NONE'));w.writeframes(array.array('h',[10000,-10000]*24000).tobytes())
        subprocess.run([shutil.which('ffmpeg'),'-loglevel','error','-y','-i',str(source),'-q:a','3',str(mp3)],check=True)
        result=prepare_mp3(mp3,self.root/'cache')
        with wave.open(result['sample'],'rb') as w:self.assertEqual((w.getnchannels(),w.getframerate(),w.getnframes()),(2,48000,24000))
    @unittest.skipUnless(Path('/usr/share/alsa/alsa.conf').exists() and (Path(__file__).resolve().parents[1]/'build/audio_engine').exists(),'Linux native sampler required')
    def test_decoded_mp3_renders_through_native_sampler(self):
        result=prepare_mp3(self.mp3,self.root/'cache');output=self.root/'render.raw';config=self.root/'alsa.conf'
        config.write_text('</usr/share/alsa/alsa.conf>\n'+f'pcm.fixture {{ type file slave.pcm "null" file "{output}" format "raw" }}\n')
        engine=Path(__file__).resolve().parents[1]/'build/audio_engine'
        process=subprocess.Popen([str(engine)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=dict(os.environ,ALSA_CONFIG_PATH=str(config)))
        try:
            process.stdin.write(f'load 0 44100 {json.dumps(result["_ready_pcm"][1])}\ndevice "fixture" 48000\n');process.stdin.flush()
            self.assertEqual(json.loads(process.stdout.readline())['status'],'ready')
            process.stdin.write('hit 0 0.5\n');process.stdin.flush();time.sleep(.1)
            process.stdin.write('quit\n');process.stdin.flush();_,errors=process.communicate(timeout=5)
            self.assertEqual(process.returncode,0,errors)
            values=array.array('h');values.frombytes(output.read_bytes());self.assertGreater(sum(v!=0 for v in values),1000)
        finally:
            if process.poll() is None:process.kill();process.communicate()

class ImportJobTests(unittest.TestCase):
    def test_slow_preview_is_cancellable_and_load_takes_priority(self):
        started=threading.Event();seen=[]
        def prepare(path,cache,cancel):
            seen.append(path)
            if path=='old':started.set();cancel.wait(2)
            return {'sample':path}
        jobs=AudioImports('/tmp',prepare);self.addCleanup(jobs.close)
        t=time.monotonic();jobs.request('preview','old',None);self.assertLess(time.monotonic()-t,.1)
        self.assertTrue(started.wait(1));jobs.request('preview','new',None);jobs.request('load','load',{'target':1})
        end=time.monotonic()+3;results=[]
        while jobs.busy and time.monotonic()<end:
            result=jobs.poll()
            if result:results.append(result)
            time.sleep(.005)
        self.assertEqual(seen,['old','load']);self.assertTrue(results[0][-1]);self.assertEqual(results[-1][0],'load')
