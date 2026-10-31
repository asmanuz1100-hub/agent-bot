"""Rahbar paneli yordamchisi: savolni kalit so'zlar bo'yicha tushunib, javobni faqat tizim ma'lumotidan tuzadi.

Tashqi sun'iy intellekt yo'q — javob bir zumda, raqamlar to'g'ridan-to'g'ri hisobotlardan.
Masalan: "bugun sotuv o'sdimi?" → "Ha, bugun realizatsiya 1 250 $ — kechaga nisbatan +27.6% (980 $)."
"""
import re
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import executive
import manager_api

MAX_QUESTION = 600
TZ = ZoneInfo('Asia/Tashkent')

HELP = ('Men tizim ma’lumotlari bo‘yicha javob beraman. Masalan so‘rang: «bugun sotuv o‘sdimi?», '
        '«haftalik to‘lovlar», «qarz qancha?», «agentlardagi pul», «eng yaxshi agent», '
        '«eng ko‘p sotilgan mahsulot», «ombor qoldig‘i», «ochiq buyurtmalar».')

_CYR = dict(zip('абвгдеёжзийклмнопрстуфхцчшъыьэюяўқғҳ',
                ['a', 'b', 'v', 'g', 'd', 'e', 'yo', 'j', 'z', 'i', 'y', 'k', 'l', 'm', 'n', 'o', 'p', 'r', 's', 't',
                 'u', 'f', 'x', 's', 'ch', 'sh', '', 'i', '', 'e', 'yu', 'ya', 'o', 'q', 'g', 'h']))

# (davr, executive davri, period_report davri, nomi, solishtirish nomi)
PERIODS = {
    'today': ('today', 'today', 'bugun', 'kechaga'),
    'yesterday': ('yesterday', None, 'kecha', 'undan oldingi kunga'),
    'd7': ('d7', 'week', 'oxirgi 7 kunda', 'oldingi 7 kunga'),
    'month': ('d30', 'month', 'oxirgi 30 kunda', 'oldingi 30 kunga'),
}

# Mavzu → kalit so'z ildizlari (lotin, kichik harf). Tartib muhim: aniqrog'i oldin.
TOPICS = (
    ('cash', ('agentlarda', 'agentdagi', 'qolida', 'naqd', 'topshir')),
    ('cashbox', ('kassa', 'pul qancha', 'balans')),
    ('debt', ('qarz', 'nasiya')),
    ('stock', ('ombor', 'qoldiq', 'zaxira', 'sklad')),
    ('orders', ('buyurtma', 'zakaz')),
    ('product', ('mahsulot', 'tovar', 'eng kop sotil', 'nima kop')),
    ('agent', ('agent', 'xodim')),
    ('payments', ('tolov', 'tushum', 'yigil', 'yigdi', 'inkassa')),
    ('visits', ('tashrif', 'vizit')),
    ('clients', ('yangi mijoz', 'mijoz qoshil')),
    ('sales', ('sotuv', 'savdo', 'realiza', 'sotil', 'sotdi', 'osdi', 'osish', 'kamaydi', 'tushdi')),
)


def normalize(text):
    t = str(text or '').lower()
    t = ''.join(_CYR.get(ch, ch) for ch in t)
    t = re.sub(r"[‘’ʻʼ`'ʹ]", '', t)          # o‘ → o, g‘ → g
    return ' '.join(re.sub(r'[^a-z0-9 ]', ' ', t).split())


def detect(question):
    q = normalize(question)
    if 'kecha' in q and 'bugun' not in q:
        period = 'yesterday'
    elif re.search(r'hafta|7 kun', q):
        period = 'd7'
    elif re.search(r'\boy\b|oylik|oyda|shu oy', q):
        period = 'month'
    else:
        period = 'today'
    topic = next((name for name, keys in TOPICS if any(k in q for k in keys)), None)
    return topic, period, q


def _money(usd):
    v = round(float(usd or 0), 2)
    s = f'{v:,.2f}'.rstrip('0').rstrip('.').replace(',', ' ')
    return f'{s} $'


def _num(n):
    return f'{int(n or 0):,}'.replace(',', ' ')


def _compare(kpi, money, versus):
    cur, prev, delta = kpi['value'], kpi.get('prev'), kpi.get('delta')
    fmt = _money if money else _num
    if prev is None or delta is None:
        return f'{fmt(cur)}.', None
    if delta['kind'] == 'new':
        return f'{fmt(cur)} — {versus} nisbatan yangi (oldin 0 edi).', True
    pct = delta['pct']
    up = pct > 0
    sign = '+' if up else ''
    text = f'{fmt(cur)} — {versus} nisbatan {sign}{pct}% ({fmt(prev)}).'
    return text, (up if pct else None)


def _kpi(ex, key):
    return next(k for k in ex['kpis'] if k['key'] == key)


