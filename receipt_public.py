"""Mijoz uchun ochiq chek: chop etilgan chekdagi QR kod shu sahifani ochadi.

- Havola: {base}/c/{sotuv_id}-{imzo}. Imzo — server sirli kaliti bilan HMAC, shuning uchun boshqa chek
  raqamini taxmin qilib ochib bo'lmaydi; login kerak emas.
- QR — reportlab matritsasidan ixcham SVG (yangi kutubxona yo'q).
- Sahifa serverda tayyorlanadi (JS yo'q), telefonda o'qiladi; bekor qilingan chek shunday belgilanadi.
"""
import hashlib
import hmac
import html
import os
import re
from datetime import datetime, timedelta, timezone

TZ = timezone(timedelta(hours=5))
_SECRET = b''
PATH_RE = re.compile(r'/c/(\d{1,12})-([0-9a-f]{16})(\.svg)?')


def configure(secret):
    global _SECRET
    _SECRET = hashlib.sha256(('receipt:' + (secret or '')).encode()).digest()


def _sig(sale_id):
    return hmac.new(_SECRET, f'sale:{int(sale_id)}'.encode(), hashlib.sha256).hexdigest()[:16]


def base_url():
    return (os.getenv('WEBHOOK_BASE_URL') or os.getenv('RENDER_EXTERNAL_URL') or '').rstrip('/')


def url(sale_id, base=None):
    base = (base or base_url()).rstrip('/')
    if not base or not _SECRET:
        return None
    return f'{base}/c/{int(sale_id)}-{_sig(sale_id)}'


def parse(path):
    """'/c/12-ab..' -> (12, is_svg) yoki None (imzo noto'g'ri bo'lsa ham None)."""
    m = PATH_RE.fullmatch(path or '')
    if not m or not _SECRET:
        return None
    sale_id = int(m.group(1))
    if not hmac.compare_digest(m.group(2), _sig(sale_id)):
        return None
    return sale_id, bool(m.group(3))


def qr_svg(text, size=200):
    from reportlab.graphics.barcode.qr import QrCodeWidget
    w = QrCodeWidget(text, barLevel='M')
    w.draw()
    q = w.qr
    n = q.getModuleCount()
    quiet = 2
    total = n + quiet * 2
    parts = []
    for r in range(n):
        c = 0
        while c < n:
            if q.isDark(r, c):
                start = c
                while c < n and q.isDark(r, c):
                    c += 1
                parts.append(f'M{start + quiet} {r + quiet}h{c - start}v1h-{c - start}z')
            else:
                c += 1
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {total} {total}" width="{size}" height="{size}" '
            f'shape-rendering="crispEdges"><rect width="{total}" height="{total}" fill="#fff"/>'
            f'<path fill="#000" d="{"".join(parts)}"/></svg>')


def _usd(v):
    return f'${v:,.2f}'.replace(',', ' ')


def page(receipt, brand):
    """receipt — shop.receipt(); brand — branding.get()."""
    e = html.escape
    r = receipt
    d = brand.get('details') or {}
    name = d.get('legalName') or brand.get('name') or ''
    when = datetime.fromtimestamp(int(r['ts']), TZ).strftime('%d.%m.%Y %H:%M')
    method = {'cash_usd': 'naqd $', 'cash_uzs': 'naqd so‘m', 'card': 'karta'}.get(r.get('method') or '', '')
    lines = ''.join(
        f'<tr><td>{e(l["name"])}<small>{l["qty"]} × {_usd(l["priceUsd"])}'
        f'{" · −" + _usd(l["discountUsd"]) if l["discountUsd"] else ""}</small></td><td class="r">{_usd(l["totalUsd"])}</td></tr>'
        for l in r['lines'])
    paid_uzs = f'<br><small>{r["paidUzs"]:,} so‘m</small>'.replace(',', ' ') if r.get('paidUzs') else ''
    cancelled = ('<div class="x">Bu chek bekor qilingan</div>' if r.get('cancelled') else '')
    logo = brand.get('logo') or ''
    logo_html = f'<img class="logo" src="{e(logo)}" alt="">' if logo.startswith('data:image/') else ''
    contact = ' · '.join(e(x) for x in (d.get('address'), d.get('phone') and 'Tel: ' + d['phone']) if x)
    return f'''<!doctype html><html lang="uz"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex">
<title>Chek № {r["id"]}{" · " + e(name) if name else ""}</title><style>
:root{{color-scheme:light}}body{{margin:0;background:#f3f4f6;font:15px/1.45 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;color:#111}}
.w{{max-width:440px;margin:0 auto;padding:16px}}.c{{background:#fff;border-radius:14px;padding:18px;box-shadow:0 1px 3px rgba(0,0,0,.08)}}
.h{{text-align:center}}.logo{{max-width:120px;max-height:64px}}h1{{font-size:20px;margin:6px 0 2px}}.m{{color:#555;font-size:13px}}
hr{{border:0;border-top:1px dashed #ccc;margin:14px 0}}table{{width:100%;border-collapse:collapse}}td{{padding:5px 0;vertical-align:top}}
td small{{display:block;color:#666;font-size:12.5px}}.r{{text-align:right;white-space:nowrap}}.b td{{font-weight:700;font-size:17px}}
.bad{{color:#b91c1c}}.x{{background:#fee2e2;color:#991b1b;border-radius:10px;padding:10px;text-align:center;font-weight:700;margin-bottom:12px}}
.f{{text-align:center;color:#777;font-size:12.5px;margin-top:14px}}</style></head><body><div class="w"><div class="c">
{cancelled}<div class="h">{logo_html}{f"<div><b>{e(name)}</b></div>" if name else ""}{f'<div class="m">{contact}</div>' if contact else ""}
<h1>Chek № {r["id"]}</h1><div class="m">{when}</div></div><hr>
<div>Mijoz: <b>{e(r["client"])}</b></div><div class="m">Sotuvchi: {e(r["seller"])}</div><hr>
<table>{lines}</table><hr><table>
{f'<tr><td>Jami narx</td><td class="r">{_usd(r["subtotalUsd"])}</td></tr><tr><td>Chegirma</td><td class="r">−{_usd(r["discountUsd"])}</td></tr>' if r["discountUsd"] else ""}
{f'<tr><td>{e(r.get("extraName") or "Qo‘shimcha xarajat")}</td><td class="r">+{_usd(r["extraUsd"])}</td></tr>' if r.get("extraUsd") else ""}
<tr class="b"><td>Jami</td><td class="r">{_usd(r["totalUsd"])}</td></tr>
<tr><td>To‘langan{" (" + method + ")" if method else ""}</td><td class="r">{_usd(r["paidUsd"])}{paid_uzs}</td></tr>
{f'<tr class="b bad"><td>Qoldiq (qarz)</td><td class="r">{_usd(r["debtUsd"])}</td></tr>' if r["debtUsd"] > 0 else ""}
</table>{f'<hr><div class="m">Izoh: {e(r["note"])}</div>' if r.get("note") else ""}
</div><div class="f">Xaridingiz uchun rahmat!</div></div></body></html>'''
