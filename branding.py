"""Web panel brendi: kompaniya nomi va logotipi (meta jadvalida saqlanadi).

Bo'sh qiymat — neytral ko'rinish: interfeys o'zi nom o'ylab topmaydi.
"""
import base64
import re

NAME_KEY='brand_name'
LOGO_KEY='brand_logo'
MAX_NAME=60
MAX_LOGO_BYTES=200_000
_LOGO_RE=re.compile(r'^data:image/(png|jpeg|webp);base64,([A-Za-z0-9+/=]+)$')


def _get(db,key):
    row=db.execute('SELECT value FROM meta WHERE key=?',(key,)).fetchone()
    return (row[0] if row else '') or ''


def _put(db,key,value):
    db.execute('INSERT INTO meta(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(key,value))


def get(db):
    return {'name':_get(db,NAME_KEY),'logo':_get(db,LOGO_KEY)}


def save(db,name=None,logo=None):
    """name/logo: None — o'zgarmaydi, '' — tozalanadi."""
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
