// SPDX-License-Identifier: GPL-3.0-or-later
// Conservative event completion. Unknown/ambiguous evidence never advances.
const key=(id,b)=>id+':'+b[0]+':'+b.length;
const packet=hex=>Uint8Array.from(hex.match(/../g)||[],x=>parseInt(x,16));
// Some HID stacks pad reports to the endpoint size. Only accept zero padding.
const jamReport=(b,id,length)=>b[0]===id&&b.length>=length&&b.length<=65&&b.subarray(length).every(value=>value===0);
const jamButtons=b=>jamReport(b,1,17);
export class ActionDetector {
 constructor(step,initial=[],now=0,options={}){this.step=step;this.profileId=options.profileId;this.jamHidButton=options.hidConnected&&this.profileId==='maschine_jam'&&(step.kind==='button'||step.kind==='pedal'||step.kind==='touch'&&step.id==='touch_encoder_touch');if(this.jamHidButton)initial=initial.filter(f=>f.interface.startsWith('hid')&&jamButtons(packet(f.hex)));this.started=now;this.readyAt=initial.length?now:now+250;this.base=new Map();this.unstable=new Map();this.warmValues=new Map();this.stats=new Map();this.frames=[];this.active=null;this.firstAction=null;this.lastMove=now;this.done=false;this.problem='';this.lastPackets=new Map();this.calibrating=new Set();for(const f of initial){const b=packet(f.hex);this.base.set(key(f.interface,b),b);}this.initial=initial;}
 record(id,b,now){const k=key(id,b),h=Array.from(b,x=>x.toString(16).padStart(2,'0')).join(''),previous=this.lastPackets.get(k);if(id.startsWith('hid')&&previous?.hex===h)return;if(b[0]===0x20&&previous&&now-previous.time<20)return;this.lastPackets.set(k,{hex:h,time:now});if(this.firstAction===null)this.frames=this.frames.filter(f=>f.time>=now-1200);if(this.frames.length>=3000){this.problem='Too much input data. Pause other controllers and retry.';return;}this.frames.push({time:now,interface:id,hex:h});}

