"""Xodimlar boshqaruvi (web panel): rollar, qo'shish, nom, akkaunt almashtirish, yopish/ochish, web login.

Mavjud qoidalar saqlanadi:
- agent va kassir uchun core'dagi tayyor funksiyalar ishlatiladi (smena, qoldiq tekshiruvlari bilan);
- admin qo'shish, akkaunt almashtirish, yopish va web login/parol — faqat asosiy rahbar (ADMINS) huquqi;
- xodim qo'shish va nomini o'zgartirish — har qanday rahbar (botdagi «➕ Ходим» bilan bir xil).
Savdo roli — Savdo Mini App (shop.py). Sex ishchilari tizimdan foydalanmaydi — ular hr.py da.
"""
import time

import core
import web_auth

ROLES = {
    'admin': 'Admin',
    'sales': 'Savdo',
    'cashier': 'Kassir',
    'agent': 'Agent',
    'warehouse': 'Ombor',
}
# Yopilgan holat nomlari (agent va kassir uchun eski nomlar saqlanadi)
DISABLED = {'agent': 'disabled', 'cashier': 'cashier_disabled', 'admin': 'admin_disabled',
            'sales': 'sales_disabled', 'warehouse': 'warehouse_disabled'}
ACTIVE_OF = {v: k for k, v in DISABLED.items()}
GENERIC = ('sales', 'warehouse')   # alohida qoidasi yo'q rollar


def _audit(db, actor, old_id, new_id, action):
    db.execute('INSERT INTO role_audit(actor,old_id,new_id,action,ts) VALUES(?,?,?,?,?)',
               (actor, old_id, new_id, action, int(time.time())))


def _user(db, uid):
    return db.execute('SELECT id,name,role FROM users WHERE id=?', (uid,)).fetchone()


def _role_of(row):
    r = row['role']
    return (r, True) if r in ROLES else (ACTIVE_OF.get(r), False)


def staff_list(db, primary_admins=()):
    accounts = {int(r['user_id']): r['login'] for r in db.execute('SELECT user_id,login FROM web_accounts').fetchall()}
    roles = tuple(ROLES) + tuple(DISABLED.values())
    marks = ','.join('?' * len(roles))
    out = []
    for r in db.execute(f'SELECT id,name,role FROM users WHERE role IN ({marks}) ORDER BY name,id', roles).fetchall():
        role, active = _role_of(r)
        uid = int(r['id'])
        out.append({'id': uid, 'name': r['name'] or str(uid), 'role': role, 'roleLabel': ROLES[role],
                    'active': active, 'primary': uid in primary_admins, 'webLogin': accounts.get(uid) or ''})
    return {'staff': out, 'roles': [{'key': k, 'label': v} for k, v in ROLES.items()]}


def add(db, actor, role, uid, name):
    if role not in ROLES:
        raise ValueError('Rol noto‘g‘ri.')
    uid = core._telegram_id(uid)
    name = core._staff_name(name, 'Xodim ismi')
    if role == 'agent':
        return core.add_agent(db, actor, uid, name)
    if role == 'cashier':
        return core.add_cashier(db, actor, uid, name)
    if role == 'admin':
        return core.add_or_promote_admin(db, actor, uid, name)
    core._require_admin(db, actor)
    row = _user(db, uid)
    if row and row['role'] != DISABLED[role]:
        raise ValueError('Bu Telegram ID avval ro‘yxatdan o‘tgan. Boshqa ID kiriting.')
    if row:
        db.execute('UPDATE users SET role=?,name=? WHERE id=?', (role, name, uid))
    else:
        db.execute('INSERT INTO users(id,role,name) VALUES(?,?,?)', (uid, role, name))
    _audit(db, actor, None, uid, role + '_created')
    return uid


def rename(db, actor, uid, name):
    core._require_admin(db, actor)
    uid = core._telegram_id(uid)
    name = core._staff_name(name, 'Yangi ism')
    row = _user(db, uid)
    if not row or row['role'] not in ROLES:
        raise ValueError('Faol xodim topilmadi.')
    if row['role'] == 'agent':
        return core.rename_agent(db, actor, uid, name)
    if row['name'] == name:
        raise ValueError('Ism o‘zgarmagan.')
    db.execute('UPDATE users SET name=? WHERE id=?', (name, uid))
    _audit(db, actor, uid, uid, row['role'] + '_renamed')
    return name


