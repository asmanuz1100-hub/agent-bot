/* AIBI ilovasi: agent smenasi tugmasi (Ishni boshlash/tugatish) + GPS ilovaga signal. Faqat /app/aibi-agent/ da. */
(function(){
if(window.__aibiShift)return;window.__aibiShift=true;
function post(m){try{window.ReactNativeWebView.postMessage(JSON.stringify(m))}catch(e){}}
var busy=false,last=null;
// O'zgarmagan qiymatni qayta yozmaymiz — aks holda MutationObserver cheksiz aylanadi.
function set(el,k,v){if(el[k]!==v)el[k]=v}
function isOpen(){var s=document.getElementById('shiftStatus');return !!s&&/Ishda/.test(s.textContent)}
function known(){var s=document.getElementById('shiftStatus');return !!s&&/Ishda|Yopiq/.test(s.textContent)}
function paint(){
 var hint=document.getElementById('shiftHint');if(!hint)return;
 // Rahbar agentni ko'rib turibdi (admin to'liq rejim): smena va GPS agentning o'zi uchun — tugma yo'q.
 if(document.body&&document.body.classList.contains('admin-full')){var x=document.getElementById('aibiShiftBtn');if(x)x.remove();return}
 var b=document.getElementById('aibiShiftBtn');
 if(!b){b=document.createElement('button');b.type='button';b.id='aibiShiftBtn';
  b.style.cssText='width:100%;margin-top:10px;padding:14px;border:0;border-radius:14px;font:inherit;font-weight:800;font-size:15px;color:#fff;cursor:pointer';
  b.onclick=toggle;hint.parentNode.insertBefore(b,hint.nextSibling);
  var tiny=hint.parentNode.querySelector('.tiny');if(tiny)tiny.textContent='Smena davomida GPS ilovadan avtomatik yuboriladi (ilova yopiq bo‘lsa ham). «Ishni tugatish» bosilganda to‘xtaydi.'}
 var open=isOpen();
 if(known()&&open!==last){last=open;post({t:'shift',open:open})}
 if(known()&&!busy)set(hint,'textContent',open?'Ish kuni davom etmoqda — GPS ilovadan yuborilmoqda.':'«Ishni boshlash» tugmasini bosing.');
 set(b,'disabled',busy||!known());set(b.style,'opacity',b.disabled?'0.6':'1');
 set(b.style,'background',open?'#e5484d':'linear-gradient(135deg,#2f80ff,#1d5fe0)');
 set(b,'textContent',busy?'Kuting…':open?'Ishni tugatish':'Ishni boshlash');
}
// Darhol javob: holatni ekranda o'zgartiramiz, so'rov orqada ketadi; xato bo'lsa qaytaramiz.
function toast(t){var d=document.createElement('div');d.textContent=t;
 d.style.cssText='position:fixed;left:50%;bottom:96px;transform:translateX(-50%);background:#0f172a;color:#fff;padding:12px 18px;border-radius:14px;font:600 14px Manrope,system-ui;z-index:99999;box-shadow:0 8px 24px #0004;max-width:88%;text-align:center';
 document.body.appendChild(d);setTimeout(function(){d.remove()},2600)}
function showState(open){
 var t=function(id,v){var e=document.getElementById(id);if(e)e.textContent=v},c=function(id){var e=document.getElementById(id);if(e)e.className='pill '+(open?'green':'')};
 t('shiftStatus',open?'Ishda':'Yopiq');c('shiftStatus');t('homeCommandStatus',open?'Ishda':'Yopiq');c('homeCommandStatus');
 t('shiftLabel',open?'Ish kuni boshlandi':'Ish kuni yopiq');t('homeCommandTitle',open?'Ish kuni davom etmoqda':'Ish kunini boshlang')}
async function toggle(){
 if(busy||!known())return;var open=isOpen();
 if(open&&!confirm('Ish kunini tugatasizmi? GPS yuborish to‘xtaydi.'))return;
 busy=true;showState(!open);last=!open;post({t:'shift',open:!open});paint();
 try{
  var r=await fetch('/api/agent',{method:'POST',headers:{'Content-Type':'application/json'},
   body:JSON.stringify({initData:"aibi-app-session",action:open?'shift_end':'shift_start',requestId:'sh_'+Date.now()+'_'+Math.random().toString(36).slice(2,8)})});
  var d=await r.json().catch(function(){return {}});
  if(!r.ok&&!/allaqachon/.test(d.error||''))throw new Error(d.error||'Saqlanmadi.');
  toast(open?'Ish tugadi. GPS to‘xtatildi.':'Ish boshlandi. GPS yoqildi.');
 }catch(e){showState(open);last=open;post({t:'shift',open:open});toast(e.message||'Saqlanmadi.')}
 finally{busy=false;paint()}
}
// O'z yozuvlarimiz kuzatuvchini qayta qo'zg'atmasin: yozish paytida uzamiz va chaqiruvlarni jamlaymiz.
var obs,pending=0,opts={subtree:true,childList:true,characterData:true};
function run(){pending=0;obs.disconnect();try{paint()}finally{obs.observe(document.documentElement,opts)}}
obs=new MutationObserver(function(){if(!pending)pending=setTimeout(run,150)});
obs.observe(document.documentElement,opts);
document.addEventListener('DOMContentLoaded',run);
})();
