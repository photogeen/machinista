// SPDX-License-Identifier: GPL-3.0-or-later
import {FORMAT, MAX_BYTES, stepsFor, validateReport, coverage, compactFrames, matchedMidiPorts,emailDraft,availableProfiles,upgradeChecklist} from './core.mjs?v=15';
import {displayInventory,PATTERNS,testImage,sendMono,sendColor,transmissionEvidence,displayCoverage,openColor,sendPrompt} from './displays.mjs?v=10';
import {enableBacklight,restoreBacklight,ledInventory,showLed,clearLeds,ledCoverage} from './outputs.mjs?v=17';
import {createActionDetector} from './guided.mjs?v=17';
const $=id=>document.getElementById(id), profiles=await (await fetch('catalog.json?v=15',{cache:'no-cache'})).json();
const config=await (await fetch('config.json',{cache:'no-cache'})).json();
let report=null, devices=[], midi=null, selectedPorts=new Set(), capture=null, latest=new Map(), stepIndex=0, db=null, saveQueue=Promise.resolve(), displayBusy=false, autoStage='idle', resumeStage='controls', autoDetector=null, autoTimer=null, autoGeneration=0, colorLink=null, promptEnabled=true, skippedDisplays=new Set(),ledIndex=0,ledSent=false,ledBusy=false,ledDetector=null,ledError='';
const hex=b=>Array.from(b,n=>n.toString(16).padStart(2,'0')).join('');
const notify=s=>{$('message').textContent=s;};
const profile=()=>profiles[$('model').value];
const steps=()=>stepsFor(profile(),report?.extra_controls||[],report?.checklist_version??3,report?.keyboard_test??$('keyboard-test').value);
const current=()=>steps()[stepIndex];
const row=()=>report?.controls.find(r=>r.id===current()?.id);
const safe=fn=>async(...args)=>{try{await fn(...args);}catch(e){notify(e.message || String(e));}};
for(const p of availableProfiles(profiles)){const o=document.createElement('option');o.value=p.id;o.textContent=p.name;$('model').append(o);}
function blank(demo,device){return {format:FORMAT,version:2,checklist_version:3,keyboard_test:$('keyboard-test').value,profile_id:profile().id,demo,layout_audited:false,extra_controls:[],device,controls:[],leds:[],displays:{},display_checks:[],tool:{name:'Machinista Browser Survey',version:1}};}
async function persist(){if(!db||!report)return;const copy=structuredClone(report);saveQueue=saveQueue.catch(()=>{}).then(()=>new Promise((resolve,reject)=>{const tx=db.transaction('state','readwrite');tx.objectStore('state').put(copy,'survey');tx.oncomplete=resolve;tx.onerror=()=>reject(tx.error);}));try{await saveQueue;}catch{notify('Browser storage is unavailable. Download a JSON copy to keep your progress.');}}
function setInterface(id,fingerprint){if(!report.device.interfaces.some(i=>i.id===id)){if(report.device.interfaces.length>=8)throw new Error('At most eight inputs can be recorded.');report.device.interfaces.push({id,...(fingerprint?{fingerprint}:{})});}}
function receive(id,bytes){
 if(!report || bytes.length===0 || bytes.length>512)return;
 const h=hex(bytes), key=id+':'+(id.startsWith('midi')?bytes[0]&0xf0:bytes[0])+':'+bytes.length;
 latest.set(key,{interface:id,hex:h});
 if(autoStage==='leds'&&ledDetector)ledDetector.feed(id,bytes,performance.now());
 if(autoStage==='controls'&&autoDetector)autoDetector.feed(id,bytes,performance.now());
 if(!capture)return;
 const ms=Math.round(performance.now()-capture.started); if(ms>6000)return;
 const prev=capture.last.get(key);
 // Ignore unchanged continuous HID reports, but retain repeated MIDI attacks.
 if(id.startsWith('hid') && prev?.hex===h)return;
 if(bytes[0]===0x20 && id.startsWith('hid') && prev && ms-prev.ms<12)return;
 capture.last.set(key,{hex:h,ms});
 if(capture.frames.length>=3000){capture.overflow=true;return;}
 capture.frames.push({ms,interface:id,hex:h});
}
function draw(){
 $('completion').hidden=autoStage!=='complete';
 if(report)$('keyboard-test').value=report.checklist_version<3?'full':report.keyboard_test||'quick';
 $('keyboard-test').disabled=!!report;$('keyboard-choice').hidden=!profile().keys;
 const p=profile(), list=steps(), s=list[stepIndex];
 $('inventory').textContent=`${p.buttons.length} buttons · ${p.encoders.length} rotary controls (one step each) · ${p.pads} pads · ${p.keys} physical keys${p.keys?' · '+list.filter(s=>s.kind==='key').length+' keys to play':''}. Touch sensors, strips and pedal sockets have separate checks.`;
 $('manual').href=p.sources[0];$('step').replaceChildren();
 list.forEach((s,i)=>{const o=document.createElement('option');o.value=i;const r=report?.controls.find(r=>r.id===s.id);o.textContent=(r?.tester_confirmed?'✓ ':r?.status==='skipped'?'— ':'')+s.name+(s.optional?' (optional)':'');$('step').append(o);});$('step').value=stepIndex;
 $('kind').textContent=s.kind.toUpperCase();$('control').textContent=s.name;$('instruction').textContent=autoStage==='controls'?autoInstruction(s):s.instruction;$('count').textContent=`${stepIndex+1} / ${list.length}`;
 $('note').value=row()?.note||'';$('audit').checked=report?.layout_audited||false;
 $('connection').textContent=report?(report.demo?'DEMO · no hardware measurements':`${report.device.name} · ${devices.length} HID interface(s) open · ${selectedPorts.size} MIDI input(s) selected`):'Not connected';
 $('model').disabled=!!report;$('connect').disabled=!!report;$('demo').disabled=!!report;
 $('more').disabled=!report||report.demo||displayBusy||!!capture;$('record').disabled=!report||['displays','controls','leds'].includes(autoStage)||displayBusy||!!capture||(!report.demo&&!devices.length);$('confirm').disabled=!row()||row().status==='skipped'||!!capture||!row().frames.some(f=>f.ms>=1000&&f.ms<5000);
 for(const id of ['skip','step','add','audit','resume','download','submit','discord','midi'])$(id).disabled=displayBusy || !!capture || (!report && !['resume','midi'].includes(id));
 $('evidence').textContent=row()?`${row().status==='skipped'?'Untested':row().tester_confirmed?(row().detection?'Automatically recorded':'Action confirmed by tester'):'Recording awaiting your confirmation'} · ${row().frames.length} raw frames${row().note?' · '+row().note:''}`:'No recording for this control yet.';
 $('visual').replaceChildren();
 if(s.kind==='pad'&&p.pads===16){const grid=document.createElement('div');grid.className='padgrid';for(let r=3;r>=0;r--)for(let c=1;c<=4;c++){const n=r*4+c,t=document.createElement('span');t.className='tile'+(s.name==='PAD '+n?' active':'');t.textContent=n;grid.append(t);}$('visual').append(grid);}
 else if(s.kind==='key'){for(let n=1;n<=p.keys;n++){const t=document.createElement('span');t.className='tile keytile'+(s.name==='KEY '+n+' FROM LEFT'?' active':'');$('visual').append(t);}}
 else {const t=document.createElement('span');t.className='symbol';t.textContent=s.kind==='encoder'?(s.name.includes('counterclockwise')?'↶':'↷'):s.kind==='slider'?'↔':s.kind==='touch'?'◎':s.kind==='pressure'?'⇓':'▣';$('visual').append(t);}
 if(['displays','controls','leds'].includes(autoStage))for(const id of ['step','add','skip','confirm','more','resume','midi'])$(id).disabled=true;
 if(midi)for(const checkbox of $('ports').querySelectorAll('input'))checkbox.disabled=!!capture||['controls','displays'].includes(autoStage)||!report||report.demo;
 $('missing').replaceChildren();if(report){const c=coverage(report,profiles);$('coverage').textContent=`${report.demo?'DEMO · ':''}${c.recorded} / ${c.total} required actions recorded and confirmed. ${c.physical_check_complete?(p.keys&&report.checklist_version>=3&&report.keyboard_test==='quick'?'Quick input mapping finished; other keys were not individually tested.':'Physical input check finished.'):'Input check incomplete.'} Driver mappings still need review. Displays: ${c.displays.confirmed}/${c.displays.total} test images confirmed. LEDs: ${c.leds.confirmed}/${c.leds.total} confirmed${c.leds.available?'':' (output protocol not yet verified)' }.`;for(const n of [...c.missing,...c.displays.missing]){const li=document.createElement('li');li.textContent=n;$('missing').append(li);}}
 $('disconnect').disabled=displayBusy;drawDisplays();drawLeds();drawFlow();
}

