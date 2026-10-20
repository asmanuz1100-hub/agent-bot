"""AIBI brend assetlari generatori (BALANCE · 09 Aurora).

Bitta geometriyadan SVG va PNG chiqaradi, shuning uchun barcha o'lchamlar bir xil:
  doira (r=200, markaz 256) vertikal kesim bilan ikkiga bo'lingan: chap yarim doira,
  o'ng tomonda yuqori va pastki chorak; segmentlar orasida bir xil tirqish.
Ishlatish:  python3 scripts/brand/build_aibi_assets.py   (faqat Pillow kerak)
"""
import math
import os
from PIL import Image, ImageDraw, ImageFilter

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
OUT = os.path.join(ROOT, 'miniapps', 'premium-kit', 'aibi')
# Asl belgi (foydalanuvchi bergan dizayn rasmidan kesilgan, fon shaffof). Bo'lsa — geometriya o'rniga shu ishlatiladi.
SOURCE = os.path.join(OUT, 'source', 'aibi-mark-source.png')

BLUE, VIOLET, PURPLE, PINK, NAVY, WHITE = '#3882F6', '#6366F1', '#A855F7', '#EC4899', '#0F172A', '#F8FAFC'
INDIGO = '#312E81'                   # o'ng yuqori bo'lakning to'q tomoni
C, R, GAP = 256.0, 200.0, 0.0        # 512 birlikli koordinata tizimi; segmentlar tirqishsiz
RADIUS = {'left': (R, R), 'tr': (R * 0.78, R), 'br': (R, R)}   # (rx, ry): o'ng yuqori bo'lak torroq ellips — «B» siluyeti
# Segmentlar: (nom, gradient boshi (x,y), oxiri (x,y), ranglar)
SEGMENTS = {
    'left':  ((120, 70), (230, 450), (PINK, PURPLE, BLUE)),
    'tr':    ((260, 100), (420, 250), (VIOLET, INDIGO)),
    'br':    ((260, 260), (430, 440), (PURPLE, PINK)),
}


def _edge(offset):
    """Doira chizig'ining x = C±offset dagi nuqtalari (y yuqori, y pastki)."""
    dy = math.sqrt(R * R - offset * offset)
    return C - dy, C + dy


def svg_paths():
    f = lambda v: f'{v:.2f}'.rstrip('0').rstrip('.')
    (lx, ly), (tx, ty), (bx, by) = RADIUS['left'], RADIUS['tr'], RADIUS['br']
    return {
        'left': f'M{f(C)} {f(C - ly)}A{f(lx)} {f(ly)} 0 0 0 {f(C)} {f(C + ly)}Z',
        'tr': f'M{f(C)} {f(C)}V{f(C - ty)}A{f(tx)} {f(ty)} 0 0 1 {f(C + tx)} {f(C)}Z',
        'br': f'M{f(C)} {f(C)}H{f(C + bx)}A{f(bx)} {f(by)} 0 0 1 {f(C)} {f(C + by)}Z',
    }


def _grad_defs(prefix):
    out = []
    for name, ((x1, y1), (x2, y2), cols) in SEGMENTS.items():
        stops = ''.join(f'<stop offset="{i / (len(cols) - 1):g}" stop-color="{c}"/>' for i, c in enumerate(cols))
        out.append(f'<linearGradient id="{prefix}{name}" x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" gradientUnits="userSpaceOnUse">{stops}</linearGradient>')
    out.append(f'<radialGradient id="{prefix}gl" cx="190" cy="150" r="230" gradientUnits="userSpaceOnUse">'
               '<stop stop-color="#fff" stop-opacity=".35"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></radialGradient>')
    return ''.join(out)


def _source_b64(px=256):
    import base64, io
    buf = io.BytesIO()
    # WebP (shaffof fon bilan) — PNG'dan ~5 baravar yengil; Telegram WebView (Android/iOS) qo'llaydi.
    Image.open(SOURCE).convert('RGBA').resize((px, px), Image.LANCZOS).save(buf, 'WEBP', quality=92, method=6)
    return base64.b64encode(buf.getvalue()).decode()


