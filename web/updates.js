/* The privileged broker owns version, channel and update job state. */
let updateState=null,updateBusy=false,updateChoice=null;
function showUpdate(s){
 updateState=s;$('updates').hidden=!s.enabled;if(!s.enabled)return;
 $('update-current').textContent=s.current||'—';$('update-latest').textContent=s.latest||(s.state==='NO RELEASE'?'No release published yet':'Not checked');$('update-channel').value=s.channel||'release';
 $('update-status').textContent=s.error||(!s.configured?'Update source not configured':s.state==='COMPLETE'?'Update complete':s.state);
 $('update-notes').textContent=s.notes||'';$('update-progress').hidden=!s.busy;$('update-progress').value=s.progress||0;
 $('update-channel').disabled=Boolean(s.busy||updateBusy);$('update-check').disabled=Boolean(s.busy||updateBusy||!s.configured);$('update-install').disabled=Boolean(s.busy||updateBusy||!s.available||!s.configured);$('update-reboot').hidden=!s.reboot_required;
 if(s.busy){$('power-reboot').disabled=true;$('power-shutdown').disabled=true}else if(!powerPending){$('power-reboot').disabled=false;$('power-shutdown').disabled=false}
}
async function updateStatus(){if(updateBusy||document.hidden)return;try{const s=await api('/api/update');if(s.state==='COMPLETE'&&updateState?.state!=='COMPLETE')token=(await api('/api/session')).token;showUpdate(s)}catch{if(updateState?.enabled)$('update-status').textContent='Update service unavailable'}}
async function updateCommand(value){if(updateBusy)return;updateBusy=true;try{const s=await api('/api/update?'+new URLSearchParams(value),{method:'POST',headers:{'X-Machinista-Token':token}});updateBusy=false;showUpdate(s)}catch(e){updateBusy=false;$('update-status').textContent=e.message;$('update-channel').value=updateState?.channel||'release'}finally{updateBusy=false}}
$('update-channel').onchange=()=>updateCommand({op:'channel',channel:$('update-channel').value});
$('update-check').onclick=()=>updateCommand({op:'check'});
$('update-install').onclick=()=>{if(!updateState?.available||updateState.busy)return;updateChoice={op:'install',channel:updateState.channel,expected:updateState.latest};$('update-dialog-version').textContent=updateState.current+' → '+updateState.latest+' / '+updateState.channel;$('update-dialog').showModal()};
$('update-cancel').onclick=()=>{$('update-dialog').close();updateChoice=null};
$('update-confirm').onclick=()=>{$('update-dialog').close();if(updateChoice)updateCommand(updateChoice);updateChoice=null};
updateStatus();setInterval(updateStatus,2000);
