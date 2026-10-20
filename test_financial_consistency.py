"""Phase 5: bir xil mijoz qarzi va bir xil pul Agent, Kassir va Rahbar (Mini App + Web) ekranlarida bir xil chiqishi.

Ssenariy: naqd dollar, so'm (kelishilgan kurs), qaytarish, karta to'lovi kassir tasdiqlashidan oldin va keyin
(ortiqcha to'lov avansga aylanadi), kassirga dollar topshirish (kutilmoqda → qabul qilindi).
"""
import time
import unittest

import agent_api
import analytics
import cashier_api
import core
import executive
import manager_api

DAY = 86400


class FinancialConsistencyTests(unittest.TestCase):
    def setUp(self):
        self.db = core.connect(':memory:')
        self.db.executemany('INSERT INTO users(id,role,name) VALUES(?,?,?)',
                            [(1, 'admin', 'Rahbar'), (2, 'agent', 'Ali'), (3, 'agent', 'Vali'), (4, 'cashier', 'Kassir')])
        self.now = int(time.time())
        t = self.now - 3600
        for cid, agent in ((10, 2), (11, 2), (20, 3), (21, 3)):
            self.db.execute("INSERT INTO clients(id,agent,name,phone,region,created_ts) VALUES(?,?,?,?,?,?)",
                            (cid, agent, f'C{cid}', f'+99890{cid:07d}', 'Qo‘qon', self.now - 40 * DAY))
        src = iter(range(100, 1000))

        def ev(agent, cid, kind, cents, ts):
            self.db.execute("""INSERT INTO events(actor,agent,client,kind,pack,qty,amount,amount_usd,note,ts,source)
                VALUES(?,?,?,?,1,1,0,?,'',?,?)""", (agent, agent, cid, kind, cents, ts, next(src)))
        ev(2, 10, 'delivery', 20000, t - 35 * DAY)          # C10: 200$ (35 kun oldin)
        ev(2, 11, 'delivery', 5000, t)                       # C11: 50$
        ev(3, 20, 'delivery', 3000, t)                       # C20: 30$
        core.record_client_payment(self.db, 2, 2, 10, 'USD', 4000, 'cash', source=next(src))            # 40$ naqd
        core.record_client_payment(self.db, 2, 2, 10, 'UZS', 254000, 'cash', rate=12700, source=next(src))  # 20$ so'mda
        ev(2, 10, 'return', 1000, t + 60)                    # 10$ qaytarish → C10 qarzi 130$
        self.card_id = core.submit_card_payment(self.db, 3, 20, 'USD', 5000, source=next(src))[0]  # 50$ karta, kutilmoqda
        self.src = src

    # --- har bir ekran qarzni qanday ko'rsatadi -------------------------------------------------
    def debts(self):
        db = self.db
        out = {'core': {}, 'agent': {}, 'cashier': {}, 'rahbar': {}, 'rahbar_detail': {}, 'insights': {}}
        for cid in (10, 11, 20, 21):
            out['core'][cid] = core.client_debt_usd(db, cid)
            out['rahbar_detail'][cid] = round(manager_api.client_detail(db, cid)['debtUsd'] * 100)
        for agent in (2, 3):
            for c in agent_api.snapshot(db, agent)['clients']:
                out['agent'][c['id']] = round(c['debtUsd'] * 100)
        for c in manager_api.dashboard(db)['clients']:
            out['rahbar'][c['id']] = round(c['debtUsd'] * 100)
        rows, _ = cashier_api._cashier_debtors(db)
        out['cashier'] = {r['id']: r['debtUsd'] for r in rows}
        for r in analytics.insights(db, 'month')['clients']:
            out['insights'][r['id']] = r['debtNowCents']
        return out

    def assert_debts(self, expected):
        d = self.debts()
        for screen in ('core', 'agent', 'rahbar', 'rahbar_detail', 'insights'):
            self.assertEqual(d[screen], expected, screen)
        # Kassir faqat qarzdorlarni ro'yxatlaydi
        self.assertEqual(d['cashier'], {k: v for k, v in expected.items() if v > 0})

    def assert_totals(self, debt_cents, advance_cents):
        dash = manager_api.dashboard(self.db)
        _, cashier_total = cashier_api._cashier_debtors(self.db)
        ex = executive.executive(self.db, 'today')
        ins = analytics.insights(self.db, 'month')['summary']
        self.assertEqual(round(dash['summary']['debtUsd'] * 100), debt_cents)
        self.assertEqual(round(dash['summary']['advanceUsd'] * 100), advance_cents)
        self.assertEqual(cashier_total, debt_cents)
        self.assertEqual(round(next(k for k in ex['kpis'] if k['key'] == 'debt')['value'] * 100), debt_cents)
        self.assertEqual(round(ex['advanceUsd'] * 100), advance_cents)
        self.assertEqual(round(sum(b['usd'] for b in ex['debtAging']) * 100), debt_cents)
        self.assertEqual(ins['debtCents'], debt_cents)
        self.assertEqual(ins['advanceCents'], advance_cents)

    def test_client_debt_matches_on_every_screen_before_and_after_card_confirmation(self):
        # Karta to'lovi kassir tasdiqlamaguncha qarzni kamaytirmaydi.
        self.assert_debts({10: 13000, 11: 5000, 20: 3000, 21: 0})
        self.assert_totals(21000, 0)
        core.decide_card_payment(self.db, 4, self.card_id, True)
        # Tasdiqlangandan keyin C20: 30$ - 50$ = -20$ (avans) — umumiy qarzga qo'shilmaydi.
        self.assert_debts({10: 13000, 11: 5000, 20: -2000, 21: 0})
        self.assert_totals(18000, 2000)

    def test_debt_aging_uses_fifo_on_real_payments(self):
        ex = executive.executive(self.db, 'today')
        aging = {b['label']: round(b['usd'] * 100) for b in ex['debtAging']}
        # C10: 200$ (35 kun) − 40 − 20 − 10 = 130$ eski partiyadan qoladi → 31–60; C11 50$ + C20 30$ → 0–30.
        self.assertEqual(aging, {'0–30': 8000, '31–60': 13000, '61–90': 0, '90+': 0})

    def test_agent_cash_matches_and_usd_uzs_stay_apart(self):
        def views():
            ex = {a['agentId']: a for a in executive.executive(self.db, 'today')['agentsCash']['agents']}
            out = {}
            for agent in (2, 3):
                s = agent_api.snapshot(self.db, agent)['summary']
                d = manager_api.agent_detail(self.db, agent)
                e = ex.get(agent, {'cashUsd': 0, 'cashUzs': 0, 'pendingUsd': 0})
                out[agent] = {'agent': (round(s['cashOnHandUsd'] * 100), s['cashOnHandUzs']),
                              'rahbar': (round(d['cashUsd'] * 100), d['legacyCashUzs'] // 100),
                              'web': (round(e['cashUsd'] * 100), e['cashUzs']),
                              'core': (core.cash_usd(self.db, agent), core.cash_som(self.db, agent))}
            return out
        v = views()
        for agent, exp in ((2, (4000, 254000)), (3, (0, 0))):   # karta agentda turmaydi
            self.assertEqual(set(v[agent].values()), {exp}, v[agent])
        # Ali kassirga 15$ topshiradi: kutilmoqda → pul hali agentda, kassirda "kutilmoqda".
        hid = self.db.execute("""INSERT INTO handovers(agent,amount,amount_usd,status,cashier,source,ts)
            VALUES(2,0,1500,'pending',NULL,?,?) RETURNING id""", (next(self.src), self.now)).fetchone()[0]
        self.assertEqual(round(executive.executive(self.db, 'today')['agentsCash']['pendingUsd'] * 100), 1500)
        self.assertEqual(round(manager_api.dashboard(self.db)['cash']['pendingUsd'] * 100), 1500)
        self.assertEqual(cashier_api.dashboard(self.db, 4)['summary']['pendingUsd'], 1500)
        self.db.execute("UPDATE handovers SET status='accepted',cashier=4,accepted_ts=? WHERE id=?", (self.now, hid))
        v = views()
        self.assertEqual(set(v[2].values()), {(2500, 254000)}, v[2])
        # Kassa: Rahbar va Kassir bir xil hamyonlarni ko'radi.
        dash = manager_api.dashboard(self.db)['cash']
        cash = cashier_api.dashboard(self.db, 4)['summary']
        self.assertEqual(round(dash['wallets']['cashUsd'] * 100), cash['wallets']['cashUsd'])
        self.assertEqual(dash['wallets']['cashUzs'], cash['wallets']['cashUzs'])
        self.assertEqual(round(dash['balanceUsd'] * 100), core.cashier_balance_usd(self.db))

    def test_period_figures_match_between_rahbar_screens(self):
        dash = manager_api.dashboard(self.db)
        ex = executive.executive(self.db, 'today')
        k = {x['key']: x['value'] for x in ex['kpis']}
        self.assertEqual(k['realization'], dash['reports']['today']['deliveredUsd'])
        self.assertEqual(k['collected'], dash['reports']['today']['paymentsUsd'])
        rep = manager_api.period_report(self.db, 'today')
        self.assertEqual(k['realization'], rep['deliveredUsd'])
        self.assertEqual(k['collected'], rep['paymentsUsd'])
        c = ex['collections']
        self.assertEqual((c['cashUsd'], c['cashUzs'], c['cashUzsAsUsd'], c['cardUsd']), (40, 254000, 20, 0))


if __name__ == '__main__':
    unittest.main()
