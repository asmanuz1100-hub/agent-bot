/* AIBI ovozli yordamchi (Rahbar ilovasi).
   - Sarlavhadagi «AIBI» tugmasi suhbat oynasini ochadi: savol yoziladi yoki 🎤 bilan aytiladi.
   - AIBI ilovasi (Android) «AIBI» so'zini eshitganda window.AIBIAssistant.wake() ni chaqiradi:
     oyna ochiladi, «Labbay» deyiladi, ilova savolni tinglab heard(matn) bilan qaytaradi.
   - Javob serverdan (ai_ask) keladi va ovozda o'qiladi: Azure o'zbekcha ovozi (ai_speak), u bo'lmasa —
     telefonning o'z ovozi ({t:'tts'}), brauzerda — speechSynthesis.
   Ilovaga xabarlar: {t:'listen'} — savolni tingla, {t:'voice',busy} — so'z kutishni to'xtat/davom et,
   {t:'tts',text} — telefon ovozida o'qi. */
(function () {
  if (window.AIBIAssistant) return;
  var D = document, history = [], busy = false, audio = null, labbayAudio = null;
  var native = !!window.ReactNativeWebView;
  function post(m) { try { window.ReactNativeWebView.postMessage(JSON.stringify(m)); } catch (e) {} }
  function req(action, payload) {
    if (window.PremiumReal && window.PremiumReal.req) return window.PremiumReal.req(action, payload);
    return Promise.reject(new Error('Yordamchi hali tayyor emas.'));
  }
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }

  var css = D.createElement('style');
  // To'liq ekranli ovoz rejimi (ChatGPT ovoz rejimi kabi): doim qorong'i sahna, markazda zarrachali shar.
  css.textContent =
    '#aiBtn{font-weight:800;font-size:11px;letter-spacing:.04em;width:auto!important;padding:0 10px 0 5px;border-radius:20px!important;display:inline-flex!important;align-items:center;gap:3px}' +
    '#aiBtn.on{background:var(--aibi-aurora,linear-gradient(135deg,#3882F6,#6366F1))!important;color:#fff!important}' +
    '#aiBtnOrb{width:28px;height:28px;display:block;border-radius:50%;background:radial-gradient(circle,#1a1c3d,#07080f)}' +
    '@media(max-width:420px){#aiBtn .t{display:none}#aiBtn{padding:0!important;width:40px!important;justify-content:center}}' +
    '#aiSh{--a-tx:#eef0fb;--a-mu:#8d92b3;--a-line:#232638;--a-soft:#151726;--a-pri:#6366F1;--a-pri2:#8B5CF6;' +
    'position:fixed;inset:0;z-index:40;display:flex;flex-direction:column;color:var(--a-tx);font-family:inherit;' +
    'background:radial-gradient(120% 70% at 50% 34%,#16183a 0%,#0a0b16 55%,#05060c 100%);' +
    'padding:calc(12px + env(safe-area-inset-top,0px)) max(16px,env(safe-area-inset-right,0px)) calc(18px + env(safe-area-inset-bottom,0px)) max(16px,env(safe-area-inset-left,0px));' +
    'transform:translateY(102%);transition:transform .42s cubic-bezier(.2,.9,.25,1);visibility:hidden}' +
    '#aiSh.on{transform:none;visibility:visible}#aiOv{display:none}' +
    '#aiTop{display:flex;align-items:center;justify-content:space-between;gap:10px;min-height:44px}' +
    '#aiTop b{font-weight:800;font-size:16px;letter-spacing:.02em}#aiTop small{display:block;color:var(--a-mu);font-size:11px;font-weight:600}' +
    '.aiIc{width:44px;height:44px;border-radius:50%;border:1px solid var(--a-line);background:#ffffff0d;color:var(--a-tx);display:grid;place-items:center;font-size:18px;cursor:pointer;flex:0 0 auto}' +
    '.aiIc:focus-visible,#aiMic:focus-visible{outline:2px solid var(--a-pri);outline-offset:2px}.aiIc.on{background:#6366F133;border-color:#6366F1}' +
    '#aiOrbBox{position:relative;flex:1 1 0;min-height:210px}#aiOrb{position:absolute;inset:0;width:100%;height:100%}' +
    '#aiSt{position:absolute;left:0;right:0;bottom:4px;display:flex;justify-content:center}' +
    '#aiSt span{display:inline-flex;align-items:center;gap:7px;padding:7px 13px;border-radius:999px;border:1px solid var(--a-line);background:#0e0f19cc;color:var(--a-mu);font-size:12px;font-weight:700}' +
    '#aiSt i{width:6px;height:6px;border-radius:50%;background:#2a2d3c;transition:background .3s}#aiSt i.on{background:var(--a-pri)}' +
    '#aiCap{flex:0 1 auto;max-height:30vh;overflow:auto;text-align:center;padding:14px 6px 4px;scrollbar-width:none}' +
    '#aiCapQ{color:var(--a-mu);font-size:14px;font-weight:600;margin:0 auto 8px;max-width:34ch;min-height:1em}' +
    '#aiCapA{font-size:19px;font-weight:700;line-height:1.42;margin:0 auto;max-width:30ch;white-space:pre-wrap;overflow-wrap:anywhere;text-wrap:pretty}' +
    '#aiCapA.e{color:#ff7a8a}#aiCapA.hint{color:var(--a-mu);font-weight:600;font-size:16px}' +
    '#aiLog{display:none;flex:1 1 auto;overflow:auto;flex-direction:column;gap:8px;padding:8px 2px}#aiSh.hist #aiLog{display:flex}#aiSh.hist #aiOrbBox,#aiSh.hist #aiCap{display:none}' +
    '.aiM{max-width:86%;padding:10px 13px;border-radius:16px;font-size:14px;line-height:1.45;white-space:pre-wrap;overflow-wrap:anywhere}' +
    '.aiM.u{align-self:flex-end;background:linear-gradient(135deg,var(--a-pri),var(--a-pri2));color:#fff;border-bottom-right-radius:6px}' +
    '.aiM.a{align-self:flex-start;background:var(--a-soft);color:var(--a-tx);border:1px solid var(--a-line);border-bottom-left-radius:6px}.aiM.e{color:#ff7a8a}' +
    '.aiDots i{display:inline-block;width:7px;height:7px;border-radius:50%;background:var(--a-mu);margin:0 3px;animation:aiB 1s infinite}' +
    '.aiDots i:nth-child(2){animation-delay:.15s}.aiDots i:nth-child(3){animation-delay:.3s}@keyframes aiB{0%,80%,100%{opacity:.25}40%{opacity:1}}' +
    '#aiF{display:none;gap:8px;margin-top:12px}#aiSh.kb #aiF{display:flex}' +
    '#aiQ{flex:1;min-width:0;border:1px solid var(--a-line);background:var(--a-soft);color:var(--a-tx);border-radius:16px;padding:13px 14px;font:inherit;font-size:15px}' +
    '#aiQ::placeholder{color:var(--a-mu)}#aiF .go{border:0;border-radius:16px;min-width:50px;font-size:18px;background:linear-gradient(135deg,var(--a-pri),var(--a-pri2));color:#fff;cursor:pointer}' +
    '#aiCtl{display:flex;align-items:center;justify-content:center;gap:26px;margin-top:14px}' +
    '#aiMic{width:74px;height:74px;border-radius:50%;border:0;cursor:pointer;color:#fff;font-size:26px;' +
    'background:linear-gradient(140deg,#3882F6,#6366F1 55%,#8B5CF6);box-shadow:0 14px 30px -12px #6366F1cc,inset 0 1px 0 #ffffff40}' +
    '#aiMic.rec{background:linear-gradient(140deg,#ff4f7a,#e5469a);animation:aiP 1.2s infinite}@keyframes aiP{50%{box-shadow:0 0 0 12px #e5469a2e}}' +
    '.aiHint{color:var(--a-mu);font-size:12px;text-align:center;margin:10px 0 0}' +
    '@media (prefers-reduced-motion:reduce){#aiSh{transition:none}#aiMic.rec{animation:none}}';
  D.head.appendChild(css);

  var ov = D.createElement('div'); ov.id = 'aiOv';
  var sh = D.createElement('div'); sh.id = 'aiSh'; sh.setAttribute('role', 'dialog'); sh.setAttribute('aria-label', 'AIBI yordamchi');
  if (!native) sh.classList.add('kb');
  sh.innerHTML = '<div id="aiTop"><div><b>AIBI</b><small>Savdo, qarz, kassa, agentlar, ombor</small></div>' +
    '<button type="button" class="aiIc" id="aiX" aria-label="Yopish">✕</button></div>' +
    '<div id="aiOrbBox"><canvas id="aiOrb" aria-hidden="true"></canvas>' +
    '<div id="aiSt"><span><i></i><i></i><i></i><i></i><i></i><b id="aiStL">Kutish</b></span></div></div>' +
    '<div id="aiCap" aria-live="polite"><p id="aiCapQ"></p><p id="aiCapA" class="hint">' +
    (native ? '«AIBI» deb chaqiring yoki 🎤 ni bosing' : 'Savolingizni yozing') + '</p></div>' +
    '<div id="aiLog"></div>' +
    '<form id="aiF"><input id="aiQ" placeholder="Masalan: bugun qancha sotildi?" maxlength="600" autocomplete="off">' +
    '<button type="submit" class="go" aria-label="Yuborish">➤</button></form>' +
    '<div id="aiCtl">' + (native ? '<button type="button" class="aiIc" id="aiKb" aria-label="Yozib so‘rash">⌨️</button>' +
    '<button type="button" id="aiMic" aria-label="Ovoz bilan so‘rash">🎤</button>' : '') +
    '<button type="button" class="aiIc" id="aiHist" aria-label="Suhbat tarixi">🕘</button></div>';
  function mount() { D.body.append(ov, sh); }
  if (D.body) mount(); else D.addEventListener('DOMContentLoaded', mount);
  var log = sh.querySelector('#aiLog'), q = sh.querySelector('#aiQ');

  /* ---- Zarrachali shar: Fibonachchi sfera nuqtalari; «o'ylash»da halqaga yoyiladi, ovozga qarab tebranadi. ---- */
  var ORB = ['idle', 'wake', 'listen', 'think', 'speak'], ORBL = { idle: 'Kutish', wake: 'Labbay', listen: 'Tinglayapman', think: 'O‘ylayapman', speak: 'Gapiryapman' };
  var orbState = 'idle', orbSince = 0, lv = 0, amp = 0, ring = 0, spin = 0, lastT = 0, analyser = null, actx = null, abuf = null;
  var reduce = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;
  function sphere(n) {
    var P = [], g = Math.PI * (3 - Math.sqrt(5));
    for (var i = 0; i < n; i++) {
      var y = 1 - 2 * (i + .5) / n, r = Math.sqrt(1 - y * y), a = i * g;
      P.push({ x: Math.cos(a) * r, y: y, z: Math.sin(a) * r, ra: (i * 7 / n) * Math.PI * 2, rj: Math.random() - .5, ph: Math.random() * 6.28, hue: i / n });
    }
    return P;
  }
  var bigP = sphere(700), smallP = sphere(110);
  function orb(s) {
    orbState = s; orbSince = performance.now();
    var i = ORB.indexOf(s);
    [].forEach.call(sh.querySelectorAll('#aiSt i'), function (d, k) { d.classList.toggle('on', k === i); });
    var l = sh.querySelector('#aiStL'); if (l) l.textContent = ORBL[s];
  }
  // Ovoz darajasi: Azure audiosi chalinsa — haqiqiy (AnalyserNode), aks holda nutqqa o'xshash taxminiy to'lqin.
  function level(t) {
    if (orbState !== 'listen' && orbState !== 'speak') return 0;
    if (analyser && audio && !audio.paused) {
      analyser.getByteTimeDomainData(abuf); var m = 0;
      for (var i = 0; i < abuf.length; i++) m = Math.max(m, Math.abs(abuf[i] - 128));
      return Math.min(1, m / 60);
    }
    return Math.min(1, Math.abs(Math.sin(t * 6.3) * Math.sin(t * 2.2 + 1) * (.55 + .45 * Math.sin(t * 14.9))) * 1.8);
  }
  function fit(c) {
    var r = c.getBoundingClientRect(), d = Math.min(2, window.devicePixelRatio || 1), W = Math.round(r.width * d), H = Math.round(r.height * d);
    if (c.width !== W || c.height !== H) { c.width = W; c.height = H; }
    return [c.getContext('2d'), W, H, d];
  }
  function drawOrb(c, P, R0, dotK) {
    if (!c || !c.getBoundingClientRect().width) return;
    var f = fit(c), g = f[0], w = f[1], h = f[2], d = f[3], cx = w / 2, cy = h * .46, R = Math.min(w, h) * R0;
    g.clearRect(0, 0, w, h);
    var wake = orbState === 'wake' ? Math.max(0, 1 - (performance.now() - orbSince) / 900) : 0;
    var scale = 1 + .18 * lv + .22 * wake + (orbState === 'idle' ? .03 * Math.sin(lastT * 1.4) : 0);
    var tilt = .35 + .1 * Math.sin(lastT * .4), ct = Math.cos(tilt), st = Math.sin(tilt), cs = Math.cos(spin), sn = Math.sin(spin);
    g.globalCompositeOperation = 'lighter';
    for (var i = 0; i < P.length; i++) {
      var p = P[i], rip = 1 + amp * .22 * Math.sin(p.ph + lastT * 9 + p.y * 4) + lv * .12 * p.rj;
      var x = p.x * rip, y = p.y * rip, z = p.z * rip, ra = p.ra + lastT * .6, rr = 1.15 + .12 * p.rj;
      x += (Math.cos(ra) * rr - x) * ring; y += (p.rj * .08 - y) * ring; z += (Math.sin(ra) * rr - z) * ring;
      var x1 = x * cs + z * sn, z1 = -x * sn + z * cs, y1 = y * ct - z1 * st, z2 = y * st + z1 * ct;
      var per = 2.6 / (2.6 + z2), depth = (1 - z2) / 2;
      g.fillStyle = 'hsla(' + (232 + p.hue * 48 + ring * 20) + ',90%,' + (62 + 18 * depth) + '%,' + (.18 + .75 * depth) + ')';
      g.beginPath(); g.arc(cx + x1 * R * scale * per, cy + y1 * R * scale * per, Math.max(.6, dotK * (.55 + 1.1 * depth) * d * per), 0, 6.283); g.fill();
    }
    g.globalCompositeOperation = 'source-over';
  }
  function frame(ms) {
    var t = ms / 1000, dt = Math.min(.05, (t - lastT) || .016); lastT = t;
    lv += (level(t) - lv) * .22; amp += (((orbState === 'speak' || orbState === 'listen') ? 1 : 0) - amp) * .08;
    ring += ((orbState === 'think' ? 1 : 0) - ring) * .05;
    spin += dt * (orbState === 'think' ? 1.6 : orbState === 'idle' ? .25 : .6 + .8 * lv);
    if (!D.hidden) {
      if (sh.classList.contains('on')) drawOrb(sh.querySelector('#aiOrb'), bigP, .34, 1.25);
      drawOrb(D.getElementById('aiBtnOrb'), smallP, .36, 1.05);
    }
    if (!reduce) requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);
  if (reduce) setInterval(function () { frame(performance.now()); }, 400);

  function add(cls, html) { var d = D.createElement('div'); d.className = 'aiM ' + cls; d.innerHTML = html; log.append(d); log.scrollTop = log.scrollHeight; return d; }
  function open() { if (!sh.classList.contains('on')) orb('idle'); sh.classList.add('on'); ov.classList.add('on'); syncBtn(); }
  function close() { stopAudio(); sh.classList.remove('on'); ov.classList.remove('on'); syncBtn(); setBusy(false); orb('idle'); }
  ov.onclick = close;
  // Ekrandagi so'nggi savol va javob (tarix — 🕘 da).
  var capQ = sh.querySelector('#aiCapQ'), capA = sh.querySelector('#aiCapA');
  function cap(qText, aHtml, cls) { capQ.textContent = qText || ''; capA.className = cls || ''; capA.innerHTML = aHtml; sh.querySelector('#aiCap').scrollTop = 0; }
  sh.querySelector('#aiX').onclick = close;
  sh.querySelector('#aiHist').onclick = function () { var on = sh.classList.toggle('hist'); this.classList.toggle('on', on); if (on) log.scrollTop = log.scrollHeight; };
  var kb = sh.querySelector('#aiKb');
  if (kb) kb.onclick = function () { var on = sh.classList.toggle('kb'); this.classList.toggle('on', on); if (on) setTimeout(function () { q.focus(); }, 50); };
  D.addEventListener('keydown', function (e) { if (e.key === 'Escape' && sh.classList.contains('on')) close(); });
  function syncBtn() { var b = D.getElementById('aiBtn'); if (b) b.classList.toggle('on', sh.classList.contains('on')); }
  function setBusy(v) { busy = v; post({ t: 'voice', busy: v }); }

  function stopAudio() { if (audio) { try { audio.pause(); } catch (e) {} audio = null; } try { window.speechSynthesis && speechSynthesis.cancel(); } catch (e) {} }
  // Javobni ovozda o'qiydi; tugaganda done() — ilova so'z kutishni qayta boshlaydi.
  function say(text, done) {
    // Ovoz «tugadi» xabari kelmasa ham ilova «band» holatida qotib qolmasin.
    var cb = done || function () {}, fired = false;
    done = function () { if (!fired) { fired = true; clearTimeout(guard); cb(); } };
    var guard = setTimeout(done, 45000);
    req('ai_speak', { text: text }).then(function (r) {
      if (r && r.audio) return playB64(r.audio, done);
      fallback(text, done);
    }).catch(function () { fallback(text, done); });
  }
  function playB64(b64, done) {
    stopAudio();
    audio = new Audio('data:audio/mpeg;base64,' + b64);
    // Shar haqiqiy ovoz balandligiga qarab tebranishi uchun.
    try {
      actx = actx || new (window.AudioContext || window.webkitAudioContext)();
      analyser = actx.createAnalyser(); analyser.fftSize = 256; abuf = new Uint8Array(analyser.fftSize);
      var src = actx.createMediaElementSource(audio); src.connect(analyser); analyser.connect(actx.destination);
      if (actx.state === 'suspended') actx.resume();
    } catch (e) { analyser = null; }
    audio.onended = audio.onerror = function () { audio = null; analyser = null; done(); };
    audio.play().catch(function () { done(); });
  }
  function fallback(text, done) {
    if (window.ReactNativeWebView) { post({ t: 'tts', text: text }); setTimeout(done, Math.min(20000, 800 + text.length * 70)); return; }
    try {
      var u = new SpeechSynthesisUtterance(text); u.lang = 'uz-UZ'; u.onend = u.onerror = done; speechSynthesis.speak(u);
    } catch (e) { done(); }
  }

  function ask(text) {
    text = String(text || '').trim();
    if (!text) return;
    open(); setBusy(true); orb('think');
    add('u', esc(text)); cap(text, '<span class="aiDots"><i></i><i></i><i></i></span>');
    var wait = add('a', '<span class="aiDots"><i></i><i></i><i></i></span>');
    req('ai_ask', { question: text, history: history.slice(-8) }).then(function (r) {
      var ans = (r && r.answer) || 'Javob bo‘sh qaytdi.';
      wait.innerHTML = esc(ans); cap(text, esc(ans));
      history.push({ role: 'user', text: text }, { role: 'assistant', text: ans });
      orb('speak');
      say(ans, function () { setBusy(false); orb('idle'); });
    }).catch(function (e) {
      wait.className = 'aiM a e'; wait.textContent = (e && e.message) || 'Yordamchi javob bermadi.'; cap(text, esc(wait.textContent), 'e');
      setBusy(false); orb('idle');
    });
  }

  sh.querySelector('#aiF').onsubmit = function (e) { e.preventDefault(); var v = q.value; q.value = ''; ask(v); };
  var mic = sh.querySelector('#aiMic');
  if (mic) mic.onclick = function () { if (mic.classList.contains('rec')) return; stopAudio(); setBusy(true); mic.classList.add('rec'); orb('listen'); cap('', 'Gapiring, tinglayapman…', 'hint'); post({ t: 'listen' }); };

  function labbay(cb) {
    var fired = false, done = function () { if (!fired) { fired = true; clearTimeout(guard); cb(); } };
    var guard = setTimeout(done, 6000);
    if (labbayAudio) return playB64(labbayAudio, done);
    req('ai_speak', { text: 'Labbay' }).then(function (r) {
      if (r && r.audio) { labbayAudio = r.audio; return playB64(r.audio, done); }
      fallback('Labbay', done);
    }).catch(function () { fallback('Labbay', done); });
  }

  window.AIBIAssistant = {
    open: open, close: close, ask: ask,
    // Ilova «AIBI» so'zini eshitdi.
    wake: function () {
      if (busy) return;
      stopAudio(); open(); setBusy(true); orb('wake');
      add('a', 'Labbay 🙂'); cap('', 'Labbay 🙂');
      labbay(function () { if (mic) mic.classList.add('rec'); orb('listen'); cap('', 'Gapiring, tinglayapman…', 'hint'); post({ t: 'listen' }); });
    },
    // Ilova savolni matnga aylantirdi ('' — hech narsa eshitilmadi).
    heard: function (text) {
      if (mic) mic.classList.remove('rec');
      if (text && String(text).trim()) ask(text);
      else { add('a e', 'Eshitmadim. Qaytadan «AIBI» deng yoki 🎤 ni bosing.'); cap('', 'Eshitmadim. Qaytadan «AIBI» deng yoki 🎤 ni bosing.', 'e'); setBusy(false); orb('idle'); }
    }
  };

  // Sarlavhaga «AIBI» tugmasi (Rahbar sarlavhasi qayta chizilsa ham qo'shiladi).
  function addBtn() {
    var rt = D.querySelector('.br .rt'); if (!rt || D.getElementById('aiBtn')) return;
    var b = D.createElement('i'); b.id = 'aiBtn'; b.setAttribute('role', 'button'); b.setAttribute('aria-label', 'AIBI yordamchi');
    b.innerHTML = '<canvas id="aiBtnOrb" aria-hidden="true"></canvas><span class="t">AIBI</span>'; b.onclick = function () { sh.classList.contains('on') ? close() : (open(), sh.classList.contains('kb') && setTimeout(function () { q.focus(); }, 350)); };
    rt.insertBefore(b, rt.firstChild); syncBtn();
  }
  new MutationObserver(addBtn).observe(D.documentElement, { childList: true, subtree: true });
  addBtn();
})();
