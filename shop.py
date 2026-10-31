"""Savdo (do'kon / ombor savdosi) hisobi — Bito «Sotuv» formulasi asosida.

Xodimlar (`users.role='sales'`, soni cheklanmagan). Har bir xodimning funksiyalarini rahbar alohida
yoqadi/o'chiradi (`shop_staff.perms`, PERMS ro'yxati). Eski ikki daraja ruxsatlar to'plamiga aylantiriladi:
- seller (ombor sotuvchisi): chakana narxda sotadi, limitgacha chegirma beradi, ruxsat bo'lsa qarzga beradi,
  naqd/karta pul oladi va kassaga topshiradi;
- head (bosh savdo xodimi): hamma narsa — diller/chakana mijozlar, istalgan narx va chegirma,
  narxlarni belgilash, mijozga maxsus narx, qarzga berish, qarz undirish.

Sotuv formulasi (Bito bilan bir xil):
  Jami narx = Σ miqdor × narx;  Jami chegirma = savdo chegirmasi;
  To'lanishi kerak = Jami narx − Jami chegirma;  Qoldiq (qarz) = To'lanishi kerak − To'langan.
Chegirma qatorlarga summa bo'yicha proporsional taqsimlanadi (qaytarish asl partiya narxida bo'lishi uchun).

Mavjud hisob bilan yagona manba: har bir sotuv qatori `events`ga 'delivery' (mijoz USD qarzi) va
'sold' (mijozda tovar qolmaydi) bo'lib yoziladi, ombor qoldig'i `warehouse_moves`dagi 'shop_sale'
bilan kamayadi, to'lov — 'payment'. Shuning uchun qarz, akt sverka, Rahbar Web, kassa avtomatik mos.
Sotuvchi qo'lidagi pul `core.cash_usd`/`core.cash` bilan hisoblanadi va `core.handover` orqali kassaga topshiriladi.
"""
import hashlib
import time

import branding
import core
import warehouse as wh
import receipt_public

LEVELS = ('seller', 'head')
# Rahbar har bir savdo xodimi uchun alohida yoqadigan funksiyalar.
PERMS = {
    'retail': 'Chakana sotuv',
    'dealer': 'Diller sotuvi',
    'discount': 'Chegirma',
    'price': 'Narxni o‘zgartirish',
    'credit': 'Qarzga berish',
    'collect': 'Qarz undirish',
    'clients': 'Mijoz qo‘shish',
    'prices': 'Narxlar ro‘yxati',
    'special': 'Maxsus narx',
    'all_sales': 'Barcha sotuvlarni ko‘rish',
}
SELLER_PERMS = ('retail', 'discount', 'credit', 'collect', 'clients')
PRICE_TYPES = ('retail', 'dealer')
METHODS = ('cash_usd', 'cash_uzs', 'card')
NOT_VOID = "NOT EXISTS(SELECT 1 FROM voids v WHERE v.kind='sale' AND v.ref=shop_sales.id)"
DEFAULT_MAX_DISCOUNT_PCT = 5
WALKIN_NAME = 'Chakana xaridor'

SCHEMA = '''
CREATE TABLE IF NOT EXISTS shop_staff(user_id INTEGER PRIMARY KEY, level TEXT NOT NULL DEFAULT 'seller', max_discount_pct INTEGER NOT NULL DEFAULT 5, allow_credit INTEGER NOT NULL DEFAULT 1, walkin_client INTEGER, perms TEXT);
CREATE TABLE IF NOT EXISTS shop_prices(pack INTEGER PRIMARY KEY, retail INTEGER NOT NULL DEFAULT 0, dealer INTEGER NOT NULL DEFAULT 0, updated_by INTEGER, updated_ts INTEGER);
CREATE TABLE IF NOT EXISTS shop_client_prices(client INTEGER NOT NULL, pack INTEGER NOT NULL, price INTEGER NOT NULL, updated_by INTEGER, updated_ts INTEGER, PRIMARY KEY(client,pack));
CREATE TABLE IF NOT EXISTS shop_clients(client INTEGER PRIMARY KEY, price_type TEXT NOT NULL DEFAULT 'retail');
CREATE TABLE IF NOT EXISTS shop_sales(id INTEGER PRIMARY KEY, seller INTEGER NOT NULL, client INTEGER NOT NULL, price_type TEXT NOT NULL, subtotal INTEGER NOT NULL, discount INTEGER NOT NULL DEFAULT 0, total INTEGER NOT NULL, paid INTEGER NOT NULL DEFAULT 0, pay_method TEXT NOT NULL DEFAULT '', paid_uzs INTEGER NOT NULL DEFAULT 0, fx_rate INTEGER NOT NULL DEFAULT 0, note TEXT NOT NULL DEFAULT '', ts INTEGER NOT NULL, source INTEGER NOT NULL UNIQUE);
CREATE TABLE IF NOT EXISTS shop_sale_lines(id INTEGER PRIMARY KEY, sale INTEGER NOT NULL, pack INTEGER NOT NULL, qty INTEGER NOT NULL, list_price INTEGER NOT NULL, price INTEGER NOT NULL, discount INTEGER NOT NULL DEFAULT 0, total INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS idx_shop_sales_seller_ts ON shop_sales(seller,ts);
CREATE INDEX IF NOT EXISTS idx_shop_sales_client ON shop_sales(client,ts);
CREATE INDEX IF NOT EXISTS idx_shop_sale_lines_sale ON shop_sale_lines(sale);
'''
PG_SCHEMA = SCHEMA.replace('INTEGER PRIMARY KEY', 'BIGSERIAL PRIMARY KEY').replace(' INTEGER', ' BIGINT')


