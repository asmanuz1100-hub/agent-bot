/* ASMAN — sodda hisobot (Rahbar va Agent): Hududlar, Mijozlar reytingi, Agentlar, Bugun kimga.
 * Sotuv = mijozga berilgan tovar qiymati. Hisob serverda (analytics.py), pul butun sentda keladi.
 * AsmanInsights.mount(el,{mode:'manager'|'agent',req:fn(payload)->Promise,openClient:fn(id),agents:fn()->[{id,name}]})
 */
(function(){
'use strict';
function esc(v){return String(v==null?'':v).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]})}
function usd(c){var n=Number(c||0)/100;return n.toLocaleString('en-US',{minimumFractionDigits:n%1?2:0,maximumFractionDigits:2})+' $'}
var CSS='.ai{--c:var(--card,var(--tg-section,#fff));--t:var(--tx,var(--tg-text,#17212b));--m:var(--mu,var(--muted,#66727f));--l:var(--line,#e5ecf5);--s:var(--soft,#f3f5f9);--p:var(--pri,var(--blue,#2a8bf2));background:var(--c);color:var(--t);border:1px solid var(--l);border-radius:20px;padding:14px;margin:0 0 14px}'+
'.ai b{font-weight:800}.ai small{color:var(--m)}.ai-h{font-size:17px;font-weight:800;margin-bottom:10px}'+
'.ai-row{display:flex;gap:6px;overflow-x:auto;margin-bottom:8px;scrollbar-width:none}.ai-row::-webkit-scrollbar{display:none}'+
'.ai-row button{flex:1 1 0;min-width:0;white-space:nowrap;border:1px solid var(--l);background:var(--s);color:var(--t);border-radius:14px;padding:8px 6px;font:inherit;font-size:12.5px;font-weight:700;cursor:pointer}'+
'.ai-row button.on{background:var(--p);border-color:transparent;color:#fff}'+
'.ai select{width:100%;border:1px solid var(--l);background:var(--s);color:var(--t);border-radius:14px;padding:9px 10px;font:inherit;font-size:13px;font-weight:700;margin-bottom:8px}'+
'.ai-sum{display:grid;grid-template-columns:repeat(3,1fr);gap:6px;margin:4px 0 10px}.ai-sum div{background:var(--s);border-radius:14px;padding:9px 8px;text-align:center}.ai-sum small{display:block;font-size:11.5px}.ai-sum b{display:block;font-size:14px;margin-top:2px;white-space:nowrap}'+
'.ai-it{display:block;width:100%;text-align:left;background:none;border:0;border-top:1px solid var(--l);padding:11px 2px;color:inherit;font:inherit;cursor:pointer}.ai-it:first-child{border-top:0}'+
'.ai-top{display:flex;justify-content:space-between;gap:8px}.ai-top b{font-size:14.5px;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.ai-top span{flex:none;font-weight:800;font-size:14.5px}'+
'.ai-it small{display:block;font-size:12.5px;margin-top:3px}.ai-sub{margin-left:8px;border-left:2px solid var(--l);padding-left:8px}'+
'.ai-leg{font-size:12px;color:var(--m);margin:0 0 4px}.ai-more{width:100%;margin-top:8px;border:1px dashed var(--l);background:none;color:var(--p);border-radius:12px;padding:10px;font:inherit;font-weight:800;cursor:pointer}'+
'.ai-empty{text-align:center;color:var(--m);font-size:13px;padding:16px 6px}';
function css(){if(document.getElementById('ai-css'))return;var s=document.createElement('style');s.id='ai-css';s.textContent=CSS;document.head.appendChild(s)}
var TODAY_CODES={agreed_visit:1,agreed_payment:1,collection_task:1,visit_due:1,prospect:1};

