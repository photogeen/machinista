import base64,hashlib,io,json,os,subprocess,tarfile,tempfile,time,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch,Mock
from app.update_manager import Manager,atomic,version,manifest,members,replace_file,verify_signature,BUSY
from app.model import Application
from app.updater import enabled,command
from app.controller_inputs import ControllerInputs
from app.mk3_surface import Mk3Surface
from app.mk3_state import snapshot
from app.mk3_display import Mk3Renderer

ELF=b'\x7fELF\x02\x01'+b'\0'*12+b'\xb7\0'+b'example audio executable'
def archive(path,changes=None):
 files={'app/branding.py':b"VERSION = '0.1.1'\n",'tools/machinista.py':b'new code','build/audio_engine':ELF,'app/new_module.py':b'new module'}
 files.update(changes or {})
 with tarfile.open(path,'w:gz') as tar:
  for name,data in files.items():
   m=tarfile.TarInfo(name);m.size=len(data);tar.addfile(m,io.BytesIO(data))
 return files

class UpdaterTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.base=Path(self.tmp.name).resolve();self.root=self.base/'app';self.root.mkdir()
  self.runtime=self.base/'runtime';(self.runtime/'app').mkdir(parents=True);self.state=self.base/'state';self.calls=[]
  self.pkg=self.base/'update.tar.gz';self.files=archive(self.pkg)
  for name in ('app/branding.py','tools/machinista.py','build/audio_engine','config/settings.json','projects/current.json','samples/keep.wav','presets/custom.json'):
   p=self.root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(('original:'+name).encode())
  self.cfg=dict(enabled=True,repository='example/machinista',public_key='test-key',current_version='0.1.0-beta.6')
  self.feed=dict(schema=1,version='0.1.1',minimum_version='0.1.0-beta.6',channel='release',architecture='arm64',os_codename='trixie',notes='Example',artifact=dict(url='https://github.com/example/machinista/releases/download/v0.1.1/update.tar.gz',size=self.pkg.stat().st_size,sha256=hashlib.sha256(self.pkg.read_bytes()).hexdigest()))
  self.pulse()
  self.m=Manager(self.cfg,self.root,self.state,self.runtime,os.getuid(),os.getgid(),fetch=self.fetch,verify=lambda *args:None,run=self.fake_run,os_name='trixie',machine='aarch64',lease_path=self.base/'lease')
  self.m.healthy=lambda:None
 def pulse(self,**values):atomic(self.runtime/'app/status.json',dict(updated=time.time(),busy=False,playing=False,pid=1,**values) if not values else dict(dict(updated=time.time(),busy=False,playing=False,pid=1),**values))
 def fetch(self,url,limit,dest=None):
  if dest:Path(dest).write_bytes(self.pkg.read_bytes());return self.pkg.stat().st_size
  if url.endswith('.sig'):return b'signature'
  return json.dumps(self.feed).encode()
 def fake_run(self,args,timeout):self.calls.append(args);return SimpleNamespace(stdout='success')
 def check(self):self.m.command('check');self.m.thread.join(15);self.assertFalse(self.m.thread.is_alive())
 def install(self):
  with patch('app.update_manager.shutil.disk_usage',return_value=SimpleNamespace(free=10*1024**3)),patch('app.update_manager.os.sync'):
   self.m.command('install',channel=self.m.channel,expected=self.feed['version']);self.m.thread.join(15)
   self.assertFalse(self.m.thread.is_alive())
 def test_semantic_versions_and_final_over_prerelease(self):
  self.assertLess(version('0.1.0-beta.9'),version('0.1.0-beta.10'));self.assertLess(version('0.1.0-rc.1'),version('0.1.0'))
  for invalid in ('latest','1.0','1.0.0;reboot'):
   with self.assertRaises(ValueError):version(invalid)
 def test_check_and_persistent_channel_do_not_execute_commands(self):
  self.check();self.assertTrue(self.m.status()['available']);self.assertEqual(self.calls,[])
  self.m.command('channel','beta');self.assertIsNone(self.m.latest);self.assertEqual(json.loads((self.state/'channel.json').read_text())['channel'],'beta')
 def test_unconfigured_source_does_not_contact_network_or_install(self):
  self.cfg['repository']=''
  with self.assertRaisesRegex(ValueError,'configured'):self.m.command('check')
  self.assertEqual(self.calls,[])
 def test_administratively_disabled_broker_rejects_actions(self):
  self.cfg['enabled']=False
  for op in ('check','channel','install'):
   with self.assertRaisesRegex(ValueError,'edition'):self.m.command(op,'beta')
 def test_only_reserved_native_factory_assets_can_be_updated(self):
  identity='a'*32
  safe={'presets/plugin-banks/machinista-synth/category-keys.json':b'{}','presets/Oscillators/'+identity+'.json':b'{}','presets/Oscillators/.assets/'+identity+'.mwave':b'MWAVET02'}
  archive(self.pkg,safe);self.assertTrue(set(safe)<=set(members(self.pkg)))
  for name in ('presets/custom.json','presets/plugin-banks/dexed/warm.json','presets/plugin-banks/machinista-synth/user-bank.json','presets/Oscillators/custom.wav'):
   archive(self.pkg,{name:b'user'})
   with self.assertRaises(ValueError):members(self.pkg)
 def test_signed_empty_release_feed_is_configured_but_has_no_installable_update(self):
  self.feed=dict(schema=1,channel='release',available=False,notes='No stable release published yet.')
  self.check();status=self.m.status();self.assertEqual(status['state'],'NO RELEASE');self.assertTrue(status['configured']);self.assertFalse(status['available']);self.assertIsNone(status['latest']);self.assertEqual(status['notes'],self.feed['notes']);self.assertEqual(self.calls,[])
 def test_empty_feed_cannot_bypass_channel_or_signature_checks(self):
  self.feed=dict(schema=1,channel='beta',available=False)
  self.check();self.assertEqual(self.m.phase,'ERROR')
  self.feed['channel']='release';self.m.verify=lambda *args:(_ for _ in ()).throw(ValueError('bad signature'))
  self.m.work('check');self.assertEqual(self.m.phase,'ERROR');self.assertEqual(self.calls,[])
 def test_incompatible_arch_os_channel_and_url_rejected(self):
  for key,value in [('architecture','x86_64'),('os_codename','bookworm'),('channel','beta')]:
   m=dict(self.feed,**{key:value})
   with self.assertRaises(ValueError):manifest(json.dumps(m),'release',self.cfg,'trixie','aarch64')
  bad=dict(self.feed,artifact=dict(self.feed['artifact'],url='https://github.com/evil/repo/releases/download/x/a.tar.gz'))
  with self.assertRaises(ValueError):manifest(json.dumps(bad),'release',self.cfg,'trixie','aarch64')
 def test_signature_failure_prevents_available_update(self):
  def reject(*args):raise ValueError('bad signature')
  self.m.verify=reject;self.m.work('check');self.assertEqual(self.m.phase,'ERROR');self.assertIsNone(self.m.latest);self.assertEqual(self.calls,[])
 def test_too_old_installed_version_requires_image(self):
  self.feed['minimum_version']='0.1.0';self.m.work('check');self.assertIn('image',self.m.error)
 def test_busy_stale_and_playing_reject_before_any_command(self):
  self.check()
  for pulse in ({'busy':True},{'playing':True},{'updated':time.time()-10}):
   self.pulse(**pulse)
   with self.assertRaises(ValueError):self.m.command('install',channel='release',expected=self.feed['version'])
  self.assertEqual(self.calls,[])
 def test_stale_confirmation_and_concurrent_job_are_rejected(self):
  self.check()
  with self.assertRaises(ValueError):self.m.command('install',channel='beta',expected=self.feed['version'])
  self.m.phase='DOWNLOADING'
  with self.assertRaises(ValueError):self.m.command('channel','beta')
 def test_checksum_failure_does_not_stop_app_or_run_apt(self):
  self.check();self.m.latest['artifact']['sha256']='0'*64;self.install()
  self.assertEqual(self.m.phase,'ERROR');self.assertEqual(self.calls,[])
 def test_success_updates_app_and_os_preserves_all_user_data(self):
  self.check();self.install();self.assertEqual(self.m.phase,'COMPLETE');self.assertTrue(self.m.reboot_required)
  self.assertEqual(self.calls[0][0],'runuser');self.assertEqual(self.calls[1],['systemctl','stop','machinista.service'])
  self.assertIn(['apt-get','update'],self.calls);self.assertIn('dist-upgrade',self.calls[4])
  for f,data in self.files.items():self.assertEqual((self.root/f).read_bytes(),data)
  for f in ('config/settings.json','projects/current.json','samples/keep.wav','presets/custom.json'):self.assertEqual((self.root/f).read_bytes(),('original:'+f).encode())
  self.assertFalse((self.state/'transaction.json').exists());self.assertEqual(self.m.current,self.feed['version'])
 def test_failed_restart_rolls_back_code_but_keeps_user_data(self):
  def fail():raise ValueError('new application failed')
  self.check();self.m.healthy=fail;self.install();self.assertEqual(self.m.phase,'ERROR')
  self.assertEqual((self.root/'tools/machinista.py').read_bytes(),b'original:tools/machinista.py');self.assertFalse((self.root/'app/new_module.py').exists())
  self.assertEqual((self.root/'projects/current.json').read_bytes(),b'original:projects/current.json');self.assertEqual(self.m.current,'0.1.0-beta.6')
 def test_apt_failure_restores_code_and_reports_partial_os_update(self):
  def fail(args,timeout):
   self.calls.append(args)
   if args[0]=='apt-get':raise ValueError('apt failed')
   return SimpleNamespace(stdout='success')
  self.m.run=fail;self.check();self.install();self.assertEqual(self.m.phase,'ERROR');self.assertIn('OS packages',self.m.error)
  self.assertFalse((self.root/'app/new_module.py').exists());self.assertIn(['systemctl','start','machinista.service'],self.calls)
 def test_archive_cannot_overwrite_samples_or_escape_or_install_x86(self):
  for extra in ({'samples/private.wav':b'data'},{'../escape':b'data'},{'build/audio_engine':b'\x7fELF'+b'\0'*25}):
   archive(self.pkg,extra)
   with self.assertRaises(ValueError):members(self.pkg)
 def test_symlink_archive_and_destination_are_rejected(self):
  with tarfile.open(self.pkg,'w:gz') as tar:
   member=tarfile.TarInfo('app/evil');member.type=tarfile.SYMTYPE;member.linkname='/etc/shadow';tar.addfile(member)
  with self.assertRaises(ValueError):members(self.pkg)
  outside=self.base/'outside';outside.mkdir();(self.root/'link').symlink_to(outside,target_is_directory=True)
  with self.assertRaises(OSError):replace_file(self.root,'link/file',b'bad',os.getuid(),os.getgid())
  self.assertFalse((outside/'file').exists())
 def test_interrupted_transaction_restores_previous_code_on_service_start(self):
  self.check();self.install()
  # Retained rollback image is the code before the successful install.
  atomic(self.state/'transaction.json',dict(files=list(self.files),new=['app/new_module.py']))
  self.m.recover();self.assertEqual(self.m.phase,'ERROR');self.assertFalse((self.root/'app/new_module.py').exists());self.assertEqual((self.root/'tools/machinista.py').read_bytes(),b'original:tools/machinista.py')
 def test_check_worker_does_not_release_another_jobs_maintenance_lease(self):
  lease=Mock();self.m.lease=lease;self.m.work('check');lease.close.assert_not_called();self.assertIs(self.m.lease,lease);self.m.lease=None
 def test_real_ed25519_signature_and_modified_manifest(self):
  key=self.base/'key.pem';pub=self.base/'key.pub';raw=self.base/'manifest';sig=self.base/'sig'
  subprocess.run(['openssl','genpkey','-algorithm','ED25519','-out',str(key)],check=True,capture_output=True)
  subprocess.run(['openssl','pkey','-in',str(key),'-pubout','-out',str(pub)],check=True,capture_output=True)
  raw.write_bytes(b'{"version":"example"}')
  subprocess.run(['openssl','pkeyutl','-sign','-rawin','-inkey',str(key),'-in',str(raw),'-out',str(sig)],check=True,capture_output=True)
  pub.chmod(0o644);verify_signature(raw.read_bytes(),base64.b64encode(sig.read_bytes()),pub)
  with self.assertRaises(subprocess.CalledProcessError):verify_signature(b'changed',base64.b64encode(sig.read_bytes()),pub)

