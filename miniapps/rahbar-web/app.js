/* ASMAN · Rahbar web paneli (kompyuter). Telegram'siz: login + parol, so'ng /api/manager bilan bir xil amallar. */
(function(){'use strict';
var API='/api/manager',AUTH='/api/web';
var TOKEN=store('rw-token')||'';
var S={dash:null,me:null,primary:false,page:'',loadedTs:0,maps:{},timer:0,cache:{}};
var $=function(id){return document.getElementById(id)};

/* ---------- helpers ---------- */
function store(k,v){try{if(v===undefined)return localStorage.getItem(k);if(v===null)localStorage.removeItem(k);else localStorage.setItem(k,v)}catch(e){return null}}
function esc(v){return String(v==null?'':v).replace(/[&<>"']/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]})}
function num(n,d){n=Number(n||0);return n.toLocaleString('en-US',{minimumFractionDigits:d||0,maximumFractionDigits:d==null?2:d}).replace(/,/g,' ')}
function usd(n){n=Number(n||0);return (n<0?'−':'')+'$'+num(Math.abs(n),Math.abs(n)%1?2:0)}
function uzs(n){return num(n,0)+' so‘m'}
var TZ='Asia/Tashkent';
function dfmt(ts,opt){if(!ts)return '—';return new Date(ts*1000).toLocaleString('ru-RU',Object.assign({timeZone:TZ},opt))}
function dt(ts){return dfmt(ts,{day:'2-digit',month:'2-digit',year:'numeric',hour:'2-digit',minute:'2-digit'})}
function dday(ts){return dfmt(ts,{day:'2-digit',month:'2-digit',year:'numeric'})}
function hm(ts){return dfmt(ts,{hour:'2-digit',minute:'2-digit'})}
function ago(ts){if(!ts)return '—';var s=Math.max(0,Date.now()/1000-ts);if(s<60)return 'hozir';if(s<3600)return Math.floor(s/60)+' daq oldin';if(s<86400)return Math.floor(s/3600)+' soat oldin';return Math.floor(s/86400)+' kun oldin'}
function hours(sec){var h=Math.floor((sec||0)/3600),m=Math.round(((sec||0)%3600)/60);return h?h+' soat '+m+' daq':m+' daq'}
function initial(name){return esc(String(name||'?').trim().charAt(0).toUpperCase()||'?')}
function avatar(name,url,cls){return '<span class="av '+(cls||'')+'"'+(url?' style="background-image:url(\''+esc(url)+'\')"':'')+'>'+(url?'':initial(name))+'</span>'}
function pill(text,cls){return '<span class="pill '+(cls||'')+'">'+text+'</span>'}
function today(){return new Date(Date.now()+5*3600e3).toISOString().slice(0,10)}
function toast(msg,err){var t=$('toast');t.textContent=msg;t.className='toast on'+(err?' err':'');clearTimeout(toast.t);toast.t=setTimeout(function(){t.className='toast'+(err?' err':'')},err?4200:2600)}
function debounce(fn,ms){var t;return function(){var a=arguments,self=this;clearTimeout(t);t=setTimeout(function(){fn.apply(self,a)},ms)}}

var AGE={fresh:['0–2 kun','p-ok','#12a75b'],yellow:['3–4 kun','p-warn','#d98a06'],red:['5+ kun','p-bad','#e5384f'],scheduled:['Rejada','p-pri','#1f6bff'],unknown:['Noma’lum','','#94a3c4']};
var AG_ST={active:['Faol','p-ok','#12a75b'],late:['Kechikkan','p-warn','#d98a06'],offline:['Yopiq','','#94a3c4']};
var KIND={delivery:'📦 Tovar berildi',payment:'💰 To‘lov',sold:'🛒 Sotildi',return:'↩️ Qaytarildi',order:'📝 Buyurtma',visit:'👣 Tashrif'};
var VISIT={active:'Faol',interested:'Qiziqdi',thinking:'O‘ylab ko‘radi',refused:'Rad etdi',closed:'Yopilgan',no_answer:'Javob yo‘q'};
var FIELD={name:'Mijoz ismi',shop_name:'Do‘kon nomi',phone:'Telefon',address:'Manzil',comment:'Izoh',payment_due:'To‘lov sanasi'};

/* ---------- API ---------- */
function relogin(msg){TOKEN='';store('rw-token',null);S.dash=null;showLogin(msg||'Sessiya tugagan. Qayta kiring.')}
async function post(url,body){
  var ctl=new AbortController(),timer=setTimeout(function(){ctl.abort()},60000);
  try{
    var r=await fetch(url,{method:'POST',cache:'no-store',signal:ctl.signal,
      headers:Object.assign({'Content-Type':'application/json'},TOKEN?{'Authorization':'Bearer '+TOKEN}:{}),body:JSON.stringify(body)});
    var d;try{d=await r.json()}catch(e){throw new Error('Server noto‘g‘ri javob qaytardi.')}
    if(r.status===401&&d.relogin){relogin(d.error);throw new Error(d.error)}
    if(!r.ok)throw new Error(d.error||('Xato '+r.status));
    return d;
  }catch(e){
    if(e.name==='AbortError')throw new Error('Server javob bermadi. Qayta urinib ko‘ring.');
    if(e instanceof TypeError)throw new Error('Internet aloqasi yo‘q yoki server ishlamayapti.');
    throw e;
  }finally{clearTimeout(timer)}
}
function api(action,args){return post(API,Object.assign({action:action},args||{}))}
function auth(action,args){return post(AUTH,Object.assign({action:action},args||{}))}

/* ---------- login ---------- */
function showLogin(msg){
  $('shell').hidden=true;$('login').hidden=false;closeDrawer();closeModal();
  $('lgErr').textContent=msg||'';$('lgPass').value='';setTimeout(function(){($('lgLogin').value?$('lgPass'):$('lgLogin')).focus()},30);
}
$('loginForm').addEventListener('submit',async function(e){
  e.preventDefault();var b=$('lgBtn');b.disabled=true;$('lgErr').textContent='';
  try{
    var d=await auth('login',{login:$('lgLogin').value.trim(),password:$('lgPass').value});
    TOKEN=d.token;store('rw-token',TOKEN);store('rw-login',$('lgLogin').value.trim());await boot();
  }catch(err){$('lgErr').textContent=err.message}
  finally{b.disabled=false}
});

async function boot(){
  if(!TOKEN){$('lgLogin').value=store('rw-login')||'';showLogin();return}
  try{var me=await auth('me')}catch(e){if(TOKEN)showLogin(e.message);return}
  S.me=me.me;S.login=me.login;S.primary=!!me.primaryAdmin;
  $('login').hidden=true;$('shell').hidden=false;
  $('meName').textContent=S.me.name||S.login;$('meAv').outerHTML=avatar(S.me.name,S.me.photoUrl).replace('class="av ','id="meAv" class="av ');
  renderNav();route();
  clearInterval(S.timer);S.timer=setInterval(autoRefresh,60000);
}

/* ---------- navigation ---------- */
var PAGES=[
  ['home','🏠','Asosiy','Bugungi jonli holat'],
  ['agents','🧭','Agentlar','Joylashuv va faoliyat'],
  ['clients','🏪','Mijozlar','Barcha mijozlar va qarzdorlik'],
  ['cash','👛','Kassa','Kirim, chiqim va qoldiq'],
  ['reports','📊','Hisobot','Davr bo‘yicha tahlil'],
  ['warehouse','📦','Ombor','Buyurtmalar va mahsulotlar'],
  ['staff','👥','Xodimlar','Agentlar va kassirlar'],
  ['settings','⚙️','Sozlamalar','Akkaunt va xavfsizlik']
];
function renderNav(){
  var d=S.dash,badge={};
  if(d){badge.warehouse=d.warehouse&&d.warehouse.newOrders;badge.cash=d.summary&&d.summary.pendingCount}
  $('nav').innerHTML=PAGES.map(function(p){return '<button data-p="'+p[0]+'" class="'+(S.page===p[0]?'on':'')+'"><span class="ic">'+p[1]+'</span><span class="lbl">'+p[2]+'</span>'+(badge[p[0]]?'<span class="badge">'+badge[p[0]]+'</span>':'')+'</button>'}).join('');
}
$('nav').addEventListener('click',function(e){var b=e.target.closest('button[data-p]');if(b)location.hash=b.dataset.p});
$('meBtn').onclick=function(){location.hash='settings'};
window.addEventListener('hashchange',route);
function route(){
  if($('shell').hidden)return;
  var p=(location.hash||'').slice(1)||'home';if(!PAGES.some(function(x){return x[0]===p}))p='home';
  S.page=p;var meta=PAGES.find(function(x){return x[0]===p});
  $('pageTitle').textContent=meta[2];$('pageSub').textContent=meta[3];document.title='ASMAN · '+meta[2];
  closeDrawer();renderNav();destroyMaps();render();
}
function destroyMaps(){Object.keys(S.maps).forEach(function(k){if(k==='drawer')return;try{S.maps[k].remove()}catch(e){}delete S.maps[k]})}
async function render(force){
  var p=S.page,page=$('page');
  var needDash=['home','agents','clients','cash'].indexOf(p)>=0;
  if(needDash&&(!S.dash||force)){
    if(!S.dash)page.innerHTML='<div class="grid g4">'+'<div class="skel"></div>'.repeat(4)+'</div>';
    try{await loadDash()}catch(e){if(TOKEN)page.innerHTML='<div class="card empty">'+esc(e.message)+'<br><br><button class="btn" onclick="location.reload()">Qayta urinish</button></div>';return}
    if(S.page!==p)return;
  }
  ({home:pageHome,agents:pageAgents,clients:pageClients,cash:pageCash,reports:pageReports,warehouse:pageWarehouse,staff:pageStaff,settings:pageSettings})[p](page,force);
}
async function loadDash(){S.dash=await api('dashboard');S.loadedTs=Date.now();stamp();renderNav();return S.dash}
function stamp(){$('updated').textContent=S.loadedTs?'Yangilandi '+new Date(S.loadedTs).toLocaleTimeString('ru-RU',{hour:'2-digit',minute:'2-digit'}):''}
async function refresh(){var b=$('refreshBtn');b.disabled=true;try{S.dash=null;S.cache={};await render(true);toast('Ma’lumotlar yangilandi')}finally{b.disabled=false}}
$('refreshBtn').onclick=refresh;
function autoRefresh(){
  if(document.hidden||$('shell').hidden||!$('modalOv').hidden)return;
  if(['home','agents','cash'].indexOf(S.page)<0)return;
  loadDash().then(function(){if(['home','cash'].indexOf(S.page)>=0)render();else if(S.page==='agents')updateAgentsLive()}).catch(function(){});
}
$('themeBtn').onclick=function(){var d=document.documentElement,dark=d.dataset.theme?d.dataset.theme==='dark':matchMedia('(prefers-color-scheme:dark)').matches;d.dataset.theme=dark?'light':'dark';store('rw-theme',d.dataset.theme)};
document.addEventListener('keydown',function(e){
  if(e.key==='Escape'){if(!$('modalOv').hidden)closeModal();else closeDrawer();return}
  if(/INPUT|TEXTAREA|SELECT/.test((e.target.tagName||''))||e.metaKey||e.ctrlKey||e.altKey)return;
  if(e.key==='/'){var s=document.querySelector('.page input[type=search]');if(s){e.preventDefault();s.focus()}}
  else if(e.key==='r'||e.key==='R')refresh();
});

/* ---------- modal / drawer ---------- */
var modalResolve=null;
function modal(html){$('modalBody').innerHTML=html;$('modalOv').hidden=false;var f=$('modalBody').querySelector('input,select,textarea,button.pri');if(f)setTimeout(function(){f.focus()},30);return new Promise(function(r){modalResolve=r})}
function closeModal(v){if($('modalOv').hidden)return;$('modalOv').hidden=true;var r=modalResolve;modalResolve=null;if(r)r(v||null)}
$('modalOv').addEventListener('click',function(e){if(e.target===$('modalOv'))closeModal()});
$('modalBody').addEventListener('click',function(e){var b=e.target.closest('[data-m]');if(!b)return;if(b.dataset.m==='cancel')closeModal()});
$('modalBody').addEventListener('submit',function(e){e.preventDefault();var o={};new FormData(e.target).forEach(function(v,k){o[k]=v});closeModal(o)});
function confirmBox(title,body,okText,danger){return modal('<form><h3>'+esc(title)+'</h3><div>'+body+'</div><div class="foot"><button type="button" class="btn" data-m="cancel">Bekor qilish</button><button class="btn '+(danger?'danger':'pri')+'">'+esc(okText||'Tasdiqlash')+'</button></div></form>').then(function(v){return !!v})}
function formBox(title,fields,okText,note){
  return modal('<form><h3>'+esc(title)+'</h3>'+(note?'<p class="muted">'+note+'</p>':'')+'<div class="form">'+fields.map(function(f){
    var a=' name="'+f.name+'"'+(f.required?' required':'')+(f.type?' type="'+f.type+'"':'')+(f.step?' step="'+f.step+'"':'')+(f.placeholder?' placeholder="'+esc(f.placeholder)+'"':'');
    var input=f.options?'<select'+a+'>'+f.options.map(function(o){return '<option value="'+esc(o[0])+'"'+(String(o[0])===String(f.value)?' selected':'')+'>'+esc(o[1])+'</option>'}).join('')+'</select>'
      :f.area?'<textarea rows="3"'+a+'>'+esc(f.value||'')+'</textarea>':'<input'+a+' value="'+esc(f.value==null?'':f.value)+'">';
    return '<label>'+esc(f.label)+input+'</label>'}).join('')+'</div><div class="foot"><button type="button" class="btn" data-m="cancel">Bekor qilish</button><button class="btn pri">'+esc(okText||'Saqlash')+'</button></div></form>');
}
async function run(fn,okMsg){try{var r=await fn();if(okMsg)toast(okMsg);return r}catch(e){toast(e.message,true);return null}}
function openDrawer(html){$('drawerBody').innerHTML=html;$('drawer').classList.add('on');$('drawerOv').classList.add('on');$('drawer').setAttribute('aria-hidden','false');$('drawer').scrollTop=0}
function closeDrawer(){$('drawer').classList.remove('on');$('drawerOv').classList.remove('on');$('drawer').setAttribute('aria-hidden','true');if(S.maps.drawer){try{S.maps.drawer.remove()}catch(e){}delete S.maps.drawer}}
$('drawerOv').onclick=closeDrawer;$('drawerX').onclick=closeDrawer;
function download(d){
  var bin=atob(d.base64),arr=new Uint8Array(bin.length);for(var i=0;i<bin.length;i++)arr[i]=bin.charCodeAt(i);
  var url=URL.createObjectURL(new Blob([arr],{type:d.mime})),a=document.createElement('a');a.href=url;a.download=d.filename;document.body.appendChild(a);a.click();a.remove();setTimeout(function(){URL.revokeObjectURL(url)},4000);
}

/* ---------- charts ---------- */
function barChart(series,keys,colors,fmt){
  if(!series||!series.length)return '<div class="empty">Ma’lumot yo‘q</div>';
  var W=760,H=220,pl=48,pb=26,pt=10,max=0;
  series.forEach(function(s){keys.forEach(function(k){max=Math.max(max,Number(s[k]||0))})});
  max=max||1;var step=Math.pow(10,Math.floor(Math.log10(max)));var top=Math.ceil(max/step)*step;
  var gw=(W-pl)/series.length,bw=Math.min(28,(gw-10)/keys.length),out='';
  for(var i=0;i<=4;i++){var y=pt+(H-pt-pb)*(1-i/4);out+='<line class="grid-l" x1="'+pl+'" x2="'+W+'" y1="'+y+'" y2="'+y+'"/><text x="'+(pl-8)+'" y="'+(y+4)+'" text-anchor="end">'+esc((fmt||num)(top*i/4))+'</text>'}
  series.forEach(function(s,i){
    var x0=pl+gw*i+(gw-bw*keys.length)/2;
    keys.forEach(function(k,j){var v=Number(s[k]||0),h=(H-pt-pb)*Math.max(0,v)/top;out+='<rect x="'+(x0+j*bw)+'" y="'+(H-pb-h)+'" width="'+(bw-2)+'" height="'+h+'" rx="3" fill="'+colors[j]+'"><title>'+esc(s.day)+': '+esc((fmt||num)(v))+'</title></rect>'});
    if(series.length<=16||i%Math.ceil(series.length/16)===0)out+='<text x="'+(pl+gw*i+gw/2)+'" y="'+(H-8)+'" text-anchor="middle">'+esc(s.day)+'</text>';
  });
  return '<svg class="chart" viewBox="0 0 '+W+' '+H+'" preserveAspectRatio="none" role="img">'+out+'</svg>';
}
function legend(items){return '<div class="legend">'+items.map(function(i){return '<span><i style="background:'+i[1]+'"></i>'+esc(i[0])+'</span>'}).join('')+'</div>'}
function kpi(ic,label,value,sub,cls,go){return '<div class="card kpi'+(go?' click" data-go="'+go:'')+'"><div class="ic">'+ic+'</div><div><small>'+label+'</small><b>'+value+'</b><em class="'+(cls||'')+'">'+(sub||'')+'</em></div></div>'}
function bindGo(root){root.querySelectorAll('[data-go]').forEach(function(el){el.onclick=function(){var g=el.dataset.go.split(':');if(g[1])S.cache.clientAge=g[1];location.hash=g[0]}})}

/* ---------- maps ---------- */
function makeMap(el,key){
  if(!window.L){el.innerHTML='<div class="empty">Xarita yuklanmadi (internetni tekshiring).</div>';return null}
  var m=L.map(el,{zoomControl:true,attributionControl:true}).setView([40.45,71.6],9);
  L.tileLayer('/tiles/{z}/{x}/{y}.png',{maxZoom:19,attribution:'© OpenStreetMap'}).addTo(m);
  S.maps[key]=m;return m;
}
function agentIcon(a,on){var c=(AG_ST[a.status]||AG_ST.offline)[2];return L.divIcon({className:'',html:'<div class="pin" style="background:'+c+(on?';outline:3px solid #1f6bff':'')+'"><b>'+initial(a.name)+'</b></div>',iconSize:[34,34],iconAnchor:[17,34]})}

/* ================= PAGES ================= */

/* ----- Asosiy ----- */
function pageHome(page){
  var d=S.dash,s=d.summary,c=d.cash,rt=d.reports.today;
  var overdue=d.clients.filter(function(x){return x.age==='red'&&!x.blacklisted}).sort(function(a,b){return (b.days||0)-(a.days||0)});
  var pend=d.transactions.filter(function(t){return t.type==='handover'&&t.state==='pending'});
  var alerts='';
  if(overdue.length)alerts+='<div class="alert r" data-go="clients:red"><span class="ic">⏰</span><div><b>'+overdue.length+' ta mijozga 5+ kundan beri tashrif yo‘q</b><small>Eng uzog‘i: '+esc(overdue[0].name)+' · '+(overdue[0].days||0)+' kun</small></div></div>';
  if(pend.length)alerts+='<div class="alert y" data-go="cash"><span class="ic">🪙</span><div><b>'+pend.length+' ta topshiriq kassir tasdig‘ini kutmoqda</b><small>Jami '+usd(s.pendingUsd)+'</small></div></div>';
  if(d.warehouse.newOrders)alerts+='<div class="alert b" data-go="warehouse"><span class="ic">📦</span><div><b>'+d.warehouse.newOrders+' ta yangi buyurtma</b><small>Ochiq buyurtmalar: '+d.warehouse.openOrders+(d.warehouse.missingProducts?' · katalogda yo‘q: '+d.warehouse.missingProducts:'')+'</small></div></div>';
  if(!alerts)alerts='<div class="empty">✅ Hozircha diqqat talab qiladigan holat yo‘q</div>';
  var agents=d.agents.slice().sort(function(a,b){return (b.shiftOpen-a.shiftOpen)||(b.done-a.done)});
  page.innerHTML=
   '<div class="grid g-main" style="margin-bottom:16px">'+
     '<div class="card hero"><div class="grid g3">'+
       '<div><small>Umumiy kassa qoldig‘i</small><b class="big">'+usd(c.balanceUsd)+'</b><div class="muted small">Naqd + karta, USD ekvivalent</div></div>'+
       '<div><small>Bugun qabul qilindi</small><b class="big" style="font-size:26px">'+usd(c.acceptedTodayUsd)+'</b><div class="muted small">Xarajat: '+usd(c.expensesTodayUsd)+'</div></div>'+
       '<div><small>Mijozlar qarzi</small><b class="big" style="font-size:26px">'+usd(s.debtUsd)+'</b><div class="muted small">'+num(d.clientCount)+' ta mijoz</div></div>'+
     '</div></div>'+
     '<div class="card"><div class="card-h"><h3>Diqqat talab qiladi</h3></div>'+alerts+'</div>'+
   '</div>'+
   '<div class="grid g4" style="margin-bottom:16px">'+
     kpi('🧭','Ishdagi agentlar',s.workingAgents+' / '+s.agentCount,'Smena ochiq','ok','agents')+
     kpi('👣','Bugungi tashriflar',num(s.visitsToday),'Barcha agentlar','', 'reports')+
     kpi('➕','Yangi mijozlar',num(s.newClientsToday),'Bugun qo‘shildi','ok','clients')+
     kpi('⚠️','Nazorat kerak',num(s.overdueClients),'5+ kun tashrifsiz','bad','clients:red')+
   '</div>'+
   '<div class="grid g-main">'+
     '<div class="grid">'+
       '<div class="card"><div class="card-h"><h3>Oxirgi 7 kun</h3>'+legend([['Realizatsiya','#1f6bff'],['To‘lovlar','#12a75b']])+'</div>'+barChart(d.reports.series,['deliveredUsd','paymentsUsd'],['#1f6bff','#12a75b'],usd)+'</div>'+
       '<div class="card flush"><div class="card-h"><h3>Bugun agentlar bo‘yicha</h3><a data-go="reports">Batafsil ›</a></div><div class="tbl-wrap" style="margin-top:12px">'+agentReportTable(rt.agents)+'</div></div>'+
     '</div>'+
     '<div class="card"><div class="card-h"><h3>Agentlar holati</h3><a data-go="agents">Xarita ›</a></div><div class="list">'+
       agents.map(function(a){var st=AG_ST[a.status]||AG_ST.offline;return '<div class="li click" data-agent="'+a.id+'">'+avatar(a.name,a.photoUrl)+'<div class="t"><b>'+esc(a.name)+'</b><small>'+(a.shiftOpen?'Smena '+hm(a.shiftStart)+' dan':'Smena yopiq')+' · '+a.done+' tashrif · '+(a.lastGpsTs?'GPS '+ago(a.lastGpsTs):'GPS yo‘q')+'</small></div>'+pill('<span class="dot"></span>'+st[0],st[1])+'</div>'}).join('')+
     '</div></div>'+
   '</div>';
  bindGo(page);bindAgentLinks(page);
}
function agentReportTable(rows){
  if(!rows||!rows.length)return '<div class="empty">Agentlar yo‘q</div>';
  return '<table><thead><tr><th>Agent</th><th class="right">Realizatsiya</th><th class="right">To‘lov</th><th class="right">Tashrif</th><th class="right">Yangi</th><th class="right">Ish vaqti</th><th class="right">Masofa</th></tr></thead><tbody>'+
   rows.map(function(a){return '<tr class="click" data-agent="'+a.agentId+'"><td><b>'+esc(a.agent)+'</b></td><td class="right num">'+usd(a.deliveredUsd)+'</td><td class="right num">'+usd(a.paymentsUsd)+'</td><td class="right num">'+a.visits+'</td><td class="right num">'+a.newClients+'</td><td class="right num">'+hours(a.workSeconds)+'</td><td class="right num">'+num(a.distanceKm,1)+' km</td></tr>'}).join('')+'</tbody></table>';
}
function bindAgentLinks(root){root.querySelectorAll('[data-agent]').forEach(function(el){el.onclick=function(){openAgent(+el.dataset.agent)}})}
function bindClientLinks(root){root.querySelectorAll('[data-client]').forEach(function(el){el.onclick=function(e){if(e.target.closest('a[href]'))return;openClient(+el.dataset.client)}})}

/* ----- Agentlar ----- */
var agFilter='';
function pageAgents(page){
  page.innerHTML='<div class="agents-layout"><div class="map" id="agMap"></div><div class="card"><div class="toolbar"><div class="seg" id="agSeg">'+
    [['','Barchasi'],['active','🟢 Faol'],['late','🟡 Kechikkan'],['offline','⚪ Yopiq']].map(function(x){return '<button data-f="'+x[0]+'" class="'+(agFilter===x[0]?'on':'')+'">'+x[1]+'</button>'}).join('')+
    '</div></div><div class="list" id="agList"></div></div></div>';
  $('agSeg').onclick=function(e){var b=e.target.closest('button');if(!b)return;agFilter=b.dataset.f;$('agSeg').querySelectorAll('button').forEach(function(x){x.classList.toggle('on',x===b)});agentsList()};
  var m=makeMap($('agMap'),'agents');S.agMarkers={};
  if(m){S.dash.agents.forEach(function(a){if(a.lat==null)return;S.agMarkers[a.id]=L.marker([a.lat,a.lon],{icon:agentIcon(a)}).addTo(m).bindPopup(agentPopup(a)).on('click',function(){openAgent(a.id,true)})});
    var pts=S.dash.agents.filter(function(a){return a.lat!=null}).map(function(a){return [a.lat,a.lon]});if(pts.length)m.fitBounds(pts,{padding:[40,40],maxZoom:14});setTimeout(function(){m.invalidateSize()},50)}
  agentsList();
}
function agentPopup(a){return '<b>'+esc(a.name)+'</b><br>'+(a.locationSource==='live'?'Jonli GPS':'Oxirgi ma’lum joy')+' · '+ago(a.lastGpsTs)}
function agentsList(){
  var rows=S.dash.agents.filter(function(a){return !agFilter||a.status===agFilter}).sort(function(a,b){return (b.shiftOpen-a.shiftOpen)||(b.done-a.done)||a.name.localeCompare(b.name)});
  $('agList').innerHTML=rows.length?rows.map(function(a){var st=AG_ST[a.status]||AG_ST.offline;return '<div class="li click" data-agent="'+a.id+'">'+avatar(a.name,a.photoUrl)+'<div class="t"><b>'+esc(a.name)+'</b><small>'+a.done+' tashrif bugun · '+a.clients+' mijoz'+(a.late?' · <span class="bad">'+a.late+' kechikkan</span>':'')+'</small><small>'+(a.lastGpsTs?'📍 '+(a.locationSource==='live'?'jonli':'oxirgi')+' · '+ago(a.lastGpsTs):'📍 GPS yo‘q')+'</small></div>'+pill('<span class="dot"></span>'+st[0],st[1])+'</div>'}).join(''):'<div class="empty">Agent topilmadi</div>';
  $('agList').querySelectorAll('[data-agent]').forEach(function(el){el.onclick=function(){var id=+el.dataset.agent,mk=S.agMarkers&&S.agMarkers[id];if(mk&&S.maps.agents){S.maps.agents.flyTo(mk.getLatLng(),15,{duration:.5});mk.openPopup()}openAgent(id,true)}});
}
function updateAgentsLive(){
  if(!S.maps.agents)return;
  S.dash.agents.forEach(function(a){if(a.lat==null)return;var mk=S.agMarkers[a.id];if(mk){mk.setLatLng([a.lat,a.lon]);mk.setIcon(agentIcon(a));mk.setPopupContent(agentPopup(a))}else S.agMarkers[a.id]=L.marker([a.lat,a.lon],{icon:agentIcon(a)}).addTo(S.maps.agents).bindPopup(agentPopup(a))});
  agentsList();
}

/* Agent kartasi */
async function openAgent(id){
  openDrawer('<div class="loading">Agent ma’lumotlari yuklanmoqda…</div>');
  var a=await run(function(){return api('agent_detail',{agentId:id})});if(!a){closeDrawer();return}
  renderAgent(a);
}
function renderAgent(a){
  var dashA=S.dash&&S.dash.agents.find(function(x){return x.id===a.id})||{};
  var P=a.periods,cols=[['today','Bugun'],['week','7 kun'],['month','30 kun']];
  var stat=function(k,f){return '<tr><td class="muted">'+k+'</td>'+cols.map(function(c){return '<td class="right num">'+f(P[c[0]])+'</td>'}).join('')+'</tr>'};
  var stocks=a.stocks.filter(function(s){return s.qty});
  openDrawer(
   '<div class="dh">'+avatar(a.name,a.photoUrl||dashA.photoUrl,'lg')+'<div><h2>'+esc(a.name)+'</h2><div class="muted">ID '+a.id+' · '+a.clients+' mijoz · '+(a.active?(a.shiftOpen?pill('<span class="dot"></span>Smena ochiq · '+hm(a.shiftStart),'p-ok'):pill('Smena yopiq')):pill('Bloklangan','p-bad'))+'</div></div></div>'+
   '<div class="grid g3" style="margin-bottom:14px">'+
     '<div class="card"><small class="muted">Qo‘lidagi pul</small><b style="display:block;font-size:20px">'+usd(a.cashUsd)+'</b>'+(a.legacyCashUzs?'<small class="muted">+ '+uzs(a.legacyCashUzs)+'</small>':'')+'</div>'+
     '<div class="card"><small class="muted">Kassaga kutilmoqda</small><b style="display:block;font-size:20px">'+usd(a.pendingHandoverUsd)+'</b></div>'+
     '<div class="card"><small class="muted">Oxirgi GPS</small><b style="display:block;font-size:16px">'+(a.lastGpsTs?ago(a.lastGpsTs):'—')+'</b><small class="muted">'+(a.lastGpsTs?dt(a.lastGpsTs):'')+'</small></div>'+
   '</div>'+
   '<div class="card" style="padding:0;margin-bottom:14px"><div id="drMap" style="height:260px;border-radius:14px"></div></div>'+
   '<div class="card flush" style="margin-bottom:14px"><table><thead><tr><th>Ko‘rsatkich</th>'+cols.map(function(c){return '<th class="right">'+c[1]+'</th>'}).join('')+'</tr></thead><tbody>'+
     stat('Realizatsiya',function(p){return usd(p.deliveredUsd)})+stat('To‘lovlar',function(p){return usd(p.paymentsUsd)})+stat('Qaytarilgan',function(p){return usd(p.returnsUsd)})+
     stat('Tashriflar',function(p){return p.visits})+stat('Yangi mijozlar',function(p){return p.newClients})+stat('Ish vaqti',function(p){return hours(p.workSeconds)})+stat('Masofa',function(p){return num(p.distanceKm,1)+' km'})+
   '</tbody></table></div>'+
   '<div class="grid g2" style="margin-bottom:14px">'+
     '<div class="card"><div class="card-h"><h3>Qo‘lidagi tovar</h3></div>'+(stocks.length?'<div class="list">'+stocks.map(function(s){return '<div class="li"><div class="t"><b>'+esc(s.name)+'</b></div><b class="num">'+s.qty+'</b></div>'}).join('')+'</div>':'<div class="muted">Tovar yo‘q</div>')+'</div>'+
     '<div class="card"><div class="card-h"><h3>Huquqlar</h3></div>'+a.features.map(function(f){return '<div class="switch"><span>'+esc(f.label)+'</span><button class="tog'+(f.enabled?' on':'')+'" data-feat="'+esc(f.key)+'" data-on="'+(f.enabled?1:0)+'" aria-label="'+esc(f.label)+'"'+(a.active?'':' disabled')+'></button></div>'}).join('')+'</div>'+
   '</div>'+
   '<div class="actions">'+(a.active?'<button class="btn" id="agRename">✏️ Nomini o‘zgartirish</button>':'')+
     (S.primary&&a.active?'<button class="btn" id="agTransfer">🔁 Akkauntni almashtirish</button><button class="btn danger" id="agBlock">⛔ Bloklash</button>':'')+'</div>'+
   (a.audit.length?'<div class="card" style="margin-top:14px"><div class="card-h"><h3>Akkaunt tarixi</h3></div><div class="list">'+a.audit.map(function(x){return '<div class="li"><div class="t"><b>'+esc(x.action)+'</b><small>'+esc(x.actor)+' · '+dt(x.ts)+(x.newId&&x.oldId!==x.newId?' · '+esc(x.oldId)+' → '+esc(x.newId):'')+'</small></div></div>'}).join('')+'</div></div>':''));
  agentRouteMap(a);
  $('drawerBody').querySelectorAll('[data-feat]').forEach(function(b){b.onclick=async function(){
    var on=b.dataset.on!=='1',f=a.features.find(function(x){return x.key===b.dataset.feat});
    if(!await confirmBox('Huquqni o‘zgartirish','<p><b>'+esc(a.name)+'</b> uchun «'+esc(f.label)+'» '+(on?'yoqiladi':'o‘chiriladi')+'.</p>'))return;
    var r=await run(function(){return api('agent_feature_set',{agentId:a.id,feature:f.key,enabled:on,confirm:true})},'Saqlandi');if(r)renderAgent(r.agent)}});
  var rn=$('agRename');if(rn)rn.onclick=async function(){
    var v=await formBox('Agent nomi',[{name:'name',label:'Yangi nom',value:a.name,required:true}]);if(!v)return;
    var p=await run(function(){return api('agent_rename_preview',{agentId:a.id,name:v.name})});if(!p)return;
    if(!await confirmBox('Tasdiqlang','<div class="diff"><s>'+esc(p.oldName||a.name)+'</s> → <ins>'+esc(p.newName)+'</ins></div>'))return;
    var r=await run(function(){return api('agent_rename_commit',{agentId:a.id,name:v.name,confirm:true})},'Nom o‘zgartirildi');if(r){S.dash=null;renderAgent(r.agent)}};
  var tr=$('agTransfer');if(tr)tr.onclick=async function(){
    var v=await formBox('Akkauntni almashtirish',[{name:'newId',label:'Yangi Telegram ID',required:true,placeholder:'123456789'}],'Davom etish','Agent yangi Telegram akkauntga o‘tadi. Mijozlar, qarz va tarix saqlanadi.');if(!v)return;
    var p=await run(function(){return api('agent_transfer_preview',{agentId:a.id,newId:v.newId})});if(!p)return;
    if(!await confirmBox('Tasdiqlang','<p>'+esc(a.name)+': <b>'+esc(p.agentId)+'</b> → <b>'+esc(p.newId)+'</b></p>','Almashtirish',true))return;
    var r=await run(function(){return api('agent_transfer_commit',{agentId:a.id,newId:v.newId,confirm:true})},'Akkaunt almashtirildi');if(r){S.dash=null;renderAgent(r.agent)}};
  var bl=$('agBlock');if(bl)bl.onclick=async function(){
    var p=await run(function(){return api('agent_deactivate_preview',{agentId:a.id})});if(!p)return;
    if(!await confirmBox('Agentni bloklash','<p><b>'+esc(a.name)+'</b> botga kira olmaydi. Tarix saqlanadi.</p>'+(p.warning?'<p class="bad">'+esc(p.warning)+'</p>':''),'Bloklash',true))return;
    var r=await run(function(){return api('agent_deactivate_commit',{agentId:a.id,confirm:true})},'Agent bloklandi');if(r){S.dash=null;renderAgent(r.agent)}};
}
async function agentRouteMap(a){
  var el=$('drMap');if(!el||!window.L)return;
  if(S.maps.drawer){try{S.maps.drawer.remove()}catch(e){}}
  var m=L.map(el).setView(a.lat!=null?[a.lat,a.lon]:[40.45,71.6],a.lat!=null?14:9);
  L.tileLayer('/tiles/{z}/{x}/{y}.png',{maxZoom:19,attribution:'© OpenStreetMap'}).addTo(m);S.maps.drawer=m;
  [120,320,600].forEach(function(t){setTimeout(function(){if(S.maps.drawer===m)m.invalidateSize()},t)});
  if(!a.active)return;
  var r=await api('route',{agentId:a.id}).catch(function(){return null});
  if(!r||S.maps.drawer!==m)return;
  var pts=r.points.map(function(p){return [p.lat,p.lon]});
  if(pts.length>1){L.polyline(pts,{color:'#1f6bff',weight:4,opacity:.85}).addTo(m);L.circleMarker(pts[0],{radius:6,color:'#fff',fillColor:'#12a75b',fillOpacity:1,weight:2}).addTo(m).bindTooltip('Boshlanish '+hm(r.points[0].ts));m.fitBounds(pts,{padding:[24,24]})}
  if(a.lat!=null)L.marker([a.lat,a.lon],{icon:agentIcon(Object.assign({status:a.shiftOpen?'active':'offline'},a))}).addTo(m).bindTooltip('Oxirgi joy · '+ago(a.lastGpsTs));
  var info=document.createElement('div');info.className='muted small';info.style.padding='8px 12px';
  info.textContent=r.start?('Oxirgi smena: '+dt(r.start)+(r.end?' – '+hm(r.end):' (ochiq)')+' · '+pts.length+' GPS nuqta'):'Smena tarixi yo‘q';
  el.parentNode.appendChild(info);
}

/* ----- Mijozlar ----- */
var CL={q:'',age:'',agent:'',debt:'',region:'',sort:'lastTs',dir:-1,page:0,view:'table'};
var PAGE_SIZE=50;
function pageClients(page){
  if(S.cache.clientAge){CL.age=S.cache.clientAge;delete S.cache.clientAge}
  var d=S.dash,agents=d.agents.slice().sort(function(a,b){return a.name.localeCompare(b.name)});
  var regions=Array.from(new Set(d.clients.map(function(c){return c.region}).filter(Boolean))).sort();
  page.innerHTML=(d.clientsTruncated?'<div class="banner">Ro‘yxatda oxirgi '+num(d.clients.length)+' ta mijoz ko‘rsatilgan (jami '+num(d.clientCount)+'). To‘liq ro‘yxat uchun Excel eksportdan foydalaning.</div>':'')+
   '<div class="toolbar"><input type="search" id="clQ" placeholder="Qidirish: nom, telefon, manzil…  ( / )" value="'+esc(CL.q)+'">'+
   '<select id="clAgent"><option value="">Barcha agentlar</option>'+agents.map(function(a){return '<option value="'+a.id+'"'+(String(CL.agent)===String(a.id)?' selected':'')+'>'+esc(a.name)+'</option>'}).join('')+'</select>'+
   '<select id="clDebt">'+[['','Qarz: barchasi'],['debt','Qarzi bor'],['big','Qarz $100+'],['none','Qarzsiz'],['black','Qora ro‘yxat']].map(function(o){return '<option value="'+o[0]+'"'+(CL.debt===o[0]?' selected':'')+'>'+o[1]+'</option>'}).join('')+'</select>'+
   (regions.length?'<select id="clRegion"><option value="">Barcha hududlar</option>'+regions.map(function(r){return '<option'+(CL.region===r?' selected':'')+'>'+esc(r)+'</option>'}).join('')+'</select>':'')+
   '<span class="grow"></span><div class="seg" id="clView"><button data-v="table" class="'+(CL.view==='table'?'on':'')+'">☰ Jadval</button><button data-v="map" class="'+(CL.view==='map'?'on':'')+'">🗺 Xarita</button></div>'+
   '</div>'+
   '<div class="toolbar"><div class="seg" id="clAge"></div><span class="grow"></span><span class="muted small" id="clCount"></span><button class="btn" id="clXlsx">⬇ Excel</button><button class="btn" id="clPdf">⬇ PDF</button></div>'+
   '<div id="clBody"></div>';
  var upd=function(){CL.page=0;clientsBody()};
  $('clQ').oninput=debounce(function(){CL.q=this.value;upd()},150);
  $('clAgent').onchange=function(){CL.agent=this.value;upd()};
  $('clDebt').onchange=function(){CL.debt=this.value;upd()};
  if($('clRegion'))$('clRegion').onchange=function(){CL.region=this.value;upd()};
  $('clView').onclick=function(e){var b=e.target.closest('button');if(!b)return;CL.view=b.dataset.v;$('clView').querySelectorAll('button').forEach(function(x){x.classList.toggle('on',x===b)});clientsBody()};
  $('clAge').onclick=function(e){var b=e.target.closest('button');if(!b)return;CL.age=b.dataset.a;upd()};
  $('clXlsx').onclick=function(){exportAll('xlsx',this)};$('clPdf').onclick=function(){exportAll('pdf',this)};
  clientsBody();
}
async function exportAll(fmt,btn){btn.disabled=true;toast('Fayl tayyorlanmoqda…');var r=await run(function(){return api('all_clients_export',{format:fmt})});btn.disabled=false;if(r)download(r)}
function filteredClients(ignoreAge){
  var q=CL.q.trim().toLowerCase();
  return S.dash.clients.filter(function(c){
    if(!ignoreAge&&CL.age&&c.age!==CL.age)return false;
    if(CL.agent&&String(c.agentId)!==String(CL.agent))return false;
    if(CL.region&&c.region!==CL.region)return false;
    if(CL.debt==='debt'&&!(c.debtUsd>0))return false;if(CL.debt==='big'&&!(c.debtUsd>=100))return false;
    if(CL.debt==='none'&&c.debtUsd>0)return false;if(CL.debt==='black'&&!c.blacklisted)return false;
    if(q&&(c.name+' '+c.person+' '+c.phone+' '+c.address+' '+c.agent+' '+c.region+' #'+c.id).toLowerCase().indexOf(q)<0)return false;
    return true});
}
function clientsBody(){
  var base=filteredClients(true),counts={'':base.length};base.forEach(function(c){counts[c.age]=(counts[c.age]||0)+1});
  $('clAge').innerHTML=[['','Barchasi'],['fresh','0–2 kun'],['yellow','3–4 kun'],['red','5+ kun'],['scheduled','Rejada']].map(function(x){return '<button data-a="'+x[0]+'" class="'+(CL.age===x[0]?'on':'')+'">'+x[1]+'<b>'+(counts[x[0]]||0)+'</b></button>'}).join('');
  var rows=filteredClients(false),debt=rows.reduce(function(s,c){return s+(c.debtUsd||0)},0);
  $('clCount').textContent=num(rows.length)+' ta mijoz · qarz '+usd(debt);
  var body=$('clBody');
  if(S.maps.clients){try{S.maps.clients.remove()}catch(e){}delete S.maps.clients}
  if(CL.view==='map'){
    body.innerHTML='<div class="map" id="clMap" style="height:calc(100vh - 230px)"></div>';
    var m=makeMap($('clMap'),'clients');if(!m)return;var pts=[];
    rows.forEach(function(c){if(c.lat==null)return;pts.push([c.lat,c.lon]);
      L.circleMarker([c.lat,c.lon],{radius:7,color:'#fff',weight:2,fillColor:c.blacklisted?'#111':(AGE[c.age]||AGE.unknown)[2],fillOpacity:.95}).addTo(m)
       .bindTooltip(esc(c.name)+(c.debtUsd>0?' · '+usd(c.debtUsd):'')).on('click',function(){openClient(c.id)})});
    if(pts.length)m.fitBounds(pts,{padding:[30,30],maxZoom:15});setTimeout(function(){m.invalidateSize()},50);return;
  }
  var key=CL.sort,dir=CL.dir;
  rows.sort(function(a,b){var x=a[key],y=b[key];if(x==null)x=key==='name'||key==='agent'||key==='region'?'':-1;if(y==null)y=key==='name'||key==='agent'||key==='region'?'':-1;return (typeof x==='string'?x.localeCompare(y):x-y)*dir});
  var pages=Math.max(1,Math.ceil(rows.length/PAGE_SIZE));if(CL.page>=pages)CL.page=pages-1;
  var slice=rows.slice(CL.page*PAGE_SIZE,(CL.page+1)*PAGE_SIZE);
  var th=function(k,label,cls){return '<th class="sort '+(cls||'')+(CL.sort===k?(CL.dir>0?' asc':' desc'):'')+'" data-k="'+k+'">'+label+'</th>'};
  body.innerHTML='<div class="card flush"><div class="tbl-wrap"><table><thead><tr>'+th('name','Mijoz')+th('agent','Agent')+th('region','Hudud')+'<th>Telefon</th>'+th('debtUsd','Qarz','right')+th('lastTs','Oxirgi aloqa')+th('age','Holat')+'</tr></thead><tbody>'+
   (slice.length?slice.map(function(c){var ag=AGE[c.age]||AGE.unknown;return '<tr class="click" data-client="'+c.id+'"><td><div class="cell">'+(c.thumbUrl?'<span class="av sq" style="background-image:url(\''+esc(c.thumbUrl)+'\')"></span>':avatar(c.name,'','sq'))+'<div class="t"><b>'+esc(c.name)+(c.blacklisted?' ⛔':'')+'</b><small>'+esc(c.person||c.address||'')+'</small></div></div></td><td>'+esc(c.agent)+'</td><td>'+esc(c.region||'—')+'</td><td class="num">'+(c.phone?'<a href="tel:'+esc(c.phone.split(/[,\/\n]/)[0].trim())+'">'+esc(c.phone)+'</a>':'—')+'</td><td class="right num '+(c.debtUsd>0?'bad':'')+'">'+(c.debtUsd?usd(c.debtUsd):'—')+'</td><td><span class="num">'+(c.lastTs?dday(c.lastTs):'—')+'</span><br><small class="muted">'+(c.days!=null?c.days+' kun':'')+(c.followup?' · reja '+esc(c.followup):'')+'</small></td><td>'+pill(ag[0],ag[1])+'</td></tr>'}).join(''):'<tr><td colspan="7" class="empty">Mijoz topilmadi</td></tr>')+
   '</tbody></table></div>'+(pages>1?'<div class="pager"><span>'+(CL.page*PAGE_SIZE+1)+'–'+Math.min(rows.length,(CL.page+1)*PAGE_SIZE)+' / '+num(rows.length)+'</span><span class="actions"><button class="btn sm" id="pgPrev"'+(CL.page?'':' disabled')+'>‹ Oldingi</button><button class="btn sm" id="pgNext"'+(CL.page<pages-1?'':' disabled')+'>Keyingi ›</button></span></div>':'')+'</div>';
  body.querySelectorAll('th.sort').forEach(function(h){h.onclick=function(){var k=h.dataset.k;if(CL.sort===k)CL.dir=-CL.dir;else{CL.sort=k;CL.dir=(k==='name'||k==='agent'||k==='region')?1:-1}clientsBody()}});
  if($('pgPrev'))$('pgPrev').onclick=function(){CL.page--;clientsBody();scrollTo(0,0)};
  if($('pgNext'))$('pgNext').onclick=function(){CL.page++;clientsBody();scrollTo(0,0)};
  bindClientLinks(body);
}

/* Mijoz kartasi */
async function openClient(id){
  openDrawer('<div class="loading">Mijoz ma’lumotlari yuklanmoqda…</div>');
  var c=await run(function(){return api('client_detail',{clientId:id})});if(!c){closeDrawer();return}
  renderClient(c,'events');
}
function renderClient(c,tab){
  var t=c.totals;
  var tabs=[['events','Harakatlar',c.events.length],['visits','Tashriflar',c.visits.length],['stock','Qoldiq',c.stocks.filter(function(s){return s.qty}).length],['edits','O‘zgarishlar',c.edits.length+(c.blacklistLog||[]).length]];
  var tabBody={
    events:function(){return c.events.length?'<table><thead><tr><th>Sana</th><th>Amal</th><th>Tovar</th><th class="right">Miqdor</th><th class="right">Summa</th><th>Kim</th></tr></thead><tbody>'+c.events.map(function(e){return '<tr><td class="num">'+dt(e.ts)+'</td><td>'+(KIND[e.kind]||esc(e.kind))+'</td><td>'+esc(e.product||'—')+(e.note?'<br><small class="muted">'+esc(e.note)+'</small>':'')+'</td><td class="right num">'+(e.qty||'—')+'</td><td class="right num">'+(e.amountUsd?usd(e.amountUsd):e.amountUzs?uzs(e.amountUzs):'—')+'</td><td>'+esc(e.actor)+'</td></tr>'}).join('')+'</tbody></table>':'<div class="empty">Harakat yo‘q</div>'},
    visits:function(){return c.visits.length?'<div class="list" style="padding:0 18px">'+c.visits.map(function(v){return '<div class="li">'+(v.thumbUrl?'<a href="'+esc(v.photoUrl)+'" target="_blank" rel="noopener"><span class="av sq" style="background-image:url(\''+esc(v.thumbUrl)+'\');width:48px;height:48px"></span></a>':'<span class="av sq">👣</span>')+'<div class="t"><b>'+esc(VISIT[v.status]||v.status||'Tashrif')+'</b><small>'+esc(v.note)+'</small><small>'+esc(v.actor)+' · '+dt(v.ts)+(v.followup?' · qayta: '+esc(v.followup):'')+'</small></div></div>'}).join('')+'</div>':'<div class="empty">Tashrif yo‘q</div>'},
    stock:function(){var s=c.stocks.filter(function(x){return x.qty});return s.length?'<table><thead><tr><th>Tovar</th><th class="right">Do‘konda</th></tr></thead><tbody>'+s.map(function(x){return '<tr><td>'+esc(x.name)+'</td><td class="right num">'+x.qty+'</td></tr>'}).join('')+'</tbody></table>':'<div class="empty">Do‘konda tovar qoldig‘i yo‘q</div>'},
    edits:function(){var rows=c.edits.map(function(e){return '<div class="li"><div class="t"><b>'+esc(FIELD[e.field]||e.field)+'</b><div class="diff"><s>'+esc(e.old||'—')+'</s> → <ins>'+esc(e.new||'—')+'</ins></div><small>'+esc(e.actor)+' · '+dt(e.ts)+'</small></div></div>'}).concat((c.blacklistLog||[]).map(function(l){return '<div class="li"><div class="t"><b>'+(l.action==='on'||l.action==='add'?'⛔ Qora ro‘yxatga':'✅ Qora ro‘yxatdan chiqdi')+'</b><small>'+esc(l.reason)+'</small><small>'+esc(l.actor)+' · '+dt(l.ts)+'</small></div></div>'}));return rows.length?'<div class="list" style="padding:0 18px">'+rows.join('')+'</div>':'<div class="empty">O‘zgarish yo‘q</div>'}
  };
  openDrawer(
   '<div class="dh">'+(c.thumbUrl?'<span class="av lg" style="background-image:url(\''+esc(c.thumbUrl)+'\')"></span>':avatar(c.name,'','lg'))+'<div><h2>'+esc(c.name)+(c.blacklisted?' '+pill('⛔ Qora ro‘yxat','p-bad'):'')+'</h2><div class="muted">#'+c.id+' · agent: '+esc(c.agent)+(c.region?' · '+esc(c.region):'')+'</div></div></div>'+
   (c.blacklisted&&c.blacklistReason?'<div class="banner">Sabab: '+esc(c.blacklistReason)+'</div>':'')+
   '<div class="grid g4" style="margin-bottom:14px">'+
     '<div class="card"><small class="muted">Qarz</small><b style="display:block;font-size:19px" class="'+(c.debtUsd>0?'bad':'ok')+'">'+usd(c.debtUsd)+'</b></div>'+
     '<div class="card"><small class="muted">Berilgan</small><b style="display:block;font-size:19px">'+usd(t.deliveredUsd)+'</b></div>'+
     '<div class="card"><small class="muted">To‘langan</small><b style="display:block;font-size:19px">'+usd(t.paidUsd)+'</b></div>'+
     '<div class="card"><small class="muted">Qaytarilgan</small><b style="display:block;font-size:19px">'+usd(t.returnedUsd)+'</b></div>'+
   '</div>'+
   '<div class="grid '+(c.photoUrl?'g2':'')+'" style="margin-bottom:14px"><div class="card"><dl class="kv">'+
     '<dt>Mijoz</dt><dd>'+esc(c.person||'—')+'</dd><dt>Do‘kon</dt><dd>'+esc(c.shopName||'—')+'</dd>'+
     '<dt>Telefon</dt><dd>'+(c.phone?esc(c.phone):'—')+'</dd><dt>Manzil</dt><dd>'+esc(c.address||'—')+'</dd>'+
     '<dt>To‘lov sanasi</dt><dd>'+esc(c.paymentDue||'—')+'</dd><dt>Izoh</dt><dd>'+esc(c.comment||'—')+'</dd>'+
     '<dt>Qo‘shilgan</dt><dd>'+dt(c.createdTs)+'</dd>'+
     '<dt>Joylashuv</dt><dd>'+(c.lat!=null?'<a href="https://www.google.com/maps/search/?api=1&query='+c.lat+','+c.lon+'" target="_blank" rel="noopener">Google xaritada ochish ↗</a>':'—')+'</dd>'+
   '</dl></div>'+(c.photoUrl?'<div><a href="'+esc(c.photoUrl)+'" target="_blank" rel="noopener"><img class="photo" src="'+esc(c.photoUrl)+'" alt="Do‘kon rasmi"></a></div>':'')+'</div>'+
   '<div class="actions"><button class="btn" id="cEdit">✏️ Tahrirlash</button><button class="btn" id="cXlsx">⬇ Akt sverka Excel</button><button class="btn" id="cPdf">⬇ Akt sverka PDF</button>'+
     '<button class="btn" id="cBlack">'+(c.blacklisted?'✅ Qora ro‘yxatdan chiqarish':'⛔ Qora ro‘yxatga')+'</button><button class="btn danger" id="cDel">🗑 O‘chirish</button></div>'+
   '<div class="tabs" id="cTabs">'+tabs.map(function(x){return '<button data-t="'+x[0]+'" class="'+(tab===x[0]?'on':'')+'">'+x[1]+' <span class="muted">'+x[2]+'</span></button>'}).join('')+'</div>'+
   '<div class="card flush"><div class="tbl-wrap" style="max-height:none">'+tabBody[tab]()+'</div></div>');
  $('cTabs').onclick=function(e){var b=e.target.closest('button');if(b)renderClient(c,b.dataset.t)};
  var exp=function(fmt,btn){btn.disabled=true;run(function(){return api('client_export',{clientId:c.id,format:fmt})}).then(function(r){btn.disabled=false;if(r)download(r)})};
  $('cXlsx').onclick=function(){exp('xlsx',this)};$('cPdf').onclick=function(){exp('pdf',this)};
  $('cEdit').onclick=async function(){
    var cur={name:c.person,shop_name:c.shopName,phone:c.phone,address:c.address,comment:c.comment,payment_due:c.paymentDue};
    var v=await formBox('Mijozni tahrirlash',[{name:'shop_name',label:'Do‘kon nomi',value:cur.shop_name},{name:'name',label:'Mijoz ismi',value:cur.name},{name:'phone',label:'Telefon',value:cur.phone},{name:'address',label:'Manzil',value:cur.address},{name:'payment_due',label:'To‘lov sanasi (YYYY-MM-DD)',value:cur.payment_due},{name:'comment',label:'Izoh',value:cur.comment,area:true}],'Davom etish');
    if(!v)return;var values={};Object.keys(v).forEach(function(k){if(String(cur[k]||'')!==v[k].trim())values[k]=v[k]});
    if(!Object.keys(values).length){toast('Hech narsa o‘zgarmadi');return}
    var p=await run(function(){return api('client_edit_preview',{clientId:c.id,values:values})});if(!p)return;
    if(!await confirmBox('O‘zgarishlarni tasdiqlang',p.changes.map(function(ch){return '<div class="diff"><b>'+esc(FIELD[ch.field]||ch.field)+':</b> <s>'+esc(ch.old||'—')+'</s> → <ins>'+esc(ch.new||'—')+'</ins></div>'}).join(''),'Saqlash'))return;
    var r=await run(function(){return api('client_edit_commit',{clientId:c.id,values:p.values,confirm:true})},'Mijoz ma’lumotlari saqlandi');
    if(r){S.dash=null;renderClient(r.client,tab)}};
  $('cBlack').onclick=async function(){
    var on=!c.blacklisted,reason='';
    if(on){var v=await formBox('Qora ro‘yxatga qo‘shish',[{name:'reason',label:'Sabab',required:true,area:true}],'Qo‘shish','Mijoz bazada va xaritada qoladi, agentlar unga tovar bera olmaydi.');if(!v)return;reason=v.reason}
    else if(!await confirmBox('Qora ro‘yxatdan chiqarish','<p><b>'+esc(c.name)+'</b> yana oddiy mijoz bo‘ladi.</p>'))return;
    var r=await run(function(){return api('client_blacklist',{clientId:c.id,on:on,reason:reason})});
    if(r){toast(r.message||'Saqlandi');S.dash=null;openClient(c.id)}};
  $('cDel').onclick=async function(){
    var p=await run(function(){return api('client_delete_preview',{clientId:c.id})});if(!p)return;
    if(!await confirmBox('Mijozni o‘chirish','<p><b>'+esc(p.name)+'</b> · qarz '+usd(p.debtUsd)+' · '+p.eventCount+' harakat · '+p.visitCount+' tashrif'+(p.openTasks?' · '+p.openTasks+' ochiq vazifa':'')+'</p><p class="muted">'+esc(p.warning)+'</p>','O‘chirish',true))return;
    var r=await run(function(){return api('client_delete_commit',{clientId:c.id,confirm:true})},'Mijoz arxivga o‘tkazildi');
    if(r){closeDrawer();S.dash=null;render(true)}};
}

/* ----- Kassa ----- */
var KS={f:'',p:'week',q:''};
function pageCash(page){
  var d=S.dash,c=d.cash,w=c.wallets||{};
  page.innerHTML=
   '<div class="grid g4" style="margin-bottom:16px">'+
     '<div class="card hero" style="grid-column:span 2"><small>Umumiy kassa qoldig‘i</small><b class="big" style="display:block">'+usd(c.balanceUsd)+'</b><div class="muted small">Tasdiqlangan kirim − chiqim, naqd va karta</div></div>'+
     kpi('⏳','Tasdiqlanmagan',usd(c.pendingUsd),c.pendingCount+' ta topshiriq','warn')+
     kpi('📅','7 kun sof',usd(c.netWeekUsd),'Kirim '+usd(c.acceptedWeekUsd)+' · chiqim '+usd(c.expensesWeekUsd))+
   '</div>'+
   '<div class="grid g4" style="margin-bottom:16px">'+
     kpi('💵','Naqd so‘m',uzs(w.cashUzs),'Kirim '+uzs(w.inCashUzs)+' · chiqim '+uzs(w.outCashUzs))+
     kpi('💲','Naqd dollar',usd(w.cashUsd),'Kirim '+usd(w.inCashUsd)+' · chiqim '+usd(w.outCashUsd))+
     kpi('💳','Karta so‘m',uzs(w.cardUzs),'Kirim '+uzs(w.inCardUzs)+(w.outCardUzs?' · chiqim '+uzs(w.outCardUzs):''))+
     kpi('🏦','Karta dollar',usd(w.cardUsd),'Kirim '+usd(w.inCardUsd))+
   '</div>'+
   '<div class="toolbar"><div class="seg" id="ksF">'+[['','Barchasi'],['in','⬇ Kirim'],['out','⬆ Chiqim'],['pending','⏳ Tasdiqlanmagan']].map(function(x){return '<button data-f="'+x[0]+'" class="'+(KS.f===x[0]?'on':'')+'">'+x[1]+'</button>'}).join('')+'</div>'+
   '<div class="seg" id="ksP">'+[['today','Bugun'],['week','7 kun'],['month','30 kun']].map(function(x){return '<button data-p="'+x[0]+'" class="'+(KS.p===x[0]?'on':'')+'">'+x[1]+'</button>'}).join('')+'</div>'+
   '<input type="search" id="ksQ" placeholder="Qidirish…" value="'+esc(KS.q)+'"><span class="grow"></span><span class="muted small" id="ksSum"></span></div>'+
   '<div class="grid g-main"><div class="card flush" id="ksList"></div><div class="card"><div class="card-h"><h3>Xarajatlar tarkibi</h3></div><div id="ksBrk"></div></div></div>';
  $('ksF').onclick=function(e){var b=e.target.closest('button');if(!b)return;KS.f=b.dataset.f;pageCash(page)};
  $('ksP').onclick=function(e){var b=e.target.closest('button');if(!b)return;KS.p=b.dataset.p;pageCash(page)};
  $('ksQ').oninput=debounce(function(){KS.q=this.value;cashList()},150);
  cashList();
}
function cashList(){
  var d=S.dash,since=d.todayStart-({today:0,week:6,month:29}[KS.p])*86400,q=KS.q.trim().toLowerCase();
  var rows=d.transactions.filter(function(t){var ts=t.acceptedTs||t.ts;if(ts<since&&!(KS.f==='pending'&&t.state==='pending'))return false;
    if(KS.f==='in'&&t.type!=='handover')return false;if(KS.f==='out'&&t.type!=='expense')return false;if(KS.f==='pending'&&t.state!=='pending')return false;
    if(q&&[t.agent,t.cashier,t.category,t.recipient,t.note].join(' ').toLowerCase().indexOf(q)<0)return false;return true});
  var tin=0,tout=0;rows.forEach(function(t){if(t.type==='handover'&&t.state==='accepted')tin+=t.amountUsd;if(t.type==='expense')tout+=t.amountUsd});
  $('ksSum').innerHTML=rows.length+' ta · <span class="ok">+'+usd(tin)+'</span> · <span class="bad">−'+usd(tout)+'</span>';
  var ST={pending:['Kutilmoqda','p-warn'],accepted:['Qabul qilindi','p-ok'],rejected:['Rad etildi','p-bad'],expense:['Chiqim','p-bad']};
  $('ksList').innerHTML='<div class="tbl-wrap"><table><thead><tr><th>Sana</th><th>Turi</th><th>Tafsilot</th><th>Kassir</th><th class="right">Summa</th><th>Holat</th></tr></thead><tbody>'+
   (rows.length?rows.slice(0,400).map(function(t){var st=ST[t.state]||[esc(t.state),''],h=t.type==='handover';
     return '<tr><td class="num">'+dt(t.acceptedTs||t.ts)+'</td><td>'+(h?'⬇ Agentdan':'⬆ '+esc(t.category))+'</td><td>'+(h?'<b>'+esc(t.agent)+'</b>'+(t.amountUzs?'<br><small class="muted">'+uzs(t.amountUzs)+'</small>':''):'<b>'+esc(t.recipient||'—')+'</b>'+(t.note?'<br><small class="muted">'+esc(t.note)+'</small>':'')+(t.currency==='UZS'&&t.amountUzs?'<br><small class="muted">'+uzs(t.amountUzs)+' · kurs '+num(t.rateUzsPerUsd)+'</small>':''))+'</td><td>'+esc(t.cashier||'—')+'</td><td class="right num '+(h?(t.state==='accepted'?'ok':'muted'):'bad')+'">'+(h?'+':'−')+usd(t.amountUsd)+'</td><td>'+pill(st[0],st[1])+'</td></tr>'}).join(''):'<tr><td colspan="6" class="empty">Harakat yo‘q</td></tr>')+
   '</tbody></table></div>'+(rows.length>400?'<div class="pager">Birinchi 400 ta ko‘rsatildi</div>':'');
  var cat={};rows.forEach(function(t){if(t.type==='expense')cat[t.category]=(cat[t.category]||0)+t.amountUsd});
  var list=Object.keys(cat).map(function(k){return [k,cat[k]]}).sort(function(a,b){return b[1]-a[1]}),total=list.reduce(function(s,x){return s+x[1]},0);
  $('ksBrk').innerHTML=list.length?'<div class="list">'+list.map(function(x){return '<div class="li"><div class="t"><b>'+esc(x[0])+'</b><div class="share" style="margin-top:6px"><i style="width:'+(x[1]/total*100).toFixed(1)+'%"></i></div></div><b class="num">'+usd(x[1])+'</b></div>'}).join('')+'</div>':'<div class="muted">Bu davrda xarajat yo‘q</div>';
}

/* ----- Hisobot ----- */
var RP={period:'week',from:'',to:''};
async function pageReports(page,force){
  page.innerHTML='<div class="toolbar"><div class="seg" id="rpSeg">'+[['today','Bugun'],['week','7 kun'],['month','Shu oy'],['custom','Davr']].map(function(x){return '<button data-p="'+x[0]+'" class="'+(RP.period===x[0]?'on':'')+'">'+x[1]+'</button>'}).join('')+'</div>'+
   '<span id="rpCustom"'+(RP.period==='custom'?'':' hidden')+' class="actions"><input type="date" id="rpFrom" value="'+esc(RP.from||today())+'" style="width:auto"><input type="date" id="rpTo" value="'+esc(RP.to||today())+'" style="width:auto"><button class="btn pri" id="rpGo">Ko‘rsatish</button></span>'+
   '<span class="grow"></span><span class="muted" id="rpLabel"></span></div><div id="rpBody"><div class="grid g4">'+'<div class="skel"></div>'.repeat(8)+'</div></div>';
  $('rpSeg').onclick=function(e){var b=e.target.closest('button');if(!b)return;RP.period=b.dataset.p;if(RP.period==='custom'){$('rpSeg').querySelectorAll('button').forEach(function(x){x.classList.toggle('on',x===b)});$('rpCustom').hidden=false;return}pageReports(page)};
  if($('rpGo'))$('rpGo').onclick=function(){RP.from=$('rpFrom').value;RP.to=$('rpTo').value;pageReports(page)};
  if(RP.period==='custom'&&!RP.from)return;
  var key=RP.period+RP.from+RP.to,r=!force&&S.cache['rp'+key];
  if(!r){r=await run(function(){return api('period_report',{period:RP.period,from:RP.from,to:RP.to})});if(!r){$('rpBody').innerHTML='';return}S.cache['rp'+key]=r}
  if(S.page!=='reports')return;
  $('rpLabel').textContent=r.label||'';
  var cash=r.cash||{},prod=(r.products||[]).filter(function(p){return p.deliveredUsd||p.deliveredQty});
  $('rpBody').innerHTML=
   '<div class="grid g4" style="margin-bottom:16px">'+
     kpi('📦','Realizatsiya',usd(r.deliveredUsd),r.deliveredQty+' dona · qaytgan '+usd(r.returnsUsd)+(r.topProduct?'<br>Top: '+esc(r.topProduct):''))+
     kpi('💰','Mijozdan olindi',usd(r.paymentsUsd),r.deliveredUsd?Math.round(r.paymentsUsd/r.deliveredUsd*100)+'% realizatsiyaga nisbatan':'')+
     kpi('🏦','Kassaga qabul',usd(r.acceptedCashUsd),'Xarajat '+usd(r.cashierExpensesUsd))+
     kpi('🛒','Do‘konda sotildi',num(r.soldQty)+' dona','Agentlar qayd etgan')+
     kpi('👣','Tashriflar',num(r.visits),'')+kpi('➕','Yangi mijozlar',num(r.newClients),'')+
     kpi('⏱','Ish vaqti',hours(r.workSeconds),'Barcha agentlar')+kpi('🧭','Masofa',num(r.distanceKm,1)+' km','GPS bo‘yicha')+
   '</div>'+
   '<div class="card" style="margin-bottom:16px"><div class="card-h"><h3>Dinamika <span class="muted small">('+esc(r.seriesUnit||'')+')</span></h3>'+legend([['Realizatsiya','#1f6bff'],['To‘lovlar','#12a75b']])+'</div>'+barChart(r.series,['deliveredUsd','paymentsUsd'],['#1f6bff','#12a75b'],usd)+'</div>'+
   '<div class="card flush" style="margin-bottom:16px"><div class="card-h"><h3>Agentlar natijasi</h3></div><div class="tbl-wrap" style="margin-top:12px">'+agentReportTable(r.agents)+'</div></div>'+
   '<div class="grid g2">'+
     '<div class="card flush"><div class="card-h"><h3>Mahsulotlar</h3></div><div class="tbl-wrap" style="margin-top:12px">'+(prod.length?'<table><thead><tr><th>Mahsulot</th><th class="right">Dona</th><th class="right">Summa</th><th>Ulush</th></tr></thead><tbody>'+prod.map(function(p){return '<tr><td>'+esc(p.name)+'</td><td class="right num">'+num(p.deliveredQty)+'</td><td class="right num">'+usd(p.deliveredUsd)+'</td><td><div class="share"><i style="width:'+(p.sharePct||0)+'%"></i></div><small class="muted">'+(p.sharePct||0)+'%</small></td></tr>'}).join('')+'</tbody></table>':'<div class="empty">Bu davrda sotuv yo‘q</div>')+'</div></div>'+
     '<div class="card"><div class="card-h"><h3>Kassa oqimi</h3></div><dl class="kv">'+
       '<dt>Naqd kirim</dt><dd class="num">'+uzs(cash.inCashUzs)+' · '+usd(cash.inCashUsd)+'</dd><dt>Karta kirim</dt><dd class="num">'+uzs(cash.inCardUzs)+' · '+usd(cash.inCardUsd)+'</dd>'+
       '<dt>Naqd chiqim</dt><dd class="num">'+uzs(cash.outCashUzs)+' · '+usd(cash.outCashUsd)+'</dd><dt>Karta chiqim</dt><dd class="num">'+uzs(cash.outCardUzs)+' · '+usd(cash.outCardUsd)+'</dd>'+
     '</dl></div>'+
   '</div>';
  bindAgentLinks($('rpBody'));
}

/* ----- Ombor ----- */
var WH={status:'open'};
var NEXT={new:[['preparing','Tayyorlashga olish'],['rejected','Rad etish']],preparing:[['new','Yangiga qaytarish'],['rejected','Rad etish']],loaded:[['delivered','Yetkazildi']],rejected:[['new','Qayta ochish']],delivered:[]};
async function pageWarehouse(page,force){
  if(!S.cache.wh||force||S.cache.wh.filter!==WH.status){page.innerHTML='<div class="loading">Ombor yuklanmoqda…</div>';var w=await run(function(){return api('warehouse',{status:WH.status})});if(!w)return;S.cache.wh=w}
  if(S.page!=='warehouse')return;renderWarehouse(page,S.cache.wh);
}
function renderWarehouse(page,w){
  var cnt=w.counts,lab=w.statusLabels,st=w.stock||{};
  var tabs=[['open','Ochiq',(cnt.new||0)+(cnt.preparing||0)+(cnt.loaded||0)]].concat(Object.keys(lab).map(function(k){return [k,lab[k],cnt[k]||0]}));
  var SC={new:'p-pri',preparing:'p-warn',loaded:'p-ok',delivered:'',rejected:'p-bad'};
  page.innerHTML=
   '<div class="grid g4" style="margin-bottom:16px">'+kpi('🆕','Yangi buyurtma',num(cnt.new||0),'Tayyorlanmoqda: '+(cnt.preparing||0))+kpi('🚚','Agentga berildi',num(cnt.loaded||0),'Yetkazilishi kutilmoqda')+kpi('🏬','Ombordagi tovar',num(st.stockTotal||0)+' dona','Bugun berildi: '+num(st.issuedToday||0))+kpi('❓','Katalogda yo‘q',num((w.demand||[]).length),'Agentlar so‘ragan nomlar','warn')+'</div>'+
   '<div class="toolbar"><div class="seg" id="whSeg">'+tabs.map(function(t){return '<button data-s="'+t[0]+'" class="'+(w.filter===t[0]?'on':'')+'">'+esc(t[1])+'<b>'+t[2]+'</b></button>'}).join('')+'</div><span class="grow"></span><button class="btn pri" id="whAdd">➕ Yangi mahsulot</button></div>'+
   '<div class="grid g-main"><div class="card flush"><div class="tbl-wrap"><table><thead><tr><th>#</th><th>Sana</th><th>Agent / mijoz</th><th>Tovarlar</th><th class="right">Summa</th><th>Holat</th><th></th></tr></thead><tbody>'+
    (w.orders.length?w.orders.map(function(o){return '<tr><td class="num">'+o.id+'</td><td class="num">'+dt(o.ts)+'</td><td><b>'+esc(o.agentName)+'</b><br><small class="muted">'+esc(o.clientName)+'</small></td><td>'+o.items.map(function(i){return esc(i.name)+' × '+i.qty+(i.custom?' <span class="pill p-warn">katalogda yo‘q</span>':'')}).join('<br>')+(o.note?'<br><small class="muted">📝 '+esc(o.note)+'</small>':'')+(o.adminNote?'<br><small class="muted">💬 '+esc(o.adminNote)+'</small>':'')+'</td><td class="right num">'+usd(o.totalCents/100)+'</td><td>'+pill(esc(o.statusLabel),SC[o.status])+'</td><td class="actions">'+(NEXT[o.status]||[]).map(function(n){return '<button class="btn sm'+(n[0]==='rejected'?' danger':'')+'" data-o="'+o.id+'" data-to="'+n[0]+'">'+n[1]+'</button>'}).join('')+'</td></tr>'}).join(''):'<tr><td colspan="7" class="empty">Buyurtma yo‘q</td></tr>')+
   '</tbody></table></div></div>'+
   '<div class="grid" style="align-content:start">'+
    ((w.demand||[]).length?'<div class="card"><div class="card-h"><h3>Katalogda yo‘q tovarlar</h3></div><div class="list">'+w.demand.map(function(d,i){return '<div class="li"><div class="t"><b>'+esc(d.name)+'</b><small>'+d.qty+' dona · '+d.orders+' buyurtma · '+d.clients+' mijoz</small></div><button class="btn sm" data-dm="'+i+'">Bog‘lash</button></div>'}).join('')+'</div></div>':'')+
    '<div class="card"><div class="card-h"><h3>Ombor qoldig‘i</h3><span class="muted small">Shu oy berildi: '+num(st.issuedMonth||0)+'</span></div>'+((st.products||[]).length?'<div class="list">'+st.products.map(function(p){return '<div class="li"><div class="t"><b>'+esc(p.name)+'</b><small>Bugun '+p.issuedToday+' · oy '+p.issuedMonth+'</small></div><b class="num '+(p.stock<0?'bad':'')+'">'+num(p.stock)+'</b></div>'}).join('')+'</div>':'<div class="muted">Ma’lumot yo‘q</div>')+'</div>'+
   '</div></div>'+
   '<div class="card flush" style="margin-top:16px"><div class="card-h"><h3>Mahsulotlar katalogi</h3></div><div class="tbl-wrap" style="margin-top:12px"><table><thead><tr><th>Kod</th><th>Nomi</th><th class="right">Narx</th><th class="right">Og‘irlik</th><th class="right">Blokda</th><th>Holat</th><th></th></tr></thead><tbody>'+
    w.catalog.map(function(p){return '<tr><td class="num">'+p.pack+'</td><td><div class="cell">'+(p.thumbUrl||p.photoUrl?'<span class="av sq" style="background-image:url(\''+esc(p.thumbUrl||p.photoUrl)+'\')"></span>':'')+'<b>'+esc(p.name)+'</b></div></td><td class="right num">'+usd(p.priceUsd)+'</td><td class="right num">'+(p.weightKg?num(p.weightKg)+' kg':'—')+'</td><td class="right num">'+(p.blockUnits||'—')+'</td><td>'+(p.active?pill('Faol','p-ok'):pill('Yashirin'))+'</td><td><button class="btn sm" data-pe="'+p.pack+'">Tahrirlash</button></td></tr>'}).join('')+
   '</tbody></table></div></div>';
  $('whSeg').onclick=function(e){var b=e.target.closest('button');if(!b)return;WH.status=b.dataset.s;pageWarehouse(page,true)};
  page.querySelectorAll('[data-o]').forEach(function(b){b.onclick=async function(){
    var to=b.dataset.to,label=b.textContent,v=await formBox('Buyurtma #'+b.dataset.o+': '+label,[{name:'note',label:'Izoh (ixtiyoriy)',area:true}],label);if(!v)return;
    var r=await run(function(){return api('order_status',{orderId:+b.dataset.o,to:to,note:v.note,status:WH.status})},'Holat o‘zgartirildi');if(r){S.cache.wh=r.warehouse;renderWarehouse(page,r.warehouse)}}});
  page.querySelectorAll('[data-pe]').forEach(function(b){b.onclick=async function(){
    var p=w.catalog.find(function(x){return String(x.pack)===b.dataset.pe});
    var v=await formBox('Mahsulot #'+p.pack,[{name:'name',label:'Nomi',value:p.name,required:true},{name:'priceUsd',label:'Narx (USD)',value:p.priceUsd,type:'number',step:'0.01',required:true},{name:'weightKg',label:'Og‘irlik (kg)',value:p.weightKg||'',type:'number',step:'0.01'},{name:'active',label:'Holat',value:p.active?'1':'0',options:[['1','Faol (agentlarga ko‘rinadi)'],['0','Yashirin']]}]);if(!v)return;
    var args={pack:p.pack,status:WH.status,active:v.active==='1'};if(v.name!==p.name)args.name=v.name;if(Number(v.priceUsd)!==Number(p.priceUsd))args.priceUsd=v.priceUsd;if(v.weightKg&&Number(v.weightKg)!==Number(p.weightKg||0))args.weightKg=v.weightKg;
    var r=await run(function(){return api('product_update',args)},'Mahsulot saqlandi');if(r){S.cache.wh=r.warehouse;renderWarehouse(page,r.warehouse)}}});
  page.querySelectorAll('[data-dm]').forEach(function(b){b.onclick=async function(){
    var d=w.demand[+b.dataset.dm],opts=w.catalog.filter(function(p){return p.active}).map(function(p){return [p.pack,p.pack+' · '+p.name]});
    var v=await formBox('«'+d.name+'» ni bog‘lash',[{name:'pack',label:'Katalogdagi mahsulot',options:opts}],'Bog‘lash','Ochiq buyurtmalardagi shu nom tanlangan mahsulotga almashtiriladi.');if(!v)return;
    var r=await run(function(){return api('custom_map',{name:d.name,pack:+v.pack,status:WH.status})});if(r){toast(r.mapped+' ta qator bog‘landi');S.cache.wh=r.warehouse;renderWarehouse(page,r.warehouse)}}});
  $('whAdd').onclick=async function(){
    var v=await formBox('Yangi mahsulot',[{name:'name',label:'Nomi',required:true,placeholder:'Emal oq — 3 kg'},{name:'weightKg',label:'Og‘irlik (kg)',type:'number',step:'0.01',required:true},{name:'priceUsd',label:'Narx (USD)',type:'number',step:'0.01',required:true},{name:'blockUnits',label:'Blokda nechta (ixtiyoriy)',type:'number',step:'1'}],'Davom etish');if(!v)return;
    if(!await confirmBox('Mahsulotni qo‘shish','<p><b>'+esc(v.name)+'</b> · '+esc(v.weightKg)+' kg · '+usd(v.priceUsd)+(v.blockUnits?' · blokda '+esc(v.blockUnits):'')+'</p>','Qo‘shish'))return;
    var r=await run(function(){return api('product_add',{name:v.name,weightKg:v.weightKg,priceUsd:v.priceUsd,blockUnits:v.blockUnits||0,confirm:true,status:WH.status})},'Mahsulot qo‘shildi');if(r){S.cache.wh=r.warehouse;renderWarehouse(page,r.warehouse)}};
}

/* ----- Xodimlar ----- */
async function pageStaff(page,force){
  if(!S.cache.staff||force){page.innerHTML='<div class="loading">Xodimlar yuklanmoqda…</div>';var s=await run(function(){return api('staff_list')});if(!s)return;S.cache.staff=s}
  if(S.page!=='staff')return;renderStaff(page,S.cache.staff);
}
function renderStaff(page,s){
  page.innerHTML='<div class="grid g2">'+
   '<div class="card flush"><div class="card-h"><h3>Agentlar <span class="muted small">'+s.agents.filter(function(a){return a.active}).length+' faol</span></h3><button class="btn pri sm" id="stAddAgent">➕ Agent qo‘shish</button></div><div class="tbl-wrap" style="margin-top:12px"><table><thead><tr><th>Agent</th><th>Telegram ID</th><th class="right">Mijoz</th><th>Holat</th></tr></thead><tbody>'+
    s.agents.map(function(a){return '<tr class="click" data-agent="'+a.id+'"><td><div class="cell">'+avatar(a.name,a.photoUrl)+'<b>'+esc(a.name)+'</b></div></td><td class="num">'+a.id+'</td><td class="right num">'+a.clients+'</td><td>'+(a.active?(a.shiftOpen?pill('<span class="dot"></span>Smenada','p-ok'):pill('Faol','p-pri')):pill('Bloklangan','p-bad'))+'</td></tr>'}).join('')+'</tbody></table></div></div>'+
   '<div class="card flush"><div class="card-h"><h3>Kassirlar</h3><button class="btn pri sm" id="stAddCash">➕ Kassir qo‘shish</button></div><div class="tbl-wrap" style="margin-top:12px"><table><thead><tr><th>Kassir</th><th>Telegram ID</th><th class="right">Qabul</th><th>Oxirgi</th><th></th></tr></thead><tbody>'+
    (s.cashiers.length?s.cashiers.map(function(c){return '<tr><td><div class="cell">'+avatar(c.name,c.photoUrl)+'<div class="t"><b>'+esc(c.name)+'</b><small>'+(c.active?'Faol':'Yopilgan')+'</small></div></div></td><td class="num">'+c.id+'</td><td class="right num">'+c.accepted+'</td><td class="num">'+(c.lastTs?dday(c.lastTs):'—')+'</td><td class="actions"><button class="btn sm" data-cr="'+c.id+'">✏️</button>'+(S.primary?(c.active?'<button class="btn sm" data-ct="'+c.id+'">🔁</button><button class="btn sm danger" data-cd="'+c.id+'">Yopish</button>':'<button class="btn sm" data-ca="'+c.id+'">Ochish</button>'):'')+'</td></tr>'}).join(''):'<tr><td colspan="5" class="empty">Kassir yo‘q</td></tr>')+'</tbody></table></div></div>'+
   '</div>';
  bindAgentLinks(page);
  var done=function(r){if(r&&r.staff){S.cache.staff=r.staff;renderStaff(page,r.staff)}else pageStaff(page,true)};
  $('stAddAgent').onclick=async function(){
    var v=await formBox('Yangi agent',[{name:'id',label:'Telegram ID',required:true,placeholder:'123456789'},{name:'name',label:'Ismi',required:true}],'Davom etish','Agent botga /start yozib Telegram ID sini bilib oladi.');if(!v)return;
    var p=await run(function(){return api('agent_add_preview',{id:v.id,name:v.name})});if(!p)return;
    if(!await confirmBox('Agentni qo‘shish','<p><b>'+esc(p.name)+'</b> · ID '+esc(p.id)+'</p>'+(p.warning?'<p class="warn">'+esc(p.warning)+'</p>':''),'Qo‘shish'))return;
    var r=await run(function(){return api('agent_add_commit',{id:v.id,name:v.name,confirm:true})},'Agent qo‘shildi');if(r){S.dash=null;pageStaff(page,true)}};
  $('stAddCash').onclick=async function(){
    var v=await formBox('Yangi kassir',[{name:'id',label:'Telegram ID',required:true},{name:'name',label:'Ismi',required:true}],'Qo‘shish');if(!v)return;
    done(await run(function(){return api('cashier_add',{id:v.id,name:v.name,confirm:true})},'Kassir qo‘shildi'))};
  var find=function(id){return s.cashiers.find(function(c){return String(c.id)===String(id)})};
  page.querySelectorAll('[data-cr]').forEach(function(b){b.onclick=async function(){var c=find(b.dataset.cr);var v=await formBox('Kassir nomi',[{name:'name',label:'Yangi nom',value:c.name,required:true}]);if(!v)return;done(await run(function(){return api('cashier_rename',{cashierId:c.id,name:v.name,confirm:true})},'Saqlandi'))}});
  page.querySelectorAll('[data-ct]').forEach(function(b){b.onclick=async function(){var c=find(b.dataset.ct);var v=await formBox('Kassir akkauntini almashtirish',[{name:'newId',label:'Yangi Telegram ID',required:true}],'Almashtirish',esc(c.name)+' yangi Telegram akkauntga o‘tadi.');if(!v)return;done(await run(function(){return api('cashier_transfer',{cashierId:c.id,newId:v.newId,confirm:true})},'Akkaunt almashtirildi'))}});
  page.querySelectorAll('[data-cd]').forEach(function(b){b.onclick=async function(){var c=find(b.dataset.cd);if(!await confirmBox('Kassirni yopish','<p><b>'+esc(c.name)+'</b> botga kira olmaydi. Tarix saqlanadi.</p>','Yopish',true))return;done(await run(function(){return api('cashier_deactivate',{cashierId:c.id,confirm:true})},'Kassir yopildi'))}});
  page.querySelectorAll('[data-ca]').forEach(function(b){b.onclick=async function(){var c=find(b.dataset.ca);if(!await confirmBox('Kassirni qayta ochish','<p><b>'+esc(c.name)+'</b> yana ishlay oladi.</p>','Ochish'))return;done(await run(function(){return api('cashier_activate',{cashierId:c.id,confirm:true})},'Kassir ochildi'))}});
}

/* ----- Sozlamalar ----- */
function pageSettings(page){
  var me=S.me||{};
  page.innerHTML='<div class="grid g2" style="max-width:980px">'+
   '<div class="card"><div class="dh" style="margin-right:0">'+avatar(me.name,me.photoUrl,'lg')+'<div><h2>'+esc(me.name||'—')+'</h2><div class="muted">'+(S.primary?'Asosiy rahbar':'Rahbar')+' · Telegram ID '+esc(me.id)+'</div></div></div>'+
    '<dl class="kv"><dt>Web login</dt><dd><b>'+esc(S.login)+'</b></dd><dt>Telefon</dt><dd>'+esc(me.phone||'—')+'</dd></dl>'+
    '<p class="hint" style="margin-top:14px">Loginni o‘zgartirish yoki parolni unutgan bo‘lsangiz: botda <code>/webparol</code> yoki <code>/webparol yangi_login</code>. Web kirishni butunlay o‘chirish: <code>/webyopish</code>.</p>'+
    '<div class="actions" style="margin-top:16px"><button class="btn danger" id="stLogout">Chiqish</button></div></div>'+
   '<form class="card" id="pwForm"><div class="card-h"><h3>Parolni almashtirish</h3></div><div class="form" style="display:grid;gap:12px">'+
    '<label>Joriy parol<input type="password" name="old" autocomplete="current-password" required></label>'+
    '<label>Yangi parol<input type="password" name="new" autocomplete="new-password" minlength="8" required></label>'+
    '<label>Yangi parol (takror)<input type="password" name="new2" autocomplete="new-password" minlength="8" required></label>'+
    '<div class="form-err" id="pwErr"></div><button class="btn pri">Saqlash</button>'+
    '<p class="hint">Kamida 8 belgi. Parol almashganda boshqa kompyuterlardagi kirishlar yopiladi.</p></div></form>'+
   '</div>';
  $('stLogout').onclick=async function(){await auth('logout').catch(function(){});TOKEN='';store('rw-token',null);S.dash=null;S.cache={};showLogin()};
  $('pwForm').onsubmit=async function(e){
    e.preventDefault();var f=new FormData(this),err=$('pwErr');err.textContent='';
    if(f.get('new')!==f.get('new2')){err.textContent='Yangi parollar bir xil emas.';return}
    var r=await run(function(){return auth('change_password',{old:f.get('old'),new:f.get('new')})},'Parol almashtirildi');if(r)this.reset();
  };
}

boot();
})();