 feed(id,b,now){
  if(this.done||this.problem||!b.length||b.length>512)return;
  const k=key(id,b),kind=this.step.kind,old=this.base.get(k),midi=id.startsWith('midi');
  if(this.jamHidButton&&(midi||!jamButtons(b)))return;
  if(this.profileId==='maschine_jam'&&!midi){
   if((kind==='slider'||kind==='touch')&&this.step.name?.startsWith('SMART STRIP')){
    if(jamReport(b,2,49)){this.record(id,b,now);this.jamStrip(id,b,now);}
    return;
   }
   if(kind==='encoder'){
    if(jamButtons(b)){this.record(id,b,now);this.jamEncoder(id,k,old,b,now);}
    return;
   }
  }
  if(!midi&&kind!=='pad'&&[0x20,2].includes(b[0]))return;
  if(!midi&&kind==='pad'&&![0x20,2].includes(b[0]))return;
  this.record(id,b,now);
  if(this.jamHidButton){
   this.jamButton(id,k,old,b,now);
   return;
  }
  if(now<this.readyAt){if(old&&!midi&&!this.calibrating.has(k)){const mask=this.unstable.get(k)||new Uint8Array(b.length);for(let i=1;i<b.length;i++){const id=k+':'+i,values=this.warmValues.get(id)||new Set([old[i]]);values.add(b[i]);this.warmValues.set(id,values);if(values.size>=3)mask[i]|=old[i]^b[i];}this.unstable.set(k,mask);}if(this.calibrating.has(k)&&old&&b.some((v,i)=>v!==old[i]))this.readyAt=now+300;this.base.set(k,b.slice());return;}
  this.calibrating.delete(k);
  if(midi){this.midi(id,b,now);return;}
  if(kind==='pad'){
   if(b[0]===2&&b.length===64){for(let i=1;i+2<b.length;i+=3){const raw=b[i],type=b[i+1]&0xf0,value=((b[i+1]&15)<<8)|b[i+2];if(raw>15)continue;const signature=id+':pad:'+raw;if(type===0x10&&value>0)this.begin(signature,now);if(this.active?.signature===signature&&[0x20,0x30].includes(type)){if(!this.active.released){this.active.released=true;this.lastMove=now;}}}return;}
   if(b[0]===0x20&&b.length===65&&old){const adc=p=>{const a=Array.from({length:16},()=>[]);for(let i=1;i<65;i+=2)a[p[i+1]>>4].push(p[i]|((p[i+1]&15)<<8));return a.map(v=>v.reduce((a,b)=>a+b,0)/Math.max(1,v.length));};const baseline=adc(old),values=adc(b),peaks=values.map((v,i)=>({channel:i,delta:v-baseline[i]})).sort((a,b)=>b.delta-a.delta);if(peaks[0].delta>=80){if(peaks[1].delta>peaks[0].delta*.55){this.problem='More than one pad responded. Release all pads and retry one pad only.';return;}this.begin(id+':adc:'+peaks[0].channel,now);}if(this.active){const channel=Number(this.active.signature.split(':').at(-1));if(values[channel]<=baseline[channel]+25){if(!this.active.released){this.active.released=true;this.lastMove=now;}}}return;}
   return;
  }
  if([0x20,2].includes(b[0]))return; // continuous pad packets are never button/encoder evidence
  if(!old){this.base.set(k,b.slice());this.calibrating.add(k);this.readyAt=now+400;return;}
  if(['button','touch'].includes(kind)){
   const ignored=this.unstable.get(k),changed=[];for(let byte=1;byte<b.length;byte++){const delta=(old[byte]^b[byte])&~(ignored?.[byte]||0);for(let bit=0;bit<8;bit++)if(delta&(1<<bit))changed.push({byte,mask:1<<bit});}
   if(!this.active&&changed.length>1){this.problem='Several bits changed together. Retry only this control, or use manual recording.';return;}
   if(!this.active&&changed.length===1){const c=changed[0];this.begin(id+':bit:'+b[0]+':'+c.byte+':'+c.mask,now);this.active.k=k;this.active.byte=c.byte;this.active.mask=c.mask;}
   if(this.active?.k===k){const c=this.active;if(((old[c.byte]^b[c.byte])&c.mask)===0){if(!c.released){c.released=true;this.lastMove=now;}}}
   return;
  }
  if(kind==='encoder'&&this.profileId==='maschine_mk2'&&b[0]===1&&b.length===25){this.mk2Encoder(id,k,old,b,now);return;}
  if(['encoder','slider','pressure','pedal'].includes(kind)){
   for(let byte=1;byte<b.length;byte++){
    const statKey=k+':'+byte;let stat=this.stats.get(statKey);if(!stat){stat={values:new Set([old[byte]]),last:old[byte],changes:0,signature:id+':analog:'+b[0]+':'+byte};this.stats.set(statKey,stat);}if(b[byte]!==stat.last){stat.values.add(b[byte]);stat.last=b[byte];stat.changes++;this.lastMove=now;}
   }
   const moved=[...this.stats.values()].filter(s=>s.values.size>=3&&s.changes>=2);if(moved.length>1){this.problem='Several independent values moved. Retry only the named control, or use manual recording.';return;}if(moved.length===1){if(!this.active)this.begin(moved[0].signature,now);this.active.released=true;}return;
  }
 }
 // Track active-high edges separately from the idle snapshot in the export.
 jamButton(id,k,old,b,now){
  this.jamPrevious??=new Map();
  const previous=this.jamPrevious.get(k)||old;
  this.jamPrevious.set(k,b.slice());
  this.readyAt=now;
  const rising=[];
  for(let byte=2;byte<17;byte++){
   const companion=this.step.id==='button_encoder_push'&&byte===16?0x08:0;
   const bits=b[byte]&~((previous?.[byte]||0)|companion);
   for(let bit=0;bit<8;bit++)if(bits&(1<<bit))rising.push([byte,1<<bit]);
  }
  if(rising.length>1){this.problem='Several JAM buttons responded. Release everything and repeat this step.';return;}
  if(rising.length===1){
   const [byte,mask]=rising[0];
   this.begin(id+':bit:1:'+byte+':'+mask,now);
   if(this.problem)return;
   Object.assign(this.active,{k,byte,mask,released:false});
  }
  const c=this.active;
  if(c?.k===k&&!c.released&&!(b[c.byte]&c.mask)){
   if(!old)this.base.set(k,b.slice());
   c.released=true;
   this.lastMove=now;
  }
 }