def mark_svg(prefix='a', with_defs=True):
    if os.path.exists(SOURCE):
        # Belgi 512 birlikli doskada 56..456 oralig'ini egallaydi (geometriya bilan bir xil joy).
        return f'<image href="data:image/webp;base64,{_source_b64()}" x="56" y="56" width="400" height="400"/>'
    p = svg_paths()
    body = ''.join(f'<path d="{p[n]}" fill="url(#{prefix}{n})"/>' for n in ('left', 'tr', 'br'))
    glow = ''.join(f'<path d="{p[n]}" fill="url(#{prefix}gl)"/>' for n in ('left', 'tr', 'br'))
    return (f'<defs>{_grad_defs(prefix)}</defs>' if with_defs else '') + body + glow


def write_svgs():
    os.makedirs(OUT, exist_ok=True)
    head = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vb}" role="img" aria-label="AIBI">'
    files = {
        'aibi-mark.svg': head.format(vb='56 56 400 400') + mark_svg() + '</svg>',
        'aibi-icon-dark.svg': head.format(vb='0 0 512 512') + f'<rect width="512" height="512" rx="112" fill="{NAVY}"/>'
                              + '<g transform="translate(256 256) scale(.78) translate(-256 -256)">' + mark_svg() + '</g></svg>',
        'aibi-icon-light.svg': head.format(vb='0 0 512 512') + f'<rect width="512" height="512" rx="112" fill="#FFFFFF"/>'
                               + '<g transform="translate(256 256) scale(.78) translate(-256 -256)">' + mark_svg() + '</g></svg>',
    }
    word = ('<text x="{x}" y="300" font-family="Inter, Manrope, \'Segoe UI\', system-ui, -apple-system, sans-serif" '
            'font-size="190" font-weight="800" letter-spacing="6" fill="{fill}">ΛIBI</text>'
            '<text x="{x}" y="368" font-family="Inter, Manrope, system-ui, sans-serif" font-size="33" font-weight="600" '
            'letter-spacing="8" fill="{sub}">SMART BUSINESS PLATFORM</text>')
    for mode, fill, sub in (('dark', WHITE, '#CBD5E1'), ('light', NAVY, '#475569')):
        files[f'aibi-logo-{mode}.svg'] = (head.format(vb='40 40 1260 432') + mark_svg() + word.format(x=500, fill=fill, sub=sub) + '</svg>')
    for name, data in files.items():
        with open(os.path.join(OUT, name), 'w', encoding='utf-8') as fh:
            fh.write(data + '\n')
    return list(files)


# ---------- PNG (Pillow, 4x supersampling) ----------

def _hex(c):
    c = c.lstrip('#')
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def _linear(size, scale, start, end, cols):
    """size×size RGBA chiziqli gradient (koordinatalar 512 birlikda)."""
    (x1, y1), (x2, y2) = start, end
    w = size
    img = Image.new('RGBA', (w, w))
    px = img.load()
    dx, dy = x2 - x1, y2 - y1
    den = dx * dx + dy * dy
    rgb = [_hex(c) for c in cols]
    n = len(rgb) - 1
    # Har bir qator uchun alohida hisob — tez va yetarli aniq.
    for j in range(w):
        y = j / scale
        for i in range(w):
            x = i / scale
            t = max(0.0, min(1.0, ((x - x1) * dx + (y - y1) * dy) / den))
            k = min(int(t * n), n - 1)
            u = t * n - k
            a, b = rgb[k], rgb[k + 1]
            px[i, j] = (int(a[0] + (b[0] - a[0]) * u), int(a[1] + (b[1] - a[1]) * u), int(a[2] + (b[2] - a[2]) * u), 255)
    return img


def _seg_mask(size, scale, name):
    m = Image.new('L', (size, size), 0)
    d = ImageDraw.Draw(m)
    rx, ry = RADIUS[name][0] * scale, RADIUS[name][1] * scale
    cx = C * scale
    d.ellipse([cx - rx, cx - ry, cx + rx, cx + ry], fill=255)
    if name == 'left':
        d.rectangle([cx, 0, size, size], fill=0)
    elif name == 'tr':
        d.rectangle([0, 0, cx - 1, size], fill=0)
        d.rectangle([0, cx, size, size], fill=0)
    else:
        d.rectangle([0, 0, cx - 1, size], fill=0)
        d.rectangle([0, 0, size, cx - 1], fill=0)
    return m