def answer(db, topic, period, q, now=None):
    exec_period, report_period, when, versus = PERIODS[period]
    asked_growth = bool(re.search(r'osdi|osish|kopaydi|kamaydi|tushdi|yaxshi|yomon', q))

    if topic in ('sales', 'payments', 'visits', 'clients', None):
        ex = executive.executive(db, exec_period, now=now)
        key, label, money = {'sales': ('realization', 'realizatsiya', True),
                             'payments': ('collected', 'yig‘ilgan to‘lov', True),
                             'visits': ('visits', 'tashriflar', False),
                             'clients': ('newClients', 'yangi mijozlar', False),
                             None: ('realization', 'realizatsiya', True)}[topic]
        text, up = _compare(_kpi(ex, key), money, versus)
        line = f'{when.capitalize()} {label}: {text}'
        if asked_growth and up is not None:
            line = ('Ha, o‘sdi. ' if up else 'Yo‘q, kamaydi. ') + line
        elif asked_growth:
            line = 'O‘zgarish yo‘q. ' + line
        if topic in ('sales', None):
            pay, _ = _compare(_kpi(ex, 'collected'), True, versus)
            line += f' To‘lovlar: {pay}'
        return line

    if topic == 'debt':
        ex = executive.executive(db, 'today', now=now)
        debt = _kpi(ex, 'debt')['value']
        old = [b for b in ex.get('debtAging') or [] if (b.get('minDays') or 0) >= 30 and b.get('usd')]
        tail = ''.join(f' {b["label"]} kunlik qarz: {_money(b["usd"])}.' for b in old)
        return f'Umumiy qarz: {_money(debt)}.' + tail

    if topic == 'cashbox':
        c = manager_api.dashboard(db, now=now)['cash']
        text = (f'Kassa qoldig‘i: {_money(c["balanceUsd"])}. Bugun kirim {_money(c["acceptedTodayUsd"])}, '
                f'chiqim {_money(c["expensesTodayUsd"])}.')
        if c.get('pendingUsd'):
            text += f' Kassir tasdig‘ida: {_money(c["pendingUsd"])}.'
        return text

    if topic == 'cash':
        c = executive.executive(db, 'today', now=now)['agentsCash']
        text = f'Agentlardagi pul: {_money(c["cashUsd"])} va {_num(c["cashUzs"])} so‘m.'
        if c.get('pendingUsd') or c.get('pendingUzs'):
            text += f' Kassir tasdig‘ida: {_money(c["pendingUsd"])} va {_num(c["pendingUzs"])} so‘m.'
        return text

    if topic == 'agent':
        agents = [a for a in executive.executive(db, exec_period, now=now).get('agents') or [] if a['realizationUsd'] or a['paymentsUsd']]
        if not agents:
            return f'{when.capitalize()} agentlar bo‘yicha savdo yo‘q.'
        top = agents[:3]
        rest = '; '.join(f'{a["agent"]} — {_money(a["realizationUsd"])}' for a in top[1:])
        text = f'{when.capitalize()} eng yaxshi agent: {top[0]["agent"]} — realizatsiya {_money(top[0]["realizationUsd"])}, to‘lov {_money(top[0]["paymentsUsd"])}.'
        return text + (f' Keyingilar: {rest}.' if rest else '')

    if topic == 'product':
        if report_period:
            r = manager_api.period_report(db, report_period, None, None, now=now)
        else:   # kecha: aniq sana bilan
            day = (datetime.fromtimestamp(now or time.time(), TZ) - timedelta(days=1)).strftime('%Y-%m-%d')
            r = manager_api.period_report(db, 'custom', day, day, now=now)
        products = [p for p in r.get('products') or [] if p.get('deliveredUsd')]
        if report_period:
            when = (r.get('label') or when).lower()   # mahsulot hisoboti o'z davri bilan (masalan "shu oy")
        if not products:
            return f'{when.capitalize()} mahsulot sotilmagan.'
        top = products[:3]
        return f'{when.capitalize()} eng ko‘p sotilgan: ' + '; '.join(
            f'{p["name"]} — {_num(p.get("deliveredQty"))} dona, {_money(p["deliveredUsd"])}' for p in top) + '.'

    if topic == 'stock':
        s = manager_api.warehouse(db, 'open')['stock']
        low = [p['name'] for p in s.get('products') or [] if p['stock'] <= 0][:5]
        text = f'Omborda jami {_num(s["stockTotal"])} dona. Bugun berildi: {_num(s["issuedToday"])}, shu oy kirim: {_num(s["receivedMonth"])}.'
        return text + (f' Tugagan: {", ".join(low)}.' if low else '')

    if topic == 'orders':
        c = manager_api.warehouse(db, 'open')['counts']
        return (f'Yangi buyurtmalar: {c.get("new", 0)}, tayyorlanmoqda: {c.get("preparing", 0)}, '
                f'yuklangan: {c.get("loaded", 0)}.')
    return HELP


def ask(db, question, history=None, now=None):
    question = ' '.join(str(question or '').split())
    if not question:
        raise ValueError('Savolni yozing yoki ayting.')
    if len(question) > MAX_QUESTION:
        raise ValueError(f'Savol {MAX_QUESTION} belgidan oshmasin.')
    topic, period, q = detect(question)
    if topic is None and not re.search(r'bugun|kecha|hafta|oy|qancha|qalay|holat|natija|hisobot', q):
        return {'answer': HELP, 'offTopic': True}
    return {'answer': answer(db, topic, period, q, now=now), 'offTopic': False}
