/* ASMAN — Hududlar, mijozlar va mahsulotlar hisoboti (Rahbar va Agent uchun umumiy UI).
 * Hisob serverda (analytics.py); bu yerda faqat ko'rsatish. Pul — butun sentda keladi.
 * AsmanInsights.mount(el,{mode:'manager'|'agent',req:fn(payload)->Promise,openClient:fn(id),agents:fn()->[{id,name}]})
 */
(function(){
'use strict';
function esc(v){return String(v==null?'':v).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]})}
function usd(c){if(c==null)return '—';var n=Number(c)/100;return n.toLocaleString('en-US',{minimumFractionDigits:Math.round(c)%100?2:0,maximumFractionDigits:2})+' $'}
function ago(ts,now){if(!ts)return 'sana yo‘q';var d=Math.floor((now-ts)/86400);return d<=0?'bugun':d+' kun oldin'}
var CSS='.ai{--c:var(--card,var(--tg-section,#fff));--t:var(--tx,var(--tg-text,#17212b));--m:var(--mu,var(--muted,#66727f));--l:var(--line,#e5ecf5);--s:var(--soft,#f3f5f9);--p:var(--pri,var(--blue,#2a8bf2));--ok:var(--ok,#1c9b43);--bad:var(--bad,#e5484d);--warn:var(--warn,#c77c00);background:var(--c);color:var(--t);border:1px solid var(--l);border-radius:20px;padding:14px;margin:0 0 14px}'+
'.ai b{font-weight:800}.ai small{color:var(--m)}.ai-h b{font-size:16px;display:block}.ai-h small{display:block;font-size:11.5px;margin-top:2px;line-height:1.4}'+
'.ai-row{display:flex;gap:6px;overflow-x:auto;padding:2px 0 4px;scrollbar-width:none}.ai-row::-webkit-scrollbar{display:none}'+
'.ai-row button{flex:none;border:1px solid var(--l);background:var(--s);color:var(--t);border-radius:14px;padding:7px 11px;font:inherit;font-size:12.5px;font-weight:700;min-height:34px;cursor:pointer}'+
'.ai-row button.on{background:var(--p);border-color:transparent;color:#fff}.ai-tabs{margin:10px 0 6px}'+
'.ai-dates{display:none;grid-template-columns:1fr 1fr auto;gap:6px;margin:6px 0}.ai-dates.on{display:grid}.ai-dates input{min-width:0;border:1px solid var(--l);background:var(--s);color:var(--t);border-radius:12px;padding:8px;font:inherit;font-size:12px}.ai-dates button{border:0;background:var(--p);color:#fff;border-radius:12px;padding:0 14px;font-weight:800}'+
'.ai select{border:1px solid var(--l);background:var(--s);color:var(--t);border-radius:14px;padding:7px 10px;font:inherit;font-size:12.5px;font-weight:700;max-width:100%}'+
'.ai-kpi{display:grid;grid-template-columns:1fr 1fr;gap:6px;margin:8px 0}.ai-kpi div{background:var(--s);border-radius:14px;padding:9px 10px;min-width:0}.ai-kpi small{display:block;font-size:11px}.ai-kpi b{display:block;font-size:16px;margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}'+
'.ai-note{background:var(--s);border-radius:12px;padding:8px 10px;font-size:12px;line-height:1.45;margin:6px 0}'+
'.ai-it{display:block;width:100%;text-align:left;background:none;border:0;border-top:1px solid var(--l);padding:10px 2px;color:inherit;font:inherit;cursor:pointer}.ai-it:first-child{border-top:0}'+
'.ai-top{display:flex;justify-content:space-between;gap:8px;align-items:baseline}.ai-top b{font-size:14px;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.ai-top span{flex:none;font-weight:800;font-size:13.5px}'+
'.ai-it small{display:block;font-size:11.5px;line-height:1.45;margin-top:2px}.ai-tags{display:flex;flex-wrap:wrap;gap:5px;margin-top:5px}'+
'.ai-tag{font-size:11px;font-weight:800;border-radius:9px;padding:2px 7px;background:var(--s);color:var(--t)}.ai-tag.ok{color:var(--ok)}.ai-tag.bad{color:var(--bad)}.ai-tag.warn{color:var(--warn)}.ai-tag.p{color:var(--p)}'+
'.ai-bar{height:6px;border-radius:5px;background:var(--s);overflow:hidden;margin-top:6px}.ai-bar i{display:block;height:100%;background:var(--p);border-radius:5px}'+
'.ai-sub{margin:4px 0 4px 10px;border-left:2px solid var(--l);padding-left:8px}.ai-more{width:100%;margin-top:8px;border:1px dashed var(--l);background:none;color:var(--p);border-radius:12px;padding:9px;font:inherit;font-weight:800;cursor:pointer}'+
'.ai-empty{text-align:center;color:var(--m);font-size:13px;padding:16px 6px}.ai details{margin-top:10px;font-size:12px;line-height:1.5}.ai summary{cursor:pointer;font-weight:800;color:var(--p)}.ai details p{margin:6px 0;color:var(--m)}'+
'.ai-sh{position:fixed;inset:0;z-index:9999;background:#0008;display:flex;align-items:flex-end}.ai-sh>div{background:var(--c);color:var(--t);width:100%;max-height:82vh;overflow:auto;border-radius:20px 20px 0 0;padding:16px 16px calc(16px + env(safe-area-inset-bottom))}'+
'.ai-sh dl{display:grid;grid-template-columns:1fr auto;gap:6px 10px;margin:10px 0;font-size:13px}.ai-sh dt{color:var(--m)}.ai-sh dd{margin:0;font-weight:800;text-align:right}.ai-btn{display:block;width:100%;border:0;border-radius:14px;padding:12px;font:inherit;font-weight:800;margin-top:8px;cursor:pointer;background:var(--p);color:#fff}.ai-btn.g{background:var(--s);color:var(--t)}';
function css(){if(document.getElementById('ai-css'))return;var s=document.createElement('style');s.id='ai-css';s.textContent=CSS;document.head.appendChild(s)}
var PAY={clear:['Qarzi yo‘q','ok'],advance:['Avans','p'],paying:['Qarz bor · to‘layapti','warn'],unpaid:['Qarz bor · davrda to‘lov yo‘q','bad']};
var FRESH={agreed_visit:'kelishuv',collection_task:'topshiriq',sales_drop:'oxirgi “Sotildi”'};
var FILTERS=[['all','Reyting'],['growing','📈 O‘sayotgan'],['attention','⚠️ E’tibor kerak'],['new','🆕 Yangi'],['debt','💳 Qarz bor'],['nodata','❔ “Sotildi” yo‘q'],['prospect','Istiqbolli']];

