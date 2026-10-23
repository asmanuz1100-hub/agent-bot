"""Xodim ruxsatlari: rol bo'yicha standart + har bir xodimga individual o'zgartirish.

Amal bajarilishi uchun uchala shart kerak: korxona bo'limi yoqiq (modules.py), xodimda ruxsat bor
(shu modul) va ma'lumot uning doirasida. Doira: bitta kassa va bitta ombor bor, shuning uchun kassa va
ombor amallari «butun korxona»; agent faqat o'z mijozlari (agent_api allaqachon cheklaydi); savdo
xodimi «Barcha sotuvlarni ko'rish»siz faqat o'z sotuvlarini ko'radi (shop.py). Filial modeli yo'q —
filial doirasi taklif qilinmaydi.

Rollar: Admin = asosiy rahbar (server ADMIN_IDS) — barcha huquq, o'zgartirib bo'lmaydi, shuning uchun
«oxirgi admin» huquqsiz qolmaydi. Rahbar = ikkinchi darajali admin. Kassir, Omborchi — shu yerda.
Sotuvchi ruxsatlari shop.py (shop_staff.perms), agent funksiyalari core.agent_features da saqlanadi —
ikki marta saqlanmasin deb bu yerda faqat ko'rsatiladi.

Ruxsat har so'rovda bazadan o'qiladi: o'zgarish ochiq sessiyalarda ham darhol kuchga kiradi.
"""
import time

from core import PostgresDB

# kalit: (bo'lim, nom)
CATALOG={
    'cash.view':('cash','Kassani ko‘rish'),
    'cash.handover':('cash','Agent topshirig‘ini va karta to‘lovini tasdiqlash'),
    'cash.expense':('cash','Xarajat'),
    'cash.convert':('cash','Konvertatsiya'),
    'cash.rate':('cash','Kassa kursini belgilash'),
    'cash.fund':('cash','Agent xarajat hisobini to‘ldirish'),
    'cash.debt_task':('cash','Qarz undirish topshirig‘i'),
    'cash.report':('cash','Kassa hisoboti va eksport'),
    'cash.income':('cash','Qo‘lda kirim'),
    'cash.transfer':('cash','Hisoblar orasida o‘tkazma (naqd, karta, bank)'),
    'cash.cancel':('cash','Kirim/o‘tkazmani bekor qilish'),
    'cash.close':('cash','Kunni yopish (pulni sanash)'),
    'warehouse.view':('warehouse','Omborni ko‘rish'),
    'warehouse.receive':('warehouse','Kirim'),
    'warehouse.issue':('warehouse','Chiqim: agentga berish, qaytarish, so‘rovlar, buyurtma holati'),
    'warehouse.writeoff':('warehouse','Brak / hisobdan chiqarish'),
    'warehouse.catalog':('warehouse','Katalog: mahsulot qo‘shish, narx, rasm'),
    'warehouse.supply':('warehouse','Ta’minot: xarid, xom ashyo, ishlab chiqarish'),
    'warehouse.supply_pay':('warehouse','Ta’minotchiga kassadan to‘lov'),
    'hr.view':('hr','Ishchilar ro‘yxati va davomat'),
    'hr.salary_view':('hr','Oylik summalarini ko‘rish'),
    'hr.edit':('hr','Ishchi qo‘shish/tahrirlash, davomat'),
    'hr.calculate':('hr','Bonus va jarima'),
    'hr.pay':('hr','Avans va oylik to‘lash (kassadan)'),
    'reports.view':('reports','Hisobot va tahlil'),
    'reports.export':('reports','Mijozlar va hisobotni eksport'),
    'staff.manage':('staff','Xodim qo‘shish va nomini o‘zgartirish'),
}
SECTIONS={'cash':'Kassa','warehouse':'Ombor','hr':'Xodimlar va oylik','reports':'Hisobot va tahlil','staff':'Xodimlar'}
EDITABLE_ROLES=('admin','cashier','warehouse')     # admin bu yerda = ikkinchi darajali rahbar
# Rol — boshlang'ich to'plam (DEFAULTS). Admin unga boshqa bo'limdan ham ruxsat qo'sha oladi, lekin faqat
# oxirigacha ishlaydiganini: ilovaga kirish, API va ichki tekshiruv shu ruxsat bilan ochiladi (open_section).
# Ro'yxatda yo'q ruxsat bu rolda hali ishlamaydi — ko'rsatilmaydi va saqlanmaydi (soxta tugma bo'lmasin).
GRANTABLE={
    'admin':frozenset(CATALOG),
    'cashier':frozenset(k for k,v in CATALOG.items() if v[0]=='cash')|{'warehouse.view'},
    'warehouse':frozenset(k for k,v in CATALOG.items() if v[0]=='warehouse')|{'cash.view','cash.report'},
}
# Boshqa bo'lim ilovasini qaysi ruxsat bilan ochadi: (rol, bo'lim) -> ruxsat
CROSS_OPEN={('cashier','warehouse'):'warehouse.view',('warehouse','cash'):'cash.view'}
ROLE_LABELS={'primary':'Admin','admin':'Rahbar','cashier':'Kassir','warehouse':'Omborchi','sales':'Sotuvchi','agent':'Agent'}