def init(db):
    if isinstance(db, core.PostgresDB):
        for stmt in PG_SCHEMA.split(';'):
            if stmt.strip():
                db.execute(stmt)
    else:
        db.executescript(SCHEMA)
    # Birinchi versiyada perms ustuni yo'q edi.
    if isinstance(db, core.PostgresDB):
        db.execute('ALTER TABLE shop_staff ADD COLUMN IF NOT EXISTS perms TEXT')
    elif 'perms' not in [r[1] for r in db.execute('PRAGMA table_info(shop_staff)').fetchall()]:
        db.execute('ALTER TABLE shop_staff ADD COLUMN perms TEXT')
    # Qo'shimcha xarajat (yetkazish va h.k.) — mijozga qo'shiladi, qatorlarga taqsimlanadi.
    for col, typ in (('extra', 'INTEGER NOT NULL DEFAULT 0'), ('extra_name', "TEXT NOT NULL DEFAULT ''")):
        if isinstance(db, core.PostgresDB):
            db.execute(f'ALTER TABLE shop_sales ADD COLUMN IF NOT EXISTS {col} {typ.replace("INTEGER", "BIGINT")}')
        elif col not in [r[1] for r in db.execute('PRAGMA table_info(shop_sales)').fetchall()]:
            db.execute(f'ALTER TABLE shop_sales ADD COLUMN {col} {typ}')


# ---------- yordamchilar ----------

def _int(value, label, lo=0, hi=10 ** 12):
    if isinstance(value, bool):
        raise ValueError(f'{label} noto‘g‘ri.')
    try:
        n = int(str(value).strip()) if isinstance(value, str) else int(value)
    except (TypeError, ValueError):
        raise ValueError(f'{label} noto‘g‘ri.')
    if not isinstance(value, (int, str)) or not lo <= n <= hi:
        raise ValueError(f'{label} noto‘g‘ri.')
    return n


def _cents(value, label, allow_zero=False):
    if value in (None, '') and allow_zero:
        return 0
    if isinstance(value, bool):
        raise ValueError(f'{label} noto‘g‘ri.')
    if isinstance(value, int) and allow_zero and value == 0:
        return 0
    if allow_zero and str(value).strip() in ('0', '0.0', '0.00'):
        return 0
    try:
        return core.money(value)
    except ValueError:
        raise ValueError(f'{label}: musbat summa kiriting (ko‘pi bilan 2 kasr).')


def _source(actor, request_id, index=0):
    rid = str(request_id or '').strip()
    if not 8 <= len(rid) <= 80:
        raise ValueError('So‘rov ID noto‘g‘ri. Ilovani yangilang.')
    raw = f'shop:{int(actor)}:{rid}:{index}'.encode()
    # agent_api manfiy, Telegram update musbat kichik sonlar: savdo — katta musbat diapazon.
    return 10 ** 16 + int.from_bytes(hashlib.sha256(raw).digest()[:7], 'big')


def _perms_of(row):
    if row is None:
        return set(SELLER_PERMS)
    raw = row['perms']
    if raw is None:   # eski yozuv: darajadan
        if row['level'] == 'head':
            return set(PERMS)
        base = set(SELLER_PERMS)
        if not int(row['allow_credit'] if row['allow_credit'] is not None else 1):
            base.discard('credit')
        return base
    return {p for p in str(raw).split(',') if p in PERMS}


def staff(db, uid):
    """{'perms','maxDiscountPct',...} yoki None. Rahbar — barcha funksiyalar."""
    row = db.execute('SELECT role,name FROM users WHERE id=?', (uid,)).fetchone()
    if not row or row[0] not in ('sales', 'admin'):
        return None
    if row[0] == 'admin':
        perms = set(PERMS)
        pct = 100
    else:
        s = db.execute('SELECT level,max_discount_pct,allow_credit,perms FROM shop_staff WHERE user_id=?', (uid,)).fetchone()
        perms = _perms_of(s)
        pct = int(s['max_discount_pct']) if s and s['max_discount_pct'] is not None else DEFAULT_MAX_DISCOUNT_PCT
        if 'discount' not in perms:
            pct = 0
    return {'id': int(uid), 'name': row[1] or str(uid), 'role': row[0], 'perms': sorted(perms),
            'maxDiscountPct': pct, 'allowCredit': 'credit' in perms,
            'level': 'head' if row[0] == 'admin' or perms == set(PERMS) else 'seller'}


def can(s, perm):
    return perm in s['perms']


def _require(db, actor, perm=None):
    s = staff(db, actor)
    if not s:
        raise ValueError('Savdo bo‘limiga ruxsat yo‘q.')
    if perm and not can(s, perm):
        raise ValueError(f'Sizda «{PERMS[perm]}» ruxsati yo‘q. Rahbarga murojaat qiling.')
    return s


def set_staff(db, actor, uid, perms, max_discount_pct=DEFAULT_MAX_DISCOUNT_PCT):
    """Faqat rahbar: savdo xodimining funksiyalarini yoqish/o'chirish va chegirma limiti."""
    a = db.execute('SELECT role FROM users WHERE id=?', (actor,)).fetchone()
    if not a or a[0] != 'admin':
        raise ValueError('Savdo xodimlarining ruxsatlarini faqat rahbar o‘zgartiradi.')
    target = db.execute('SELECT role FROM users WHERE id=?', (uid,)).fetchone()
    if not target or target[0] != 'sales':
        raise ValueError('Savdo xodimi topilmadi.')
    if isinstance(perms, str):
        perms = [p for p in perms.split(',') if p]
    if not isinstance(perms, (list, tuple, set)) or any(p not in PERMS for p in perms):
        raise ValueError('Ruxsatlar noto‘g‘ri.')
    pct = _int(max_discount_pct, 'Chegirma limiti', 0, 100)
    perms = sorted(set(perms))
    level = 'head' if set(perms) == set(PERMS) else 'seller'
    db.execute('''INSERT INTO shop_staff(user_id,level,max_discount_pct,allow_credit,perms) VALUES(?,?,?,?,?)
        ON CONFLICT(user_id) DO UPDATE SET level=excluded.level,max_discount_pct=excluded.max_discount_pct,
        allow_credit=excluded.allow_credit,perms=excluded.perms''', (uid, level, pct, 1 if 'credit' in perms else 0, ','.join(perms)))


