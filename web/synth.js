'use strict';
const SYNTH_URI='urn:machinista:instrument:synth';
let synthVisible=false,synthSchema=null,synthContext=null,synthSlot=0,synthValues={},synthWaves={},synthCategory='Oscillators',synthModule=1;
let synthPending={},synthTimer=null,synthSending=null,synthLoading=false,synthEditing=false,synthLastEdit=0,synthSentAt=0,synthGesture='',synthMessageTimer=null,synthWidgets=new Map();
const synthUserPreviews=new Map();
const synthCategories=['Oscillators','Filters','Envelopes','LFOs','Matrix','Voicing'];
const synthPost=value=>api('/api/sounds/command',{method:'POST',headers:{'X-Machinista-Token':token,'Content-Type':'application/json'},body:JSON.stringify({operation:'synth_edit',...soundCoordinates(synthContext),slot:synthSlot,uri:SYNTH_URI,...value})});
function synthMessage(text,error=false){clearTimeout(synthMessageTimer);$('synth-message').textContent=text;$('synth-message').className=error?'error':'';if(!error)synthMessageTimer=setTimeout(()=>$('synth-message').textContent='',5000)}
function synthIdentity(c,slot){return JSON.stringify([c?.generation,c?.group,c?.pad,slot,c?.plugins?.[slot]?.uri])}
function synthPort(symbol){return synthSchema.parameters.find(p=>p.symbol===symbol)}
function synthChoices(p){return p.choice_group?synthSchema.choices[p.choice_group]:p.choices}
function synthValue(p,v){
 const choices=synthChoices(p);if(choices)return choices.find(c=>c[0]===Math.round(v))?.[1]||String(v);
 if(p.toggle)return v?'ON':'OFF';
 if(['percent','signed_percent'].includes(p.unit))return Math.round(v*100)+'%';
 if(p.unit==='cents')return (Math.round(v*10)/10)+' ct';
 if(p.unit==='hz')return v>=1000?(v/1000).toFixed(2)+' kHz':(v<10?v.toFixed(2):Math.round(v))+' Hz';
 if(p.unit==='ms')return v>=1000?(v/1000).toFixed(2)+' s':Math.round(v)+' ms';
 return (p.integer?Math.round(v):Math.round(v*100)/100)+(p.unit==='octaves'?' oct':p.unit==='semitones'?' st':'');
}
function synthRatio(p,v){return p.log&&p.min>0?Math.log(Math.max(p.min,v)/p.min)/Math.log(p.max/p.min):(v-p.min)/(p.max-p.min)}
function synthNumber(p,n){let v=p.log&&p.min>0?p.min*(p.max/p.min)**n:p.min+n*(p.max-p.min);return p.integer?Math.round(v):p.unit==='cents'?Math.round(v*10)/10:Number(v.toPrecision(9))}
function synthBegin(){synthGesture=Date.now().toString(36)+'-'+Math.random().toString(36).slice(2,9);synthEditing=true}
function synthEnd(){synthEditing=false;synthFlush()}
function synthQueue(symbol,value){synthValues[symbol]=value;synthPending[symbol]=value;synthLastEdit=Date.now();synthSync();if(synthTimer===null&&!synthSending)synthTimer=setTimeout(synthFlush,Math.max(0,50-(Date.now()-synthSentAt)))}
async function synthFlush(){
 clearTimeout(synthTimer);synthTimer=null;
 if(synthSending)return synthSending;
 if(!Object.keys(synthPending).length||!synthContext)return;
 // Throttle, not debounce: sustained knob movement must reach audio before
 // pointer-up. One in-flight write and latest values bound network/backlog.
 synthSending=(async()=>{
  while(Object.keys(synthPending).length&&synthContext){
   const wait=Math.max(0,50-(Date.now()-synthSentAt));if(wait)await new Promise(resolve=>setTimeout(resolve,wait));
   const controls=synthPending;synthPending={};const identity=synthIdentity(synthContext,synthSlot);synthSentAt=Date.now();
   try{const result=await synthPost({controls,gesture:synthGesture});if(synthIdentity(synthContext,synthSlot)!==identity)return;Object.assign(synthContext,result);synthLastEdit=Date.now();synthMessage('Changes applied. Save Sound to add this patch to your library.')}
   catch(e){synthPending={};synthMessage(e.message+' Refresh before editing again.',true);synthContext=null;$('synth-editor').hidden=true;$('synth-empty').hidden=false}
  }
 })();
 await synthSending;synthSending=null;if(Object.keys(synthPending).length)return synthFlush();
}

