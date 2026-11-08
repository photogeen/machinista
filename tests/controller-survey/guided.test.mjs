import test from 'node:test';import assert from 'node:assert/strict';
import {ActionDetector,createActionDetector} from '../../web/controller-survey/guided.mjs';
const idle=[{interface:'hid0',hex:'010000'}];
test('one button advances only after press, release and debounce',()=>{const d=new ActionDetector({kind:'button'},idle,0);d.feed('hid0',new Uint8Array([1,4,0]),1100);assert.equal(d.tick(1500).state,'release');d.feed('hid0',new Uint8Array([1,0,0]),1600);assert.notEqual(d.tick(1700).state,'complete');const r=d.tick(1900);assert.equal(r.state,'complete');assert.match(r.signature,/bit:1:1:4/);assert(r.frames.some(f=>f.ms>=1000));});
test('steady periodic idle packets cannot postpone release completion',()=>{const d=new ActionDetector({kind:'button'},idle,0);d.feed('hid0',new Uint8Array([1,4,0]),1100);d.feed('hid0',new Uint8Array([1,0,0]),1300);for(let t=1350;t<1800;t+=50)d.feed('hid0',new Uint8Array([1,0,0]),t);assert.equal(d.tick(1800).state,'complete');});
test('continuous pads cannot be mistaken for a button',()=>{const d=new ActionDetector({kind:'button'},idle,0);for(let t=0;t<90000;t+=20)d.feed('hid0',new Uint8Array(65).fill(0x20),t);assert.equal(d.tick(90000).state,'waiting');assert.equal(d.frames.length,0);});
test('two button bits pause instead of guessing',()=>{const d=new ActionDetector({kind:'button'},idle,0);d.feed('hid0',new Uint8Array([1,5,0]),1100);assert.equal(d.tick(1400).state,'ambiguous');});
test('one clockwise turn is sufficient, with no second-direction stage',()=>{const d=new ActionDetector({kind:'encoder'},idle,0);for(let n=1;n<=3;n++)d.feed('hid0',new Uint8Array([1,0,n]),1000+n*100);assert.notEqual(d.tick(1400).state,'complete');assert.equal(d.tick(1700).state,'complete');});
test('rotary touch bit alone cannot count as turning',()=>{const d=new ActionDetector({kind:'encoder'},idle,0);d.feed('hid0',new Uint8Array([1,4,0]),1100);d.feed('hid0',new Uint8Array([1,0,0]),1300);assert.equal(d.tick(1800).state,'waiting');});
test('MIDI note-off must match the played key and channel',()=>{const d=new ActionDetector({kind:'key'},[],0);d.feed('midi0',new Uint8Array([0x90,60,100]),1100);d.feed('midi0',new Uint8Array([0x81,60,0]),1300);assert.equal(d.tick(1600).state,'release');d.feed('midi0',new Uint8Array([0x80,60,0]),1700);assert.equal(d.tick(2000).state,'complete');});
test('relative MIDI encoder repeated increments count as motion',()=>{const d=new ActionDetector({kind:'encoder'},[],0);for(let i=0;i<3;i++)d.feed('midi0',new Uint8Array([0xb0,20,1]),1100+i*100);assert.equal(d.tick(1700).state,'complete');});
test('Mikro event pad must be played and released',()=>{const d=new ActionDetector({kind:'pad'},[],0);const on=new Uint8Array(64);on.set([2,12,0x12,0x40]);d.feed('hid0',on,1100);assert.equal(d.tick(1500).state,'release');const off=new Uint8Array(64);off.set([2,12,0x20,0]);d.feed('hid0',off,1600);assert.equal(d.tick(1900).state,'complete');});
test('a long-held control pauses; waiting idle does not time out',()=>{const d=new ActionDetector({kind:'button'},idle,0);assert.equal(d.tick(20000).state,'waiting');d.feed('hid0',new Uint8Array([1,4,0]),21000);assert.equal(d.tick(30000).state,'ambiguous');});
test('unknown initial HID idle state can be learned without permanently ignoring the button',()=>{const d=new ActionDetector({kind:'button'},[],0);d.feed('hid0',new Uint8Array([1,4]),1100);d.feed('hid0',new Uint8Array([1,0]),1300);assert.equal(d.tick(1800).state,'waiting');d.feed('hid0',new Uint8Array([1,4]),2000);d.feed('hid0',new Uint8Array([1,0]),2200);assert.equal(d.tick(2500).state,'complete');});
test('an early tap during settling does not permanently disable the expected bit',()=>{const d=new ActionDetector({kind:'button'},idle,0);d.feed('hid0',new Uint8Array([1,4,0]),300);d.feed('hid0',new Uint8Array([1,0,0]),500);d.feed('hid0',new Uint8Array([1,4,0]),1300);d.feed('hid0',new Uint8Array([1,0,0]),1500);assert.equal(d.tick(1800).state,'complete');});
test('a fast first press after a new prompt is captured once with normalized evidence',()=>{const d=new ActionDetector({kind:'button'},idle,10000);d.feed('hid0',new Uint8Array([1,4,0]),10050);d.feed('hid0',new Uint8Array([1,0,0]),10130);const r=d.tick(10400);assert.equal(r.state,'complete');assert(r.frames.some(f=>f.ms===1000&&f.hex==='010400'));});
function mk2Packet(knob=0,master=0,second=0){const b=new Uint8Array(25);b[0]=1;b[8]=master;new DataView(b.buffer).setUint16(9,knob,true);new DataView(b.buffer).setUint16(11,second,true);return b;}
function mk2Detector(base){return new ActionDetector({kind:'encoder',name:'KNOB 1'},[{interface:'hid0',hex:Array.from(base,n=>n.toString(16).padStart(2,'0')).join('')}],0,{profileId:'maschine_mk2'});}
test('MK2 knob 1 is one 16-bit counter across carries and modulus-1000 wrap',()=>{for(const values of [[254,255,256,257],[998,999,0,1],[510,511,512,513],[100,300,600,800]]){const d=mk2Detector(mk2Packet(values[0]));for(let n=1;n<values.length;n++)d.feed('hid0',mk2Packet(values[n]),100+n*80);const result=d.tick(700);assert.equal(result.state,'complete');assert.equal(result.signature,'hid0:counter:1:9:2:1000');}});
test('MK2 master 4-bit wrap works and knob 2 has its own signature',()=>{const m=mk2Detector(mk2Packet(400,15));m.feed('hid0',mk2Packet(400,0),100);m.feed('hid0',mk2Packet(400,1),200);assert.equal(m.tick(500).signature,'hid0:counter:1:8:1:16');const d=mk2Detector(mk2Packet(400,0,254));d.feed('hid0',mk2Packet(400,0,255),100);d.feed('hid0',mk2Packet(400,0,256),200);assert.equal(d.tick(500).signature,'hid0:counter:1:11:2:1000');});
test('MK2 held buttons and unchanged reports do not count as turning; two knobs pause',()=>{const d=mk2Detector(mk2Packet(100));const b=mk2Packet(100);b[1]=1;d.feed('hid0',b,100);assert.equal(d.tick(500).state,'waiting');d.feed('hid0',mk2Packet(101,0,1),600);assert.equal(d.tick(900).state,'ambiguous');});

