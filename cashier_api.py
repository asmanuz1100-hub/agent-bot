"""Cashier Mini App: signed Telegram identity, existing ledger rules."""
import hashlib
import json
import re
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import core
import cashier_pending
import cashier_daily
import manager_api


def require_cashier(db, actor):
    row = db.execute("SELECT name FROM users WHERE id=? AND role IN ('cashier','admin')", (actor,)).fetchone()
    if not row:
        raise ValueError('Бу бўлим фақат кассир ёки админ учун.')
    return row[0]


TZ = ZoneInfo('Asia/Tashkent')


def _cashier_summary(db):
    now = datetime.now(TZ)
    start = int(now.replace(hour=0, minute=0, second=0, microsecond=0).timestamp())
    end = int((now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)).timestamp())
    accepted_today = int(db.execute("""SELECT COALESCE(SUM(amount_usd),0) FROM handovers
        WHERE status='accepted' AND accepted_ts>=? AND accepted_ts<?""",(start,end)).fetchone()[0] or 0)
    expense_today = int(db.execute("""SELECT COALESCE(SUM(amount_usd),0) FROM cashier_expenses
        WHERE ts>=? AND ts<?""",(start,end)).fetchone()[0] or 0)
    funded_today = int(db.execute("""SELECT COALESCE(SUM(amount_usd),0) FROM agent_funds
        WHERE kind='topup' AND ts>=? AND ts<?""",(start,end)).fetchone()[0] or 0)
    pending = db.execute("""SELECT COUNT(*) AS count,
        COALESCE(SUM(amount_usd),0) AS usd, COALESCE(SUM(amount),0) AS uzs
        FROM handovers WHERE status='pending'""").fetchone()
    wallet_total = int(db.execute("""SELECT COALESCE(SUM(CASE WHEN kind='topup' THEN amount_usd
        WHEN kind='expense' THEN -amount_usd ELSE 0 END),0) FROM agent_funds""").fetchone()[0] or 0)
    return {
        'acceptedToday': accepted_today,
        'cashExpenseToday': expense_today,
        'fundedToday': funded_today,
        'cashOutToday': expense_today + funded_today,
        'netToday': accepted_today - expense_today - funded_today,
        'pendingCount': int(pending['count'] or 0),
        'pendingUsd': int(pending['usd'] or 0),
        'pendingUzs': int(pending['uzs'] or 0),
        'agentWalletTotal': wallet_total,
    }


def _cashier_activity(db):
    rows=[]
    for x in db.execute("""SELECT h.id,h.agent,h.cashier,h.amount_usd,h.amount,h.status,
            h.ts,h.accepted_ts,a.name AS agent_name,c.name AS actor_name
            FROM handovers h LEFT JOIN users a ON a.id=h.agent LEFT JOIN users c ON c.id=h.cashier
            WHERE h.status!='pending' ORDER BY COALESCE(h.accepted_ts,h.ts) DESC LIMIT 40""").fetchall():
        rows.append({'kind':'handover','id':int(x['id']),'ts':int(x['accepted_ts'] or x['ts'] or 0),
                     'status':x['status'],'amount_usd':int(x['amount_usd'] or 0),'amount_uzs':int(x['amount'] or 0),
                     'agent_name':x['agent_name'] or str(x['agent']),'actor_name':x['actor_name'] or '',
                     'note':''})
    for x in db.execute("""SELECT e.id,e.amount_usd,e.amount_uzs,e.currency,e.category,e.recipient,e.note,e.ts,
            u.name AS actor_name FROM cashier_expenses e LEFT JOIN users u ON u.id=e.cashier
            ORDER BY e.ts DESC LIMIT 40""").fetchall():
        rows.append({'kind':'cash_expense','id':int(x['id']),'ts':int(x['ts'] or 0),
                     'amount_usd':int(x['amount_usd'] or 0),'amount_uzs':int(x['amount_uzs'] or 0),
                     'currency':x['currency'],'category':x['category'],'recipient':x['recipient'],
                     'actor_name':x['actor_name'] or '','note':x['note'] or ''})
    for x in db.execute("""SELECT f.id,f.kind,f.amount_usd,f.category,f.note,f.ts,
            a.name AS agent_name,u.name AS actor_name FROM agent_funds f
            LEFT JOIN users a ON a.id=f.agent LEFT JOIN users u ON u.id=f.actor
            ORDER BY f.ts DESC LIMIT 60""").fetchall():
        rows.append({'kind':'agent_'+x['kind'],'id':int(x['id']),'ts':int(x['ts'] or 0),
                     'amount_usd':int(x['amount_usd'] or 0),'amount_uzs':0,
                     'category':x['category'] or '','agent_name':x['agent_name'] or '',
                     'actor_name':x['actor_name'] or '','note':x['note'] or ''})
    rows.sort(key=lambda x:(x['ts'],x['id']),reverse=True)
    return rows[:80]