class UpdateUITests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.a=Application(self.tmp.name);self.s=Mk3Surface(self.a,ControllerInputs(self.a))
 def test_legacy_public_image_now_shows_update_menu(self):
  root=Path(self.tmp.name);(root/'deploy').mkdir();(root/'deploy/image-edition.json').write_text('{"edition":"public","updater":false}')
  self.a=Application(root);self.a.open_settings('SYSTEM');self.assertIn('UPDATE',self.a.setting_entries());self.assertTrue(enabled(root))
 def test_all_controller_screens_and_channel_actions(self):
  from app.ni_display import frame
  from app.mk2_display import Mk2Renderer,snapshot as mk2_state
  self.a.open_settings('SYSTEM');self.assertIn('UPDATE',self.a.setting_entries());self.a.page='UPDATE'
  self.s.softkey(4);self.assertIn(('update',{'op':'channel','channel':'beta'}),self.a.actions)
  self.assertEqual(len(frame(self.a)),8192)
  r=Mk3Renderer();self.addCleanup(r.close);self.assertEqual(tuple(map(len,r(snapshot(self.s)))),(261120,261120))
  r2=Mk2Renderer();self.addCleanup(r2.close);self.assertEqual(len(r2(mk2_state(self.s))[0]),16384)
  self.s.softkey(3);self.assertEqual(self.a.page,'SETTINGS');self.assertEqual(self.a.settings_folder,'SYSTEM')
 def test_install_requires_confirmation_and_idle(self):
  a=self.a;a.page='UPDATE';a.update_status.update(available=True,latest='0.1.1');a.playing=True
  command(a,'install');self.assertFalse(any(k=='update' for k,v in a.actions));a.playing=False;command(a,'install');self.assertEqual(a.page,'CONFIRM')
 def test_update_handshake_freezes_new_recording_and_notes_and_times_out(self):
  from app.updater import prepare
  a=self.a
  for values in ({'playing':True},{'recording':True},{'capture_armed':True}):
   key,value=next(iter(values.items()));setattr(a,key,value)
   with self.assertRaises(ValueError):prepare(a,False,time.monotonic())
   setattr(a,key,False)
  now=time.monotonic();prepare(a,False,now);before=len(a.actions)
  self.s.button('REC',True);self.s.button('REC',False);a.pad_on(0)
  self.assertFalse(a.recording);self.assertEqual(len(a.actions),before)
  with patch('app.model.time.monotonic',return_value=now+11):a.button('PLAY',True)
  self.assertTrue(a.playing)

