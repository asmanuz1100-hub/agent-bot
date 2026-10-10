(function(){
'use strict';

const REAL_API='/api/manager';
let REAL_MODE=false,REAL_DASH=null,REAL_CLIENTS=[],REAL_AGENTS=[],REAL_TX=[];
let leafletPromise=null,agentLayer=null,clientMapObj=null,clientLayer=null;
const baseToast=toast,baseGo=go;

function $(id){return document.getElementById(id)}
function esc(v){return String(v==null?'':v).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]})}
function usd(v){return Number(v||0).toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2})}
function setText(el,v){if(!el)return;el.textContent=String(v);try{delete el._m}catch(e){}}
function eventTs(t){return t&&t.type==='handover'&&t.state==='accepted'?(t.acceptedTs||t.ts):t&&t.ts}
function clock(ts){if(!ts)return '—';try{return new Date(Number(ts)*1000).toLocaleString('uz-UZ',{timeZone:'Asia/Tashkent',day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'})}catch(e){return '—'}}
function validCoord(lat,lon){return Number.isFinite(Number(lat))&&Number.isFinite(Number(lon))&&Math.abs(Number(lat))<=90&&Math.abs(Number(lon))<=180}
function currentPage(){return Array.from(document.querySelectorAll('section')).findIndex(function(x){return x.classList.contains('on')})}
function ageKey(c){return !c?'Noma’lum':c.age==='scheduled'?'Rejada':c.age==='red'?'5+ kun':c.age==='yellow'?'3–4 kun':c.age==='fresh'?'0–2 kun':'Noma’lum'}
function agentState(a){if(!a||!a.shiftOpen)return 'Yopiq';return a.status==='active'&&a.locationSource==='live'?'Faol':'Kechikkan'}
function agentInfo(a){
 if(!a)return 'Agent';
 if(!a.shiftOpen)return a.lastGpsTs?'Smena yopiq · oxirgi GPS '+clock(a.lastGpsTs):'Smena yopiq · GPS yo‘q';
 if(a.locationSource==='live'&&a.status==='active')return 'Ishda · GPS faol · '+clock(a.lastGpsTs);
 if(a.lastGpsTs)return 'Ishda · GPS eskirgan · '+clock(a.lastGpsTs);
 return 'Ishda · GPS yo‘q';
}
function pct(cur,prev){cur=Number(cur||0);prev=Number(prev||0);if(!prev)return null;return (cur-prev)/Math.abs(prev)*100}
function delta(cur,prev){const p=pct(cur,prev);return p==null?(Number(cur||0)?'Yangi':'0.0%'):(p>=0?'+':'')+p.toFixed(1)+'%'}
function kindLabel(k){return ({delivery:'Tovar berildi',payment:'Qarz to‘lovi',return:'Tovar qaytdi',sold:'Sotildi',order:'Buyurtma',visit:'Tashrif'})[k]||k||'Operatsiya'}

toast=function(m){if(REAL_MODE&&String(m).indexOf('Abduvoxid: Nur savdo')>=0)return;baseToast(m)};

// Faqat o'qish so'rovlari: tarmoq uzilsa (iOS "Load failed") 2 marta qayta urinadi. Yozish amallari qayta yuborilmaydi.
var READ_ACTIONS={dashboard:1,client_detail:1,period_report:1,route:1,insights:1,agent_detail:1,agent_period_detail:1};
async function req(action,arg){
 for(var attempt=0;;attempt++){
  try{return await req1(action,arg)}
  catch(e){var net=e instanceof TypeError||/load failed|failed to fetch|network/i.test(e.message||'');
   if(!net||!READ_ACTIONS[action])throw e;
   if(attempt>=2)throw new Error('Internet aloqasi uzildi. Qayta urinib ko‘ring.');
   await new Promise(function(r){setTimeout(r,1200*(attempt+1))})}
 }
}
async function req1(action,arg){
 if(!tg||!tg.initData)throw new Error('Real ma’lumot faqat Telegram botdagi 🧪 Rahbar Premium TEST orqali ochiladi.');
 const payload={initData:tg.initData,action:action};if(arg&&typeof arg==='object')Object.assign(payload,arg);
 const ctl=new AbortController(),timer=setTimeout(function(){ctl.abort()},60000);
 try{
  const r=await fetch(REAL_API,{method:'POST',headers:{'Content-Type':'application/json'},cache:'no-store',signal:ctl.signal,body:JSON.stringify(payload)});
  let d;try{d=await r.json()}catch(e){throw new Error('Server noto‘g‘ri javob qaytardi.')}
  if(!r.ok)throw new Error(d.error||('API xatosi '+r.status));return d;
 }catch(e){if(e.name==='AbortError')throw new Error('Server javob bermadi. Qayta urinib ko‘ring.');throw e}
 finally{clearTimeout(timer)}
}

function loadLeaflet(){
 if(window.L)return Promise.resolve(window.L);
 if(leafletPromise)return leafletPromise;
 leafletPromise=new Promise(function(resolve,reject){
  if(!document.querySelector('link[data-asman-leaflet]')){
   const css=document.createElement('link');css.rel='stylesheet';css.href='https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css';css.dataset.asmanLeaflet='1';document.head.appendChild(css);
  }
  const old=document.querySelector('script[data-asman-leaflet]');
  if(old){old.addEventListener('load',function(){window.L?resolve(window.L):reject(Error('Map kutubxonasi mavjud emas.'))},{once:true});old.addEventListener('error',function(){reject(Error('Map kutubxonasi yuklanmadi.'))},{once:true});return}
  const sc=document.createElement('script');sc.src='https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js';sc.async=true;sc.dataset.asmanLeaflet='1';
  sc.onload=function(){window.L?resolve(window.L):reject(Error('Map kutubxonasi mavjud emas.'))};sc.onerror=function(){reject(Error('Map kutubxonasi yuklanmadi.'))};document.body.appendChild(sc);
 }).catch(function(e){leafletPromise=null;throw e});
 return leafletPromise;
}

function markReal(){
 document.querySelectorAll('.live').forEach(function(x){x.textContent='● REAL DATA'});
 const note=$('clientmap-count');if(note)note.textContent='Haqiqiy mijoz nuqtalari';
}

function updateHome(d){
 const s=d.summary||{},c=d.cash||{},home=document.querySelectorAll('section')[0];
 document.querySelectorAll('.bal').forEach(function(x){setText(x,usd(c.balanceUsd))});
 document.querySelectorAll('.pend').forEach(function(x){setText(x,usd(c.pendingUsd))});
 const grid=home.querySelector('.bd > .two'),cards=grid?grid.querySelectorAll('.c.kp'):[];
 const vals=[[s.agentCount||0,'● '+(s.workingAgents||0)+' tasi ishda'],[d.clientCount||REAL_CLIENTS.length,'● '+(s.newClientsToday||0)+' ta yangi bugun'],[s.visitsToday||0,'Agentlar qaydi'],[s.overdueClients||0,'● 5+ kun tashrifsiz']];
 vals.forEach(function(v,i){if(!cards[i])return;setText(cards[i].querySelector('b'),v[0]);setText(cards[i].querySelector('em'),v[1])});
 const bad=home.querySelector('.al.r .bad');if(bad)setText(bad,(s.overdueClients||0)+' ta');
 if(typeof pal!=='undefined')setText(pal,usd(c.pendingUsd)+' USD tasdiq kutmoqda');
 if(typeof pas!=='undefined')setText(pas,(c.pendingCount||0)+' ta operatsiya kassir tasdig‘ida');
 const plan=home.querySelector('.plan'),today=d.reports&&d.reports.today;
 if(plan&&today){
  const ratio=today.paymentToDeliveryPct==null?0:Number(today.paymentToDeliveryPct);
  const title=plan.querySelector('div[style*="flex:1"] > b');if(title)setText(title,'Bugungi tushum / realizatsiya');
  const sub=plan.querySelector('div[style*="flex:1"] > small');if(sub)setText(sub,usd(today.paymentsUsd)+' $ / '+usd(today.deliveredUsd)+' $');
  const ring=plan.querySelector('.rg text');if(ring)setText(ring,Math.round(ratio)+'%');
  const ringCircle=plan.querySelector('.rg .v');if(ringCircle){ringCircle.dataset.to=(226*(1-Math.min(100,ratio)/100)).toFixed(1);ringCircle.style.strokeDashoffset=ringCircle.dataset.to}
  const box=plan.querySelector('div[style*="flex:1"]');if(box){
   box.querySelectorAll('.pr').forEach(function(x){x.remove()});
   (today.agents||[]).slice().sort(function(a,b){return Number(b.deliveredUsd||0)-Number(a.deliveredUsd||0)}).slice(0,3).forEach(function(a){
    const r=Number(a.deliveredUsd||0)>0?Math.min(100,Number(a.paymentsUsd||0)/Number(a.deliveredUsd||0)*100):0;
    box.insertAdjacentHTML('beforeend','<div class="pr"><span>'+esc(a.agent||'Agent')+'</span><div><u data-w="'+r.toFixed(0)+'" style="width:'+r.toFixed(0)+'%"></u></div><em>'+r.toFixed(0)+'%</em></div>');
   });
  }
 }
}

function refreshAgents(d){
 const by=new Map(((d.reports&&d.reports.today&&d.reports.today.agents)||[]).map(function(x){return [Number(x.agentId),x]}));
 AG.splice(0,AG.length);AG_LL.splice(0,AG_LL.length);
 REAL_AGENTS.forEach(function(a){
  const r=by.get(Number(a.id))||{};
  AG.push([a.name||String(a.id),agentInfo(a),Number(a.done||0),Number(r.newClients||0),agentState(a)]);
  AG_LL.push(validCoord(a.lat,a.lon)?[Number(a.lat),Number(a.lon)]:[NaN,NaN]);
 });
 al();tog(agch,function(i){al(['','Faol','Kechikkan','Yopiq'][i])});
 if(AG.length){autoSel=true;try{selA(Math.min(selAgent,AG.length-1))}finally{autoSel=false}}
}

function refreshClients(d){
 cols['Noma’lum']=['pri','p-pri'];
 CL.splice(0,CL.length);CL_LL.splice(0,CL_LL.length);
 REAL_CLIENTS.forEach(function(c){
  CL.push([c.name||'Mijoz',c.address||'Manzil kiritilmagan','Agent: '+(c.agent||'—'),Number(c.debtUsd||0),ageKey(c)]);
  CL_LL.push(validCoord(c.lat,c.lon)?[Number(c.lat),Number(c.lon)]:[NaN,NaN]);
 });
 const items=[['Barchasi',CL.length,''],['0–2 kun',CL.filter(function(c){return c[4]==='0–2 kun'}).length,'0–2 kun'],['3–4 kun',CL.filter(function(c){return c[4]==='3–4 kun'}).length,'3–4 kun'],['5+ kun',CL.filter(function(c){return c[4]==='5+ kun'}).length,'5+ kun'],['Rejada',CL.filter(function(c){return c[4]==='Rejada'}).length,'Rejada'],['Noma’lum',CL.filter(function(c){return c[4]==='Noma’lum'}).length,'Noma’lum']];
 CH.splice(0,CH.length);items.forEach(function(x){CH.push(x)});
 clch.innerHTML=CH.map(function(c,i){return '<button class="'+(i?'':'on')+'">'+c[0]+' <b>'+c[1]+'</b></button>'}).join('');
 cf='';tog(clch,function(i){cf=CH[i][2];rc()});rc();
 const countSpan=document.querySelectorAll('section')[2].querySelector('.c h3 span:last-child');if(countSpan)setText(countSpan,(d.clientCount||CL.length)+' mijoz');
}

selA=function(i){
 const a=AG[i];if(!a)return;setText(sa_av,(a[0]||'?')[0]);setText(sa_n,a[0]);setText(sa_i,'📍 '+a[1]+' · '+a[2]+' ta tashrif · '+a[3]+' ta yangi mijoz');
 sa_p.className='pill '+(a[4]==='Faol'?'p-ok':a[4]==='Kechikkan'?'p-wa':'p-pri');setText(sa_p,'● '+a[4]);selAgent=i;window.pmSelAgent=i;
 const count=document.querySelectorAll('section')[1].querySelector('.two .pill:nth-child(2)');if(count&&REAL_AGENTS[i]){setText(count,'👥 Mijozlar ('+Number(REAL_AGENTS[i].clients||0)+')');count.style.cursor='pointer';count.setAttribute('role','button');count.onclick=function(){goCl(0);const q=document.getElementById('qi');qq=a[0];if(q)q.value=a[0];rc()}}
 ymapPMs.forEach(function(m,k){if(!m)return;m.setIcon(agentIcon(L,REAL_AGENTS[k]||{name:AG[k]&&AG[k][0]},k===i))});
 setSelAvatar(i);
 const ll=AG_LL[i];if(ymapObj&&ll&&validCoord(ll[0],ll[1]))ymapObj.flyTo(ll,15,{duration:.45});
 if(REAL_MODE&&ymapObj&&currentPage()===1){if(!autoSel)drawAgentTrack(i);else if(trackAgentId!=null&&REAL_AGENTS[i]&&REAL_AGENTS[i].id===trackAgentId)drawAgentTrack(i,true)}
 scrollTo({top:0,behavior:'smooth'});
};

ymapRoute=function(i){
 const ll=AG_LL[i];if(!ll||!validCoord(ll[0],ll[1])){toast('Bu agentda GPS nuqta yo‘q');return}
 const url='https://www.google.com/maps/dir/?api=1&destination='+ll[0]+','+ll[1];if(tg&&tg.openLink)tg.openLink(url);else window.open(url,'_blank');
};

/* Agent photos: preload with retries (a cold server may need a few seconds for the first thumbnail);
   markers/list show the initial until the photo is really loaded, then switch without a reload. */
const AGPH={};
function agPhotoSrc(url){const x=url&&AGPH[url];return x&&x.ok?x.src:''}
function agPhotoLoad(url,cb){
 if(!url)return;let x=AGPH[url];if(x&&x.ok){if(cb)cb();return}
 if(!x){x=AGPH[url]={ok:false,n:0,cbs:[]};}if(cb)x.cbs.push(cb);if(x.busy||x.dead)return;x.busy=true;
 const waits=[0,1500,3500,7000,15000];
 (function attempt(){const im=new Image(),src=x.n?url+(url.indexOf('?')<0?'?':'&')+'r='+x.n:url;
  im.onload=function(){x.ok=true;x.busy=false;x.src=src;const cbs=x.cbs.splice(0);cbs.forEach(function(f){try{f()}catch(e){}})};
  im.onerror=function(){x.n++;if(x.n>=waits.length){x.busy=false;x.dead=true;return}setTimeout(attempt,waits[x.n])};
  im.src=src})();
}
window.pmPhotoSrc=agPhotoSrc;window.pmPhotoLoad=agPhotoLoad;
function preloadAgentPhotos(){REAL_AGENTS.forEach(function(a){if(a&&a.photoUrl)agPhotoLoad(a.photoUrl,refreshAgentPhotos)})}
let agPhotoTimer=0;
function refreshAgentPhotos(){clearTimeout(agPhotoTimer);agPhotoTimer=setTimeout(function(){
 if(window.L)ymapPMs.forEach(function(m,k){if(m)m.setIcon(agentIcon(window.L,REAL_AGENTS[k],k===selAgent))});
 if(window.pmAgPhotos)window.pmAgPhotos();setSelAvatar(selAgent)},60)}
function setSelAvatar(i){const sav=document.getElementById('sa_av'),ra=REAL_AGENTS[i],a=AG[i]||[];if(!sav)return;const src=ra&&agPhotoSrc(ra.photoUrl);
 if(src){sav.classList.add('pm-agph');sav.innerHTML='<img class="pm-agph" alt="" src="'+esc(src)+'">'}else{sav.classList.remove('pm-agph');sav.textContent=(a[0]||'?')[0];if(ra&&ra.photoUrl)agPhotoLoad(ra.photoUrl,refreshAgentPhotos)}}
/* Agent marker: round photo (or initial) in a status-coloured ring; tap opens the agent card */
function agentIcon(L,a,on){a=a||{};const color=!a.shiftOpen||a.locationSource==='last'?'#7f8fa6':a.status==='active'?'#16b364':'#f59e0b';const ini=esc((a.name||'?')[0]);
 const src=agPhotoSrc(a.photoUrl);if(a.photoUrl&&!src)agPhotoLoad(a.photoUrl,refreshAgentPhotos);
 const inner=src?'<img class="pm-agph" alt="" src="'+esc(src)+'">':ini;
 return L.divIcon({className:'',html:'<div class="ymap-ava'+(on?' on':'')+'" style="--c:'+color+'" role="button" aria-label="'+esc(a.name||'Agent')+'"><span>'+inner+'</span></div>',iconSize:[46,53],iconAnchor:[23,53]})}
window.pmAgPhotos=function(){const list=document.getElementById('aglist');if(!list)return;list.querySelectorAll('.row[onclick^="selA("] > .av').forEach(function(av){const n=Number((av.parentNode.getAttribute('onclick').match(/selA\((\d+)\)/)||[])[1]),a=REAL_AGENTS[n];if(!a||!a.photoUrl||av.classList.contains('pm-agph'))return;const src=agPhotoSrc(a.photoUrl);if(!src){agPhotoLoad(a.photoUrl,refreshAgentPhotos);return}av.classList.add('pm-agph');av.innerHTML='<img class="pm-agph" alt="" src="'+esc(src)+'">'})};
/* Selected agent's latest-shift GPS trail on the main map */
let trackLayer=null,trackSeq=0,trackAgentId=null,autoSel=false;
function hm(ts){try{return new Date(Number(ts)*1000).toLocaleTimeString('uz-UZ',{timeZone:'Asia/Tashkent',hour:'2-digit',minute:'2-digit'})}catch(e){return '—'}}
function kmOf(pts){let km=0;for(let k=1;k<pts.length;k++){const a=pts[k-1],b=pts[k],r=Math.PI/180,dl=(b.lat-a.lat)*r,dn=(b.lon-a.lon)*r,h=Math.sin(dl/2)**2+Math.cos(a.lat*r)*Math.cos(b.lat*r)*Math.sin(dn/2)**2,d=12742*Math.asin(Math.sqrt(h));if(d<25)km+=d}return km}
async function drawAgentTrack(i,quiet){
 const a=REAL_AGENTS[i],seq=++trackSeq;if(!a||!ymapObj||!window.L)return;const L=window.L;
 if(!trackLayer)trackLayer=L.layerGroup().addTo(ymapObj);if(!quiet)trackLayer.clearLayers();trackAgentId=a.id;
 let r;try{r=await req('route',{agentId:a.id})}catch(e){return}
 if(seq!==trackSeq||!ymapObj)return;trackLayer.clearLayers();
 const pts=(r&&r.points||[]).filter(function(p){return validCoord(p.lat,p.lon)});if(pts.length<2){trackLayer.clearLayers();if(!quiet)toast('🛣 '+(a.name||'Agent')+': bugun GPS yo‘l yozilmagan');return}
 const segs=[];let cur=[];pts.forEach(function(p,k){const q=pts[k-1];if(q&&(p.ts-q.ts>1800||kmOf([q,p])>=25)){if(cur.length)segs.push(cur);cur=[]}cur.push(p)});if(cur.length)segs.push(cur);
 segs.forEach(function(sg){if(sg.length>1){L.polyline(sg.map(function(p){return[p.lat,p.lon]}),{color:'#ffffff',weight:8,opacity:.9}).addTo(trackLayer);L.polyline(sg.map(function(p){return[p.lat,p.lon]}),{color:'#1f6bff',weight:4.5,opacity:.95}).addTo(trackLayer)}});
 const f=pts[0];L.circleMarker([f.lat,f.lon],{radius:7,color:'#fff',weight:3,fillColor:'#16b364',fillOpacity:1}).bindTooltip('Boshlanish · '+hm(f.ts)).addTo(trackLayer);
 if(quiet)return;const b=L.latLngBounds(pts.map(function(p){return[p.lat,p.lon]}));if(b.isValid())ymapObj.flyToBounds(b.pad(.2),{maxZoom:16,duration:.5});
 toast('🛣 '+(a.name||'Agent')+' · '+(r.end?'oxirgi smena':'bugun')+': '+kmOf(pts).toFixed(1)+' km · '+hm(f.ts)+'–'+hm(pts[pts.length-1].ts));
}
async function renderAgentMap(){
 if(!REAL_MODE||currentPage()!==1)return;
 const box=$('ymap');if(!box)return;
 try{
  const L=await loadLeaflet();if(currentPage()!==1)return;
  const validAgents=REAL_AGENTS.filter(function(a){return validCoord(a.lat,a.lon)&&a.lastGpsTs});
  const validClients=REAL_CLIENTS.filter(function(c){return validCoord(c.lat,c.lon)});
  if(!validAgents.length&&!validClients.length){box.innerHTML='<div id="ymap-ld">Agent yoki mijozlarda haqiqiy GPS koordinata yo‘q.</div>';return}
  if(!ymapObj){
   box.innerHTML='';ymapObj=L.map('ymap',{zoomControl:true,attributionControl:true,scrollWheelZoom:false,preferCanvas:true}).setView([40.55,70.94],9);
   L.tileLayer('/tiles/{z}/{x}/{y}.png',{maxZoom:17,updateWhenIdle:true,keepBuffer:2}).addTo(ymapObj);agentLayer=L.layerGroup().addTo(ymapObj);
  }
  if(!agentLayer)agentLayer=L.layerGroup().addTo(ymapObj);agentLayer.clearLayers();ymapPMs=[];ymapCPMs=[];const bounds=[];
  REAL_CLIENTS.forEach(function(c,i){if(!validCoord(c.lat,c.lon))return;const color=c.age==='fresh'?'#16b364':c.age==='yellow'?'#f59e0b':c.age==='red'?'#f0384f':c.age==='scheduled'?'#1f6bff':'#94a3b8';const icon=L.divIcon({className:'',html:'<div class="ymap-dot" style="background:'+color+'"></div>',iconSize:[16,16],iconAnchor:[8,8]});const m=L.marker([Number(c.lat),Number(c.lon)],{icon:icon,zIndexOffset:100,title:c.name||'Mijoz'}).addTo(agentLayer);m.bindPopup('<div class="ymap-bln"><b>'+esc(c.name||'Mijoz')+'</b><small>📍 '+esc(c.address||'Manzil yo‘q')+'</small><small>Agent: '+esc(c.agent||'—')+' · Qarz: '+usd(c.debtUsd)+' $</small><button onclick="openC('+i+')">Mijoz kartasi</button></div>');ymapCPMs[i]=m;bounds.push([Number(c.lat),Number(c.lon)])});
  REAL_AGENTS.forEach(function(a,i){if(!validCoord(a.lat,a.lon)||!a.lastGpsTs)return;const icon=agentIcon(L,a,i===selAgent);const m=L.marker([Number(a.lat),Number(a.lon)],{icon:icon,zIndexOffset:1000,title:a.name||'Agent',keyboard:true}).addTo(agentLayer);m.on('click',function(){selA(i);if(window.pmOpenAgent)window.pmOpenAgent(a.id)});ymapPMs[i]=m;bounds.push([Number(a.lat),Number(a.lon)])});
  if(bounds.length){const b=L.latLngBounds(bounds);if(b.isValid())ymapObj.fitBounds(b.pad(.15),{maxZoom:13,animate:false})}
  ymapObj.invalidateSize(false);setTimeout(function(){if(ymapObj&&currentPage()===1)ymapObj.invalidateSize(false)},250);
 }catch(e){box.innerHTML='<div id="ymap-ld">Xarita yuklanmadi: '+esc(e.message||'Internetni tekshiring')+'</div>'}
}

async function renderClientMap(){
 if(!REAL_MODE||currentPage()!==2)return;
 const box=$('clientmap'),count=$('clientmap-count');if(!box)return;
 try{
  const L=await loadLeaflet();if(currentPage()!==2)return;
  const pts=REAL_CLIENTS.filter(function(c){return validCoord(c.lat,c.lon)});
  if(count)setText(count,pts.length+' / '+REAL_CLIENTS.length+' ta GPS nuqta');
  if(!pts.length){box.innerHTML='<div id="clientmap-ld">Mijozlarda haqiqiy GPS koordinata yo‘q.</div>';return}
  if(!clientMapObj){
   box.innerHTML='';clientMapObj=L.map('clientmap',{zoomControl:true,attributionControl:true,scrollWheelZoom:false,preferCanvas:true}).setView([40.55,70.94],9);
   L.tileLayer('/tiles/{z}/{x}/{y}.png',{maxZoom:17,updateWhenIdle:true,keepBuffer:2}).addTo(clientMapObj);clientLayer=L.layerGroup().addTo(clientMapObj);
  }
  if(!clientLayer)clientLayer=L.layerGroup().addTo(clientMapObj);clientLayer.clearLayers();const bounds=[];
  REAL_CLIENTS.forEach(function(c,i){if(!validCoord(c.lat,c.lon))return;const color=c.age==='fresh'?'#16b364':c.age==='yellow'?'#f59e0b':c.age==='red'?'#f0384f':c.age==='scheduled'?'#1f6bff':'#94a3b8';const glyph=c.age==='red'?'!':c.age==='scheduled'?'•':'';const icon=L.divIcon({className:'',html:'<div class="ymap-dot" style="width:22px;height:22px;background:'+color+';display:grid;place-items:center;color:white;font-size:10px;font-weight:800">'+glyph+'</div>',iconSize:[22,22],iconAnchor:[11,11]});L.marker([Number(c.lat),Number(c.lon)],{icon:icon,title:c.name||'Mijoz'}).addTo(clientLayer).bindPopup('<div class="ymap-bln"><b>'+esc(c.name||'Mijoz')+'</b><small>'+esc(c.address||'Manzil yo‘q')+'</small><small>Agent: '+esc(c.agent||'—')+' · '+(c.days==null?'Faollik noma’lum':c.days+' kun')+'</small><small>Qarz: '+usd(c.debtUsd)+' USD</small><button onclick="openC('+i+')">Kartochkani ochish</button></div>');bounds.push([Number(c.lat),Number(c.lon)])});
  const b=L.latLngBounds(bounds);if(b.isValid())clientMapObj.fitBounds(b.pad(.15),{maxZoom:13,animate:false});clientMapObj.invalidateSize(false);setTimeout(function(){if(clientMapObj&&currentPage()===2)clientMapObj.invalidateSize(false)},250);
 }catch(e){box.innerHTML='<div id="clientmap-ld">Xarita yuklanmadi: '+esc(e.message||'Internetni tekshiring')+'</div>'}
}

openC=async function(i){
 const c=REAL_CLIENTS[i];if(!c)return;sh.innerHTML='<div style="width:44px;height:5px;border-radius:5px;background:var(--line);margin:0 auto 14px"></div><div style="padding:22px;text-align:center;color:var(--mu)">Real mijoz kartasi yuklanmoqda…</div>';sh.classList.add('on');ov.classList.add('on');if(tg&&tg.BackButton)tg.BackButton.show();
 try{
  const d=await req('client_detail',{clientId:c.id}),ev=(d.events||[]).slice(0,8),visits=(d.visits||[]).slice(0,4);
  sh.innerHTML='<div style="width:44px;height:5px;border-radius:5px;background:var(--line);margin:0 auto 14px"></div><div class="kp">'+((d.photoUrl||c.photoUrl)?'<img class="pm-cphoto" src="'+esc(d.thumbUrl||c.thumbUrl||d.photoUrl||c.photoUrl)+'" data-full="'+esc(d.photoUrl||c.photoUrl)+'" alt="" decoding="async" onclick="pmPhoto(this.dataset.full||this.src)" onerror="this.outerHTML=\'<div class=&quot;av&quot; style=&quot;width:56px;height:56px;background:linear-gradient(135deg,#2f7bff,#0b3fae)&quot;>'+esc((d.name||'?')[0])+'</div>\'">':'<div class="av" style="width:56px;height:56px;background:linear-gradient(135deg,#2f7bff,#0b3fae)">'+esc((d.name||'?')[0])+'</div>')+'<div style="flex:1"><b style="font-size:18px">'+esc(d.name||'Mijoz')+'</b><small>📍 '+esc(d.address||'Manzil kiritilmagan')+'</small></div><span class="pill '+(Number(d.debtUsd||0)>0?'p-wa':'p-ok')+'">'+(Number(d.debtUsd||0)>0?'Qarzdor':'Yopiq')+'</span></div>'+
  '<div class="three" style="margin:16px 0"><div class="c" style="margin:0"><small style="color:var(--mu);font-size:11px">Qarzdorlik</small><b style="display:block;font-size:17px">'+usd(d.debtUsd)+' $</b></div><div class="c" style="margin:0"><small style="color:var(--mu);font-size:11px">Realizatsiya</small><b style="display:block;font-size:14px;margin-top:3px">'+usd(d.totals&&d.totals.deliveredUsd)+' $</b></div><div class="c" style="margin:0"><small style="color:var(--mu);font-size:11px">To‘langan</small><b style="display:block;font-size:17px">'+usd(d.totals&&d.totals.paidUsd)+' $</b></div></div>'+
  '<div class="tl"><span>📞 Telefon</span><b>'+esc(d.phone||'—')+'</b></div><div class="tl"><span>👤 Mas’ul agent</span><b>'+esc(d.agent||'—')+'</b></div><div class="tl"><span>🗒 Izoh</span><b>'+esc(d.comment||'—')+'</b></div>'+
  '<h3 style="margin:16px 0 4px;font-size:14px">So‘nggi operatsiyalar</h3>'+(ev.length?ev.map(function(x){return '<div class="tl"><span>'+esc(kindLabel(x.kind))+'<br><small>'+esc(x.actor||'—')+' · '+clock(x.ts)+'</small></span><b>'+(Number(x.amountUsd||0)?usd(x.amountUsd)+' $':(x.qty?x.qty+' dona':'—'))+'</b></div>'}).join(''):'<div class="tl"><small>Operatsiya yo‘q</small></div>')+
  (visits.length?'<h3 style="margin:16px 0 4px;font-size:14px">Tashriflar</h3>'+visits.map(function(v){return '<div class="tl"><span>'+esc(v.status||'Tashrif')+'<br><small>'+esc(v.actor||'—')+' · '+clock(v.ts)+'</small></span>'+(v.photoUrl?'<img class="pm-vphoto" src="'+esc(v.thumbUrl||v.photoUrl)+'" data-full="'+esc(v.photoUrl)+'" alt="" loading="lazy" decoding="async" onclick="pmPhoto(this.dataset.full||this.src)">':'<small>'+esc(v.note||'')+'</small>')+'</div>'}).join(''):'')+'<div class="btn g" style="margin-top:16px" onclick="closeS()">Yopish</div>';
 }catch(e){sh.innerHTML='<div style="padding:22px"><b>Real ma’lumot ochilmadi</b><small style="display:block;color:var(--mu);margin-top:8px">'+esc(e.message)+'</small></div>'}
};

function renderCash(){
 if(!REAL_MODE)return;
 const start=Number(REAL_DASH.todayStart||0);let rows=REAL_TX.filter(function(t){if(kf===2)return t.type==='handover'&&t.state==='pending';const ts=Number(eventTs(t)||0);return kf===0?ts>=start:ts>=start-6*86400}).slice(0,100);
 kmlist.innerHTML=rows.map(function(t){
  if(t.type==='expense'){
   const som=t.currency==='UZS'&&Number(t.amountUzs||0)?Number(t.amountUzs).toLocaleString('en-US')+' UZS':'';
   const cm=String(t.category||'Kassa rasxodi').match(/^([^\p{L}\p{N}]*)(.*)$/u),cic=(cm&&cm[1].trim())||'📦',ctitle=(cm&&cm[2].trim())||'Kassa rasxodi';
   return '<div class="row" style="margin:0 0 8px;cursor:default"><div class="ic">'+esc(cic)+'</div><div class="t"><b>'+esc(ctitle)+(t.payFrom==='card'?' · 💳 karta':'')+'</b><small>'+esc([t.recipient?('Kimga: '+t.recipient):'',t.cashier?('Kassir: '+t.cashier):''].filter(Boolean).join(' · '))+'</small><small>'+clock(t.ts)+'</small></div><div class="am"><b class="bad">−'+(som?esc(som)+'</b><small class="muted" style="display:block;text-align:right">≈ '+usd(t.amountUsd)+' USD</small>':usd(t.amountUsd)+' USD</b>')+'<span class="pill p-bad">Rasxod</span></div></div>';
  }
  const accepted=t.state==='accepted',rejected=t.state==='rejected',label=accepted?'Qabul qilindi':rejected?'Rad etildi':'Kutilmoqda',pill=accepted?'p-ok':rejected?'p-bad':'p-wa',sign=accepted?'+':'';
  return '<div class="row" style="margin:0 0 8px;cursor:default"><div class="ic">🪙</div><div class="t"><b>'+esc(t.agent||'Agent')+'</b><small>'+(t.cashier?'Kassir: '+esc(t.cashier):'Kassa topshirig‘i')+'</small><small>'+clock(eventTs(t))+'</small></div><div class="am">'+(Number(t.amountUzs||0)>0?'<b class="'+(accepted?'ok':rejected?'bad':'')+'">'+sign+Math.round(Number(t.amountUzs)).toLocaleString('en-US')+' so‘m</b><small class="muted" style="display:block;text-align:right">≈ '+usd(t.amountUsd)+' USD</small>':'<b class="'+(accepted?'ok':rejected?'bad':'')+'">'+sign+usd(t.amountUsd)+' USD</b>')+'<span class="pill '+pill+'">'+label+'</span></div></div>';
 }).join('')||'<div style="text-align:center;color:var(--mu);padding:16px">Operatsiya yo‘q</div>';
 const badge=document.querySelectorAll('section')[3].querySelector('.c h3 .pill');if(badge)setText(badge,rows.length+' ta');
}
renderK=renderCash;confirmP=function(){toast('🔒 Pul topshiriqlarini kassir Kassir ilovasida tasdiqlaydi.')};

function updateCash(d){
 const c=d.cash||{},sec=document.querySelectorAll('section')[3];sec.querySelectorAll('.bal').forEach(function(x){setText(x,usd(c.balanceUsd))});
 const cards=sec.querySelectorAll('.bd > .three .c'),vals=[c.acceptedWeekUsd,c.expensesWeekUsd,c.netWeekUsd];vals.forEach(function(v,i){if(cards[i])setText(cards[i].querySelector('b'),usd(v))});
 const start=Number(d.todayStart||0)-6*86400,agg={};REAL_TX.filter(function(t){return t.type==='expense'&&Number(t.ts||0)>=start}).forEach(function(t){const k=t.category||'Boshqa xarajat';agg[k]=(agg[k]||0)+Number(t.amountUsd||0)});
 const items=Object.keys(agg).map(function(k){return [k,agg[k]]}).sort(function(a,b){return b[1]-a[1]}).slice(0,4),mx=Math.max.apply(null,[1].concat(items.map(function(x){return x[1]})));
 xbrk.innerHTML=items.length?items.map(function(x){const cm=String(x[0]).match(/^([^\p{L}\p{N}]*)(.*)$/u);return '<div class="xr"><b>'+esc((cm&&cm[1].trim())||'📦')+' '+esc((cm&&cm[2].trim())||x[0])+'</b><div><u style="width:'+Math.max(8,x[1]/mx*100)+'%;background:#1f6bff"></u></div><em>'+usd(x[1])+' $</em></div>'}).join(''):'<div style="color:var(--mu);font-size:12px">7 kunda USD xarajat yo‘q.</div>';
 tog(kseg,function(i){kf=i;renderCash()});kf=1;renderCash();
}

function reportSeg(i){
 const box=$('rcustom'),lab=$('rlabel');if(box)box.style.display=i===3?'grid':'none';
 if(i===4){go(1);return}
 if(i===0||i===1){if(lab)setText(lab,'');renderReport(i===0?'today':'week');return}
 if(i===3){const f=$('rFrom'),t=$('rTo');if(f&&!f.value){const n=new Date(),p=function(x){return String(x).padStart(2,'0')};t.value=n.getFullYear()+'-'+p(n.getMonth()+1)+'-'+p(n.getDate());f.value=n.getFullYear()+'-'+p(n.getMonth()+1)+'-01'}if($('rGo'))$('rGo').onclick=function(){loadPeriod('custom')};return}
 loadPeriod('month');
}
async function loadPeriod(period){
 const lab=$('rlabel'),arg={period:period};if(period==='custom'){arg.from=$('rFrom').value;arg.to=$('rTo').value;if(!arg.from||!arg.to){toast('Sanalarni tanlang');return}}
 if(lab)setText(lab,'Yuklanmoqda…');
 try{const rep=await req('period_report',arg);if(lab)setText(lab,'📅 '+rep.label);renderReport(rep)}catch(e){if(lab)setText(lab,'');toast('⚠️ '+e.message)}
}
function renderReport(period){
 const d=REAL_DASH,rep=typeof period==='object'?period:(d&&d.reports&&d.reports[period]);if(!rep)return;const sec=document.querySelectorAll('section')[4],s=d.summary||{};
 const top=sec.querySelectorAll('.hd > .three .hb');if(top[0]){setText(top[0].querySelector('b'),s.workingAgents||0);setText(top[0].querySelectorAll('small')[1],'Jami: '+(s.agentCount||0))}if(top[1]){setText(top[1].querySelector('b'),s.overdueClients||0);setText(top[1].querySelectorAll('small')[1],'5+ kun')}if(top[2]){setText(top[2].querySelector('b'),usd(s.debtUsd)+'$');setText(top[2].querySelectorAll('small')[1],'USD')}
 const first=sec.querySelector('.bd > .two'),fc=first?first.querySelectorAll('.c.kp'):[];if(fc[0]){setText(fc[0].querySelector('small'),'To‘lov / realizatsiya');setText(fc[0].querySelector('b'),rep.paymentToDeliveryPct==null?'—':rep.paymentToDeliveryPct+'%');setText(fc[0].querySelector('em'),usd(rep.paymentsUsd)+' / '+usd(rep.deliveredUsd)+' $')}if(fc[1]){const v=Number(rep.netReceivableChangeUsd||0);setText(fc[1].querySelector('small'),'Davr qarz o‘zgarishi');setText(fc[1].querySelector('b'),(v>0?'+':'')+usd(v)+' $');const e=fc[1].querySelector('em');setText(e,delta(v,rep.previous&&rep.previous.netReceivableChangeUsd));e.className=v<=0?'ok':'bad'}
 const status=Array.from(sec.querySelectorAll('.c')).find(function(x){const h=x.querySelector('h3');return h&&h.textContent.indexOf('Mijozlar holati')>=0});if(status){const counts=[s.freshClients||0,s.yellowClients||0,s.overdueClients||0,s.scheduledClients||0],total=Math.max(1,counts.reduce(function(a,b){return a+b},0));status.querySelectorAll('.st b').forEach(function(b,i){setText(b,counts[i]||0)});status.querySelectorAll('.sb i').forEach(function(el,i){el.style.flex=String(Math.max(1,Math.round((counts[i]||0)/total*100)))})}
 const main=Array.from(sec.querySelectorAll('.c')).find(function(x){const h=x.querySelector('h3');return h&&h.textContent.indexOf('Asosiy ko')===0});if(main){const cs=main.querySelectorAll('.c.kp'),prev=rep.previous||{},vals=[[usd(rep.deliveredUsd)+' $',delta(rep.deliveredUsd,prev.deliveredUsd)],[usd(rep.paymentsUsd)+' $',delta(rep.paymentsUsd,prev.paymentsUsd)],[rep.visits||0,delta(rep.visits,prev.visits)],[rep.newClients||0,delta(rep.newClients,prev.newClients)],[(Number(rep.workSeconds||0)/3600).toFixed(1)+' soat','Real smena'],[Number(rep.distanceKm||0).toFixed(1)+' km','Real GPS']];vals.forEach(function(v,i){if(!cs[i])return;setText(cs[i].querySelector('b'),v[0]);setText(cs[i].querySelector('em'),v[1])})}
 const fin=Array.from(sec.querySelectorAll('.c')).find(function(x){const h=x.querySelector('h3');return h&&h.textContent.indexOf('Moliyaviy')>=0});if(fin){const cs=fin.querySelectorAll('.c.kp'),vals=[rep.acceptedCashUsd,rep.cashierExpensesUsd,rep.returnsUsd];vals.forEach(function(v,i){if(cs[i])setText(cs[i].querySelector('b'),usd(v))})}
 const prod=Array.from(sec.querySelectorAll('.c')).find(function(x){const h=x.querySelector('h3');return h&&h.textContent.indexOf('Mahsulotlar')>=0});if(prod){window.__pmRep=rep;window.__pmRepLabel=typeof period==='object'?rep.label:({today:'Bugun',week:'So‘nggi 7 kun',month:'So‘nggi 30 kun'}[period]||'');prod.classList.add('pm-tap');prod.onclick=function(){if(window.pmProducts)window.pmProducts()};const ps=(rep.products||[]).slice(0,4),ul=prod.querySelector('ul'),txt=prod.querySelector('svg text'),circles=prod.querySelectorAll('svg circle');if(txt)setText(txt,usd(rep.deliveredUsd)+'$');if(ul)ul.innerHTML=ps.length?ps.map(function(p,i){return '<li>'+['🔵','🟣','🟢','🟠'][i]+' '+esc(p.name||('Mahsulot '+(i+1)))+'<b>'+Number(p.sharePct||0).toFixed(1)+'%</b></li>'}).join(''):'<li>Bu davrda realizatsiya yo‘q</li>';let off=0;circles.forEach(function(c,i){const sh=ps[i]?Number(ps[i].sharePct||0):0;c.setAttribute('stroke-dasharray',sh+' 100');c.setAttribute('stroke-dashoffset',String(-off));off+=sh})}
 const series=typeof period==='object'?((rep.series&&rep.series.length)?rep.series:[{day:rep.label||'Davr',deliveredUsd:rep.deliveredUsd}]):period==='week'?(d.reports.series||[]):[{day:period==='today'?'Bugun':'30 kun',deliveredUsd:rep.deliveredUsd}],mx=Math.max.apply(null,[1].concat(series.map(function(x){return Number(x.deliveredUsd||0)})));const dense=series.length>10,every=Math.ceil(series.length/8);bars.innerHTML=series.map(function(x,k){const v=Number(x.deliveredUsd||0);return '<div title="'+esc(x.day||'')+': '+usd(v)+' $"><i style="height:'+Math.max(v?4:1,v/mx*100)+'px"></i>'+(dense?'':usd(v)+'<br>')+(!dense||k%every===0?esc(x.day||''):'&nbsp;')+'</div>'}).join('');
 const dh=bars.parentNode&&bars.parentNode.querySelector('h3');if(dh){const unit=typeof period==='object'?(rep.seriesUnit||'kunlik'):'kunlik';dh.textContent=typeof period==='object'?('Dinamika · '+unit+' · '+(rep.label||'')):period==='today'?'Bugungi realizatsiya':'7 kunlik dinamika'}
 const ranks=(rep.agents||[]).slice().sort(function(a,b){return Number(b.deliveredUsd||0)-Number(a.deliveredUsd||0)}).slice(0,8),rmax=Math.max.apply(null,[1].concat(ranks.map(function(x){return Number(x.deliveredUsd||0)})));rblist.innerHTML=ranks.map(function(r,i){const score=Math.round(Number(r.deliveredUsd||0)/rmax*100);return '<div class="row" style="margin:0 0 8px"><div class="rk g'+Math.min(i+1,3)+'">'+(i+1)+'</div><div class="t"><b>'+esc(r.agent||'Agent')+'</b><small>'+Number(r.visits||0)+' tashrif · '+Number(r.newClients||0)+' yangi mijoz</small><div class="bar"><u style="width:'+score+'%"></u></div></div><div class="am"><b>'+usd(r.deliveredUsd)+' $</b><span class="ok" style="font-size:11px">'+usd(r.paymentsUsd)+' $ olindi</span></div></div>'}).join('')||'<div style="color:var(--mu);padding:12px">Agent statistikasi yo‘q.</div>';
}

go=function(i){baseGo(i);if(!REAL_MODE)return;if(i===1)setTimeout(renderAgentMap,90);if(i===2)setTimeout(renderClientMap,90)};

const PM_HOOKS=[];
window.PremiumReal={req:req,reload:loadReal,clients:function(){return REAL_CLIENTS},agents:function(){return REAL_AGENTS},data:function(){return REAL_DASH},onLoad:function(f){PM_HOOKS.push(f);if(REAL_DASH){try{f(REAL_DASH)}catch(e){}}}};
async function loadReal(silent){
 try{
  const d=await req('dashboard');if(!d||d.readOnly!==true)throw new Error('Manager API read-only javob bermadi.');
  REAL_MODE=true;REAL_DASH=d;REAL_CLIENTS=Array.isArray(d.clients)?d.clients:[];REAL_AGENTS=Array.isArray(d.agents)?d.agents:[];REAL_TX=Array.isArray(d.transactions)?d.transactions:[];
  markReal();preloadAgentPhotos();updateHome(d);refreshAgents(d);refreshClients(d);updateCash(d);renderReport('week');tog(rseg,function(i){reportSeg(i)});
  if(currentPage()===1)setTimeout(renderAgentMap,80);if(currentPage()===2)setTimeout(renderClientMap,80);
  if(window.pmReady)window.pmReady();
  if(!silent)toast('✅ Haqiqiy ma’lumotlar yangilandi');
  PM_HOOKS.forEach(function(f){try{f(d)}catch(e){console.error(e)}});
 }catch(e){REAL_MODE=false;document.querySelectorAll('.live').forEach(function(x){x.textContent='● DEMO'});if(window.pmFail&&document.getElementById('sp'))window.pmFail(e.message);else toast('⚠️ Real data: '+e.message)}
}

sync=function(b){if(b){b.style.transition='transform .8s';b._r=(b._r||0)+360;b.style.transform='rotate('+b._r+'deg)'}loadReal(true).then(function(){toast('🔄 Haqiqiy ma’lumotlar yangilandi')})};

if(tg&&tg.initData){loadReal(true)}
else{
 document.querySelectorAll('.live').forEach(function(x){x.textContent='● DEMO'});if(window.pmReady)window.pmReady();
 const a=$('ymap'),c=$('clientmap');if(a)a.innerHTML='<div id="ymap-ld">Real xarita Telegram botdagi 📱 Rahbar Mini App ichida ochiladi.</div>';if(c)c.innerHTML='<div id="clientmap-ld">Real mijoz xaritasi Telegram botdagi 📱 Rahbar Mini App ichida ochiladi.</div>';
 setTimeout(function(){toast('ℹ️ Real data uchun Telegram botdagi 🧪 Rahbar Premium TEST tugmasidan oching')},1800);
}
})();
