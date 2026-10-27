// Capture the actual local WebUI with isolated example API data; no Pi or live engine.
const {chromium}=require(process.env.MACHINISTA_PLAYWRIGHT || 'playwright');
const fs=require('fs'),http=require('http'),path=require('path');
const out=path.resolve('assets/manual-web');fs.mkdirSync(out,{recursive:true});
const chord={version:1,name:'Evening Keys',root:60,chords:[{input:60,name:'Cmaj7',notes:[60,64,67,71]},{input:62,name:'Dm7',notes:[62,65,69,72]}]};
const draft={name:'Electric Piano',folder:'Keys',tags:['keys','warm'],kind:'SAMPLER',zones:[{sample:'Piano C3.wav',root:60,key_lo:0,key_hi:65,vel_lo:1,vel_hi:127},{sample:'Piano C4.wav',root:72,key_lo:66,key_hi:127,vel_lo:1,vel_hi:127}],sampler:{type:'ADSR',polyphony:16,release:150}};
const context={available:true,busy:false,playing:false,recording:false,group:0,pad:0,name:'Electric Piano',audio:'USB Audio',midi_outputs:[],inputs:[],autosampler:{state:'IDLE'},plugins:[]};
const data={
'/api/session':{token:'manual-example'},'/api/sources':[{id:'sd',name:'SD CARD',readOnly:false}],
'/api/list':{source:'sd',path:'',writable:true,entries:[{name:'Library',folder:true},{name:'Kick 01.wav',folder:false,bytes:44100,size:44100}]},
'/api/system':{hostname:'machinista',cpu:40,cpu_cores:[100,35,10,15].map((percent,id)=>({id,percent})),ram:{percent:18,used:720000000,total:4000000000},storage:[{name:'SD CARD',percent:12,used:3800000000,total:32000000000}],temperature:43,uptime:3600},
'/api/ssh':{active:false,enabled:false,user:'machinista'},'/api/power':{available:true},'/api/network':{mode:'hotspot',ssid:'Machinista-12AB'},'/api/network/scan':{networks:[{ssid:'Home Wi-Fi',signal:80,security:'WPA2'}]},
'/api/projects':[{id:'first-beat',name:'First Beat',current:true,modified:1792324800}],
'/api/chords':[{id:'evening-keys',preset:chord}],
'/api/sounds':{folders:['Keys'],sounds:[{id:'electric-piano',name:'Electric Piano',folder:'Keys',tags:['keys','warm'],kind:'SAMPLER',zones:2}],job:{state:'IDLE'}},
'/api/sounds/runtime':context,'/api/sounds/item':draft,'/api/sounds/current':draft,
'/api/plugin-banks':[{id:'dexed',uri:'https://github.com/dcoredump/dexed.lv2',name:'Dexed',banks:[{id:'warm',name:'Warm Circuits',patches:32,canDelete:true}]}],
'/api/lv2':{target:'ARM64',busy:false,jobs:[],bundles:[],error:''},
'/api/virtualjv':{available:false,banks:[],uploads:[],runtime:{plugins:[]}},
};
(async()=>{let server=http.createServer((q,r)=>{const name=q.url==='/'?'index.html':q.url.slice(1);const p=path.join(process.cwd(),'web',name);if(!fs.existsSync(p)){r.writeHead(404);return r.end()}r.setHeader('Content-Type',name.endsWith('.js')?'text/javascript':name.endsWith('.css')?'text/css':name.endsWith('.png')?'image/png':'text/html');r.end(fs.readFileSync(p))}).listen(8789,'127.0.0.1');let browser;
try{browser=await chromium.launch({headless:true,...(process.env.MACHINISTA_CHROME ? {executablePath:process.env.MACHINISTA_CHROME} : {})});const page=await browser.newPage({viewport:{width:1440,height:1200},deviceScaleFactor:1.5});await page.route('**/api/**',route=>{const p=new URL(route.request().url()).pathname;return route.fulfill({contentType:'application/json',body:JSON.stringify(data[p]||{})})});await page.route('http://machinista.local:8080/**',route=>{const n=new URL(route.request().url()).pathname;if(n.startsWith('/api/'))return route.fallback();const name=n==='/'?'index.html':n.slice(1),file=path.join(process.cwd(),'web',name);return route.fulfill({contentType:name.endsWith('.js')?'text/javascript':name.endsWith('.css')?'text/css':name.endsWith('.png')?'image/png':'text/html',body:fs.readFileSync(file)})});await page.goto('http://machinista.local:8080/');await page.waitForTimeout(400);
async function shot(name,selector){await page.locator(selector).screenshot({path:path.join(out,name+'.png')});console.log(name)}
await shot('library','#sample-panel');await shot('system','aside');await shot('network','#wifi-form');await shot('ssh','.ssh');await shot('power','.power');
await page.locator('#tab-projects').click();await shot('projects','#project-panel');
await page.locator('#tab-chords').click();await page.locator('#chords-list button').filter({hasText:/^Edit$/}).click();await shot('chords','#chords-panel');await shot('chord-editor','#chords-editor');
await page.locator('#tab-lv2').click();await shot('plugins','#lv2-panel');await page.locator('#tab-banks').click();await shot('patch-banks','#banks-panel');
await page.locator('#tab-sounds').click();await page.locator('#sounds-list > details > summary').first().click();await page.locator('#sounds-list > details > details > summary').first().click();await page.locator('#sounds-list button').filter({hasText:/^Edit$/}).click();await shot('zones','#sound-editor');await shot('zone-map','#zone-map');await shot('zone-table','#sound-editor .file-table');
await page.locator('#sound-cancel').click();await page.locator('#sound-capture').click();await page.locator('#sound-capture-name').fill('Electric Piano Live');await shot('patch','#sound-name-dialog');await page.locator('#sound-capture-cancel').click();
await page.locator('#sound-auto-open').click();await page.locator('#auto-name').fill('Electric Piano Sampled');await shot('autosampler','#autosampler-form');
}finally{await browser?.close();server.close()}})().catch(e=>{console.error(e);process.exitCode=1});