class UpdateHTTPTests(unittest.TestCase):
 def setUp(self):
  from app.web_server import Library,Server
  import threading
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
  self.library=Library(self.root,lambda:[]);self.server=Server(('127.0.0.1',0),self.library)
  self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start();self.addCleanup(self.close)
 def close(self):self.server.shutdown();self.server.server_close();self.thread.join(2)
 def call(self,path,method='GET',token=True):
  import http.client
  c=http.client.HTTPConnection('127.0.0.1',self.server.server_port)
  headers={'X-Machinista-Token':self.library.token} if token else {}
  c.request(method,path,headers=headers);r=c.getresponse();result=(r.status,json.loads(r.read()));c.close();return result
 def test_status_and_channel_share_service_and_protect_writes(self):
  with patch('app.updater.request',return_value={'enabled':True,'channel':'beta'}) as call:
   self.assertEqual(self.call('/api/update')[1]['channel'],'beta')
   self.assertEqual(self.call('/api/update?op=channel&channel=beta','POST')[0],200)
   self.assertEqual(call.call_args.args[0]['channel'],'beta')
   self.assertEqual(self.call('/api/update?op=install','POST',False)[0],403)
 def test_legacy_public_marker_no_longer_blocks_service_access(self):
  (self.root/'deploy').mkdir();(self.root/'deploy/image-edition.json').write_text('{"edition":"public","updater":false}')
  with patch('app.updater.request',return_value={'enabled':True,'channel':'release'}):
   self.assertTrue(self.call('/api/update')[1]['enabled'])
   self.assertEqual(self.call('/api/update?op=check','POST')[0],200)