test('unchanged periodic reports cannot indefinitely postpone unknown-stream calibration',()=>{const d=new ActionDetector({kind:'encoder'},[],0);d.feed('hid0',new Uint8Array([1,0,10]),500);for(let t=550;t<1200;t+=50)d.feed('hid0',new Uint8Array([1,0,10]),t);d.feed('hid0',new Uint8Array([1,0,11]),1300);d.feed('hid0',new Uint8Array([1,0,12]),1400);assert.equal(d.tick(1700).state,'complete');});

const jamButton = bits => Uint8Array.of(1, 2, bits, ...new Uint8Array(14));
const jamOptions = {profileId:'maschine_jam',hidConnected:true};
const jamIdle = [{interface:'hid0',hex:'0102'+'00'.repeat(15)}];

test('JAM guided button uses its HID packet even when MIDI arrives first',()=>{
 const d=new ActionDetector({kind:'button'},jamIdle,0,jamOptions);
 d.feed('midi0',Uint8Array.of(0x90,60,100),1000);
 d.feed('midi1',Uint8Array.of(0xb0,20,127),1010);
 d.feed('hid0',jamButton(1),1020);
 assert.equal(d.tick(1200).state,'release');
 d.feed('hid0',jamButton(0),1300);
 const result=d.tick(1600);
 assert.equal(result.state,'complete');
 assert.equal(result.signature,'hid0:bit:1:2:1');
 assert(result.frames.every(frame=>frame.interface==='hid0'));
});

