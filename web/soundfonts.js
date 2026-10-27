'use strict';
let sfData={files:[],job:{state:'IDLE'}},sfPreview=null,sfSequence=-1,sfBusy=false,sfPolling=false,sfSeenDone=-1;
const sfError=e=>{$('soundfont-error').textContent=e.message||String(e)};
function sfReset(){sfPreview=null;$('soundfont-review').hidden=true;$('soundfont-accept').checked=false;$('soundfont-error').textContent='';sfButtons()}
function sfFiles(){
 const previous=$('soundfont-font').value;$('soundfont-font').replaceChildren(...sfData.files.map(f=>new Option(f.name+' · '+f.presets.length+(f.presets.length===1?' instrument':' instruments'),f.id)));
 if(sfData.files.some(f=>f.id===previous))$('soundfont-font').value=previous;
 sfPresets();
}
function sfPresets(){const f=sfData.files.find(f=>f.id===$('soundfont-font').value),previous=$('soundfont-preset').value;$('soundfont-preset').replaceChildren(...(f?.presets||[]).map(p=>new Option(p.name+' · Bank '+p.bank+' / Program '+(p.program+1),p.index)));if(f?.presets.some(p=>String(p.index)===previous))$('soundfont-preset').value=previous;sfButtons()}
function sfButtons(){
 const selected=Boolean($('soundfont-font').value);$('soundfont-file').disabled=sfBusy;$('soundfont-font').disabled=sfBusy;$('soundfont-preset').disabled=sfBusy;$('soundfont-inspect').disabled=sfBusy||!selected;$('soundfont-delete').disabled=sfBusy||!selected;
 $('soundfont-import').disabled=sfBusy||!sfPreview||sfPreview.blockers.length>0||!$('soundfont-accept').checked||!$('soundfont-name').value.trim();
}
async function sfLoad(){
 if(sfPolling)return;sfPolling=true;
 try{
  const data=await api('/api/soundfonts'),job=data.job;const old=JSON.stringify(sfData.files);sfData=data;sfBusy=data.busy;
  if(old!==JSON.stringify(data.files))sfFiles();
  $('soundfont-status').textContent=job.message||({UPLOADING:'Uploading…',PARSING:'Reading SoundFont…',ANALYZING:'Inspecting instrument…',IMPORTING:'Copying samples into a native Sound…'}[job.state]||'');
  if(job.state==='READY'&&sfSequence!==job.sequence){sfSequence=job.sequence;$('soundfont-font').value=job.font;sfPresets();sfReset()}
  if(job.state==='REVIEW'&&sfSequence!==job.sequence){
   sfSequence=job.sequence;sfPreview=job.preview;$('soundfont-review').hidden=false;$('soundfont-accept').checked=false;
   $('soundfont-instrument').textContent=sfPreview.preset.name;$('soundfont-summary').textContent=sfPreview.zone_count+(sfPreview.zone_count===1?' sample zone':' sample zones')+' · Native sampler';$('soundfont-notes').replaceChildren(...sfPreview.warnings.map(w=>element('li',w)));$('soundfont-blockers').textContent=sfPreview.blockers.join(' ');$('soundfont-name').value=sfPreview.preset.name.replace(/[\/\\\x00-\x1f]/g,'-').replace(/^\.+/,'').slice(0,80)||'Imported Sound';
  }
  if(job.state==='ERROR')$('soundfont-error').textContent=job.message;
  if(job.state==='DONE'&&sfSeenDone!==job.sequence){sfSeenDone=job.sequence;sfReset();soundMessage(job.message);await soundsLoad()}
  sfButtons();
 }catch(e){sfError(e)}finally{sfPolling=false}
}
async function sfAction(path,value){$('soundfont-error').textContent='';sfBusy=true;sfButtons();try{await soundPost('/api/soundfonts/'+path,value);await sfLoad()}catch(e){sfBusy=false;sfButtons();sfError(e)}}
$('soundfont-open').onclick=async()=>{sfReset();$('soundfont-dialog').showModal();await sfLoad()};
$('soundfont-close').onclick=()=>$('soundfont-dialog').close();
$('soundfont-font').onchange=()=>{sfReset();sfPresets()};$('soundfont-preset').onchange=sfReset;
$('soundfont-file').onchange=async()=>{
 const file=$('soundfont-file').files[0];if(!file)return;sfReset();sfBusy=true;sfButtons();$('soundfont-status').textContent='Uploading '+file.name+'…';
 try{await api('/api/soundfonts/upload?'+new URLSearchParams({name:file.name}),{method:'POST',headers:{'X-Machinista-Token':token},body:file});await sfLoad()}catch(e){sfError(e);sfBusy=false;sfButtons()}finally{$('soundfont-file').value=''}
};
$('soundfont-inspect').onclick=()=>{sfReset();sfAction('inspect',{font:$('soundfont-font').value,preset:Number($('soundfont-preset').value)})};
$('soundfont-import').onclick=()=>sfAction('import',{font:$('soundfont-font').value,preset:Number($('soundfont-preset').value),name:$('soundfont-name').value,folder:$('soundfont-folder').value,tags:soundTags($('soundfont-tags').value),accept_warnings:$('soundfont-accept').checked});
$('soundfont-delete').onclick=()=>{if(confirm('Remove this SoundFont upload? Imported Sounds keep their samples.')){sfReset();sfAction('delete',{font:$('soundfont-font').value})}};
$('soundfont-name').oninput=sfButtons;$('soundfont-accept').onchange=sfButtons;
setInterval(()=>{if($('soundfont-dialog').open&&!document.hidden)sfLoad()},1200);
