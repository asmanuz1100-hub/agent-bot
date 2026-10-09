/* ASMAN Rahbar Premium — Hududlar va mijozlar reytingi (KPI).
 * Hisobot bo'limining boshiga bitta karta qo'shadi: mijozlar reytingi, hududlar va agentlar kesimi.
 * Ma'lumot /api/manager "insights" amalidan olinadi.
 */
(function(){
'use strict';
var P=window.PremiumReal;if(!P)return;
function $(id){return document.getElementById(id)}
function esc(v){return String(v==null?'':v).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]})}
function usd(v){return Number(v||0).toLocaleString('en-US',{minimumFractionDigits:0,maximumFractionDigits:0})}
var GC={best:'#16b364',growing:'#2a8bf2',stable:'#7c8db5',attention:'#f59e0b',risky:'#f0384f',sleeping:'#94a3b8'};
var st={period:'month',from:'',to:'',agent:'',tab:'clients',group:'',limit:25,data:null,busy:false,seq:0};

var css=document.createElement('style');css.textContent=
'.ki-card{background:var(--card);border:1px solid var(--line);border-radius:22px;padding:14px;margin:0 0 14px;box-shadow:0 6px 18px #0a1f5a12}'+
'.ki-h{display:flex;justify-content:space-between;align-items:center;gap:8px}.ki-h b{font-size:17px}.ki-h small{display:block;color:var(--mu);font-size:11.5px;margin-top:2px}'+
'.ki-seg{display:grid;grid-template-columns:repeat(3,1fr);gap:4px;background:var(--soft);border-radius:14px;padding:4px;margin:12px 0 10px}.ki-seg button{border:0;background:none;color:var(--mu);font-weight:700;font-size:12.5px;padding:9px 4px;border-radius:11px;cursor:pointer}.ki-seg button.on{background:var(--card);color:var(--tx);box-shadow:0 2px 8px #0a1f5a1f}'+
'.ki-tools{display:flex;gap:6px;align-items:center;flex-wrap:wrap;margin-bottom:10px}.ki-tools button{border:1px solid var(--line);background:var(--card);color:var(--tx);border-radius:20px;padding:7px 11px;font-size:12px;font-weight:700;cursor:pointer}.ki-tools button.on{background:var(--pri);border-color:var(--pri);color:#fff}.ki-tools select{border:1px solid var(--line);background:var(--card);color:var(--tx);border-radius:20px;padding:7px 10px;font-size:12px;font-weight:700;max-width:100%}'+
'.ki-dates{display:none;grid-template-columns:1fr 1fr auto;gap:6px;margin-bottom:10px}.ki-dates.on{display:grid}.ki-dates input{border:1px solid var(--line);background:var(--soft);color:var(--tx);border-radius:12px;padding:8px;font:inherit;font-size:12px;min-width:0}.ki-dates button{border:0;background:var(--pri);color:#fff;border-radius:12px;padding:0 14px;font-weight:800}'+
'.ki-kpi{display:grid;grid-template-columns:1fr 1fr;gap:7px;margin-bottom:10px}.ki-kpi div{background:var(--soft);border-radius:14px;padding:10px}.ki-kpi small{display:block;color:var(--mu);font-size:10.5px}.ki-kpi b{display:block;font-size:17px;margin-top:3px}'+
'.ki-groups{display:flex;gap:6px;overflow-x:auto;padding-bottom:4px;margin-bottom:6px}.ki-groups button{flex:none;display:flex;align-items:center;gap:6px;border:1px solid var(--line);background:var(--card);color:var(--tx);border-radius:14px;padding:7px 10px;font-size:12px;font-weight:700;cursor:pointer}.ki-groups button i{font-style:normal;min-width:20px;text-align:center;border-radius:10px;padding:1px 6px;color:#fff;background:var(--gc,#7c8db5);font-size:11px}.ki-groups button.on{border-color:var(--gc);box-shadow:0 0 0 2px var(--gc) inset}'+
'.ki-advice{background:var(--soft);border-radius:12px;padding:9px 11px;font-size:12px;color:var(--tx);margin:4px 0 8px;line-height:1.45}'+
'.ki-row{display:grid;grid-template-columns:34px 1fr auto;gap:10px;align-items:center;padding:11px 2px;border-top:1px solid var(--line);cursor:pointer}.ki-row:first-child{border-top:0}.ki-row:active{transform:scale(.99)}'+
'.ki-n{width:32px;height:32px;border-radius:11px;display:grid;place-items:center;font-weight:800;font-size:12.5px;color:#fff;background:var(--gc,#2a8bf2)}'+
'.ki-row b{display:block;font-size:13.5px;line-height:1.25}.ki-row small{display:block;color:var(--mu);font-size:11px;margin-top:2px;line-height:1.4}'+
'.ki-sc{text-align:right;min-width:52px}.ki-sc b{font-size:19px;color:var(--gc)}.ki-sc small{font-size:10px}'+
'.ki-bar{height:6px;border-radius:6px;background:var(--soft);overflow:hidden;margin-top:6px}.ki-bar u{display:block;height:100%;border-radius:6px;background:var(--gc,#2a8bf2)}'+
'.ki-more{display:block;width:100%;margin-top:8px;border:1px dashed var(--line);background:none;color:var(--pri);border-radius:12px;padding:10px;font-weight:800;cursor:pointer}'+
'.ki-up{color:var(--ok);font-weight:800}.ki-down{color:var(--bad);font-weight:800}'+
'.ki-badges{display:flex;gap:6px;flex-wrap:wrap;margin-top:4px}.ki-badges span{font-size:10.5px;font-weight:800;border-radius:9px;padding:2px 7px;background:var(--soft)}'+
'.ki-parts div{display:grid;grid-template-columns:96px 1fr 44px;gap:8px;align-items:center;font-size:12px;margin:7px 0}.ki-parts em{font-style:normal;text-align:right;font-weight:800}'+
'.ki-help{margin-top:10px;font-size:11.5px;color:var(--mu);line-height:1.5}.ki-help summary{cursor:pointer;font-weight:800;color:var(--pri)}'+
'.ki-empty{text-align:center;color:var(--mu);font-size:12.5px;padding:18px 8px}';
document.head.appendChild(css);