async function synthCommand(extra){
 await synthFlush();if(!synthContext)return;
 synthEditing=true;$('synth-editor').inert=true;
 try{const result=await synthPost(extra);Object.assign(synthContext,result);synthLastEdit=0;await synthLoad(true)}catch(e){synthMessage(e.message,true)}finally{synthEditing=false;$('synth-editor').inert=false}
}
async function synthLoad(force=false){
 if(synthLoading||(!force&&(synthSending||synthEditing||Object.keys(synthPending).length||Date.now()-synthLastEdit<800)))return;
 synthLoading=true;const started=synthLastEdit;
 try{
  const [c,schema]=await Promise.all([api('/api/sounds/runtime'),synthSchema&&!force?Promise.resolve(synthSchema):api('/api/synth')]);synthSchema=schema;for(const port of schema.parameters)if(port.choice_group)port.choices=schema.choices[port.choice_group];
  if(synthLastEdit!==started||(!force&&(synthSending||synthEditing||Object.keys(synthPending).length)))return;
  const slots=(c.plugins||[]).map((p,i)=>p.uri===SYNTH_URI?i:-1).filter(i=>i>=0);
  if(!slots.includes(synthSlot))synthSlot=slots[0]??0;
  const changed=synthIdentity(c,synthSlot)!==synthIdentity(synthContext,synthSlot);
  $('synth-context').textContent=c.available?'Selected: Group '+String.fromCharCode(65+c.group)+' / Pad '+(c.pad+1)+' · '+c.name+(c.playing?' · PLAYING':''):'Controller engine unavailable.';
  const plugin=c.plugins?.[synthSlot];const available=c.available&&plugin?.uri===SYNTH_URI;
  $('synth-empty').hidden=available;$('synth-editor').hidden=!available;
  synthContext=c;if(!available)return;$('synth-save').disabled=Boolean(c.playing||c.recording||c.busy);
  synthValues=Object.fromEntries(schema.parameters.map(p=>[p.symbol,plugin.controls?.[p.symbol]??p.default]));synthWaves=plugin.synth_waves||{};for(const wave of Object.values(synthWaves))synthFetchWave(wave.id);
  const slot=$('synth-slot');slot.replaceChildren(...slots.map(i=>new Option('Slot '+(i+1),i)));slot.value=String(synthSlot);
  if(changed||force||!synthWidgets.size){synthPresetLists(plugin.profile_preset);synthRender()}else synthSync();
 }catch(e){synthMessage(e.message,true)}finally{synthLoading=false}
}
function synthPresetLists(stored={}){
 $('synth-bank').replaceChildren(...synthSchema.banks.map(b=>new Option(b.name,b.id)));$('synth-bank').value=synthSchema.banks.some(b=>b.id===stored.bank)?stored.bank:'init';synthPatchList();const bank=synthSchema.banks.find(b=>b.id===$('synth-bank').value),named=stored.name?bank?.patches.indexOf(stored.name):-1;$('synth-patch').value=String(named>=0?named:(stored.program||0));
}
function synthPatchList(){const bank=synthSchema.banks.find(b=>b.id===$('synth-bank').value);$('synth-patch').replaceChildren(...(bank?.patches||[]).map((p,i)=>new Option(p,i)))}
function synthCard(port){
 const box=element('label',undefined,'synth-control');box.dataset.symbol=port.symbol;
 const title=element('span',port.name,'synth-label'),value=element('output',undefined,'synth-value');box.append(title);const choices=synthChoices(port);let input,knob,exact;
 if(/^osc[1-4]_wave$/.test(port.symbol)){
  input=element('select');input.setAttribute('aria-label',port.name+' '+port.symbol);
  for(let i=0;i<32;i++)input.append(new Option(synthSchema.waves[i],'f:'+i));
  for(const r of synthSchema.users)input.append(new Option((r.folder?r.folder+'/':'')+r.name,'u:'+r.id));
  const stored=synthWaves[port.symbol[3]];if(stored&&!synthSchema.users.some(r=>r.id===stored.id))input.append(new Option('Saved: '+stored.name,'u:'+stored.id));
  input.onchange=()=>{synthGesture='';if(input.value.startsWith('f:'))synthQueue(port.symbol,Number(input.value.slice(2)));else synthCommand({wave:{osc:Number(port.symbol[3]),id:input.value.slice(2)}})};
 }else if(choices||port.toggle){
  input=element('select');for(const [v,label] of choices||[[0,'Off'],[1,'On']])input.append(new Option(label.replaceAll('_',' '),v));
  input.onchange=()=>{synthGesture='';synthQueue(port.symbol,Number(input.value));synthFlush()};
 }else{
  const dial=element('div',undefined,'synth-dial');knob=element('div',undefined,'synth-knob');knob.append(element('i'));knob.onclick=e=>{e.preventDefault();e.stopPropagation()};dial.append(knob);
  input=element('input');input.type='range';input.min=0;input.max=1000;input.step=1;
  input.onpointerdown=synthBegin;input.onpointerup=synthEnd;input.onpointercancel=synthEnd;input.onblur=()=>{if(synthEditing)synthEnd()};
  input.onkeydown=e=>{if(['ArrowLeft','ArrowRight','ArrowUp','ArrowDown','Home','End','PageUp','PageDown'].includes(e.key)&&!synthEditing)synthBegin()};input.onkeyup=synthEnd;
  input.oninput=()=>synthQueue(port.symbol,synthNumber(port,Number(input.value)/1000));
  // The dial itself drags vertically, using the same accessible range input.
  knob.onpointerdown=e=>{e.preventDefault();knob.setPointerCapture(e.pointerId);synthBegin();const y=e.clientY,start=Number(input.value);knob.onpointermove=move=>{input.value=String(Math.max(0,Math.min(1000,start+(y-move.clientY)*(move.shiftKey?1:5))));input.oninput()};knob.onpointerup=knob.onpointercancel=()=>{knob.onpointermove=null;synthEnd()}};
  box.append(dial);
  exact=element('input');exact.type='number';exact.className='synth-exact';const scale=['percent','signed_percent'].includes(port.unit)?100:1;exact.min=port.min*scale;exact.max=port.max*scale;exact.step=scale===100||port.integer?1:port.unit==='cents'?.1:'any';exact.setAttribute('aria-label','Exact '+port.name+' '+port.symbol);
  exact.onchange=()=>{const value=Number(exact.value)/scale;if(exact.value.trim()===''||!Number.isFinite(value)||value<port.min||value>port.max||port.integer&&!Number.isInteger(value)){exact.setCustomValidity('Enter a value within the parameter range.');exact.reportValidity();return}exact.setCustomValidity('');synthGesture='';synthQueue(port.symbol,value);synthFlush()};

 }
 input.setAttribute('aria-label',port.name+' '+port.symbol);box.append(input,value);if(exact)box.append(exact);
 synthWidgets.set(port.symbol,{port,input,value,knob,exact,box});return box;
}
function synthGroup(page){const advanced=/CHARACTER|RESPONSE|RING|LOOP/.test(page.title),card=element(advanced?'details':'article',undefined,'synth-section');card.append(element(advanced?'summary':'h3',page.title));const grid=element('div',undefined,'synth-grid');for(const symbol of page.controls){if(symbol.startsWith('@'))continue;const port=synthPort(symbol);if(port)grid.append(synthCard(port))}card.append(grid);return card}
function synthRender(){
 synthWidgets.clear();$('synth-tabs').replaceChildren();for(const category of synthCategories){const button=element('button',category);button.setAttribute('aria-pressed',String(category===synthCategory));button.onclick=()=>{synthCategory=category;synthModule=1;synthRender()};$('synth-tabs').append(button)}
 $('synth-subtabs').replaceChildren();const names=synthCategory==='Oscillators'?['OSC 1','OSC 2','OSC 3','OSC 4']:synthCategory==='Envelopes'?['Amplitude','Filter','Pitch','Auxiliary']:synthCategory==='LFOs'?['Voice LFO 1','Voice LFO 2','Global LFO 1','Global LFO 2']:[];
 for(const [i,name] of names.entries()){const b=element('button',name);b.setAttribute('aria-pressed',String(synthModule===i+1));b.onclick=()=>{synthModule=i+1;synthRender()};$('synth-subtabs').append(b)}
 if(synthCategory==='Matrix'){const label=element('label','Route'),select=element('select');select.setAttribute('aria-label','Modulation route');for(let i=1;i<=32;i++)select.append(new Option('Route '+i,i));select.value=String(synthModule);select.onchange=()=>{synthModule=Number(select.value);synthRender()};label.append(select);$('synth-subtabs').append(label)}
 const host=$('synth-controls');host.replaceChildren();let pages=synthSchema.pages.filter(p=>p.title!=='SYNTH / PRESETS');
 if(synthCategory==='Oscillators')pages=pages.filter(p=>p.title.startsWith('OSC '+synthModule+' /'));
 else if(synthCategory==='Filters'){pages=pages.filter(p=>p.title==='FILTER 1'||p.title==='FILTER 2');pages.push({title:'FILTER ROUTING',controls:['filter_parallel','filter_blend']})}
 else if(synthCategory==='Envelopes')pages=pages.filter(p=>p.title.startsWith(['AMP','FILTER','PITCH','AUX'][synthModule-1]+' ENV'));
 else if(synthCategory==='LFOs')pages=pages.filter(p=>p.title===(synthModule>2?'GLOBAL ':'')+'LFO '+((synthModule-1)%2+1));
 else if(synthCategory==='Matrix'){
  pages=pages.filter(p=>p.title==='MOD MATRIX '+String(synthModule).padStart(2,'0'));
  pages.push({title:'ROUTE SHAPER',controls:['matrix'+synthModule+'_shape','matrix'+synthModule+'_shape_amount']});
 }else {pages=pages.filter(p=>p.title.startsWith('SYNTH /'));pages.push({title:'PAN / MODULATION SOURCES',controls:['amp_pan','velocity_pan','ramp1','ramp2','counter1','counter2']})}
 const visual=element('div',undefined,'synth-visual'),canvas=element('canvas');canvas.id='synth-graph';canvas.width=1000;canvas.height=190;canvas.setAttribute('role','img');canvas.setAttribute('aria-label',synthCategory+' preview');visual.append(canvas);host.append(visual);
 for(const page of pages)host.append(synthGroup(page));synthSync();
}
function synthSync(){
 for(const [symbol,w] of synthWidgets){const v=synthValues[symbol]??w.port.default;
  if(/^osc[1-4]_wave$/.test(symbol)){w.input.value=v===32?'u:'+synthWaves[symbol[3]]?.id:'f:'+v;w.value.textContent=v===32?(synthWaves[symbol[3]]?.name||'Missing wave'):synthSchema.waves[v]}
  else {w.input.value=synthChoices(w.port)||w.port.toggle?String(v):String(Math.round(1000*synthRatio(w.port,v)));w.value.textContent=synthValue(w.port,v)}
  if(w.exact&&document.activeElement!==w.exact)w.exact.value=String(Number((v*(['percent','signed_percent'].includes(w.port.unit)?100:1)).toPrecision(7)));
  if(w.knob)w.knob.style.setProperty('--angle',(synthRatio(w.port,v)*270-135)+'deg');
  w.input.setAttribute('aria-valuetext',w.value.textContent);
  const match=symbol.match(/^osc([1-4])_(shape|xfade|direction|phase|free|random_phase)$/);
  if(match){const wave=synthValues['osc'+match[1]+'_wave'],stored=synthWaves[match[1]],row=synthSchema.users.find(r=>r.id===stored?.id);const table=wave>=24&&wave<=31||wave===32&&(row||stored)?.frames>1,key=match[2];
   const inactive=key==='shape'&&![4,6].includes(wave)&&!table||key==='xfade'&&!table||key==='direction'&&wave!==2||['phase','free','random_phase'].includes(key)&&[7,8].includes(wave);
   w.input.disabled=inactive;if(w.exact)w.exact.disabled=inactive;w.box.classList.toggle('synth-inactive',inactive);w.knob?.classList.toggle('disabled',inactive);
   if(key==='shape')w.box.querySelector('.synth-label').textContent=table?'POSITION':wave===4?'PULSE WIDTH':'SHAPE';
  }
 }synthDraw();
}
function synthDraw(){
 const canvas=$('synth-graph');if(!canvas)return;const g=canvas.getContext('2d'),w=canvas.width,h=canvas.height;
 g.clearRect(0,0,w,h);g.strokeStyle='#48403a';g.lineWidth=1;for(let x=0;x<w;x+=50){g.beginPath();g.moveTo(x,0);g.lineTo(x,h);g.stroke()}for(let y=0;y<h;y+=38){g.beginPath();g.moveTo(0,y);g.lineTo(w,y);g.stroke()}
 const v=synthValues;g.strokeStyle='#ff9b45';g.lineWidth=3;g.beginPath();let label='';
 if(synthCategory==='Matrix'){
  const prefix='mod'+synthModule+'_',source=synthPort(prefix+'source'),target=synthPort(prefix+'target');g.font='bold 23px system-ui';g.fillStyle='#f4f0ec';g.fillText(synthValue(source,v[prefix+'source']),30,65);g.fillText('→',w/2-20,65);g.fillText(synthValue(target,v[prefix+'target']).replaceAll('_',' '),w/2+40,65,w/2-60);
  const amount=v[prefix+'amount'];g.fillStyle='#ff9b45';g.fillRect(w/2,115,amount*w*.4,18);g.fillStyle='#b7aaa0';g.font='18px system-ui';g.fillText(Math.round(amount*100)+'% · '+(v[prefix+'source']&&v[prefix+'target']?'active route':'select source and destination'),30,160);return;
 }
 let points=[];
 if(synthCategory==='Oscillators'){
  const prefix='osc'+synthModule+'_',wave=v[prefix+'wave'],frames=wave===32?synthUserPreviews.get(synthWaves[String(synthModule)]?.id):synthSchema.previews[wave],shape=v[prefix+'shape'];label=wave===32?(synthWaves[String(synthModule)]?.name||'User wave'):synthSchema.waves[wave];
  if(frames){const pos=shape*(frames.length-1),a=Math.floor(pos),b=Math.min(a+1,frames.length-1),t=pos-a;points=frames[a].map((value,i)=>(1-t)*value+t*frames[b][i]);if(wave===4)points=points.map((_,i)=>i/points.length<.02+.96*shape?.85:-.85);if(wave===6)points=points.map((value,i)=>(1-shape)*value+shape*synthSchema.previews[3][0][i]);if(wave===2&&v[prefix+'direction'])points.reverse()}
  else {g.fillStyle='#b7aaa0';g.font='22px system-ui';g.fillText('Imported waveform · '+(synthWaves[String(synthModule)]?.frames||1)+' frames',30,105)}
 }else if(synthCategory==='Envelopes'){
  const prefix='env'+synthModule+'_',times=['delay','attack','hold','decay','release'].map(k=>v[prefix+k]),s=v[prefix+'sustain'],total=Math.max(1,times.reduce((a,b)=>a+b,0)),segments=[[times[0],0,0],[times[1],0,1],[times[2],1,1],[times[3],1,s],[total*.2,s,s],[times[4],s,0]],sum=segments.reduce((a,b)=>a+b[0],0);
  for(let i=0;i<256;i++){let t=i*sum/255,value=0;for(const [duration,a,b] of segments){if(duration>0&&t<=duration){value=a+(b-a)*(t/duration)**(3**(-v[prefix+'curve']));break}t-=duration}points.push(value*1.6-.8)}label='DAHDSR · '+['Amplitude','Filter','Pitch','Auxiliary'][synthModule-1];
 }else if(synthCategory==='LFOs'){
  const prefix='lfo'+synthModule+'_',wave=v[prefix+'wave'];for(let i=0;i<256;i++){const x=(i/128+v[prefix+'phase'])%1;points.push((wave===0?Math.sin(Math.PI*2*x):wave===1?1-4*Math.abs(x-.5):wave===2?2*x-1:wave===3?1-2*x:wave===4?(x<.5?1:-1):Math.sin(Math.floor(x*8)*73.1))*v[prefix+'level'])}label='LFO · '+synthValue(synthPort(prefix+'wave'),wave);
 }else if(synthCategory==='Filters'){
  const cut=v.filter1_cutoff,res=v.filter1_resonance,type=v.filter1_type;for(let i=0;i<256;i++){const freq=20*1000**(i/255),x=freq/cut,den=Math.sqrt((1-x*x)**2+(2-1.95*res)**2*x*x);let magnitude=type?(type<=2?1:type<=4?x*x:type<=6?x:Math.abs(1-x*x))/Math.max(.0001,den):1;if(type&&type%2===0)magnitude*=magnitude;points.push(Math.max(-1,Math.min(1,(20*Math.log10(Math.max(.001,magnitude))+24)/36)))}label='Filter 1 · '+synthValue(synthPort('filter1_type'),type)+' · '+synthValue(synthPort('filter1_cutoff'),cut);
 }else{
  g.font='bold 22px system-ui';for(let o=1;o<=4;o++){g.fillStyle='#b7aaa0';g.fillText('OSC '+o,25+(o-1)*w/4,45);g.fillStyle='#ff9b45';g.fillRect(25+(o-1)*w/4,80,(w/4-55)*v['osc'+o+'_level']*v['osc'+o+'_on'],32)}return;
 }
 for(const [i,value] of points.entries()){const x=15+i*(w-30)/Math.max(1,points.length-1),y=h/2-value*(h/2-32);if(i===0)g.moveTo(x,y);else g.lineTo(x,y)}g.stroke();g.fillStyle='#b7aaa0';g.font='16px system-ui';g.fillText(label,18,h-9);
}
async function synthFetchWave(id){if(synthUserPreviews.has(id))return;synthUserPreviews.set(id,null);try{const result=await api('/api/synth/wave?'+new URLSearchParams({id}));synthUserPreviews.set(id,result.frames);while(synthUserPreviews.size>8)synthUserPreviews.delete(synthUserPreviews.keys().next().value);synthDraw()}catch(e){/* Saved native states still play if the source catalog was removed. */}}
$('tab-synth').onclick=()=>workspace('synth');$('synth-refresh').onclick=async()=>{await synthFlush();synthLoad(true)};
$('synth-bank').onchange=synthPatchList;
$('synth-preset').onclick=()=>{if(confirm('Replace this Synth patch? Unsaved edits can be recovered with Undo.'))synthCommand({preset:{bank:$('synth-bank').value,patch:Number($('synth-patch').value)}})};
$('synth-slot').onchange=async()=>{await synthFlush();synthSlot=Number($('synth-slot').value);synthLoad(true)};
$('synth-save').onclick=async()=>{await synthFlush();if(!synthContext)return;workspace('sounds');$('sound-capture').click()};
$('synth-import').onclick=()=>workspace('oscillators');
setInterval(()=>{if(synthVisible&&!document.hidden)synthLoad()},1000);
