/* ASMAN Rahbar Premium — management layer.
 * Brings the working actions of the classic Rahbar app into the Premium design:
 * Ombor (orders, catalog, products missing from the catalog), agent management
 * (profile, period routes, permissions, add/rename/transfer/block) and client
 * actions (edit, delete, act sverka export). Uses the same /api/manager actions.
 */
(function(){
'use strict';
var P=window.PremiumReal;if(!P)return;
var tg=window.Telegram&&window.Telegram.WebApp;
function $(id){return document.getElementById(id)}
function esc(v){return String(v==null?'':v).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]})}
function usd(v){return Number(v||0).toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2})}
function when(ts){if(!ts)return '—';try{return new Date(Number(ts)*1000).toLocaleString('uz-UZ',{timeZone:'Asia/Tashkent',day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'})}catch(e){return '—'}}
function dur(s){s=Math.max(0,Number(s||0));var h=Math.floor(s/3600),m=Math.floor(s%3600/60);return h+'s '+String(m).padStart(2,'0')+'d'}
function say(m){if(typeof window.toast==='function')window.toast(m)}
var primaryAdmin=false,wh=null,whTab='orders',whFilter='open',pending=null,periodMap=null,editPreview=null;
async function api(action,arg){var r=await P.req(action,arg);if(r&&typeof r.primaryAdmin==='boolean')primaryAdmin=r.primaryAdmin;return r}

/* ---------- styles ---------- */
var css=document.createElement('style');css.textContent=
'.pm-tap{cursor:pointer}.pm-tap:active{transform:scale(.985)}.pm-rk{display:grid;grid-template-columns:34px 1fr auto;gap:10px;align-items:center;padding:12px 0;border-top:1px solid var(--line);animation:up .45s cubic-bezier(.2,.9,.3,1) both}.pm-rk:first-child{border-top:0}.pm-rk .n{width:34px;height:34px;border-radius:11px;display:grid;place-items:center;font-weight:800;color:#fff;background:linear-gradient(160deg,#ffffff4d,#fff0 60%),var(--q,#2a8bf2);box-shadow:0 8px 14px -8px var(--q,#2a8bf2)}.pm-rk b{font-size:14px;display:block}.pm-rk small{display:block;color:var(--mu);font-size:12px;margin-top:3px}.pm-rk .v{text-align:right;font-weight:800;font-size:14px}.pm-rk .v small{font-weight:600}.pm-rk .tr{grid-column:2/4;height:6px;border-radius:6px;background:var(--soft);overflow:hidden}.pm-rk .tr i{display:block;height:100%;border-radius:6px;background:linear-gradient(90deg,#6bb4ff,#2a8bf2 45%,#1f6fd1);transform-origin:left;animation:pmgx .8s cubic-bezier(.2,.9,.3,1) both}@keyframes pmgx{from{transform:scaleX(0)}}'+
'.pm-h{display:flex;align-items:center;justify-content:space-between;gap:10px;margin:0 0 12px}.pm-h b{font-size:18px}.pm-h small{display:block;color:var(--mu);font-size:12px;margin-top:2px}'+
'.pm-grab{width:44px;height:5px;border-radius:5px;background:var(--line);margin:0 auto 14px}'+
'.pm-tabs{display:flex;gap:6px;overflow-x:auto;margin:0 0 12px;padding-bottom:2px}.pm-tabs button{flex:none;border:1px solid var(--line);background:var(--card);color:var(--tx);border-radius:20px;padding:8px 12px;font-size:12.5px;font-weight:600;cursor:pointer}.pm-tabs button.on{background:var(--pri);border-color:var(--pri);color:#fff}'+
'.pm-chips{display:flex;gap:5px;overflow-x:auto;margin:0 0 10px}.pm-chips button{flex:none;border:1px solid var(--line);background:var(--soft);color:var(--tx);border-radius:14px;padding:6px 10px;font-size:11.5px;font-weight:600;cursor:pointer}.pm-chips button.on{background:var(--tx);color:var(--card);border-color:var(--tx)}'+
'.pm-card{background:var(--card);border:1px solid var(--line);border-radius:18px;padding:13px;margin-bottom:10px;box-shadow:0 4px 14px #0a1f5a0d}.pm-card small{display:block;color:var(--mu);font-size:11.5px;margin-top:3px;line-height:1.45}'+
'.pm-top{display:flex;justify-content:space-between;align-items:flex-start;gap:8px}.pm-top b{font-size:14px}'+
'.pm-items{list-style:none;margin:8px 0 0;padding:0;font-size:13px}.pm-items li{display:flex;justify-content:space-between;gap:8px;padding:6px 0;border-top:1px dashed var(--line)}.pm-items li:first-child{border-top:0}.pm-items li.cu{color:var(--warn);font-weight:700}'+
'.pm-act{display:grid;grid-template-columns:1fr 1fr;gap:7px;margin-top:10px}.pm-act .w{grid-column:1/-1}'+
'.pm-b{border:1px solid var(--line);background:var(--soft);color:var(--pri);border-radius:13px;padding:11px 8px;font-size:12.5px;font-weight:700;text-align:center;cursor:pointer}.pm-b.p{background:var(--pri);border-color:var(--pri);color:#fff}.pm-b.r{background:#fff0f3;border-color:#ffd2db;color:var(--bad)}.pm-b[disabled]{opacity:.5;pointer-events:none}'+
'.pm-row{display:flex;justify-content:space-between;align-items:center;gap:8px;padding:10px 0;border-top:1px solid var(--line)}.pm-row:first-child{border-top:0}.pm-row b{font-size:13px}.pm-row.off{opacity:.55}'+
'.pm-tag{font-size:10px;font-weight:800;border-radius:20px;padding:3px 8px;background:var(--soft);color:var(--pri);white-space:nowrap}.pm-tag.new{background:#e9f0ff;color:#1f6bff}.pm-tag.preparing,.pm-tag.cu{background:#fff4e0;color:#b26a00}.pm-tag.loaded,.pm-tag.ok{background:#e4f8ee;color:#087b51}.pm-tag.rejected,.pm-tag.bad{background:#ffe9ed;color:#c8334d}.pm-tag.off{background:#eef1f5;color:#8a96a8}'+
'.pm-f label{display:block;font-size:12px;color:var(--mu);font-weight:600;margin:10px 0 0}.pm-f input,.pm-f textarea,.pm-f select{display:block;width:100%;box-sizing:border-box;margin-top:5px;border:1px solid var(--line);background:var(--soft);color:var(--tx);border-radius:12px;padding:11px 12px;font-size:14px;font-family:inherit;outline:0}.pm-f textarea{min-height:70px;resize:vertical}.pm-f input:focus,.pm-f textarea:focus{border-color:var(--pri)}'+
'.pm-note{background:var(--soft);color:var(--mu);border-radius:12px;padding:10px 12px;font-size:12px;line-height:1.5;margin:10px 0}'+
'.pm-kpis{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin:12px 0}.pm-kpis div{background:var(--soft);border-radius:14px;padding:10px}.pm-kpis small{display:block;color:var(--mu);font-size:11px}.pm-kpis b{display:block;font-size:16px;margin-top:3px}'+
'.pm-per{display:grid;grid-template-columns:repeat(3,1fr);gap:7px}.pm-per button{border:1px solid var(--line);background:var(--card);color:var(--tx);border-radius:14px;padding:9px 7px;text-align:left;font-size:11px;line-height:1.5;cursor:pointer}.pm-per button b{display:block;font-size:12.5px;color:var(--pri)}'+
'.pm-sw{display:flex;justify-content:space-between;align-items:center;gap:10px;width:100%;border:0;background:none;color:var(--tx);padding:10px 0;border-top:1px solid var(--line);text-align:left;cursor:pointer}.pm-sw:first-of-type{border-top:0}.pm-sw i{font-style:normal;font-size:11px;font-weight:800;border-radius:20px;padding:4px 10px;background:#e4f8ee;color:#087b51}.pm-sw.off i{background:#eef1f5;color:#8a96a8}'+
'.pm-hero{display:flex;gap:12px;align-items:center;margin-bottom:6px}.pm-av{width:54px;height:54px;border-radius:18px;overflow:hidden;display:grid;place-items:center;font-weight:800;font-size:20px;color:#fff;background:linear-gradient(135deg,#2f7bff,#0b3fae);flex:none}.pm-hero b{font-size:18px}'+
'#pm-map{height:260px;border-radius:16px;overflow:hidden;margin:10px 0;background:var(--soft)}'+
'.pm-entry{display:flex;align-items:center;gap:12px;cursor:pointer}.pm-entry .ic{width:44px;height:44px;border-radius:14px;display:grid;place-items:center;font-size:22px;background:var(--soft);flex:none}.pm-entry b{font-size:15px}.pm-entry small{display:block;color:var(--mu);font-size:12px;margin-top:2px}.pm-entry em{margin-left:auto;font-style:normal;font-weight:800;color:var(--pri)}'+
'.pm-badge{display:inline-block;min-width:20px;padding:2px 7px;border-radius:12px;background:var(--bad);color:#fff;font-size:11px;font-weight:800;text-align:center;margin-left:6px}'+
'.pm-cphoto{width:56px;height:56px;border-radius:16px;object-fit:cover;flex:none;cursor:zoom-in;background:var(--soft)}.pm-vphoto{width:52px;height:52px;border-radius:12px;object-fit:cover;cursor:zoom-in;background:var(--soft)}'+
'#pm-photo{position:fixed;inset:0;z-index:9999;background:#000d;display:flex;align-items:center;justify-content:center;padding:16px}#pm-photo img{max-width:100%;max-height:100%;border-radius:14px}'+
'.pm-pock{display:grid;grid-template-columns:repeat(3,1fr);gap:7px}.pm-pock div{background:var(--soft);border-radius:14px;padding:10px 9px;min-width:0}.pm-pock small{display:block;color:var(--mu);font-size:10.5px}.pm-pock b{display:block;font-size:16px;margin-top:4px;overflow-wrap:anywhere}.pm-pock em{display:block;font-style:normal;color:var(--mu);font-size:10.5px}'+
'.pm-cur3{display:grid;grid-template-columns:auto 1fr 1fr 1fr;gap:6px 8px;font-size:12.5px;align-items:center}.pm-cur3 b{text-align:right}.pm-cur3 small{text-align:right;color:var(--mu);font-size:10.5px}.pm-pos{color:var(--ok)}.pm-neg{color:var(--bad)}.pm-off{opacity:.6}'+
'.three>.c.kp{flex-direction:column;align-items:flex-start;gap:8px;padding:12px 10px;min-width:0}.three>.c.kp>div:last-child{min-width:0;width:100%}.three>.c.kp>:first-child:not(:last-child){width:38px!important;height:38px!important;min-width:38px;flex:none;font-size:17px}.three>.c.kp b{font-size:17px!important;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;letter-spacing:-.3px}.three>.c.kp small,.three>.c.kp em{white-space:nowrap}'+
'.pm-lphoto{width:100%;height:100%;object-fit:cover;border-radius:inherit;display:block}.av.pm-hasph{padding:0;overflow:hidden;cursor:zoom-in}.pm-open{display:block;margin-top:8px;color:var(--mu);font-size:11.5px}'+
'.pm-chg{display:grid;grid-template-columns:1fr;gap:3px;padding:9px 0;border-top:1px solid var(--line);font-size:13px}.pm-chg span{color:var(--mu);text-decoration:line-through}.pm-chg strong{color:var(--ok)}';
document.head.appendChild(css);

/* ---------- sheet ---------- */
function sheet(title,body,sub){
 if(periodMap){try{periodMap.remove()}catch(e){}periodMap=null}
 var sh=$('sh'),ov=$('ov');if(!sh)return;
 sh.innerHTML='<div class="pm-grab"></div><div class="pm-h"><div><b>'+title+'</b>'+(sub?'<small>'+sub+'</small>':'')+'</div><div class="pm-b" data-pm="close" style="padding:8px 12px">✕</div></div>'+body;
 sh.classList.add('on');if(ov)ov.classList.add('on');if(tg&&tg.BackButton)tg.BackButton.show();sh.scrollTop=0;
}
function loading(title){sheet(title,'<div class="pm-note" style="text-align:center">Yuklanmoqda…</div>')}
function confirmBox(title,html,action,payload){
 pending={action:action,payload:payload};
 sheet(title,'<div class="pm-card">'+html+'</div><div class="pm-act"><div class="pm-b p" data-pm="confirm">✅ Tasdiqlash</div><div class="pm-b" data-pm="close">Bekor qilish</div></div>');
}
async function runPending(btn){
 if(!pending)return;var p=pending;pending=null;if(btn)btn.setAttribute('disabled','');
 try{var r=await api(p.action,Object.assign({},p.payload,{confirm:true}));say('✅ Saqlandi');await P.reload(true);
  if(r&&r.agent&&r.agent.id)renderAgent(r.agent);else if(p.after)p.after(r);else agentManagement();
 }catch(e){say('⚠️ '+(e.message||'Saqlanmadi'));if(btn)btn.removeAttribute('disabled')}
}

/* ---------- download ---------- */
function download(f){
 var raw=atob(f.base64),bytes=new Uint8Array(raw.length);for(var i=0;i<raw.length;i++)bytes[i]=raw.charCodeAt(i);
 var url=URL.createObjectURL(new Blob([bytes],{type:f.mime||'application/octet-stream'})),a=document.createElement('a');
 a.href=url;a.download=f.filename||'ASMAN.dat';a.target='_blank';document.body.appendChild(a);a.click();a.remove();setTimeout(function(){URL.revokeObjectURL(url)},60000);
}
async function exportFile(action,arg,label){
 say('⏳ '+label+' tayyorlanmoqda…');
 try{download(await api(action,arg));say('✅ '+label+' tayyor')}catch(e){say('⚠️ '+(e.message||'Fayl tayyorlanmadi'))}
}

/* =================== OMBOR =================== */
function whStatusTag(o){return '<span class="pm-tag '+esc(o.status)+'">'+esc(o.statusLabel)+'</span>'}
function whOrder(o){
 var items=o.items.map(function(i){return '<li class="'+(i.custom?'cu':'')+'"><span>'+esc(i.name)+(i.custom?' ⚠️':'')+'</span><b>'+i.qty+' dona</b></li>'}).join('');
 var a=[];
 if(o.status==='new')a.push('<div class="pm-b" data-pm="wh-status" data-to="preparing" data-id="'+o.id+'">📦 Tayyorlashga</div>');
 if(o.status==='new'||o.status==='preparing')a.push('<div class="pm-b p" data-pm="wh-status" data-to="loaded" data-id="'+o.id+'">🚚 Agentga berish</div>','<div class="pm-b r w" data-pm="wh-reject" data-id="'+o.id+'">❌ Rad etish</div>');
 if(o.status==='loaded')a.push('<div class="pm-b w" data-pm="wh-status" data-to="delivered" data-id="'+o.id+'">✅ Yetkazildi deb belgilash</div>');
 if(o.status==='rejected')a.push('<div class="pm-b w" data-pm="wh-status" data-to="new" data-id="'+o.id+'">↺ Qayta ochish</div>');
 return '<div class="pm-card"><div class="pm-top"><div><b>#'+o.id+' · '+esc(o.clientName)+'</b><small>'+esc(o.agentName)+' · '+when(o.ts)+(o.totalCents?' · '+usd(o.totalCents/100)+' $':'')+'</small></div>'+whStatusTag(o)+'</div>'+
  '<ul class="pm-items">'+items+'</ul>'+(o.note?'<small>📝 '+esc(o.note)+'</small>':'')+(o.adminNote?'<small>Rahbar: '+esc(o.adminNote)+'</small>':'')+
  (o.unmapped&&o.status!=='rejected'?'<small style="color:var(--warn)">⚠️ '+o.unmapped+' ta mahsulot katalogda yo‘q — «Katalogda yo‘q» bo‘limida qo‘shing yoki bog‘lang.</small>':'')+
  (a.length?'<div class="pm-act">'+a.join('')+'</div>':'')+'</div>';
}
function renderWarehouse(){
 if(!wh)return;var c=wh.counts||{},open=(c.new||0)+(c.preparing||0)+(c.loaded||0);
 var body='<div class="pm-tabs">'+[['orders','🛒 Buyurtmalar · '+open],['catalog','📋 Katalog · '+(wh.catalog||[]).length],['missing','⚠️ Katalogda yo‘q · '+(wh.demand||[]).length]].map(function(t){return '<button data-pm="wh-tab" data-tab="'+t[0]+'" class="'+(whTab===t[0]?'on':'')+'">'+t[1]+'</button>'}).join('')+'</div>';
 if(whTab==='orders'){
  body+='<div class="pm-chips">'+[['open','Ochiq'],['new','Yangi · '+(c.new||0)],['preparing','Tayyorlanmoqda · '+(c.preparing||0)],['loaded','Agentda · '+(c.loaded||0)],['delivered','Yetkazildi'],['rejected','Rad etildi']].map(function(x){return '<button data-pm="wh-filter" data-f="'+x[0]+'" class="'+(whFilter===x[0]?'on':'')+'">'+x[1]+'</button>'}).join('')+'</div>';
  body+=(wh.orders||[]).map(whOrder).join('')||'<div class="pm-note" style="text-align:center">Bu holatda buyurtma yo‘q.</div>';
 }else if(whTab==='catalog'){
  body+='<div class="pm-b p" data-pm="wh-new" style="margin-bottom:10px">＋ Yangi mahsulot qo‘shish</div><div class="pm-card">'+
   (wh.catalog||[]).map(function(p){return '<div class="pm-row'+(p.active?'':' off')+'" data-pm="wh-edit" data-pack="'+p.pack+'" style="cursor:pointer"><div><b>'+esc(p.name)+'</b><small>'+(p.weightKg!=null?p.weightKg+' kg · ':'')+usd(p.priceUsd)+' $'+'</small></div><div style="display:flex;gap:5px;align-items:center">'+(p.custom?'<span class="pm-tag cu">yangi</span>':'')+(p.active?'':'<span class="pm-tag off">arxiv</span>')+'<b style="color:var(--pri)">✎</b></div></div>'}).join('')+'</div>'+
   '<div class="pm-note">Arxivdagi mahsulot agentlarga ko‘rinmaydi, lekin eski savdo va akt sverkalarda saqlanadi.</div>';
 }else{
  var d=wh.demand||[];
  body+=d.length?d.map(function(x,i){return '<div class="pm-card"><b>'+esc(x.name)+'</b><small>'+x.clients+' mijoz · '+x.agents+' agent · '+x.orders+' buyurtma · jami '+x.qty+' dona'+(x.variants.length>1?'<br>Yozilishi: '+x.variants.map(esc).join(' | '):'')+'</small><div class="pm-act"><div class="pm-b p" data-pm="wh-demand-add" data-i="'+i+'">＋ Katalogga qo‘shish</div><div class="pm-b" data-pm="wh-demand-map" data-i="'+i+'">🔗 Mavjudga bog‘lash</div></div></div>'}).join(''):'<div class="pm-note" style="text-align:center">Katalogda yo‘q mahsulot so‘ralmagan.</div>';
 }
 sheet('📦 Ombor',body,'Buyurtmalar, katalog va narxlar');
}
async function openWarehouse(){loading('📦 Ombor');try{wh=await api('warehouse',{status:whFilter});renderWarehouse()}catch(e){sheet('📦 Ombor','<div class="pm-note">'+esc(e.message||'Ombor yuklanmadi')+'</div>')}}
function productForm(p,mapName){
 var custom=!p||p.custom;
 sheet(p?'Mahsulotni tahrirlash':'Yangi mahsulot','<div class="pm-f">'+
  (custom?'<label>Mahsulot nomi<input id="pm-p-name" maxlength="120" value="'+esc(p?p.name:(mapName||''))+'" placeholder="Masalan: Emal PF-115 oq 2.7 kg"></label><label>Og‘irligi (kg)<input id="pm-p-weight" inputmode="decimal" value="'+esc(p&&p.weightKg!=null?p.weightKg:'')+'" placeholder="2.7"></label>':'<div class="pm-note"><b>'+esc(p.name)+'</b><br>Asosiy mahsulot — nomi va og‘irligi o‘zgarmaydi.</div>')+
  '<label>Narxi (USD, 1 dona)<input id="pm-p-price" inputmode="decimal" value="'+esc(p?p.priceUsd:'')+'" placeholder="4.50"></label>'+
  (p?'':'<label>Blokdagi dona (ixtiyoriy)<input id="pm-p-block" inputmode="numeric" placeholder="masalan 6"></label>')+
  (p?'<label style="display:flex;justify-content:space-between;align-items:center;gap:10px">Agentlarga ko‘rinadi (o‘chirilsa arxivga tushadi)<input id="pm-p-active" type="checkbox" style="width:auto;margin:0"'+(p.active?' checked':'')+'></label>':'')+
  (mapName?'<div class="pm-note">Saqlangach «'+esc(mapName)+'» deb yozilgan barcha ochiq buyurtmalar shu mahsulotga bog‘lanadi.</div>':'')+
  '</div><div class="pm-b p" style="margin-top:14px" data-pm="wh-save" data-pack="'+(p?p.pack:'new')+'"'+(mapName?' data-map="'+esc(mapName)+'"':'')+'>💾 Saqlash</div>');
}
async function saveProduct(b){
 b.setAttribute('disabled','');
 try{var r,isNew=b.dataset.pack==='new';
  if(isNew){r=await api('product_add',{confirm:true,name:$('pm-p-name').value,weightKg:$('pm-p-weight').value,priceUsd:$('pm-p-price').value,blockUnits:($('pm-p-block')||{}).value||0,mapName:b.dataset.map||'',status:whFilter});say('✅ Mahsulot qo‘shildi'+(r.mapped?' · '+r.mapped+' ta qator bog‘landi':''))}
  else{var arg={pack:Number(b.dataset.pack),priceUsd:$('pm-p-price').value,active:$('pm-p-active').checked,status:whFilter};if($('pm-p-name'))arg.name=$('pm-p-name').value;if($('pm-p-weight'))arg.weightKg=$('pm-p-weight').value;r=await api('product_update',arg);say('✅ Saqlandi')}
  wh=r.warehouse;whTab=b.dataset.map?'missing':'catalog';renderWarehouse();P.reload(true);
 }catch(e){say('⚠️ '+(e.message||'Saqlanmadi'));b.removeAttribute('disabled')}
}
function mapForm(i){
 var x=(wh.demand||[])[i];if(!x)return;
 sheet('Mavjud mahsulotga bog‘lash','<div class="pm-note">So‘ralgan: <b>'+esc(x.name)+'</b> · '+x.qty+' dona</div><div class="pm-f"><label>Katalogdagi mahsulot<select id="pm-map-pack">'+(wh.catalog||[]).filter(function(p){return p.active}).map(function(p){return '<option value="'+p.pack+'">'+esc(p.name)+'</option>'}).join('')+'</select></label></div><div class="pm-b p" style="margin-top:14px" data-pm="wh-map-save" data-i="'+i+'">🔗 Bog‘lash</div>');
}
async function mapSave(b){
 var x=(wh.demand||[])[Number(b.dataset.i)];if(!x)return;b.setAttribute('disabled','');
 try{var r=await api('custom_map',{name:x.name,pack:Number($('pm-map-pack').value),status:whFilter});wh=r.warehouse;say('✅ '+r.mapped+' ta qator bog‘landi');whTab='missing';renderWarehouse();P.reload(true)}
 catch(e){say('⚠️ '+(e.message||'Bog‘lab bo‘lmadi'));b.removeAttribute('disabled')}
}
async function setStatus(id,to,note,b){
 if(b)b.setAttribute('disabled','');
 try{var r=await api('order_status',{orderId:id,to:to,note:note||'',status:whFilter});wh=r.warehouse;say('✅ Buyurtma #'+id+': '+((wh.statusLabels||{})[to]||to));whTab='orders';renderWarehouse();P.reload(true)}
 catch(e){say('⚠️ '+(e.message||'Holat o‘zgarmadi'));if(b)b.removeAttribute('disabled')}
}

/* =================== AGENTS =================== */
var FEAT_ICON={client:'🏪',clients:'👥',delivery:'📦',order:'🛒',sold:'💵',payment:'💰',return:'↩️',visit:'📍',handover:'🏦',balance:'📊'};
function periodBtn(label,p,key,id){p=p||{};return '<button data-pm="ag-period" data-period="'+key+'" data-id="'+id+'"><b>'+label+'</b>📦 '+usd(p.deliveredUsd)+' $<br>💰 '+usd(p.paymentsUsd)+' $<br>✓ '+Number(p.visits||0)+' · ＋'+Number(p.newClients||0)+'<br>⌁ '+Number(p.distanceKm||0).toFixed(1)+' km</button>'}
function renderAgent(a){
 var live=a.shiftOpen?(a.lastGpsTs?'Smena ochiq · GPS '+when(a.lastGpsTs):'Smena ochiq · GPS yo‘q'):(a.lastGpsTs?'Smena yopiq · oxirgi GPS '+when(a.lastGpsTs):'Smena yopiq');
 var stock=(a.stocks||[]).filter(function(s){return s.qty}).map(function(s){return '<div class="pm-row"><span>'+esc(s.name)+'</span><b style="color:'+(s.qty<0?'var(--bad)':'var(--tx)')+'">'+s.qty+' dona</b></div>'}).join('');
 var feats=(a.features||[]).map(function(f){return '<button class="pm-sw'+(f.enabled?'':' off')+'" data-pm="ag-feature" data-id="'+a.id+'" data-key="'+esc(f.key)+'" data-on="'+(f.enabled?1:0)+'"'+(a.active?'':' disabled')+'><span>'+(FEAT_ICON[f.key]||'•')+' '+esc(f.label)+'</span><i>'+(f.enabled?'ON':'OFF')+'</i></button>'}).join('');
 var manage=a.active?'<div class="pm-act"><div class="pm-b" data-pm="ag-rename" data-id="'+a.id+'" data-name="'+esc(a.name)+'">✏️ Nomini o‘zgartirish</div>'+(primaryAdmin?'<div class="pm-b" data-pm="ag-transfer" data-id="'+a.id+'">🔁 Akkaunt almashtirish</div><div class="pm-b r w" data-pm="ag-block" data-id="'+a.id+'">⛔ Kirishni bloklash</div>':'')+'</div>'+(primaryAdmin?'':'<div class="pm-note">Akkaunt almashtirish va bloklash faqat asosiy rahbarga ruxsat.</div>'):'<div class="pm-note">Bu agent bloklangan. Tarix va hisob ma’lumotlari saqlangan.</div>';
 sheet('Agent profili','<div class="pm-hero"><div class="pm-av">'+(a.photoUrl?'<img alt="" src="'+esc((window.pmPhotoSrc&&window.pmPhotoSrc(a.photoUrl))||a.photoUrl)+'" style="width:100%;height:100%;object-fit:cover;border-radius:inherit" onclick="pmPhoto(this.src)" onerror="var t=this;if(!t._r){t._r=1;setTimeout(function(){t.src=t.src+(t.src.indexOf(\'?\')<0?\'?\':\'&\')+\'r=9\'},1500)}">':esc((a.name||'?')[0]))+'</div><div style="flex:1"><b>'+esc(a.name)+'</b><small style="display:block;color:var(--mu);font-size:12px">ID '+a.id+' · '+esc(live)+'</small></div><span class="pm-tag '+(a.active?'ok':'bad')+'">'+(a.active?'FAOL':'BLOK')+'</span></div>'+
  '<div class="pm-kpis"><div><small>Mijozlar</small><b>'+a.clients+'</b></div><div><small>Qo‘ldagi pul</small><b>'+usd(a.cashUsd)+' $</b></div><div><small>Tasdiq kutilmoqda</small><b>'+usd(a.pendingHandoverUsd)+' $</b></div><div><small>Oxirgi GPS</small><b style="font-size:13px">'+(a.lastGpsTs?when(a.lastGpsTs):'Yo‘q')+'</b></div></div>'+
  '<div class="pm-card"><b>📊 Natijalar va marshrut</b><small>Davrni bosing — xaritada GPS yo‘li va tashriflar</small><div class="pm-per" style="margin-top:9px">'+periodBtn('Bugun',a.periods&&a.periods.today,'today',a.id)+periodBtn('7 kun',a.periods&&a.periods.week,'week',a.id)+periodBtn('30 kun',a.periods&&a.periods.month,'month',a.id)+'</div></div>'+
  '<div class="pm-card"><b>📦 Agentdagi tovar</b>'+(stock||'<small>Tovar yo‘q</small>')+'</div>'+
  '<div class="pm-card"><b>🔐 Huquqlar</b><small>Bosib yoqing yoki o‘chiring</small>'+feats+'</div>'+
  '<div class="pm-card"><b>⚙️ Boshqaruv</b>'+manage+'</div>',esc(a.name));
}
window.pmOpenAgent=function(id){openAgent(id)};
async function openAgent(id){loading('Agent profili');try{var ad=await api('agent_detail',{agentId:id});if(ad&&!ad.photoUrl){var ra=(P.agents()||[]).find(function(x){return Number(x.id)===Number(id)});if(ra&&ra.photoUrl)ad.photoUrl=ra.photoUrl}renderAgent(ad)}catch(e){sheet('Agent profili','<div class="pm-note">'+esc(e.message||'Yuklanmadi')+'</div>')}}
var staffTab='agents',staff=null;
function renderStaff(){
 var d=staff||{agents:[],cashiers:[]},act=function(x){return x.active!==false};
 var tabs='<div class="pm-tabs">'+[['agents','🧑‍💼 Agentlar · '+d.agents.filter(act).length],['cashiers','🏦 Kassirlar · '+d.cashiers.filter(act).length]].map(function(t){return '<button data-pm="st-tab" data-tab="'+t[0]+'" class="'+(staffTab===t[0]?'on':'')+'">'+t[1]+'</button>'}).join('')+'</div>';
 var body;
 if(staffTab==='agents'){
  body='<div class="pm-b p" data-pm="ag-add" style="margin-bottom:10px">＋ Yangi agent qo‘shish</div><div class="pm-card">'+
   (d.agents.map(function(a){return '<div class="pm-row'+(act(a)?'':' off')+'" data-pm="ag-open" data-id="'+a.id+'" style="cursor:pointer"><div><b>'+esc(a.name)+'</b><small>ID '+a.id+(a.clients!=null?' · '+a.clients+' mijoz':'')+(a.shiftOpen?' · 🟢 smenada':'')+'</small></div><span class="pm-tag '+(act(a)?'ok':'bad')+'">'+(act(a)?'Faol':'Blok')+'</span></div>'}).join('')||'<small>Agent yo‘q</small>')+'</div>'+
   '<div class="pm-note">Agentni bosing — profil, huquqlar, nomini o‘zgartirish, akkaunt almashtirish va bloklash. Bloklash ma’lumotlarni o‘chirmaydi.</div>';
 }else{
  body='<div class="pm-b p" data-pm="cs-add" style="margin-bottom:10px">＋ Yangi kassir qo‘shish</div>'+
   (d.cashiers.map(function(c){var a=act(c);return '<div class="pm-card'+(a?'':' pm-off')+'"><div class="pm-top"><div><b>'+esc(c.name)+'</b><small>ID '+c.id+' · '+c.accepted+' ta topshiriq qabul qilgan'+(c.lastTs?' · oxirgi '+when(c.lastTs):'')+'</small></div><span class="pm-tag '+(a?'ok':'bad')+'">'+(a?'Faol':'Yopiq')+'</span></div><div class="pm-act">'+
    (a?'<div class="pm-b" data-pm="cs-rename" data-id="'+c.id+'" data-name="'+esc(c.name)+'">✏️ Nomini o‘zgartirish</div>'+(primaryAdmin?'<div class="pm-b" data-pm="cs-transfer" data-id="'+c.id+'" data-name="'+esc(c.name)+'">🔁 Akkaunt almashtirish</div><div class="pm-b r w" data-pm="cs-off" data-id="'+c.id+'" data-name="'+esc(c.name)+'">⛔ Kirishni yopish</div>':'')
     :(primaryAdmin?'<div class="pm-b w" data-pm="cs-on" data-id="'+c.id+'" data-name="'+esc(c.name)+'">↺ Qayta ochish</div>':''))+'</div></div>'}).join('')||'<div class="pm-note">Kassir yo‘q.</div>')+
   '<div class="pm-note">Yopilgan kassirning qabul qilgan pullari va xarajatlari tarixda o‘z ismi bilan qoladi.'+(primaryAdmin?'':' Almashtirish va yopish faqat asosiy rahbarga ruxsat.')+'</div>';
 }
 sheet('👥 Xodimlar',tabs+body,'Agentlar va kassirlarni boshqarish');
}
async function agentManagement(tab){
 if(tab)staffTab=tab;loading('👥 Xodimlar');
 try{staff=await api('staff_list');renderStaff()}catch(e){sheet('👥 Xodimlar','<div class="pm-note">'+esc(e.message||'Yuklanmadi')+'</div>')}
}
async function staffDo(action,payload,btn,msg){
 if(btn)btn.setAttribute('disabled','');
 try{var r=await api(action,Object.assign({confirm:true},payload));staff=r.staff;say('✅ '+msg);renderStaff()}catch(e){say('⚠️ '+(e.message||'Saqlanmadi'));if(btn)btn.removeAttribute('disabled')}
}
async function agentPeriod(id,period){
 var labels={today:'Bugun',week:'7 kun',month:'30 kun'};loading(labels[period]+' · marshrut');
 try{var d=await api('agent_period_detail',{agentId:id,period:period}),g=d.route||{};
  var rows=(d.newClients||[]).map(function(c){return '<div class="pm-row"><div><b>＋ '+esc(c.name)+'</b><small>Yangi mijoz · '+when(c.ts)+'</small></div></div>'}).join('')+
   (d.visits||[]).map(function(v){return '<div class="pm-row"><div><b>✓ '+esc(v.name)+'</b><small>'+esc(v.status||'Tashrif')+' · '+when(v.ts)+(v.note?' · '+esc(v.note):'')+'</small></div></div>'}).join('');
  sheet(labels[period]+' · '+esc(d.agent),'<div class="pm-kpis"><div><small>Yangi mijoz</small><b>'+Number(d.newClientsTotal||0)+'</b></div><div><small>Tashrif</small><b>'+Number(d.visitsTotal||0)+'</b></div><div><small>GPS nuqta</small><b>'+Number(g.gpsTotal||0)+'</b></div><div><small>Agent</small><b style="font-size:13px">'+esc(d.agent)+'</b></div></div>'+
   '<div id="pm-map"></div><div class="pm-note" id="pm-map-st">Xarita yuklanmoqda…</div>'+
   '<div class="pm-card"><b>Faoliyat</b>'+(rows||'<small>Bu davrda tashrif yoki yangi mijoz yo‘q.</small>')+'</div><div class="pm-b" data-pm="ag-open" data-id="'+id+'">← Agent profiliga qaytish</div>',labels[period]);
  drawPeriod(d);
 }catch(e){sheet('Marshrut','<div class="pm-note">'+esc(e.message||'Yuklanmadi')+'</div>')}
}
function drawPeriod(d){
 var L=window.L,box=$('pm-map'),st=$('pm-map-st');if(!L||!box){if(st)st.textContent='Xarita kutubxonasi yuklanmadi.';return}
 periodMap=L.map(box,{zoomControl:true,attributionControl:false,preferCanvas:true}).setView([40.55,70.94],10);
 L.tileLayer('/tiles/{z}/{x}/{y}.png',{maxZoom:17}).addTo(periodMap);
 var bounds=[],segs=(d.route&&d.route.segments)||[];
 segs.forEach(function(s){var ll=s.map(function(p){return [p.lat,p.lon]});if(ll.length>1)L.polyline(ll,{color:'#1f6bff',weight:4,opacity:.88}).addTo(periodMap);ll.forEach(function(x){bounds.push(x)})});
 function pin(lat,lon,color,glyph,title){if(!Number.isFinite(lat)||!Number.isFinite(lon))return;L.marker([lat,lon],{icon:L.divIcon({className:'',html:'<div style="width:24px;height:24px;border-radius:50%;background:'+color+';color:#fff;display:grid;place-items:center;font-size:12px;font-weight:800;border:2px solid #fff;box-shadow:0 2px 8px #0005">'+glyph+'</div>',iconSize:[24,24],iconAnchor:[12,12]})}).addTo(periodMap).bindPopup(esc(title));bounds.push([lat,lon])}
 (d.newClients||[]).forEach(function(c){pin(c.lat,c.lon,'#16b364','＋',c.name)});(d.visits||[]).forEach(function(v){pin(v.lat,v.lon,'#f59e0b','✓',v.name)});
 if(bounds.length)periodMap.fitBounds(L.latLngBounds(bounds).pad(.16),{maxZoom:14,animate:false});
 setTimeout(function(){if(periodMap)periodMap.invalidateSize()},120);
 if(st)st.textContent=segs.length?'Ko‘k chiziq — GPS yo‘li · 🟢 yangi mijoz · 🟠 tashrif':'Bu davrda GPS marshruti qayd etilmagan.';
}

/* =================== CLIENTS =================== */
function clientActions(id){
 return '<div class="pm-card" style="margin-top:14px"><b>⚙️ Boshqaruv</b><div class="pm-act"><div class="pm-b" data-pm="cl-edit" data-id="'+id+'">✎ Tahrirlash</div><div class="pm-b r" data-pm="cl-delete" data-id="'+id+'">🗑 O‘chirish</div><div class="pm-b" data-pm="cl-export" data-id="'+id+'" data-f="pdf">📄 Akt sverka PDF</div><div class="pm-b" data-pm="cl-export" data-id="'+id+'" data-f="xlsx">📊 Akt sverka Excel</div></div></div>';
}
var baseOpenC=window.openC;
window.openC=async function(i){
 await baseOpenC(i);
 var c=(P.clients()||[])[i],sh=$('sh');if(!c||!sh||!sh.classList.contains('on'))return;
 var close=Array.prototype.slice.call(sh.querySelectorAll('.btn.g')).pop();
 var block=document.createElement('div');block.innerHTML=clientActions(c.id);
 if(close)sh.insertBefore(block.firstChild,close);else sh.appendChild(block.firstChild);
};
async function editClient(id){
 loading('Mijozni tahrirlash');
 try{var c=await api('client_detail',{clientId:id});
  sheet('Mijozni tahrirlash','<div class="pm-f"><label>Do‘kon nomi<input id="pm-c-shop" value="'+esc(c.shopName)+'"></label><label>Kontakt shaxs<input id="pm-c-name" value="'+esc(c.person)+'"></label><label>Telefon<input id="pm-c-phone" value="'+esc(c.phone)+'"></label><label>Manzil<textarea id="pm-c-address">'+esc(c.address)+'</textarea></label><label>To‘lov sanasi<input id="pm-c-due" value="'+esc(c.paymentDue)+'" placeholder="YYYY-MM-DD"></label><label>Izoh<textarea id="pm-c-comment">'+esc(c.comment)+'</textarea></label></div>'+
   '<div class="pm-note">Tovar, qarz va to‘lov tarixi bu yerda o‘zgarmaydi. O‘zgarishlar auditda saqlanadi.</div><div class="pm-b p" data-pm="cl-preview" data-id="'+id+'">O‘zgarishni tekshirish →</div>',esc(c.name||''));
 }catch(e){sheet('Mijozni tahrirlash','<div class="pm-note">'+esc(e.message||'Yuklanmadi')+'</div>')}
}
async function previewClient(id){
 var values={name:$('pm-c-name').value,shop_name:$('pm-c-shop').value,phone:$('pm-c-phone').value,address:$('pm-c-address').value,payment_due:$('pm-c-due').value,comment:$('pm-c-comment').value};
 try{var p=await api('client_edit_preview',{clientId:id,values:values});editPreview=p;
  sheet('O‘zgarishni tasdiqlash','<div class="pm-card">'+(p.changes||[]).map(function(x){return '<div class="pm-chg"><b>'+esc(x.field)+'</b><span>'+esc(x.old||'—')+'</span><strong>→ '+esc(x.new||'—')+'</strong></div>'}).join('')+'</div><div class="pm-act"><div class="pm-b p" data-pm="cl-commit">✅ Saqlash</div><div class="pm-b" data-pm="cl-edit" data-id="'+id+'">← Qaytish</div></div>');
 }catch(e){say('⚠️ '+(e.message||'Tekshirib bo‘lmadi'))}
}
async function commitClient(b){
 if(!editPreview)return;var p=editPreview;editPreview=null;b.setAttribute('disabled','');
 try{await api('client_edit_commit',{clientId:p.clientId,values:p.values,confirm:true});say('✅ Mijoz ma’lumoti saqlandi');await P.reload(true);
  var idx=(P.clients()||[]).findIndex(function(c){return c.id===p.clientId});if(idx>=0)window.openC(idx);else window.closeS();
 }catch(e){say('⚠️ '+(e.message||'Saqlanmadi'));b.removeAttribute('disabled')}
}
async function deleteClient(id){
 try{var p=await api('client_delete_preview',{clientId:id});
  pending={action:'client_delete_commit',payload:{clientId:id},after:function(){window.closeS()}};
  sheet('Mijozni o‘chirish','<div class="pm-card"><b>'+esc(p.name)+'</b><small>Qarz: '+usd(p.debtUsd)+' $ · '+Number(p.eventCount||0)+' operatsiya · '+Number(p.visitCount||0)+' tashrif</small><div class="pm-note" style="margin-bottom:0">'+esc(p.warning||'')+'</div></div>'+
   '<div class="pm-act"><div class="pm-b r" data-pm="confirm">🗑 Ha, o‘chirish</div><div class="pm-b" data-pm="close">Bekor qilish</div></div>');
 }catch(e){say('⚠️ '+(e.message||'O‘chirib bo‘lmadi'))}
}

/* =================== ENTRY POINTS =================== */
function sections(){return document.querySelectorAll('section')}
function ensureEntries(d){
 var s=sections();if(!s.length)return;var w=(d&&d.warehouse)||{};
 var home=s[0]&&s[0].querySelector('.bd');
 if(home){
  var e=$('pm-home-ombor');
  if(!e){e=document.createElement('div');e.className='c';e.id='pm-home-ombor';home.insertBefore(e,home.children[1]||null)}
  e.innerHTML='<div class="pm-entry" data-pm="ombor"><div class="ic">📦</div><div><b>Ombor'+(w.newOrders?'<span class="pm-badge">'+w.newOrders+'</span>':'')+'</b><small>'+(w.openOrders||0)+' ta ochiq buyurtma'+(w.missingProducts?' · '+w.missingProducts+' ta mahsulot katalogda yo‘q':' · katalog va narxlar')+'</small></div><em>›</em></div>';
  var t2=$('pm-home-tools');
  if(!t2){t2=document.createElement('div');t2.className='c';t2.id='pm-home-tools';e.parentNode.insertBefore(t2,e.nextSibling)}
  t2.innerHTML='<div class="pm-entry" data-pm="ag-manage"><div class="ic">👥</div><div><b>Xodimlar</b><small>Agentlar va kassirlar · qo‘shish, almashtirish, yopish</small></div><em>›</em></div>'+
   '<div class="pm-entry" data-pm="all-export" data-f="xlsx" style="margin-top:12px;padding-top:12px;border-top:1px solid var(--line)"><div class="ic">📊</div><div><b>Barcha mijozlar</b><small>Excel hisobot yuklab olish</small></div><em>›</em></div>';
 }
 var ag=s[1]&&s[1].querySelector('.bd');
 if(ag&&!$('pm-ag-tools')){
  var t=document.createElement('div');t.id='pm-ag-tools';t.className='pm-act';t.style.margin='0 0 12px';
  t.innerHTML='<div class="pm-b p" data-pm="ag-selected">⚙️ Tanlangan agent profili</div><div class="pm-b" data-pm="ag-manage">👥 Xodimlar · ＋ qo‘shish</div>';
  var card=ag.querySelector('#sa_av');card=card&&card.closest('.c');
  if(card&&card.nextSibling)ag.insertBefore(t,card.nextSibling);else ag.appendChild(t);
 }
 var cl=s[2]&&s[2].querySelector('.bd');
 if(cl&&!$('pm-cl-tools')){
  var x=document.createElement('div');x.id='pm-cl-tools';x.className='pm-act';x.style.margin='0 0 12px';
  x.innerHTML='<div class="pm-b" data-pm="all-export" data-f="xlsx">📊 Barcha mijozlar · Excel</div><div class="pm-b" data-pm="all-export" data-f="pdf">📄 Barcha mijozlar · PDF</div>';
  cl.insertBefore(x,cl.children[1]||null);
 }
}
P.onLoad(function(d){if(d&&typeof d.primaryAdmin==='boolean')primaryAdmin=d.primaryAdmin;ensureEntries(d)});

window.pmPhoto=function(src){var o=document.createElement('div');o.id='pm-photo';o.innerHTML='<img alt="" src="'+esc(src)+'">';o.onclick=function(){o.remove()};document.body.appendChild(o)};
document.addEventListener('click',function(ev){var card=ev.target.closest('.c');if(!card||!card.querySelector('#sa_av')||ev.target.closest('button,.pill,a,[data-pm]'))return;var a=(P.agents()||[])[window.pmSelAgent||0];if(a)openAgent(a.id)});

/* =================== KASSA: 3 pockets + period =================== */
var cashPeriod='today';
function som(v){return Number(v||0).toLocaleString('en-US')}
function flowsHtml(c){c=c||{};function r(t,a,b,k,cls){return '<span>'+t+'</span><b class="'+(cls||'')+'">'+a+'</b><b class="'+(cls||'')+'">'+b+'</b><b class="'+(cls||'')+'">'+k+'</b>'}
 return '<div class="pm-cur3"><span></span><small>Naqd so‘m</small><small>Naqd $</small><small>Karta</small>'+
  r('Kirim','+'+som(c.inCashUzs),'+'+usd(c.inCashUsd),'+'+som(c.inCardUzs)+(c.inCardUsd?' / '+usd(c.inCardUsd)+'$':''),'pm-pos')+
  r('Chiqim','−'+som(c.outCashUzs),'−'+usd(c.outCashUsd),'—','pm-neg')+
  r('Sof',som((c.inCashUzs||0)-(c.outCashUzs||0)),usd((c.inCashUsd||0)-(c.outCashUsd||0)),som(c.inCardUzs))+'</div>'}
function ensureCash(d){
 var s=sections()[3],bd=s&&s.querySelector('.bd');if(!bd)return;var w=(d&&d.cash&&d.cash.wallets)||{};
 var e=$('pm-pockets');if(!e){e=document.createElement('div');e.className='c';e.id='pm-pockets';bd.insertBefore(e,bd.firstChild)}
 e.innerHTML='<h3 style="margin:0 0 10px">💼 Kassa qoldig‘i <small style="color:var(--mu);font-weight:600;font-size:11px">har biri o‘z valyutasida</small></h3><div class="pm-pock"><div><small>💵 Naqd so‘m</small><b class="'+(w.cashUzs<0?'pm-neg':'')+'">'+som(w.cashUzs)+'</b><em>so‘m</em></div><div><small>💲 Naqd dollar</small><b class="'+(w.cashUsd<0?'pm-neg':'')+'">'+usd(w.cashUsd)+'</b><em>USD</em></div><div><small>💳 Karta / bank</small><b>'+som(w.cardUzs)+'</b><em>so‘m'+(w.cardUsd?' + '+usd(w.cardUsd)+' $':'')+'</em></div></div>'+
  (w.since&&w.openingUsd?'<small class="pm-open">Oldingi umumiy qoldiq ('+when(w.since)+' gacha, USD ekvivalent): <b>'+usd(w.openingUsd)+' $</b> · hamyonlar shu vaqtdan keyingi kirim-chiqimni ko‘rsatadi</small>':'')+
  '<div class="pm-chips" style="margin:12px 0 8px">'+[['today','Bugun'],['week','7 kun'],['month','Shu oy'],['custom','Davr']].map(function(x){return '<button data-pm="cash-per" data-p="'+x[0]+'" class="'+(cashPeriod===x[0]?'on':'')+'">'+x[1]+'</button>'}).join('')+'</div>'+
  '<div id="pm-cash-custom" style="display:'+(cashPeriod==='custom'?'grid':'none')+';grid-template-columns:1fr 1fr auto;gap:6px;margin-bottom:8px" class="pm-f"><input type="date" id="pm-cf" style="margin:0"><input type="date" id="pm-ct" style="margin:0"><div class="pm-b p" data-pm="cash-go" style="padding:9px 12px">OK</div></div><div id="pm-cash-flows"><small style="color:var(--mu)">Yuklanmoqda…</small></div>';
 if(cashPeriod!=='custom')loadCashPeriod();
 var home=sections()[0],hb=home&&home.querySelector('.hero .hb small:last-child');if(hb)hb.textContent='Naqd: '+som(w.cashUzs)+' so‘m · '+usd(w.cashUsd)+' $ · Karta: '+som(w.cardUzs)+' so‘m';
}
/* Kassa tiles (qabul / rasxod / sof) follow the selected period instead of a fixed 7 days */
function setCashTiles(r){var s=sections()[3];if(!s||!r)return;var cs=s.querySelectorAll('.bd > .three .c');var lab={today:'Bugun',week:'7 kunda',month:'Shu oy',custom:'Davrda'}[cashPeriod]||'';var a=Number(r.acceptedCashUsd||0),e=Number(r.cashierExpensesUsd||0);
 [[lab+' qabul',a],[lab+' rasxod',e],['Sof o‘zgarish',a-e]].forEach(function(x,i){var c=cs[i];if(!c)return;var sm=c.querySelector('small'),b=c.querySelector('b');if(sm)sm.textContent=x[0];if(b){b.textContent=usd(x[1]);b.classList.toggle('pm-neg',i===2&&x[1]<0);b.style.animation='none';void b.offsetWidth;b.style.animation='up .45s cubic-bezier(.2,.9,.3,1) both'}})}
async function loadCashPeriod(){
 var box=$('pm-cash-flows');if(!box)return;var arg={period:cashPeriod};
 if(cashPeriod==='custom'){arg.from=($('pm-cf')||{}).value;arg.to=($('pm-ct')||{}).value;if(!arg.from||!arg.to){box.innerHTML='<small style="color:var(--mu)">Sanalarni tanlang</small>';return}}
 box.innerHTML='<small style="color:var(--mu)">Yuklanmoqda…</small>';
 try{var r=await api('period_report',arg);box.innerHTML='<small style="display:block;color:var(--mu);margin-bottom:6px">📅 '+esc(r.label)+'</small>'+flowsHtml(r.cash);setCashTiles(r)}catch(e){box.innerHTML='<small style="color:var(--bad)">'+esc(e.message)+'</small>'}
}
P.onLoad(function(d){ensureCash(d)});
function decorateClientList(){
 var list=$('cllist');if(!list)return;var cl=P.clients()||[];
 list.querySelectorAll('.row > .av[onclick^="openC("]').forEach(function(av){
  var i=Number((av.getAttribute('onclick').match(/openC\((\d+)\)/)||[])[1]),c=cl[i];if(!c||!c.photoUrl||av.classList.contains('pm-hasph'))return;
  var letter=av.textContent;av.classList.add('pm-hasph');av.removeAttribute('onclick');av.dataset.photo=c.photoUrl;
  var img=document.createElement('img');img.className='pm-lphoto';img.alt='';img.loading='lazy';img.decoding='async';img.src=c.thumbUrl||c.photoUrl;
  img.onerror=function(){av.classList.remove('pm-hasph');delete av.dataset.photo;av.textContent=letter};
  av.textContent='';av.appendChild(img);
  av.addEventListener('click',function(ev){ev.stopPropagation();if(av.dataset.photo)window.pmPhoto(av.dataset.photo);else window.openC(i)});
 });
}
if(typeof window.rc==='function'){var baseRc=window.rc;window.rc=function(){var r=baseRc.apply(this,arguments);try{decorateClientList()}catch(e){}return r}}
P.onLoad(function(){setTimeout(decorateClientList,50)});

/* =================== CLICKS =================== */
document.addEventListener('click',function(ev){
 var b=ev.target.closest('[data-pm]');if(!b)return;var k=b.dataset.pm,id=Number(b.dataset.id||0);
 if(k==='close'){window.closeS();return}
 if(k==='confirm'){runPending(b);return}
 if(k==='ombor'){openWarehouse();return}
 if(k==='wh-tab'){whTab=b.dataset.tab;renderWarehouse();return}
 if(k==='wh-filter'){whFilter=b.dataset.f;openWarehouse();return}
 if(k==='wh-new'){productForm(null);return}
 if(k==='wh-edit'){productForm((wh.catalog||[]).find(function(p){return p.pack===Number(b.dataset.pack)}));return}
 if(k==='wh-save'){saveProduct(b);return}
 if(k==='wh-demand-add'){var x=(wh.demand||[])[Number(b.dataset.i)];if(x)productForm(null,x.name);return}
 if(k==='wh-demand-map'){mapForm(Number(b.dataset.i));return}
 if(k==='wh-map-save'){mapSave(b);return}
 if(k==='wh-status'){var to=b.dataset.to;if(to==='loaded'&&!b.dataset.ok){b.dataset.ok='1';b.textContent='Tasdiqlash: tovar agentga o‘tadi';return}setStatus(id,to,'',b);return}
 if(k==='wh-reject'){sheet('Buyurtmani rad etish','<div class="pm-f"><label>Sabab<input id="pm-rej" maxlength="300" placeholder="Masalan: omborda yo‘q"></label></div><div class="pm-b r" style="margin-top:14px" data-pm="wh-reject-save" data-id="'+id+'">❌ Rad etish</div>');return}
 if(k==='wh-reject-save'){setStatus(id,'rejected',$('pm-rej').value,b);return}
 if(k==='ag-manage'){agentManagement();return}
 if(k==='st-tab'){staffTab=b.dataset.tab;renderStaff();return}
 if(k==='cs-add'){sheet('Yangi kassir','<div class="pm-f"><label>Telegram ID<input id="pm-cs-id" inputmode="numeric" placeholder="Masalan: 123456789"></label><label>Kassir ismi<input id="pm-cs-name" placeholder="Ism familiya"></label></div><div class="pm-note">Kassir botga /start yuborib Telegram ID sini bilib oladi.</div><div class="pm-b p" data-pm="cs-add-ok">✅ Qo‘shish</div><div class="pm-b" style="margin-top:8px" data-pm="st-back">← Xodimlar</div>');return}
 if(k==='cs-add-ok'){staffTab='cashiers';staffDo('cashier_add',{id:$('pm-cs-id').value,name:$('pm-cs-name').value},b,'Kassir qo‘shildi');return}
 if(k==='cs-rename'){sheet('Kassir nomini o‘zgartirish','<div class="pm-f"><label>Yangi ism<input id="pm-cs-rn" value="'+esc(b.dataset.name||'')+'"></label></div><div class="pm-b p" style="margin-top:14px" data-pm="cs-rename-ok" data-id="'+id+'">💾 Saqlash</div><div class="pm-b" style="margin-top:8px" data-pm="st-back">← Xodimlar</div>');return}
 if(k==='cs-rename-ok'){staffDo('cashier_rename',{cashierId:id,name:$('pm-cs-rn').value},b,'Saqlandi');return}
 if(k==='cs-transfer'){sheet('Kassir akkauntini almashtirish','<div class="pm-note"><b>'+esc(b.dataset.name)+'</b> · eski ID '+id+'</div><div class="pm-f"><label>Yangi Telegram ID<input id="pm-cs-new" inputmode="numeric"></label></div><div class="pm-note">Eski akkaunt yopiladi, yangi ID kassir bo‘ladi. Eski operatsiyalar tarixda qoladi.</div><div class="pm-b p" data-pm="cs-transfer-ok" data-id="'+id+'">🔁 Almashtirish</div><div class="pm-b" style="margin-top:8px" data-pm="st-back">← Xodimlar</div>');return}
 if(k==='cs-transfer-ok'){staffDo('cashier_transfer',{cashierId:id,newId:$('pm-cs-new').value},b,'Akkaunt almashtirildi');return}
 if(k==='cs-off'){if(!b.dataset.ok){b.dataset.ok='1';b.textContent='Tasdiqlash: '+(b.dataset.name||'')+' kira olmaydi';return}staffDo('cashier_deactivate',{cashierId:id},b,'Kassir yopildi');return}
 if(k==='cs-on'){staffDo('cashier_activate',{cashierId:id},b,'Kassir qayta ochildi');return}
 if(k==='st-back'){renderStaff();return}
 if(k==='cash-per'){cashPeriod=b.dataset.p;b.parentNode.querySelectorAll('button').forEach(function(x){x.classList.toggle('on',x===b)});var cc=$('pm-cash-custom');if(cc){cc.style.display=cashPeriod==='custom'?'grid':'none';if(cashPeriod==='custom'&&!$('pm-cf').value){var n=new Date(),pd=function(x){return String(x).padStart(2,'0')};$('pm-ct').value=n.getFullYear()+'-'+pd(n.getMonth()+1)+'-'+pd(n.getDate());$('pm-cf').value=n.getFullYear()+'-'+pd(n.getMonth()+1)+'-01'}}if(cashPeriod!=='custom')loadCashPeriod();return}
 if(k==='cash-go'){loadCashPeriod();return}
 if(k==='ag-open'){openAgent(id);return}
 if(k==='ag-selected'){var ags=P.agents()||[],a=ags[window.pmSelAgent||0];if(a)openAgent(a.id);else say('Agent tanlanmagan');return}
 if(k==='ag-period'){agentPeriod(id,b.dataset.period);return}
 if(k==='ag-feature'){var on=b.dataset.on!=='1',label=b.querySelector('span').textContent;confirmBox('Huquqni o‘zgartirish','<b>'+esc(label)+'</b><small>Yangi holat: <b>'+(on?'ON · ruxsat beriladi':'OFF · o‘chiriladi')+'</b></small>','agent_feature_set',{agentId:id,feature:b.dataset.key,enabled:on});return}
 if(k==='ag-add'){sheet('Yangi agent','<div class="pm-f"><label>Telegram ID<input id="pm-a-id" inputmode="numeric" placeholder="Masalan: 123456789"></label><label>Agent ismi<input id="pm-a-name" placeholder="Ism familiya"></label></div><div class="pm-note">Agent botga /start yuborib Telegram ID sini bilib oladi.</div><div class="pm-b p" data-pm="ag-add-prev">Tekshirish →</div>');return}
 if(k==='ag-add-prev'){api('agent_add_preview',{id:$('pm-a-id').value,name:$('pm-a-name').value}).then(function(p){confirmBox('Agent qo‘shish','Yangi agent: <b>'+esc(p.name)+'</b><small>Telegram ID: '+p.id+'</small>','agent_add_commit',{id:p.id,name:p.name})}).catch(function(e){say('⚠️ '+e.message)});return}
 if(k==='ag-rename'){sheet('Agent nomini o‘zgartirish','<div class="pm-f"><label>Yangi ism<input id="pm-a-rename" value="'+esc(b.dataset.name||'')+'"></label></div><div class="pm-b p" style="margin-top:14px" data-pm="ag-rename-prev" data-id="'+id+'">Tekshirish →</div>');return}
 if(k==='ag-rename-prev'){api('agent_rename_preview',{agentId:id,name:$('pm-a-rename').value}).then(function(p){confirmBox('Nomni o‘zgartirish','Eski: <b>'+esc(p.oldName)+'</b><br>Yangi: <b>'+esc(p.newName)+'</b>','agent_rename_commit',{agentId:id,name:p.newName})}).catch(function(e){say('⚠️ '+e.message)});return}
 if(k==='ag-transfer'){sheet('Akkaunt almashtirish','<div class="pm-f"><label>Yangi Telegram ID<input id="pm-a-new" inputmode="numeric"></label></div><div class="pm-note">Eski ID bloklanadi. Mijozlar, savdo, pul, smena va tarix yangi IDga o‘tadi. Agent smenasi yopiq bo‘lishi shart.</div><div class="pm-b p" data-pm="ag-transfer-prev" data-id="'+id+'">Tekshirish →</div>');return}
 if(k==='ag-transfer-prev'){api('agent_transfer_preview',{agentId:id,newId:$('pm-a-new').value}).then(function(p){var st=(p.stocks||[]).filter(function(x){return x.qty}).map(function(x){return esc(x.name)+': '+x.qty}).join('<br>')||'Tovar qoldig‘i yo‘q';confirmBox('Akkaunt almashtirish','Agent: <b>'+esc(p.agent)+'</b><br>Yangi ID: <b>'+p.newId+'</b><small>Mijozlar: '+p.clients+' · Qo‘ldagi pul: '+usd(p.cashUsd)+' $<br>'+st+'</small>','agent_transfer_commit',{agentId:id,newId:p.newId})}).catch(function(e){say('⚠️ '+e.message)});return}
 if(k==='ag-block'){api('agent_deactivate_preview',{agentId:id}).then(function(p){confirmBox('Kirishni bloklash','<b>'+esc(p.agent)+'</b><small>'+esc(p.warning)+'<br>Mijozlar: '+p.clients+' · Qo‘ldagi pul: '+usd(p.cashUsd)+' $ · Kutilmoqda: '+usd(p.pendingHandoverUsd)+' $</small>','agent_deactivate_commit',{agentId:id})}).catch(function(e){say('⚠️ '+e.message)});return}
 if(k==='cl-edit'){editClient(id);return}
 if(k==='cl-preview'){previewClient(id);return}
 if(k==='cl-commit'){commitClient(b);return}
 if(k==='cl-delete'){deleteClient(id);return}
 if(k==='cl-export'){exportFile('client_export',{clientId:id,format:b.dataset.f},'Akt sverka '+(b.dataset.f==='pdf'?'PDF':'Excel'));return}
 if(k==='all-export'){exportFile('all_clients_export',{format:b.dataset.f},'Barcha mijozlar '+(b.dataset.f==='pdf'?'PDF':'Excel'));return}
},true);

/* ---------- photos: retry a failed image twice (1.2s, 3.5s) before its fallback runs ---------- */
document.addEventListener('error',function(e){var img=e.target;if(!(img instanceof HTMLImageElement)||!/\bpm-(cphoto|vphoto|lphoto|agph)\b/.test(img.className))return;
 if(!img.dataset.src)img.dataset.src=img.getAttribute('src')||'';var n=Number(img.dataset.retry||0),base=img.dataset.src;
 if(n<2&&base&&navigator.onLine!==false){e.stopImmediatePropagation();img.dataset.retry=String(n+1);setTimeout(function(){if(img.isConnected)img.src=base+(base.indexOf('?')>=0?'&':'?')+'r='+(n+1)},n?3500:1200)}},true);
/* ---------- product rating (Hisobot → Mahsulotlar bo'yicha) ---------- */
window.pmProducts=function(){
 var rep=window.__pmRep,d=P.data();
 if(!rep&&d&&d.reports)rep=d.reports.today;
 var list=((rep&&rep.products)||[]).slice();
 if(!list.length){sheet('📦 Mahsulotlar reytingi','<div class="pm-note" style="text-align:center">Bu davrda realizatsiya yo‘q.</div>',rep&&rep.label);return}
 var mx=Math.max.apply(null,[1].concat(list.map(function(p){return Number(p.deliveredUsd||0)})));
 var Q=['#2a8bf2','#8b5cf6','#34c759','#f5a524','#f0527a','#2b9ac9'];
 var tot=list.reduce(function(a,p){return a+Number(p.deliveredUsd||0)},0),qty=list.reduce(function(a,p){return a+Number(p.deliveredQty||0)},0);
 var body='<div class="pm-kpis" style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:12px"><div class="pm-card" style="margin:0"><small>Jami realizatsiya</small><b style="font-size:20px">'+usd(tot)+' $</b></div><div class="pm-card" style="margin:0"><small>Berilgan dona</small><b style="font-size:20px">'+qty.toLocaleString('en-US')+'</b></div></div><div class="pm-card">'+
  list.map(function(p,i){var w=mx?Math.max(2,Number(p.deliveredUsd||0)/mx*100):0;return '<div class="pm-rk" style="--q:'+Q[i%Q.length]+';animation-delay:'+Math.min(i,10)*40+'ms"><span class="n">'+(i+1)+'</span><div><b>'+esc(p.name||('Mahsulot '+p.pack))+'</b><small>Berildi '+Number(p.deliveredQty||0)+' · sotildi '+Number(p.soldQty||0)+' · qaytdi '+Number(p.returnedQty||0)+'</small></div><div class="v">'+usd(p.deliveredUsd)+' $<small>'+Number(p.sharePct||0).toFixed(1)+'%</small></div><div class="tr"><i style="width:'+w.toFixed(1)+'%;animation-delay:'+Math.min(i,10)*40+'ms"></i></div></div>'}).join('')+'</div>';
 sheet('📦 Mahsulotlar reytingi',body,(rep&&rep.label)||window.__pmRepLabel||'Tanlangan davr');
};
})();