# ---------- narxlar ----------

def prices(db):
    rows = {int(r['pack']): r for r in db.execute('SELECT pack,retail,dealer FROM shop_prices').fetchall()}
    out = {}
    for pack in core.PRODUCTS:
        r = rows.get(pack)
        base = core.product_price(db, pack)
        out[pack] = {'retail': int(r['retail']) if r and int(r['retail'] or 0) > 0 else base,
                     'dealer': int(r['dealer']) if r and int(r['dealer'] or 0) > 0 else base}
    return out


def set_price(db, actor, pack, retail=None, dealer=None):
    _require(db, actor, 'prices')
    pack = _int(pack, 'Mahsulot')
    if pack not in core.PRODUCTS:
        raise ValueError('Mahsulot noto‘g‘ri.')
    cur = prices(db)[pack]
    r = _cents(retail, 'Chakana narx') if retail not in (None, '') else cur['retail']
    d = _cents(dealer, 'Diller narx') if dealer not in (None, '') else cur['dealer']
    db.execute('''INSERT INTO shop_prices(pack,retail,dealer,updated_by,updated_ts) VALUES(?,?,?,?,?)
        ON CONFLICT(pack) DO UPDATE SET retail=excluded.retail,dealer=excluded.dealer,
        updated_by=excluded.updated_by,updated_ts=excluded.updated_ts''', (pack, r, d, actor, int(time.time())))
    return {'pack': pack, 'retail': r, 'dealer': d}


def set_client_price(db, actor, client, pack, price):
    """Mijozga maxsus narx (price bo'sh/0 — o'chirish)."""
    _require(db, actor, 'special')
    client = _client(db, client)['id']
    pack = _int(pack, 'Mahsulot')
    if pack not in core.PRODUCTS:
        raise ValueError('Mahsulot noto‘g‘ri.')
    if price in (None, '', 0, '0'):
        db.execute('DELETE FROM shop_client_prices WHERE client=? AND pack=?', (client, pack))
        return None
    cents = _cents(price, 'Maxsus narx')
    db.execute('''INSERT INTO shop_client_prices(client,pack,price,updated_by,updated_ts) VALUES(?,?,?,?,?)
        ON CONFLICT(client,pack) DO UPDATE SET price=excluded.price,updated_by=excluded.updated_by,
        updated_ts=excluded.updated_ts''', (client, pack, cents, actor, int(time.time())))
    return cents


def set_client_type(db, actor, client, price_type):
    _require(db, actor, 'special')
    client = _client(db, client)['id']
    if price_type not in PRICE_TYPES:
        raise ValueError('Narx turi noto‘g‘ri.')
    db.execute('''INSERT INTO shop_clients(client,price_type) VALUES(?,?)
        ON CONFLICT(client) DO UPDATE SET price_type=excluded.price_type''', (client, price_type))


def client_type(db, client):
    r = db.execute('SELECT price_type FROM shop_clients WHERE client=?', (client,)).fetchone()
    return r[0] if r and r[0] in PRICE_TYPES else 'retail'


def client_prices(db, client):
    return {int(r['pack']): int(r['price']) for r in
            db.execute('SELECT pack,price FROM shop_client_prices WHERE client=?', (client,)).fetchall()}


def price_for(db, client, pack, table=None, special=None, ptype=None):
    """Mijoz uchun asosiy narx: maxsus > diller (diller mijozga) > chakana."""
    special = client_prices(db, client) if special is None else special
    if pack in special:
        return special[pack], 'special'
    table = prices(db) if table is None else table
    ptype = client_type(db, client) if ptype is None else ptype
    return table[pack][ptype], ptype


# ---------- mijozlar ----------

def _client(db, client):
    cid = _int(client, 'Mijoz', 1)
    row = db.execute('SELECT id,name,shop_name,phone,blacklisted FROM clients WHERE id=?', (cid,)).fetchone()
    if not row:
        raise ValueError('Mijoz topilmadi.')
    return {'id': int(row['id']), 'name': row['name'], 'shopName': row['shop_name'], 'phone': row['phone'],
            'blacklisted': bool(int(row['blacklisted'] or 0))}


def walkin_client(db, seller):
    """Har bir sotuvchining «Chakana xaridor» mijozi (faqat to'liq to'langan sotuvlar uchun)."""
    r = db.execute('SELECT walkin_client FROM shop_staff WHERE user_id=?', (seller,)).fetchone()
    if r and r[0] and db.execute('SELECT 1 FROM clients WHERE id=?', (int(r[0]),)).fetchone():
        return int(r[0])
    cur = db.execute("""INSERT INTO clients(agent,name,shop_name,phone,address,region,comment,created_ts,map_only)
        VALUES(?,?,?,NULL,'','','Savdo: naqd chakana xaridorlar',?,1) RETURNING id""",
                     (seller, WALKIN_NAME, WALKIN_NAME, int(time.time())))
    cid = int(cur.fetchone()[0])
    db.execute('''INSERT INTO shop_staff(user_id,walkin_client) VALUES(?,?)
        ON CONFLICT(user_id) DO UPDATE SET walkin_client=excluded.walkin_client''', (seller, cid))
    return cid


def _walkin_ids(db):
    return {int(r[0]) for r in db.execute('SELECT walkin_client FROM shop_staff WHERE walkin_client IS NOT NULL').fetchall()}