 jamEncoder(id,k,old,b,now){
  const value=b[1]&15;
  let stat=this.stats.get(k);
  if(!stat){stat={last:old?old[1]&15:value,moves:0};this.stats.set(k,stat);}
  if(stat.last===value)return;
  stat.last=value;
  this.lastMove=now;
  if(++stat.moves>=2){
   this.begin(id+':counter:1:1:1:16',now);
   if(!this.problem)this.active.released=true;
  }
 }

 jamStrip(id,b,now){
  const occupied=[];
  for(let strip=0;strip<8;strip++){
   const offset=3+strip*6;
   const primary=b[offset]|(b[offset+1]&3)<<8;
   const secondary=b[offset+2]|(b[offset+3]&3)<<8;
   if(primary||secondary)occupied.push({strip,primary,secondary});
  }
  if(occupied.length>1){this.problem='Touch only the named Smart Strip.';return;}
  const dual=this.step.name.endsWith('/ two fingers');
  const contact=occupied[0];
  if(!contact){
   if(this.active&&!this.active.released){
    if(this.step.kind==='touch'||this.active.positions.size>=3){
     this.active.released=true;
     this.lastMove=now;
    }else this.problem='Move along the strip before releasing and repeat this step.';
   }
   return;
  }
  const signature=id+':strip:'+contact.strip+':'+(this.step.kind==='touch'?'touch':dual?'dual':'single');
  if(!dual&&contact.secondary){this.problem='Use one finger for this Smart Strip step.';return;}
  if(dual&&!this.active&&!contact.secondary)return;
  this.begin(signature,now);
  if(this.problem)return;
  this.active.positions??=new Set();
  if(!dual||contact.secondary)this.active.positions.add(dual?contact.secondary:contact.primary);
 }

 mk2Encoder(id,k,old,b,now){
  const values=p=>[p[8],...Array.from({length:8},(_,i)=>p[9+i*2]|p[10+i*2]<<8)],current=values(b),baseline=values(old);
  if(current[0]>15||baseline[0]>15||current.slice(1).some(v=>v>999)||baseline.slice(1).some(v=>v>999)){this.problem='Invalid MK2 rotary-counter packet. Repeat this control after reconnecting.';return;}
  for(let i=0;i<9;i++){
   const offset=i?9+(i-1)*2:8,modulus=i?1000:16,statKey=k+':counter:'+offset;
   let stat=this.stats.get(statKey);if(!stat){stat={last:baseline[i],changes:0,distance:0,signature:id+':counter:1:'+offset+':'+(i?2:1)+':'+modulus};this.stats.set(statKey,stat);}
   const delta=(current[i]-stat.last+modulus/2+modulus)%modulus-modulus/2;
   if(delta){if(Math.abs(delta)>=modulus/2){this.problem='Ambiguous MK2 rotary jump. Turn more slowly and repeat.';return;}stat.last=current[i];stat.changes++;stat.distance+=Math.abs(delta);this.lastMove=now;}
  }
  const moved=[...this.stats.values()].filter(s=>s.changes>0);
  if(moved.length>1){this.problem='Several MK2 encoders moved. Turn only the named knob and retry.';return;}
  if(moved.length===1&&moved[0].changes>=2&&moved[0].distance>=2){this.begin(moved[0].signature,now);this.active.released=true;}
 }

