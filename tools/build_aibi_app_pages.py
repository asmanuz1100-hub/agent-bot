"""AIBI ilovasi sahifalari — Telegram Mini App'lardan Telegram'siz nusxa.

    python3 tools/build_aibi_app_pages.py

Telegram Mini App'lar (miniapps/agent, ombor, savdo, rahbar-premium, cashier-miniapp.html) O'ZGARMAYDI.
Ilova uchun nusxalar miniapps/aibi-<nom>/ ga yoziladi va /app/aibi-<nom>/ da beriladi:
  * Telegram skripti o'rniga /app/aibi-kit/bridge.js (login tokeni bilan ishlaydi, botga bog'liq emas);
  * window.Telegram / Telegram.WebApp -> window.AIBI / AIBI.WebApp;
  * Agent, Kassa, Rahbar — Ombor/Savdo palitrasi va shrifti.
Mini App o'zgarganda shu skriptni qayta ishga tushiring va natijani commit qiling.
"""
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MINI = ROOT / 'miniapps'
TG_SCRIPT = re.compile(r'<script[^>]*src="https://telegram\.org/js/telegram-web-app\.js[^"]*"[^>]*>\s*</script>')
BRIDGE = '<script src="/app/aibi-kit/bridge.js?v=1"></script>'
BANNER = '<!-- AVTOMATIK: tools/build_aibi_app_pages.py — qo\'lda tahrirlamang (manba: {src}) -->\n'

# Ombor/Savdo palitrasi (miniapps/ombor :root).
OMBOR = dict(bg='#f1f2f6', card='#fff', tx='#17212b', mu='#7b8794', line='#e7e9ef', pri='#2a8bf2', k='#1f6fd1',
             ok='#16b364', bad='#f0384f', warn='#f59e0b', soft='#f3f5f9',
             grad='linear-gradient(135deg,#6bb4ff,#2a8bf2 45%,#1f6fd1)', sh='0 1px 0 #fff inset,0 14px 30px -18px #0a2a8a40')
FONT = 'Manrope,Inter,-apple-system,"Segoe UI",Roboto,sans-serif'
VARS = {
    'agent': ('--tg-bg:{bg};--paper:{bg};--tg-text:{tx};--navy:{tx};--tg-header:{tx};--tg-section:{card};--tg-hint:{mu};'
              '--muted:{mu};--line:{line};--blue:{pri};--green:{ok};--mp:{ok};--red:{bad};--amber:{warn};--purple:{k};'),
    'kassa': ('--tg-bg:{bg};--tg-text:{tx};--tg-header:{bg};--tg-section:{card};--tg-hint:{mu};--tg-line:{line};'
              '--pri:{pri};--grad:{grad};--k:{k};'),
    'rahbar': ('--bg:{bg};--card:{card};--tx:{tx};--mu:{mu};--line:{line};--pri:{pri};--ok:{ok};--bad:{bad};--warn:{warn};'
               '--soft:{soft};--a:{pri};--q:{pri};--gold:{pri};--gold2:{k};--gl:{grad};--sh:{sh};'),
}
# (manba, nusxa nomi, palitra)
PAGES = [
    (MINI / 'ombor', 'ombor', None),
    (MINI / 'savdo', 'savdo', None),
    (ROOT / 'cashier-miniapp.html', 'kassa', 'kassa'),
    (MINI / 'agent', 'agent', 'agent'),
    (MINI / 'rahbar-premium', 'rahbar', 'rahbar'),
]


def theme_css(kind):
    v = VARS[kind].format(**OMBOR)
    return ('<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Manrope:wght@500;600;700;800&display=swap">'
            '<style id="aibi-app-theme">@media (prefers-color-scheme: light){'
            f'html:root,html:root body{{{v}}}'
            f'html:root body{{background:{OMBOR["bg"]};color:{OMBOR["tx"]}}}}}'
            f'html:root body,html:root body button,html:root body input,html:root body select,html:root body textarea{{font-family:{FONT}}}'
            '</style>')


def detelegram_js(text):
    text = text.replace('window.Telegram', 'window.AIBI')
    return re.sub(r'(?<![\w.])Telegram\.(WebApp|WebView|Utils)\b', r'AIBI.\1', text)


def convert_html(text, src, kind):
    text, n = TG_SCRIPT.subn(BRIDGE, text)
    if not n:  # Telegram skripti yo'q sahifa — ko'prik <head> boshida
        text = re.sub(r'<head(\s[^>]*)?>', lambda m: m.group(0) + BRIDGE, text, count=1)
    text = detelegram_js(text)
    if kind:
        text = re.sub(r'</head>', theme_css(kind) + '</head>', text, count=1, flags=re.I)
    # Izoh <!doctype> dan keyin — oldida bo'lsa ba'zi WebView'lar quirks rejimiga o'tadi.
    m = re.match(r'\s*<!doctype[^>]*>\s*', text, re.I)
    cut = m.end() if m else 0
    return text[:cut] + BANNER.format(src=src) + text[cut:]


def build():
    for src, name, kind in PAGES:
        dst = MINI / f'aibi-{name}'
        if dst.exists():
            shutil.rmtree(dst)
        rel = src.relative_to(ROOT)
        if src.is_file():
            dst.mkdir(parents=True)
            (dst / 'index.html').write_text(convert_html(src.read_text(encoding='utf-8'), rel, kind), encoding='utf-8')
            continue
        shutil.copytree(src, dst)
        for f in dst.rglob('*'):
            if f.suffix == '.html':
                f.write_text(convert_html(f.read_text(encoding='utf-8'), rel, kind), encoding='utf-8')
            elif f.suffix == '.js' and 'vendor' not in f.parts:
                f.write_text(detelegram_js(f.read_text(encoding='utf-8')), encoding='utf-8')
        print(f'{rel} -> {dst.relative_to(ROOT)}')


if __name__ == '__main__':
    build()