def render_mark(px_size, ss=4):
    """512 birlikli doskada belgini px_size o'lchamda (shaffof fon) chizadi."""
    if os.path.exists(SOURCE):
        return Image.open(SOURCE).convert('RGBA').resize((px_size, px_size), Image.LANCZOS)
    size = px_size * ss
    scale = size / 512.0
    work = max(256, min(size, 1024))       # gradientni kichikroq hisoblab kattalashtiramiz
    wscale = work / 512.0
    out = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    glow = Image.new('L', (work, work), 0)
    gd = glow.load()
    for j in range(work):
        for i in range(work):
            dist = math.hypot(i / wscale - 190, j / wscale - 150) / 230
            gd[i, j] = int(max(0.0, 1 - dist) * 0.35 * 255)
    glow = glow.resize((size, size), Image.BICUBIC)
    white = Image.new('RGBA', (size, size), (255, 255, 255, 255))
    for name, (a, b, cols) in SEGMENTS.items():
        grad = _linear(work, wscale, a, b, cols).resize((size, size), Image.BICUBIC)
        mask = _seg_mask(size, scale, name)
        layer = Image.composite(white, grad, glow)
        out.paste(layer, (0, 0), mask)
    return out.resize((px_size, px_size), Image.LANCZOS)


def _tile(px_size, bg, inset=0.78, radius=112 / 512):
    tile = Image.new('RGBA', (px_size * 4, px_size * 4), (0, 0, 0, 0))
    ImageDraw.Draw(tile).rounded_rectangle([0, 0, px_size * 4 - 1, px_size * 4 - 1], radius=int(px_size * 4 * radius), fill=_hex(bg) + (255,))
    tile = tile.resize((px_size, px_size), Image.LANCZOS)
    m = render_mark(int(px_size * inset))
    off = (px_size - m.size[0]) // 2
    tile.alpha_composite(m, (off, off))
    return tile


def write_pngs():
    files = []
    big = render_mark(1024)
    big.save(os.path.join(OUT, 'aibi-mark-1024.png')); files.append('aibi-mark-1024.png')
    for s in (512, 192, 64):
        big.resize((s, s), Image.LANCZOS).save(os.path.join(OUT, f'aibi-mark-{s}.png')); files.append(f'aibi-mark-{s}.png')
    for mode, bg in (('dark', NAVY), ('light', '#FFFFFF')):
        base = _tile(1024, bg)
        for s in (1024, 512, 192, 180, 120, 64, 32, 16):
            name = f'aibi-icon-{mode}-{s}.png'
            (base if s == 1024 else base.resize((s, s), Image.LANCZOS)).save(os.path.join(OUT, name)); files.append(name)
    # Android adaptive icon: oldingi qatlam (xavfsiz zona 66%) va fon alohida.
    fg = Image.new('RGBA', (1024, 1024), (0, 0, 0, 0))
    m = big.resize((600, 600), Image.LANCZOS)
    fg.alpha_composite(m, (212, 212))
    fg.save(os.path.join(OUT, 'aibi-adaptive-foreground.png')); files.append('aibi-adaptive-foreground.png')
    Image.new('RGBA', (1024, 1024), _hex(NAVY) + (255,)).save(os.path.join(OUT, 'aibi-adaptive-background.png')); files.append('aibi-adaptive-background.png')
    # Splash: to'q fon, markazda belgi (matn ilovaning o'zida chiziladi).
    sp = Image.new('RGBA', (1284, 2778), _hex(NAVY) + (255,))
    sm = big.resize((420, 420), Image.LANCZOS)
    sp.alpha_composite(sm, ((1284 - 420) // 2, 1100))
    sp.save(os.path.join(OUT, 'aibi-splash.png')); files.append('aibi-splash.png')
    # favicon.ico (16/32/64)
    _tile(64, NAVY).save(os.path.join(OUT, 'favicon.ico'), sizes=[(16, 16), (32, 32), (64, 64)]); files.append('favicon.ico')
    return files


if __name__ == '__main__':
    print('SVG:', ', '.join(write_svgs()))
    print('PNG:', ', '.join(write_pngs()))