# Standart huquqlar hozirgi xatti-harakatni saqlaydi: rahbar ombor/ta'minot/oylik pul amallarini
# kiritmaydi (avval ham faqat asosiy rahbar kiritardi), lekin admin ularni alohida berishi mumkin.
DEFAULTS={
    'admin':{'cash.view','cash.handover','cash.expense','cash.convert','cash.rate','cash.fund','cash.debt_task','cash.report',
             'warehouse.view','warehouse.catalog','hr.view','hr.salary_view','hr.edit','reports.view','reports.export','staff.manage'},
    'cashier':{'cash.view','cash.handover','cash.expense','cash.convert','cash.rate','cash.fund','cash.debt_task','cash.report',
               'cash.income','cash.transfer','cash.close'},
    # omborchi avvaldan Ombor ilovasida mahsulot rasmini yuklaydi (catalog) — saqlanadi
    'warehouse':{'warehouse.view','warehouse.receive','warehouse.issue','warehouse.writeoff','warehouse.catalog'},
}

SCHEMA='''
CREATE TABLE IF NOT EXISTS user_perms(user_id INTEGER NOT NULL, perm TEXT NOT NULL, allowed INTEGER NOT NULL, actor INTEGER, ts INTEGER NOT NULL, PRIMARY KEY(user_id,perm));
CREATE TABLE IF NOT EXISTS perm_audit(id INTEGER PRIMARY KEY, actor INTEGER NOT NULL, target INTEGER NOT NULL, perm TEXT NOT NULL, before TEXT NOT NULL, after TEXT NOT NULL, ts INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS idx_perm_audit_target ON perm_audit(target,ts);
'''
PG_SCHEMA=SCHEMA.replace('INTEGER PRIMARY KEY','BIGSERIAL PRIMARY KEY').replace(' INTEGER',' BIGINT')


def init(db):
    if isinstance(db,PostgresDB):
        for stmt in PG_SCHEMA.split(';'):
            if stmt.strip():db.execute(stmt)
    else:
        db.executescript(SCHEMA)


class Denied(ValueError):
    """Ruxsat yo'q: HTTP 403, tushunarli matn."""


def _role(db,uid):
    row=db.execute('SELECT role FROM users WHERE id=?',(uid,)).fetchone()
    return row[0] if row else None


def effective(db,uid,primary=()):
    """Xodimning hozirgi ruxsatlari (to'plam)."""
    if uid in primary:return set(CATALOG)
    role=_role(db,uid)
    out=set(DEFAULTS.get(role,()))
    for r in db.execute('SELECT perm,allowed FROM user_perms WHERE user_id=?',(uid,)).fetchall():
        if r['perm'] not in CATALOG:continue
        if int(r['allowed']):out.add(r['perm'])
        else:out.discard(r['perm'])
    return out


def open_section(db,uid,section,primary=()):
    """Boshqa rol xodimi shu bo'lim ilovasiga kira oladimi (masalan, kassir omborni ko'rish uchun)."""
    need=CROSS_OPEN.get((_role(db,uid),section))
    return bool(need) and has(db,uid,need,primary)


def has(db,uid,perm,primary=()):
    return perm in effective(db,uid,primary)


def require(db,uid,perm,primary=()):
    if perm and not has(db,uid,perm,primary):
        raise Denied(f"Sizda «{CATALOG[perm][1]}» ruxsati yo‘q. Admin Xodimlar bo‘limida beradi.")