function mount(el,o){
 css();var mgr=o.mode==='manager';
 var st={period:'month',agent:'',tab:mgr?'regions':'today',limit:30,open:{},data:null,key:'',at:0,err:''};
 el.classList.add('ai');
 function marks(list){var buyers=list.filter(function(c){return c.deliveredCents>0});var top=Math.ceil(buyers.length/3);
  buyers.forEach(function(c,i){c._m=i<top?'🟢':'🟡'});list.forEach(function(c){if(!(c.deliveredCents>0))c._m='🔴'});return list}
 function ranked(d){return marks((d.clients||[]).filter(function(c){return !c.prospect}).sort(function(a,b){return b.deliveredCents-a.deliveredCents||b.payment.paidCents-a.payment.paidCents}))}
 function clientRow(c,n){return '<button type="button" class="ai-it" data-ai-open="'+c.id+'"><div class="ai-top"><b>'+(n?n+'. ':'')+c._m+' '+esc(c.name)+'</b><span>'+usd(c.deliveredCents)+'</span></div>'+
  '<small>'+(c.deliveredCents>0?'':'Bu davrda tovar olmagan · ')+'To‘lov '+usd(c.payment.paidCents)+' · Qarz '+usd(Math.max(0,c.payment.debtEndCents))+(mgr?' · '+esc(c.agent):'')+'</small></button>'}
 function regions(d){var rk=ranked(d),by={};rk.forEach(function(c){by[c.id]=c});
  var list=(d.regions||[]).slice().sort(function(a,b){return b.deliveredCents-a.deliveredCents});if(!list.length)return '<div class="ai-empty">Ma’lumot yo‘q.</div>';
  return list.map(function(r){var open=st.open[r.key];var members=r.clientIds.map(function(id){return by[id]}).filter(Boolean).sort(function(a,b){return b.deliveredCents-a.deliveredCents});
   return '<div><button type="button" class="ai-it" data-ai-region="'+esc(r.key)+'"><div class="ai-top"><b>'+(open?'▾ ':'▸ ')+esc(r.name)+'</b><span>'+usd(r.deliveredCents)+'</span></div>'+
    '<small>'+(r.clients-r.prospects)+' mijoz · To‘lov '+usd(r.paidCents)+' · Qarz '+usd(Math.max(0,r.debtEndCents))+'</small></button>'+
    (open?'<div class="ai-sub">'+(members.length?members.map(function(c){return clientRow(c,0)}).join(''):'<div class="ai-empty">Mijoz yo‘q.</div>')+'</div>':'')+'</div>'}).join('')}
 function clients(d){var list=ranked(d);if(!list.length)return '<div class="ai-empty">Mijoz yo‘q.</div>';
  var h='<div class="ai-leg">🟢 eng ko‘p olgan · 🟡 olgan · 🔴 bu davrda olmagan</div>'+list.slice(0,st.limit).map(function(c,i){return clientRow(c,i+1)}).join('');
  if(list.length>st.limit)h+='<button type="button" class="ai-more" data-ai-more>Yana ko‘rsatish ('+(list.length-st.limit)+')</button>';return h}
 function agents(d){var list=(d.agents||[]).slice().sort(function(a,b){return b.operations.deliveredCents-a.operations.deliveredCents});if(!list.length)return '<div class="ai-empty">Ma’lumot yo‘q.</div>';
  return list.map(function(a){return '<div class="ai-it" style="cursor:default"><div class="ai-top"><b>'+esc(a.agent)+'</b><span>'+usd(a.operations.deliveredCents)+'</span></div>'+
   '<small>'+(a.clients-a.prospects)+' mijoz · To‘lov '+usd(a.operations.paidCents)+' · Qarz '+usd(Math.max(0,a.debtEndCents))+'</small></div>'}).join('')}
 function today(d){var t=d.today;var items=((t&&t.items)||[]).map(function(i){var r=i.reasons.filter(function(x){return TODAY_CODES[x.code]});return r.length?{i:i,r:r[0]}:null}).filter(Boolean);
  if(!items.length)return '<div class="ai-empty">✅ Bugun shoshilinch mijoz yo‘q.</div>';
  return items.map(function(x){var i=x.i;return '<button type="button" class="ai-it" data-ai-open="'+i.clientId+'"><div class="ai-top"><b>'+esc(i.name)+'</b><span>'+(i.debtNowCents>0?usd(i.debtNowCents):'')+'</span></div>'+
   '<small>'+esc(x.r.text)+(mgr?' · '+esc(i.agent):'')+'</small></button>'}).join('')}
 function load(force){var key=st.period+'|'+st.agent;
  if(!force&&st.key===key&&st.data&&Date.now()-st.at<120000){paint();return}
  st.err='';paint();var p={period:st.period};if(mgr&&st.agent)p.agentId=st.agent;
  o.req(p).then(function(d){if(key!==st.period+'|'+st.agent)return;st.data=d;st.key=key;st.at=Date.now();paint()},function(e){st.err=(e&&e.message)||'Hisobot yuklanmadi.';paint()})}
 function paint(){var d=st.key===st.period+'|'+st.agent?st.data:null;
  var tabs=mgr?[['regions','Hududlar'],['clients','Mijozlar'],['agents','Agentlar'],['today','🎯 Kimga']]:[['today','Bugun kimga'],['regions','Hududlar'],['clients','Mijozlar']];
  var h='<div class="ai-h">📊 Hisobot</div><div class="ai-row">'+tabs.map(function(x){return '<button type="button" data-ai-tab="'+x[0]+'" class="'+(st.tab===x[0]?'on':'')+'">'+x[1]+'</button>'}).join('')+'</div>';
  if(st.tab!=='today'){h+='<div class="ai-row">'+[['today','Bugun'],['week','Hafta'],['month','Oy']].map(function(x){return '<button type="button" data-ai-per="'+x[0]+'" class="'+(st.period===x[0]?'on':'')+'">'+x[1]+'</button>'}).join('')+'</div>';
   if(mgr){var ags=(o.agents&&o.agents())||[];h+='<select data-ai-agent aria-label="Agent"><option value="">Barcha agentlar</option>'+ags.map(function(a){return '<option value="'+esc(a.id)+'"'+(String(a.id)===st.agent?' selected':'')+'>'+esc(a.name||a.id)+'</option>'}).join('')+'</select>'}}
  if(st.err){el.innerHTML=h+'<div class="ai-empty">'+esc(st.err)+'<button type="button" class="ai-more" data-ai-retry>↻ Qayta urinish</button></div>';return}
  if(!d){el.innerHTML=h+'<div class="ai-empty">Yuklanmoqda…</div>';return}
  if(st.tab==='today'){el.innerHTML=h+today(d);return}
  var s=d.summary;h+='<div class="ai-sum"><div><small>Sotuv</small><b>'+usd(s.deliveredCents)+'</b></div><div><small>To‘lov</small><b>'+usd(s.paidCents)+'</b></div><div><small>Qarz</small><b>'+usd(s.debtEndCents)+'</b></div></div>';
  h+=st.tab==='regions'?regions(d):st.tab==='clients'?clients(d):agents(d);el.innerHTML=h}
 el.addEventListener('click',function(e){var t=e.target.closest('button');if(!t||!el.contains(t))return;var ds=t.dataset,hit=true;
  if(ds.aiTab){st.tab=ds.aiTab;st.limit=30;paint()}
  else if(ds.aiPer){st.period=ds.aiPer;st.limit=30;load()}
  else if(ds.aiMore!==undefined){st.limit+=30;paint()}
  else if(ds.aiRegion!==undefined){st.open[ds.aiRegion]=!st.open[ds.aiRegion];paint()}
  else if(ds.aiOpen){o.openClient(Number(ds.aiOpen))}
  else if(ds.aiRetry!==undefined){load(true)}
  else hit=false;
  if(hit)e.stopPropagation()});
 el.addEventListener('change',function(e){if(e.target.matches('[data-ai-agent]')){st.agent=e.target.value;load()}});
 return {show:function(){load(false)},reset:function(){st.data=null;st.key='';st.err='';load(true)},state:st};
}
window.AsmanInsights={mount:mount,usd:usd};
})();
