/* ASMAN Rahbar Premium — Hisobot bo'limiga "Hududlar va mijozlar" kartasi.
 * UI: /app/premium-kit/insights-ui.js, hisob: /api/manager "insights" (analytics.py).
 */
(function(){
'use strict';
var P=window.PremiumReal;if(!P)return;
var view=null;
// Hisobot bo'limida bitta umumiy davr: tepadagi Bugun / 7 kun / Shu oy / Davr tanlovi.
function segPeriod(){var on=document.querySelector('#rseg button.on'),bs=Array.prototype.slice.call(document.querySelectorAll('#rseg button'));
 return ['today','week','month','custom'][bs.indexOf(on)]||'week'}
window.pmInsightsPeriod=function(p,f,t){if(view)view.setPeriod(p,f,t)};
function card(){
 var sec=document.querySelectorAll('section')[4],bd=sec&&sec.querySelector('.bd');if(!bd||!window.AsmanInsights)return null;
 var el=document.getElementById('ki-card');
 if(!el){el=document.createElement('div');el.id='ki-card';bd.insertBefore(el,bd.firstChild)}
 if(!view)view=window.AsmanInsights.mount(el,{mode:'manager',externalPeriod:true,period:segPeriod(),
  req:function(p){return P.req('insights',p)},
  agents:function(){return (P.agents&&P.agents())||[]},
  openClient:function(id){var list=(P.clients&&P.clients())||[],i=list.findIndex(function(c){return Number(c.id)===Number(id)});
   if(i>=0&&typeof window.openC==='function')window.openC(i);else if(window.toast)window.toast('Mijoz kartasi ro‘yxatda topilmadi')}});
 return el;
}
P.onLoad(function(){if(card()){var p=segPeriod();if(p==='custom'){var f=document.getElementById('rFrom'),t=document.getElementById('rTo');view.setPeriod('custom',f&&f.value,t&&t.value)}else view.setPeriod(p);view.show()}});
})();
