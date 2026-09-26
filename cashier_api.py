"""Cashier Mini App: signed Telegram identity, existing ledger rules."""
import hashlib
import json
import re
import time
import core
import cashier_pending
import cashier_daily
import manager_api


def require_cashier(db, actor):
    row = db.execute("SELECT name FROM users WHERE id=? AND role='cashier'", (actor,)).fetchone()
    if not row:
        raise ValueError('Бу бўлим фақат кассир учун.')
    return row[0]


def dashboard(db, actor):
    name = require_cashier(db, actor)
    pending = [dict(x) for x in db.execute("""SELECT h.*,u.name AS agent_name FROM handovers h
        LEFT JOIN users u ON u.id=h.agent WHERE h.status='pending' ORDER BY h.ts,h.id""").fetchall()]
    history = [dict(x) for x in db.execute("""SELECT h.*,u.name AS agent_name,c.name AS cashier_name FROM handovers h
        LEFT JOIN users u ON u.id=h.agent LEFT JOIN users c ON c.id=h.cashier
        WHERE h.status!='pending' ORDER BY h.accepted_ts DESC,h.id DESC LIMIT 100""").fetchall()]
    expenses = [dict(x) for x in db.execute("""SELECT e.*,u.name AS cashier_name FROM cashier_expenses e
        LEFT JOIN users u ON u.id=e.cashier ORDER BY e.ts DESC,e.id DESC LIMIT 100""").fetchall()]
    return {'name': name, 'balance': core.cashier_balance_usd(db), 'rate': core.cashier_rate(db),
            'pending': pending, 'history': history, 'expenses': expenses,
            'categories': list(core.CASHIER_EXPENSE_CATEGORIES), 'daily': cashier_daily.report(db)}


def review(db, actor, hid):
    require_cashier(db, actor)
    row = db.execute("SELECT * FROM handovers WHERE id=? AND status='pending'", (int(hid),)).fetchone()
    if not row:
        raise ValueError('Топшириқ топилмади ёки аввал ҳал қилинган.')
    db.execute('INSERT INTO meta(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',
               (f'cashier_review:{actor}:{row["id"]}', str(int(time.time()))))
    return {'context': cashier_pending.handover_context(db, row), 'handover': dict(row)}


def mutate(db, actor, action, payload):
    require_cashier(db, actor)
    if action not in ('accept', 'reject', 'expense', 'rate'):
        raise ValueError('Амал нотўғри.')
    rid = payload.get('requestId', '')
    if not isinstance(rid, str) or not re.fullmatch(r'[A-Za-z0-9_-]{8,96}', rid):
        raise ValueError('Сўров IDси нотўғри. Панелни қайта очинг.')
    key = f'cashier_api:{actor}:{rid}'
    fingerprint = hashlib.sha256(json.dumps({k:v for k,v in payload.items() if k!='initData'}, sort_keys=True).encode()).hexdigest()
    # Serialize same-cashier retries; core functions also lock the shared cashbox/agent.
    core.lock_agent(db, actor)
    old = db.execute('SELECT value FROM meta WHERE key=?', (key,)).fetchone()
    if old:
        if old[0] != fingerprint:
            raise ValueError('Бу сўров бошқа амал учун ишлатилган.')
        return {'ok': True, 'duplicate': True}
    source = 2**60 + int.from_bytes(hashlib.sha256(key.encode()).digest()[:7], 'big')
    notify = {'text': '', 'agent': None}
    if action in ('accept', 'reject'):
        hid = int(payload.get('handoverId') or 0)
        reviewed = db.execute('SELECT value FROM meta WHERE key=?', (f'cashier_review:{actor}:{hid}',)).fetchone()
        if not reviewed or int(reviewed[0]) < int(time.time())-900:
            raise ValueError('Аввал топшириқни кўриб чиқинг.')
        row = db.execute('SELECT * FROM handovers WHERE id=?', (hid,)).fetchone()
        core.accept(db, actor, hid, action=='accept')
        amount = f"{cashier_pending.usd(row['amount_usd'])} USD" if row['amount_usd'] else f"{cashier_pending.usd(row['amount'])} сўм"
        notify = {'agent': int(row['agent']), 'text': f"{'✅ ҚАБУЛ ҚИЛИНДИ' if action=='accept' else '❌ РАД ЭТИЛДИ'}\nТопшириш #{hid} · {amount}\nКассир: {require_cashier(db,actor)}"}
    elif action == 'expense':
        currency = payload.get('currency')
        args = (payload.get('category'), payload.get('recipient'), payload.get('note', ''), source)
        if currency == 'USD':
            amount = core.money(payload.get('amount'))
            eid = core.add_cashier_expense(db, actor, amount, *args)
        elif currency == 'UZS':
            som = core.parse_whole_som(payload.get('amount'))
            rate = core.parse_whole_som(payload.get('expectedRate'), 'Курс')
            eid, amount, _ = core.add_cashier_expense_uzs(db, actor, som, *args, expected_rate=rate)
        else:
            raise ValueError('Валютани танланг.')
        notify['text'] = f"🧾 КАССА ХАРАЖАТИ #{eid}\n{cashier_pending.usd(amount)} USD · {payload.get('category')}\n{payload.get('recipient')}\nКассир: {require_cashier(db,actor)}"
    else:
        rate = core.parse_whole_som(payload.get('rate'), 'Курс')
        core.set_cashier_rate(db, actor, rate, source)
        notify['text'] = f'💱 Касса курси: 1 USD = {rate:,} сўм\nКассир: {require_cashier(db,actor)}'
    db.execute('INSERT INTO meta(key,value) VALUES(?,?)', (key, fingerprint))
    return {'ok': True, '_notify': notify}