def add_client(db, actor, name, phone, shop_name='', region='', address='', price_type='retail'):
    s = _require(db, actor, 'clients')
    name = str(name or '').strip()
    if not 2 <= len(name) <= 80:
        raise ValueError('Mijoz ismini yozing (2–80 belgi).')
    phone = str(phone or '').strip().replace(' ', '').replace('-', '')
    if phone and not (phone.startswith('+') and phone[1:].isdigit() and 9 <= len(phone) <= 16):
        raise ValueError('Telefon raqami +998901234567 ko‘rinishida bo‘lsin.')
    if not phone:
        raise ValueError('Qarzga berish uchun mijoz telefonini kiriting.')
    if db.execute('SELECT 1 FROM clients WHERE phone=?', (phone,)).fetchone():
        raise ValueError('Bu telefon bilan mijoz bor — qidiruvdan tanlang.')
    if price_type not in PRICE_TYPES:
        raise ValueError('Narx turi noto‘g‘ri.')
    if price_type == 'dealer' and not can(s, 'dealer'):
        raise ValueError('Diller mijoz qo‘shish ruxsati yo‘q.')
    cur = db.execute("""INSERT INTO clients(agent,name,shop_name,phone,address,region,comment,created_ts,map_only)
        VALUES(?,?,?,?,?,?,'Savdo bo‘limi',?,1) RETURNING id""",
                     (actor, name, str(shop_name or '').strip()[:80] or name, phone,
                      str(address or '').strip()[:200], str(region or '').strip()[:60], int(time.time())))
    cid = int(cur.fetchone()[0])
    if price_type != 'retail':
        db.execute('INSERT INTO shop_clients(client,price_type) VALUES(?,?)', (cid, price_type))
    return cid


def search_clients(db, actor, q='', limit=30):
    _require(db, actor)
    q = str(q or '').strip().lower()
    walk = _walkin_ids(db)
    rows = db.execute('SELECT id,name,shop_name,phone,region FROM clients WHERE COALESCE(blacklisted,0)=0').fetchall()
    out = []
    for r in rows:
        if int(r['id']) in walk:
            continue
        text = f"{r['name'] or ''} {r['shop_name'] or ''} {r['phone'] or ''} {r['region'] or ''}".lower()
        if q and q not in text:
            continue
        out.append(r)
    out.sort(key=lambda r: ((r['shop_name'] or r['name'] or '').lower(), int(r['id'])))
    types = {int(r[0]): r[1] for r in db.execute('SELECT client,price_type FROM shop_clients').fetchall()}
    return [{'id': int(r['id']), 'name': (r['shop_name'] or r['name'] or '').strip() or f"Mijoz #{r['id']}",
             'person': r['name'] or '', 'phone': r['phone'] or '', 'region': r['region'] or '',
             'priceType': types.get(int(r['id']), 'retail'), 'debtUsd': core.client_debt_usd(db, int(r['id'])) / 100}
            for r in out[:max(1, min(int(limit), 100))]]


# ---------- to'lov ----------

def _payment(db, payload, total_limit):
    """(cents, method, uzs, rate) — to'langan summa USD sentda."""
    method = payload.get('method') or ''
    if payload.get('paid') in (None, '', 0, '0') and payload.get('paidUzs') in (None, '', 0, '0'):
        return 0, '', 0, 0
    if method not in METHODS:
        raise ValueError('To‘lov turini tanlang: naqd $, naqd so‘m yoki karta.')
    if method == 'cash_uzs':
        uzs = core.parse_whole_som(payload.get('paidUzs'), 'So‘m summasi')
        rate = core.validate_agent_rate(db, _int(payload.get('rate'), 'Kurs', 1, 10 ** 7))
        cents = core.som_to_usd_cents(uzs, rate)
    else:
        uzs, rate = 0, 0
        cents = _cents(payload.get('paid'), 'To‘langan summa')
    if total_limit is not None and cents > total_limit:
        raise ValueError(f'To‘lov ({cents / 100:.2f} $) to‘lanishi kerak bo‘lgan summadan ({total_limit / 100:.2f} $) ko‘p.')
    return cents, method, uzs, rate


def _seller(db, actor, payload):
    """Sotuv kimning hisobiga yoziladi: savdo xodimi — o'zi; rahbar (web panel) — tanlangan savdo xodimi.

    Naqd pul o'sha xodim qo'lida hisoblanadi va u kassaga topshiradi."""
    s = _require(db, actor)
    if s['role'] == 'sales':
        return actor
    raw = payload.get('sellerId')
    if raw in (None, '', 0, '0'):
        raise ValueError('Sotuv qaysi savdo xodimi nomidan ekanini tanlang.')
    sid = _int(raw, 'Savdo xodimi', 1)
    if sid == actor:
        return actor   # rahbar o'z nomidan sotadi: pul to'g'ridan kassaga (_insert_payment)
    r = db.execute('SELECT role FROM users WHERE id=?', (sid,)).fetchone()
    if not r or r[0] != 'sales':
        raise ValueError('Faol savdo xodimini tanlang.')
    return sid


def _insert_payment(db, actor, agent, client, cents, method, uzs, rate, note, source, ts):
    row = db.execute('SELECT role FROM users WHERE id=?', (agent,)).fetchone()
    if row and row[0] == 'admin':
        # Rahbar o'zi sotgan: pul hech kimning qo'lida qolmaydi — kassa kirimi va mijoz to'lovi bitta yozuvda
        # (cashbook «Mijozdan to'lov» bilan bir xil: events agent bo'sh, cash_moves bog'langan).
        import cashbook
        cashbook.record_client_payment(db, actor, client, 'card' if method == 'card' else 'cash',
                                       'UZS' if uzs else 'USD', uzs or cents, cents, rate, note, source, ts)
        return
    db.execute("""INSERT INTO events(actor,agent,client,kind,pack,qty,amount,amount_usd,note,ts,source,pay_method,paid_uzs,fx_rate)
        VALUES(?,?,?,'payment',0,0,0,?,?,?,?,?,?,?)""",
               (actor, agent, client, cents, note, ts, source, 'card' if method == 'card' else 'cash', uzs, rate))