function section(){return document.querySelectorAll('section')[4]}
function ensure(){
 var sec=section(),bd=sec&&sec.querySelector('.bd');if(!bd)return null;
 var c=$('ki-card');if(c)return c;
 c=document.createElement('div');c.id='ki-card';c.className='ki-card';
 c.innerHTML='<div class="ki-h"><div><b>📊 Mijozlar va hududlar</b><small id="ki-sub">Reyting · KPI</small></div></div>'+
  '<div class="ki-seg" id="ki-tabs"><button data-ki-tab="clients" class="on">Mijozlar</button><button data-ki-tab="regions">Hududlar</button><button data-ki-tab="agents">Agentlar</button></div>'+
  '<div class="ki-tools"><button data-ki-per="week">7 kun</button><button data-ki-per="month" class="on">Shu oy</button><button data-ki-per="custom">Davr</button><select id="ki-agent" aria-label="Agent"><option value="">Barcha agentlar</option></select></div>'+
  '<div class="ki-dates" id="ki-dates"><input type="date" id="ki-from"><input type="date" id="ki-to"><button data-ki-go="1">OK</button></div>'+
  '<div id="ki-body"><div class="ki-empty">Yuklanmoqda…</div></div>';
 bd.insertBefore(c,bd.firstChild);
 return c;
}
function fillAgents(){
 var sel=$('ki-agent');if(!sel)return;var cur=sel.value;
 var ags=(P.agents&&P.agents())||[];
 sel.innerHTML='<option value="">Barcha agentlar</option>'+ags.map(function(a){return '<option value="'+a.id+'">'+esc(a.name||a.id)+'</option>'}).join('');
 sel.value=cur;
}
async function load(){
 if(!ensure())return;var seq=++st.seq;st.busy=true;
 var arg={period:st.period};if(st.period==='custom'){arg.from=st.from;arg.to=st.to}if(st.agent)arg.agentId=st.agent;
 try{var d=await P.req('insights',arg);if(seq!==st.seq)return;st.data=d;st.limit=25;render()}
 catch(e){if(seq!==st.seq)return;$('ki-body').innerHTML='<div class="ki-empty">'+esc(e.message||'Yuklanmadi')+'</div>'}
 finally{st.busy=false}
}
function growth(g){if(g==null)return '<span style="color:var(--mu)">yangi</span>';return '<span class="'+(g>=0?'ki-up':'ki-down')+'">'+(g>=0?'▲':'▼')+Math.abs(g).toFixed(0)+'%</span>'}
function render(){
 var d=st.data;if(!d)return;var s=d.summary||{};
 $('ki-sub').textContent=d.label+' · '+(s.ratedClients||0)+' ta mijoz baholandi';
 document.querySelectorAll('[data-ki-tab]').forEach(function(b){b.classList.toggle('on',b.dataset.kiTab===st.tab)});
 var h='<div class="ki-kpi"><div><small>Faol mijozlar</small><b>'+(s.activeClients||0)+' / '+(s.totalClients||0)+'</b></div><div><small>O‘rtacha ball</small><b>'+(s.avgScore||0)+' / 100</b></div><div><small>Realizatsiya</small><b>'+usd(s.salesUsd)+' $</b></div><div><small>Qarz</small><b>'+usd(s.debtUsd)+' $</b></div></div>';
 if(st.tab==='clients')h+=clientsHtml(d);else if(st.tab==='regions')h+=regionsHtml(d);else h+=agentsHtml(d);
 h+='<details class="ki-help"><summary>Ball qanday hisoblanadi?</summary>100 ballik baho: <b>Sotuv hajmi</b> — 40 ball, <b>To‘lov</b> (qarzi yo‘q yoki vaqtida to‘laydi) — 30 ball, <b>Muntazamlik</b> (har hafta tovar oladi) — 15 ball, <b>O‘sish</b> (o‘tgan davrga nisbatan) — 15 ball. '+(d.scoring?d.scoring.sleepDays:30)+' kun tovar olmagan mijoz — 💤, qarzi '+(d.scoring?d.scoring.riskDebtDays:21)+' kundan ortiq to‘lanmagan — 🔴.</details>';
 $('ki-body').innerHTML=h;
}
function clientsHtml(d){
 var groups=d.groups||[],h='<div class="ki-groups"><button data-ki-group="" class="'+(st.group?'':'on')+'" style="--gc:#2a8bf2">Hammasi <i>'+(d.clients||[]).length+'</i></button>'+
  groups.map(function(g){return '<button data-ki-group="'+g.key+'" class="'+(st.group===g.key?'on':'')+'" style="--gc:'+GC[g.key]+'">'+g.icon+' '+esc(g.label)+' <i>'+g.count+'</i></button>'}).join('')+'</div>';
 if(st.group){var g=groups.find(function(x){return x.key===st.group});if(g)h+='<div class="ki-advice"><b>'+g.icon+' '+esc(g.label)+':</b> '+esc(g.advice)+'</div>'}
 var list=(d.clients||[]).filter(function(c){return !st.group||c.group===st.group});
 if(!list.length)return h+'<div class="ki-empty">Bu guruhda mijoz yo‘q.</div>';
 h+=list.slice(0,st.limit).map(function(c){var col=GC[c.group];
  return '<div class="ki-row" data-ki-client="'+c.id+'" style="--gc:'+col+'"><div class="ki-n">'+c.rank+'</div><div><b>'+esc(c.name)+'</b><small>'+esc(c.region)+' · '+esc(c.agent)+'</small><small>'+c.groupIcon+' '+esc((c.reasons||[]).join(' · '))+'</small></div><div class="ki-sc"><b>'+c.score+'</b><small>ball</small></div></div>'}).join('');
 if(list.length>st.limit)h+='<button class="ki-more" data-ki-more="1">Yana ko‘rsatish ('+(list.length-st.limit)+')</button>';
 return h;
}
function regionsHtml(d){
 var list=d.regions||[];if(!list.length)return '<div class="ki-empty">Hudud ma’lumoti yo‘q.</div>';
 var mx=Math.max.apply(null,[1].concat(list.map(function(r){return r.salesUsd})));
 var h=(d.summary&&d.summary.noRegionClients?'<div class="ki-advice">ℹ️ '+d.summary.noRegionClients+' ta mijozda hudud kiritilmagan — ular «Belgilanmagan» qatorida.</div>':'');
 return h+list.map(function(r,i){var col=i===0?'#16b364':i===1?'#2a8bf2':i===2?'#8b5cf6':'#7c8db5';
  return '<div class="ki-row" style="--gc:'+col+';cursor:default"><div class="ki-n">'+r.rank+'</div><div><b>'+esc(r.name)+'</b>'+
   '<small>Faol '+r.activeClients+'/'+r.clients+' mijoz · o‘rtacha '+usd(r.avgPerActiveUsd)+' $ · qarz '+usd(r.debtUsd)+' $</small>'+
   '<div class="ki-bar"><u style="width:'+Math.max(3,r.salesUsd/mx*100)+'%"></u></div>'+
   '<div class="ki-badges">'+(r.best?'<span>🏆 '+r.best+'</span>':'')+(r.risky?'<span>🔴 '+r.risky+'</span>':'')+(r.sleeping?'<span>💤 '+r.sleeping+'</span>':'')+(r.prospects?'<span>🆕 '+r.prospects+' olmagan</span>':'')+'</div>'+
   (r.topClient?'<small>Eng yaxshi: '+esc(r.topClient.name)+' · '+usd(r.topClient.salesUsd)+' $</small>':'')+'</div>'+
   '<div class="ki-sc"><b>'+usd(r.salesUsd)+'$</b><small>'+r.sharePct+'% · '+growth(r.growthPct)+'</small></div></div>'}).join('');
}
function agentsHtml(d){
 var list=d.agents||[];if(!list.length)return '<div class="ki-empty">Agent ma’lumoti yo‘q.</div>';
 return list.map(function(a,i){var col=a.avgScore>=70?GC.best:a.avgScore>=45?GC.growing:GC.attention;
  return '<div class="ki-row" style="--gc:'+col+';cursor:default"><div class="ki-n">'+(i+1)+'</div><div><b>'+esc(a.agent)+'</b><small>Faol '+a.active+'/'+a.clients+' mijoz · sotuv '+usd(a.salesUsd)+' $ · qarz '+usd(a.debtUsd)+' $</small>'+
   '<div class="ki-badges"><span>🏆 '+a.best+'</span><span>📈 '+a.growing+'</span><span>✅ '+a.stable+'</span><span>⚠️ '+a.attention+'</span><span>🔴 '+a.risky+'</span><span>💤 '+a.sleeping+'</span></div></div>'+
   '<div class="ki-sc"><b>'+a.avgScore+'</b><small>o‘rtacha ball</small></div></div>'}).join('');
}
function openClient(id){
 var c=((st.data&&st.data.clients)||[]).find(function(x){return x.id===id});if(!c)return;
 var col=GC[c.group],p=c.parts||{};
 var part=function(lbl,v,max){return '<div><span>'+lbl+'</span><div class="ki-bar" style="margin:0;--gc:'+col+'"><u style="width:'+Math.max(2,v/max*100)+'%"></u></div><em>'+v+'/'+max+'</em></div>'};
 var body='<div class="ki-row" style="--gc:'+col+';cursor:default;border:0"><div class="ki-n">'+c.rank+'</div><div><b>'+esc(c.name)+'</b><small>'+esc(c.region)+' · '+esc(c.agent)+'</small></div><div class="ki-sc"><b>'+c.score+'</b><small>ball</small></div></div>'+
  '<div class="ki-advice"><b>'+c.groupIcon+' '+esc(c.groupLabel)+':</b> '+esc(c.advice)+'</div>'+
  '<div class="ki-parts">'+part('Sotuv hajmi',p.sales||0,40)+part('To‘lov',p.payment||0,30)+part('Muntazamlik',p.regular||0,15)+part('O‘sish',p.growth||0,15)+'</div>'+
  '<div class="ki-kpi"><div><small>Realizatsiya</small><b>'+usd(c.salesUsd)+' $</b></div><div><small>O‘tgan davr</small><b>'+usd(c.prevSalesUsd)+' $ '+growth(c.growthPct)+'</b></div><div><small>To‘lagan</small><b>'+usd(c.paidUsd)+' $</b></div><div><small>Qarz</small><b>'+usd(c.debtUsd)+' $</b>'+(c.debtDays?'<small>'+c.debtDays+' kun</small>':'')+'</div></div>'+
  '<small style="display:block;color:var(--mu);margin:4px 0 10px">'+esc((c.reasons||[]).join(' · '))+(c.daysSinceDelivery!=null?' · oxirgi tovar '+c.daysSinceDelivery+' kun oldin':'')+'</small>'+
  '<div class="pm-b p" data-ki-card="'+c.id+'">Mijoz kartasini ochish</div>';
 if(typeof window.pmSheet==='function')window.pmSheet('Mijoz reytingi',body,d_label());else fallbackSheet(body);
}
function d_label(){return st.data?st.data.label:''}
function fallbackSheet(body){var sh=$('sh'),ov=$('ov');if(!sh)return;sh.innerHTML='<div class="pm-grab"></div><div class="pm-h"><div><b>Mijoz reytingi</b><small>'+esc(d_label())+'</small></div><div class="pm-b" data-pm="close" style="padding:8px 12px">✕</div></div>'+body;sh.classList.add('on');if(ov)ov.classList.add('on');sh.scrollTop=0}