class PublisherTests(unittest.TestCase):
 def test_signed_release_builder_produces_verifiable_compatible_artifact(self):
  import sys
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp).resolve();payload=root/'payload.tar.gz';archive(payload);key=root/'private.pem';pub=root/'public.pem';out=root/'out'
   subprocess.run(['openssl','genpkey','-algorithm','ED25519','-out',str(key)],check=True,capture_output=True)
   subprocess.run(['openssl','pkey','-in',str(key),'-pubout','-out',str(pub)],check=True,capture_output=True)
   subprocess.run([sys.executable,'tools/build_update.py','--payload',str(payload),'--key',str(key),'--repository','example/machinista','--channel','release','--version','0.1.1','--minimum-version','0.1.0-beta.6','--os-codename','trixie','--output',str(out)],check=True,capture_output=True)
   raw=(out/'update.json').read_bytes();pub.chmod(0o644);verify_signature(raw,(out/'update.json.sig').read_bytes(),pub)
   m=manifest(raw,'release',{'repository':'example/machinista'},'trixie','aarch64')
   artifact=out/'machinista-0.1.1-arm64.tar.gz';self.assertEqual(m['artifact']['sha256'],hashlib.sha256(artifact.read_bytes()).hexdigest());self.assertIn('build/audio_engine',members(artifact))
