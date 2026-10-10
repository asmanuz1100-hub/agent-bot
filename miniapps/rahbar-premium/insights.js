/* ASMAN Rahbar Premium — Hisobot bo'limiga "Hududlar va mijozlar" kartasi.
 * UI: /app/premium-kit/insights-ui.js, hisob: /api/manager "insights" (analytics.py).
 */
(function(){
'use strict';
var P=window.PremiumReal;if(!P)return;
var view=null;
function card(){
 var sec=document.querySelectorAll('section')[4],bd=sec&&sec.querySelector('.bd');if(!bd||!window.AsmanInsights)return null;
 var el=document.getElementById('ki-card');
 if(!el){el=document.createElement('div');el.id='ki-card';bd.insertBefore(el,bd.firstChild)}
 if(!view)view=window.AsmanInsights.mount(el,{mode:'manager',
  req:function(p){return P.req('insights',p)},
  agents:function(){return (P.agents&&P.agents())||[]},
  openClient:function(id){var list=(P.clients&&P.clients())||[],i=list.findIndex(function(c){return Number(c.id)===Number(id)});
   if(i>=0&&typeof window.openC==='function')window.openC(i);else if(window.toast)window.toast('Mijoz kartasi ro‘yxatda topilmadi')}});
 return el;
}
P.onLoad(function(){if(card())view.show()});
})();
