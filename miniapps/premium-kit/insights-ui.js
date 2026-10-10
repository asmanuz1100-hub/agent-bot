/* ASMAN — sodda hisobot (Rahbar va Agent): Hududlar, Mahsulotlar, Mijozlar KPI, Agentlar, Bugun kimga.
 * Hisob serverda (analytics.py), pul butun sentda keladi. Bu fayl faqat ko'rsatadi.
 * AsmanInsights.mount(el,{mode:'manager'|'agent',req:fn(payload)->Promise,openClient:fn(id),agents:fn()->[{id,name}]})
 */
(function(){
'use strict';
function esc(v){return String(v==null?'':v).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]})}
function usd(c){var n=Number(c||0)/100;return '$'+n.toLocaleString('en-US',{minimumFractionDigits:n%1?2:0,maximumFractionDigits:2}).replace(/,/g,' ')}
var CSS='.ai{--c:var(--card,var(--tg-section,#fff));--t:var(--tx,var(--tg-text,#17212b));--m:var(--mu,var(--muted,#66727f));--l:var(--line,#e5ecf5);--s:var(--soft,#f3f5f9);--p:var(--pri,var(--blue,#2a8bf2));--aok:var(--ok,#1c9b43);--abad:var(--bad,#e5484d);--awarn:var(--warn,#c77c00);background:var(--c);color:var(--t);border:1px solid var(--l);border-radius:20px;padding:14px;margin:0 0 14px}'+
'.ai b{font-weight:800}.ai small{color:var(--m)}.ai-h{font-size:17px;font-weight:800;margin-bottom:10px}'+
'.ai-row{display:flex;gap:6px;overflow-x:auto;margin-bottom:8px;scrollbar-width:none}.ai-row::-webkit-scrollbar{display:none}'+
'.ai-row button{flex:1 0 auto;white-space:nowrap;border:1px solid var(--l);background:var(--s);color:var(--t);border-radius:14px;padding:8px 10px;font:inherit;font-size:12.5px;font-weight:700;cursor:pointer}'+
'.ai-row button.on{background:var(--p);border-color:transparent;color:#fff}'+
'.ai select{width:100%;border:1px solid var(--l);background:var(--s);color:var(--t);border-radius:14px;padding:9px 10px;font:inherit;font-size:13px;font-weight:700;margin-bottom:8px}'+
'.ai-dates{display:grid;grid-template-columns:1fr 1fr auto;gap:6px;margin-bottom:8px}.ai-dates input{min-width:0;border:1px solid var(--l);background:var(--s);color:var(--t);border-radius:12px;padding:8px;font:inherit;font-size:12px}.ai-dates button{border:0;background:var(--p);color:#fff;border-radius:12px;padding:0 14px;font-weight:800}'+
'.ai-sum{display:grid;grid-template-columns:1fr 1fr;gap:6px;margin:4px 0 6px}.ai-sum div{background:var(--s);border-radius:14px;padding:9px 10px}.ai-sum small{display:block;font-size:11.5px}.ai-sum b{display:block;font-size:16px;margin-top:2px;white-space:nowrap}'+
'.ai-cmp{font-size:11.5px;color:var(--m);margin:0 0 8px}'+
'.ai-it{display:block;width:100%;text-align:left;background:none;border:0;border-top:1px solid var(--l);padding:11px 2px;color:inherit;font:inherit}.ai-it:first-child{border-top:0}button.ai-it{cursor:pointer}'+
'.ai-top{display:flex;justify-content:space-between;gap:8px;align-items:baseline}.ai-top b{font-size:14.5px;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.ai-top span{flex:none;font-weight:800;font-size:13px}'+
'.ai-it small{display:block;font-size:12.5px;margin-top:3px}.ai-sub{margin-left:8px;border-left:2px solid var(--l);padding-left:8px}'+
'.ai-up{color:var(--aok);font-weight:700}.ai-down{color:var(--abad);font-weight:700}'+
'.ai-g-active{color:var(--aok)}.ai-g-low{color:var(--awarn)}.ai-g-passive{color:var(--abad)}'+
'.ai-sec{margin-top:12px;font-weight:800;font-size:13.5px}.ai-why{display:inline-block;margin-top:5px;border:1px solid var(--l);background:var(--s);color:var(--p);border-radius:10px;padding:3px 8px;font:inherit;font-size:11.5px;font-weight:700;cursor:pointer}'+
'.ai-parts{background:var(--s);border-radius:12px;padding:8px 10px;font-size:12px;margin-top:6px;line-height:1.6}'+
'.ai-more{width:100%;margin-top:8px;border:1px dashed var(--l);background:none;color:var(--p);border-radius:12px;padding:10px;font:inherit;font-weight:800;cursor:pointer}'+
'.ai-note{font-size:12px;color:var(--awarn);margin:4px 0 8px}.ai-empty{text-align:center;color:var(--m);font-size:13px;padding:16px 6px}';
function css(){if(document.getElementById('ai-css'))return;var s=document.createElement('style');s.id='ai-css';s.textContent=CSS;document.head.appendChild(s)}
function gtxt(g){if(!g)return '';var c=g.kind==='pct'?(g.pct>=0?'ai-up':'ai-down'):'';return '<span class="'+c+'">'+esc(g.text)+'</span>'}