function detectorOptions(){return {profileId:profile().id,hidConnected:devices.length>0,midiSelected:selectedPorts.size>0,jamInput:$('jam-input').value};}
function autoInstruction(s){
 if(profile().id==='maschine_jam'){
  if(s.kind==='slider')return s.name.endsWith('/ two fingers')
   ?'Place two fingers apart on the same strip, slide them up or down, then lift both. No pinch needed.'
   :'Touch this strip with one finger, slide along it, then lift.';
  if(s.kind==='encoder')return 'Turn clockwise a few clicks, then stop. Both directions use the same counter.';
  if(s.id==='button_encoder_push')return 'Press the encoder until it clicks, then fully release it.';
  if(s.kind==='pedal')return 'Press and release the connected footswitch once. Skip if none is connected.';
 }
 return s.kind==='encoder'?'Turn clockwise through a few steps, then stop.':s.kind==='button'||s.kind==='touch'?'Press or touch once, then release.':s.kind==='pad'||s.kind==='key'?'Play once, then release.':'Move only this control, then release or stop.';}
function drawFlow(){
 const jam=profile().id==='maschine_jam';
 $('jam-input-panel').hidden=!jam;
 $('jam-input').querySelector('[value=midi]').disabled=!selectedPorts.size;
 if(!selectedPorts.size&&$('jam-input').value==='midi')$('jam-input').value='auto';
 $('jam-input').disabled=!report||!!capture||autoStage==='leds';
 const running=['displays','controls','leds'].includes(autoStage);document.body.classList.toggle('mapping-running',running);
 $('mapping-start').disabled=ledBusy||!report||report.demo||!devices.length||displayBusy||!!capture||running;
 $('mapping-start').textContent=autoStage==='paused'?'Resume mapping':'Start mapping';
 $('mapping-pause').disabled=!running;$('mapping-retry').disabled=ledBusy||!report||!devices.length||displayBusy||!!capture;
 $('mapping-skip').disabled=!running||displayBusy||ledBusy;
 $('mapping-status').textContent=autoStage==='displays'?'DISPLAY CHECK · Compare each picture, then confirm.':autoStage==='controls'?'AUTOMATIC · '+(stepIndex+1)+' / '+steps().length+' · '+current().name+' · '+autoInstruction(current()):autoStage==='paused'?'PAUSED · '+($('phase').textContent||'Resume when ready.'):autoStage==='leds'?'LED CHECK · '+(ledIndex+1)+' / '+ledInventory(profile()).length+' · Identify the illuminated control.':autoStage==='complete'?'CHECK COMPLETE. Mapping finished. Review missing or skipped items before sending the JSON.':report?'Ready. Start mapping checks the displays first.':'Connect a controller to start.';
}
function pauseMapping(message){if(!['displays','controls','leds'].includes(autoStage))return;resumeStage=autoStage;autoStage='paused';autoDetector=null;ledDetector=null;autoGeneration++;if(autoTimer){clearInterval(autoTimer);autoTimer=null;}$('phase').textContent=message||'Mapping paused.';notify(message||'Mapping paused.');draw();$('mapping-flow').scrollIntoView({block:'start'});}
async function advanceDisplays(){
 if(autoStage!=='displays'||displayBusy)return;
 const pending=displayInventory(profile()).flatMap(d=>PATTERNS.map(pattern=>({d,pattern}))).find(({d,pattern})=>!skippedDisplays.has(d.id)&&!report.display_checks?.some(r=>r.display_id===d.id&&r.pattern===pattern&&['confirmed','not_tested'].includes(r.status)));
 if(!pending){await beginControls();return;}
 $('display-select').value=pending.d.id;$('display-pattern').value=pending.pattern;$('display-note').value='';drawDisplays();
 await $('display-send').onclick();
}
async function beginControls(){
 autoStage='controls';resumeStage='controls';$('wizard').scrollIntoView({block:'start'});stepIndex=Math.max(0,steps().findIndex(s=>!report.controls.some(r=>r.id===s.id&&r.tester_confirmed)));promptEnabled=true;
 if(steps().every(s=>report.controls.some(r=>r.id===s.id&&r.tester_confirmed))){finishMapping();return;}
 if(autoTimer)clearInterval(autoTimer);autoTimer=setInterval(autoTick,50);await armStep();
}
async function finishAll(){
 autoStage='complete';autoDetector=null;ledDetector=null;autoGeneration++;if(autoTimer)clearInterval(autoTimer);autoTimer=null;
 try{await clearLeds(profile(),devices);}catch{}await persist();draw();
 $('completion').hidden=false;const c=coverage(report,profiles);$('completion-summary').textContent=`${c.recorded}/${c.total} controls · ${c.displays.confirmed}/${c.displays.total} display checks · ${c.leds.confirmed}/${c.leds.total} LEDs confirmed. Skipped or unavailable items remain untested.`;
 $('completion').scrollIntoView({block:'start'});notify('CHECK COMPLETE. Download your JSON below.');
 await devicePrompt(['CHECK COMPLETE','DOWNLOAD JSON','IN THE BROWSER']);
}
function finishMapping(){beginLeds().catch(e=>{pauseMapping(e.message);});}
async function devicePrompt(lines){
 if(!promptEnabled)return;
 const panels=displayInventory(profile()).filter(d=>PATTERNS.every(pattern=>report.display_checks?.some(r=>r.display_id===d.id&&r.pattern===pattern&&r.status==='confirmed')));
 for(const panel of panels)try{await sendPrompt(profile(),panel,lines,devices,colorLink);}catch(e){promptEnabled=false;notify('On-device instructions unavailable: '+e.message+' Continue using the browser.');break;}
}