test('JAM guided mapping still pauses for a second physical button',()=>{
 const d=new ActionDetector({kind:'button'},jamIdle,0,jamOptions);
 d.feed('hid0',jamButton(1),1000);
 d.feed('hid0',jamButton(3),1100);
 assert.equal(d.tick(1400).state,'ambiguous');
});

test('JAM MIDI-only button capture still accepts MIDI',()=>{
 const d=new ActionDetector({kind:'button'},[],0,{profileId:'maschine_jam'});
 d.feed('midi0',Uint8Array.of(0x90,60,100),1000);
 d.feed('midi0',Uint8Array.of(0x80,60,0),1200);
 assert.equal(d.tick(1500).state,'complete');
});

test('JAM encoder push can arrive with its companion touch bit',()=>{
 const d=new ActionDetector({id:'button_encoder_push',kind:'button'},jamIdle,0,jamOptions);
 const held=jamButton(0);
 held[16]=0x18;
 d.feed('hid0',held,1000);
 held[16]=0x08;
 d.feed('hid0',held,1200);
 assert.equal(d.tick(1500).signature,'hid0:bit:1:16:16');
});

const jamDualOptions = {...jamOptions,midiSelected:true};
test('JAM with an open but silent HID interface can finish a Windows MIDI button',()=>{
 const d=createActionDetector({kind:'button'},[],0,jamDualOptions);
 d.feed('midi0',Uint8Array.of(0x90,60,100),100);
 d.feed('midi0',Uint8Array.of(0x80,60,0),200);
 assert.notEqual(d.tick(500).state,'complete');
 const result=d.tick(1150);
 assert.equal(result.state,'complete');
 assert.equal(result.signature,'midi0:note:0:60');
});

test('JAM keeps HID evidence when MIDI and HID mirror a press',()=>{
 const d=createActionDetector({kind:'button'},jamIdle,0,jamDualOptions);
 d.feed('midi0',Uint8Array.of(0x90,60,100),1000);
 d.feed('midi0',Uint8Array.of(0xb0,20,127),1005);
 d.feed('hid0',jamButton(1),1020);
 d.feed('hid0',jamButton(0),1300);
 assert.equal(d.tick(1600).signature,'hid0:bit:1:2:1');
});

test('JAM with no button reports times out with transport diagnostics',()=>{
 const d=createActionDetector({kind:'button'},[],0,jamDualOptions);
 assert.match(d.tick(15001).message,/HID: 0 reports, MIDI: 0 reports/);
});

test('explicit JAM MIDI mode ignores HID and finishes on MIDI release',()=>{
 const d=createActionDetector({kind:'button'},jamIdle,0,{...jamDualOptions,jamInput:'midi'});
 d.feed('hid0',jamButton(3),100);
 d.feed('midi0',Uint8Array.of(0xb0,20,127),110);
 d.feed('midi0',Uint8Array.of(0xb0,20,0),200);
 assert.equal(d.tick(500).signature,'midi0:cc-button:0:20');
 assert.equal(d.inputStatus(),'HID reports: 1 · MIDI reports: 2');
});
test('explicit JAM HID mode does not fall back to MIDI',()=>{
 const d=createActionDetector({kind:'button'},jamIdle,0,{...jamDualOptions,jamInput:'hid'});
 d.feed('midi0',Uint8Array.of(0x90,60,100),100);
 d.feed('midi0',Uint8Array.of(0x80,60,0),200);
 assert.equal(d.tick(2000).state,'waiting');
 d.feed('hid0',jamButton(1),2100);
 d.feed('hid0',jamButton(0),2300);
 assert.equal(d.tick(2600).signature,'hid0:bit:1:2:1');
});

test('JAM next button tolerates a different rotary counter from the previous idle report',()=>{
 const song=createActionDetector({kind:'button'},jamIdle,0,jamDualOptions);
 song.feed('hid0',jamButton(1),1000);
 song.feed('hid0',jamButton(0),1200);
 assert.equal(song.tick(1500).signature,'hid0:bit:1:2:1');
 const scene=createActionDetector({kind:'button'},jamIdle,1500,jamDualOptions);
 const press=jamButton(2),release=jamButton(0);
 press[1]=3;
 release[1]=4;
 scene.feed('hid0',press,1800);
 scene.feed('hid0',release,2000);
 assert.equal(scene.tick(2300).signature,'hid0:bit:1:2:2');
});