document.addEventListener('click',function(e){
 var t=e.target.closest('[data-ki-tab],[data-ki-per],[data-ki-group],[data-ki-more],[data-ki-client],[data-ki-card],[data-ki-go]');if(!t)return;
 if(t.dataset.kiTab){st.tab=t.dataset.kiTab;render();return}
 if(t.dataset.kiPer){st.period=t.dataset.kiPer;document.querySelectorAll('[data-ki-per]').forEach(function(b){b.classList.toggle('on',b===t)});$('ki-dates').classList.toggle('on',st.period==='custom');if(st.period!=='custom')load();return}
 if(t.dataset.kiGo){st.from=$('ki-from').value;st.to=$('ki-to').value;if(!st.from||!st.to){if(window.toast)window.toast('Sanalarni tanlang');return}load();return}
 if(t.dataset.kiGroup!==undefined&&t.hasAttribute('data-ki-group')){st.group=t.dataset.kiGroup;st.limit=25;render();return}
 if(t.dataset.kiMore){st.limit+=25;render();return}
 if(t.dataset.kiClient){openClient(Number(t.dataset.kiClient));return}
 if(t.dataset.kiCard){var id=Number(t.dataset.kiCard),i=((P.clients&&P.clients())||[]).findIndex(function(c){return Number(c.id)===id});var sh=$('sh'),ov=$('ov');if(sh)sh.classList.remove('on');if(ov)ov.classList.remove('on');if(i>=0&&typeof window.openC==='function')window.openC(i);return}
});
document.addEventListener('change',function(e){if(e.target&&e.target.id==='ki-agent'){st.agent=e.target.value;load()}});

P.onLoad(function(){if(ensure()){fillAgents();if(!st.data)load()}});
})();