function drawLeds(){
 const test=ledInventory(profile())[ledIndex],active=autoStage==='leds';$('led-current').textContent=test?`${ledIndex+1} / ${ledInventory(profile()).length} · ${test.name} · ${test.color.toUpperCase()}`:'No verified LED output protocol for this model.';
 $('led-status').textContent=ledBusy?'Lighting the next LED…':ledError||(!active?'LED check follows the inputs.':ledSent?test?.kind==='unknown'?'Check which light is on, then confirm below.':'Press the illuminated button or pad, then release. You can also identify it below and click Confirm & next.':'No LED output confirmed. Retry or mark untested.');
 for(const id of ['led-observed','led-color','led-note','led-next','led-dark','led-skip-all'])$(id).disabled=!active||ledBusy;
 $('led-next').disabled=!active||ledBusy||!ledSent;
 $('led-resume').hidden=profile().id!=='maschine_jam';
 $('led-resume').disabled=!report||report.demo||!devices.length||!!capture||displayBusy||ledBusy||active||['controls','displays'].includes(autoStage);
}
async function beginLeds(){
 if(autoTimer)clearInterval(autoTimer);autoDetector=null;ledDetector=null;
 if(!ledInventory(profile()).length){await finishAll();return;}
 autoStage='leds';resumeStage='leds';ledIndex=ledInventory(profile()).findIndex(t=>!report.leds.some(r=>r.id===t.id&&['confirmed','not_tested'].includes(r.status)));if(ledIndex<0){await finishAll();return;}
 $('led-panel').scrollIntoView({block:'start'});autoTimer=setInterval(autoTick,50);await armLed();
}
async function armLed(){
 const t=ledInventory(profile())[ledIndex];if(!t){await finishAll();return;}const generation=++autoGeneration;ledBusy=true;ledSent=false;ledDetector=null;ledError='';$('led-observed').value='';$('led-note').value='';$('led-color').value=t.color==='observe'?'unknown':t.color;draw();
 try{await showLed(profile(),devices,t);if(autoStage!=='leds'||generation!==autoGeneration)return;ledSent=true;if(profile().id==='maschine_jam'&&!t.name.startsWith('OUTPUT '))$('led-observed').value=t.name;await devicePrompt(['LED '+(ledIndex+1)+' / '+ledInventory(profile()).length,t.color==='observe'?'WHICH LED IS ON':t.name+' '+t.color,'PRESS LIT CONTROL']);
 if(t.kind!=='unknown')ledDetector=createActionDetector({kind:t.kind},[...latest.values()],performance.now(),detectorOptions());
 }catch(e){ledError=e.message;}finally{ledBusy=false;draw();}
}
async function saveLed(status,observed){
 if(autoStage!=='leds'||ledBusy)return;const t=ledInventory(profile())[ledIndex];if(status==='confirmed'&&(!ledSent||!observed.trim()))throw new Error('Name the illuminated control before confirming.');
 report.leds=report.leds.filter(r=>r.id!==t.id);report.leds.push({id:t.id,bank:t.bank,offset:t.offset,value:t.value,status,observed,color:$('led-color').value,note:$('led-note').value,sent:ledSent});ledDetector=null;await persist();ledIndex=ledInventory(profile()).findIndex((next,index)=>index>ledIndex&&!report.leds.some(r=>r.id===next.id&&['confirmed','not_tested'].includes(r.status)));if(ledIndex<0)await finishAll();else await armLed();
}
$('led-resume').onclick=safe(beginLeds);
$('led-next').onclick=safe(()=>saveLed('confirmed',$('led-observed').value.trim()));
$('led-dark').onclick=safe(()=>saveLed(ledSent?'failed':'blocked',$('led-observed').value.trim()));
$('led-skip-all').onclick=safe(async()=>{if(!confirm('Skip the remaining LED tests? They will remain untested in the JSON.'))return;for(const t of ledInventory(profile()).slice(ledIndex))if(!report.leds.some(r=>r.id===t.id))report.leds.push({id:t.id,status:'not_tested',observed:'',color:'',note:'Skipped by tester.',sent:false});await finishAll();});
$('completion-download').onclick=()=>download();

