const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const elements=new Map(),listeners=new Map(),calls=[];
function element(){return {hidden:true,value:'',options:[],style:{},addEventListener(){},replaceChildren(...v){this.options=v},append(v){this.options.push(v)}}}
let data={installed:false,available:true,banks:[{id:0,patches:['Old']}],uploads:[],runtime:{}};
const context=vm.createContext({$:id=>{if(!elements.has(id))elements.set(id,element());return elements.get(id)},document:{addEventListener:(name,fn)=>listeners.set(name,fn)},api:async(url,options)=>{calls.push({url,options});return url.startsWith('/api/virtualjv/delete')?{ok:true,message:'ROM deleted.'}:data},confirm:()=>true,token:'test-token',Option:function(label,value){this.label=label;this.value=value},element,bytes:String,URLSearchParams,setTimeout});
vm.runInContext(fs.readFileSync('web/virtualjv.js','utf8'),context);
(async()=>{
 await vm.runInContext('vjRefresh()',context);assert.equal(elements.get('vj-panel').hidden,true);
 data={installed:true,available:false,banks:[],uploads:[],runtime:{}};
 await vm.runInContext('vjRefresh()',context);assert.equal(elements.get('vj-panel').hidden,false);
 listeners.get('lv2-status')({detail:{bundles:[]}});assert.equal(elements.get('vj-panel').hidden,true);
 listeners.get('lv2-status')({detail:{bundles:[{status:'OK',plugins:[{uri:'urn:machinista:ports:virtualjv-multi'}]}]}});
 await new Promise(resolve=>setImmediate(resolve));assert.equal(elements.get('vj-panel').hidden,false);
 listeners.get('lv2-status')({detail:{bundles:[{status:'NOT OK',plugins:[{uri:'urn:machinista:ports:virtualjv'}]}]}});assert.equal(elements.get('vj-panel').hidden,true);
 await vm.runInContext("vjDelete('Expansion & Keys.bin')",context);
 const deletion=calls.find(c=>c.url.startsWith('/api/virtualjv/delete'));assert.equal(deletion.options.method,'POST');assert.equal(deletion.options.headers['X-Machinista-Token'],'test-token');assert.match(deletion.url,/Expansion\+%26\+Keys.bin/);
 assert.match(fs.readFileSync('web/app.js','utf8'),/dispatchEvent\(new CustomEvent\('lv2-status'/);
 console.log('VirtualJV visibility: retained banks hidden, installation shown, removal/reinstallation refreshed.');
})().catch(error=>{console.error(error);process.exitCode=1});