function mount(el,o){
 css();var mgr=o.mode==='manager';
 var st={period:'month',from:'',to:'',agent:'',tab:mgr?'regions':'today',grp:'all',limit:30,open:{},why:{},data:null,key:'',at:0,err:''};
 el.classList.add('ai');
 function key(){return st.period+'|'+st.from+'|'+st.to+'|'+st.agent}
 function money(c){return 'Olgan '+usd(c.deliveredCents)+' · Bergan '+usd(c.paidCents)+' · '+(c.debtCents<0?'Avans '+usd(-c.debtCents):'Qarz '+usd(c.debtCents))}
 function clientRow(c){var k=c.kpi,head;
  if(k.status==='rated')head=(c.rank?c.rank+'. ':'')+esc(c.name)+' · '+k.score+' ball · <span class="ai-g-'+k.group+'">'+esc(k.label)+'</span>';
  else head=esc(c.name)+' · <small style="display:inline">'+esc(k.label)+'</small>';
  var h='<div class="ai-it"><button type="button" class="ai-it" style="border:0;padding:0" data-ai-open="'+c.id+'"><div class="ai-top"><b>'+head+'</b></div>'+
   '<small>'+money(c)+(mgr?' · '+esc(c.agent):'')+'</small>'+
   (k.status==='prospect'?'':'<small>Tovar olish '+gtxt(c.deliveryGrowth)+' · To‘lov '+gtxt(c.paymentGrowth)+'</small>')+'</button>';
  if(k.parts){h+='<button type="button" class="ai-why" data-ai-why="'+c.id+'">Ball qanday hisoblandi?</button>';
   if(st.why[c.id]){var p=k.parts;h+='<div class="ai-parts">Tovar olish faolligi: <b>'+p.activity+'</b> / 30<br>To‘lov holati: <b>'+p.payment+'</b> / 40<br>'+
    'Tovar olish o‘sishi: <b>'+(p.deliveryGrowth==null?'—':p.deliveryGrowth)+'</b> / 15<br>To‘lov o‘sishi: <b>'+(p.paymentGrowth==null?'—':p.paymentGrowth)+'</b> / 15</div>'}}
  return h+'</div>'}
 function summary(d){var s=d.summary;return '<div class="ai-sum"><div><small>Berilgan tovar</small><b>'+usd(s.deliveredCents)+'</b></div><div><small>Olingan pul</small><b>'+usd(s.paidCents)+'</b></div>'+
  '<div><small>Qaytgan tovar</small><b>'+usd(s.returnedCents)+'</b></div><div><small>Qolgan qarz</small><b>'+usd(s.debtCents)+'</b>'+(s.advanceCents?'<small>Avans '+usd(s.advanceCents)+'</small>':'')+'</div></div>'+
  '<div class="ai-cmp">Tovar olish '+gtxt(s.deliveryGrowth)+' · To‘lov '+gtxt(s.paymentGrowth)+'<br>Taqqoslash: '+esc(d.compareLabel)+(d.trimmed?' (oy qisqa — teng kunlar)':'')+'</div>'+
  (s.legacyEvents?'<div class="ai-note">⚠ '+s.legacyEvents+' ta eski so‘mdagi yozuv dollar hisobiga kirmagan.</div>':'')}
 function regions(d){var by={};(d.clients||[]).forEach(function(c){by[c.id]=c});var list=d.regions||[];if(!list.length)return '<div class="ai-empty">Ma’lumot yo‘q.</div>';
  return list.map(function(r){var open=st.open[r.key];
   return '<div><button type="button" class="ai-it" data-ai-region="'+esc(r.key)+'"><div class="ai-top"><b>'+(open?'▾ ':'▸ ')+esc(r.name)+'</b><span>'+usd(r.deliveredCents)+'</span></div>'+
    '<small>Pul '+usd(r.paidCents)+' · Qarz '+usd(r.debtCents)+(r.advanceCents?' · Avans '+usd(r.advanceCents):'')+' · '+r.clients+' mijoz</small>'+
    '<small>Tovar olish '+gtxt(r.deliveryGrowth)+' · To‘lov '+gtxt(r.paymentGrowth)+'</small></button>'+
    (open?'<div class="ai-sub">'+r.clientIds.map(function(id){return by[id]?clientRow(by[id]):''}).join('')+'</div>':'')+'</div>'}).join('')}
 function products(d){var list=d.products||[];if(!list.length)return '<div class="ai-empty">Bu davrda tovar harakati yo‘q.</div>';
  return list.map(function(p){return '<div class="ai-it"><div class="ai-top"><b>'+esc(p.name)+'</b><span>'+usd(p.deliveredCents)+'</span></div>'+
   '<small>Berilgan '+p.deliveredQty+' dona · Qaytgan '+p.returnedQty+' dona ('+usd(p.returnedCents)+')</small>'+
   '<small>Summa '+gtxt(p.amountGrowth)+' · Miqdor '+gtxt(p.qtyGrowth)+'</small></div>'}).join('')}
 function clients(d){var all=d.clients||[];var rated=all.filter(function(c){return c.kpi.status==='rated'});
  var groups=[['all','Hammasi'],['active','Faol'],['low','Faolligi past'],['passive','Passiv']];
  var h='<div class="ai-row">'+groups.map(function(g){var n=g[0]==='all'?rated.length:rated.filter(function(c){return c.kpi.group===g[0]}).length;
   return '<button type="button" data-ai-grp="'+g[0]+'" class="'+(st.grp===g[0]?'on':'')+'">'+g[1]+' '+n+'</button>'}).join('')+'</div>';
  var list=rated.filter(function(c){return st.grp==='all'||c.kpi.group===st.grp});
  h+=list.length?list.slice(0,st.limit).map(clientRow).join(''):'<div class="ai-empty">Reytingda mijoz yo‘q.</div>';
  if(list.length>st.limit)h+='<button type="button" class="ai-more" data-ai-more>Yana ko‘rsatish ('+(list.length-st.limit)+')</button>';
  [['new','Yangi mijozlar'],['insufficient','Baholash uchun ma’lumot yetarli emas'],['nobase','Baholash uchun asos yo‘q'],['prospect','Istiqbolli mijozlar']].forEach(function(s){
   var xs=all.filter(function(c){return c.kpi.status===s[0]});if(!xs.length)return;var open=st.open['s:'+s[0]];
   h+='<button type="button" class="ai-it ai-sec" data-ai-region="s:'+s[0]+'">'+(open?'▾ ':'▸ ')+esc(s[1])+' — '+xs.length+'</button>'+(open?'<div class="ai-sub">'+xs.map(clientRow).join('')+'</div>':'')});
  return h}
 function agents(d){var list=d.agents||[];if(!list.length)return '<div class="ai-empty">Ma’lumot yo‘q.</div>';
  return list.map(function(a){var op=a.operations;return '<div class="ai-it"><div class="ai-top"><b>'+esc(a.agent)+'</b><span>'+usd(op.deliveredCents)+'</span></div>'+
   '<small>Pul '+usd(op.paidCents)+' · Qaytgan '+usd(op.returnedCents)+'</small><small>Qarz '+usd(a.debtCents)+(a.advanceCents?' · Avans '+usd(a.advanceCents):'')+' · '+a.clients+' mijoz</small></div>'}).join('')}
 function today(d){var t=d.today,items=(t&&t.items)||[];if(!items.length)return '<div class="ai-empty">✅ Bugun shoshilinch mijoz yo‘q.</div>';
  return items.map(function(i){return '<button type="button" class="ai-it" data-ai-open="'+i.clientId+'"><div class="ai-top"><b>'+esc(i.name)+'</b><span>'+(i.debtNowCents>0?'Qarz '+usd(i.debtNowCents):'')+'</span></div>'+
   '<small>'+esc(i.reasons[0].text)+(mgr?' · '+esc(i.agent):'')+'</small><small>👉 '+esc(i.action)+'</small></button>'}).join('')}
 function load(force){var k=key();
  if(!force&&st.key===k&&st.data&&Date.now()-st.at<120000){paint();return}
  if(st.period==='custom'&&(!st.from||!st.to)){paint();return}
  st.err='';paint();var p={period:st.period};if(st.period==='custom'){p.from=st.from;p.to=st.to}if(mgr&&st.agent)p.agentId=st.agent;
  o.req(p).then(function(d){if(k!==key())return;st.data=d;st.key=k;st.at=Date.now();paint()},function(e){if(k!==key())return;st.err=(e&&e.message)||'Hisobot yuklanmadi.';paint()})}
 function paint(){var d=st.key===key()?st.data:(st.tab==='today'?st.data:null);
  var tabs=mgr?[['regions','Hududlar'],['products','Mahsulotlar'],['clients','Mijozlar'],['agents','Agentlar'],['today','Bugun kimga']]:[['today','Bugun kimga'],['regions','Hududlar'],['products','Mahsulotlar'],['clients','Mijozlar']];
  var h='<div class="ai-h">📊 Hisobot</div><div class="ai-row">'+tabs.map(function(x){return '<button type="button" data-ai-tab="'+x[0]+'" class="'+(st.tab===x[0]?'on':'')+'">'+x[1]+'</button>'}).join('')+'</div>';
  if(st.tab!=='today'){h+='<div class="ai-row">'+[['today','Bugun'],['week','7 kun'],['month','Shu oy'],['custom','Davr']].map(function(x){return '<button type="button" data-ai-per="'+x[0]+'" class="'+(st.period===x[0]?'on':'')+'">'+x[1]+'</button>'}).join('')+'</div>';
   if(st.period==='custom')h+='<div class="ai-dates"><input type="date" data-ai-from value="'+esc(st.from)+'"><input type="date" data-ai-to value="'+esc(st.to)+'"><button type="button" data-ai-go>OK</button></div>';
   if(mgr){var ags=(o.agents&&o.agents())||[];h+='<select data-ai-agent aria-label="Agent"><option value="">Barcha agentlar</option>'+ags.map(function(a){return '<option value="'+esc(a.id)+'"'+(String(a.id)===st.agent?' selected':'')+'>'+esc(a.name||a.id)+'</option>'}).join('')+'</select>'}}
  if(st.err){el.innerHTML=h+'<div class="ai-empty">'+esc(st.err)+'<button type="button" class="ai-more" data-ai-retry>↻ Qayta urinish</button></div>';return}
  if(!d){el.innerHTML=h+'<div class="ai-empty">'+(st.period==='custom'&&(!st.from||!st.to)?'Sanalarni tanlang.':'Yuklanmoqda…')+'</div>';return}
  if(st.tab==='today'){el.innerHTML=h+today(d);return}
  h+='<small style="display:block;margin-bottom:6px">'+esc(d.label)+'</small>'+summary(d);
  h+=st.tab==='regions'?regions(d):st.tab==='products'?products(d):st.tab==='clients'?clients(d):agents(d);el.innerHTML=h}
 el.addEventListener('click',function(e){var t=e.target.closest('button');if(!t||!el.contains(t))return;var ds=t.dataset,hit=true;
  if(ds.aiTab){st.tab=ds.aiTab;st.limit=30;paint()}
  else if(ds.aiPer){st.period=ds.aiPer;st.limit=30;load()}
  else if(ds.aiGo!==undefined){st.from=(el.querySelector('[data-ai-from]')||{}).value||'';st.to=(el.querySelector('[data-ai-to]')||{}).value||'';load(true)}
  else if(ds.aiGrp){st.grp=ds.aiGrp;st.limit=30;paint()}
  else if(ds.aiMore!==undefined){st.limit+=30;paint()}
  else if(ds.aiRegion!==undefined){st.open[ds.aiRegion]=!st.open[ds.aiRegion];paint()}
  else if(ds.aiWhy){st.why[ds.aiWhy]=!st.why[ds.aiWhy];paint()}
  else if(ds.aiOpen){o.openClient(Number(ds.aiOpen))}
  else if(ds.aiRetry!==undefined){load(true)}
  else hit=false;
  if(hit)e.stopPropagation()});
 el.addEventListener('change',function(e){if(e.target.matches('[data-ai-agent]')){st.agent=e.target.value;load()}});
 return {show:function(){load(false)},reset:function(){st.data=null;st.key='';st.err='';load(true)},state:st};
}
window.AsmanInsights={mount:mount,usd:usd};
})();