test('JAM accepts a button report with zero padding and preserves raw evidence',()=>{
 const padded=bits=>Uint8Array.of(...jamButton(bits),...new Uint8Array(48));
 const initial=[{interface:'hid0',hex:Buffer.from(padded(0)).toString('hex')}];
 const d=createActionDetector({kind:'button'},initial,0,jamDualOptions);
 d.feed('hid0',padded(2),1000);
 d.feed('hid0',padded(0),1200);
 const result=d.tick(1500);
 assert.equal(result.signature,'hid0:bit:1:2:2');
 assert(result.frames.every(frame=>frame.hex.length===130));
});

function jamStripPacket(strip,primary,secondary=0,time=0){
 const b=new Uint8Array(49);b[0]=2;
 const view=new DataView(b.buffer),offset=1+strip*6;
 view.setUint16(offset,time,true);
 view.setUint16(offset+2,primary,true);
 view.setUint16(offset+4,secondary,true);
 return b;
}
test('JAM strip position, dual position and touch each use one verified HID gesture',()=>{
 for(let strip=0;strip<8;strip++)for(const gesture of ['single','dual','touch']){
  const kind=gesture==='touch'?'touch':'slider';
  const name='SMART STRIP '+(strip+1)+(gesture==='dual'?' / two fingers':'');
  const d=createActionDetector({kind,name},[],0,jamOptions);
  for(let i=1;i<=3;i++)d.feed('hid0',jamStripPacket(strip,255+i,gesture==='dual'?511+i:0,i),i*100);
  assert.notEqual(d.tick(600).state,'complete');
  d.feed('hid0',jamStripPacket(strip,0,0,4),700);
  assert.equal(d.tick(1000).signature,'hid0:strip:'+strip+':'+gesture);
 }
});
test('JAM encoder reads only its wrapped counter and ignores touch changes',()=>{
 const d=createActionDetector({kind:'encoder'},jamIdle,0,jamOptions);
 for(const [i,count] of [14,15,0].entries()){
  const b=jamButton(0);b[1]=count;b[16]=i?8:0;d.feed('hid0',b,300+i*100);
 }
 assert.equal(d.tick(800).signature,'hid0:counter:1:1:1:16');
});
test('JAM footswitch uses the HID button report',()=>{
 const d=createActionDetector({kind:'pedal',name:'FOOTSWITCH'},jamIdle,0,jamOptions);
 const pressed=jamButton(0);pressed[16]=0x20;
 d.feed('hid0',pressed,1000);d.feed('hid0',jamButton(0),1200);
 assert.equal(d.tick(1500).signature,'hid0:bit:1:16:32');
});

test('first JAM press and release work without an idle report at connect time',()=>{
 const d=createActionDetector({kind:'button'},[],0,{...jamOptions,jamInput:'hid'});
 d.feed('hid0',jamButton(1),100);
 assert.notEqual(d.tick(200).state,'complete');
 d.feed('hid0',jamButton(0),230);
 const result=d.tick(500);
 assert.equal(result.signature,'hid0:bit:1:2:1');
 assert.equal(result.frames.filter(f=>f.ms>=1000).length,2);
});

test('JAM encoder touch does not end an encoder push or turn its release into a matrix press',()=>{
 const push={id:'button_encoder_push',kind:'button'};
 const p=new ActionDetector(push,jamIdle,0,jamOptions);
 const encoder=bits=>{const report=jamButton(0);report[16]=bits;return report;};
 p.feed('hid0',encoder(8),100);
 p.feed('hid0',encoder(24),200);
 p.feed('hid0',encoder(16),300);
 assert.equal(p.tick(600).state,'release');
 p.feed('hid0',encoder(0),700);
 assert.equal(p.tick(1000).signature,'hid0:bit:1:16:16');
 const held=[{interface:'hid0',hex:Buffer.from(encoder(16)).toString('hex')}];
 const matrix=new ActionDetector({kind:'button'},held,1000,jamOptions);
 matrix.feed('hid0',encoder(0),1100);
 assert.equal(matrix.tick(1400).state,'waiting');
 matrix.feed('hid0',jamButton(4),1500);
 matrix.feed('hid0',jamButton(0),1600);
 assert.equal(matrix.tick(1900).signature,'hid0:bit:1:2:4');
});