 begin(signature,now){if(this.active&&this.active.signature!==signature){this.problem='More than one control responded. Release everything and retry.';return;}if(!this.active){this.active={signature,released:false};this.firstAction=now;this.lastMove=now;}}
 midi(id,b,now){
  const status=b[0]&0xf0,ch=b[0]&15,kind=this.step.kind;
  if(['key','pad','button','touch','pedal'].includes(kind)&&b.length===3&&[0x80,0x90].includes(status)){const signature=id+':note:'+ch+':'+b[1];if(status===0x90&&b[2]>0)this.begin(signature,now);else if(this.active?.signature===signature){if(!this.active.released){this.active.released=true;this.lastMove=now;}}return;}
  if(['button','touch'].includes(kind)&&status===0xb0&&b.length===3){const signature=id+':cc-button:'+ch+':'+b[1];if(b[2]>0)this.begin(signature,now);else if(this.active?.signature===signature&&!this.active.released){this.active.released=true;this.lastMove=now;}return;}
  if(kind==='pressure'&&[0xa0,0xd0].includes(status)){const signature=id+':pressure:'+ch;this.begin(signature,now);this.active.pressure ||=new Set();this.active.pressure.add(b.at(-1));if(this.active.pressure.size>=3&&b.at(-1)===0)this.active.released=true;return;}
  if(['encoder','slider','pedal'].includes(kind)&&b.length===3&&[0xb0,0xe0].includes(status)){
   const signature=id+':cc:'+ch+':'+(status===0xb0?b[1]:'pitch');this.begin(signature,now);this.lastMove=now;this.active.events=(this.active.events||0)+1;this.active.values ||=new Set();this.active.values.add(status===0xb0?b[2]:b[1]|b[2]<<7);if(this.active.events>=3&&(kind==='encoder'||this.active.values.size>=3))this.active.released=true;
  }
 }
 tick(now){
  if(this.problem)return {state:'ambiguous',message:this.problem};
  if(now<this.readyAt)return {state:'settling'};
  if(this.firstAction!==null&&now-this.firstAction>8000)return {state:'ambiguous',message:'This action took too long. Release the control and retry.'};
  if(this.active?.released&&now-this.lastMove>=250){this.done=true;return {state:'complete',signature:this.active.signature,frames:this.evidence()};}
  if(this.profileId==='maschine_mk2'&&this.step.kind==='encoder'&&!this.active&&[...this.stats.values()].some(s=>s.changes>0))return {state:'waiting',message:'Rotary movement received · turn one more step, then stop.'};
  return {state:this.active?'release':'waiting',message:this.calibrating.size?'Release, then operate this control once more to verify its idle state.':undefined};
 }
 evidence(){
  const start=this.firstAction-1000, initial=[...this.base].map(([k,b])=>({ms:0,interface:k.split(':')[0],hex:Array.from(b,x=>x.toString(16).padStart(2,'0')).join('')}));
  // Idle snapshots are retained at window start; actual event times stay relative to it.
  return [...initial,...this.frames.filter(f=>f.time>=start).map(f=>({ms:Math.round(f.time-start),interface:f.interface,hex:f.hex}))].sort((a,b)=>a.ms-b.ms);
 }
}

// A connected JAM can report a button over HID, MIDI, or both. Track each
// transport independently so mirrored messages cannot look like two controls.
export function createActionDetector(step,initial,now,options){
 if(options.profileId!=='maschine_jam'||step.kind!=='button'||!options.hidConnected)
  return new ActionDetector(step,initial,now,options);
 const hid=new ActionDetector(step,initial,now,options);
 const mode=options.jamInput||'auto';
 const midi=options.midiSelected&&mode!=='hid'?new ActionDetector(step,[],now):null;
 if(midi)midi.readyAt=now;
 let midiReadyAt=null,hidReports=0,midiReports=0;
 const hidFormats=new Set();
 return {
  feed(id,bytes,time){
   if(id.startsWith('midi')){
    midiReports++;
    midi?.feed(id,bytes,time);
   }else{
    hidReports++;
    if(hidFormats.size<4)hidFormats.add('0x'+bytes[0].toString(16)+'/'+bytes.length);
    if(mode!=='midi')hid.feed(id,bytes,time);
   }
  },
  inputStatus(){return 'HID reports: '+hidReports+' · MIDI reports: '+midiReports;},
  tick(time){
   const h=mode==='midi'?{state:'waiting'}:hid.tick(time);
   if(h.state==='complete'||h.state==='ambiguous')return h;
   const m=midi?.tick(time);
   if(m?.state==='complete'){
    midiReadyAt??=time;
    if(h.state!=='release'&&time-midiReadyAt>=(mode==='midi'?0:650))return m;
   }
   if(h.state==='release'||m?.state==='release')return {state:'release'};
   if(m?.state==='ambiguous'&&h.state!=='release'&&time-now>=2000)return m;
   if(time-now>=15000)return {state:'ambiguous',message:
    'No complete JAM button press detected (HID: '+hidReports+' reports, MIDI: '+midiReports+' reports'+(hidFormats.size?', HID formats: '+[...hidFormats].join(', '):'')+'). '+
    (mode==='hid'?'Check the HID input and repeat this step.':'Check the JAM input and repeat this step.')};
   return h;
  },
 };
}
