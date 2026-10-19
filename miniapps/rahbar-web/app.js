/* ASMAN · Rahbar web paneli (kompyuter). Telegram'siz: login + parol, so'ng /api/manager bilan bir xil amallar. */
(function(){'use strict';
var API='/api/manager',AUTH='/api/web';
var TOKEN=store('rw-token')||'';
var S={dash:null,me:null,primary:false,page:'',loadedTs:0,maps:{},timer:0,cache:{}};
var $=function(id){return document.getElementById(id)};

/* ---------- helpers ---------- */
function store(k,v){try{if(v===undefined)return localStorage.getItem(k);if(v===null)localStorage.removeItem(k);else localStorage.setItem(k,v)}catch(e){return null}}
function esc(v){return String(v==null?'':v).replace(/[&<>"']/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]})}
/* Chiziqli ikonlar (Lucide uslubi, 24×24). */
var ICONS={
 home:'<path d="M3 10.5 12 3l9 7.5"/><path d="M5 9.5V21h14V9.5"/><path d="M9.5 21v-6h5v6"/>',
 compass:'<circle cx="12" cy="12" r="9"/><path d="m15.5 8.5-2 5-5 2 2-5z"/>',
 store:'<path d="M3 9.5 4.5 4h15L21 9.5"/><path d="M3 9.5a3 3 0 0 0 6 0 3 3 0 0 0 6 0 3 3 0 0 0 6 0"/><path d="M5 12v9h14v-9"/><path d="M10 21v-5h4v5"/>',
 wallet:'<path d="M19 7V5a2 2 0 0 0-2-2H5a2 2 0 0 0 0 4h14a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5"/><path d="M16 14h.01"/>',
 chart:'<path d="M3 3v18h18"/><path d="M7 15l4-4 3 3 5-6"/>',
 target:'<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1"/>',
 box:'<path d="M21 8 12 3 3 8v8l9 5 9-5z"/><path d="m3 8 9 5 9-5"/><path d="M12 13v8"/>',
 users:'<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20a6.5 6.5 0 0 1 13 0"/><path d="M16 4.5a3.5 3.5 0 0 1 0 7"/><path d="M18 14a6 6 0 0 1 3.5 6"/>',
 settings:'<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/>',
 refresh:'<path d="M21 12a9 9 0 0 1-15.5 6.2L3 16"/><path d="M3 12A9 9 0 0 1 18.5 5.8L21 8"/><path d="M21 3v5h-5"/><path d="M3 21v-5h5"/>',
 moon:'<path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/>',
 sun:'<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
 search:'<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
 x:'<path d="M18 6 6 18M6 6l12 12"/>',
 download:'<path d="M12 3v12"/><path d="m7 10 5 5 5-5"/><path d="M5 21h14"/>',
 alert:'<path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/><path d="M12 9v4M12 17h.01"/>',
 clock:'<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
 plus:'<path d="M12 5v14M5 12h14"/>',
 userplus:'<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20a6.5 6.5 0 0 1 13 0"/><path d="M19 8v6M16 11h6"/>',
 pin:'<path d="M12 21s-7-6.2-7-11.5a7 7 0 0 1 14 0C19 14.8 12 21 12 21z"/><circle cx="12" cy="9.5" r="2.5"/>',
 phone:'<path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1.9.3 1.8.6 2.7a2 2 0 0 1-.5 2.1L8 9.8a16 16 0 0 0 6 6l1.3-1.3a2 2 0 0 1 2.1-.4c.9.3 1.8.5 2.7.6a2 2 0 0 1 1.7 2z"/>',
 edit:'<path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z"/>',
 trash:'<path d="M3 6h18"/><path d="M8 6V4h8v2"/><path d="M6 6l1 15h10l1-15"/><path d="M10 11v6M14 11v6"/>',
 ban:'<circle cx="12" cy="12" r="9"/><path d="m5.6 5.6 12.8 12.8"/>',
 check:'<path d="M20 6 9 17l-5-5"/>',
 checkc:'<circle cx="12" cy="12" r="9"/><path d="m8 12 3 3 5-6"/>',
 swap:'<path d="M16 3l4 4-4 4"/><path d="M20 7H4"/><path d="M8 21l-4-4 4-4"/><path d="M4 17h16"/>',
 coins:'<circle cx="8" cy="8" r="6"/><path d="M18.1 10.4A6 6 0 1 1 10.3 18"/><path d="M7 6h1v4"/>',
 in:'<path d="M17 7 7 17"/><path d="M17 17H7V7"/>',
 out:'<path d="M7 17 17 7"/><path d="M7 7h10v10"/>',
 truck:'<path d="M1 4h14v12H1z"/><path d="M15 9h4l3 3v4h-7"/><circle cx="5.5" cy="18.5" r="2"/><circle cx="17.5" cy="18.5" r="2"/>',
 cart:'<circle cx="9" cy="20" r="1.5"/><circle cx="18" cy="20" r="1.5"/><path d="M2 3h3l2.7 12.4a2 2 0 0 0 2 1.6h8.6a2 2 0 0 0 2-1.6L22 7H6"/>',
 walk:'<circle cx="13" cy="4" r="2"/><path d="m9 21 2-6 3 3v3"/><path d="M8 11l3-4 3 2 3 1"/><path d="m11 15-1-4"/>',
 route:'<circle cx="6" cy="19" r="2.5"/><circle cx="18" cy="5" r="2.5"/><path d="M8.5 19H17a3.5 3.5 0 0 0 0-7H7a3.5 3.5 0 0 1 0-7h8.5"/>',
 bell:'<path d="M18 8a6 6 0 1 0-12 0c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.7 21a2 2 0 0 1-3.4 0"/>',
 receipt:'<path d="M4 2v20l3-2 3 2 2-2 2 2 3-2 3 2V2l-3 2-3-2-2 2-2-2-3 2z"/><path d="M8 8h8M8 12h8M8 16h5"/>',
 card:'<rect x="2" y="5" width="20" height="14" rx="2"/><path d="M2 10h20"/>',
 cash:'<rect x="2" y="6" width="20" height="12" rx="2"/><circle cx="12" cy="12" r="2.5"/><path d="M6 12h.01M18 12h.01"/>',
 dollar:'<path d="M12 2v20"/><path d="M17 6H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/>',
 bank:'<path d="M3 21h18"/><path d="M5 21V11M9.5 21V11M14.5 21V11M19 21V11"/><path d="m2 10 10-6 10 6z"/>',
 calendar:'<rect x="3" y="4.5" width="18" height="16.5" rx="2"/><path d="M3 9.5h18M8 2.5v4M16 2.5v4"/>',
 hourglass:'<path d="M6 2h12M6 22h12"/><path d="M7 2v4a5 5 0 0 0 10 0V2"/><path d="M7 22v-4a5 5 0 0 1 10 0v4"/>',
 timer:'<circle cx="12" cy="13" r="8"/><path d="M12 9v4l2 2"/><path d="M9 2h6"/>',
 warehouse:'<path d="M22 8.4V20a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V8.4a2 2 0 0 1 1.2-1.8l8-3.4a2 2 0 0 1 1.6 0l8 3.4A2 2 0 0 1 22 8.4z"/><path d="M6 21v-9h12v9M6 16h12"/>',
 sparkle:'<path d="M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9z"/>',
 help:'<circle cx="12" cy="12" r="9"/><path d="M9.1 9a3 3 0 0 1 5.8 1c0 2-3 3-3 3"/><path d="M12 17h.01"/>',
 list:'<path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/>',
 map:'<path d="m9 4-6 2.5v13.5l6-2.5 6 2.5 6-2.5V4l-6 2.5z"/><path d="M9 4v13.5M15 6.5V20"/>',
 file:'<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6M8 13h8M8 17h5"/>',
 logout:'<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="m16 17 5-5-5-5"/><path d="M21 12H9"/>',
 trend:'<path d="m22 7-8.5 8.5-5-5L2 17"/><path d="M16 7h6v6"/>',
 stop:'<rect x="5" y="5" width="14" height="14" rx="2"/>',
 note:'<path d="M4 4h16v12l-4 4H4z"/><path d="M16 20v-4h4"/>'
};
function ic(name,cls){var p=ICONS[name];return p?'<svg class="ico '+(cls||'')+'" viewBox="0 0 24 24" aria-hidden="true">'+p+'</svg>':''}
/* Eski emoji belgilar → ikon va rang (KPI kartalar uchun). */
var EMO={'🧭':['compass','blue'],'📦':['box','blue'],'💰':['coins','green'],'👣':['walk','violet'],'🏦':['bank','cyan'],'➕':['userplus','green'],
 '🧾':['receipt','red'],'🛒':['cart','amber'],'🚚':['truck','cyan'],'📅':['calendar','violet'],'💵':['cash','green'],'💳':['card','blue'],'💲':['dollar','green'],
 '🏬':['warehouse','violet'],'🏪':['store','blue'],'🆕':['sparkle','blue'],'❓':['help','amber'],'⚠️':['alert','red'],'⏳':['hourglass','amber'],'⏱':['timer','cyan']};
function tone(icon,color,size){return '<div class="tone t-'+(color||'blue')+'">'+ic(icon,size||'lg')+'</div>'}
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

var C={pri:'#1F6BFF',forest:'#246B57',yellow:'#F3CF56',orange:'#E46542',ink:'#191D23',gray:'#A3A8A1',violet:'#6D4FC2',cyan:'#0E7490'};
var AGE={fresh:['0–2 kun','p-ok',C.forest],yellow:['3–4 kun','p-warn',C.yellow],red:['5+ kun','p-bad',C.orange],scheduled:['Rejada','p-pri',C.pri],unknown:['Noma’lum','',C.gray]};
var AG_ST={active:['Faol','p-ok',C.forest],late:['Kechikkan','p-warn','#D9A520'],offline:['Yopiq','',C.gray]};
var KIND={delivery:ic('box','sm')+' Tovar berildi',payment:ic('coins','sm')+' To‘lov',sold:ic('cart','sm')+' Sotildi',return:ic('in','sm')+' Qaytarildi',order:ic('note','sm')+' Buyurtma',visit:ic('walk','sm')+' Tashrif'};
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
  clearInterval(S.timer);S.timer=setInterval(autoRefresh,30000);S.tick=0;
}

/* ---------- navigation ---------- */
var PAGES=[
  ['home','home','Asosiy','Bugungi jonli holat'],
  ['agents','compass','GPS markaz','Agentlar joylashuvi, marshruti va mijozlar xaritasi'],
  ['clients','store','Mijozlar','Barcha mijozlar va qarzdorlik'],
  ['cash','wallet','Kassa','Kirim, chiqim va qoldiq',0,'Moliya'],
  ['reports','chart','Hisobot','Davr bo‘yicha tahlil'],
  ['insights','target','Tahlil','Bugungi reja, mijozlar reytingi va hududlar'],
  ['warehouse','box','Ombor','Buyurtmalar va mahsulotlar',0,'Buyurtmalar'],
  ['staff','users','Xodimlar','Agentlar va kassirlar',1],
  ['settings','settings','Sozlamalar','Akkaunt va xavfsizlik',1]
];
function renderNav(){
  var d=S.dash,badge={};
  if(d){badge.warehouse=d.warehouse&&d.warehouse.newOrders;badge.cash=d.summary&&d.summary.pendingCount}
  $('nav').innerHTML=PAGES.filter(function(p){return !p[4]}).map(function(p){return '<button data-p="'+p[0]+'" class="'+(S.page===p[0]?'on':'')+'"'+(S.page===p[0]?' aria-current="page"':'')+'>'+ic(p[1])+'<span class="lbl">'+(p[5]||p[2])+'</span>'+(badge[p[0]]?'<span class="badge">'+badge[p[0]]+'</span>':'')+'</button>'}).join('');
  ['railStaff','railSettings'].forEach(function(id,i){var b=$(id);if(b)b.classList.toggle('on',S.page===['staff','settings'][i])});
}
$('nav').addEventListener('click',function(e){var b=e.target.closest('button[data-p]');if(b)location.hash=b.dataset.p});
$('meBtn').onclick=function(){location.hash='settings'};
/* Rail (1817): tezkor amallar; logotip bosilsa kengayadi / yig'iladi (holat saqlanadi). */
(function(){var r=$('rail'),w=store('rw-rail')==='1';r.classList.toggle('wide',w);$('railToggle').setAttribute('aria-expanded',w)})();
$('railToggle').onclick=function(){var r=$('rail'),w=!r.classList.contains('wide');r.classList.toggle('wide',w);this.setAttribute('aria-expanded',w);store('rw-rail',w?'1':'0');setTimeout(function(){Object.keys(S.maps).forEach(function(k){try{S.maps[k].invalidateSize()}catch(e){}})},260)};
$('railSearch').onclick=function(){$('gq').focus();$('gq').select()};
$('railStaff').onclick=function(){location.hash='staff'};
$('railSettings').onclick=function(){location.hash='settings'};
$('railFeed').onclick=function(){openFeedDrawer()};
function openFeedDrawer(){
  $('railDot').hidden=true;S.feedSeen=(S.feed||[]).length;
  openDrawer('<div class="dh"><div class="tone t-blue">'+ic('bell','lg')+'</div><div><h2>Jonli lenta</h2><div class="muted">Panel ochiq turganda kelgan hodisalar · har 30 soniyada tekshiriladi</div></div></div><div class="card"><div class="list" id="feed"></div></div>');
  renderFeed();
}
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
  var needDash=['home','agents','clients','cash','insights'].indexOf(p)>=0;
  if(needDash&&(!S.dash||force)){
    if(!S.dash)page.innerHTML='<div class="grid g4">'+'<div class="skel"></div>'.repeat(4)+'</div>';
    try{await loadDash()}catch(e){if(TOKEN){page.innerHTML=errState(e.message);page.querySelector('[data-retry]').onclick=function(){render(true)}}return}
    if(S.page!==p)return;
  }
  ({home:pageHome,agents:pageAgents,clients:pageClients,cash:pageCash,reports:pageReports,insights:pageInsights,warehouse:pageWarehouse,staff:pageStaff,settings:pageSettings})[p](page,force);
}
async function loadDash(){S.dash=await api('dashboard');S.loadedTs=Date.now();stamp();renderNav();return S.dash}
function stamp(){var u=$('updated');u.className='live';u.innerHTML=S.loadedTs?'<i></i>Jonli<span> · '+new Date(S.loadedTs).toLocaleTimeString('ru-RU',{hour:'2-digit',minute:'2-digit',second:'2-digit'})+'</span>':''}
async function refresh(){var b=$('refreshBtn');b.disabled=true;try{S.dash=null;S.cache={};await render(true);toast('Ma’lumotlar yangilandi')}finally{b.disabled=false}}
$('refreshBtn').onclick=refresh;
function autoRefresh(){
  if($('shell').hidden||!TOKEN)return;
  S.tick++;if(document.hidden&&S.tick%2)return;   // fon rejimida har 60 soniyada
  var prev=S.dash;
  loadDash().then(function(d){
    notifyAll(diffDash(prev,d));
    if(!$('modalOv').hidden)return;
    if(S.page==='home'&&$('dashSide')){$('dashSide').innerHTML=homeSide(d);bindSide();renderOps();if(EX.period!=="yesterday"&&S.tick%2===0)exRender(true)}
    else if(S.page==='cash')render();else if(S.page==='agents')updateAgentsLive();
  }).catch(function(){var u=$('updated');u.className='live off';u.innerHTML='<i></i>Aloqa yo‘q'});
}
/* Jonli o'zgarishlar: oldingi va yangi holatni solishtirib, faqat yangi hodisalar haqida xabar beradi. */
function diffDash(prev,d){
  var ev=[];if(!prev||!d)return ev;
  var seen={};prev.transactions.forEach(function(t){seen[t.type+t.id]=t.state});
  d.transactions.forEach(function(t){if(t.type!=='handover')return;var was=seen[t.type+t.id];
    if(was===undefined&&t.state==='pending')ev.push(['🪙 Kassaga topshiriq',t.agent+': '+usd(t.amountUsd)+' tasdiq kutmoqda','cash']);
    else if(was==='pending'&&t.state==='accepted')ev.push(['✅ Kassir qabul qildi',t.agent+': '+usd(t.amountUsd),'cash'])});
  var dn=(d.warehouse.newOrders||0)-(prev.warehouse.newOrders||0);
  if(dn>0)ev.push(['📦 Yangi buyurtma',dn+' ta yangi buyurtma omborda','warehouse']);
  var old={};prev.clients.forEach(function(c){old[c.id]=1});
  d.clients.forEach(function(c){if(!old[c.id]&&(c.createdTs||0)>=prev.generatedTs-300)ev.push(['🏪 Yangi mijoz',c.name+' · '+c.agent,'clients'])});
  var pa={};prev.agents.forEach(function(a){pa[a.id]=a});
  d.agents.forEach(function(a){var o=pa[a.id];if(!o)return;
    if(!o.shiftOpen&&a.shiftOpen)ev.push(['🧭 Ish boshlandi',a.name+' smenani ochdi','agents']);
    if(o.shiftOpen&&!a.shiftOpen)ev.push(['⏹ Ish tugadi',a.name+' smenani yopdi','agents'])});
  return ev;
}
var unseen=0,audioCtx=null;
document.addEventListener('pointerdown',function(){if(!audioCtx&&window.AudioContext&&store('rw-sound')!=='0'){try{audioCtx=new AudioContext()}catch(e){}}},{once:false,passive:true});
function beep(){
  if(store('rw-sound')==='0'||!audioCtx)return;
  try{var t=audioCtx.currentTime;[0,0.16].forEach(function(dt,i){var o=audioCtx.createOscillator(),g=audioCtx.createGain();o.frequency.value=i?1046:784;g.gain.setValueAtTime(0.0001,t+dt);g.gain.exponentialRampToValueAtTime(0.18,t+dt+0.02);g.gain.exponentialRampToValueAtTime(0.0001,t+dt+0.14);o.connect(g).connect(audioCtx.destination);o.start(t+dt);o.stop(t+dt+0.15)})}catch(e){}
}
function notifyAll(ev){
  if(!ev.length)return;
  if(ev.length>4)ev=ev.slice(0,3).concat([['🔔 Yana o‘zgarishlar',(ev.length-3)+' ta boshqa hodisa','home']]);
  beep();
  ev.forEach(function(e,i){setTimeout(function(){toast(e[0]+' — '+e[1])},i*2800)});
  S.feed=ev.map(function(e){return {t:e[0],b:e[1],p:e[2],ts:Date.now()/1000}}).concat(S.feed||[]).slice(0,30);renderFeed();
  if($('railDot'))$('railDot').hidden=false;
  if(document.hidden){unseen+=ev.length;document.title='('+unseen+') '+document.title.replace(/^\(\d+\) /,'')}
  if(store('rw-notify')==='1'&&window.Notification&&Notification.permission==='granted'&&document.hidden){
    ev.forEach(function(e){try{var n=new Notification(e[0],{body:e[1],icon:'/app/premium-kit/emblem.png',tag:'asman-'+e[2]+'-'+e[1]});n.onclick=function(){window.focus();location.hash=e[2];n.close()}}catch(x){}});
  }
}
document.addEventListener('visibilitychange',function(){if(!document.hidden&&unseen){unseen=0;document.title=document.title.replace(/^\(\d+\) /,'')}});
function renderFeed(){
  var el=$('feed');if(!el)return;var f=S.feed||[];
  var FI={cash:['coins','amber'],warehouse:['box','blue'],clients:['store','green'],agents:['compass','violet'],settings:['bell','cyan'],home:['bell','cyan']};
  el.innerHTML=f.length?f.map(function(e){var fi=FI[e.p]||FI.home;return '<div class="li click" data-go="'+e.p+'"><div class="tone t-'+fi[1]+'" style="width:34px;height:34px;border-radius:10px">'+ic(fi[0])+'</div><div class="t"><b>'+esc(e.t.replace(/^[^A-Za-z\u0400-\u04FFʻʼ‘’]+\s*/,''))+'</b><small>'+esc(e.b)+' · '+ago(e.ts)+'</small></div></div>'}).join(''):'<div class="muted small">Panel ochiq turganda yangi buyurtma, kassaga topshiriq, yangi mijoz va smena o‘zgarishlari shu yerda chiqadi.</div>';
  bindGo(el);
}
function themeIcon(){var dk=document.documentElement.dataset.theme==='dark';$('themeBtn').innerHTML=ic(dk?'sun':'moon')+'<span class="lbl">'+(dk?'Yorug‘ mavzu':'To‘q mavzu')+'</span>'}
$('themeBtn').onclick=function(){var d=document.documentElement;d.dataset.theme=d.dataset.theme==='dark'?'light':'dark';store('rw-theme',d.dataset.theme);themeIcon();if(S.page)render()};
themeIcon();
document.addEventListener('keydown',function(e){
  if(e.key==='Escape'){if(!$('modalOv').hidden)closeModal();else closeDrawer();return}
  if(/INPUT|TEXTAREA|SELECT/.test((e.target.tagName||''))||e.metaKey||e.ctrlKey||e.altKey)return;
  if(e.key==='/'){var s=document.querySelector('.page input[type=search]');if(s){e.preventDefault();s.focus()}}
  else if(e.key==='r'||e.key==='R')refresh();
});

/* ---------- global qidiruv (Ctrl/Cmd+K) ---------- */
var GS={items:[],sel:0};
function gsearch(q){
  var box=$('gres');q=String(q||'').trim().toLowerCase();
  if(q.length<2||!S.dash){box.hidden=true;return}
  var norm=function(v){return String(v||'').toLowerCase()},digits=q.replace(/\D/g,'');
  var ag=S.dash.agents.filter(function(a){return norm(a.name).indexOf(q)>=0||String(a.id)===q}).slice(0,5).map(function(a){return {k:'agent',id:a.id,t:a.name,s:(AG_ST[a.status]||AG_ST.offline)[0]+' · '+a.clients+' mijoz',ph:a.photoUrl}});
  var cl=S.dash.clients.filter(function(c){var hay=norm(c.name+' '+c.person+' '+c.address+' '+c.region+' '+c.agent);return hay.indexOf(q)>=0||(digits.length>=4&&String(c.phone||'').replace(/\D/g,'').indexOf(digits)>=0)}).slice(0,8)
    .map(function(c){return {k:'client',id:c.id,t:c.name,s:[c.region,c.agent,c.debtUsd>0?'qarz '+usd(c.debtUsd):''].filter(Boolean).join(' · '),ph:c.thumbUrl}});
  var pg=PAGES.filter(function(p){return norm(p[2]).indexOf(q)>=0}).map(function(p){return {k:'page',id:p[0],t:p[2],s:p[3],icon:p[1]}});
  GS.items=pg.concat(ag,cl);GS.sel=0;
  var row=function(it,i){return '<div class="it'+(i===GS.sel?' on':'')+'" data-i="'+i+'" role="option">'+(it.k==='page'?'<div class="tone t-blue" style="width:32px;height:32px">'+ic(it.icon)+'</div>':avatar(it.t,it.ph,it.k==='client'?'sq':''))+'<div class="t"><b>'+esc(it.t)+'</b><small>'+esc(it.s||'')+'</small></div></div>'};
  var html='',i=0,grp=function(name,arr){if(!arr.length)return;html+='<div class="grp">'+name+'</div>';arr.forEach(function(it){html+=row(it,i++)})};
  grp('Sahifalar',pg);grp('Agentlar',ag);grp('Mijozlar',cl);
  box.innerHTML=html||'<div class="empty" style="padding:20px">Hech narsa topilmadi</div>';box.hidden=false;
}
function gpick(i){var it=GS.items[i];if(!it)return;$('gres').hidden=true;$('gq').value='';$('gq').blur();
  if(it.k==='page')location.hash=it.id;else if(it.k==='agent')openAgent(it.id);else openClient(it.id)}
$('gq').addEventListener('input',debounce(function(){gsearch(this.value)},120));
$('gq').addEventListener('focus',function(){if(!S.dash)loadDash().catch(function(){});gsearch(this.value)});
$('gq').addEventListener('keydown',function(e){
  var n=GS.items.length;if(e.key==='ArrowDown'||e.key==='ArrowUp'){if(!n)return;e.preventDefault();GS.sel=(GS.sel+(e.key==='ArrowDown'?1:n-1))%n;
    $('gres').querySelectorAll('.it').forEach(function(el){el.classList.toggle('on',+el.dataset.i===GS.sel);if(+el.dataset.i===GS.sel)el.scrollIntoView({block:'nearest'})})}
  else if(e.key==='Enter'){e.preventDefault();gpick(GS.sel)}
  else if(e.key==='Escape'){$('gres').hidden=true;this.blur()}});
$('gres').addEventListener('mousedown',function(e){var it=e.target.closest('.it');if(it){e.preventDefault();gpick(+it.dataset.i)}});
$('gq').addEventListener('blur',function(){setTimeout(function(){$('gres').hidden=true},120)});
document.addEventListener('keydown',function(e){if((e.metaKey||e.ctrlKey)&&(e.key==='k'||e.key==='K')){e.preventDefault();$('gq').focus();$('gq').select()}});

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
var CHARTS={},chartSeq=0;
function smooth(pts,lo,hi){
  var cl=function(y){return lo==null?y:Math.max(lo,Math.min(hi,y))};
  if(pts.length<2)return pts.length?'M'+pts[0][0]+','+pts[0][1]:'';
  var d='M'+pts[0][0]+','+pts[0][1];
  for(var i=0;i<pts.length-1;i++){var p0=pts[i-1]||pts[i],p1=pts[i],p2=pts[i+1],p3=pts[i+2]||p2,t=.18;
    d+=' C'+(p1[0]+(p2[0]-p0[0])*t)+','+cl(p1[1]+(p2[1]-p0[1])*t)+' '+(p2[0]-(p3[0]-p1[0])*t)+','+cl(p2[1]-(p3[1]-p1[1])*t)+' '+p2[0]+','+p2[1]}
  return d;
}
function niceTop(max){if(max<=0)return 1;var e=Math.pow(10,Math.floor(Math.log10(max))),f=max/e;return (f<=1?1:f<=2?2:f<=2.5?2.5:f<=5?5:10)*e}
/* Silliq maydon grafigi: bir nechta qator, gradient to'ldirish, sichqoncha bilan tooltip. */
function areaChart(series,keys,colors,fmt,names){
  if(!series||!series.length)return '<div class="empty">Ma’lumot yo‘q</div>';
  fmt=fmt||num;var W=800,H=250,pl=56,pr=12,pt=14,pb=28,max=0,id='c'+(++chartSeq);
  series.forEach(function(s){keys.forEach(function(k){max=Math.max(max,Number(s[k]||0))})});
  var top=niceTop(max),n=series.length,step=n>1?(W-pl-pr)/(n-1):0;
  var X=function(i){return n>1?pl+i*step:(pl+W-pr)/2},Y=function(v){return pt+(H-pt-pb)*(1-Math.max(0,v)/top)};
  var out='<defs>'+keys.map(function(k,j){return '<linearGradient id="'+id+'g'+j+'" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="'+colors[j]+'" stop-opacity=".16"/><stop offset="1" stop-color="'+colors[j]+'" stop-opacity="0"/></linearGradient>'}).join('')+'</defs>';
  for(var i=0;i<=4;i++){var y=pt+(H-pt-pb)*(1-i/4);out+='<line class="grid-l" x1="'+pl+'" x2="'+(W-pr)+'" y1="'+y+'" y2="'+y+'"/><text x="'+(pl-10)+'" y="'+(y+4)+'" text-anchor="end">'+esc(fmt(top*i/4))+'</text>'}
  var every=Math.ceil(n/12);
  series.forEach(function(s,i){if(i%every===0||(i===n-1&&(n-1)%every>=every/2))out+='<text x="'+X(i)+'" y="'+(H-8)+'" text-anchor="middle">'+esc(s.day)+'</text>'});
  keys.forEach(function(k,j){var pts=series.map(function(s,i){return [X(i),Y(Number(s[k]||0))]}),line=smooth(pts,pt,H-pb);
    out+='<path d="'+line+' L'+pts[pts.length-1][0]+','+(H-pb)+' L'+pts[0][0]+','+(H-pb)+' Z" fill="url(#'+id+'g'+j+')"/>';
    out+='<path class="ln" d="'+line+'" fill="none" stroke="'+colors[j]+'" stroke-width="2.2" stroke-linecap="round"/>';
    out+='<circle class="hdot" data-k="'+j+'" r="5" cx="-99" cy="-99" fill="'+colors[j]+'" stroke="var(--card-solid)" stroke-width="2.5"/>'});
  out+='<line class="cross" x1="-99" x2="-99" y1="'+pt+'" y2="'+(H-pb)+'"/>';
  CHARTS[id]={series:series,keys:keys,colors:colors,fmt:fmt,names:names||keys,X:X,Y:Y,n:n,W:W,pl:pl,pr:pr};
  return '<div class="chartbox" data-chart="'+id+'"><svg class="chart" viewBox="0 0 '+W+' '+H+'" preserveAspectRatio="none" role="img">'+out+'</svg><div class="ctip"></div></div>';
}
var barChart=function(series,keys,colors,fmt){return areaChart(series,keys,colors,fmt,keys.map(function(k){return {deliveredUsd:'Realizatsiya',paymentsUsd:'To‘lovlar',visits:'Tashriflar'}[k]||k}))};
document.addEventListener('mousemove',function(e){
  var box=e.target.closest&&e.target.closest('.chartbox');
  document.querySelectorAll('.chartbox.hov').forEach(function(b){if(b!==box)b.classList.remove('hov')});
  if(!box)return;var c=CHARTS[box.dataset.chart];if(!c)return;
  var svg=box.querySelector('svg'),r=svg.getBoundingClientRect(),sx=(e.clientX-r.left)/r.width*c.W;
  var i=c.n>1?Math.round((sx-c.pl)/((c.W-c.pl-c.pr)/(c.n-1))):0;i=Math.max(0,Math.min(c.n-1,i));
  var s=c.series[i],x=c.X(i);box.classList.add('hov');
  var cr=svg.querySelector('.cross');cr.setAttribute('x1',x);cr.setAttribute('x2',x);
  svg.querySelectorAll('.hdot').forEach(function(d){var k=c.keys[+d.dataset.k];d.setAttribute('cx',x);d.setAttribute('cy',c.Y(Number(s[k]||0)))});
  var tip=box.querySelector('.ctip');tip.innerHTML='<b>'+esc(s.day)+'</b>'+c.keys.map(function(k,j){return '<div><span><i style="background:'+c.colors[j]+'"></i> '+esc(c.names[j])+'</span>&nbsp;&nbsp;<b style="display:inline;margin:0">'+esc(c.fmt(Number(s[k]||0)))+'</b></div>'}).join('');
  var px=x/c.W*r.width,tw=tip.offsetWidth;tip.style.left=Math.max(0,Math.min(r.width-tw,px+14>r.width-tw?px-tw-14:px+14))+'px';tip.style.top='8px';
});
/* Donut: [[nom, qiymat, rang], …] */
function donut(parts,center,sub){
  var total=parts.reduce(function(a,p){return a+Math.max(0,p[1])},0),R=70,r=48,cx=84,cy=84,a0=-Math.PI/2,out='';
  if(!total)out='<circle cx="84" cy="84" r="59" fill="none" stroke="var(--line2)" stroke-width="22"/>';
  parts.forEach(function(p){if(p[1]<=0)return;var a1=a0+p[1]/total*Math.PI*2-(parts.length>1?.02:0),big=a1-a0>Math.PI?1:0;
    if(p[1]===total){out+='<circle cx="84" cy="84" r="59" fill="none" stroke="'+p[2]+'" stroke-width="22"><title>'+esc(p[0])+': '+p[1]+'</title></circle>'}
    else out+='<path d="M'+(cx+R*Math.cos(a0))+','+(cy+R*Math.sin(a0))+' A'+R+','+R+' 0 '+big+' 1 '+(cx+R*Math.cos(a1))+','+(cy+R*Math.sin(a1))+' L'+(cx+r*Math.cos(a1))+','+(cy+r*Math.sin(a1))+' A'+r+','+r+' 0 '+big+' 0 '+(cx+r*Math.cos(a0))+','+(cy+r*Math.sin(a0))+' Z" fill="'+p[2]+'"><title>'+esc(p[0])+': '+p[1]+'</title></path>';
    a0=a1+(parts.length>1?.02:0)});
  out+='<text x="84" y="82" text-anchor="middle" font-size="24" font-weight="800">'+esc(center)+'</text><text x="84" y="102" text-anchor="middle" font-size="11" style="fill:var(--mu)">'+esc(sub||'')+'</text>';
  return '<div class="donut-wrap"><svg class="donut" viewBox="0 0 168 168">'+out+'</svg><div class="donut-legend">'+parts.map(function(p){return '<div><i style="background:'+p[2]+'"></i><span>'+esc(p[0])+'</span><b>'+(p[3]!=null?p[3]:num(p[1]))+'</b><small class="muted" style="width:40px;text-align:right">'+(total?Math.round(p[1]/total*100):0)+'%</small></div>'}).join('')+'</div></div>';
}
/* Mini grafik (KPI kartalar uchun). */
function spark(values,color){
  if(!values||values.length<2)return '';
  var max=Math.max.apply(null,values.concat([0])),min=Math.min.apply(null,values.concat([0])),W=92,H=34,rg=max-min||1;
  var pts=values.map(function(v,i){return [i*(W/(values.length-1)),H-3-(v-min)/rg*(H-6)]}),d=smooth(pts),gid='s'+(++chartSeq);
  return '<svg class="spark" viewBox="0 0 '+W+' '+H+'" preserveAspectRatio="none"><defs><linearGradient id="'+gid+'" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="'+color+'" stop-opacity=".35"/><stop offset="1" stop-color="'+color+'" stop-opacity="0"/></linearGradient></defs><path d="'+d+' L'+W+','+H+' L0,'+H+' Z" fill="url(#'+gid+')"/><path d="'+d+'" fill="none" stroke="'+color+'" stroke-width="2" stroke-linecap="round"/></svg>';
}
function delta(cur,prev){if(!prev)return '';var p=Math.round((cur-prev)/Math.abs(prev)*100);return '<span class="delta '+(p>=0?'up':'down')+'">'+(p>=0?'↑':'↓')+Math.abs(p)+'%</span>'}
function legend(items){return '<div class="legend">'+items.map(function(i){return '<span><i style="background:'+i[1]+'"></i>'+esc(i[0])+'</span>'}).join('')+'</div>'}
function errState(msg){return '<div class="card err-state"><div class="tone t-red">'+ic('alert','lg')+'</div><h3>Ma’lumotni yuklab bo‘lmadi</h3><p class="muted">'+esc(msg)+'</p><button class="btn pri" data-retry>'+ic('refresh','sm')+' Qayta urinish</button></div>'}
function emptyState(text,icon){return '<div class="empty">'+ic(icon||'list')+esc(text)+'</div>'}
function kpi(icon,label,value,sub,cls,go,spark){var m=EMO[icon]||[icon,'blue'];
  return '<div class="card kpi'+(spark?' has-spark':'')+(go?' click" data-go="'+go:'')+'">'+tone(m[0],m[1])+'<div><small>'+label+'</small><b>'+value+'</b><em class="'+(cls||'')+'">'+(sub||'')+'</em></div>'+(spark||'')+'</div>'}
function bindGo(root){root.querySelectorAll('[data-go]').forEach(function(el){el.onclick=function(){var g=el.dataset.go.split(':');
  if(g[1]==='debt'){CL.debt='debt';CL.age='';CL.sort='debtUsd';CL.dir=-1}
  else if(g[1]==='new'){CL.debt='';CL.age='';CL.sort='createdTs';CL.dir=-1}
  else if(g[1])S.cache.clientAge=g[1];
  if(g[0]==='clients'&&S.page==='home'){CL.agent=EX.agent||'';CL.page=0}
  location.hash=g[0]}})}

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
/* ----- Asosiy: Executive Dashboard V2 (1816 kompozitsiya + 1817 grafiklar) ----- */
var EX=(function(){try{return Object.assign({period:'today',from:'',to:'',agent:'',region:'',currency:'all',group:'auto'},JSON.parse(store('rw-ex')||'{}'))}catch(e){return {period:'today',from:'',to:'',agent:'',region:'',currency:'all',group:'auto'}}})();
var EX_PERIODS=[['today','Bugun'],['yesterday','Kecha'],['d7','7 kun'],['d30','30 kun'],['month','Joriy oy'],['custom','Davr'],['all','Umumiy']];
var OPS={f:''};
function exKey(){return JSON.stringify([EX.period,EX.from,EX.to,EX.agent,EX.region,EX.group])}
async function loadEx(force){
  var key='ex'+exKey();if(!force&&S.cache[key])return S.cache[key];
  var d=await api('executive',{period:EX.period,from:EX.from,to:EX.to,agentId:EX.agent?+EX.agent:undefined,region:EX.region||undefined,group:EX.group});
  S.cache[key]=d;S.ex=d;return d;
}
function exDelta(k){
  var d=k.delta;if(!d)return k.prev==null?'':'<span class="delta flat">—</span>';
  if(d.kind==='new')return '<span class="delta up">yangi</span>';
  var good=k.key==='debt'?d.pct<=0:d.pct>=0,cls=d.pct===0?'flat':good?'up':'down';
  return '<span class="delta '+cls+'">'+(d.pct>0?'↑':d.pct<0?'↓':'')+Math.abs(d.pct)+'%</span>';
}
function greet(){var h=new Date(Date.now()+5*3600e3).getUTCHours();return h<5?'Xayrli tun':h<11?'Xayrli tong':h<17?'Xayrli kun':'Xayrli kech'}
function pageHome(page,force){
  var name=(S.me&&S.me.name||'').split(' ')[0];
  $('pageTitle').textContent=greet()+(name?', '+name:'');
  var nd=new Date(Date.now()+5*3600e3),WD=['yakshanba','dushanba','seshanba','chorshanba','payshanba','juma','shanba'],MO=['yanvar','fevral','mart','aprel','may','iyun','iyul','avgust','sentyabr','oktyabr','noyabr','dekabr'];
  $('pageSub').textContent=nd.getUTCDate()+'-'+MO[nd.getUTCMonth()]+' '+nd.getUTCFullYear()+', '+WD[nd.getUTCDay()];
  page.innerHTML=
   '<div class="toolbar" id="exBar">'+
     '<div class="seg" id="exSeg" role="tablist" aria-label="Davr">'+EX_PERIODS.map(function(p){return '<button role="tab" data-p="'+p[0]+'" class="'+(EX.period===p[0]?'on':'')+'" aria-selected="'+(EX.period===p[0])+'">'+p[1]+'</button>'}).join('')+'</div>'+
     '<span id="exCustom" class="actions"'+(EX.period==='custom'?'':' hidden')+'><input type="date" id="exFrom" value="'+esc(EX.from||today())+'" max="'+today()+'" style="width:auto" aria-label="Boshlanish sanasi"><input type="date" id="exTo" value="'+esc(EX.to||today())+'" max="'+today()+'" style="width:auto" aria-label="Tugash sanasi"><button class="btn ink sm" id="exGo">Qo‘llash</button></span>'+
     '<select id="exRegion" aria-label="Hudud"><option value="">Barcha hududlar</option></select>'+
     '<select id="exAgent" aria-label="Agent"><option value="">Barcha agentlar</option></select>'+
     '<select id="exCur" aria-label="Valyuta" title="Yig‘ilgan pul qaysi valyutada ko‘rsatilsin">'+[['all','Pul: hammasi (USD)'],['usd','Naqd dollar'],['uzs','Naqd so‘m'],['card','Karta']].map(function(o){return '<option value="'+o[0]+'"'+(EX.currency===o[0]?' selected':'')+'>'+o[1]+'</option>'}).join('')+'</select>'+
     '<button class="btn sm" id="exReset" title="Filtrlarni tozalash">'+ic('x','sm')+' Tozalash</button>'+
     '<span class="grow"></span><span class="muted small" id="exLabel"></span>'+
   '</div>'+
   '<div class="dash"><div class="dash-main" id="exBody">'+
     '<div class="grid g4">'+'<div class="skel"></div>'.repeat(4)+'</div><div class="grid g3">'+'<div class="skel" style="height:86px"></div>'.repeat(3)+'</div><div class="skel" style="height:320px"></div>'+
   '</div><aside class="dash-side" id="dashSide" aria-label="Faollik paneli">'+homeSide(S.dash)+'</aside></div>';
  var save=function(){store('rw-ex',JSON.stringify(EX))},reload=function(){save();exRender(true)};
  $('exSeg').onclick=function(e){var b=e.target.closest('button');if(!b)return;$('exSeg').querySelectorAll('button').forEach(function(x){x.classList.toggle('on',x===b);x.setAttribute('aria-selected',x===b)});
    if(b.dataset.p==='custom'){$('exCustom').hidden=false;$('exFrom').focus();return}$('exCustom').hidden=true;EX.period=b.dataset.p;reload()};
  $('exGo').onclick=function(){var f=$('exFrom').value,t=$('exTo').value;if(!f||!t){toast('Ikkala sanani tanlang',true);return}EX.period='custom';EX.from=f;EX.to=t;reload()};
  $('exRegion').onchange=function(){EX.region=this.value;reload()};
  $('exAgent').onchange=function(){EX.agent=this.value;reload()};
  $('exCur').onchange=function(){EX.currency=this.value;save();exRender(false)};
  $('exReset').onclick=function(){EX={period:'today',from:'',to:'',agent:'',region:'',currency:'all',group:'auto'};save();pageHome(page)};
  bindSide();
  exRender(!!force);
}
async function exRender(force){
  var d;try{d=await loadEx(force)}catch(e){if(S.page!=='home')return;$('exBody').innerHTML=errState(e.message);$('exBody').querySelector('[data-retry]').onclick=function(){exRender(true)};return}
  if(S.page!=='home'||!$('exBody'))return;
  var fill=function(sel,items,cur,ph){sel.innerHTML='<option value="">'+ph+'</option>'+items.map(function(o){return '<option value="'+esc(o[0])+'"'+(String(cur)===String(o[0])?' selected':'')+'>'+esc(o[1])+'</option>'}).join('')};
  fill($('exRegion'),d.options.regions.map(function(r){return [r.key,r.name]}),EX.region,'Barcha hududlar');
  fill($('exAgent'),d.options.agents.map(function(a){return [a.id,a.name]}),EX.agent,'Barcha agentlar');
  var r=d.range;$('exLabel').textContent=r.label+(r.prevLabel?' · taqqoslash: '+r.prevLabel:'');
  var col=function(k){return d.series.map(function(x){return Number(x[k]||0)})},K={};d.kpis.forEach(function(k){K[k.key]=k});
  var c=d.collections,cur=EX.currency,coll=K.collected,collVal=usd(coll.value),collSub=exDelta(coll)+' oldingi davrga nisbatan';
  if(cur==='usd'){collVal=usd(c.cashUsd);collSub='Naqd dollarda olingan'}
  else if(cur==='uzs'){collVal=uzs(c.cashUzs);collSub='≈ '+usd(c.cashUzsAsUsd)+' to‘lov kunidagi kurs bilan'}
  else if(cur==='card'){collVal=usd(c.cardUsd);collSub='Karta orqali (kassir tasdiqlagan)'}
  var prevTxt=function(k,money){return k.prev!=null?' <span class="muted">oldin '+(money?usd(k.prev):num(k.prev))+'</span>':''};
  var sp=function(key,color){return d.series.length>1?spark(col(key),color):''};
  var ac=d.agentsCash;
  // Undiruv darajasi: yig'ilgan pul / realizatsiya (davr bo'yicha)
  var rate=K.realization.value>0?Math.min(999,Math.round(coll.value/K.realization.value*100)):null;
  var aging=d.debtAging,amax=Math.max.apply(null,aging.map(function(b){return b.usd}).concat([1])),atot=aging.reduce(function(a,b){return a+b.usd},0);
  var regs=d.regionSales.filter(function(x){return x.realizationUsd>0}),rtot=regs.reduce(function(a,x){return a+x.realizationUsd},0),RC=[C.yellow,C.forest,C.orange,C.ink,C.pri,C.violet,C.cyan,C.gray];
  var ag=d.agents.filter(function(a){return a.realizationUsd||a.paymentsUsd||a.visits}).slice(0,8),gmax=Math.max.apply(null,ag.map(function(a){return Math.max(a.realizationUsd,a.paymentsUsd)}).concat([1]));
  var groups=[['auto','Avto'],['day','Kun'],['week','Hafta'],['month','Oy']];
  var kcard=function(cls,icon,label,value,sub,go,sparkHtml){var m=EMO[icon]||[icon,'blue'];return '<div class="card kpi lift click '+cls+(sparkHtml?' has-spark':'')+'" data-go="'+go+'" tabindex="0" role="button">'+tone(m[0],m[1])+'<div><small>'+label+'</small><b>'+value+'</b><em>'+sub+'</em></div>'+(sparkHtml||'')+'</div>'};
  $('exBody').innerHTML=
   '<div class="grid g4 kpis">'+
     kcard('','📦','Realizatsiya',usd(K.realization.value),exDelta(K.realization)+prevTxt(K.realization,1),'reports',sp('realizationUsd',C.pri))+
     kcard('','💰','Yig‘ilgan pul',collVal,cur==='all'?exDelta(coll)+prevTxt(coll,1):collSub,'cash',cur==='all'?sp('paymentsUsd',C.forest):'')+
     kcard('c-orange','🧾','Umumiy qarzdorlik',usd(K.debt.value),exDelta(K.debt)+' davr boshiga nisbatan'+(d.advanceUsd?' · avans '+usd(d.advanceUsd):''),'clients:debt')+
     kcard('c-ink','💵','Agentlardagi pul',usd(ac.cashUsd),'+ '+uzs(ac.cashUzs)+(ac.pendingUsd||ac.pendingUzs?' · kassirda kutilmoqda: '+usd(ac.pendingUsd)+(ac.pendingUzs?' + '+uzs(ac.pendingUzs):''):''),'cash')+
   '</div>'+
   '<div class="grid g3 kpis sm">'+
     kcard('','🧭','Faol agentlar',num(K.activeAgents.value),exDelta(K.activeAgents)+prevTxt(K.activeAgents),'agents')+
     kcard('','➕','Yangi mijozlar',num(K.newClients.value),exDelta(K.newClients)+prevTxt(K.newClients),'clients:new')+
     kcard('','👣','Tashriflar',num(K.visits.value),exDelta(K.visits)+prevTxt(K.visits),'reports')+
   '</div>'+
   '<div class="card"><div class="card-h"><div><h3>'+ic('trend')+' Savdo</h3><div class="stat-strip" style="margin-top:8px"><div><b style="font-size:28px">'+usd(K.realization.value)+'</b>'+(K.realization.delta&&K.realization.delta.kind==='pct'?'<span class="pill-badge'+(K.realization.delta.pct<0?' o':'')+'">'+(K.realization.delta.pct>=0?'+':'')+K.realization.delta.pct+'%</span>':'')+'<small>'+esc(r.label)+' realizatsiya · yig‘ilgan '+usd(coll.value)+'</small></div></div></div>'+
     '<div class="acts"><div class="seg" id="exGrp">'+groups.map(function(g){return '<button data-g="'+g[0]+'" class="'+(EX.group===g[0]?'on':'')+'">'+g[1]+'</button>'}).join('')+'</div><button class="round-btn" data-go="reports" title="Hisobotga o‘tish">'+ic('out','sm')+'</button></div></div>'+
     legend([['Realizatsiya',C.orange],['Yig‘ilgan pul',C.forest]])+'<div style="margin-top:8px">'+areaChart(d.series,['realizationUsd','paymentsUsd'],[C.orange,C.forest],usd,['Realizatsiya','Yig‘ilgan pul'])+'</div></div>'+
   '<div class="grid g-main">'+
     '<div class="card"><div class="card-h"><div><h3>'+ic('clock')+' Qarzdorlik yoshi</h3><small class="muted">To‘lanmagan tovar, berilgan kunidan beri (FIFO)</small></div><button class="round-btn" data-go="clients:debt" title="Qarzdor mijozlar">'+ic('out','sm')+'</button></div>'+
       (atot?'<div class="aging">'+aging.map(function(b,i){return '<div class="col'+(i===aging.length-1?' last':'')+'" title="'+esc(b.label)+' kun: '+usd(b.usd)+'"><i style="height:'+Math.max(3,b.usd/amax*100)+'%"></i></div>'}).join('')+'</div><div class="aging-x">'+aging.map(function(b){return '<span>'+esc(b.label)+'</span>'}).join('')+'</div>'+
       '<div class="list aging-rows">'+aging.map(function(b,i){return '<div class="li'+(i===aging.length-1?' last':'')+'"><i></i><div class="t"><b>'+esc(b.label)+' kun</b></div><span class="muted small">'+b.clients+' mijoz</span>&nbsp;&nbsp;<b class="num">'+usd(b.usd)+'</b></div>'}).join('')+'</div>':emptyState('To‘lanmagan qarz yo‘q','checkc'))+'</div>'+
     '<div class="card c-forest"><div class="card-h"><h3>'+ic('target')+' Undiruv darajasi</h3></div>'+
       '<div class="quota">'+quotaRing(rate)+'</div><p class="small" style="margin:8px 0 0;opacity:.85;text-align:center">'+esc(r.label)+': yig‘ilgan '+usd(coll.value)+' / realizatsiya '+usd(K.realization.value)+'</p></div>'+
   '</div>'+
   '<div class="grid g2">'+
     '<div class="card"><div class="card-h"><h3>'+ic('map')+' Hududlar bo‘yicha savdo</h3><span class="muted small">'+usd(rtot)+'</span></div>'+
       (regs.length?'<div class="segbar">'+regs.slice(0,8).map(function(x,i){return '<i style="flex:'+Math.max(x.realizationUsd,rtot*.02)+';background:'+RC[i%RC.length]+'" title="'+esc(x.name)+': '+usd(x.realizationUsd)+'"></i>'}).join('')+'</div>'+
       '<div class="list seglist">'+regs.slice(0,8).map(function(x,i){return '<div class="li"><i style="background:'+RC[i%RC.length]+'"></i><div class="t"><b>'+esc(x.name)+'</b></div><span class="muted small">'+Math.round(x.realizationUsd/rtot*100)+'% · pul '+usd(x.paymentsUsd)+'</span>&nbsp;&nbsp;<b class="num">'+usd(x.realizationUsd)+'</b></div>'}).join('')+'</div>':emptyState('Bu davrda savdo yo‘q','map'))+'</div>'+
     '<div class="card"><div class="card-h"><h3>'+ic('chart')+' Agentlar KPI reytingi</h3>'+legend([['Realizatsiya',C.pri],['Pul',C.forest]])+'</div>'+
       (ag.length?ag.map(function(a,i){return '<div class="hbar" data-agent="'+a.agentId+'"><span class="nm">'+(i+1)+'. '+esc(a.agent)+'</span><div style="display:grid;gap:4px"><div class="track"><i style="width:'+(Math.max(0,a.realizationUsd)/gmax*100)+'%;background:'+C.pri+'"></i></div><div class="track"><i style="width:'+(a.paymentsUsd/gmax*100)+'%;background:'+C.forest+'"></i></div></div><b>'+usd(a.realizationUsd)+(a.collectionPct!=null?' <span class="pill '+(a.collectionPct>=70?'p-ok':a.collectionPct>=40?'p-warn':'p-bad')+'">'+Math.round(a.collectionPct)+'%</span>':'')+'</b></div>'}).join(''):emptyState('Bu davrda agent faoliyati yo‘q','compass'))+'</div>'+
   '</div>'+
   '<div class="grid g2">'+
     '<div class="card"><div class="card-h"><h3>'+ic('receipt')+' Qarzdorlik dinamikasi</h3><span class="muted small">Har '+({hour:'soat',day:'kun',week:'hafta',month:'oy'}[d.group]||'davr')+' oxirida</span></div>'+areaChart(d.series,['debtUsd'],[C.ink],usd,['Umumiy qarz'])+'</div>'+
     '<div class="card"><div class="card-h"><h3>'+ic('compass')+' GPS monitoring</h3><button class="round-btn" data-go="agents" title="GPS markazga o‘tish">'+ic('out','sm')+'</button></div><div class="mini-map" id="miniMap"></div><div id="miniAg"></div></div>'+
   '</div>'+
   '<div class="card flush"><div class="card-h"><h3>'+ic('list')+' So‘nggi muhim operatsiyalar</h3><div class="acts"><div class="seg" id="opsSeg">'+[['','Hammasi'],['in','Kirim'],['out','Chiqim'],['pending','Kutilmoqda']].map(function(x){return '<button data-f="'+x[0]+'" class="'+(OPS.f===x[0]?'on':'')+'">'+x[1]+'</button>'}).join('')+'</div><button class="round-btn" data-go="cash" title="Moliyaga o‘tish">'+ic('out','sm')+'</button></div></div><div class="tbl-wrap" id="opsBody" style="margin-top:10px"></div></div>';
  $('exGrp').onclick=function(e){var b=e.target.closest('button');if(!b)return;EX.group=b.dataset.g;store('rw-ex',JSON.stringify(EX));exRender(false)};
  $('opsSeg').onclick=function(e){var b=e.target.closest('button');if(!b)return;OPS.f=b.dataset.f;$('opsSeg').querySelectorAll('button').forEach(function(x){x.classList.toggle('on',x===b)});renderOps()};
  $('exBody').querySelectorAll('[role=button][data-go]').forEach(function(el){el.addEventListener('keydown',function(e){if(e.key==='Enter'||e.key===' '){e.preventDefault();el.click()}})});
  bindGo($('exBody'));bindAgentLinks($('exBody'));renderOps();miniMap();
  if($('calCard')){$('calCard').innerHTML=calendarHtml(d.calendar);bindSide()}
}
function quotaRing(p){
  var v=p==null?0:Math.min(100,p),R=58,L=2*Math.PI*R,off=L*(1-v/100);
  return '<svg viewBox="0 0 150 150" role="img" aria-label="Undiruv '+(p==null?'—':p+'%')+'"><circle cx="75" cy="75" r="'+R+'" fill="none" stroke="rgba(255,255,255,.18)" stroke-width="12"/>'+
    '<circle cx="75" cy="75" r="'+R+'" fill="none" stroke="'+C.yellow+'" stroke-width="12" stroke-linecap="round" stroke-dasharray="'+L+'" stroke-dashoffset="'+off+'" transform="rotate(-90 75 75)" style="transition:stroke-dashoffset .8s var(--ease)"/>'+
    '<text x="75" y="80" text-anchor="middle" font-size="30" font-weight="600" fill="#fff">'+(p==null?'—':p+'%')+'</text><text x="75" y="100" text-anchor="middle" font-size="11" fill="rgba(255,255,255,.75)">undirildi</text></svg>';
}
function renderOps(){
  var el=$('opsBody');if(!el||!S.dash)return;
  var ST={pending:['Kutilmoqda','p-warn'],accepted:['Qabul qilindi','p-ok'],rejected:['Rad etildi','p-bad'],expense:['Chiqim','p-bad']};
  var rows=S.dash.transactions.filter(function(t){if(OPS.f==='in')return t.type==='handover';if(OPS.f==='out')return t.type==='expense';if(OPS.f==='pending')return t.state==='pending';return true}).slice(0,8);
  el.innerHTML=rows.length?'<table class="ops"><thead><tr><th>Sana</th><th>Operatsiya</th><th>Kim</th><th class="right">Summa</th><th>Holat</th></tr></thead><tbody>'+rows.map(function(t){var h=t.type==='handover',st=ST[t.state]||[esc(t.state),''];
    return '<tr><td class="num">'+dt(t.acceptedTs||t.ts)+'</td><td>'+(h?ic('in','sm')+' Kassaga topshiriq':ic('out','sm')+' '+esc(t.category))+(h&&t.amountUzs?' <small class="muted">'+uzs(t.amountUzs)+'</small>':'')+'</td><td><b>'+esc(h?t.agent:(t.recipient||'—'))+'</b>'+(t.cashier?'<br><small class="muted">'+esc(t.cashier)+'</small>':'')+'</td><td class="right num '+(h?(t.state==='accepted'?'ok':''):'bad')+'">'+(h?'+':'−')+usd(t.amountUsd)+'</td><td>'+pill('<span class="dot"></span>'+st[0],st[1])+'</td></tr>'}).join('')+'</tbody></table>':emptyState('Operatsiya yo‘q','list');
}
function miniMap(){
  var el=$('miniMap');if(!el||!window.L)return;
  if(S.maps.mini){try{S.maps.mini.remove()}catch(e){}}
  var m=L.map(el,{zoomControl:false,attributionControl:false,dragging:true,scrollWheelZoom:false}).setView([40.45,71.6],9);
  L.tileLayer('/tiles/{z}/{x}/{y}.png',{maxZoom:19}).addTo(m);S.maps.mini=m;
  var pts=[];S.dash.agents.forEach(function(a){if(a.lat==null)return;pts.push([a.lat,a.lon]);L.marker([a.lat,a.lon],{icon:agentIcon(a)}).addTo(m).bindTooltip(esc(a.name)+' · '+(a.lastGpsTs?ago(a.lastGpsTs):'GPS yo‘q')).on('click',function(){GPS.agent=a.id;gpsSave();location.hash='agents'})});
  if(pts.length)m.fitBounds(pts,{padding:[30,30],maxZoom:13});setTimeout(function(){m.invalidateSize()},80);
  var by={active:0,late:0,offline:0};S.dash.agents.forEach(function(a){by[a.status]=(by[a.status]||0)+1});
  var stale=S.dash.agents.filter(function(a){return a.shiftOpen&&a.lastGpsTs&&Date.now()/1000-a.lastGpsTs>STALE}).length;
  $('miniAg').innerHTML='<div class="actions">'+pill('<span class="dot"></span>Faol '+by.active,'p-ok')+pill('<span class="dot"></span>Kechikkan '+by.late,'p-warn')+pill('Yopiq '+by.offline)+(stale?pill(ic('alert','sm')+' GPS eskirgan: '+stale,'p-bad'):'')+'</div>';
}
/* O'ng panel (1816 Activity/Calendar): kassa, kalendar, diqqat, jonli lenta — filtrdan qat'i nazar hozirgi holat */
function homeSide(d){
  var s=d.summary,c=d.cash,cal=S.ex&&S.ex.calendar;
  var overdue=d.clients.filter(function(x){return x.age==='red'&&!x.blacklisted});
  var pend=d.transactions.filter(function(t){return t.type==='handover'&&t.state==='pending'});
  var alerts='';
  if(overdue.length)alerts+='<div class="alert r" data-go="clients:red"><div class="tone">'+ic('clock')+'</div><div><b>'+overdue.length+' mijozga 5+ kun tashrif yo‘q</b><small>Qizil — uzoq vaqt tashrif bo‘lmagan</small></div></div>';
  if(pend.length)alerts+='<div class="alert y" data-go="cash"><div class="tone">'+ic('hourglass')+'</div><div><b>'+pend.length+' topshiriq tasdiq kutmoqda</b><small>Jami '+usd(s.pendingUsd)+'</small></div></div>';
  if(d.warehouse.newOrders)alerts+='<div class="alert b" data-go="warehouse"><div class="tone">'+ic('box')+'</div><div><b>'+d.warehouse.newOrders+' yangi buyurtma</b><small>Ochiq: '+d.warehouse.openOrders+'</small></div></div>';
  if(!alerts)alerts=emptyState('Diqqat talab qiladigan holat yo‘q','checkc');
  return '<div class="card hero"><div style="position:relative"><small>'+ic('wallet','sm')+' Umumiy kassa qoldig‘i</small><b class="big">'+usd(c.balanceUsd)+'</b><div class="muted small">Naqd va karta, USD ekvivalentida</div></div>'+
      '<div class="hero-stats" style="grid-template-columns:1fr 1fr"><div><small>Bugun qabul</small><b>'+usd(c.acceptedTodayUsd)+'</b></div><div><small>Bugun xarajat</small><b>'+usd(c.expensesTodayUsd)+'</b></div></div></div>'+
    '<div class="card" id="calCard">'+calendarHtml(cal)+'</div>'+
    '<div class="card"><div class="card-h"><h3>'+ic('alert')+' Diqqat</h3></div>'+alerts+'</div>'+
    '<div class="card"><div class="card-h"><h3>'+ic('bell')+' Jonli lenta</h3><span class="live" style="padding:4px 9px"><i></i>30 s</span></div><div class="list" id="feed"></div></div>';
}
function calendarHtml(cal){
  if(!cal)return '<div class="card-h"><h3>'+ic('calendar')+' Kalendar</h3></div><div class="skel" style="height:220px;border:0"></div>';
  var MN=['Yanvar','Fevral','Mart','Aprel','May','Iyun','Iyul','Avgust','Sentyabr','Oktyabr','Noyabr','Dekabr'];
  var vals=Object.keys(cal.values).map(function(k){return cal.values[k].realizationUsd}),max=Math.max.apply(null,vals.concat([0]));
  var t=today(),ym=cal.year+'-'+String(cal.month).padStart(2,'0'),sel=EX.period==='custom'&&EX.from===EX.to?EX.from:(EX.period==='today'?t:'');
  var html='<div class="cal-head"><b>'+ic('calendar')+' '+MN[cal.month-1]+' '+cal.year+'</b><span class="muted small">kunlik realizatsiya</span></div><div class="cal">'+['Du','Se','Ch','Pa','Ju','Sh','Ya'].map(function(x){return '<span>'+x+'</span>'}).join('');
  for(var i=0;i<cal.firstWeekday;i++)html+='<span></span>';
  for(var dd=1;dd<=cal.days;dd++){var key=ym+'-'+String(dd).padStart(2,'0'),v=(cal.values[dd]||{}).realizationUsd||0,lv=v<=0?0:max?Math.ceil(v/max*3):0;
    html+='<button data-day="'+key+'" class="'+(lv?'h'+lv:'')+(key===t?' today':'')+(key===sel?' sel':'')+'"'+(key>t?' disabled':'')+' title="'+key+(v?': '+usd(v):'')+'">'+dd+'</button>'}
  return html+'</div><p class="hint" style="margin-top:10px">Kunni bosing — dashboard o‘sha kun bo‘yicha ko‘rsatiladi.</p>';
}
function bindSide(){
  var side=$('dashSide');if(!side)return;bindGo(side);renderFeed();
  side.querySelectorAll('[data-day]').forEach(function(b){b.onclick=function(){EX.period='custom';EX.from=EX.to=b.dataset.day;store('rw-ex',JSON.stringify(EX));pageHome($('page'))}});
}
function agentReportTable(rows){
  if(!rows||!rows.length)return '<div class="empty">Agentlar yo‘q</div>';
  return '<table><thead><tr><th>Agent</th><th class="right">Realizatsiya</th><th class="right">To‘lov</th><th class="right">Tashrif</th><th class="right">Yangi</th><th class="right">Ish vaqti</th><th class="right">Masofa</th></tr></thead><tbody>'+
   rows.map(function(a){return '<tr class="click" data-agent="'+a.agentId+'"><td><b>'+esc(a.agent)+'</b></td><td class="right num">'+usd(a.deliveredUsd)+'</td><td class="right num">'+usd(a.paymentsUsd)+'</td><td class="right num">'+a.visits+'</td><td class="right num">'+a.newClients+'</td><td class="right num">'+hours(a.workSeconds)+'</td><td class="right num">'+num(a.distanceKm,1)+' km</td></tr>'}).join('')+'</tbody></table>';
}
function bindAgentLinks(root){root.querySelectorAll('[data-agent]').forEach(function(el){el.onclick=function(){openAgent(+el.dataset.agent)}})}
function bindClientLinks(root){root.querySelectorAll('[data-client]').forEach(function(el){el.onclick=function(e){if(e.target.closest('a[href]'))return;openClient(+el.dataset.client)}})}

/* ----- Agentlar ----- */
/* ----- GPS Control Center: chapda agentlar, markazda xarita, o'ngda tanlangan agent ----- */
var GPS=(function(){try{return Object.assign({agent:null,region:'',status:'',q:'',clients:true,day:''},JSON.parse(store('rw-gps')||'{}'))}catch(e){return {agent:null,region:'',status:'',q:'',clients:true,day:''}}})();
var STALE=300;  // dashboard qoidasi: oxirgi GPS 5 daqiqadan eski bo'lsa "kechikkan"
function gpsSave(){store('rw-gps',JSON.stringify(GPS))}
function agentRegions(){
  // Agent hududi = mijozlari joylashgan hududlar (agentlarda alohida hudud maydoni yo'q).
  var m={};S.dash.clients.forEach(function(c){var k=(c.region||'').trim();if(!k)return;(m[c.agentId]=m[c.agentId]||{})[k]=((m[c.agentId]||{})[k]||0)+1});return m;
}
function gpsAgents(){
  var q=GPS.q.trim().toLowerCase(),reg=agentRegions();
  return S.dash.agents.filter(function(a){
    if(GPS.status&&a.status!==GPS.status)return false;
    if(GPS.region&&!(reg[a.id]&&reg[a.id][GPS.region]))return false;
    if(q&&a.name.toLowerCase().indexOf(q)<0)return false;return true})
   .sort(function(a,b){return (b.shiftOpen-a.shiftOpen)||(b.done-a.done)||a.name.localeCompare(b.name)});
}
function pageAgents(page){
  var regions=Array.from(new Set(S.dash.clients.map(function(c){return (c.region||'').trim()}).filter(Boolean))).sort();
  if(GPS.agent&&!S.dash.agents.some(function(a){return a.id===GPS.agent}))GPS.agent=null;
  page.innerHTML='<div class="gps">'+
   '<div class="card gps-list"><div class="gps-tools"><input type="search" id="gpsQ" placeholder="Agent qidirish…" value="'+esc(GPS.q)+'">'+
     '<div class="seg" id="gpsSt">'+[['','Hammasi'],['active','Faol'],['late','Kechikkan'],['offline','Yopiq']].map(function(x){return '<button data-s="'+x[0]+'" class="'+(GPS.status===x[0]?'on':'')+'">'+x[1]+'</button>'}).join('')+'</div>'+
     '<select id="gpsRegion" aria-label="Hudud"><option value="">Barcha hududlar</option>'+regions.map(function(r){return '<option'+(GPS.region===r?' selected':'')+'>'+esc(r)+'</option>'}).join('')+'</select></div>'+
     '<div class="list" id="gpsList"></div></div>'+
   '<div class="gps-map"><div class="map" id="agMap"></div>'+
     '<div class="map-legend"><label><input type="checkbox" id="gpsCl"'+(GPS.clients?' checked':'')+'> Mijozlar</label>'+
     [[C.forest,'0–2 kun'],[C.yellow,'3–4 kun'],[C.orange,'5+ kun'],[C.pri,'Rejada'],[C.gray,'Noma’lum']].map(function(x){return '<span><i style="background:'+x[0]+'"></i>'+x[1]+'</span>'}).join('')+'</div></div>'+
   '<div class="card gps-detail" id="gpsDetail"></div></div>';
  $('gpsQ').oninput=debounce(function(){GPS.q=this.value;gpsSave();gpsListRender()},150);
  $('gpsSt').onclick=function(e){var b=e.target.closest('button');if(!b)return;GPS.status=b.dataset.s;gpsSave();$('gpsSt').querySelectorAll('button').forEach(function(x){x.classList.toggle('on',x===b)});gpsListRender();gpsMarkers(true)};
  $('gpsRegion').onchange=function(){GPS.region=this.value;gpsSave();gpsListRender();gpsMarkers(true);gpsClientLayer(true);if(!GPS.agent)gpsDetail();gpsFitClients()};
  $('gpsCl').onchange=function(){GPS.clients=this.checked;gpsSave();gpsClientLayer(true)};
  var m=makeMap($('agMap'),'agents');S.agMarkers={};S.gpsLayers={};
  if(m){S.gpsLayers.route=L.layerGroup().addTo(m);gpsClientLayer(false);gpsMarkers(true);setTimeout(function(){m.invalidateSize()},60)}
  gpsListRender();gpsDetail();
}
function agentPopup(a){return '<b>'+esc(a.name)+'</b><br>'+(a.locationSource==='live'?'Jonli GPS':'Oxirgi ma’lum joy')+' · '+ago(a.lastGpsTs)}
function gpsListRender(){
  var rows=gpsAgents(),rep={};(S.dash.reports.today.agents||[]).forEach(function(r){rep[r.agentId]=r});
  $('gpsList').innerHTML=(GPS.agent?'<div class="li click" data-all="1"><div class="tone t-blue" style="width:32px;height:32px">'+ic('users')+'</div><div class="t"><b>Barcha agentlar</b><small>Tanlovni bekor qilish</small></div></div>':'')+
   (rows.length?rows.map(function(a){var st=AG_ST[a.status]||AG_ST.offline,r=rep[a.id]||{},stale=a.shiftOpen&&a.lastGpsTs&&Date.now()/1000-a.lastGpsTs>STALE;
    return '<div class="li click gps-ag'+(GPS.agent===a.id?' on':'')+'" data-gid="'+a.id+'"><span class="ring" style="--ring:'+st[2]+'">'+avatar(a.name,a.photoUrl)+'</span><div class="t"><b>'+esc(a.name)+'</b>'+
      '<small>'+(a.lastGpsTs?(stale?'<span class="warn">'+ic('alert','sm')+' GPS '+ago(a.lastGpsTs)+'</span>':ic('pin','sm')+' '+ago(a.lastGpsTs)):'GPS yo‘q')+'</small>'+
      '<small>'+a.done+' tashrif · '+usd(r.deliveredUsd||0)+' · '+usd(r.paymentsUsd||0)+'</small></div>'+pill('<span class="dot"></span>'+st[0],st[1])+'</div>'}).join(''):emptyState('Agent topilmadi','users'));
  $('gpsList').querySelectorAll('[data-gid]').forEach(function(el){el.onclick=function(){gpsSelect(+el.dataset.gid)}});
  var all=$('gpsList').querySelector('[data-all]');if(all)all.onclick=function(){gpsSelect(null)};
}
function gpsFitClients(){var m=S.maps.agents,l=S.gpsLayers&&S.gpsLayers.clients;if(!m||!l||!l.getBounds)return;var b=l.getBounds();if(b.isValid())m.fitBounds(b,{padding:[40,40],maxZoom:14})}
function gpsSelect(id){
  GPS.agent=id;GPS.day='';gpsSave();gpsListRender();gpsMarkers(false);gpsClientLayer(true);gpsDetail();
  var mk=id&&S.agMarkers[id],m=S.maps.agents;if(mk&&m)m.flyTo(mk.getLatLng(),14,{duration:.5});
}
function gpsMarkers(fit){
  var m=S.maps.agents;if(!m)return;var keep=gpsAgents().map(function(a){return a.id}),pts=[];
  S.dash.agents.forEach(function(a){var mk=S.agMarkers[a.id];
    if(a.lat==null||keep.indexOf(a.id)<0){if(mk){m.removeLayer(mk);delete S.agMarkers[a.id]}return}
    var icon=agentIcon(a,GPS.agent===a.id);
    if(mk){mk.setLatLng([a.lat,a.lon]);mk.setIcon(icon);mk.setPopupContent(agentPopup(a))}
    else S.agMarkers[a.id]=L.marker([a.lat,a.lon],{icon:icon,zIndexOffset:1000}).addTo(m).bindPopup(agentPopup(a)).on('click',function(){gpsSelect(a.id)});
    pts.push([a.lat,a.lon])});
  if(fit&&!GPS.agent&&pts.length)m.fitBounds(pts,{padding:[50,50],maxZoom:13});
}
function gpsClientLayer(rebuild){
  var m=S.maps.agents;if(!m)return;
  if(S.gpsLayers.clients){m.removeLayer(S.gpsLayers.clients);S.gpsLayers.clients=null}
  if(!GPS.clients)return;
  var grp=window.L&&L.markerClusterGroup?L.markerClusterGroup({showCoverageOnHover:false,maxClusterRadius:46,spiderfyOnMaxZoom:true,
    iconCreateFunction:function(cl){var ms=cl.getAllChildMarkers(),n=ms.length,c={fresh:0,yellow:0,red:0};ms.forEach(function(x){c[x.options.age]=(c[x.options.age]||0)+1});
      var col=c.red?C.orange:c.yellow?C.yellow:C.forest,sz=n<10?34:n<50?40:48;
      return L.divIcon({className:'',html:'<div class="ccl" style="--c:'+col+';width:'+sz+'px;height:'+sz+'px"><b>'+n+'</b>'+(c.red?'<i>'+c.red+'</i>':'')+'</div>',iconSize:[sz,sz]})}}):L.layerGroup();
  S.dash.clients.forEach(function(c){
    if(c.lat==null)return;if(GPS.agent&&c.agentId!==GPS.agent)return;if(GPS.region&&(c.region||'').trim()!==GPS.region)return;
    var col=c.blacklisted?C.ink:(AGE[c.age]||AGE.unknown)[2];
    grp.addLayer(L.marker([c.lat,c.lon],{age:c.age,icon:L.divIcon({className:'',html:'<div class="cdot" style="background:'+col+'"></div>',iconSize:[14,14],iconAnchor:[7,7]})})
      .bindTooltip(esc(c.name)+' · '+(AGE[c.age]||AGE.unknown)[0]+(c.debtUsd>0?' · qarz '+usd(c.debtUsd):'')).on('click',function(){openClient(c.id)}));
  });
  S.gpsLayers.clients=grp.addTo(m);
}
async function gpsDetail(){
  var el=$('gpsDetail');if(!el)return;var d=S.dash;
  if(!GPS.agent){
    var by={active:0,late:0,offline:0};d.agents.forEach(function(a){by[a.status]=(by[a.status]||0)+1});
    var stale=d.agents.filter(function(a){return a.shiftOpen&&a.lastGpsTs&&Date.now()/1000-a.lastGpsTs>STALE});
    var cl=d.clients.filter(function(c){return !GPS.region||(c.region||'').trim()===GPS.region}),cnt={fresh:0,yellow:0,red:0,scheduled:0,unknown:0};cl.forEach(function(c){cnt[c.age]=(cnt[c.age]||0)+1});
    el.innerHTML='<div class="card-h"><h3>'+ic('compass')+' Umumiy holat</h3>'+(GPS.region?pill(esc(GPS.region),'p-pri'):'')+'</div>'+
     '<div class="grid g3" style="gap:8px;margin-bottom:14px"><div class="mini"><small>Faol</small><b class="ok">'+by.active+'</b></div><div class="mini"><small>Kechikkan</small><b class="warn">'+by.late+'</b></div><div class="mini"><small>Yopiq</small><b>'+by.offline+'</b></div></div>'+
     (stale.length?'<div class="banner">'+ic('alert','sm')+' '+stale.length+' agentdan GPS kechikmoqda: '+stale.map(function(a){return esc(a.name)+' ('+ago(a.lastGpsTs)+')'}).join(', ')+'</div>':'')+
     '<div class="card-h" style="margin-top:6px"><h3>'+ic('store')+' Mijozlar ('+num(cl.length)+')</h3></div>'+donut([['0–2 kun',cnt.fresh,C.forest],['3–4 kun',cnt.yellow,C.yellow],['5+ kun',cnt.red,C.orange],['Rejada',cnt.scheduled,C.pri],['Noma’lum',cnt.unknown,C.gray]],num(cl.length),'mijoz')+
     '<p class="hint" style="margin-top:12px">Agentni tanlang: uning bugungi marshruti, tashriflari, savdosi va smena vaqtlari shu yerda chiqadi. GPS Telegram jonli lokatsiyasidan keladi va panel har 30 soniyada yangilanadi.</p>';
    if(S.gpsLayers&&S.gpsLayers.route)S.gpsLayers.route.clearLayers();return;
  }
  var a=d.agents.find(function(x){return x.id===GPS.agent});if(!a){GPS.agent=null;return gpsDetail()}
  var st=AG_ST[a.status]||AG_ST.offline,r=(d.reports.today.agents||[]).find(function(x){return x.agentId===a.id})||{};
  var day=GPS.day||today(),isToday=day===today(),stale=a.shiftOpen&&a.lastGpsTs&&Date.now()/1000-a.lastGpsTs>STALE;
  el.innerHTML='<div class="dh" style="margin:0 0 12px">'+avatar(a.name,a.photoUrl,'lg')+'<div style="min-width:0"><h2 style="font-size:18px">'+esc(a.name)+'</h2><div>'+pill('<span class="dot"></span>'+st[0],st[1])+'</div></div></div>'+
   (stale?'<div class="banner">'+ic('alert','sm')+' GPS kechikmoqda: oxirgi nuqta '+ago(a.lastGpsTs)+' ('+hm(a.lastGpsTs)+'). Xaritada oxirgi ma’lum joy ko‘rsatilgan.</div>':'')+
   '<dl class="kv" style="grid-template-columns:120px 1fr;margin-bottom:12px"><dt>Oxirgi GPS</dt><dd>'+(a.lastGpsTs?dt(a.lastGpsTs)+' <span class="muted">('+ago(a.lastGpsTs)+')</span>':'—')+'</dd>'+
   '<dt>Joylashuv</dt><dd>'+(a.lat!=null?(a.locationSource==='live'?'Jonli':'Oxirgi ma’lum')+' · <a href="https://www.google.com/maps/search/?api=1&query='+a.lat+','+a.lon+'" target="_blank" rel="noopener">xaritada ↗</a>':'—')+'</dd>'+
   '<dt>Smena</dt><dd id="gpsShift">…</dd></dl>'+
   '<div class="toolbar" style="margin-bottom:10px"><div class="seg" id="gpsDay"><button data-d="today" class="'+(isToday?'on':'')+'">Bugun</button><button data-d="pick" class="'+(isToday?'':'on')+'">Kun</button></div><input type="date" id="gpsDate" value="'+day+'" max="'+today()+'" style="width:auto"'+(isToday?' hidden':'')+'></div>'+
   (isToday?'<div class="grid g3" style="gap:8px;margin-bottom:12px"><div class="mini"><small>Realizatsiya</small><b>'+usd(r.deliveredUsd||0)+'</b></div><div class="mini"><small>Yig‘ilgan pul</small><b>'+usd(r.paymentsUsd||0)+'</b></div><div class="mini"><small>Tashrif</small><b>'+a.done+'</b></div>'+
     '<div class="mini"><small>Yangi mijoz</small><b>'+(r.newClients||0)+'</b></div><div class="mini"><small>Ish vaqti</small><b>'+num((r.workSeconds||0)/3600,1)+' soat</b></div><div class="mini"><small>Masofa</small><b>'+num(r.distanceKm||0,1)+' km</b></div></div>':'')+
   '<div id="gpsInfo" class="muted small"></div><div id="gpsVisits"></div>'+
   '<div class="actions" style="margin-top:12px"><button class="btn sm" id="gpsCard">'+ic('file','sm')+' To‘liq karta</button></div>';
  $('gpsCard').onclick=function(){openAgent(a.id)};
  $('gpsDay').onclick=function(e){var b=e.target.closest('button');if(!b)return;if(b.dataset.d==='today'){GPS.day='';gpsSave();gpsDetail()}else{$('gpsDate').hidden=false;$('gpsDay').querySelectorAll('button').forEach(function(x){x.classList.toggle('on',x===b)})}};
  $('gpsDate').onchange=function(){GPS.day=this.value===today()?'':this.value;gpsSave();gpsDetail()};
  var dd=await api('agent_period_detail',{agentId:a.id,period:'custom',from:day,to:day}).catch(function(e){$('gpsInfo').textContent=e.message;return null});
  if(!dd||GPS.agent!==a.id||!$('gpsShift'))return;
  $('gpsShift').innerHTML=dd.shifts.length?dd.shifts.map(function(sh){return hm(sh.start)+' – '+(sh.end?hm(sh.end):'<span class="ok">davom etmoqda</span>')}).join('<br>'):'<span class="muted">Bu kunda smena yo‘q</span>';
  var lay=S.gpsLayers&&S.gpsLayers.route,m=S.maps.agents;if(lay)lay.clearLayers();var bounds=[],km=0;
  dd.route.segments.forEach(function(sg,i){var pts=sg.map(function(p){return [p.lat,p.lon]});bounds=bounds.concat(pts);for(var j=1;j<sg.length;j++)km+=hav(sg[j-1],sg[j]);
    if(lay){if(pts.length>1)L.polyline(pts,{color:C.pri,weight:4,opacity:.85}).addTo(lay).bindTooltip(hm(sg[0].ts)+' – '+hm(sg[sg.length-1].ts));
      L.circleMarker(pts[0],{radius:5,color:'#fff',fillColor:C.forest,fillOpacity:1,weight:2}).addTo(lay).bindTooltip('Boshlanish '+hm(sg[0].ts));
      L.circleMarker(pts[pts.length-1],{radius:5,color:'#fff',fillColor:C.orange,fillOpacity:1,weight:2}).addTo(lay).bindTooltip('Oxirgi nuqta '+hm(sg[sg.length-1].ts))}});
  dd.visits.forEach(function(v){if(v.lat==null||!lay)return;bounds.push([v.lat,v.lon]);L.marker([v.lat,v.lon],{zIndexOffset:900,icon:L.divIcon({className:'',html:'<div class="vpin">'+ic('check','sm')+'</div>',iconSize:[22,22],iconAnchor:[11,11]})}).addTo(lay).bindTooltip('Tashrif: '+esc(v.name)+' · '+hm(v.ts)).on('click',function(){openClient(v.clientId)})});
  if(m&&bounds.length)m.fitBounds(bounds.concat(a.lat!=null&&isToday?[[a.lat,a.lon]]:[]),{padding:[40,40],maxZoom:15});
  $('gpsInfo').innerHTML=num(dd.route.gpsTotal)+' GPS nuqta · ~'+num(km,1)+' km · '+dd.visitsTotal+' tashrif · '+dd.newClientsTotal+' yangi mijoz';
  var ev=dd.visits.map(function(v){return {ts:v.ts,id:v.clientId,t:VISIT[v.status]||v.status||'Tashrif',n:v.name,ic:'walk'}}).concat(dd.newClients.map(function(c){return {ts:c.ts,id:c.id,t:'Yangi mijoz',n:c.name,ic:'userplus'}})).sort(function(x,y){return y.ts-x.ts});
  $('gpsVisits').innerHTML='<div class="card-h" style="margin:14px 0 4px"><h3>'+ic('walk')+' Tashrif buyurilgan mijozlar</h3></div>'+(ev.length?'<div class="list">'+ev.map(function(e){return '<div class="li click" data-client="'+e.id+'"><div class="t"><b>'+esc(e.n)+'</b><small>'+ic(e.ic,'sm')+' '+esc(e.t)+' · '+hm(e.ts)+'</small></div></div>'}).join('')+'</div>':emptyState('Bu kunda tashrif yo‘q','walk'));
  bindClientLinks($('gpsVisits'));
}
function updateAgentsLive(){
  if(!S.maps.agents||!$('gpsList'))return;
  gpsMarkers(false);gpsListRender();
  if(!GPS.agent)gpsDetail();
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
   '<div class="card" style="margin-bottom:14px"><div class="card-h"><h3>Marshrut</h3><div class="actions"><div class="seg" id="rtSeg">'+[['last','Oxirgi smena'],['today','Bugun'],['week','7 kun'],['day','Kun']].map(function(x){return '<button data-r="'+x[0]+'" class="'+(x[0]==='last'?'on':'')+'">'+x[1]+'</button>'}).join('')+'</div><input type="date" id="rtDay" value="'+today()+'" max="'+today()+'" style="width:auto" hidden></div></div>'+
     '<div id="drMap" style="height:320px;border-radius:12px;overflow:hidden"></div><div id="drInfo" class="muted small" style="padding-top:8px"></div><div id="drVisits"></div></div>'+
   '<div class="card flush" style="margin-bottom:14px"><table><thead><tr><th>Ko‘rsatkich</th>'+cols.map(function(c){return '<th class="right">'+c[1]+'</th>'}).join('')+'</tr></thead><tbody>'+
     stat('Realizatsiya',function(p){return usd(p.deliveredUsd)})+stat('To‘lovlar',function(p){return usd(p.paymentsUsd)})+stat('Qaytarilgan',function(p){return usd(p.returnsUsd)})+
     stat('Tashriflar',function(p){return p.visits})+stat('Yangi mijozlar',function(p){return p.newClients})+stat('Ish vaqti',function(p){return hours(p.workSeconds)})+stat('Masofa',function(p){return num(p.distanceKm,1)+' km'})+
   '</tbody></table></div>'+
   '<div class="grid g2" style="margin-bottom:14px">'+
     '<div class="card"><div class="card-h"><h3>Qo‘lidagi tovar</h3></div>'+(stocks.length?'<div class="list">'+stocks.map(function(s){return '<div class="li"><div class="t"><b>'+esc(s.name)+'</b></div><b class="num">'+s.qty+'</b></div>'}).join('')+'</div>':'<div class="muted">Tovar yo‘q</div>')+'</div>'+
     '<div class="card"><div class="card-h"><h3>Huquqlar</h3></div>'+a.features.map(function(f){return '<div class="switch"><span>'+esc(f.label)+'</span><button class="tog'+(f.enabled?' on':'')+'" data-feat="'+esc(f.key)+'" data-on="'+(f.enabled?1:0)+'" aria-label="'+esc(f.label)+'"'+(a.active?'':' disabled')+'></button></div>'}).join('')+'</div>'+
   '</div>'+
   '<div class="actions">'+(a.active?'<button class="btn" id="agRename">'+ic('edit')+' Nomini o‘zgartirish</button>':'')+
     (S.primary&&a.active?'<button class="btn" id="agTransfer">'+ic('swap')+' Akkauntni almashtirish</button><button class="btn danger" id="agBlock">'+ic('ban')+' Bloklash</button>':'')+'</div>'+
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
var RT_ST={visit:[C.pri,'Tashrif'],newc:[C.forest,'Yangi mijoz']};
async function agentRouteMap(a){
  var seg=$('rtSeg'),day=$('rtDay');
  seg.onclick=function(e){var b=e.target.closest('button');if(!b)return;seg.querySelectorAll('button').forEach(function(x){x.classList.toggle('on',x===b)});day.hidden=b.dataset.r!=='day';drawRoute(a,b.dataset.r)};
  day.onchange=function(){drawRoute(a,'day')};
  drawRoute(a,'last');
}
function drawerMap(a){
  var el=$('drMap');if(!el||!window.L)return null;
  if(S.maps.drawer){try{S.maps.drawer.remove()}catch(e){}}
  var m=L.map(el).setView(a.lat!=null?[a.lat,a.lon]:[40.45,71.6],a.lat!=null?14:9);
  L.tileLayer('/tiles/{z}/{x}/{y}.png',{maxZoom:19,attribution:'© OpenStreetMap'}).addTo(m);S.maps.drawer=m;
  [120,320,600].forEach(function(t){setTimeout(function(){if(S.maps.drawer===m)m.invalidateSize()},t)});
  return m;
}
async function drawRoute(a,mode){
  var m=drawerMap(a);if(!m)return;var info=$('drInfo'),list=$('drVisits');info.textContent='Yuklanmoqda…';list.innerHTML='';
  var bounds=[];
  if(a.lat!=null&&(mode==='last'||mode==='today'))L.marker([a.lat,a.lon],{icon:agentIcon(Object.assign({status:a.shiftOpen?'active':'offline'},a))}).addTo(m).bindTooltip('Oxirgi joy · '+ago(a.lastGpsTs));
  if(mode==='last'){
    if(!a.active){info.textContent='Agent bloklangan: oxirgi smena ko‘rsatilmaydi.';return}
    var r=await api('route',{agentId:a.id}).catch(function(e){info.textContent=e.message;return null});
    if(!r||S.maps.drawer!==m)return;
    var pts=r.points.map(function(p){return [p.lat,p.lon]});
    if(pts.length>1){L.polyline(pts,{color:C.pri,weight:4,opacity:.85}).addTo(m);L.circleMarker(pts[0],{radius:6,color:'#fff',fillColor:C.forest,fillOpacity:1,weight:2}).addTo(m).bindTooltip('Boshlanish '+hm(r.points[0].ts));m.fitBounds(pts,{padding:[24,24]})}
    info.textContent=r.start?('Oxirgi smena: '+dt(r.start)+(r.end?' – '+hm(r.end):' (ochiq)')+' · '+pts.length+' GPS nuqta'):'Smena tarixi yo‘q';
    return;
  }
  var args={agentId:a.id,period:mode==='day'?'custom':mode};
  if(mode==='day'){args.from=args.to=$('rtDay').value||today()}
  var d=await api('agent_period_detail',args).catch(function(e){info.textContent=e.message;return null});
  if(!d||S.maps.drawer!==m)return;
  var colors=[C.pri,C.violet,C.cyan,C.orange,C.forest,C.orange];
  d.route.segments.forEach(function(sg,i){var pts=sg.map(function(p){return [p.lat,p.lon]});bounds=bounds.concat(pts);
    if(pts.length>1)L.polyline(pts,{color:colors[i%colors.length],weight:4,opacity:.85}).addTo(m).bindTooltip(hm(sg[0].ts)+' – '+hm(sg[sg.length-1].ts));
    L.circleMarker(pts[0],{radius:5,color:'#fff',fillColor:C.forest,fillOpacity:1,weight:2}).addTo(m).bindTooltip('Boshlanish '+dt(sg[0].ts))});
  var dot=function(x,kind){if(x.lat==null)return;bounds.push([x.lat,x.lon]);
    L.circleMarker([x.lat,x.lon],{radius:7,color:'#fff',weight:2,fillColor:RT_ST[kind][0],fillOpacity:.95}).addTo(m).bindTooltip(RT_ST[kind][1]+': '+esc(x.name)+' · '+hm(x.ts)).on('click',function(){openClient(x.clientId||x.id)})};
  d.visits.forEach(function(v){dot(v,'visit')});d.newClients.forEach(function(c){dot(c,'newc')});
  if(bounds.length)m.fitBounds(bounds,{padding:[24,24],maxZoom:16});
  var km=0;d.route.segments.forEach(function(sg){for(var i=1;i<sg.length;i++)km+=hav(sg[i-1],sg[i])});
  var lbl=String(d.label||'').split(' – ');info.innerHTML=esc(lbl.length===2&&lbl[0]===lbl[1]?lbl[0]:d.label)+' · '+num(d.route.gpsTotal)+' GPS nuqta'+(d.route.sampled?' ('+d.route.gpsShown+' tasi chizildi)':'')+' · ~'+num(km,1)+' km · '+d.visitsTotal+' tashrif · '+d.newClientsTotal+' yangi mijoz'+
    ' &nbsp; '+legend([['Tashrif',C.pri],['Yangi mijoz',C.forest]]).replace('class="legend"','class="legend" style="display:inline-flex"');
  var ev=d.visits.map(function(v){return {ts:v.ts,id:v.clientId,t:ic('walk','sm')+' '+(VISIT[v.status]||v.status||'Tashrif'),n:v.name,note:v.note}}).concat(d.newClients.map(function(c){return {ts:c.ts,id:c.id,t:ic('userplus','sm')+' Yangi mijoz',n:c.name,note:c.address}})).sort(function(x,y){return y.ts-x.ts});
  list.innerHTML=ev.length?'<div class="list" style="margin-top:10px;max-height:320px;overflow:auto">'+ev.map(function(e){return '<div class="li click" data-client="'+e.id+'"><div class="t"><b>'+esc(e.n)+'</b><small>'+e.t+' · '+dt(e.ts)+(e.note?' · '+esc(e.note):'')+'</small></div></div>'}).join('')+'</div>':'<div class="muted small" style="padding-top:8px">Bu davrda tashrif yoki yangi mijoz yo‘q.</div>';
  bindClientLinks(list);
}
function hav(p,q){var R=6371,r=Math.PI/180,dl=(q.lat-p.lat)*r,dn=(q.lon-p.lon)*r,x=Math.sin(dl/2)*Math.sin(dl/2)+Math.cos(p.lat*r)*Math.cos(q.lat*r)*Math.sin(dn/2)*Math.sin(dn/2);return 2*R*Math.asin(Math.sqrt(x))}

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
   '<span class="grow"></span><div class="seg" id="clView"><button data-v="table" class="'+(CL.view==='table'?'on':'')+'">'+ic('list')+' Jadval</button><button data-v="map" class="'+(CL.view==='map'?'on':'')+'">'+ic('map')+' Xarita</button></div>'+
   '</div>'+
   '<div class="toolbar"><div class="seg" id="clAge"></div><span class="grow"></span><span class="muted small" id="clCount"></span><button class="btn sm" id="clView2" title="Ekrandagi (filtrlangan) qatorlar">'+ic('download','sm')+' Excel</button><button class="btn sm" id="clXlsx" title="Barcha mijozlar, to‘liq hisobot">'+ic('file','sm')+' Hammasi</button><button class="btn sm" id="clPdf" title="Barcha mijozlar, PDF">'+ic('file','sm')+' PDF</button></div>'+
   '<div id="clBody"></div>';
  var upd=function(){CL.page=0;clientsBody()};
  $('clQ').oninput=debounce(function(){CL.q=this.value;upd()},150);
  $('clAgent').onchange=function(){CL.agent=this.value;upd()};
  $('clDebt').onchange=function(){CL.debt=this.value;upd()};
  if($('clRegion'))$('clRegion').onchange=function(){CL.region=this.value;upd()};
  $('clView').onclick=function(e){var b=e.target.closest('button');if(!b)return;CL.view=b.dataset.v;$('clView').querySelectorAll('button').forEach(function(x){x.classList.toggle('on',x===b)});clientsBody()};
  $('clAge').onclick=function(e){var b=e.target.closest('button');if(!b)return;CL.age=b.dataset.a;upd()};
  $('clXlsx').onclick=function(){exportAll('xlsx',this)};
  $('clView2').onclick=function(){var rows=sortedClients(filteredClients(false));exportRows('ASMAN-mijozlar',['ID','Mijoz','Shaxs','Telefon','Manzil','Hudud','Agent','Qarz USD','Oxirgi aloqa','Kun','Reja','Holat','Qora ro‘yxat'],rows.map(function(c){return [c.id,c.name,c.person,c.phone,c.address,c.region,c.agent,c.debtUsd,c.lastTs?dday(c.lastTs):'',c.days==null?'':c.days,c.followup||'',(AGE[c.age]||AGE.unknown)[0],c.blacklisted?'Ha':'']}))};$('clPdf').onclick=function(){exportAll('pdf',this)};
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
  sortedClients(rows);
  var pages=Math.max(1,Math.ceil(rows.length/PAGE_SIZE));if(CL.page>=pages)CL.page=pages-1;
  var slice=rows.slice(CL.page*PAGE_SIZE,(CL.page+1)*PAGE_SIZE);
  var th=function(k,label,cls){return '<th class="sort '+(cls||'')+(CL.sort===k?(CL.dir>0?' asc':' desc'):'')+'" data-k="'+k+'">'+label+'</th>'};
  body.innerHTML='<div class="card flush"><div class="tbl-wrap"><table><thead><tr>'+th('name','Mijoz')+th('agent','Agent')+th('region','Hudud')+'<th>Telefon</th>'+th('debtUsd','Qarz','right')+th('lastTs','Oxirgi aloqa')+th('age','Holat')+'</tr></thead><tbody>'+
   (slice.length?slice.map(function(c){var ag=AGE[c.age]||AGE.unknown;return '<tr class="click" data-client="'+c.id+'"><td><div class="cell">'+(c.thumbUrl?'<span class="av sq" style="background-image:url(\''+esc(c.thumbUrl)+'\')"></span>':avatar(c.name,'','sq'))+'<div class="t"><b>'+esc(c.name)+(c.blacklisted?' '+ic('ban','sm bad'):'')+'</b><small>'+esc(c.person||c.address||'')+'</small></div></div></td><td>'+esc(c.agent)+'</td><td>'+esc(c.region||'—')+'</td><td class="num">'+(c.phone?'<a href="tel:'+esc(c.phone.split(/[,\/\n]/)[0].trim())+'">'+esc(c.phone)+'</a>':'—')+'</td><td class="right num '+(c.debtUsd>0?'bad':'')+'">'+(c.debtUsd?usd(c.debtUsd):'—')+'</td><td><span class="num">'+(c.lastTs?dday(c.lastTs):'—')+'</span><br><small class="muted">'+(c.days!=null?c.days+' kun':'')+(c.followup?' · reja '+esc(c.followup):'')+'</small></td><td>'+pill(ag[0],ag[1])+'</td></tr>'}).join(''):'<tr><td colspan="7" class="empty">Mijoz topilmadi</td></tr>')+
   '</tbody></table></div>'+(pages>1?'<div class="pager"><span>'+(CL.page*PAGE_SIZE+1)+'–'+Math.min(rows.length,(CL.page+1)*PAGE_SIZE)+' / '+num(rows.length)+'</span><span class="actions"><button class="btn sm" id="pgPrev"'+(CL.page?'':' disabled')+'>‹ Oldingi</button><button class="btn sm" id="pgNext"'+(CL.page<pages-1?'':' disabled')+'>Keyingi ›</button></span></div>':'')+'</div>';
  body.querySelectorAll('th.sort').forEach(function(h){h.onclick=function(){var k=h.dataset.k;if(CL.sort===k)CL.dir=-CL.dir;else{CL.sort=k;CL.dir=(k==='name'||k==='agent'||k==='region')?1:-1}clientsBody()}});
  if($('pgPrev'))$('pgPrev').onclick=function(){CL.page--;clientsBody();scrollTo(0,0)};
  if($('pgNext'))$('pgNext').onclick=function(){CL.page++;clientsBody();scrollTo(0,0)};
  bindClientLinks(body);
}

function sortedClients(rows){
  var key=CL.sort,dir=CL.dir,txt=key==='name'||key==='agent'||key==='region';
  return rows.sort(function(a,b){var x=a[key],y=b[key];if(x==null)x=txt?'':-1;if(y==null)y=txt?'':-1;return (typeof x==='string'?x.localeCompare(y):x-y)*dir});
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
    visits:function(){return c.visits.length?'<div class="list" style="padding:0 18px">'+c.visits.map(function(v){return '<div class="li">'+(v.thumbUrl?'<a href="'+esc(v.photoUrl)+'" target="_blank" rel="noopener"><span class="av sq" style="background-image:url(\''+esc(v.thumbUrl)+'\');width:48px;height:48px"></span></a>':'<span class="av sq">'+ic('walk')+'</span>')+'<div class="t"><b>'+esc(VISIT[v.status]||v.status||'Tashrif')+'</b><small>'+esc(v.note)+'</small><small>'+esc(v.actor)+' · '+dt(v.ts)+(v.followup?' · qayta: '+esc(v.followup):'')+'</small></div></div>'}).join('')+'</div>':'<div class="empty">Tashrif yo‘q</div>'},
    stock:function(){var s=c.stocks.filter(function(x){return x.qty});return s.length?'<table><thead><tr><th>Tovar</th><th class="right">Do‘konda</th></tr></thead><tbody>'+s.map(function(x){return '<tr><td>'+esc(x.name)+'</td><td class="right num">'+x.qty+'</td></tr>'}).join('')+'</tbody></table>':'<div class="empty">Do‘konda tovar qoldig‘i yo‘q</div>'},
    edits:function(){var rows=c.edits.map(function(e){return '<div class="li"><div class="t"><b>'+esc(FIELD[e.field]||e.field)+'</b><div class="diff"><s>'+esc(e.old||'—')+'</s> → <ins>'+esc(e.new||'—')+'</ins></div><small>'+esc(e.actor)+' · '+dt(e.ts)+'</small></div></div>'}).concat((c.blacklistLog||[]).map(function(l){return '<div class="li"><div class="t"><b>'+(l.action==='on'||l.action==='add'?ic('ban','sm')+' Qora ro‘yxatga':ic('checkc','sm')+' Qora ro‘yxatdan chiqdi')+'</b><small>'+esc(l.reason)+'</small><small>'+esc(l.actor)+' · '+dt(l.ts)+'</small></div></div>'}));return rows.length?'<div class="list" style="padding:0 18px">'+rows.join('')+'</div>':'<div class="empty">O‘zgarish yo‘q</div>'}
  };
  openDrawer(
   '<div class="dh">'+(c.thumbUrl?'<span class="av lg" style="background-image:url(\''+esc(c.thumbUrl)+'\')"></span>':avatar(c.name,'','lg'))+'<div><h2>'+esc(c.name)+(c.blacklisted?' '+pill(ic('ban','sm')+' Qora ro‘yxat','p-bad'):'')+'</h2><div class="muted">#'+c.id+' · agent: '+esc(c.agent)+(c.region?' · '+esc(c.region):'')+'</div></div></div>'+
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
   '<div class="actions"><button class="btn" id="cEdit">'+ic('edit')+' Tahrirlash</button><button class="btn" id="cXlsx">'+ic('download')+' Akt sverka Excel</button><button class="btn" id="cPdf">'+ic('download')+' Akt sverka PDF</button>'+
     '<button class="btn" id="cBlack">'+(c.blacklisted?ic('checkc')+' Qora ro‘yxatdan chiqarish':ic('ban')+' Qora ro‘yxatga')+'</button><button class="btn danger" id="cDel">'+ic('trash')+' O‘chirish</button></div>'+
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
   '<div class="toolbar"><div class="seg" id="ksF">'+[['','Barchasi'],['in','Kirim'],['out','Chiqim'],['pending','Tasdiqlanmagan']].map(function(x){return '<button data-f="'+x[0]+'" class="'+(KS.f===x[0]?'on':'')+'">'+x[1]+'</button>'}).join('')+'</div>'+
   '<div class="seg" id="ksP">'+[['today','Bugun'],['week','7 kun'],['month','30 kun']].map(function(x){return '<button data-p="'+x[0]+'" class="'+(KS.p===x[0]?'on':'')+'">'+x[1]+'</button>'}).join('')+'</div>'+
   '<input type="search" id="ksQ" placeholder="Qidirish…" value="'+esc(KS.q)+'"><span class="grow"></span><span class="muted small" id="ksSum"></span><button class="btn" id="ksExp">'+ic('download')+' Excel</button></div>'+
   '<div class="grid g-main"><div class="card flush" id="ksList"></div><div class="card"><div class="card-h"><h3>Xarajatlar tarkibi</h3></div><div id="ksBrk"></div></div></div>';
  $('ksF').onclick=function(e){var b=e.target.closest('button');if(!b)return;KS.f=b.dataset.f;pageCash(page)};
  $('ksP').onclick=function(e){var b=e.target.closest('button');if(!b)return;KS.p=b.dataset.p;pageCash(page)};
  $('ksQ').oninput=debounce(function(){KS.q=this.value;cashList()},150);
  $('ksExp').onclick=function(){var ST={pending:'Kutilmoqda',accepted:'Qabul qilindi',rejected:'Rad etildi',expense:'Chiqim'};
    exportRows('ASMAN-kassa',['Sana','Turi','Agent / oluvchi','Kategoriya','Izoh','Kassir','USD','So‘m','Kurs','Holat'],S.cashRows.map(function(t){var h=t.type==='handover';return [dt(t.acceptedTs||t.ts),h?'Kirim':'Chiqim',h?t.agent:t.recipient,h?'':t.category,t.note||'',t.cashier||'',(h?1:-1)*t.amountUsd,t.amountUzs||'',t.rateUzsPerUsd||'',ST[t.state]||t.state]}))};
  cashList();
}
function cashList(){
  var d=S.dash,since=d.todayStart-({today:0,week:6,month:29}[KS.p])*86400,q=KS.q.trim().toLowerCase();
  var rows=d.transactions.filter(function(t){var ts=t.acceptedTs||t.ts;if(ts<since&&!(KS.f==='pending'&&t.state==='pending'))return false;
    if(KS.f==='in'&&t.type!=='handover')return false;if(KS.f==='out'&&t.type!=='expense')return false;if(KS.f==='pending'&&t.state!=='pending')return false;
    if(q&&[t.agent,t.cashier,t.category,t.recipient,t.note].join(' ').toLowerCase().indexOf(q)<0)return false;return true});
  S.cashRows=rows;var tin=0,tout=0;rows.forEach(function(t){if(t.type==='handover'&&t.state==='accepted')tin+=t.amountUsd;if(t.type==='expense')tout+=t.amountUsd});
  $('ksSum').innerHTML=rows.length+' ta · <span class="ok">+'+usd(tin)+'</span> · <span class="bad">−'+usd(tout)+'</span>';
  var ST={pending:['Kutilmoqda','p-warn'],accepted:['Qabul qilindi','p-ok'],rejected:['Rad etildi','p-bad'],expense:['Chiqim','p-bad']};
  $('ksList').innerHTML='<div class="tbl-wrap"><table><thead><tr><th>Sana</th><th>Turi</th><th>Tafsilot</th><th>Kassir</th><th class="right">Summa</th><th>Holat</th></tr></thead><tbody>'+
   (rows.length?rows.slice(0,400).map(function(t){var st=ST[t.state]||[esc(t.state),''],h=t.type==='handover';
     return '<tr><td class="num">'+dt(t.acceptedTs||t.ts)+'</td><td>'+(h?ic('in','sm')+' Agentdan':ic('out','sm')+' '+esc(t.category))+'</td><td>'+(h?'<b>'+esc(t.agent)+'</b>'+(t.amountUzs?'<br><small class="muted">'+uzs(t.amountUzs)+'</small>':''):'<b>'+esc(t.recipient||'—')+'</b>'+(t.note?'<br><small class="muted">'+esc(t.note)+'</small>':'')+(t.currency==='UZS'&&t.amountUzs?'<br><small class="muted">'+uzs(t.amountUzs)+' · kurs '+num(t.rateUzsPerUsd)+'</small>':''))+'</td><td>'+esc(t.cashier||'—')+'</td><td class="right num '+(h?(t.state==='accepted'?'ok':'muted'):'bad')+'">'+(h?'+':'−')+usd(t.amountUsd)+'</td><td>'+pill(st[0],st[1])+'</td></tr>'}).join(''):'<tr><td colspan="6" class="empty">Harakat yo‘q</td></tr>')+
   '</tbody></table></div>'+(rows.length>400?'<div class="pager">Birinchi 400 ta ko‘rsatildi</div>':'');
  var cat={};rows.forEach(function(t){if(t.type==='expense')cat[t.category]=(cat[t.category]||0)+t.amountUsd});
  var list=Object.keys(cat).map(function(k){return [k,cat[k]]}).sort(function(a,b){return b[1]-a[1]}),total=list.reduce(function(s,x){return s+x[1]},0);
  var PAL=[C.pri,C.violet,C.cyan,C.yellow,C.orange,C.forest,C.orange,C.gray];
  $('ksBrk').innerHTML=list.length?donut(list.slice(0,7).concat(list.length>7?[['Boshqa',list.slice(7).reduce(function(a,x){return a+x[1]},0)]]:[]).map(function(x,i){return [x[0],Math.round(x[1]*100)/100,PAL[i],usd(x[1])]}),usd(total),'xarajat'):'<div class="empty">Bu davrda xarajat yo‘q</div>';
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
     kpi('👣','Tashriflar',num(r.visits),'')+kpi('userplus','Yangi mijozlar',num(r.newClients),'')+
     kpi('⏱','Ish vaqti',num((r.workSeconds||0)/3600,1)+' soat',hours(r.workSeconds)+' · barcha agentlar')+kpi('🧭','Masofa',num(r.distanceKm,1)+' km','GPS bo‘yicha')+
   '</div>'+
   '<div class="card" style="margin-bottom:16px"><div class="card-h"><h3>Dinamika <span class="muted small">('+esc(r.seriesUnit||'')+')</span></h3>'+legend([['Realizatsiya',C.pri],['To‘lovlar',C.forest]])+'</div>'+barChart(r.series,['deliveredUsd','paymentsUsd'],[C.pri,C.forest],usd)+'</div>'+
   '<div class="card flush" style="margin-bottom:16px"><div class="card-h"><h3>Agentlar natijasi</h3></div><div class="tbl-wrap" style="margin-top:12px">'+agentReportTable(r.agents)+'</div></div>'+
   '<div class="grid g2">'+
     '<div class="card flush"><div class="card-h"><h3>'+ic('box')+' Mahsulotlar</h3></div>'+(prod.length?'<div style="padding:16px 20px 4px">'+donut(prod.slice(0,6).map(function(p,i){return [p.name,Math.round(p.deliveredUsd*100)/100,[C.pri,C.violet,C.cyan,C.yellow,C.forest,C.orange][i],usd(p.deliveredUsd)]}),usd(r.deliveredUsd),'realizatsiya')+'</div>':'')+'<div class="tbl-wrap" style="margin-top:12px">'+(prod.length?'<table><thead><tr><th>Mahsulot</th><th class="right">Dona</th><th class="right">Summa</th><th>Ulush</th></tr></thead><tbody>'+prod.map(function(p){return '<tr><td>'+esc(p.name)+'</td><td class="right num">'+num(p.deliveredQty)+'</td><td class="right num">'+usd(p.deliveredUsd)+'</td><td><div class="share"><i style="width:'+(p.sharePct||0)+'%"></i></div><small class="muted">'+(p.sharePct||0)+'%</small></td></tr>'}).join('')+'</tbody></table>':'<div class="empty">Bu davrda sotuv yo‘q</div>')+'</div></div>'+
     '<div class="card"><div class="card-h"><h3>Kassa oqimi</h3></div><dl class="kv">'+
       '<dt>Naqd kirim</dt><dd class="num">'+uzs(cash.inCashUzs)+' · '+usd(cash.inCashUsd)+'</dd><dt>Karta kirim</dt><dd class="num">'+uzs(cash.inCardUzs)+' · '+usd(cash.inCardUsd)+'</dd>'+
       '<dt>Naqd chiqim</dt><dd class="num">'+uzs(cash.outCashUzs)+' · '+usd(cash.outCashUsd)+'</dd><dt>Karta chiqim</dt><dd class="num">'+uzs(cash.outCardUzs)+' · '+usd(cash.outCardUsd)+'</dd>'+
     '</dl></div>'+
   '</div>';
  bindAgentLinks($('rpBody'));
}

/* ----- Tahlil (insights) ----- */
var IN={period:'month',from:'',to:'',agent:'',q:'',tab:'plan',page:0};
var PRI={1:['Muhim','p-bad'],2:['O‘rta','p-warn'],3:['Past','p-pri']};
var KGRP={active:['Faol','p-ok'],low:['Faolligi past','p-warn'],passive:['Passiv','p-bad']};
function cents(c){return usd((c||0)/100)}
function grow(g){if(!g)return '';var cls=g.kind==='pct'?(g.pct>=0?'ok':'bad'):'muted';return '<span class="small '+cls+'" title="'+esc(g.text)+'">'+esc(g.kind==='pct'?g.text:g.kind==='started'?'yangi':g.kind==='zero'?'0':'—')+'</span>'}
async function pageInsights(page,force){
  var agents=(S.dash?S.dash.agents:[]).slice().sort(function(a,b){return a.name.localeCompare(b.name)});
  page.innerHTML='<div class="toolbar"><div class="seg" id="inSeg">'+[['today','Bugun'],['week','7 kun'],['month','Shu oy'],['custom','Davr']].map(function(x){return '<button data-p="'+x[0]+'" class="'+(IN.period===x[0]?'on':'')+'">'+x[1]+'</button>'}).join('')+'</div>'+
   '<span id="inCustom"'+(IN.period==='custom'?'':' hidden')+' class="actions"><input type="date" id="inFrom" value="'+esc(IN.from||today())+'" style="width:auto"><input type="date" id="inTo" value="'+esc(IN.to||today())+'" style="width:auto"><button class="btn pri" id="inGo">Ko‘rsatish</button></span>'+
   '<select id="inAgent"><option value="">Barcha agentlar</option>'+agents.map(function(a){return '<option value="'+a.id+'"'+(String(IN.agent)===String(a.id)?' selected':'')+'>'+esc(a.name)+'</option>'}).join('')+'</select>'+
   '<span class="grow"></span><span class="muted" id="inLabel"></span></div><div id="inBody"><div class="grid g4">'+'<div class="skel"></div>'.repeat(4)+'</div></div>';
  $('inSeg').onclick=function(e){var b=e.target.closest('button');if(!b)return;IN.period=b.dataset.p;if(IN.period==='custom'){$('inSeg').querySelectorAll('button').forEach(function(x){x.classList.toggle('on',x===b)});$('inCustom').hidden=false;return}IN.page=0;pageInsights(page)};
  $('inGo').onclick=function(){IN.from=$('inFrom').value;IN.to=$('inTo').value;IN.page=0;pageInsights(page)};
  $('inAgent').onchange=function(){IN.agent=this.value;IN.page=0;pageInsights(page)};
  if(IN.period==='custom'&&!IN.from)return;
  var key='in'+IN.period+IN.from+IN.to+IN.agent,d=!force&&S.cache[key];
  if(!d){d=await run(function(){return api('insights',{period:IN.period,from:IN.from,to:IN.to,agentId:IN.agent?+IN.agent:undefined})});if(!d){$('inBody').innerHTML='';return}S.cache[key]=d}
  if(S.page!=='insights')return;
  S.insights=d;$('inLabel').textContent=(d.label||'')+(d.compareLabel?' · taqqoslash: '+d.compareLabel:'');renderInsights();
}
function renderInsights(){
  var d=S.insights,sm=d.summary,plan=d.today||{items:[],total:0};
  var groups={active:0,low:0,passive:0},st={};
  d.clients.forEach(function(c){var k=c.kpi||{};if(k.status==='rated')groups[k.group]=(groups[k.group]||0)+1;else st[k.status]=(st[k.status]||0)+1});
  var tabs=[['plan',ic('target','sm')+' Bugun kimga',plan.total],['clients',ic('trend','sm')+' Mijozlar reytingi',d.clients.length],['regions',ic('map','sm')+' Hududlar',d.regions.length],['agents',ic('compass','sm')+' Agentlar',d.agents.length],['products',ic('box','sm')+' Mahsulotlar',d.products.length]];
  $('inBody').innerHTML=
   '<div class="grid g4" style="margin-bottom:16px">'+
     kpi('📦','Tovar berildi',cents(sm.deliveredCents),num(sm.deliveredQty)+' dona · '+(sm.deliveryGrowth?esc(sm.deliveryGrowth.text):''))+
     kpi('💰','To‘lov olindi',cents(sm.paidCents),sm.paymentGrowth?esc(sm.paymentGrowth.text):'')+
     kpi('🧾','Qarz (davr oxiri)',cents(sm.debtCents),sm.advanceCents?'Avans: '+cents(sm.advanceCents):'','bad')+
     kpi('🏪','Mijozlar',num(sm.clients),sm.rated+' baholangan · '+sm.prospects+' istiqbolli')+
   '</div>'+
   '<div class="card" style="margin-bottom:16px"><div class="card-h"><h3>Mijozlar faolligi</h3><span class="muted small">Ball: faollik + to‘lov intizomi + o‘sish (0–100)</span></div>'+
     '<div class="stack" style="margin-bottom:10px">'+[['active',C.forest],['low','#d98a06'],['passive','#e5384f']].map(function(g){return groups[g[0]]?'<i style="flex:'+groups[g[0]]+';background:'+g[1]+'"></i>':''}).join('')+'</div>'+
     '<div class="actions">'+Object.keys(KGRP).map(function(k){return pill(KGRP[k][0]+' · '+(groups[k]||0),KGRP[k][1])}).join('')+
       [['new','Yangi'],['prospect','Istiqbolli'],['nobase','Asos yo‘q'],['insufficient','Ma’lumot kam'],['incomplete','Hisob to‘liq emas'],['blacklisted','Qora ro‘yxat']].map(function(x){return st[x[0]]?pill(x[1]+' · '+st[x[0]]):''}).join('')+'</div></div>'+
   '<div class="tabs" id="inTabs">'+tabs.map(function(t){return '<button data-t="'+t[0]+'" class="'+(IN.tab===t[0]?'on':'')+'">'+t[1]+' <span class="muted">'+t[2]+'</span></button>'}).join('')+'</div>'+
   '<div id="inTab"></div>';
  $('inTabs').onclick=function(e){var b=e.target.closest('button');if(!b)return;IN.tab=b.dataset.t;IN.page=0;renderInsights()};
  ({plan:inPlan,clients:inClients,regions:inRegions,agents:inAgents,products:inProducts})[IN.tab]($('inTab'),d);
}
function inPlan(el,d){
  var p=d.today||{items:[],total:0};
  el.innerHTML='<div class="toolbar"><span class="muted">Davrdan qat’i nazar, joriy holat bo‘yicha. '+(p.total>p.items.length?'Eng muhim '+p.items.length+' tasi ko‘rsatildi (jami '+p.total+').':'')+'</span><span class="grow"></span><button class="btn" id="inExp">'+ic('download')+' Excel</button></div>'+
   '<div class="card flush"><div class="tbl-wrap"><table><thead><tr><th>Muhimlik</th><th>Mijoz</th><th>Agent</th><th>Sabab</th><th>Nima qilish kerak</th><th class="right">Qarz</th><th>Oxirgi tashrif</th></tr></thead><tbody>'+
   (p.items.length?p.items.map(function(i){var pr=PRI[i.priority]||PRI[3];return '<tr class="click" data-client="'+i.clientId+'"><td>'+pill(pr[0],pr[1])+'</td><td><b>'+esc(i.name)+'</b><br><small class="muted">'+esc(i.region)+'</small></td><td>'+esc(i.agent)+'</td><td>'+i.reasons.map(function(r){return esc(r.text)}).join('<br>')+'</td><td><b>'+esc(i.action)+'</b></td><td class="right num '+(i.debtNowCents>0?'bad':'')+'">'+(i.debtNowCents?cents(i.debtNowCents):'—')+'</td><td class="num">'+(i.lastVisitTs?dday(i.lastVisitTs):'—')+'</td></tr>'}).join(''):'<tr><td colspan="7" class="empty">'+ic('checkc','lg')+'<br>Bugun shoshilinch ish yo‘q</td></tr>')+
   '</tbody></table></div></div>';
  bindClientLinks(el);
  $('inExp').onclick=function(){exportRows('ASMAN-bugungi-reja',['Muhimlik','Mijoz','Hudud','Agent','Sabab','Amal','Qarz USD','Oxirgi tashrif'],p.items.map(function(i){return [(PRI[i.priority]||PRI[3])[0],i.name,i.region,i.agent,i.reasons.map(function(r){return r.text}).join('; '),i.action,(i.debtNowCents||0)/100,i.lastVisitTs?dday(i.lastVisitTs):'']}))};
}
function inClients(el,d){
  var q=IN.q.trim().toLowerCase(),rows=d.clients.filter(function(c){return !q||(c.name+' '+c.agent+' '+c.region).toLowerCase().indexOf(q)>=0});
  var pages=Math.max(1,Math.ceil(rows.length/PAGE_SIZE));if(IN.page>=pages)IN.page=pages-1;
  var slice=rows.slice(IN.page*PAGE_SIZE,(IN.page+1)*PAGE_SIZE);
  var kp=function(k){if(!k)return '';if(k.status==='rated'){var g=KGRP[k.group]||['',''];return '<b class="num">'+k.score+'</b> '+pill(g[0],g[1])+(k.provisional?' <small class="muted" title="Taxminiy: davr hali tugamagan">~</small>':'')}return pill(esc(k.label),k.status==='blacklisted'?'p-bad':k.status==='new'?'p-pri':'')};
  el.innerHTML='<div class="toolbar"><input type="search" id="inQ" placeholder="Mijoz, agent yoki hudud…" value="'+esc(IN.q)+'"><span class="grow"></span><span class="muted small">'+num(rows.length)+' ta</span><button class="btn" id="inExp">'+ic('download')+' Excel</button></div>'+
   '<div class="card flush"><div class="tbl-wrap"><table><thead><tr><th class="right">#</th><th>Mijoz</th><th>Agent</th><th>Hudud</th><th>Ball</th><th class="right">Tovar</th><th class="right">To‘lov</th><th class="right">Qarz</th><th>O‘sish</th></tr></thead><tbody>'+
   (slice.length?slice.map(function(c){return '<tr class="click" data-client="'+c.id+'"><td class="right num muted">'+(c.rank||'')+'</td><td><b>'+esc(c.name)+'</b></td><td>'+esc(c.agent)+'</td><td>'+esc(c.region)+'</td><td>'+kp(c.kpi)+'</td><td class="right num">'+cents(c.deliveredCents)+'</td><td class="right num">'+cents(c.paidCents)+'</td><td class="right num '+(c.debtCents>0?'bad':'')+'">'+cents(c.debtCents)+'</td><td>'+grow(c.deliveryGrowth)+' / '+grow(c.paymentGrowth)+'</td></tr>'}).join(''):'<tr><td colspan="9" class="empty">Mijoz topilmadi</td></tr>')+
   '</tbody></table></div>'+(pages>1?'<div class="pager"><span>'+(IN.page*PAGE_SIZE+1)+'–'+Math.min(rows.length,(IN.page+1)*PAGE_SIZE)+' / '+num(rows.length)+'</span><span class="actions"><button class="btn sm" id="inPrev"'+(IN.page?'':' disabled')+'>‹ Oldingi</button><button class="btn sm" id="inNext"'+(IN.page<pages-1?'':' disabled')+'>Keyingi ›</button></span></div>':'')+'</div>';
  $('inQ').oninput=debounce(function(){IN.q=this.value;IN.page=0;inClients(el,d);var i=$('inQ');i.focus();i.setSelectionRange(i.value.length,i.value.length)},200);
  if($('inPrev'))$('inPrev').onclick=function(){IN.page--;inClients(el,d)};
  if($('inNext'))$('inNext').onclick=function(){IN.page++;inClients(el,d)};
  bindClientLinks(el);
  $('inExp').onclick=function(){exportRows('ASMAN-mijozlar-reytingi',['O‘rin','Mijoz','Agent','Hudud','Ball','Guruh / holat','Tovar USD','To‘lov USD','Qarz USD','Tovar o‘sishi','To‘lov o‘sishi'],rows.map(function(c){var k=c.kpi||{};return [c.rank||'',c.name,c.agent,c.region,k.score==null?'':k.score,k.label||'',c.deliveredCents/100,c.paidCents/100,c.debtCents/100,c.deliveryGrowth?c.deliveryGrowth.text:'',c.paymentGrowth?c.paymentGrowth.text:'']}))};
}
function inRegions(el,d){
  el.innerHTML='<div class="toolbar"><span class="grow"></span><button class="btn" id="inExp">'+ic('download')+' Excel</button></div><div class="card flush"><div class="tbl-wrap"><table><thead><tr><th>Hudud</th><th class="right">Mijoz</th><th class="right">Istiqbolli</th><th class="right">Tovar</th><th class="right">To‘lov</th><th class="right">Qarz</th><th>O‘sish (tovar / to‘lov)</th></tr></thead><tbody>'+
   d.regions.map(function(r){return '<tr><td><b>'+esc(r.name)+'</b></td><td class="right num">'+r.clients+'</td><td class="right num">'+r.prospects+'</td><td class="right num">'+cents(r.deliveredCents)+'</td><td class="right num">'+cents(r.paidCents)+'</td><td class="right num '+(r.debtCents>0?'bad':'')+'">'+cents(r.debtCents)+'</td><td>'+grow(r.deliveryGrowth)+' / '+grow(r.paymentGrowth)+'</td></tr>'}).join('')+'</tbody></table></div></div>';
  $('inExp').onclick=function(){exportRows('ASMAN-hududlar',['Hudud','Mijoz','Istiqbolli','Tovar USD','To‘lov USD','Qarz USD','Tovar o‘sishi','To‘lov o‘sishi'],d.regions.map(function(r){return [r.name,r.clients,r.prospects,r.deliveredCents/100,r.paidCents/100,r.debtCents/100,r.deliveryGrowth.text,r.paymentGrowth.text]}))};
}
function inAgents(el,d){
  el.innerHTML='<div class="toolbar"><span class="grow"></span><button class="btn" id="inExp">'+ic('download')+' Excel</button></div><div class="card flush"><div class="tbl-wrap"><table><thead><tr><th>Agent</th><th class="right">Mijozlar</th><th class="right">Tovar berdi</th><th class="right">Qaytarildi</th><th class="right">To‘lov oldi</th><th class="right">Portfel qarzi</th></tr></thead><tbody>'+
   d.agents.map(function(a){var o=a.operations;return '<tr class="click" data-agent="'+a.agentId+'"><td><b>'+esc(a.agent)+'</b></td><td class="right num">'+a.clients+'</td><td class="right num">'+cents(o.deliveredCents)+'</td><td class="right num">'+cents(o.returnedCents)+'</td><td class="right num">'+cents(o.paidCents)+'</td><td class="right num '+(a.debtCents>0?'bad':'')+'">'+cents(a.debtCents)+'</td></tr>'}).join('')+'</tbody></table></div></div>';
  bindAgentLinks(el);
  $('inExp').onclick=function(){exportRows('ASMAN-agentlar',['Agent','Mijozlar','Tovar USD','Qaytarildi USD','To‘lov USD','Qarz USD'],d.agents.map(function(a){var o=a.operations;return [a.agent,a.clients,o.deliveredCents/100,o.returnedCents/100,o.paidCents/100,a.debtCents/100]}))};
}
function inProducts(el,d){
  el.innerHTML='<div class="toolbar"><span class="grow"></span><button class="btn" id="inExp">'+ic('download')+' Excel</button></div><div class="card flush"><div class="tbl-wrap"><table><thead><tr><th>Mahsulot</th><th class="right">Berildi</th><th class="right">Summa</th><th class="right">Qaytdi</th><th>O‘sish (dona / summa)</th></tr></thead><tbody>'+
   (d.products.length?d.products.map(function(p){return '<tr><td><b>'+esc(p.name)+'</b></td><td class="right num">'+num(p.deliveredQty)+'</td><td class="right num">'+cents(p.deliveredCents)+'</td><td class="right num">'+(p.returnedQty?num(p.returnedQty)+' · '+cents(p.returnedCents):'—')+'</td><td>'+grow(p.qtyGrowth)+' / '+grow(p.amountGrowth)+'</td></tr>'}).join(''):'<tr><td colspan="5" class="empty">Bu davrda tovar harakati yo‘q</td></tr>')+'</tbody></table></div></div>';
  $('inExp').onclick=function(){exportRows('ASMAN-mahsulotlar',['Mahsulot','Berildi dona','Summa USD','Qaytdi dona','Qaytdi USD','Dona o‘sishi','Summa o‘sishi'],d.products.map(function(p){return [p.name,p.deliveredQty,p.deliveredCents/100,p.returnedQty,p.returnedCents/100,p.qtyGrowth.text,p.amountGrowth.text]}))};
}

/* ----- Excel eksport (ekranda ko'rinayotgan qatorlar) ----- */
function exportRows(name,head,rows){
  // UTF-16LE + BOM, tab bilan ajratilgan: Excel kirill/lotin harflarini va ustunlarni har qanday tilda to'g'ri ochadi.
  var cell=function(v){v=v==null?'':String(v);return /[\t\n"]/.test(v)?'"'+v.replace(/"/g,'""')+'"':v};
  var text=[head].concat(rows).map(function(r){return r.map(cell).join('\t')}).join('\r\n');
  var buf=new Uint8Array(2+text.length*2);buf[0]=0xFF;buf[1]=0xFE;
  for(var i=0;i<text.length;i++){var c=text.charCodeAt(i);buf[2+i*2]=c&255;buf[3+i*2]=c>>8}
  var url=URL.createObjectURL(new Blob([buf],{type:'text/csv;charset=utf-16le'})),a=document.createElement('a');
  a.href=url;a.download=name+'-'+today()+'.csv';document.body.appendChild(a);a.click();a.remove();setTimeout(function(){URL.revokeObjectURL(url)},4000);
  toast(num(rows.length)+' qator yuklab olindi');
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
   '<div class="toolbar"><div class="seg" id="whSeg">'+tabs.map(function(t){return '<button data-s="'+t[0]+'" class="'+(w.filter===t[0]?'on':'')+'">'+esc(t[1])+'<b>'+t[2]+'</b></button>'}).join('')+'</div><span class="grow"></span><button class="btn pri" id="whAdd">'+ic('plus')+' Yangi mahsulot</button></div>'+
   '<div class="grid g-main"><div class="card flush"><div class="tbl-wrap"><table><thead><tr><th>#</th><th>Sana</th><th>Agent / mijoz</th><th>Tovarlar</th><th class="right">Summa</th><th>Holat</th><th></th></tr></thead><tbody>'+
    (w.orders.length?w.orders.map(function(o){return '<tr><td class="num">'+o.id+'</td><td class="num">'+dt(o.ts)+'</td><td><b>'+esc(o.agentName)+'</b><br><small class="muted">'+esc(o.clientName)+'</small></td><td>'+o.items.map(function(i){return esc(i.name)+' × '+i.qty+(i.custom?' <span class="pill p-warn">katalogda yo‘q</span>':'')}).join('<br>')+(o.note?'<br><small class="muted">'+ic('note','sm')+' '+esc(o.note)+'</small>':'')+(o.adminNote?'<br><small class="muted">'+ic('edit','sm')+' '+esc(o.adminNote)+'</small>':'')+'</td><td class="right num">'+usd(o.totalCents/100)+'</td><td>'+pill(esc(o.statusLabel),SC[o.status])+'</td><td class="actions">'+(NEXT[o.status]||[]).map(function(n){return '<button class="btn sm'+(n[0]==='rejected'?' danger':'')+'" data-o="'+o.id+'" data-to="'+n[0]+'">'+n[1]+'</button>'}).join('')+'</td></tr>'}).join(''):'<tr><td colspan="7" class="empty">Buyurtma yo‘q</td></tr>')+
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
   '<div class="card flush"><div class="card-h"><h3>Agentlar <span class="muted small">'+s.agents.filter(function(a){return a.active}).length+' faol</span></h3><button class="btn pri sm" id="stAddAgent">'+ic('plus')+' Agent qo‘shish</button></div><div class="tbl-wrap" style="margin-top:12px"><table><thead><tr><th>Agent</th><th>Telegram ID</th><th class="right">Mijoz</th><th>Holat</th></tr></thead><tbody>'+
    s.agents.map(function(a){return '<tr class="click" data-agent="'+a.id+'"><td><div class="cell">'+avatar(a.name,a.photoUrl)+'<b>'+esc(a.name)+'</b></div></td><td class="num">'+a.id+'</td><td class="right num">'+a.clients+'</td><td>'+(a.active?(a.shiftOpen?pill('<span class="dot"></span>Smenada','p-ok'):pill('Faol','p-pri')):pill('Bloklangan','p-bad'))+'</td></tr>'}).join('')+'</tbody></table></div></div>'+
   '<div class="card flush"><div class="card-h"><h3>Kassirlar</h3><button class="btn pri sm" id="stAddCash">'+ic('plus')+' Kassir qo‘shish</button></div><div class="tbl-wrap" style="margin-top:12px"><table><thead><tr><th>Kassir</th><th>Telegram ID</th><th class="right">Qabul</th><th>Oxirgi</th><th></th></tr></thead><tbody>'+
    (s.cashiers.length?s.cashiers.map(function(c){return '<tr><td><div class="cell">'+avatar(c.name,c.photoUrl)+'<div class="t"><b>'+esc(c.name)+'</b><small>'+(c.active?'Faol':'Yopilgan')+'</small></div></div></td><td class="num">'+c.id+'</td><td class="right num">'+c.accepted+'</td><td class="num">'+(c.lastTs?dday(c.lastTs):'—')+'</td><td class="actions"><button class="btn sm" data-cr="'+c.id+'">'+ic('edit','sm')+'</button>'+(S.primary?(c.active?'<button class="btn sm" data-ct="'+c.id+'">'+ic('swap','sm')+'</button><button class="btn sm danger" data-cd="'+c.id+'">Yopish</button>':'<button class="btn sm" data-ca="'+c.id+'">Ochish</button>'):'')+'</td></tr>'}).join(''):'<tr><td colspan="5" class="empty">Kassir yo‘q</td></tr>')+'</tbody></table></div></div>'+
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
   '<div class="card"><div class="card-h"><h3>'+ic('bell')+' Bildirishnomalar</h3></div>'+
    '<div class="switch"><span>Brauzer bildirishnomasi<br><small class="muted">Panel boshqa oynada bo‘lsa ham xabar chiqadi</small></span><button class="tog'+(store('rw-notify')==='1'&&window.Notification&&Notification.permission==='granted'?' on':'')+'" id="tgNotify" aria-label="Brauzer bildirishnomasi"></button></div>'+
    '<div class="switch"><span>Ovozli signal</span><button class="tog'+(store('rw-sound')!=='0'?' on':'')+'" id="tgSound" aria-label="Ovozli signal"></button></div>'+
    '<p class="hint" style="margin-top:10px">Panel har 30 soniyada yangilanadi (fon rejimida — har 60 soniyada). Xabarlar: yangi buyurtma, kassaga topshiriq va uning qabuli, yangi mijoz, agent smenani ochishi/yopishi.</p>'+
    '<div class="actions"><button class="btn sm" id="tgTest">Sinab ko‘rish</button></div></div>'+
   '<form class="card" id="pwForm"><div class="card-h"><h3>Parolni almashtirish</h3></div><div class="form" style="display:grid;gap:12px">'+
    '<label>Joriy parol<input type="password" name="old" autocomplete="current-password" required></label>'+
    '<label>Yangi parol<input type="password" name="new" autocomplete="new-password" minlength="8" required></label>'+
    '<label>Yangi parol (takror)<input type="password" name="new2" autocomplete="new-password" minlength="8" required></label>'+
    '<div class="form-err" id="pwErr"></div><button class="btn pri">Saqlash</button>'+
    '<p class="hint">Kamida 8 belgi. Parol almashganda boshqa kompyuterlardagi kirishlar yopiladi.</p></div></form>'+
   '</div>';
  $('stLogout').onclick=async function(){await auth('logout').catch(function(){});TOKEN='';store('rw-token',null);S.dash=null;S.cache={};showLogin()};
  $('tgNotify').onclick=async function(){var b=this;
    if(b.classList.contains('on')){store('rw-notify','0');b.classList.remove('on');return}
    if(!window.Notification){toast('Bu brauzer bildirishnomani qo‘llamaydi',true);return}
    var p=Notification.permission==='granted'?'granted':await Notification.requestPermission();
    if(p==='granted'){store('rw-notify','1');b.classList.add('on');toast('Bildirishnomalar yoqildi')}else toast('Brauzer ruxsat bermadi. Manzil satridagi qulf belgisidan ruxsat bering.',true)};
  $('tgSound').onclick=function(){var on=!this.classList.contains('on');store('rw-sound',on?'1':'0');this.classList.toggle('on',on);if(on&&!audioCtx&&window.AudioContext){try{audioCtx=new AudioContext()}catch(e){}}};
  $('tgTest').onclick=function(){var h=document.hidden;notifyAll([['🔔 Sinov','Bildirishnoma ishlayapti','settings']]);if(store('rw-notify')==='1'&&window.Notification&&Notification.permission==='granted'&&!h){try{new Notification('🔔 Sinov',{body:'Bildirishnoma ishlayapti',icon:'/app/premium-kit/emblem.png'})}catch(e){}}};
  $('pwForm').onsubmit=async function(e){
    e.preventDefault();var f=new FormData(this),err=$('pwErr');err.textContent='';
    if(f.get('new')!==f.get('new2')){err.textContent='Yangi parollar bir xil emas.';return}
    var r=await run(function(){return auth('change_password',{old:f.get('old'),new:f.get('new')})},'Parol almashtirildi');if(r)this.reset();
  };
}

boot();
})();