def set_perms(db,actor,target,changes,primary=(),now=None):
    """changes: {perm: True|False|None}; None — rol standartiga qaytarish. Faqat Admin (asosiy rahbar)."""
    if actor not in primary:raise Denied('Ruxsatlarni faqat Admin (asosiy rahbar) o‘zgartiradi.')
    try:target=int(target)
    except (TypeError,ValueError):raise ValueError('Xodim noto‘g‘ri.')
    if target==actor:raise Denied('O‘zingizga huquq bera olmaysiz.')
    if target in primary:raise Denied('Admin (asosiy rahbar) huquqlari to‘liq va o‘zgarmaydi.')
    role=_role(db,target)
    if role not in EDITABLE_ROLES:
        raise ValueError('Bu xodimning ruxsatlari o‘z bo‘limida: sotuvchi — Xodimlar → Savdo jamoasi, agent — agent kartasi.')
    if not isinstance(changes,dict) or any(p not in CATALOG for p in changes):raise ValueError('Ruxsatlar noto‘g‘ri.')
    bad=[p for p in changes if p not in GRANTABLE[role]]
    if bad:
        raise ValueError(f"«{CATALOG[bad[0]][1]}» ruxsati {ROLE_LABELS[role].lower()} rolida hozircha ishlamaydi. "
                         'Bunday ish uchun xodimga mos rol bering.')
    ts=int(time.time() if now is None else now)
    before=effective(db,target,primary)
    for perm,val in changes.items():
        if val is None:
            db.execute('DELETE FROM user_perms WHERE user_id=? AND perm=?',(target,perm))
        else:
            db.execute('''INSERT INTO user_perms(user_id,perm,allowed,actor,ts) VALUES(?,?,?,?,?)
                ON CONFLICT(user_id,perm) DO UPDATE SET allowed=excluded.allowed,actor=excluded.actor,ts=excluded.ts''',
                       (target,perm,1 if val else 0,actor,ts))
    after=effective(db,target,primary)
    for perm in sorted(before^after):
        db.execute('INSERT INTO perm_audit(actor,target,perm,before,after,ts) VALUES(?,?,?,?,?,?)',
                   (actor,target,perm,'1' if perm in before else '0','1' if perm in after else '0',ts))
    return after


# ---------- kirish yo'llari ----------
# Web — login/parol (web_auth) bor-yo'qligi. Telegram Mini App — alohida yoqiladi/o'chiriladi (standart: yoqiq).
# Bu ruxsat katalogda emas (bo'lim huquqi emas): faqat qaysi yo'l bilan kirishni belgilaydi.
MINIAPP='access.miniapp'
MINIAPP_OFF='Telegram ilovasi orqali kirish o‘chirilgan. Admin Xodimlar bo‘limida yoqadi.'


def miniapp_allowed(db,uid):
    row=db.execute('SELECT allowed FROM user_perms WHERE user_id=? AND perm=?',(uid,MINIAPP)).fetchone()
    return row is None or bool(int(row[0]))


def set_miniapp(db,actor,target,on,primary=(),now=None):
    if actor not in primary:raise Denied('Kirish yo‘llarini faqat Admin (asosiy rahbar) o‘zgartiradi.')
    try:target=int(target)
    except (TypeError,ValueError):raise ValueError('Xodim noto‘g‘ri.')
    if target==actor or target in primary:raise Denied('Admin (asosiy rahbar) kirishi o‘chirilmaydi.')
    if _role(db,target) is None:raise ValueError('Xodim topilmadi.')
    on=bool(on)
    if miniapp_allowed(db,target)==on:return on
    ts=int(time.time() if now is None else now)
    if on:db.execute('DELETE FROM user_perms WHERE user_id=? AND perm=?',(target,MINIAPP))
    else:db.execute('INSERT INTO user_perms(user_id,perm,allowed,actor,ts) VALUES(?,?,0,?,?)',(target,MINIAPP,actor,ts))
    db.execute('INSERT INTO perm_audit(actor,target,perm,before,after,ts) VALUES(?,?,?,?,?,?)',
               (actor,target,MINIAPP,'0' if on else '1','1' if on else '0',ts))
    return on


