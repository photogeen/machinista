const {chromium}=require(process.env.MACHINISTA_PLAYWRIGHT||'playwright');
const fs=require('fs'),path=require('path'),assert=require('assert');
const root=process.cwd(),out=path.join(root,'output/native-synth');
const schema=JSON.parse(fs.readFileSync(path.join(out,'web-schema-fixture.json')));
const uri='urn:machinista:instrument:synth';let context={available:true,group:0,pad:3,generation:0,revision:0,name:'Soft Saw Keys',plugins:[{uri,kind:'INSTRUMENT',controls:Object.fromEntries(schema.parameters.map(p=>[p.symbol,p.default])),synth_waves:{},profile_preset:{bank:'init',program:0}}]},writes=[];
const fixture={'/api/session':{token:'test'},'/api/sources':[{id:'sd',name:'SD CARD'}],'/api/list':{entries:[],writable:true},'/api/system':{hostname:'machinista',cpu:4,ram:{percent:12},storage:[]},'/api/ssh':{active:false},'/api/network':{mode:'hotspot'},'/api/virtualjv':{available:false}};
(async()=>{let browser;try{browser=await chromium.launch({headless:true,executablePath:process.env.MACHINISTA_CHROME||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});const page=await browser.newPage({viewport:{width:1500,height:1100}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
await page.route('http://machinista.local:8080/**',async route=>{const r=route.request(),u=new URL(r.url());let value=fixture[u.pathname]||{},status=200;
 if(u.pathname.startsWith('/api/')){
  if(u.pathname==='/api/synth')value=schema;
  if(u.pathname==='/api/sounds/runtime')value=context;
  if(u.pathname==='/api/sounds/command'){const body=JSON.parse(r.postData());writes.push(body);assert.equal(r.headers()['x-machinista-token'],'test');if(body.revision!==context.revision||body.pad!==context.pad){status=400;value={error:'Selected Sound changed. Refresh the current Sound first.'}}else {assert.equal(body.operation,'synth_edit');Object.assign(context.plugins[0].controls,body.controls||{});context.revision++;value={ok:true,group:context.group,pad:context.pad,generation:0,revision:context.revision}}}
  return route.fulfill({status,contentType:'application/json',body:JSON.stringify(value)})
 }
 const name=u.pathname==='/'?'index.html':u.pathname.slice(1);return route.fulfill({contentType:name.endsWith('.js')?'text/javascript':name.endsWith('.css')?'text/css':name.endsWith('.png')?'image/png':'text/html',body:fs.readFileSync(path.join(root,'web',name))})});
await page.goto('http://machinista.local:8080/');await page.locator('#tab-synth').click();await page.locator('#synth-controls .synth-control').first().waitFor();
const seen=new Set();async function collect(){for(const s of await page.locator('.synth-control').evaluateAll(rows=>rows.map(n=>n.dataset.symbol)))seen.add(s)}
await collect();
const level=page.getByLabel('Exact LEVEL osc1_level',{exact:true});await level.fill('42');await level.dispatchEvent('change');await page.waitForFunction(()=>document.querySelector('#synth-message').textContent.startsWith('Changes applied'));
assert.equal(context.plugins[0].controls.osc1_level,.42);
const dial=page.locator('[data-symbol=osc1_level] .synth-knob'),bounds=await dial.boundingBox();await page.mouse.move(bounds.x+bounds.width/2,bounds.y+bounds.height/2);await page.mouse.down();const during=writes.length;await page.mouse.move(bounds.x+bounds.width/2,bounds.y+bounds.height/2-20,{steps:10});await page.waitForTimeout(130);assert(writes.length>during,'Knob edits must reach audio while the pointer is still held');await page.mouse.up();await page.waitForTimeout(200);assert(Math.abs(context.plugins[0].controls.osc1_level-.52)<.002,'Dragging the dial must apply immediately and stop on release: '+context.plugins[0].controls.osc1_level);

await page.getByLabel('WAVE osc1_wave',{exact:true}).selectOption('f:24');await page.waitForTimeout(150);assert.equal(context.plugins[0].controls.osc1_wave,24);assert.equal(await page.locator('[data-symbol=osc1_shape] .synth-label').textContent(),'POSITION');
await page.locator('#synth-panel').screenshot({path:path.join(out,'web-synth-editor-desktop.png')});await page.locator('#synth-controls').screenshot({path:path.join(root,'assets/manual-web/synth-editor.png')});
for(let i=1;i<=4;i++){await page.locator('#synth-subtabs').getByRole('button',{name:'OSC '+i,exact:true}).click();await collect()}
for(const category of ['Filters','Envelopes','LFOs','Matrix','Voicing']){
 await page.locator('#synth-tabs').getByRole('button',{name:category,exact:true}).click();await collect();
 if(category==='Envelopes'||category==='LFOs'){const buttons=page.locator('#synth-subtabs button');for(let i=0;i<4;i++){await buttons.nth(i).click();await collect()}}
 if(category==='Matrix'){for(let i=1;i<=32;i++){await page.getByLabel('Modulation route',{exact:true}).selectOption(String(i));await collect()}}
}
assert.equal(seen.size,588,'Every DSP parameter must remain accessible in the web editor');
await page.locator('#synth-tabs').getByRole('button',{name:'Envelopes',exact:true}).click();
await page.locator('#synth-panel').screenshot({path:path.join(out,'web-synth-editor-envelope.png')});
await page.setViewportSize({width:425,height:950});await page.locator('#synth-panel').screenshot({path:path.join(out,'web-synth-editor-mobile.png')});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'mobile horizontal overflow');
// Stale browser target must never overwrite a newly selected pad.
context.pad=7;await page.getByLabel('Exact ATTACK env1_attack',{exact:true}).fill('30');await page.getByLabel('Exact ATTACK env1_attack',{exact:true}).dispatchEvent('change');await page.waitForFunction(()=>document.querySelector('#synth-message').classList.contains('error'));assert.equal(context.plugins[0].controls.env1_attack,5);
assert.deepEqual(errors,[]);fs.writeFileSync(path.join(out,'compact-browser-test.json'),JSON.stringify({passed:true,parameters:seen.size,writes:writes.length,errors},null,2));console.log('All 588 parameters reachable; live edits, units, source changes, stale-target rejection, desktop/mobile passed.');
}finally{await browser?.close()}})().catch(e=>{console.error(e);process.exitCode=1});