async function armStep(){
 if(autoStage!=='controls')return;autoDetector=null;const generation=++autoGeneration,s=current();if(['key','pressure'].includes(s.kind)&&profile().keys&&!selectedPorts.size){pauseMapping('Select this keyboard in MIDI inputs, then resume mapping.');return;}draw();$('phase').textContent='Preparing next control…';
 $('instruction').textContent=autoInstruction(s);
 autoDetector=createActionDetector(s,[...latest.values()],performance.now(),detectorOptions());$('phase').textContent='Ready · '+autoInstruction(s);drawFlow();
 await devicePrompt([String(stepIndex+1)+' / '+steps().length,s.name,s.kind==='encoder'?'TURN RIGHT':s.kind==='pad'||s.kind==='key'?'PLAY - RELEASE':'PRESS - RELEASE']);
 if(autoStage!=='controls'||generation!==autoGeneration)return;

}
function autoTick(){
 if(autoStage==='leds'){
  if(!ledDetector||ledBusy)return;const result=ledDetector.tick(performance.now());if(result.state==='ambiguous'){ledError=result.message;ledDetector=null;drawLeds();return;}
  if(result.state==='complete'){ledDetector=null;const mapped=report.controls.find(r=>r.detection?.signature===result.signature);if(!mapped){ledError='Input received. Identify the lit control below, then confirm.';drawLeds();return;}$('led-observed').value=mapped.name;saveLed('confirmed',mapped.name).catch(e=>notify(e.message));}return;
 }
 if(autoStage!=='controls'||!autoDetector)return;
 const result=autoDetector.tick(performance.now());
 if(autoDetector.inputStatus)$('jam-input-status').textContent=autoDetector.inputStatus();
 if(result.state==='ambiguous'){pauseMapping(result.message);return;}
 if(result.state==='complete'){
  const s=current(),duplicate=report.controls.find(r=>r.id!==s.id&&r.kind===s.kind&&r.detection?.signature===result.signature);
  if(duplicate){pauseMapping('This signal was already recorded for '+duplicate.name+'. Retry the named control or use manual recording.');return;}
  const r={id:s.id,name:s.name,kind:s.kind,status:'captured',tester_confirmed:true,frames:compactFrames(result.frames),note:$('note').value,detection:{method:'automatic',signature:result.signature}};
  if(!r.frames.some(f=>f.ms>=1000&&f.ms<5000)){pauseMapping('Not enough clear evidence. Release everything and repeat this control.');return;}
  report.controls=report.controls.filter(r=>r.id!==s.id);report.controls.push(r);report.layout_audited=false;autoDetector=null;persist();
  if(stepIndex===steps().length-1){finishMapping();return;}stepIndex++;armStep();return;
 }
 $('phase').textContent=result.state==='settling'?'Keep all controls released…':result.state==='release'?'Signal received · release the control / stop turning…':result.message||autoInstruction(current());
}
$('mapping-start').onclick=safe(async()=>{
 if(!report||report.demo||!devices.length||displayBusy||capture)return;
 const testedColor=displayInventory(profile()).find(d=>d.protocol==='ni-color'&&PATTERNS.every(pattern=>report.display_checks?.some(r=>r.display_id===d.id&&r.pattern===pattern&&r.status==='confirmed')));if(testedColor&&!colorLink){try{colorLink=await openColor(profile(),testedColor,navigator.usb);}catch(e){notify('Display instructions unavailable; continue in the browser. '+e.message);}}
 if(autoStage==='paused'&&resumeStage==='leds'){autoStage='leds';if(autoTimer)clearInterval(autoTimer);autoTimer=setInterval(autoTick,50);await armLed();return;}
 if(autoStage==='paused'&&resumeStage==='controls'){autoStage='controls';if(autoTimer)clearInterval(autoTimer);autoTimer=setInterval(autoTick,50);await armStep();return;}
 if(profile().keys&&!selectedPorts.size){if(!midi)await $('midi').onclick();if(!selectedPorts.size){autoStage='displays';pauseMapping('Choose this keyboard in MIDI inputs, then resume mapping.');return;}}
 $('display-enable').checked=true;autoStage='displays';resumeStage='displays';draw();$('display-panel').scrollIntoView({block:'start'});await advanceDisplays();
});
$('jam-input').onchange=safe(async()=>{
 if(autoStage==='controls')await armStep();
 else if(autoStage==='paused'&&resumeStage==='controls')await $('mapping-retry').onclick();
});
$('mapping-pause').onclick=()=>pauseMapping('Paused by tester.');
$('mapping-retry').onclick=safe(async()=>{if(!report||displayBusy||ledBusy)return;if(autoStage==='leds'||autoStage==='paused'&&resumeStage==='leds'){autoStage='leds';await armLed();return;}if(autoStage==='displays'||autoStage==='paused'&&resumeStage==='displays'){autoStage='displays';await $('display-send').onclick();return;}autoStage='controls';if(autoTimer)clearInterval(autoTimer);autoTimer=setInterval(autoTick,50);await armStep();});
$('mapping-skip').onclick=safe(async()=>{
 if(!report||displayBusy||ledBusy)return;
 if(autoStage==='leds'){await saveLed('not_tested','');return;}
 if(autoStage==='displays'){
  const id=$('display-select').value;skippedDisplays.add(id);for(const pattern of PATTERNS)if(!report.display_checks?.some(r=>r.display_id===id&&r.pattern===pattern))storeDisplay({display_id:id,pattern,status:'not_tested',note:'Skipped by tester during guided mapping.'});await advanceDisplays();return;
 }
 if(autoStage==='controls'){const s=current();report.controls=report.controls.filter(r=>r.id!==s.id);report.controls.push({id:s.id,name:s.name,kind:s.kind,status:'skipped',tester_confirmed:false,frames:[],note:'Skipped by tester during guided mapping.'});persist();autoDetector=null;if(stepIndex===steps().length-1)finishMapping();else{stepIndex++;await armStep();}}
});