function mount(el,o){
 css();var mgr=o.mode==='manager';
 var st={period:'month',from:'',to:'',agent:'',tab:mgr?'regions':'today',filter:'all',limit:20,open:{},data:null,key:'',at:0,busy:false,err:''};
 el.classList.add('ai');
 function tabs(){var t=mgr?[['regions','Hududlar'],['clients','Mijozlar'],['products','Mahsulotlar'],['agents','Agentlar'],['today','🎯 Bugun']]:[['today','🎯 Bugun kimga'],['regions','Hududlar'],['clients','Mijozlar'],['products','Mahsulotlar']];
  return '<div class="ai-row ai-tabs">'+t.map(function(x){return '<button type="button" data-ai-tab="'+x[0]+'" class="'+(st.tab===x[0]?'on':'')+'">'+x[1]+'</button>'}).join('')+'</div>'}
 function periods(){var p=[['today','Bugun'],['week','Hafta'],['month','Oy'],['custom','Davr']];
  var h='<div class="ai-row">'+p.map(function(x){return '<button type="button" data-ai-per="'+x[0]+'" class="'+(st.period===x[0]?'on':'')+'">'+x[1]+'</button>'}).join('');
  if(mgr){var ags=(o.agents&&o.agents())||[];h+='<select data-ai-agent aria-label="Agent"><option value="">Barcha agentlar</option>'+ags.map(function(a){return '<option value="'+esc(a.id)+'"'+(String(a.id)===st.agent?' selected':'')+'>'+esc(a.name||a.id)+'</option>'}).join('')+'</select>'}
  return h+'</div><div class="ai-dates'+(st.period==='custom'?' on':'')+'"><input type="date" data-ai-from value="'+esc(st.from)+'"><input type="date" data-ai-to value="'+esc(st.to)+'"><button type="button" data-ai-go>OK</button></div>'}
 function load(force){
  var key=st.period+'|'+st.from+'|'+st.to+'|'+st.agent;
  if(!force&&st.key===key&&Date.now()-st.at<120000){paint();return}
  if(st.period==='custom'&&(!st.from||!st.to)){st.err='Boshlanish va tugash sanasini tanlang.';st.data=null;paint();return}
  st.busy=true;st.err='';paint();var p={period:st.period};if(st.period==='custom'){p.from=st.from;p.to=st.to}if(mgr&&st.agent)p.agentId=st.agent;
  o.req(p).then(function(d){if(key!==st.period+'|'+st.from+'|'+st.to+'|'+st.agent)return;st.data=d;st.key=key;st.at=Date.now();st.busy=false;paint()},
   function(e){st.busy=false;st.err=(e&&e.message)||'Hisobot yuklanmadi.';paint()});
 }
 function payTag(p){var x=PAY[p.code]||['',''];var t=p.code==='advance'?'Avans '+usd(-p.debtEndCents):p.code==='clear'?x[0]:'Qarz '+usd(p.debtEndCents);
  return '<span class="ai-tag '+x[1]+'">'+esc(t)+'</span>'+(p.oldestOpenDays!=null?'<span class="ai-tag">eng eski yuk '+p.oldestOpenDays+' kun</span>':'')}
 function growthTag(g){if(!g)return '';var cls=g.kind==='pct'?(g.pct>=0?'ok':'bad'):g.kind==='started'?'ok':g.kind==='new'?'p':'';return '<span class="ai-tag '+cls+'">'+esc(g.text)+'</span>'}
 function clientRow(c,n){var real=c.realizationCents==null?'<small>“Sotildi” yo‘q</small>':usd(c.realizationCents);
  return '<button type="button" class="ai-it" data-ai-client="'+c.id+'"><div class="ai-top"><b>'+(n?n+'. ':'')+esc(c.name)+'</b><span>'+real+'</span></div>'+
   '<small>'+esc(c.region)+(mgr?' · '+esc(c.agent):'')+(c.prospect?' · istiqbolli':' · berilgan '+usd(c.deliveredCents)+(c.payment.paidCents?' · to‘lov '+usd(c.payment.paidCents):''))+'</small>'+
   (c.prospect?'':'<div class="ai-tags">'+growthTag(c.growth)+payTag(c.payment)+(c.realizationPartial?'<span class="ai-tag warn">narxsiz sotuv bor</span>':'')+'</div>')+
   (c.attention&&c.attention.length?'<small>⚠️ '+esc(c.attention.join(' · '))+'</small>':'')+'</button>'}
 function kpis(d){var s=d.summary;return '<div class="ai-kpi"><div><small>Realizatsiya (sotilgan)</small><b>'+(s.realizationCents==null?'Ma’lumot yo‘q':usd(s.realizationCents))+'</b></div><div><small>Berilgan tovar</small><b>'+usd(s.deliveredCents)+'</b></div>'+
  '<div><small>Olingan to‘lov</small><b>'+usd(s.paidCents)+'</b></div><div><small>Davr oxiridagi qarz</small><b>'+usd(s.debtEndCents)+'</b>'+(s.advanceCents?'<small>avans '+usd(s.advanceCents)+'</small>':'')+'</div></div>'+
  '<small style="display:block;font-size:11.5px">Faol '+s.activeClients+' / '+s.ratedClients+' mijoz · yangi '+s.newClients+' · istiqbolli '+s.prospects+(d.complete?'':' · hozirgi qarz '+usd(s.debtNowCents))+'</small>'}
 function regions(d){var list=d.regions||[];if(!list.length)return '<div class="ai-empty">Hudud ma’lumoti yo‘q.</div>';
  var mx=Math.max.apply(null,[1].concat(list.map(function(r){return r.realizationCents||0})));
  return list.map(function(r){var open=st.open[r.key];var members=(d.clients||[]).filter(function(c){return r.clientIds.indexOf(c.id)>=0});
   return '<div><button type="button" class="ai-it" data-ai-region="'+esc(r.key)+'"><div class="ai-top"><b>'+(open?'▾ ':'▸ ')+esc(r.name)+'</b><span>'+(r.realizationCents==null?'<small>“Sotildi” yo‘q</small>':usd(r.realizationCents))+'</span></div>'+
    '<div class="ai-bar"><i style="width:'+Math.max(2,(r.realizationCents||0)/mx*100)+'%"></i></div>'+
    '<small>Berilgan '+usd(r.deliveredCents)+' · to‘lov '+usd(r.paidCents)+' · davr oxiri qarz '+usd(r.debtEndCents)+'</small>'+
    '<small>Faol '+r.activeClients+' · yangi '+r.newClients+' · istiqbolli '+r.prospects+' · jami '+r.clients+(r.realizationPerActiveCents!=null?' · 1 faolga '+usd(r.realizationPerActiveCents):'')+'</small>'+
    '<div class="ai-tags">'+growthTag(r.growth)+(r.sharePct?'<span class="ai-tag">'+r.sharePct+'% ulush</span>':'')+'</div></button>'+
    (open?'<div class="ai-sub">'+members.map(function(c){return clientRow(c,c.rank)}).join('')+'</div>':'')+'</div>'}).join('')}
 function clients(d){var all=d.clients||[];var f=st.filter;
  var list=all.filter(function(c){return f==='all'?!c.prospect:f==='prospect'?c.prospect:f==='debt'?(!c.prospect&&c.payment.debtEndCents>0):f==='nodata'?c.tags.indexOf('noSalesData')>=0:c.tags.indexOf(f)>=0});
  if(f==='debt')list.sort(function(a,b){return b.payment.debtEndCents-a.payment.debtEndCents});
  var h='<div class="ai-row">'+FILTERS.map(function(x){var n=all.filter(function(c){return x[0]==='all'?!c.prospect:x[0]==='prospect'?c.prospect:x[0]==='debt'?(!c.prospect&&c.payment.debtEndCents>0):x[0]==='nodata'?c.tags.indexOf('noSalesData')>=0:c.tags.indexOf(x[0])>=0}).length;
   return '<button type="button" data-ai-filter="'+x[0]+'" class="'+(f===x[0]?'on':'')+'">'+x[1]+' '+n+'</button>'}).join('')+'</div>';
  if(f==='new')h+='<div class="ai-note">Yangi mijozlar eski mijozlar bilan taqqoslanmaydi.</div>';
  if(f==='attention')h+='<div class="ai-note">Realizatsiya o‘tgan teng davrga nisbatan '+Math.abs(d.rules.declinePct)+'%+ tushgan yoki bu davrda “Sotildi” yozilmagan.</div>';
  if(!list.length)return h+'<div class="ai-empty">Bu ro‘yxatda mijoz yo‘q.</div>';
  h+=list.slice(0,st.limit).map(function(c){return clientRow(c,f==='all'?c.rank:null)}).join('');
  if(list.length>st.limit)h+='<button type="button" class="ai-more" data-ai-more>Yana ko‘rsatish ('+(list.length-st.limit)+')</button>';
  return h}
 function products(d){var list=d.products||[];if(!list.length)return '<div class="ai-empty">Bu davrda mahsulot harakati yo‘q.</div>';
  return list.map(function(p){return '<div class="ai-it" style="cursor:default"><div class="ai-top"><b>'+esc(p.name)+'</b><span>'+(p.realizationCents==null?'<small>“Sotildi” yo‘q</small>':usd(p.realizationCents))+'</span></div>'+
   '<small>Sotilgan '+p.soldQty+' dona · berilgan '+p.deliveredQty+' dona ('+usd(p.deliveredCents)+') · qaytgan '+p.returnedQty+' dona ('+usd(p.returnedCents)+')</small></div>'}).join('')}
 function agents(d){var list=d.agents||[];if(!list.length)return '<div class="ai-empty">Agent ma’lumoti yo‘q.</div>';
  return '<div class="ai-note">Operatsiyalar — agent o‘zi bajargan amallar. Portfel — hozir unga biriktirilgan mijozlar (o‘tkazilgan mijoz tarixi bilan).</div>'+list.map(function(a){var op=a.operations;
   return '<div class="ai-it" style="cursor:default"><div class="ai-top"><b>'+esc(a.agent)+'</b><span>'+usd(op.realizationCents)+'</span></div>'+
    '<small>Operatsiyalar: sotildi '+usd(op.realizationCents)+' · berdi '+usd(op.deliveredCents)+' · to‘lov oldi '+usd(op.paidCents)+'</small>'+
    '<small>Portfel: '+a.clients+' mijoz · faol '+a.activeClients+' · yangi '+a.newClients+' · istiqbolli '+a.prospects+' · qarz '+usd(a.debtEndCents)+'</small>'+
    '<div class="ai-tags"><span class="ai-tag ok">📈 '+a.growing+'</span><span class="ai-tag bad">⚠️ '+a.attention+'</span></div></div>'}).join('')}
 function today(d){var t=d.today;if(!t)return '<div class="ai-empty">Ma’lumot yo‘q.</div>';
  var h='<div class="ai-note">'+esc(t.note)+'</div>';if(!t.items.length)return h+'<div class="ai-empty">✅ Bugun shoshilinch ish yo‘q.</div>';
  return h+t.items.map(function(i){return '<button type="button" class="ai-it" data-ai-open="'+i.clientId+'"><div class="ai-top"><b>'+esc(i.name)+'</b><span>'+(i.debtNowCents>0?'<small>qarz</small> '+usd(i.debtNowCents):'')+'</span></div>'+
   '<small>'+esc(i.region)+(mgr?' · '+esc(i.agent):'')+' · oxirgi aloqa: '+(i.lastContactTs?ago(i.lastContactTs,t.asOf):'yozilmagan')+'</small>'+i.reasons.map(function(r){var f=FRESH[r.code]&&r.since?' <span style="opacity:.75">('+FRESH[r.code]+' '+ago(r.since,t.asOf)+')</span>':'';return '<small>• '+esc(r.text)+f+'</small>'}).join('')+
   '<div class="ai-tags"><span class="ai-tag p">👉 '+esc(i.action)+'</span><span class="ai-tag">Kartani ochish →</span></div></button>'}).join('')+(t.total>t.items.length?'<small style="display:block;margin-top:6px">Yana '+(t.total-t.items.length)+' ta mijoz bor.</small>':'')}
 function help(d){return '<details><summary>Hisob qanday qilinadi?</summary><p><b>Realizatsiya</b> — “Sotildi” yozuvlari, tovar partiya narxida. Yozuv bo‘lmasa “ma’lumot yo‘q”, 0 emas.</p><p><b>Berilgan tovar</b> — mijozga berilgan tovar qiymati. <b>Qaytgan</b> — sotilmagan tovar, qarzni kamaytiradi.</p><p><b>Davr oxiridagi qarz</b> = berilgan − to‘lov − qaytgan (davr oxirigacha). Keyingi to‘lovlar eski davrga ta’sir qilmaydi.</p><p><b>Eng eski yuk</b> — to‘lovlar eski yuklarni yopadi deb (FIFO) hisoblangan taxmin; to‘lov muddati yozilmagani uchun “muddati o‘tgan” deyilmaydi.</p><p><b>O‘sish</b> — '+esc(d.compareLabel)+'.'+(d.equalCompare?'':' Diqqat: oldingi davr qisqaroq.')+'</p>'+
  (d.quality.legacyUzsEvents?'<p>Eski so‘mdagi '+d.quality.legacyUzsEvents+' ta yozuv USD hisobga kirmagan.</p>':'')+'</details>'}
 function paint(){var d=st.data;
  var h='<div class="ai-h"><b>'+(mgr?'📊 Hududlar va mijozlar':'Hudud va mijozlar tahlili')+'</b><small>'+(st.tab==='today'?'Joriy holat — davr filtriga bog‘liq emas':d?esc(d.label)+'<br>Taqqoslash: '+esc(d.compareLabel):'Bugun · Hafta · Oy · Davr')+'</small></div>'+tabs();
  if(st.tab!=='today')h+=periods();
  if(st.err){h+='<div class="ai-empty">'+esc(st.err)+'<br><button type="button" class="ai-more" data-ai-retry>↻ Qayta urinish</button></div>';el.innerHTML=h;return}
  if(!d){h+='<div class="ai-empty">Yuklanmoqda…</div>';el.innerHTML=h;return}
  if(st.tab==='today'){h+=today(d);el.innerHTML=h;return}
  h+=kpis(d);var q=d.quality;
  if(q.noSalesDataClients||d.summary.realizationCents==null)h+='<div class="ai-note">ℹ️ '+q.noSalesDataClients+' ta mijozda qoldiq bor, lekin “Sotildi” hech yozilmagan — realizatsiya to‘liq emas.</div>';
  if(q.noRegionClients&&st.tab==='regions')h+='<div class="ai-note">ℹ️ '+q.noRegionClients+' ta mijozda hudud yozilmagan — “Belgilanmagan”da.</div>';
  h+=st.tab==='regions'?regions(d):st.tab==='clients'?clients(d):st.tab==='products'?products(d):agents(d);
  el.innerHTML=h+help(d)}
 function sheet(c){var d=st.data,p=c.payment;var w=document.createElement('div');w.className='ai ai-sh';w.style.cssText='border:0;padding:0;margin:0;border-radius:0;background:#0008';
  w.innerHTML='<div><b style="font-size:17px">'+esc(c.name)+'</b><small style="display:block">'+esc(c.region)+' · '+esc(c.agent)+(c.person&&c.person!==c.name?' · '+esc(c.person):'')+'</small>'+
   '<div class="ai-tags">'+growthTag(c.growth)+payTag(p)+'</div><dl>'+
   '<dt>Realizatsiya (sotilgan)</dt><dd>'+(c.realizationCents==null?'ma’lumot yo‘q':usd(c.realizationCents)+' · '+c.soldQty+' dona')+'</dd>'+
   '<dt>Oldingi teng davr</dt><dd>'+(c.prevRealizationCents==null?'ma’lumot yo‘q':usd(c.prevRealizationCents))+'</dd>'+
   '<dt>Berilgan tovar</dt><dd>'+usd(c.deliveredCents)+' · '+c.deliveredQty+' dona</dd><dt>Qaytgan (sotilmagan)</dt><dd>'+usd(c.returnedCents)+'</dd>'+
   '<dt>Davrda to‘lov</dt><dd>'+usd(p.paidCents)+'</dd><dt>Davr oxiridagi qarz</dt><dd>'+usd(p.debtEndCents)+'</dd><dt>Hozirgi qarz</dt><dd>'+usd(c.debtNowCents)+'</dd>'+
   '<dt>Oxirgi to‘lovdan beri</dt><dd>'+(p.lastPaymentDays==null?'to‘lov yo‘q':p.lastPaymentDays+' kun')+'</dd><dt>Eng eski to‘lanmagan yuk (FIFO)</dt><dd>'+(p.oldestOpenDays==null?'—':p.oldestOpenDays+' kun oldin')+'</dd>'+
   '<dt>Mijozdagi qoldiq</dt><dd>'+c.stockQty+' dona · '+usd(c.stockValueCents)+'</dd><dt>Oxirgi “Sotildi”</dt><dd>'+(c.lastSoldDays==null?'yozilmagan':c.lastSoldDays+' kun oldin')+'</dd></dl>'+
   (c.attention&&c.attention.length?'<div class="ai-note">⚠️ '+esc(c.attention.join(' · '))+'</div>':'')+
   '<small style="display:block">'+esc(d.label)+'</small><button type="button" class="ai-btn" data-ai-open="'+c.id+'">Mijoz kartasini ochish</button><button type="button" class="ai-btn g" data-ai-close>Yopish</button></div>';
  document.body.appendChild(w);
  w.addEventListener('click',function(e){var t=e.target;if(t===w||t.closest('[data-ai-close]')){w.remove();return}var b=t.closest('[data-ai-open]');if(b){w.remove();o.openClient(Number(b.dataset.aiOpen))}})}
 el.addEventListener('click',function(e){var t=e.target.closest('button');if(!t||!el.contains(t))return;var ds=t.dataset,hit=true;
  if(ds.aiTab){st.tab=ds.aiTab;paint();if(!st.data)load()}
  else if(ds.aiPer){st.period=ds.aiPer;st.limit=20;if(st.period==='custom')paint();else load()}
  else if(ds.aiGo!==undefined){st.from=(el.querySelector('[data-ai-from]')||{}).value||'';st.to=(el.querySelector('[data-ai-to]')||{}).value||'';load(true)}
  else if(ds.aiFilter){st.filter=ds.aiFilter;st.limit=20;paint()}
  else if(ds.aiMore!==undefined){st.limit+=20;paint()}
  else if(ds.aiRegion!==undefined){st.open[ds.aiRegion]=!st.open[ds.aiRegion];paint()}
  else if(ds.aiClient){var c=(st.data.clients||[]).filter(function(x){return x.id===Number(ds.aiClient)})[0];if(c)sheet(c)}
  else if(ds.aiOpen){o.openClient(Number(ds.aiOpen))}
  else if(ds.aiRetry!==undefined){load(true)}
  else hit=false;
  if(hit)e.stopPropagation()});
 el.addEventListener('change',function(e){if(e.target.matches('[data-ai-agent]')){st.agent=e.target.value;load()}});
 return {show:function(){if(!st.data&&!st.busy)load();else load(false)},reset:function(){st.data=null;st.key='';st.err='';paint();load(true)},state:st};
}
window.AsmanInsights={mount:mount,usd:usd};
})();