def transfer(db, actor, uid, new_id, primary_admins=()):
    """Xodim rolini yangi Telegram akkauntga o'tkazish; eski akkaunt yopiladi, tarix saqlanadi."""
    core._require_admin(db, actor)
    uid = core._telegram_id(uid)
    new_id = core._telegram_id(new_id)
    row = _user(db, uid)
    if not row or row['role'] not in ROLES:
        raise ValueError('Faol xodim topilmadi.')
    role = row['role']
    if role == 'agent':
        return core.transfer_agent_account(db, actor, uid, new_id)
    if role == 'cashier':
        return core.transfer_cashier_account(db, actor, uid, new_id)
    if role == 'admin':
        raise ValueError('Admin akkauntini almashtirish o‘rniga yangi admin qo‘shing va eskisini yoping.')
    if uid == new_id:
        raise ValueError('Yangi ID eskisidan farq qilsin.')
    other = _user(db, new_id)
    if other and other['role'] != DISABLED[role]:
        raise ValueError('Yangi Telegram ID avval ro‘yxatdan o‘tgan.')
    if other:
        db.execute('UPDATE users SET role=?,name=? WHERE id=?', (role, row['name'], new_id))
    else:
        db.execute('INSERT INTO users(id,role,name) VALUES(?,?,?)', (new_id, role, row['name']))
    db.execute('UPDATE users SET role=? WHERE id=?', (DISABLED[role], uid))
    web_auth.revoke(db, uid)
    _audit(db, actor, uid, new_id, role + '_transferred')
    return new_id


def deactivate(db, actor, uid, primary_admins=()):
    core._require_admin(db, actor)
    uid = core._telegram_id(uid)
    row = _user(db, uid)
    if not row or row['role'] not in ROLES:
        raise ValueError('Faol xodim topilmadi.')
    role = row['role']
    if role == 'agent':
        return core.deactivate_agent(db, actor, uid)
    if role == 'cashier':
        return core.deactivate_cashier(db, actor, uid)
    if role == 'admin':
        if uid in primary_admins:
            raise ValueError('Asosiy rahbarni paneldan yopib bo‘lmaydi (server sozlamasida belgilangan).')
        if uid == actor:
            raise ValueError('O‘zingizni yopib bo‘lmaydi.')
        # role() yopilgan ikkinchi adminni qayta tiklamasin
        db.execute('DELETE FROM meta WHERE key=?', (f'secondary_admin:{uid}',))
    db.execute('UPDATE users SET role=? WHERE id=?', (DISABLED[role], uid))
    db.execute('DELETE FROM sessions WHERE agent=?', (uid,))
    web_auth.revoke(db, uid)
    _audit(db, actor, uid, None, role + '_deactivated')


def activate(db, actor, uid):
    core._require_admin(db, actor)
    uid = core._telegram_id(uid)
    row = _user(db, uid)
    role = ACTIVE_OF.get(row['role']) if row else None
    if not role:
        raise ValueError('Yopilgan xodim topilmadi.')
    if role == 'cashier':
        return core.activate_cashier(db, actor, uid)
    db.execute('UPDATE users SET role=? WHERE id=?', (role, uid))
    if role == 'admin':
        db.execute("INSERT INTO meta(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                   (f'secondary_admin:{uid}', '1'))
    _audit(db, actor, None, uid, role + '_activated')


def issue_login(db, actor, uid, login=None):
    """Web panel login/parol: panel faqat rahbarlar uchun, shuning uchun faqat faol admin akkauntiga beriladi."""
    core._require_admin(db, actor)
    uid = core._telegram_id(uid)
    row = _user(db, uid)
    if not row or row['role'] != 'admin':
        raise ValueError('Web panelga faqat faol admin kira oladi. Boshqa xodimlar Telegram ilovasi orqali ishlaydi.')
    return web_auth.issue_password(db, uid, (login or '').strip() or None)


def revoke_login(db, actor, uid):
    core._require_admin(db, actor)
    uid = core._telegram_id(uid)
    if not web_auth.account(db, uid):
        raise ValueError('Bu xodimning web logini yo‘q.')
    web_auth.revoke(db, uid)