function displayRow(){return report?.display_checks?.find(r=>r.display_id===$('display-select').value&&r.pattern===$('display-pattern').value);}
function drawDisplays(){
 const inventory=displayInventory(profile()),selected=$('display-select').value;
 $('display-select').replaceChildren();for(const d of inventory){const o=document.createElement('option');o.value=d.id;o.textContent=d.name;$('display-select').append(o);}if(inventory.some(d=>d.id===selected))$('display-select').value=selected;
 const display=inventory.find(d=>d.id===$('display-select').value),r=displayRow();
 $('display-info').textContent=display?`${inventory.length} physical display(s). Test each with three images. ${display.reason||'Compare the preview with the hardware, then confirm only if it matches.'}`:'This controller has no bitmap display. Its LEDs/meters need a separate LED check.';
 $('display-preview').hidden=!display;
 if(display){$('display-expected').textContent=$('display-pattern').value==='border'?'Check all four one-pixel edges, upright text and the correct display number.':$('display-pattern').value==='grid'?'Check a regular, aligned black-and-white grid across the whole screen. No missing rows or shifted columns.':display.color?'Check the display number and bars in this order: red, green, blue, white, orange, gray.':'Check the display number and four areas: black, sparse dots, dense dots, white. This is a 1-bit display; gray uses dots.';const canvas=$('display-preview');canvas.width=display.width;canvas.height=display.height;const rgb=testImage(display,$('display-pattern').value),rgba=new Uint8ClampedArray(display.width*display.height*4);for(let i=0;i<rgb.length/3;i++){rgba[i*4]=rgb[i*3];rgba[i*4+1]=rgb[i*3+1];rgba[i*4+2]=rgb[i*3+2];rgba[i*4+3]=255;}canvas.getContext('2d').putImageData(new ImageData(rgba,display.width,display.height),0,0);}
 const locked=!report||!!capture||displayBusy||autoStage==='controls'||!display;
 for(const id of ['display-select','display-pattern','display-enable','display-skip','display-note'])$(id).disabled=locked;
 if(autoStage==='displays')for(const id of ['display-select','display-pattern','display-enable'])$(id).disabled=true;
 $('display-send').disabled=locked||!$('display-enable').checked||report?.demo;
 $('display-good').disabled=locked||r?.status!=='sent';$('display-bad').disabled=locked||r?.status!=='sent';
 $('display-result').textContent=displayBusy?'Sending the test image…':report?.demo?'Demo: preview only; no display output or confirmation.':r?`${r.status.toUpperCase()}${r.note?' · '+r.note:''}`:'Not tested';
 if(report){const c=displayCoverage(report,profile());$('display-summary').textContent=`${c.confirmed}/${c.total} display tests confirmed. ${c.complete?'Display check complete.':'Display check incomplete.'}`;}else $('display-summary').textContent='Connect a controller before sending a test image.';
}
function storeDisplay(result){report.display_checks ||= [];report.display_checks=report.display_checks.filter(r=>r.display_id!==result.display_id||r.pattern!==result.pattern);report.display_checks.push(result);persist();}
$('display-select').onchange=()=>{$('display-note').value=displayRow()?.note||'';drawDisplays();};$('display-pattern').onchange=()=>{$('display-note').value=displayRow()?.note||'';drawDisplays();};$('display-enable').onchange=drawDisplays;
$('display-note').onchange=()=>{const r=displayRow();if(r){r.note=$('display-note').value;persist();}};
$('display-send').onclick=safe(async()=>{
 if(!report||report.demo||capture||displayBusy||!$('display-enable').checked)return;
 const target=report,display=displayInventory(profile()).find(d=>d.id===$('display-select').value),pattern=$('display-pattern').value,observation=$('display-note').value;
 if(!display)return;displayBusy=true;draw();
 try{
  if(display.protocol==='pending-odr')throw new Error(display.reason);
  try{await enableBacklight(profile(),devices);}catch(e){notify('Backlight unavailable: '+e.message);}
  const result=display.protocol==='ni-color'?(autoStage==='displays'?(colorLink ||= await openColor(profile(),display,navigator.usb),await colorLink.send(display,pattern)):await sendColor(profile(),display,pattern,navigator.usb)):await sendMono(profile(),display,pattern,devices);
  const evidence=await transmissionEvidence(result);if(report!==target)throw new Error('Controller session changed. Repeat the test.');
  storeDisplay({display_id:display.id,pattern,status:'sent',note:observation,...evidence});notify('Test image sent. Compare the physical display with the preview before confirming.');
 }catch(e){if(report===target)storeDisplay({display_id:display.id,pattern,status:'blocked',note:String(e.message).slice(0,300)});notify('Display test not confirmed: '+e.message);}
 finally{displayBusy=false;draw();}
});
function finishDisplay(okay){const r=displayRow();if(!r||r.status!=='sent'||displayBusy)return;r.status=okay?'confirmed':'failed';r.note=$('display-note').value;persist();if(okay){const inventory=displayInventory(profile()),pattern=PATTERNS.indexOf(r.pattern);if(pattern<2)$('display-pattern').value=PATTERNS[pattern+1];else{const index=inventory.findIndex(d=>d.id===r.display_id);if(index<inventory.length-1){$('display-select').value=inventory[index+1].id;$('display-pattern').value=PATTERNS[0];}}$('display-note').value=displayRow()?.note||'';}draw();if(autoStage==='displays'&&okay)advanceDisplays();}
$('display-good').onclick=()=>finishDisplay(true);$('display-bad').onclick=()=>finishDisplay(false);
$('display-skip').onclick=()=>{if(autoStage==='displays'){ $('mapping-skip').onclick();return;}if(!report||displayBusy)return;storeDisplay({display_id:$('display-select').value,pattern:$('display-pattern').value,status:'not_tested',note:$('display-note').value});draw();};

