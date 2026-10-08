"""Staff profiles for the Agent / Kassir Mini Apps: own photo, display name and phone."""
import re
import time

ROLE_LABELS={'agent':'Agent','cashier':'Kassir','admin':'Rahbar'}
_PHONE=re.compile(r'\+?[0-9][0-9 ()-]{6,22}')


def _row(db,uid):
    return db.execute('SELECT photo,phone,updated_ts FROM user_profiles WHERE user_id=?',(int(uid),)).fetchone()


def photo_file_id(db,uid):
    r=_row(db,uid)
    return (r['photo'] if r else '') or ''


def photo_ids(db,ids=None):
    """{user_id: True} for staff with a profile photo (used to attach signed photo links)."""
    rows=db.execute("SELECT user_id FROM user_profiles WHERE photo<>''").fetchall()
    out={int(r['user_id']) for r in rows}
    if ids is not None:out&={int(x) for x in ids}
    return out


def photo_versions(db):
    """{user_id: updated_ts} for staff with a profile photo (cache-busting version for links)."""
    return {int(r['user_id']):int(r['updated_ts'] or 0)
            for r in db.execute("SELECT user_id,updated_ts FROM user_profiles WHERE photo<>''").fetchall()}


def get(db,uid):
    u=db.execute('SELECT id,role,name FROM users WHERE id=?',(int(uid),)).fetchone()
    if not u:raise ValueError('Foydalanuvchi topilmadi.')
    r=_row(db,uid)
    return {'id':int(u['id']),'role':u['role'],'roleLabel':ROLE_LABELS.get(u['role'],u['role']),
            'name':u['name'] or str(u['id']),'phone':(r['phone'] if r else '') or '',
            'hasPhoto':bool(r and r['photo']),'updatedTs':int(r['updated_ts']) if r else 0}


def save(db,uid,payload,photo_file=None,now=None):
    """Update the caller's own name / phone and (optionally) photo file_id. Returns the fresh profile."""
    now=int(time.time() if now is None else now)
    if not db.execute('SELECT 1 FROM users WHERE id=?',(int(uid),)).fetchone():
        raise ValueError('Foydalanuvchi topilmadi.')
    payload=payload if isinstance(payload,dict) else {}
    if 'name' in payload:
        name=re.sub(r'\s+',' ',str(payload.get('name') or '')).strip()
        if not 2<=len(name)<=60:raise ValueError('Ism 2–60 belgidan iborat bo‘lsin.')
        db.execute('UPDATE users SET name=? WHERE id=?',(name,int(uid)))
    cur=_row(db,uid)
    phone=(cur['phone'] if cur else '') or ''
    photo=(cur['photo'] if cur else '') or ''
    if 'phone' in payload:
        phone=str(payload.get('phone') or '').strip()
        if phone and not _PHONE.fullmatch(phone):raise ValueError('Telefon raqami noto‘g‘ri. Masalan: +998 90 123 45 67')
    if payload.get('removePhoto'):photo=''
    if photo_file:photo=str(photo_file)
    db.execute('''INSERT INTO user_profiles(user_id,photo,phone,updated_ts) VALUES(?,?,?,?)
        ON CONFLICT(user_id) DO UPDATE SET photo=excluded.photo,phone=excluded.phone,updated_ts=excluded.updated_ts''',
        (int(uid),photo,phone,now))
    return get(db,uid)