# ---------- sotuv ----------

def quote(db, actor, payload):
    """Hisob-kitob (saqlamaydi): ilova savatchasi uchun ham, sell() uchun ham yagona formula."""
    s = _require(db, actor)
    raw_client = payload.get('clientId')
    walkin = raw_client in (None, '', 0, '0')
    client = None if walkin else _client(db, raw_client)
    if client and client['blacklisted']:
        raise ValueError(core.BLACKLIST_MSG)
    cid = client['id'] if client else 0
    ptype = client_type(db, cid) if client else 'retail'
    special = client_prices(db, cid) if client else {}
    table = prices(db)
    items = payload.get('items')
    if not isinstance(items, list) or not 1 <= len(items) <= 60:
        raise ValueError('Savatcha bo‘sh.')
    lines, subtotal, need = [], 0, {}
    for it in items:
        if not isinstance(it, dict):
            raise ValueError('Savatcha noto‘g‘ri.')
        pack = _int(it.get('pack'), 'Mahsulot')
        if pack not in core.PRODUCTS or pack in core.INACTIVE_PRODUCTS:
            raise ValueError('Mahsulot noto‘g‘ri yoki arxivda.')
        qty = _int(it.get('qty'), 'Miqdor', 1, 100000)
        base, source = price_for(db, cid, pack, table, special, ptype)
        price = base
        if it.get('price') not in (None, ''):
            price = _cents(it.get('price'), 'Narx')
            if price != base and not can(s, 'price'):
                raise ValueError(f'{core.product_name(pack)}: sizda narxni o‘zgartirish ruxsati yo‘q.')
        if price <= 0:
            raise ValueError(f'{core.product_name(pack)}: narx belgilanmagan. Bosh savdo xodimi narx qo‘ysin.')
        lines.append({'pack': pack, 'name': core.product_name(pack), 'qty': qty, 'listPrice': base,
                      'priceSource': source, 'price': price, 'gross': qty * price})
        subtotal += qty * price
        need[pack] = need.get(pack, 0) + qty
    # Chegirma: summa ($) yoki foiz. Ruxsat etilgan chegirma — ro'yxat narxidan pastga tushirilgan narx ham hisobga olinadi.
    discount = 0
    if payload.get('discountPct') not in (None, '', 0, '0'):
        pct = payload.get('discountPct')
        try:
            pct = float(str(pct).replace(',', '.'))
        except ValueError:
            raise ValueError('Chegirma foizi noto‘g‘ri.')
        if not 0 <= pct <= 100:
            raise ValueError('Chegirma foizi 0–100 oralig‘ida bo‘lsin.')
        discount = int(round(subtotal * pct / 100))
    elif payload.get('discount') not in (None, '', 0, '0'):
        discount = _cents(payload.get('discount'), 'Chegirma')
    if discount > subtotal:
        raise ValueError('Chegirma jami summadan katta bo‘lishi mumkin emas.')
    list_total = sum(l['qty'] * l['listPrice'] for l in lines)
    total = subtotal - discount
    # Narxni o'zgartirish ruxsati bo'lsa, tanlangan narx asos; aks holda ro'yxat narxi (yashirin chegirma ham limitga kiradi).
    basis = subtotal if can(s, 'price') else list_total
    eff_pct = (basis - total) * 100.0 / basis if basis else 0
    if s['role'] != 'admin' and eff_pct > s['maxDiscountPct'] + 1e-9:
        if not can(s, 'discount'):
            raise ValueError('Sizda chegirma berish ruxsati yo‘q.')
        raise ValueError(f"Chegirma {eff_pct:.1f}% — sizning limitingiz {s['maxDiscountPct']}%. Rahbarga murojaat qiling.")
    need_perm = 'dealer' if ptype == 'dealer' else 'retail'
    if not can(s, need_perm):
        raise ValueError(f'Sizda «{PERMS[need_perm]}» ruxsati yo‘q.')
    # Chegirmani qatorlarga taqsimlash (oxirgi qator qoldiqni oladi).
    left = discount
    for i, l in enumerate(lines):
        d = left if i == len(lines) - 1 else (l['gross'] * discount // subtotal if subtotal else 0)
        d = min(d, l['gross'], left)
        l['discount'] = d
        l['total'] = l['gross'] - d
        left -= d
    # Qo'shimcha xarajat: mijoz to'laydi; qatorlarga summasi bo'yicha taqsimlanadi, shuning uchun qarz/hisobot o'zgarmasdan to'g'ri.
    extra = _cents(payload.get('extra'), 'Qo‘shimcha xarajat', allow_zero=True)
    extra_name = str(payload.get('extraName') or '').strip()[:100]
    left = extra
    for i, l in enumerate(lines):
        e = left if i == len(lines) - 1 else l['gross'] * extra // subtotal
        l['total'] += e
        left -= e
    total += extra
    # Mavjud = ombor qoldig'i − ochiq buyurtmalarda band (sale_orders). Buyurtma bo'lmasa — avvalgidek.
    import sale_orders
    stock = {p: sale_orders.available(db, p) for p in need}
    short = [f'{core.product_name(p)}: mavjud {stock[p]} dona' for p, q in need.items() if stock[p] < q]
    debt = core.client_debt_usd(db, cid) if client else 0
    return {'client': client, 'walkin': walkin, 'priceType': ptype, 'lines': lines, 'subtotal': subtotal,
            'discount': discount, 'extra': extra, 'extraName': extra_name, 'total': total, 'discountPct': round(eff_pct, 2), 'stockShort': short,
            'clientDebt': debt, 'staff': s}


def sell(db, actor, payload):
    """Sotuvni saqlash. Qaytaradi: sotuv kartasi (receipt).

    replaceSaleId — rahbar tahriri: eski sotuv bekor qilinadi (tovar/pul/qarz qaytadi) va shu tranzaksiyada yangisi yoziladi."""
    src = _source(actor, payload.get('requestId'))
    old = db.execute('SELECT id FROM shop_sales WHERE source=?', (src,)).fetchone()
    if old:
        return receipt(db, int(old[0]))
    replace = payload.get('replaceSaleId')
    if replace not in (None, '', 0, '0'):
        import corrections
        replace = _int(replace, 'Sotuv', 1)
        corrections.cancel_sale(db, actor, replace, payload.get('reason') or 'Tahrirlandi')
    else:
        replace = None
    who = _seller(db, actor, payload)
    core.lock_agent(db, who)
    wh._lock_warehouse(db)
    q = quote(db, actor, payload)
    s = q['staff']
    if q['stockShort']:
        raise ValueError('Omborda yetarli emas — ' + '; '.join(q['stockShort']))
    paid, method, uzs, rate = _payment(db, payload, q['total'])
    debt = q['total'] - paid
    if q['walkin'] and debt > 0:
        raise ValueError('Chakana xaridorga qarzga berib bo‘lmaydi: mijozni tanlang yoki to‘liq to‘lov oling.')
    if debt > 0 and not can(s, 'credit'):
        raise ValueError('Sizga qarzga berish ruxsati yo‘q. To‘liq to‘lov oling.')
    note = str(payload.get('note') or '').strip()
    if len(note) > 300:
        raise ValueError('Izoh 300 belgidan oshmasin.')
    cid = walkin_client(db, who) if q['walkin'] else q['client']['id']
    ts = int(time.time())
    cur = db.execute('''INSERT INTO shop_sales(seller,client,price_type,subtotal,discount,extra,extra_name,total,paid,pay_method,paid_uzs,fx_rate,note,ts,source)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) RETURNING id''',
                     (who, cid, q['priceType'], q['subtotal'], q['discount'], q['extra'], q['extraName'], q['total'], paid, method, uzs, rate, note, ts, src))
    sale = int(cur.fetchone()[0])
    tag = f'Savdo #{sale}' + (f' | {note}' if note else '')
    for i, l in enumerate(q['lines'], 1):
        db.execute('''INSERT INTO shop_sale_lines(sale,pack,qty,list_price,price,discount,total) VALUES(?,?,?,?,?,?,?)''',
                   (sale, l['pack'], l['qty'], l['listPrice'], l['price'], l['discount'], l['total']))
        wh._move(db, actor, 'shop_sale', l['pack'], l['qty'], agent=who, note=tag, source=_source(actor, payload.get('requestId'), 100 + i))
        db.execute('''INSERT INTO events(actor,agent,client,kind,pack,qty,amount,amount_usd,note,ts,source)
            VALUES(?,?,?,'delivery',?,?,0,?,?,?,?)''', (actor, who, cid, l['pack'], l['qty'], l['total'], tag, ts,
                                                         _source(actor, payload.get('requestId'), 200 + i)))
        db.execute('''INSERT INTO events(actor,agent,client,kind,pack,qty,amount,amount_usd,note,ts,source)
            VALUES(?,?,?,'sold',?,?,0,?,?,?,?)''', (actor, who, cid, l['pack'], l['qty'], l['total'], tag, ts,
                                                     _source(actor, payload.get('requestId'), 300 + i)))
    if paid:
        _insert_payment(db, actor, who, cid, paid, method, uzs, rate, tag, _source(actor, payload.get('requestId'), 1), ts)
    if replace:
        import corrections
        corrections.link_replacement(db, 'sale', replace, sale)
    return receipt(db, sale)


def collect(db, actor, payload):
    """Mijoz qarzini undirish (sotuvsiz to'lov)."""
    s = _require(db, actor, 'collect')
    src = _source(actor, payload.get('requestId'))
    if db.execute('SELECT 1 FROM events WHERE source=?', (src,)).fetchone():
        return {'ok': True, 'duplicate': True}
    client = _client(db, payload.get('clientId'))
    who = _seller(db, actor, payload)
    core.lock_agent(db, who)
    debt = core.client_debt_usd(db, client['id'])
    if debt <= 0:
        raise ValueError('Bu mijozda qarz yo‘q.')
    cents, method, uzs, rate = _payment(db, payload, debt)
    if not cents:
        raise ValueError('To‘lov summasini kiriting.')
    note = str(payload.get('note') or '').strip()[:300]
    _insert_payment(db, actor, who, client['id'], cents, method, uzs, rate, 'Savdo: qarz to‘lovi' + (f' | {note}' if note else ''), src, int(time.time()))
    return {'ok': True, 'clientId': client['id'], 'paidUsd': cents / 100, 'debtUsd': (debt - cents) / 100, 'level': s['level']}


def receipt(db, sale):
    h = db.execute('''SELECT s.*,u.name AS seller_name,c.name AS client_name,c.shop_name,c.phone FROM shop_sales s
        LEFT JOIN users u ON u.id=s.seller LEFT JOIN clients c ON c.id=s.client WHERE s.id=?''', (sale,)).fetchone()
    if not h:
        raise ValueError('Sotuv topilmadi.')
    lines = [{'pack': int(r['pack']), 'name': core.product_name(int(r['pack'])), 'qty': int(r['qty']),
              'listPriceUsd': int(r['list_price']) / 100, 'priceUsd': int(r['price']) / 100,
              'discountUsd': int(r['discount']) / 100,   # qatorda xarajat ulushi ko'rsatilmaydi — u alohida qatorda
              'totalUsd': (int(r['qty']) * int(r['price']) - int(r['discount'])) / 100}
             for r in db.execute('SELECT * FROM shop_sale_lines WHERE sale=? ORDER BY id', (sale,)).fetchall()]
    total, paid = int(h['total']), int(h['paid'])
    return {'id': int(h['id']), 'ts': int(h['ts']), 'sellerId': int(h['seller']), 'seller': h['seller_name'] or '',
            'clientId': int(h['client']), 'client': (h['shop_name'] or h['client_name'] or '').strip(), 'phone': h['phone'] or '',
            'priceType': h['price_type'], 'subtotalUsd': int(h['subtotal']) / 100, 'discountUsd': int(h['discount']) / 100,
            'extraUsd': int(h['extra'] or 0) / 100, 'extraName': h['extra_name'] or '', 'totalUsd': total / 100, 'paidUsd': paid / 100, 'debtUsd': (total - paid) / 100, 'method': h['pay_method'],
            'paidUzs': int(h['paid_uzs'] or 0), 'rate': int(h['fx_rate'] or 0), 'note': h['note'] or '', 'lines': lines,
            'cancelled': _void_info(db, int(h['id'])), 'publicUrl': receipt_public.url(int(h['id']))}


def _void_info(db, sale):
    r = db.execute('''SELECT v.*,u.name AS who FROM voids v LEFT JOIN users u ON u.id=v.actor WHERE v.kind='sale' AND v.ref=?''',
                   (sale,)).fetchone()
    if not r:
        return None
    return {'reason': r['reason'], 'who': r['who'] or '', 'ts': int(r['ts']),
            'replacedBy': int(r['replaced_by']) if r['replaced_by'] is not None else None}


def handover(db, actor, payload):
    """Sotuvchi qo'lidagi naqd pulni kassaga topshirish (kassir tasdiqlaydi)."""
    _require(db, actor)
    if staff(db, actor)['role'] != 'sales':
        raise ValueError('Rahbar kassaga topshirmaydi.')
    currency = payload.get('currency')
    src = _source(actor, payload.get('requestId'))
    if db.execute('SELECT 1 FROM handovers WHERE source=?', (src,)).fetchone():
        return {'ok': True, 'duplicate': True}
    if currency == 'USD':
        value = _cents(payload.get('amount'), 'Summa')
    elif currency == 'UZS':
        value = core.parse_whole_som(payload.get('amount'), 'So‘m summasi') * 100   # handovers.amount — tiyinda
    else:
        raise ValueError('Valyutani tanlang.')
    core.handover(db, actor, value, src, currency=currency)
    return {'ok': True}


# ---------- ilova ma'lumoti ----------

def dashboard(db, actor, now=None):
    s = _require(db, actor)
    now = int(time.time() if now is None else now)
    day0 = wh.day_start(now)
    table = prices(db)
    stock = wh.stock_all(db)
    import sale_orders
    held = sale_orders.reserved_all(db)
    # stock — sotish mumkin (ochiq buyurtmalarda band qilingani ayirilgan); onHand — ombordagi jismoniy qoldiq.
    products = [{'pack': p, 'name': core.product_name(p), 'retailUsd': table[p]['retail'] / 100,
                 'dealerUsd': table[p]['dealer'] / 100, 'stock': stock.get(p, 0) - held.get(p, 0),
                 'onHand': stock.get(p, 0), 'reserved': held.get(p, 0)}
                for p in core.PRODUCTS if p not in core.INACTIVE_PRODUCTS]
    products.sort(key=lambda x: (x['stock'] <= 0, x['name']))
    mine = not can(s, 'all_sales')
    where, args = ('WHERE ts>=?', [day0]) if not mine else ('WHERE ts>=? AND seller=?', [day0, actor])
    where += ' AND ' + NOT_VOID   # bekor qilingan sotuv bugungi jamiga kirmaydi
    rows = db.execute(f'SELECT id,total,paid FROM shop_sales {where} ORDER BY ts DESC,id DESC', args).fetchall()
    today = {'count': len(rows), 'totalUsd': sum(int(r['total']) for r in rows) / 100,
             'paidUsd': sum(int(r['paid']) for r in rows) / 100,
             'debtUsd': sum(int(r['total']) - int(r['paid']) for r in rows) / 100}
    recent_args = [actor] if mine else []
    recent = [receipt(db, int(r[0])) for r in db.execute(
        'SELECT id FROM shop_sales' + (' WHERE seller=?' if mine else '') + ' ORDER BY ts DESC,id DESC LIMIT 30', recent_args).fetchall()]
    cash = None
    if s['role'] == 'sales':
        pend_usd = db.execute("SELECT COALESCE(SUM(amount_usd),0) FROM handovers WHERE agent=? AND status='pending' AND COALESCE(amount,0)=0", (actor,)).fetchone()[0]
        pend_uzs = db.execute("SELECT COALESCE(SUM(amount),0) FROM handovers WHERE agent=? AND status='pending' AND COALESCE(amount,0)>0", (actor,)).fetchone()[0]
        cash = {'usd': core.cash_usd(db, actor) / 100, 'uzs': int(core.cash(db, actor)) // 100,
                'pendingUsd': int(pend_usd or 0) / 100, 'pendingUzs': int(pend_uzs or 0) // 100}
    team = None
    sellers = None
    if s['role'] == 'admin':
        sellers = [{'id': actor, 'name': f"{s['name']} (o‘zim) — pul to‘g‘ridan kassaga", 'self': True}]
    if can(s, 'all_sales'):
        team = []
        for u in db.execute("SELECT id,name FROM users WHERE role='sales' ORDER BY name,id").fetchall():
            st = staff(db, int(u['id']))
            r = db.execute('SELECT COUNT(*),COALESCE(SUM(total),0),COALESCE(SUM(paid),0) FROM shop_sales WHERE seller=? AND ts>=? AND ' + NOT_VOID,
                           (int(u['id']), day0)).fetchone()
            team.append({'id': int(u['id']), 'name': u['name'] or str(u['id']), 'level': st['level'], 'perms': st['perms'],
                         'maxDiscountPct': st['maxDiscountPct'], 'allowCredit': st['allowCredit'],
                         'todayCount': int(r[0] or 0), 'todayUsd': int(r[1] or 0) / 100, 'todayPaidUsd': int(r[2] or 0) / 100,
                         'cashUsd': core.cash_usd(db, int(u['id'])) / 100, 'cashUzs': int(core.cash(db, int(u['id']))) // 100})
    return {'me': {k: s[k] for k in ('id', 'name', 'role', 'level', 'perms', 'maxDiscountPct', 'allowCredit')},
            'permLabels': PERMS,
            'rate': core.cashier_rate(db), 'products': products, 'today': today, 'recent': recent,
            'cash': cash, 'team': team, 'sellers': (sellers or []) + [{'id': u['id'], 'name': u['name']} for u in (team or [])],
            'brand': branding.get(db), 'generatedTs': now}


def client_card(db, actor, client):
    _require(db, actor)
    c = _client(db, client)
    special = client_prices(db, c['id'])
    sales_rows = [receipt(db, int(r[0])) for r in db.execute(
        'SELECT id FROM shop_sales WHERE client=? ORDER BY ts DESC,id DESC LIMIT 20', (c['id'],)).fetchall()]
    return {'client': {**c, 'priceType': client_type(db, c['id']), 'debtUsd': core.client_debt_usd(db, c['id']) / 100},
            'special': [{'pack': p, 'name': core.product_name(p), 'priceUsd': v / 100} for p, v in sorted(special.items())],
            'sales': sales_rows}


# ---------- Mini App API ----------

ACTIONS = ('dashboard', 'quote', 'sell', 'collect', 'clients', 'client', 'add_client', 'handover',
           'set_price', 'set_client_price', 'set_client_type', 'set_staff', 'receipt', 'orders', 'sale_cancel')


def handle(db, actor, action, payload):
    """/api/shop: har bir amal huquqni o'zi tekshiradi. `_notify` — commitdan keyin yuboriladigan xabarlar."""
    if action not in ACTIONS:
        raise ValueError('Amal noto‘g‘ri.')
    _require(db, actor)
    out = {}
    if action == 'quote':
        q = quote(db, actor, payload)
        q.pop('staff')
        return {'quote': {**q, 'subtotalUsd': q['subtotal'] / 100, 'discountUsd': q['discount'] / 100,
                          'extraUsd': q['extra'] / 100, 'totalUsd': q['total'] / 100, 'clientDebtUsd': q['clientDebt'] / 100,
                          'lines': [{**l, 'listPriceUsd': l['listPrice'] / 100, 'priceUsd': l['price'] / 100,
                                     'discountUsd': l['discount'] / 100, 'totalUsd': l['total'] / 100} for l in q['lines']]}}
    if action == 'sale_cancel':
        import corrections
        sid = _int(payload.get('saleId'), 'Sotuv', 1)
        corrections.cancel_sale(db, actor, sid, payload.get('reason'))
        out['receipt'] = receipt(db, sid)
        out.update(dashboard(db, actor))
        return out
    if action == 'orders':
        # Ombordan buyurtma: band qilish, qisman yetkazish/to'lov, qaytarish (sale_orders.py)
        import sale_orders
        return sale_orders.handle(db, actor, payload.get('orderOp') or 'list', payload)
    if action == 'sell':
        out['receipt'] = sell(db, actor, payload)
    elif action == 'collect':
        out['collected'] = collect(db, actor, payload)
    elif action == 'clients':
        return {'clients': search_clients(db, actor, payload.get('q'))}
    elif action == 'client':
        return client_card(db, actor, payload.get('clientId'))
    elif action == 'receipt':
        return {'receipt': receipt(db, _int(payload.get('saleId'), 'Sotuv', 1))}
    elif action == 'add_client':
        cid = add_client(db, actor, payload.get('name'), payload.get('phone'), payload.get('shopName'),
                         payload.get('region'), payload.get('address'), payload.get('priceType') or 'retail')
        return client_card(db, actor, cid)
    elif action == 'handover':
        handover(db, actor, payload)
        row = db.execute('SELECT id,amount,amount_usd FROM handovers WHERE source=?', (_source(actor, payload.get('requestId')),)).fetchone()
        if row:
            out['_handover'] = (int(row[0]), int(row[2] or 0), 'UZS' if int(row[1] or 0) > 0 else 'USD',
                                int(row[1] or 0) // 100 if int(row[1] or 0) > 0 else None)
    elif action == 'set_price':
        set_price(db, actor, payload.get('pack'), payload.get('retail'), payload.get('dealer'))
    elif action == 'set_client_price':
        set_client_price(db, actor, payload.get('clientId'), payload.get('pack'), payload.get('price'))
        return client_card(db, actor, payload.get('clientId'))
    elif action == 'set_client_type':
        set_client_type(db, actor, payload.get('clientId'), payload.get('priceType'))
        return client_card(db, actor, payload.get('clientId'))
    elif action == 'set_staff':
        set_staff(db, actor, _int(payload.get('userId'), 'Xodim', 1), payload.get('perms') or [],
                  payload.get('maxDiscountPct', DEFAULT_MAX_DISCOUNT_PCT))
    out.update(dashboard(db, actor))
    return out