def dashboard(db, actor):
    name = require_cashier(db, actor)
    pending = [dict(x) for x in db.execute("""SELECT h.*,u.name AS agent_name FROM handovers h
        LEFT JOIN users u ON u.id=h.agent WHERE h.status='pending' ORDER BY h.ts,h.id""").fetchall()]
    history = [dict(x) for x in db.execute("""SELECT h.*,u.name AS agent_name,c.name AS cashier_name FROM handovers h
        LEFT JOIN users u ON u.id=h.agent LEFT JOIN users c ON c.id=h.cashier
        WHERE h.status!='pending' ORDER BY h.accepted_ts DESC,h.id DESC LIMIT 100""").fetchall()]
    expenses = [dict(x) for x in db.execute("""SELECT e.*,u.name AS cashier_name FROM cashier_expenses e
        LEFT JOIN users u ON u.id=e.cashier ORDER BY e.ts DESC,e.id DESC LIMIT 100""").fetchall()]
    agents = [{'id': int(x['id']), 'name': x['name'], 'fund_balance': core.agent_fund_balance_usd(db,int(x['id']))}
              for x in db.execute("SELECT id,name FROM users WHERE role='agent' ORDER BY name,id").fetchall()]
    agents.sort(key=lambda x:(-x['fund_balance'],x['name'] or ''))
    agent_funds = [dict(x) for x in db.execute("""SELECT f.*,a.name AS agent_name,u.name AS actor_name
        FROM agent_funds f LEFT JOIN users a ON a.id=f.agent LEFT JOIN users u ON u.id=f.actor
        ORDER BY f.ts DESC,f.id DESC LIMIT 100""").fetchall()]
    return {'name': name, 'balance': core.cashier_balance_usd(db), 'rate': core.cashier_rate(db),
            'pending': pending, 'history': history, 'expenses': expenses,
            'agents': agents, 'agentFunds': agent_funds, 'summary': _cashier_summary(db),
            'activity': _cashier_activity(db),
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
    if action not in ('accept', 'reject', 'expense', 'rate', 'fund'):
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
    elif action == 'fund':
        agent = int(payload.get('agentId') or 0)
        amount = core.money(payload.get('amount'))
        note = payload.get('note', '')
        fid = core.fund_agent_expense(db, actor, agent, amount, note, source)
        balance = core.agent_fund_balance_usd(db, agent)
        agent_row = db.execute("SELECT name FROM users WHERE id=? AND role='agent'", (agent,)).fetchone()
        notify = {'agent': agent, 'text': f"💳 АГЕНТ ҲИСОБИ ТЎЛДИРИЛДИ #{fid}\n"
                  f"Агент: {agent_row[0] if agent_row else agent}\n"
                  f"Сумма: {cashier_pending.usd(amount)} USD\n"
                  f"Янги харажат баланси: {cashier_pending.usd(balance)} USD\n"
                  f"Кассир: {require_cashier(db,actor)}"}
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
