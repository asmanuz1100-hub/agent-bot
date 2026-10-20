"""Web panel brendi: kompaniya nomi va logotipi (meta jadvalida saqlanadi).

Bo'sh qiymat — neytral ko'rinish: interfeys o'zi nom o'ylab topmaydi.
"""
import base64
import re

import json

NAME_KEY='brand_name'
DETAILS_KEY='brand_details'
# Hujjatlarda (akt sverka) chiqadigan rekvizitlar: kalit -> (sarlavha, maks. uzunlik)
DETAILS={'legalName':('Yuridik nomi',160),'address':('Manzil',240),'phone':('Telefon',80),
         'inn':('STIR (INN)',20),'bank':('Bank rekvizitlari',240),'director':('Rahbar F.I.Sh.',120)}
# Rekvizit kiritilmagan bo'lsa hujjatlar avvalgidek chiqadi (hozirgi foydalanuvchi uchun).
DEFAULT_DOCUMENT_NAME='ASMAN SILICAT'
LOGO_KEY='brand_logo'
MAX_NAME=60
MAX_LOGO_BYTES=200_000
_LOGO_RE=re.compile(r'^data:image/(png|jpeg|webp);base64,([A-Za-z0-9+/=]+)$')


def _get(db,key):
    row=db.execute('SELECT value FROM meta WHERE key=?',(key,)).fetchone()
    return (row[0] if row else '') or ''


def _put(db,key,value):
    db.execute('INSERT INTO meta(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(key,value))


def details(db):
    try:d=json.loads(_get(db,DETAILS_KEY) or '{}')
    except ValueError:d={}
    return {k:str(d.get(k) or '') for k in DETAILS}


def get(db):
    return {'name':_get(db,NAME_KEY),'logo':_get(db,LOGO_KEY),'details':details(db)}


def document_issuer(db):
    """Hujjat sarlavhasi uchun: nom (yuridik nom > brend nomi > standart), rekvizit qatorlari va logotip."""
    d=details(db);name=d['legalName'] or _get(db,NAME_KEY) or DEFAULT_DOCUMENT_NAME
    lines=[f'{DETAILS[k][0]}: {d[k]}' for k in ('address','phone','inn','bank') if d[k]]
    return {'name':name,'lines':lines,'logo':_get(db,LOGO_KEY),'director':d['director']}


def save(db,name=None,logo=None,details_in=None):
    """name/logo/details: None — o'zgarmaydi, '' — tozalanadi."""
    if details_in is not None:
        if not isinstance(details_in,dict):raise ValueError('Rekvizitlar noto‘g‘ri.')
        clean={}
        for k,(label,mx) in DETAILS.items():
            v=' '.join(str(details_in.get(k) or '').split())
            if len(v)>mx:raise ValueError(f'{label} {mx} belgidan oshmasin.')
            clean[k]=v
        _put(db,DETAILS_KEY,json.dumps(clean,ensure_ascii=False))
    if name is not None:
        name=' '.join(str(name).split())
        if len(name)>MAX_NAME:
            raise ValueError(f'Kompaniya nomi {MAX_NAME} belgidan oshmasin.')
        _put(db,NAME_KEY,name)
    if logo is not None:
        logo=str(logo).strip()
        if logo:
            m=_LOGO_RE.match(logo)
            if not m:
                raise ValueError('Logotip PNG, JPEG yoki WebP rasm bo‘lishi kerak.')
            try:raw=base64.b64decode(m.group(2),validate=True)
            except ValueError:raise ValueError('Logotip fayli buzilgan.')
            if len(raw)>MAX_LOGO_BYTES:
                raise ValueError('Logotip 200 KB dan kichik bo‘lsin.')
        _put(db,LOGO_KEY,logo)
    return get(db)


def file_prefix(db):
    """Yuklab olinadigan fayl nomi boshi: brend nomidan; bo'lmasa avvalgidek ASMAN."""
    name=_get(db,NAME_KEY)
    slug=re.sub(r'[^0-9A-Za-z]+','-',name).strip('-')[:40]
    return slug or 'ASMAN'
