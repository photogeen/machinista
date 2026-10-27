'use strict';
let vjData=null,vjBusy=false;
const VJ_URI='urn:machinista:ports:virtualjv';
function vjMessage(message,bad=false){$('vj-status').textContent=message;$('vj-status').style.color=bad?'var(--danger)':''}
function vjPrograms(){
 const bank=vjData?.banks.find(b=>b.id===Number($('vj-bank').value)),rhythm=Number($('vj-mode').value);
 $('vj-program').replaceChildren();
 const names=rhythm?Array.from({length:bank?.drums||0},(_,i)=>'Rhythm Set '+(i+1)):bank?.patches||[];
 names.forEach((name,i)=>$('vj-program').append(new Option(String(i+1).padStart(3,'0')+' · '+name,String(i))));
 $('vj-apply').disabled=vjBusy||!$('vj-slot').value||!names.length||vjData?.runtime?.playing||vjData?.runtime?.recording;
}
function vjSelection(){
 const slot=Number($('vj-slot').value),controls=vjData?.runtime?.plugins?.[slot]?.controls||{};
 $('vj-bank').value=String(controls.bank??0);$('vj-mode').value=String(controls.rhythm??0);vjPrograms();$('vj-program').value=String(controls.program??0);
}
async function vjRefresh(){
 try{
  const data=await api('/api/virtualjv');vjData=data;$('vj-panel').hidden=!data.installed;
  if($('vj-panel').hidden)return;
  $('vj-bank').replaceChildren(...data.banks.map(b=>new Option(b.name+' · '+b.patches.length+' patches',String(b.id))));
  $('vj-slot').replaceChildren(new Option('Load VirtualJV on the controller first',''));
  (data.runtime?.plugins||[]).forEach((p,i)=>{if(p.uri===VJ_URI)$('vj-slot').append(new Option('Slot '+(i+1)+' · '+data.runtime.name,String(i)))});
  if($('vj-slot').options.length>1)$('vj-slot').selectedIndex=1;
  vjSelection();$('vj-prepare').disabled=vjBusy||!data.available;
  $('vj-rom-list').replaceChildren(...data.uploads.map(r=>{
   const row=element('li',undefined,'lv2-bundle-footer'),remove=element('button','Delete ROM');remove.type='button';remove.disabled=vjBusy||data.runtime?.playing||data.runtime?.recording||data.runtime?.busy;
   remove.onclick=()=>vjDelete(r.name);row.append(element('span',r.name+' · '+bytes(r.bytes)),remove);return row;
  }));
  vjMessage(data.runtime?.playing||data.runtime?.recording?'Stop playback and recording before changing the patch.':!data.banks.length?'Upload the base ROM set and choose Prepare ROMs.':'Bank changes also work from the controller’s Bank and Patch parameters.');
 }catch(e){vjMessage(e.message,true)}
}
$('vj-bank').onchange=vjPrograms;$('vj-mode').onchange=vjPrograms;$('vj-slot').onchange=vjSelection;$('vj-refresh').onclick=vjRefresh;
$('tab-lv2').addEventListener('click',vjRefresh);
document.addEventListener('lv2-status',event=>{
 const installed=event.detail.bundles.some(b=>b.status==='OK'&&b.plugins.some(p=>p.uri===VJ_URI||p.uri===VJ_URI+'-multi'));
 if(!installed){$('vj-panel').hidden=true;vjData=null}
 else if($('vj-panel').hidden)vjRefresh();
});
$('vj-apply').onclick=async()=>{
 if(vjBusy||!vjData||!$('vj-slot').value)return;vjBusy=true;$('vj-apply').disabled=true;
 try{
  const c=vjData.runtime;
  await api('/api/sounds/command',{method:'POST',headers:{'Content-Type':'application/json','X-Machinista-Token':token},body:JSON.stringify({operation:'plugin_parameters',generation:c.generation,group:c.group,pad:c.pad,revision:c.revision,slot:Number($('vj-slot').value),uri:VJ_URI,controls:{bank:Number($('vj-bank').value),program:Number($('vj-program').value),rhythm:Number($('vj-mode').value)}})});
  vjMessage('Patch selected. Allow a moment for the instrument to prepare.');setTimeout(vjRefresh,600);
 }catch(e){vjMessage(e.message,true)}finally{vjBusy=false;$('vj-apply').disabled=false}
};
$('vj-roms').onchange=async()=>{
 if(vjBusy)return;vjBusy=true;$('vj-roms').disabled=true;
 try{
  for(const file of $('vj-roms').files){$('vj-upload-status').textContent='Uploading '+file.name+'…';await api('/api/virtualjv/upload?'+new URLSearchParams({name:file.name}),{method:'POST',headers:{'X-Machinista-Token':token,'Content-Type':'application/octet-stream'},body:file})}
  $('vj-upload-status').textContent='ROMs saved. Choose Prepare ROMs to check and import them.';await vjRefresh();
 }catch(e){$('vj-upload-status').textContent=e.message}finally{vjBusy=false;$('vj-roms').disabled=false;$('vj-roms').value=''}
};
$('vj-prepare').onclick=async()=>{
 if(vjBusy)return;vjBusy=true;$('vj-prepare').disabled=true;$('vj-upload-status').textContent='Checking and preparing your ROMs…';
 try{const result=await api('/api/virtualjv/prepare',{method:'POST',headers:{'X-Machinista-Token':token}});$('vj-upload-status').textContent=result.message;await vjRefresh()}
 catch(e){$('vj-upload-status').textContent=e.message}finally{vjBusy=false;$('vj-prepare').disabled=false}
};

async function vjDelete(name){
 if(vjBusy||!confirm('Delete '+name+' from this Pi? Remaining banks will be rebuilt. Deleting a required base ROM makes VirtualJV unavailable until its base ROM set is restored.'))return;
 vjBusy=true;$('vj-roms').disabled=true;$('vj-prepare').disabled=true;
 try{const result=await api('/api/virtualjv/delete?'+new URLSearchParams({name}),{method:'POST',headers:{'X-Machinista-Token':token}});$('vj-upload-status').textContent=result.message}
 catch(e){$('vj-upload-status').textContent=e.message}
 finally{vjBusy=false;$('vj-roms').disabled=false;await vjRefresh()}
}
