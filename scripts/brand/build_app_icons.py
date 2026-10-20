"""AIBI ilova ikonkalari (Agent, Manager, Cashier, Warehouse, Dashboard) — foydalanuvchi bergan to'plamdan.

Manba: miniapps/premium-kit/aibi/source/apps/<app>.png (dizayn taxtasidan kesilgan ~110 px plitkalar).
Har birini kvadratga keltirib, burchaklarini yumaloq shaffof qiladi va 180/192/64/32 px PNG yasaydi.
Ishlatish:  python3 scripts/brand/build_app_icons.py
"""
import os
from PIL import Image, ImageDraw

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
AIBI = os.path.join(ROOT, 'miniapps', 'premium-kit', 'aibi')
SRC = os.path.join(AIBI, 'source', 'apps')
OUT = os.path.join(AIBI, 'apps')
SIZES = (192, 180, 64, 32)


def _tile(path):
    im = Image.open(path).convert('RGBA')
    w, h = im.size
    side = min(w, h)
    im = im.crop(((w - side) // 2, (h - side) // 2, (w - side) // 2 + side, (h - side) // 2 + side))
    big = im.resize((side * 4, side * 4), Image.LANCZOS)
    inset = int(side * 4 * 0.035)          # plitka chetidagi taxta fonini kesib tashlaymiz
    mask = Image.new('L', big.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([inset, inset, big.width - inset - 1, big.height - inset - 1],
                                           radius=int(big.width * 0.22), fill=255)
    big.putalpha(mask)
    return big


def main():
    os.makedirs(OUT, exist_ok=True)
    made = []
    for f in sorted(os.listdir(SRC)):
        if not f.endswith('.png'):
            continue
        name = f[:-4]
        big = _tile(os.path.join(SRC, f))
        for s in SIZES:
            p = f'{name}-{s}.png'
            big.resize((s, s), Image.LANCZOS).save(os.path.join(OUT, p), optimize=True)
            made.append(p)
        big.resize((64, 64), Image.LANCZOS).save(os.path.join(OUT, f'{name}.ico'), sizes=[(16, 16), (32, 32), (64, 64)])
        made.append(f'{name}.ico')
    tp = os.path.join(AIBI, 'source', 'telegram-profile.png')
    if os.path.exists(tp):
        im = Image.open(tp).convert('RGBA')
        side = min(im.size)
        im = im.crop(((im.width - side) // 2, (im.height - side) // 2, (im.width - side) // 2 + side, (im.height - side) // 2 + side))
        im.convert('RGB').resize((512, 512), Image.LANCZOS).save(os.path.join(AIBI, 'telegram-profile-512.png'))
        made.append('telegram-profile-512.png')
    print(', '.join(made))


if __name__ == '__main__':
    main()
