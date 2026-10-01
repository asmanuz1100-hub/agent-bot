(function(){
'use strict';

const REAL_API='https://asman-agent-test.onrender.com/api/manager';
let REAL_MODE=false;
let REAL_DASH=null;
let REAL_CLIENTS=[];
let REAL_AGENTS=[];
let REAL_TX=[];
const baseToast=toast;

function esc(v){return String(v==null?'':v).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]})}
function usd(v){return Number(v||0).toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2})}
function setText(el,v){if(!el)return;el.textContent=String(v);try{delete el._m}catch(e){}}
function clock(ts){if(!ts)return '—';try{return new Date(Number(ts)*1000).toLocaleString('uz-UZ',{timeZone:'Asia/Tashkent',day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'})}catch(e){return '—'}}
function ageLabel(c){if(!c)return '0–2 kun';if(c.age==='red')return '5+ kun';if(c.age==='yellow')return '3–4 kun';if(c.age==='scheduled')return 'Rejada';return '0–2 kun'}
function statusLabel(a){if(a&&a.status==='active')return 'Faol';if(a&&a.status==='late')return 'Kechikkan';return 'Boshqaruv'}
function validCoord(a,b){return Number.isFinite(Number(a))&&Number.isFinite(Number(b))&&Math.abs(Number(a))<=90&&Math.abs(Number(b))<=180}
function pct(cur,prev){cur=Number(cur||0);prev=Number(prev||0);if(!prev)return null;return ((cur-prev)/Math.abs(prev))*100}
function deltaText(cur,prev){const p=pct(cur,prev);if(p==null)return 'Oldingi davr: ma’lumot yo‘q';return (p>=0?'↑ +':'↓ ')+p.toFixed(1)+'% oldingi davrga'}
function kindLabel(k){return ({delivery:'Tovar berildi',payment:'Qarz to‘lovi',return:'Tovar qaytdi',sold:'Sotildi',order:'Buyurtma',visit:'Tashrif'})[k]||k||'Operatsiya'}

toast=function(m){if(REAL_MODE&&String(m).indexOf('Abduvoxid: Nur savdo')>=0)return;baseToast(m)};

async function req(action,arg){
  if(!tg||!tg.initData)throw new Error('Real ma’lumot faqat Telegram botdagi 🧪 Rahbar Premium TEST orqali ochiladi.');
  const payload={initData:tg.initData,action:action};
  if(arg&&typeof arg==='object')Object.assign(payload,arg);
  const ctl=new AbortController(),timer=setTimeout(function(){ctl.abort()},45000);
  try{
    const r=await fetch(REAL_API,{method:'POST',headers:{'Content-Type':'application/json'},cache:'no-store',signal:ctl.signal,body:JSON.stringify(payload)});
    const d=await r.json();
    if(!r.ok)throw new Error(d.error||('API xatosi '+r.status));
    return d;
  }finally{clearTimeout(timer)}
}

function markReal(){
  document.querySelectorAll('.live').forEach(function(x){x.textContent='● REAL DATA'});
}

function updateHome(d){
  const s=d.summary||{},c=d.cash||{},home=document.querySelectorAll('section')[0];
  document.querySelectorAll('.bal').forEach(function(x){setText(x,usd(c.balanceUsd))});
  document.querySelectorAll('.pend').forEach(function(x){setText(x,usd(c.pendingUsd))});
  const grid=home.querySelector('.bd > .two');
  const cards=grid?grid.querySelectorAll('.c.kp'):[];
  const vals=[
    [s.agentCount||0,'● '+(s.workingAgents||0)+' tasi ishda'],
    [d.clientCount||REAL_CLIENTS.length,'● '+(s.newClientsToday||0)+' ta yangi bugun'],
    [s.visitsToday||0,'Agentlar qaydi'],
    [s.overdueClients||0,'● 5+ kun tashrifsiz']
  ];
  vals.forEach(function(v,i){if(!cards[i])return;setText(cards[i].querySelector('b'),v[0]);setText(cards[i].querySelector('em'),v[1])});
  const bad=home.querySelector('.al.r .bad');if(bad)setText(bad,(s.overdueClients||0)+' ta');
  if(typeof pal!=='undefined')setText(pal,usd(c.pendingUsd)+' USD tasdiq kutmoqda');
  if(typeof pas!=='undefined')setText(pas,(c.pendingCount||0)+' ta operatsiya kassir tasdig‘ida');

  const plan=home.querySelector('.plan');
  const today=d.reports&&d.reports.today;
  if(plan&&today){
    const ratio=today.paymentToDeliveryPct==null?0:Number(today.paymentToDeliveryPct);
    const title=plan.querySelector('div[style*="flex:1"] > b');if(title)setText(title,'Bugungi tushum / realizatsiya');
    const sub=plan.querySelector('div[style*="flex:1"] > small');if(sub)setText(sub,usd(today.paymentsUsd)+' $ / '+usd(today.deliveredUsd)+' $');
    const ring=plan.querySelector('.rg text');if(ring)setText(ring,Math.round(ratio)+'%');
    const ringCircle=plan.querySelector('.rg .v');if(ringCircle)ringCircle.style.strokeDashoffset=226*(1-Math.min(100,ratio)/100);
    const box=plan.querySelector('div[style*="flex:1"]');
    if(box){
      box.querySelectorAll('.pr').forEach(function(x){x.remove()});
      const rows=(today.agents||[]).slice().sort(function(a,b){return Number(b.deliveredUsd||0)-Number(a.deliveredUsd||0)}).slice(0,3);
      rows.forEach(function(a){
        const r=Number(a.deliveredUsd||0)>0?Math.min(100,Number(a.paymentsUsd||0)/Number(a.deliveredUsd||0)*100):0;
        box.insertAdjacentHTML('beforeend','<div class="pr"><span>'+esc(a.agent||'Agent')+'</span><div><u style="width:'+r.toFixed(0)+'%"></u></div><em>'+r.toFixed(0)+'%</em></div>');
      });
    }
  }
}

function refreshAgentUi(d){
  const by=new Map(((d.reports&&d.reports.today&&d.reports.today.agents)||[]).map(function(x){return [Number(x.agentId),x]}));
  AG.splice(0,AG.length);
  AG_LL.splice(0,AG_LL.length);
  REAL_AGENTS.forEach(function(a){
    const r=by.get(Number(a.id))||{};
    const gps=a.lastGpsTs?Math.max(0,Math.floor((Date.now()/1000-Number(a.lastGpsTs))/60)):null;
    const where=a.locationSource==='none'?'GPS yo‘q':(gps==null?'GPS yo‘q':gps+' daqiqa oldin');
    AG.push([a.name||String(a.id),where,Number(a.done||0),Number(r.newClients||0),statusLabel(a)]);
    AG_LL.push(validCoord(a.lat,a.lon)?[Number(a.lat),Number(a.lon)]:[NaN,NaN]);
  });
  al();
  tog(agch,function(i){al(['','Faol','Kechikkan','Boshqaruv'][i])});
  if(AG.length)selA(Math.min(selAgent,AG.length-1));
}

function refreshClientUi(d){
  CL.splice(0,CL.length);
  CL_LL.splice(0,CL_LL.length);
  REAL_CLIENTS.forEach(function(c){
    CL.push([c.name||'Mijoz',c.address||c.agent||'Manzil yo‘q',c.status||'Mijoz',Number(c.debtUsd||0),ageLabel(c)]);
    CL_LL.push(validCoord(c.lat,c.lon)?[Number(c.lat),Number(c.lon)]:[NaN,NaN]);
  });
  CH[0][1]=CL.length;
  CH[1][1]=CL.filter(function(c){return c[4]==='0–2 kun'}).length;
  CH[2][1]=CL.filter(function(c){return c[4]==='3–4 kun'}).length;
  CH[3][1]=CL.filter(function(c){return c[4]==='5+ kun'}).length;
  CH[4][1]=CL.filter(function(c){return c[4]==='Rejada'}).length;
  clch.innerHTML=CH.map(function(c,i){return '<button class="'+(i?'':'on')+'">'+c[0]+' <b>'+c[1]+'</b></button>'}).join('');
  cf='';tog(clch,function(i){cf=CH[i][2];rc()});rc();
  const countSpan=document.querySelectorAll('section')[2].querySelector('.c h3 span:last-child');
  if(countSpan)setText(countSpan,(d.clientCount||CL.length)+' mijoz');
}

selA=function(i){
  const a=AG[i];if(!a)return;
  setText(sa_av,(a[0]||'?')[0]);setText(sa_n,a[0]);setText(sa_i,'📍 '+a[1]+' · '+a[2]+' ta tashrif · '+a[3]+' ta yangi mijoz');
  sa_p.className='pill '+(a[4]==='Faol'?'p-ok':a[4]==='Kechikkan'?'p-wa':'p-pri');setText(sa_p,'● '+a[4]);selAgent=i;
  ymapPMs.forEach(function(m,k){if(!m)return;m.setIcon(L.divIcon({className:'',html:'<div class="ymap-pin'+(k===i?' on':'')+'"><b>'+esc((AG[k]&&AG[k][0]||'?')[0])+'</b></div>',iconSize:[38,38],iconAnchor:[19,34]}))});
  const ll=AG_LL[i];if(ymapObj&&ll&&validCoord(ll[0],ll[1]))ymapObj.flyTo(ll,15,{duration:.6});
  scrollTo({top:0,behavior:'smooth'});
};

ymapRoute=function(i){
  const ll=AG_LL[i];if(!ll||!validCoord(ll[0],ll[1])){toast('Bu agentda GPS nuqta yo‘q');return}
  const url='https://www.google.com/maps/dir/?api=1&destination='+ll[0]+','+ll[1];
  if(tg&&tg.openLink)tg.openLink(url);else window.open(url,'_blank');
};

function rebuildMap(){
  if(typeof L==='undefined'||typeof ymap==='undefined')return;
  try{if(ymapObj)ymapObj.remove()}catch(e){}
  ymapObj=null;ymapPMs=[];ymapCPMs=[];ymap.innerHTML='';
  const coords=[];
  REAL_AGENTS.forEach(function(a){if(validCoord(a.lat,a.lon))coords.push([Number(a.lat),Number(a.lon)])});
  REAL_CLIENTS.forEach(function(c){if(validCoord(c.lat,c.lon))coords.push([Number(c.lat),Number(c.lon)])});
  if(!coords.length){ymap.innerHTML='<div id="ymap-ld">Real GPS nuqtalari hozircha yo‘q</div>';return}
  ymapObj=L.map('ymap',{zoomControl:true,attributionControl:true,scrollWheelZoom:false}).setView(coords[0],13);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'© OpenStreetMap'}).addTo(ymapObj);
  ymapPMs=AG.map(function(a,i){
    const ll=AG_LL[i];if(!ll||!validCoord(ll[0],ll[1]))return null;
    const icon=L.divIcon({className:'',html:'<div class="ymap-pin'+(i===selAgent?' on':'')+'"><b>'+esc((a[0]||'?')[0])+'</b></div>',iconSize:[38,38],iconAnchor:[19,34]});
    const m=L.marker(ll,{icon:icon}).addTo(ymapObj);m.on('click',function(){selA(i)});return m;
  });
  const colors={red:'#f0384f',yellow:'#f59e0b',scheduled:'#8b5cf6',fresh:'#16b364',unknown:'#6b7a99'};
  ymapCPMs=REAL_CLIENTS.map(function(c,i){
    if(!validCoord(c.lat,c.lon))return null;
    const icon=L.divIcon({className:'',html:'<div class="ymap-dot" style="background:'+(colors[c.age]||'#6b7a99')+'"></div>',iconSize:[16,16],iconAnchor:[8,8]});
    const m=L.marker([Number(c.lat),Number(c.lon)],{icon:icon}).addTo(ymapObj);
    m.bindPopup('<div class="ymap-bln"><b>'+esc(c.name||'Mijoz')+'</b><small>📍 '+esc(c.address||'Manzil yo‘q')+' · Qarz: '+usd(c.debtUsd)+' $</small><button onclick="openC('+i+')">Mijoz kartasi</button></div>');
    return m;
  });
  const marks=ymapPMs.concat(ymapCPMs).filter(Boolean);
  if(marks.length>1){try{ymapObj.fitBounds(L.featureGroup(marks).getBounds().pad(.12),{maxZoom:14})}catch(e){}}
}

openC=async function(i){
  const c=REAL_CLIENTS[i];if(!c)return;
  sh.innerHTML='<div style="width:44px;height:5px;border-radius:5px;background:var(--line);margin:0 auto 14px"></div><div style="padding:22px;text-align:center;color:var(--mu)">Real mijoz kartasi yuklanmoqda…</div>';
  sh.classList.add('on');ov.classList.add('on');if(tg&&tg.BackButton)tg.BackButton.show();
  try{
    const d=await req('client_detail',{clientId:c.id});
    const ev=(d.events||[]).slice(0,6);
    const visits=(d.visits||[]).slice(0,3);
    sh.innerHTML='<div style="width:44px;height:5px;border-radius:5px;background:var(--line);margin:0 auto 14px"></div>'+
      '<div class="kp"><div class="av" style="width:56px;height:56px;background:linear-gradient(135deg,#2f7bff,#0b3fae)">'+esc((d.name||'?')[0])+'</div><div style="flex:1"><b style="font-size:18px">'+esc(d.name||'Mijoz')+'</b><small>📍 '+esc(d.address||'Manzil kiritilmagan')+'</small></div><span class="pill '+(Number(d.debtUsd||0)>0?'p-wa':'p-ok')+'">'+(Number(d.debtUsd||0)>0?'Qarzdor':'Yopiq')+'</span></div>'+
      '<div class="three" style="margin:16px 0"><div class="c" style="margin:0"><small style="color:var(--mu);font-size:11px">Qarzdorlik</small><b style="display:block;font-size:17px">'+usd(d.debtUsd)+' $</b></div><div class="c" style="margin:0"><small style="color:var(--mu);font-size:11px">Realizatsiya</small><b style="display:block;font-size:14px;margin-top:3px">'+usd(d.totals&&d.totals.deliveredUsd)+' $</b></div><div class="c" style="margin:0"><small style="color:var(--mu);font-size:11px">To‘langan</small><b style="display:block;font-size:17px">'+usd(d.totals&&d.totals.paidUsd)+' $</b></div></div>'+
      '<div class="tl"><span>📞 Telefon</span><b>'+esc(d.phone||'—')+'</b></div><div class="tl"><span>👤 Mas’ul agent</span><b>'+esc(d.agent||'—')+'</b></div><div class="tl"><span>🗒 Izoh</span><b>'+esc(d.comment||'—')+'</b></div>'+
      '<h3 style="margin:16px 0 4px;font-size:14px">So‘nggi operatsiyalar</h3>'+
      (ev.length?ev.map(function(x){return '<div class="tl"><span>'+esc(kindLabel(x.kind))+'<br><small>'+esc(x.actor||'—')+' · '+clock(x.ts)+'</small></span><b>'+(Number(x.amountUsd||0)?usd(x.amountUsd)+' $':(x.qty?x.qty+' dona':'—'))+'</b></div>'}).join(''):'<div class="tl"><small>Operatsiya yo‘q</small></div>')+
      (visits.length?'<h3 style="margin:16px 0 4px;font-size:14px">Tashriflar</h3>'+visits.map(function(v){return '<div class="tl"><span>'+esc(v.status||'Tashrif')+'<br><small>'+esc(v.actor||'—')+' · '+clock(v.ts)+'</small></span><small>'+esc(v.note||'')+'</small></div>'}).join(''):'')+
      '<div class="btn g" style="margin-top:16px" onclick="closeS()">Yopish</div>';
  }catch(e){sh.innerHTML='<div style="padding:22px"><b>Real ma’lumot ochilmadi</b><small style="display:block;color:var(--mu);margin-top:8px">'+esc(e.message)+'</small></div>'}
};

function txTime(t){return Number(t.acceptedTs||t.ts||0)}
function renderRealKassa(){
  if(!REAL_MODE)return;
  const start=Number(REAL_DASH.todayStart||0);
  let rows=REAL_TX.slice();
  if(kf===0)rows=rows.filter(function(t){return txTime(t)>=start});
  else if(kf===1)rows=rows.filter(function(t){return txTime(t)>=start-6*86400});
  else rows=rows.filter(function(t){return t.type==='handover'&&t.state==='pending'});
  rows=rows.slice(0,80);
  kmlist.innerHTML=rows.map(function(t){
    const expense=t.type==='expense',pendingTx=t.state==='pending';
    const title=expense?(t.category||'Xarajat'):(t.agent||'Agent');
    const desc=expense?(t.recipient||t.note||'Kassa chiqimi'):(pendingTx?'Kassir tasdig‘ida':'Kassa qabul qilgan');
    let amount='0.00 USD';
    if(Number(t.amountUsd||0))amount=(expense?'-':'+')+usd(t.amountUsd)+' USD';
    else if(Number(t.amountUzs||0))amount=(expense?'-':'+')+Number(t.amountUzs).toLocaleString('en-US')+' UZS';
    const cls=expense?'bad':pendingTx?'':'ok';
    const pill=pendingTx?'p-wa':expense?'p-bad':'p-ok';
    const state=pendingTx?'Kutilmoqda':expense?'Rasxod':'Qabul qilindi';
    return '<div class="row" style="margin:0 0 8px;cursor:default"><div class="ic">'+(expense?'📦':'⬇️')+'</div><div class="t"><b>'+esc(title)+'</b><small>'+esc(desc)+'</small><small>'+clock(txTime(t))+'</small></div><div class="am"><b class="'+cls+'">'+amount+'</b><span class="pill '+pill+'">'+state+'</span></div></div>';
  }).join('')||'<div style="text-align:center;color:var(--mu);padding:16px">Operatsiya yo‘q</div>';
  const badge=document.querySelectorAll('section')[3].querySelector('.c h3 .pill');if(badge)setText(badge,rows.length+' ta');
}
renderK=renderRealKassa;
confirmP=function(){toast('🔒 Test real-data rejimi read-only. Tasdiqlash eski Kassir/Rahbar tizimida qoladi.')};

function updateCash(d){
  const c=d.cash||{},sec=document.querySelectorAll('section')[3];
  sec.querySelectorAll('.bal').forEach(function(x){setText(x,usd(c.balanceUsd))});
  const cards=sec.querySelectorAll('.bd > .three .c');
  const vals=[c.acceptedWeekUsd,c.expensesWeekUsd,c.netWeekUsd];
  vals.forEach(function(v,i){if(cards[i])setText(cards[i].querySelector('b'),usd(v))});
  KH.splice(0,KH.length,...[c.balanceUsd,c.balanceUsd,c.balanceUsd,c.balanceUsd,c.balanceUsd,c.balanceUsd,c.balanceUsd].map(Number));try{kChart()}catch(e){}
  const start=Number(d.todayStart||0)-6*86400,agg={};
  REAL_TX.filter(function(t){return t.type==='expense'&&txTime(t)>=start}).forEach(function(t){
    const k=t.category||'Boshqa xarajat';agg[k]=(agg[k]||0)+Number(t.amountUsd||0);
  });
  const items=Object.keys(agg).map(function(k){return [k,agg[k]]}).sort(function(a,b){return b[1]-a[1]}).slice(0,4);
  xbrk.innerHTML=items.length?items.map(function(x){return '<div class="xr"><b>📦 '+esc(x[0])+'</b><div><u style="width:'+Math.max(8,Math.min(100,x[1]/Math.max.apply(null,items.map(function(y){return y[1]||1}))*100))+'%;background:#1f6bff"></u></div><em>'+usd(x[1])+' $</em></div>'}).join(''):'<div style="color:var(--mu);font-size:12px">7 kunda USD xarajat yo‘q.</div>';
  tog(kseg,function(i){kf=i;renderRealKassa()});kf=1;renderRealKassa();
}

function renderReport(period){
  const d=REAL_DASH,rep=d&&d.reports&&d.reports[period];if(!rep)return;
  const sec=document.querySelectorAll('section')[4],s=d.summary||{};
  const top=sec.querySelectorAll('.hd > .three .hb');
  if(top[0]){setText(top[0].querySelector('b'),s.workingAgents||0);setText(top[0].querySelectorAll('small')[1],'Jami: '+(s.agentCount||0))}
  if(top[1]){setText(top[1].querySelector('b'),s.overdueClients||0);setText(top[1].querySelectorAll('small')[1],'5+ kun')}
  if(top[2]){setText(top[2].querySelector('b'),usd(s.debtUsd)+'$');setText(top[2].querySelectorAll('small')[1],'USD')}
  const first=sec.querySelector('.bd > .two'),firstCards=first?first.querySelectorAll('.c.kp'):[];
  if(firstCards[0]){setText(firstCards[0].querySelector('small'),'To‘lov / realizatsiya');setText(firstCards[0].querySelector('b'),rep.paymentToDeliveryPct==null?'—':rep.paymentToDeliveryPct+'%');setText(firstCards[0].querySelector('em'),usd(rep.paymentsUsd)+' / '+usd(rep.deliveredUsd)+' $')}
  if(firstCards[1]){const v=Number(rep.netReceivableChangeUsd||0);setText(firstCards[1].querySelector('small'),'Davr qarz o‘zgarishi');setText(firstCards[1].querySelector('b'),(v>0?'+':'')+usd(v)+' $');const e=firstCards[1].querySelector('em');setText(e,deltaText(v,rep.previous&&rep.previous.netReceivableChangeUsd));e.className=v<=0?'ok':'bad'}

  const statusCard=Array.from(sec.querySelectorAll('.c')).find(function(x){const h=x.querySelector('h3');return h&&h.textContent.indexOf('Mijozlar holati')>=0});
  if(statusCard){
    const counts=[s.freshClients||0,s.yellowClients||0,s.overdueClients||0,s.scheduledClients||0],total=Math.max(1,counts.reduce(function(a,b){return a+b},0));
    statusCard.querySelectorAll('.st b').forEach(function(b,i){setText(b,counts[i]||0)});
    statusCard.querySelectorAll('.sb i').forEach(function(el,i){el.style.flex=String(Math.max(1,Math.round((counts[i]||0)/total*100)))});
  }

  const main=Array.from(sec.querySelectorAll('.c')).find(function(x){const h=x.querySelector('h3');return h&&h.textContent==='Asosiy ko‘rsatkichlar'||(h&&h.textContent.indexOf('Asosiy ko')===0)});
  if(main){
    const cs=main.querySelectorAll('.c.kp'),prev=rep.previous||{};
    const vals=[
      [usd(rep.deliveredUsd)+' $',deltaText(rep.deliveredUsd,prev.deliveredUsd)],
      [usd(rep.paymentsUsd)+' $',deltaText(rep.paymentsUsd,prev.paymentsUsd)],
      [rep.visits||0,deltaText(rep.visits,prev.visits)],
      [rep.newClients||0,deltaText(rep.newClients,prev.newClients)],
      [(Number(rep.workSeconds||0)/3600).toFixed(1)+' soat','Real GPS/smena'],
      [Number(rep.distanceKm||0).toFixed(1)+' km','Real GPS']
    ];
    vals.forEach(function(v,i){if(!cs[i])return;setText(cs[i].querySelector('b'),v[0]);const em=cs[i].querySelector('em');setText(em,v[1]);em.className=String(v[1]).indexOf('↓')===0?'bad':'ok'});
  }

  const fin=Array.from(sec.querySelectorAll('.c')).find(function(x){const h=x.querySelector('h3');return h&&h.textContent.indexOf('Moliyaviy')>=0});
  if(fin){const cs=fin.querySelectorAll('.c.kp'),vals=[rep.acceptedCashUsd,rep.cashierExpensesUsd,rep.returnsUsd];vals.forEach(function(v,i){if(cs[i])setText(cs[i].querySelector('b'),usd(v))})}

  const prod=Array.from(sec.querySelectorAll('.c')).find(function(x){const h=x.querySelector('h3');return h&&h.textContent.indexOf('Mahsulotlar')>=0});
  if(prod){
    const ps=(rep.products||[]).slice(0,4),ul=prod.querySelector('ul'),txt=prod.querySelector('svg text'),circles=prod.querySelectorAll('svg circle');
    if(txt)setText(txt,usd(rep.deliveredUsd)+'$');
    if(ul)ul.innerHTML=ps.length?ps.map(function(p,i){return '<li>'+['🔵','🟣','🟢','🟠'][i]+' '+esc(p.name||('Mahsulot '+(i+1)))+'<b>'+Number(p.sharePct||0).toFixed(1)+'%</b></li>'}).join(''):'<li>Bu davrda realizatsiya yo‘q</li>';
    let off=0;circles.forEach(function(c,i){const sh=ps[i]?Number(ps[i].sharePct||0):0;c.setAttribute('stroke-dasharray',sh+' 100');c.setAttribute('stroke-dashoffset',String(-off));off+=sh});
  }

  const series=period==='week'?(d.reports.series||[]):[{day:period==='today'?'Bugun':'30 kun',deliveredUsd:rep.deliveredUsd}];
  const mx=Math.max.apply(null,[1].concat(series.map(function(x){return Number(x.deliveredUsd||0)})));
  bars.innerHTML=series.map(function(x){const v=Number(x.deliveredUsd||0);return '<div><i style="height:'+Math.max(4,v/mx*100)+'px"></i>'+usd(v)+'<br>'+esc(x.day||'')+'</div>'}).join('');

  const ranks=(rep.agents||[]).slice().sort(function(a,b){return Number(b.deliveredUsd||0)-Number(a.deliveredUsd||0)}).slice(0,8);
  const rmax=Math.max.apply(null,[1].concat(ranks.map(function(x){return Number(x.deliveredUsd||0)})));
  rblist.innerHTML=ranks.map(function(r,i){const score=Math.round(Number(r.deliveredUsd||0)/rmax*100);return '<div class="row" style="margin:0 0 8px"><div class="rk g'+Math.min(i+1,3)+'">'+(i+1)+'</div><div class="t"><b>'+esc(r.agent||'Agent')+'</b><small>'+Number(r.visits||0)+' tashrif · '+Number(r.newClients||0)+' yangi mijoz</small><div class="bar"><u style="width:'+score+'%"></u></div></div><div class="am"><b>'+usd(r.deliveredUsd)+' $</b><span class="ok" style="font-size:11px">'+usd(r.paymentsUsd)+' $ olindi</span></div></div>'}).join('')||'<div style="color:var(--mu);padding:12px">Agent statistikasi yo‘q.</div>';
}

async function loadReal(silent){
  try{
    const d=await req('dashboard');
    if(!d||d.readOnly!==true)throw new Error('Manager API read-only javob bermadi.');
    REAL_MODE=true;REAL_DASH=d;REAL_CLIENTS=Array.isArray(d.clients)?d.clients:[];REAL_AGENTS=Array.isArray(d.agents)?d.agents:[];REAL_TX=Array.isArray(d.transactions)?d.transactions:[];
    markReal();updateHome(d);refreshAgentUi(d);refreshClientUi(d);updateCash(d);rebuildMap();renderReport('week');
    tog(rseg,function(i){if(i===3){go(1);return}renderReport(['today','week','month'][i]||'week')});
    if(!silent)toast('✅ Haqiqiy ma’lumotlar ulandi');
  }catch(e){
    REAL_MODE=false;
    document.querySelectorAll('.live').forEach(function(x){x.textContent='● DEMO'});
    toast('⚠️ Real data: '+e.message);
  }
}

sync=function(b){if(b){b.style.transition='transform .8s';b._r=(b._r||0)+360;b.style.transform='rotate('+b._r+'deg)'}loadReal(true).then(function(){toast('🔄 Haqiqiy ma’lumotlar yangilandi')})};

if(tg&&tg.initData){
  setTimeout(function(){loadReal(false)},150);
}else{
  setTimeout(function(){toast('ℹ️ Real data uchun Telegram botdagi 🧪 Rahbar Premium TEST tugmasidan oching')},2200);
}
})();