/* AIBI ilovasi ko'prigi — Telegram'siz.
   AIBI ilovasi (Android) sahifani /app/aibi-*/#aibi=<token> bilan ochadi. Token telefonda saqlanadi,
   API so'rovlariga «Authorization: Bearer» bo'lib qo'shiladi. Telegram Mini App'lar bu fayldan foydalanmaydi.
   window.AIBI.WebApp — sahifa kodi kutadigan interfeys (ready, MainButton, BackButton, HapticFeedback, ...). */
(function () {
  if (window.AIBI) return;
  var KEY = 'aibi.token', SENTINEL = 'aibi-app-session';
  var m = /[#&]aibi=([A-Za-z0-9_\-]+)/.exec(location.hash || '');
  if (m) {
    try { localStorage.setItem(KEY, m[1]); } catch (e) {}
    try { history.replaceState(null, '', location.pathname + location.search); } catch (e) {}
  }
  var token = '';
  try { token = localStorage.getItem(KEY) || ''; } catch (e) {}
  var q = new URLSearchParams(location.search), dark = q.get('theme') === 'dark';

  function post(msg) { try { window.ReactNativeWebView.postMessage(JSON.stringify(msg)); } catch (e) {} }
  function noop() {}
  var light = { bg_color: '#ffffff', secondary_bg_color: '#f1f2f6', text_color: '#17212b', hint_color: '#7b8794', link_color: '#2a8bf2',
    button_color: '#2a8bf2', button_text_color: '#ffffff', header_bg_color: '#ffffff', section_bg_color: '#ffffff', accent_text_color: '#2a8bf2',
    section_header_text_color: '#7b8794', subtitle_text_color: '#7b8794', destructive_text_color: '#f0384f', bottom_bar_bg_color: '#ffffff' };
  var night = { bg_color: '#17212b', secondary_bg_color: '#232e3c', text_color: '#f5f5f5', hint_color: '#708499', link_color: '#6ab3f3',
    button_color: '#5288c1', button_text_color: '#ffffff', header_bg_color: '#17212b', section_bg_color: '#17212b', accent_text_color: '#6ab2f2',
    section_header_text_color: '#6ab3f3', subtitle_text_color: '#708499', destructive_text_color: '#ec3942', bottom_bar_bg_color: '#17212b' };
  var theme = dark ? night : light, root = document.documentElement;
  Object.keys(theme).forEach(function (k) { root.style.setProperty('--tg-theme-' + k.replace(/_/g, '-'), theme[k]); });
  root.style.setProperty('--tg-viewport-height', innerHeight + 'px');
  root.style.setProperty('--tg-viewport-stable-height', innerHeight + 'px');

  var handlers = {}, back = [], backVisible = false;
  function button() {
    var b = { isVisible: false, isActive: true, text: '', color: '', textColor: '', isProgressVisible: false };
    ['setText', 'onClick', 'offClick', 'show', 'hide', 'enable', 'disable', 'showProgress', 'hideProgress', 'setParams']
      .forEach(function (n) { b[n] = function () { return b; }; });
    return b;
  }
  var WebApp = {
    initData: token ? SENTINEL : '',
    initDataUnsafe: { user: { id: 0, first_name: '', language_code: 'uz' }, auth_date: Math.floor(Date.now() / 1000) },
    version: '8.0', platform: 'aibi', colorScheme: dark ? 'dark' : 'light', themeParams: theme,
    isExpanded: true, viewportHeight: innerHeight, viewportStableHeight: innerHeight, isVerticalSwipesEnabled: false, isFullscreen: false,
    safeAreaInset: { top: 0, bottom: 0, left: 0, right: 0 }, contentSafeAreaInset: { top: 0, bottom: 0, left: 0, right: 0 },
    headerColor: theme.header_bg_color, backgroundColor: theme.bg_color,
    isVersionAtLeast: function () { return true; },
    ready: noop, expand: noop, close: function () { post({ t: 'close' }); },
    setHeaderColor: function (c) { post({ t: 'header', c: c }); }, setBackgroundColor: noop, setBottomBarColor: noop,
    enableClosingConfirmation: noop, disableClosingConfirmation: noop, enableVerticalSwipes: noop, disableVerticalSwipes: noop,
    requestFullscreen: noop, exitFullscreen: noop, lockOrientation: noop, unlockOrientation: noop,
    onEvent: function (e, f) { (handlers[e] = handlers[e] || []).push(f); },
    offEvent: function (e, f) { handlers[e] = (handlers[e] || []).filter(function (x) { return x !== f; }); },
    sendData: noop,
    openLink: function (u) { post({ t: 'link', u: String(u) }) || (window.ReactNativeWebView || window.open(String(u), '_blank')); },
    openTelegramLink: function (u) { post({ t: 'link', u: String(u) }); },
    showAlert: function (msg, cb) { alert(msg); cb && cb(); },
    showConfirm: function (msg, cb) { var r = confirm(msg); cb && cb(r); },
    showPopup: function (p, cb) {
      var bs = (p && p.buttons) || [], ok = confirm((p.title ? p.title + '\n\n' : '') + p.message);
      var pick = bs.filter(function (b) { return b.type !== 'cancel' && b.type !== 'close'; })[0];
      cb && cb(ok ? (pick && pick.id) || 'ok' : '');
    },
    HapticFeedback: {
      impactOccurred: function () { post({ t: 'haptic', k: 'impact' }); },
      notificationOccurred: function (k) { post({ t: 'haptic', k: k }); },
      selectionChanged: function () { post({ t: 'haptic', k: 'select' }); }
    },
    BackButton: {
      get isVisible() { return backVisible; },
      show: function () { backVisible = true; return this; }, hide: function () { backVisible = false; return this; },
      onClick: function (f) { back.push(f); return this; }, offClick: function (f) { back = back.filter(function (x) { return x !== f; }); return this; }
    },
    MainButton: button(), SecondaryButton: button(), SettingsButton: { show: noop, hide: noop, onClick: noop, offClick: noop },
    CloudStorage: {
      setItem: function (k, v, cb) { try { localStorage.setItem('cs:' + k, v); cb && cb(null, true); } catch (e) { cb && cb(e); } },
      getItem: function (k, cb) { cb && cb(null, localStorage.getItem('cs:' + k) || ''); },
      removeItem: function (k, cb) { localStorage.removeItem('cs:' + k); cb && cb(null, true); },
      getItems: function (ks, cb) { var o = {}; ks.forEach(function (k) { o[k] = localStorage.getItem('cs:' + k) || ''; }); cb && cb(null, o); },
      getKeys: function (cb) { cb && cb(null, []); }
    }
  };
  // Android «orqaga» tugmasi: avval sahifaning o'z BackButton'i.
  window.__aibiBack = function () { if (backVisible && back.length) { back[back.length - 1](); return true; } return false; };
  window.AIBI = { WebApp: WebApp, Utils: {}, WebView: { initParams: {}, onEvent: noop, offEvent: noop, postEvent: noop, receiveEvent: noop } };

  // API: initData o'rniga Bearer token.
  var _fetch = window.fetch.bind(window);
  window.fetch = function (input, init) {
    var url = typeof input === 'string' ? input : (input && input.url) || '';
    try {
      if (init && typeof init.body === 'string' && /\/api\//.test(url) && init.body.indexOf(SENTINEL) >= 0) {
        var body = JSON.parse(init.body);
        if (body.initData === SENTINEL) {
          delete body.initData;
          var h = new Headers(init.headers || {}); h.set('Authorization', 'Bearer ' + token);
          init = Object.assign({}, init, { body: JSON.stringify(body), headers: h });
        }
      }
    } catch (e) {}
    return _fetch(input, init).then(function (r) {
      if (r.status === 401 && /\/api\//.test(url)) post({ t: 'relogin' });
      return r;
    });
  };
})();