async function detach(){pauseMapping('Controller disconnected. Resume after reconnecting the same controller.');await restoreBacklight();try{if(report)await clearLeds(profile(),devices);}catch{}if(colorLink){await colorLink.close();colorLink=null;}$('display-enable').checked=false;if(capture){clearInterval(capture.timer);capture=null;notify('Recording cancelled by disconnect. Repeat this control.');}for(const d of devices){d.device.removeEventListener('inputreport',d.listener);try{await d.device.close();}catch{}}devices=[];if(midi)for(const p of midi.inputs.values())p.onmidimessage=null;selectedPorts.clear();latest.clear();draw();}
async function openHid(additional=false){
 if(!navigator.hid)throw new Error('WebHID is unavailable. Open this page in desktop Chrome or Edge.');
 const filters=[{vendorId:0x17cc,...(additional?{productId:report.device.product_id}:{})}];
 const found=await navigator.hid.requestDevice({filters});if(!found.length)return;
 const first=found[0], p=profile();
 if(p.product_ids.length&&!p.product_ids.includes(first.productId))throw new Error('The USB device does not match the chosen model. Choose the correct model first.');
 if(additional&&first.productId!==report.device.product_id)throw new Error('Choose an interface of the same controller.');
 const old=report;
 try{
  if(!report){autoStage='idle';skippedDisplays.clear();}if(!report)report=blank(false,{vendor_id:0x17cc,product_id:first.productId,name:p.name,identity_verified:p.product_ids.includes(first.productId),interfaces:[]});
  for(const device of found){if(devices.some(d=>d.device===device))continue;if(device.productId!==report.device.product_id)continue;if(devices.length>=4)throw new Error('At most four HID interfaces are supported.');const fingerprint=(device.collections||[]).map(c=>[c.usagePage,c.usage,...(c.inputReports||[]).map(r=>r.reportId)].join(':')).join(';').slice(0,512);
   const saved=report.device.interfaces.filter(i=>i.id.startsWith('hid')&&i.fingerprint===fingerprint&&!devices.some(d=>d.id===i.id));
   if(saved.length>1)throw new Error('These saved HID interfaces cannot be distinguished safely. Start a fresh session for this controller.');
   const id=saved[0]?.id || 'hid'+Array.from({length:4},(_,i)=>i).find(i=>!report.device.interfaces.some(r=>r.id==='hid'+i));
   if(id==='hidundefined')throw new Error('No free HID interface slot.');
   await device.open();
   const listener=e=>receive(id,new Uint8Array([e.reportId,...new Uint8Array(e.data.buffer,e.data.byteOffset,e.data.byteLength)]));
   device.addEventListener('inputreport',listener);devices.push({device,id,listener});setInterface(id,fingerprint);
  }
 }catch(e){await detach();report=old;throw e;}
 notify('USB connected. If some buttons send no data, try Add HID interface. MIDI keybeds may also need Find MIDI inputs.');await persist();draw();
}
$('connect').onclick=safe(()=>openHid());$('more').onclick=safe(()=>openHid(true));
$('disconnect').onclick=safe(async()=>{await persist();await detach();if((report?.controls.length||report?.display_checks?.length) && !confirm('End this session? Download a copy first if you need it. A browser recovery copy remains until the next session is saved.'))return;report=null;stepIndex=0;autoStage='idle';skippedDisplays.clear();draw();});
if(navigator.hid)navigator.hid.addEventListener('disconnect',safe(async e=>{if(devices.some(d=>d.device===e.device)){await detach();notify('USB disconnected. Download your progress, then resume and reconnect the same controller.');}}));
$('model').onchange=()=>{stepIndex=0;ledIndex=0;$('completion').hidden=true;draw();};$('keyboard-test').onchange=()=>{stepIndex=0;draw();};$('step').onchange=()=>{pauseMapping('Manual control selection.');stepIndex=Number($('step').value);draw();};
$('demo').onclick=()=>{report=blank(true,{vendor_id:0x17cc,product_id:profile().product_ids[0]||0,name:profile().name,identity_verified:false,interfaces:[{id:'hid0'}]});draw();notify('Demo mode. These measurements cannot be submitted as real hardware data.');};
$('record').onclick=()=>{
 const s=current();if(!report||capture||['displays','controls','leds'].includes(autoStage))return;
 capture={step:s,started:performance.now(),frames:[...latest.values()].map(f=>({...f,ms:0})),last:new Map(),overflow:false};$('progress').value=0;draw();
 capture.timer=setInterval(()=>{
  if(!capture)return;const elapsed=(performance.now()-capture.started)/1000;$('progress').value=elapsed;
  $('phase').textContent=elapsed<1?'Keep all controls still…':elapsed<5?'NOW · '+s.instruction:'Release · keep still…';
  if(report.demo && elapsed>1 && elapsed<5 && capture.frames.length<20){const n=capture.frames.length;capture.frames.push({ms:Math.round(elapsed*1000),interface:'hid0',hex:'0100'+(n%2?'04':'00')});}
  if(elapsed>=6){const c=capture;clearInterval(c.timer);capture=null;const r={id:s.id,name:s.name,kind:s.kind,status:'captured',tester_confirmed:false,frames:compactFrames(c.frames),note:c.overflow?'Capture exceeded rate limit; repeat more slowly.':''};report.controls=report.controls.filter(r=>r.id!==s.id);report.controls.push(r);report.layout_audited=false;$('phase').textContent=c.overflow?'Too much data · repeat this control':r.frames.length?'Recorded · confirm only if you performed the requested action':'No input data · check interfaces, MIDI ports or app ownership';persist();draw();}
 },80);
};
$('confirm').onclick=safe(async()=>{if(!row()||!row().frames.some(f=>f.ms>=1000&&f.ms<5000))return;row().tester_confirmed=true;row().note=$('note').value;if(stepIndex===steps().length-1){await persist();finishMapping();return;}stepIndex++;$('phase').textContent='Ready when you are';draw();await persist();});
$('skip').onclick=safe(async()=>{const s=current();report.controls=report.controls.filter(r=>r.id!==s.id);report.controls.push({id:s.id,name:s.name,kind:s.kind,status:'skipped',tester_confirmed:false,frames:[],note:$('note').value});report.layout_audited=false;if(stepIndex===steps().length-1){await persist();finishMapping();return;}stepIndex++;draw();await persist();});
$('note').onchange=()=>{if(row()){row().note=$('note').value;persist();}};
$('audit').onchange=()=>{if(report){report.layout_audited=$('audit').checked;persist();draw();}};
$('add').onclick=safe(async()=>{const extra={name:$('extra-name').value.trim(),kind:$('extra-kind').value};const next=[...report.extra_controls,extra];stepsFor(profile(),next,report.checklist_version,report.keyboard_test);report.extra_controls=next;report.layout_audited=false;stepIndex=steps().length-1;$('extra-name').value='';await persist();draw();});
$('midi').onclick=safe(async()=>{
 if(!navigator.requestMIDIAccess)throw new Error('Web MIDI is unavailable in this browser.');
 midi=await navigator.requestMIDIAccess({sysex:false});const suggested=matchedMidiPorts([...midi.inputs.values()],profile());if(report&&!report.demo&&suggested.length===1){const port=suggested[0],id='midi'+[...midi.inputs.values()].indexOf(port);setInterface(id);selectedPorts.add(port.id);port.onmidimessage=e=>{const b=new Uint8Array(e.data);if(b[0]<0xf0)receive(id,b);};}renderPorts();midi.onstatechange=()=>{for(const id of [...selectedPorts])if(!midi.inputs.has(id)){selectedPorts.delete(id);notify('A MIDI input disconnected. Repeat any interrupted capture.');}renderPorts();};
});
function renderPorts(){
 $('ports').replaceChildren();const ports=[...midi.inputs.values()], matches=matchedMidiPorts(ports,profile());
 if(!ports.length){$('ports').textContent='No USB-MIDI inputs exposed by the operating system.';return;}
 ports.forEach(port=>{const l=document.createElement('label'),c=document.createElement('input');c.type='checkbox';c.checked=selectedPorts.has(port.id);c.disabled=!report||report.demo||!!capture;l.className='check';l.append(c,document.createTextNode(port.name+(matches.includes(port)?' · suggested':'')));c.onchange=safe(async()=>{if(c.checked){if(selectedPorts.size>=4)throw new Error('Select at most four MIDI inputs.');const id='midi'+[...midi.inputs.values()].indexOf(port);setInterface(id);selectedPorts.add(port.id);port.onmidimessage=e=>{const b=new Uint8Array(e.data);if(b[0]<0xf0)receive(id,b);};}else{selectedPorts.delete(port.id);port.onmidimessage=null;}await persist();draw();renderPorts();});$('ports').append(l);});
}
function download(){if(!report)throw new Error('Record a controller first.');const clean=validateReport(report,profiles),blob=new Blob([JSON.stringify(clean,null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='machinista-'+report.profile_id+'-'+(report.demo?'demo-':'')+Date.now()+'.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),2000);return clean;}
$('download').onclick=safe(download);
$('submit').onclick=safe(async()=>{
 if(!report||report.demo)throw new Error('Demo reports cannot be submitted.');
 if(!$('consent').checked)throw new Error('Please agree to publication before preparing your email.');
 const draft=emailDraft(config.submissionEmail,profile().name,coverage(report,profiles));
 download();window.location.href=draft;
 notify('JSON downloaded. In your mail app, attach that downloaded file, then send the email. The browser cannot attach it automatically. If no mail app opens, use the address below with your webmail.');
});
$('discord').onclick=safe(()=>{
 if(!report||report.demo)throw new Error('Demo reports cannot be submitted.');
 if(!$('consent').checked)throw new Error('Please agree to publication before sharing your measurements.');
 if(!/^https:\/\/(discord\.gg\/[A-Za-z0-9-]+|discord\.com\/(channels\/\d+\/\d+|invite\/[A-Za-z0-9-]+))\/?$/.test(config.discordUrl||''))throw new Error('The Discord channel is not configured.');
 download();window.open(config.discordUrl,'_blank','noopener');notify('JSON downloaded. Join or open the Machinista server, choose #controllers, attach the downloaded .json file there, and send it. Discord sign-in may be required.');
});
$('discord').hidden=!config.discordUrl;
if(config.discordUrl)$('submit-info').append(document.createTextNode(' Discord submissions belong in #controllers. The invite may open another channel first; choose #controllers before attaching your file.'));
$('resume').onchange=safe(async()=>{const f=$('resume').files[0];if(!f)return;if(f.size>MAX_BYTES)throw new Error('The file exceeds 8 MiB.');const saved=upgradeChecklist(JSON.parse(await f.text()),profiles);if(!availableProfiles(profiles).some(p=>p.id===saved.profile_id))throw new Error('This controller is already supported and no longer needs a survey. Your saved JSON remains valid for maintainer review.');if(!confirm('Resume this survey? Only reconnect the SAME physical controller and keep its settings unchanged.'))return;await detach();report=saved;autoStage='idle';skippedDisplays.clear();$('model').value=report.profile_id;stepIndex=0;draw();notify('Progress restored. Click Add HID interface to reconnect the same controller. Re-select MIDI inputs.');});
try{db=await new Promise((resolve,reject)=>{const req=indexedDB.open('machinista-controller-lab',1);req.onupgradeneeded=()=>req.result.createObjectStore('state');req.onsuccess=()=>resolve(req.result);req.onerror=()=>reject(req.error);});const saved=await new Promise(resolve=>{const req=db.transaction('state').objectStore('state').get('survey');req.onsuccess=()=>resolve(req.result);req.onerror=()=>resolve(null);});if(saved && (!profiles[saved.profile_id]||!availableProfiles(profiles).some(p=>p.id===saved.profile_id))){notify('Your previous survey belongs to an already supported controller. Choose one of the remaining models. Your saved JSON can still be reviewed.');}else if(saved && confirm('Restore your previous controller survey?')){report=upgradeChecklist(saved,profiles);$('model').value=report.profile_id;notify('Recovered progress. Reconnect the same controller with Add HID interface.');}}catch{notify('Browser recovery storage is unavailable. Download JSON regularly to save progress.');}
document.addEventListener('visibilitychange',()=>{if(document.hidden&&['controls','displays','leds'].includes(autoStage))pauseMapping('Mapping paused because the page was hidden.');if(document.hidden&&capture){clearInterval(capture.timer);capture=null;notify('Recording cancelled because the page was hidden. Keep this page visible and repeat.');draw();}});
$('submit-info').append(document.createTextNode(config.submissionEmail?' Send your downloaded JSON to '+config.submissionEmail+'. Prepare email opens your mail app; attach the file yourself. Webmail also works.':' The public email address has not been configured yet. You can already download your JSON.'));
window.addEventListener('beforeunload',e=>{if(capture){e.preventDefault();e.returnValue='';}});draw();
