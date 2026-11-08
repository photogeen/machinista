import test from 'node:test';import assert from 'node:assert/strict';import {readFile} from 'node:fs/promises';
import {enableBacklight,restoreBacklight,showLed,ledInventory,sanitizeLeds,ledCoverage} from '../../web/controller-survey/outputs.mjs';
import {validateReport} from '../../web/controller-survey/core.mjs';
const profiles=JSON.parse(await readFile(new URL('../../web/controller-survey/catalog.json',import.meta.url))),p=JSON.parse(await readFile(new URL('./fixtures/mk2.json',import.meta.url)));
profiles.maschine_mk2=p;
function device(){const writes=[],features=[],initial=rid=>new Uint8Array([rid,0,1,64,0,7,8,9,0,45,1]);return {writes,features,device:{vendorId:0x17cc,productId:0x1140,collections:[{outputReports:p.led_banks.map(b=>({reportId:b.report_id,items:[{reportSize:8,reportCount:b.size-1}]})),featureReports:[0xf8,0xf9].map(reportId=>({reportId,items:[{reportSize:8,reportCount:10}]}))}],receiveFeatureReport:async rid=>new DataView(initial(rid).buffer),sendFeatureReport:async(id,data)=>features.push({id,data:[...data]}),sendReport:async(id,data)=>writes.push({id,data:[...data]})}};}
test('MK2 backlight preserves every unrelated setting and restores on disconnect',async()=>{const d=device();await enableBacklight(p,[d]);assert.equal(d.features.length,2);for(const f of d.features){assert.equal(f.data[7],85);assert.equal(f.data[8],45);assert.deepEqual(f.data.slice(0,7),[0,1,64,0,7,8,9]);}await restoreBacklight();assert.equal(d.features.length,4);assert.equal(d.features[2].data[7],0);});
test('MK2 LED inventory covers all pad/group RGB channels and every lighted button',async()=>{const tests=ledInventory(p);assert.equal(tests.filter(t=>t.kind==='pad').length,48);assert.equal(tests.filter(t=>t.name.startsWith('GROUP')).length,24);const d=device(),t=tests.find(t=>t.name==='PAD 1'&&t.color==='red');await showLed(p,[d],t);assert.equal(d.writes.length,4);const last=d.writes.at(-1);assert.equal(last.id,0x80);assert.equal(last.data.filter(Boolean).length,1);assert.equal(last.data[t.offset-1],60);const group=tests.find(t=>t.name==='GROUP A'&&t.color==='blue');await showLed(p,[d],group);assert.equal(d.writes.at(-1).data.filter(Boolean).length,2);});
test('LED output requires exact model and descriptor framing; unknown IDs are rejected',async()=>{const d=device();d.device.productId=0x1300;await assert.rejects(showLed(p,[d],p.led_tests[0]));await assert.rejects(showLed(p,[device()],{id:'arbitrary'}));});
test('LED observations survive browser export and cannot claim confirmation without output',()=>{const t=p.led_tests[0],r={id:t.id,status:'confirmed',observed:t.name,color:'white',sent:true};const clean=sanitizeLeds([r],p);assert.equal(clean[0].bank,t.bank);assert.equal(ledCoverage({demo:false,leds:clean},p).confirmed,1);assert.throws(()=>sanitizeLeds([{...r,sent:false}],p));assert.throws(()=>sanitizeLeds([r,r],p));const report={format:'Machinista-controller-survey',version:2,checklist_version:3,keyboard_test:'quick',profile_id:p.id,demo:false,layout_audited:false,device:{vendor_id:0x17cc,product_id:0x1140,interfaces:[{id:'hid0'}]},controls:[],leds:clean};assert.equal(validateReport(report,profiles).leds[0].id,t.id);});

test('JAM tests every declared LED byte using the descriptor payload lengths',async()=>{
 const jam=profiles.maschine_jam;
 const sizes=[[128,53],[129,80],[130,88]];
 const writes=[];
 const d={device:{vendorId:0x17cc,productId:0x1500,collections:[{outputReports:sizes.map(([reportId,reportCount])=>({
  reportId,items:[{reportSize:8,reportCount}],
 }))}],sendReport:async(id,data)=>writes.push({id,data})}};
 const tests=ledInventory(jam);
 assert.equal(tests.length,221);
 for(const t of tests){
  await showLed(jam,[d],t);
  const {id,data}=writes.at(-1);
  assert.equal(id,t.bank);
  assert.equal(data.length,sizes.find(([bank])=>bank===id)[1]);
  assert.equal(data.filter(Boolean).length,1);
  assert.equal(data[t.offset-1],t.value);
 }
 assert.equal(tests.filter(t=>t.name.startsWith('SMART STRIP')).length,88);
 assert.deepEqual(sanitizeLeds([{id:'led_80_65_observe',status:'blocked',sent:false}],jam),[]);
});

test('JAM accepts padded Windows LED reports and can test a bank when another is unavailable',async()=>{
 const jam=profiles.maschine_jam,writes=[];
 const d={device:{vendorId:0x17cc,productId:0x1500,collections:[{children:[{
  outputReports:[{reportId:0x80,items:[{reportSize:8,reportCount:65}]}],
 }]}],sendReport:async(id,data)=>writes.push({id,data})}};
 await showLed(jam,[d],jam.led_tests[0]);
 assert.equal(writes.at(-1).data.length,65);
 assert.equal(writes.at(-1).data[0],60);
 const rgb=jam.led_tests.find(t=>t.bank===0x81);
 await assert.rejects(showLed(jam,[d],rgb),/Browser advertises: 0x80\/65/);
});

test('JAM sends all three LED banks with the Windows 88-byte descriptor',async()=>{
 const jam=profiles.maschine_jam,writes=[];
 const d={device:{vendorId:0x17cc,productId:0x1500,collections:[{
  outputReports:[0x80,0x81,0x82,0xf4].map(reportId=>({
   reportId,items:[{reportSize:8,reportCount:88}],
  })),
 }],sendReport:async(id,data)=>writes.push({id,data})}};
 for(const bank of [0x80,0x81,0x82]){
  const led=jam.led_tests.find(t=>t.bank===bank);
  await showLed(jam,[d],led);
  const {id,data}=writes.at(-1);
  assert.equal(id,bank);
  assert.equal(data[led.offset-1],led.value);
  assert.equal(data.filter(Boolean).length,1);
 }
 assert.deepEqual([...new Set(writes.map(w=>w.id))],[0x80,0x81,0x82]);
 assert.ok(writes.every(w=>w.data.length===88));
});
