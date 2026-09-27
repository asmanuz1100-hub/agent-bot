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
    funded_today_uzs = int(db.execute("""SELECT COALESCE(SUM(amount_uzs),0) FROM agent_funds
        WHERE kind='topup' AND ts>=? AND ts<?""",(start,end)).fetchone()[0] or 0)
    pending = db.execute("""SELECT COUNT(*) AS count,
        COALESCE(SUM(amount_usd),0) AS usd, COALESCE(SUM(amount),0) AS uzs
        FROM handovers WHERE status='pending'""").fetchone()
    wallet_total = int(db.execute("""SELECT COALESCE(SUM(CASE WHEN kind='topup' THEN amount_usd
        WHEN kind='expense' THEN -amount_usd ELSE 0 END),0) FROM agent_funds""").fetchone()[0] or 0)
    wallet_total_uzs = int(db.execute("""SELECT COALESCE(SUM(CASE WHEN kind='topup' THEN amount_uzs
        WHEN kind='expense' THEN -amount_uzs ELSE 0 END),0) FROM agent_funds""").fetchone()[0] or 0)
    return {
        'acceptedToday': accepted_today,
        'cashExpenseToday': expense_today,
        'fundedToday': funded_today,
        'fundedTodayUzs': funded_today_uzs,
        'cashOutToday': expense_today + funded_today,
        'netToday': accepted_today - expense_today - funded_today,
        'pendingCount': int(pending['count'] or 0),
        'pendingUsd': int(pending['usd'] or 0),
        'pendingUzs': int(pending['uzs'] or 0),
        'agentWalletTotal': wallet_total,
        'agentWalletTotalUzs': wallet_total_uzs,
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
    for x in db.execute("""SELECT f.id,f.kind,f.amount_usd,f.amount_uzs,f.rate_uzs_per_usd,f.category,f.note,f.ts,
            a.name AS agent_name,u.name AS actor_name FROM agent_funds f
            LEFT JOIN users a ON a.id=f.agent LEFT JOIN users u ON u.id=f.actor
            ORDER BY f.ts DESC LIMIT 60""").fetchall():
        rows.append({'kind':'agent_'+x['kind'],'id':int(x['id']),'ts':int(x['ts'] or 0),
                     'amount_usd':int(x['amount_usd'] or 0),'amount_uzs':int(x['amount_uzs'] or 0),
                     'rate_uzs_per_usd':int(x['rate_uzs_per_usd'] or 0),
                     'category':x['category'] or '','agent_name':x['agent_name'] or '',
                     'actor_name':x['actor_name'] or '','note':x['note'] or ''})
    rows.sort(key=lambda x:(x['ts'],x['id']),reverse=True)
    return rows[:80]


def _cashier_debtors(db):
    debt_rows=db.execute("""SELECT c.id,c.agent,c.name,c.shop_name,c.phone,c.address,u.name AS agent_name,
        COALESCE(SUM(CASE WHEN e.kind='delivery' THEN e.amount_usd
                          WHEN e.kind IN ('payment','return') THEN -e.amount_usd ELSE 0 END),0) AS debt_usd
        FROM clients c LEFT JOIN users u ON u.id=c.agent LEFT JOIN events e ON e.client=c.id
        GROUP BY c.id,c.agent,c.name,c.shop_name,c.phone,c.address,u.name
        HAVING COALESCE(SUM(CASE WHEN e.kind='delivery' THEN e.amount_usd
                                 WHEN e.kind IN ('payment','return') THEN -e.amount_usd ELSE 0 END),0)>0
        ORDER BY debt_usd DESC,c.id DESC LIMIT 1000""").fetchall()
    task_rows=db.execute("""SELECT t.*,ua.name AS assigned_name,uc.name AS cashier_name
        FROM collection_tasks t LEFT JOIN users ua ON ua.id=t.agent LEFT JOIN users uc ON uc.id=t.cashier
        WHERE t.status='open' ORDER BY t.created_ts DESC,t.id DESC""").fetchall()
    open_by_client={}
    for t in task_rows:
        cid=int(t['client'])
        if cid not in open_by_client:open_by_client[cid]=t
    out=[]
    total=0
    for x in debt_rows:
        debt=int(x['debt_usd'] or 0);total+=debt
        task=open_by_client.get(int(x['id']))
        out.append({'id':int(x['id']),'name':x['shop_name'] or x['name'] or f"Мижоз #{x['id']}",
                    'person':x['name'] or '','phone':x['phone'] or '','address':x['address'] or '',
                    'agentId':int(x['agent']),'agentName':x['agent_name'] or str(x['agent']),
                    'debtUsd':debt,
                    'task':({'id':int(task['id']),'agentId':int(task['agent']),
                             'agentName':task['assigned_name'] or str(task['agent']),
                             'cashierName':task['cashier_name'] or str(task['cashier']),
                             'debtUsd':int(task['debt_usd'] or 0),'note':task['note'] or '',
                             'createdTs':int(task['created_ts'] or 0)}
                            if task else None)})
    return out,total


def dashboard(db, actor):
    name = require_cashier(db, actor)
    pending = [dict(x) for x in db.execute("""SELECT h.*,u.name AS agent_name FROM handovers h
        LEFT JOIN users u ON u.id=h.agent WHERE h.status='pending' ORDER BY h.ts,h.id""").fetchall()]
    history = [dict(x) for x in db.execute("""SELECT h.*,u.name AS agent_name,c.name AS cashier_name FROM handovers h
        LEFT JOIN users u ON u.id=h.agent LEFT JOIN users c ON c.id=h.cashier
        WHERE h.status!='pending' ORDER BY h.accepted_ts DESC,h.id DESC LIMIT 100""").fetchall()]
    expenses = [dict(x) for x in db.execute("""SELECT e.*,u.name AS cashier_name FROM cashier_expenses e
        LEFT JOIN users u ON u.id=e.cashier ORDER BY e.ts DESC,e.id DESC LIMIT 100""").fetchall()]
    agents = [{'id': int(x['id']), 'name': x['name'],
               'fund_balance': core.agent_fund_balance_usd(db,int(x['id'])),
               'fund_balance_uzs': core.agent_fund_balance_uzs(db,int(x['id']))}
              for x in db.execute("SELECT id,name FROM users WHERE role='agent' ORDER BY name,id").fetchall()]
    agents.sort(key=lambda x:(-x['fund_balance_uzs'],x['name'] or ''))
    agent_funds = [dict(x) for x in db.execute("""SELECT f.*,a.name AS agent_name,u.name AS actor_name
        FROM agent_funds f LEFT JOIN users a ON a.id=f.agent LEFT JOIN users u ON u.id=f.actor
        ORDER BY f.ts DESC,f.id DESC LIMIT 100""").fetchall()]
    debtors,total_debt=_cashier_debtors(db)
    return {'name': name, 'balance': core.cashier_balance_usd(db), 'rate': core.cashier_rate(db),
            'pending': pending, 'history': history, 'expenses': expenses,
            'agents': agents, 'agentFunds': agent_funds, 'summary': _cashier_summary(db),
            'activity': _cashier_activity(db),'debtors':debtors,
            'debtSummary':{'count':len(debtors),'totalUsd':total_debt,
                           'assignedCount':sum(1 for x in debtors if x['task'])},
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
    if action not in ('accept', 'reject', 'expense', 'rate', 'fund', 'assign_debt'):
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
    if action == 'assign_debt':
        try:client=int(payload.get('clientId') or 0);agent=int(payload.get('agentId') or 0)
        except (TypeError,ValueError):raise ValueError('Мижоз ёки агент нотўғри.')
        client_row=db.execute("SELECT id,agent,name,shop_name,phone,address FROM clients WHERE id=?",(client,)).fetchone()
        if not client_row:raise ValueError('Мижоз топилмади.')
        agent_row=db.execute("SELECT id,name FROM users WHERE id=? AND role='agent'",(agent,)).fetchone()
        if not agent_row:raise ValueError('Фаол агентни танланг.')
        debt=core.client_debt_usd(db,client)
        if debt<=0:raise ValueError('Бу мижозда жорий қарз йўқ.')
        note=str(payload.get('note') or '').strip()
        if len(note)>1000:raise ValueError('Изоҳ 1000 белгидан ошмасин.')
        now=int(time.time())
        existing=db.execute("SELECT id FROM collection_tasks WHERE client=? AND status='open' ORDER BY id DESC LIMIT 1",(client,)).fetchone()
        if existing:
            tid=int(existing['id'])
            db.execute("""UPDATE collection_tasks SET agent=?,cashier=?,debt_usd=?,note=?,created_ts=?
                WHERE id=?""",(agent,actor,debt,note,now,tid))
        else:
            row=db.execute("""INSERT INTO collection_tasks(client,agent,cashier,debt_usd,note,status,created_ts)
                VALUES(?,?,?,?,?,'open',?) RETURNING id""",(client,agent,actor,debt,note,now)).fetchone()
            tid=int(row[0])
        label=client_row['shop_name'] or client_row['name'] or f"Мижоз #{client}"
        notify={'agent':agent,'text':f"📌 ҚАРЗ УНДИРИШ ТОПШИРИҒИ #{tid}\n"
                f"🏪 Мижоз: {label}\n💵 Жорий қарз: {cashier_pending.usd(debt)} USD\n"
                f"📞 {client_row['phone'] or 'Телефон йўқ'}\n"
                f"📍 {client_row['address'] or 'Манзил йўқ'}"
                +(f"\n📝 {note}" if note else '')
                +f"\n👤 Кассир: {require_cashier(db,actor)}"}
        db.execute('INSERT INTO meta(key,value) VALUES(?,?)', (key, fingerprint))
        return {'ok':True,'taskId':tid,'_notify':notify}
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
        amount_uzs = core.parse_whole_som(payload.get('amount'),'Сумма')
        expected_rate = core.parse_whole_som(payload.get('expectedRate'),'Курс')
        note = payload.get('note', '')
        fid, amount, rate = core.fund_agent_expense_uzs(
            db, actor, agent, amount_uzs, note, source, expected_rate=expected_rate)
        balance_uzs = core.agent_fund_balance_uzs(db, agent)
        agent_row = db.execute("SELECT name FROM users WHERE id=? AND role='agent'", (agent,)).fetchone()
        notify = {'agent': agent, 'text': f"💳 АГЕНТ ҲИСОБИ ТЎЛДИРИЛДИ #{fid}\n"
                  f"Агент: {agent_row[0] if agent_row else agent}\n"
                  f"Сумма: {amount_uzs:,} сўм\n"
                  f"Курс: 1 USD = {rate:,} сўм\n"
                  f"Умумий ҳисоб: {cashier_pending.usd(amount)} USD\n"
                  f"Янги харажат баланси: {balance_uzs:,} сўм\n"
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
