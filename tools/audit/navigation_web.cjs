// Capture the actual local WebUI with isolated example API data; no Pi or live engine.
const {chromium}=require(process.env.MACHINISTA_PLAYWRIGHT || 'playwright');
const fs=require('fs'),http=require('http'),path=require('path');
const out=path.resolve('diagnostics/navigation-web-review');fs.mkdirSync(out,{recursive:true});
const chord={version:1,name:'Evening Keys',root:60,chords:[{input:60,name:'Cmaj7',notes:[60,64,67,71]},{input:62,name:'Dm7',notes:[62,65,69,72]}]};
const draft={name:'Electric Piano',folder:'Keys',tags:['keys','warm'],kind:'SAMPLER',zones:[{sample:'Piano C3.wav',root:60,key_lo:0,key_hi:65,vel_lo:1,vel_hi:127},{sample:'Piano C4.wav',root:72,key_lo:66,key_hi:127,vel_lo:1,vel_hi:127}],sampler:{type:'ADSR',polyphony:16,release:150}};
const context={available:true,busy:false,playing:false,recording:false,group:0,pad:0,name:'Electric Piano',audio:'USB Audio',midi_outputs:[],inputs:[],autosampler:{state:'IDLE'},plugins:[]};
const data={
'/api/session':{token:'manual-example'},'/api/sources':[{id:'sd',name:'SD CARD',readOnly:false}],
'/api/list':{source:'sd',path:'',writable:true,entries:[{name:'Library',folder:true},{name:'Kick 01.wav',folder:false,bytes:44100,size:44100}]},
'/api/system':{hostname:'machinista',cpu:8,ram:{percent:18,used:720000000,total:4000000000},storage:[{name:'SD CARD',percent:12,used:3800000000,total:32000000000}],temperature:43,uptime:3600},
'/api/ssh':{active:false,enabled:false,user:'machinista'},'/api/power':{available:true},'/api/network':{mode:'hotspot',ssid:'Machinista-12AB'},'/api/network/scan':{networks:[{ssid:'Home Wi-Fi',signal:80,security:'WPA2'}]},
'/api/projects':[{id:'first-beat',name:'First Beat',current:true,modified:1792324800}],
'/api/chords':[{id:'evening-keys',preset:chord}],
'/api/sounds':{folders:['Keys'],sounds:[{id:'electric-piano',name:'Electric Piano',folder:'Keys',tags:['keys','warm'],kind:'SAMPLER',zones:2}],job:{state:'IDLE'}},
'/api/sounds/runtime':context,'/api/sounds/item':draft,'/api/sounds/current':draft,
'/api/lv2':{target:'ARM64',busy:false,jobs:[],bundles:[],error:''},
'/api/virtualjv':{available:false,banks:[],uploads:[],runtime:{plugins:[]}},
};

const assert=require('assert');
(async()=>{let browser;try{browser=await chromium.launch({headless:true,executablePath:process.env.MACHINISTA_CHROME});const page=await browser.newPage({viewport:{width:1440,height:1000}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
await page.route('http://machinista.local:8080/**',async route=>{const u=new URL(route.request().url());if(u.pathname.startsWith('/api/')){let value=data[u.pathname]||{};if(u.pathname==='/api/upload')value={saved_name:'Kick.wav'};if(u.pathname==='/api/sounds'){value={...data[u.pathname],folders:['','Electric Pianos','Keys','Keys/Electric Piano'],sounds:[{...data[u.pathname].sounds[0],folder:'Keys/Electric Piano'}]};if(created)value.folders.push(created)}if(u.pathname==='/api/sounds/folder')created=JSON.parse(route.request().postData()).folder;return route.fulfill({contentType:'application/json',body:JSON.stringify(value)})}const name=u.pathname==='/'?'index.html':u.pathname.slice(1),file=path.join(process.cwd(),'web',name);return route.fulfill({contentType:name.endsWith('.js')?'text/javascript':name.endsWith('.css')?'text/css':name.endsWith('.png')?'image/png':'text/html',body:fs.readFileSync(file)})});let created='';
await page.goto('http://machinista.local:8080/');await page.waitForTimeout(300);await page.clock.install();
await page.locator('#files').setInputFiles({name:'Kick.wav',mimeType:'audio/wav',buffer:Buffer.from('fixture')});await page.waitForFunction(()=>document.querySelector('#message').textContent.includes('uploaded'));
assert.equal(await page.locator('.upload-row').count(),1);await page.clock.runFor(5100);assert.equal(await page.locator('.upload-row').count(),0);assert.equal(await page.locator('#message').textContent(),'');
await page.locator('#tab-sounds').click();await page.waitForFunction(()=>document.querySelector('#sound-folder-filter').options.length===4);const options=await page.locator('#sound-folder-filter option').allTextContents();assert(options.some(t=>t.includes('↳ Electric Piano (1)')));assert(options.includes('Electric Pianos (0)'));
await page.locator('#sound-folder-filter').selectOption('Keys');assert.equal(await page.locator('.sound-card').count(),1);await page.locator('#sound-new').click();assert.equal(await page.locator('#sound-folder').inputValue(),'Keys');await page.locator('#sound-cancel').click();page.once('dialog',d=>d.accept('New Keys'));await page.locator('#sound-folder-new').click();await page.waitForFunction(()=>document.querySelector('#sound-folder-filter').value==='Keys/New Keys');assert.equal(created,'Keys/New Keys');await page.locator('#sound-folder-filter').selectOption('');await page.locator('#sounds-panel').screenshot({path:path.join(out,'sounds-folders.png')});assert.deepEqual(errors,[]);fs.writeFileSync(path.join(out,'browser-test.json'),JSON.stringify({passed:true,options,created,errors},null,2));console.log('Browser checks passed: upload timeout, folder tree/counts, inherited folder, relative creation; no JS errors.');}finally{await browser?.close()}})().catch(e=>{console.error(e);process.exitCode=1});