def staff_view(db,uid,primary=()):
    role=_role(db,uid)
    if role is None:raise ValueError('Xodim topilmadi.')
    eff=effective(db,uid,primary)
    overrides={r['perm']:bool(int(r['allowed'])) for r in db.execute('SELECT perm,allowed FROM user_perms WHERE user_id=?',(uid,)).fetchall()}
    key='primary' if uid in primary else role
    hist=[{'perm':r['perm'],'label':'Telegram Mini App orqali kirish' if r['perm']==MINIAPP else CATALOG.get(r['perm'],('',r['perm']))[1],'on':r['after']=='1','who':r['who'],'ts':int(r['ts'])}
          for r in db.execute('''SELECT a.*,COALESCE(u.name,CAST(a.actor AS TEXT)) AS who FROM perm_audit a
              LEFT JOIN users u ON u.id=a.actor WHERE a.target=? ORDER BY a.ts DESC,a.id DESC LIMIT 40''',(uid,)).fetchall()]
    return {'id':int(uid),'role':key,'roleLabel':ROLE_LABELS.get(key,role),'editable':key in EDITABLE_ROLES,
            'perms':[{'key':k,'section':v[0],'sectionLabel':SECTIONS[v[0]],'label':v[1],'on':k in eff,
                      'default':k in DEFAULTS.get(role,()) or key=='primary','override':overrides.get(k)} for k,v in CATALOG.items()
                     if k in GRANTABLE.get(role,CATALOG)],
            'history':hist,'miniapp':miniapp_allowed(db,uid)}


# ---------- amal -> ruxsat ----------

def manager_perm(action,op=None,kind=None):
    """/api/manager amali uchun kerakli ruxsat (None — rahbar paneliga kirgan har kim)."""
    action=str(action or '');op=str(op or '')
    if action=='cash_period':return 'cash.view'
    if action=='cashbook':
        return {'income':'cash.income','expense':'cash.expense','transfer':'cash.transfer','cancel':'cash.cancel','close':'cash.close'}.get(op,'cash.view')
    if action in ('cashier_add','cashier_rename','staff_add','staff_rename','agent_add_preview','agent_add_commit',
                  'agent_rename_preview','agent_rename_commit'):return 'staff.manage'
    if action=='stock':
        return {'dashboard':'warehouse.view','moves':'warehouse.view','receive':'warehouse.receive','writeoff':'warehouse.writeoff'}.get(op,'warehouse.issue')
    if action in ('warehouse',):return 'warehouse.view'
    if action=='order_status':return 'warehouse.issue'
    if action in ('product_add','product_update','product_photo','custom_map'):return 'warehouse.catalog'
    if action=='supply':
        if op in ('dashboard','ledger',''):return 'warehouse.view'
        return 'warehouse.supply_pay' if op=='pay' else 'warehouse.supply'
    if action=='hr':
        if op=='pay_add':return 'hr.calculate' if kind in ('bonus','penalty') else 'hr.pay'
        return {'overview':'hr.view','worker':'hr.view'}.get(op,'hr.edit')
    if action in ('period_report','insights','ai_ask'):return 'reports.view'
    if action in ('client_export','all_clients_export'):return 'reports.export'
    return None


CASHIER_ACTION={'dashboard':'cash.view','review':'cash.view','handover_detail':'cash.view','report':'cash.report',
                'accept':'cash.handover','reject':'cash.handover','card_confirm':'cash.handover','card_reject':'cash.handover',
                'expense':'cash.expense','convert':'cash.convert','rate':'cash.rate','fund':'cash.fund','assign_debt':'cash.debt_task'}
WAREHOUSE_ACTION={'dashboard':'warehouse.view','orders':'warehouse.view','moves':'warehouse.view','receive':'warehouse.receive',
                  'writeoff':'warehouse.writeoff','issue':'warehouse.issue','decide':'warehouse.issue','take_back':'warehouse.issue',
                  'order_status':'warehouse.issue'}


def strip_salary(data):
    """«Oylik summalarini ko'rish» ruxsati yo'q bo'lsa pul ma'lumotini javobdan olib tashlaydi."""
    def clean(w):
        for k in ('payroll','payments','salary','salaryHistory'):w.pop(k,None)
    if isinstance(data.get('workers'),list):
        for w in data['workers']:clean(w)
    data.pop('money',None)
    if isinstance(data.get('worker'),dict):clean(data['worker'])
    data['salaryHidden']=True
    return data
