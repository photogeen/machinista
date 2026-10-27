'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const nodes=new Map(),context={console,setInterval(){},$(id){if(!nodes.has(id))nodes.set(id,{});return nodes.get(id)}};
vm.createContext(context);vm.runInContext(fs.readFileSync(path.join(__dirname,'../web/sounds.js'),'utf8'),context);
const parse=context.soundFilenameRoot,name=context.soundNoteName;
for(const [file,expected] of [
 ['Rhodes A2.WAV',57],['Rhodes A4.WAV',81],['Rhodes B1.WAV',47],['Rhodes B3.WAV',71],['Rhodes B5.WAV',95],['Rhodes C3.WAV',60],['Rhodes C5.WAV',84],['Rhodes D2.WAV',50],['Rhodes D4.WAV',74],
 ['Piano_F#3_v127.wav',66],['Piano_Gb3_R.wav',66],['EP [Bb2] vel80.WAV',58],['EP (a#2).wav',58],['EP_D♭4.wav',73],['EP_F♯3.wav',66],['C-2.wav',0],['G8.wav',127],['B#2.wav',60],['Cb3.wav',59],['/library/Keys/Piano_C3.wav',60],['C:\\Keys\\Piano_C3.wav',60],
 ['Kick60.wav',null],['Kick 01.wav',null],['Sample01.wav',null],['AB3.wav',68],['Bass3.wav',null],['Bass_C3lead.wav',null],['Pad C9.wav',null],['Pad G#8.wav',null],['C3-D3.wav',null],['C3_C3.wav',60],['Piano_C30.wav',null],['Piano_C-3.wav',null],['Pad B3 A2.wav',null]
])assert.equal(parse(file),expected,file);
assert.equal(parse('Rhodes A2.WAV',1),45);assert.equal(parse('Piano C4.wav',1),60);
for(const n of [0,12,60,69,127])assert.equal(parse(name(n)+'.wav'),n);
assert.equal(name(60),'C3');assert.equal(name(0),'C-2');assert.equal(name(127),'G8');
const rows=[{label:'Rhodes A2.WAV',root:60,key_lo:11,key_hi:72,vel_lo:24,vel_hi:100},{label:'Kick 01.wav',root:36},{label:'C3-D3.wav',root:41}];
assert.equal(context.zoneRootsFromFilenames(rows),1);assert.equal(rows[0].root,57);assert.equal(rows[0].key_lo,11);assert.equal(rows[0].key_hi,72);assert.equal(rows[0].vel_lo,24);assert.equal(rows[1].root,36);assert.equal(rows[2].root,41);
// Render uses note names but the selected values stay MIDI numbers for persistence.
context.element=()=>({options:[],setAttribute(k,v){this[k]=v},append(v){this.options.push(v)}});
context.Option=function(text,value){this.text=text;this.value=value};
const select=context.zoneNoteSelect(60,'Root');assert.equal(select.options.length,128);assert.equal(select.options[60].text,'C3');assert.equal(select.options[60].value,'60');assert.equal(select.value,'60');
console.log('Sound note parsing, octave conventions, conservative bulk detection and all 128 note choices: OK');
