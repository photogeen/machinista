// Capture the actual local WebUI with isolated example API data; no Pi or live engine.
const {chromium}=require(process.env.MACHINISTA_PLAYWRIGHT || 'playwright');
const fs=require('fs'),http=require('http'),path=require('path');
const out=path.resolve('diagnostics/per-core-cpu-review');fs.mkdirSync(out,{recursive:true});
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
(async()=>{let browser;try{data['/api/system'].cpu=40;data['/api/system'].cpu_cores=[100,35,10,15].map((percent,id)=>({id,percent}));browser=await chromium.launch({headless:true,executablePath:process.env.MACHINISTA_CHROME});const page=await browser.newPage({viewport:{width:1440,height:1200}});const errors=[];page.on('pageerror',e=>errors.push(e.message));await page.route('http://machinista.local:8080/**',route=>{const u=new URL(route.request().url());if(u.pathname.startsWith('/api/'))return route.fulfill({contentType:'application/json',body:JSON.stringify(data[u.pathname]||{})});const name=u.pathname==='/'?'index.html':u.pathname.slice(1);return route.fulfill({contentType:name.endsWith('.js')?'text/javascript':name.endsWith('.css')?'text/css':name.endsWith('.png')?'image/png':'text/html',body:fs.readFileSync(path.join(process.cwd(),'web',name))})});await page.goto('http://machinista.local:8080/');await page.waitForFunction(()=>document.querySelectorAll('.cpu-cores .meter').length===4);assert.deepEqual(await page.locator('.cpu-cores [role="progressbar"]').evaluateAll(rows=>rows.map(e=>Number(e.getAttribute('aria-valuenow')))),[100,35,10,15]);assert((await page.locator('#resources').textContent()).includes('Core 4'));await page.locator('aside').screenshot({path:path.join(out,'web.png')});assert.deepEqual(errors,[]);console.log('Per-core WebUI meters, labels and ARIA values passed; no JS errors.')}finally{await browser?.close()}})().catch(e=>{console.error(e);process.exitCode=1});
