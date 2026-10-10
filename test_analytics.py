"""Hisobotning biznes natijalari: realizatsiya, davr oxiridagi qarz, qarz yoshi, qamrov,
agent portfeli va "Bugun kimga". Kutilgan qiymatlar qo'lda hisoblangan, kod takrorlanmagan.

PostgreSQL bilan ham ishlaydi: TEST_DATABASE_URL berilsa PgInsightsTests shu bazada yuradi.
"""
import os
import time
import unittest
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

import analytics
import core

TZ = ZoneInfo('Asia/Tashkent')
DAY = 86400


def T(y, m, d, h=12, mi=0):
    return int(datetime(y, m, d, h, mi, tzinfo=TZ).timestamp())


NOW = T(2026, 10, 9, 15, 0)          # payshanba, 09.10.2026 15:00 Toshkent
PRICE = 10000                        # 1 dona = 100.00 $


class InsightsTests(unittest.TestCase):
    def make_db(self):
        return core.connect(':memory:')

    def setUp(self):
        self.db = self.make_db()
        self.db.executemany('INSERT INTO users(id,role,name) VALUES(?,?,?)',
                            [(1, 'admin', 'Rahbar'), (2, 'agent', 'Ali'), (3, 'agent', 'Vali')])
        self.db.execute('UPDATE products SET price=? WHERE pack=1', (PRICE,))
        self.src = 1000
        core.record(self.db, 1, 2, None, 'load', 1, 1000, source=1, currency='USD', ts=T(2026, 1, 1))
        core.record(self.db, 1, 3, None, 'load', 1, 1000, source=2, currency='USD', ts=T(2026, 1, 1))

    def tearDown(self):
        self.db.close()

    def client(self, cid, agent=2, shop='Do‘kon', region='Qo‘qon', map_only=0, person='Ism'):
        self.db.execute("""INSERT INTO clients(id,agent,name,shop_name,region,phone,created_ts,map_only)
            VALUES(?,?,?,?,?,?,?,?)""", (cid, agent, person, shop, region, f'+99890{cid:07d}', T(2026, 1, 1), map_only))

    def ev(self, client, kind, qty=0, ts=None, value=0, agent=2):
        self.src += 1
        core.record(self.db, agent, agent, client, kind, 1, qty, value, '', self.src, currency='USD', ts=ts)

    def month(self, agent=None):
        return analytics.insights(self.db, 'month', agent=agent, now=NOW)

    def row(self, out, cid):
        return next(c for c in out['clients'] if c['id'] == cid)

    # A. Realizatsiya = "Sotildi", berilgan tovar emas
    def test_realization_is_sold_value_not_delivered(self):
        self.client(10)
        self.ev(10, 'delivery', 10, T(2026, 10, 2))        # 1 000 $ berildi
        self.ev(10, 'sold', 2, T(2026, 10, 5))             # 200 $ sotildi
        r = self.row(self.month(), 10)
        self.assertEqual(r['deliveredCents'], 100000)
        self.assertEqual(r['realizationCents'], 20000)
        self.assertEqual(r['stockQty'], 8)
        self.assertEqual(r['stockValueCents'], 80000)
        self.assertEqual(r['payment']['debtEndCents'], 100000)   # sotish qarzni o'zgartirmaydi

    def test_unsold_return_reduces_debt_not_realization(self):
        self.client(10)
        self.ev(10, 'delivery', 10, T(2026, 10, 2))
        self.ev(10, 'sold', 2, T(2026, 10, 4))
        self.ev(10, 'return', 3, T(2026, 10, 6))           # sotilmagan 3 dona qaytdi
        r = self.row(self.month(), 10)
        self.assertEqual(r['realizationCents'], 20000)
        self.assertEqual(r['returnedCents'], 30000)
        self.assertEqual(r['payment']['debtEndCents'], 70000)
        self.assertEqual(r['stockQty'], 5)

    def test_missing_realization_is_not_zero(self):
        self.client(10)
        self.ev(10, 'delivery', 4, T(2026, 9, 1))
        self.ev(10, 'delivery', 4, T(2026, 10, 3))
        out = self.month()
        r = self.row(out, 10)
        self.assertIsNone(r['realizationCents'])
        self.assertIsNone(r['rank'])
        self.assertEqual(r['growth']['kind'], 'noData')
        self.assertIn('noSalesData', r['tags'])
        self.assertIsNone(out['summary']['realizationCents'])
        self.assertEqual(out['quality']['noSalesDataClients'], 1)

    # B. Davr oxiridagi qarz kelajakdagi to'lovni olmaydi
    def test_historical_debt_ignores_later_payment(self):
        self.client(10)
        self.ev(10, 'delivery', 10, T(2026, 9, 10))
        self.ev(10, 'payment', ts=T(2026, 10, 8), value=100)   # 1 $
        sep = analytics.insights(self.db, 'custom', '2026-09-01', '2026-09-30', now=NOW)
        r = self.row(sep, 10)
        self.assertEqual(r['payment']['debtEndCents'], 100000)
        self.assertEqual(r['payment']['paidCents'], 0)
        self.assertEqual(r['payment']['code'], 'unpaid')
        self.assertEqual(r['debtNowCents'], 99900)              # bugungi qarz alohida maydon
        self.assertTrue(sep['complete'])
        oct_ = self.row(self.month(), 10)
        self.assertEqual(oct_['payment']['debtEndCents'], 99900)
        self.assertEqual(oct_['payment']['paidCents'], 100)

    # C. Kichik to'lov eski qarz yoshini yangilamaydi
    def test_small_payment_does_not_reset_debt_age(self):
        self.client(10)
        self.ev(10, 'delivery', 10, NOW - 40 * DAY)
        self.ev(10, 'payment', ts=NOW - DAY, value=100)
        p = self.row(self.month(), 10)['payment']
        self.assertEqual(p['oldestOpenDays'], 40)
        self.assertEqual(p['lastPaymentDays'], 1)
        self.assertNotIn('overdue', p['code'])

    def test_fifo_age_moves_after_old_load_is_paid(self):
        self.client(10)
        self.ev(10, 'delivery', 1, NOW - 40 * DAY)          # 100 $
        self.ev(10, 'delivery', 1, NOW - 10 * DAY)          # 100 $
        self.ev(10, 'payment', ts=NOW - 2 * DAY, value=10000)
        p = self.row(self.month(), 10)['payment']
        self.assertEqual(p['debtEndCents'], 10000)
        self.assertEqual(p['oldestOpenDays'], 10)

    def test_advance_and_clear_payment_status(self):
        self.client(10)
        self.client(11)
        self.ev(10, 'delivery', 1, T(2026, 10, 2))
        self.ev(10, 'payment', ts=T(2026, 10, 3), value=15000)   # 50 $ avans
        self.ev(11, 'delivery', 1, T(2026, 10, 2))
        self.ev(11, 'payment', ts=T(2026, 10, 3), value=10000)
        out = self.month()
        self.assertEqual(self.row(out, 10)['payment']['code'], 'advance')
        self.assertEqual(self.row(out, 10)['payment']['debtEndCents'], -5000)
        self.assertEqual(self.row(out, 11)['payment']['code'], 'clear')
        self.assertEqual(out['summary']['advanceCents'], 5000)
        self.assertEqual(out['summary']['debtEndCents'], 0)

    # D. map_only va yangi mijoz qamrovda, lekin yomon mijoz sifatida emas
    def test_map_only_and_new_clients_in_coverage(self):
        self.client(10, region='Rishton')
        self.client(11, region='Rishton', map_only=1)
        self.client(12, region='Rishton')
        self.ev(10, 'delivery', 2, T(2026, 8, 1))
        self.ev(10, 'sold', 1, T(2026, 9, 3))
        self.ev(12, 'delivery', 2, T(2026, 10, 4))          # birinchi tovar shu oyda
        self.ev(12, 'sold', 1, T(2026, 10, 6))
        out = self.month()
        prospect = self.row(out, 11)
        self.assertTrue(prospect['prospect'])
        self.assertNotIn('attention', prospect['tags'])
        new = self.row(out, 12)
        self.assertTrue(new['new'])
        self.assertEqual(new['growth']['kind'], 'new')
        self.assertNotIn('growing', new['tags'])
        reg = next(r for r in out['regions'] if r['name'] == 'Rishton')
        self.assertEqual((reg['clients'], reg['prospects'], reg['newClients']), (3, 1, 1))
        self.assertEqual(out['summary']['prospects'], 1)
        self.assertEqual(len([c for c in out['clients'] if not c['prospect']]), out['summary']['ratedClients'])

    # Oldingi davr nol
    def test_previous_zero_means_sales_started(self):
        self.client(10)
        self.ev(10, 'delivery', 5, T(2026, 7, 1))
        self.ev(10, 'sold', 2, T(2026, 10, 3))
        r = self.row(self.month(), 10)
        self.assertEqual(r['growth']['kind'], 'started')
        self.assertEqual(r['growth']['text'], 'Bu davrda savdo boshlandi')
        self.assertIsNone(r['growth']['pct'])
        self.assertFalse(r['new'])
        self.assertIn('growing', r['tags'])

    def test_decline_needs_both_periods_and_flags_attention(self):
        self.client(10)
        self.ev(10, 'delivery', 10, T(2026, 8, 1))
        self.ev(10, 'sold', 4, T(2026, 9, 5))               # o'tgan oyning 1–9 kunlari: 400 $
        self.ev(10, 'sold', 1, T(2026, 10, 5))              # shu oy: 100 $
        self.ev(10, 'sold', 3, T(2026, 9, 20))              # taqqoslash oynasidan tashqarida
        r = self.row(self.month(), 10)
        self.assertEqual(r['prevRealizationCents'], 40000)
        self.assertEqual(r['growth']['pct'], -75.0)
        self.assertIn('attention', r['tags'])

    # E. Bir mijoz rahbar va agent ro'yxatida bir xil
    def test_manager_and_agent_views_agree(self):
        for cid, agent in ((10, 2), (11, 3)):
            self.client(cid, agent=agent)
            self.ev(cid, 'delivery', 10, T(2026, 9, 1), agent=agent)
            self.ev(cid, 'sold', 3 if agent == 2 else 9, T(2026, 10, 4), agent=agent)
        keys = ('realizationCents', 'deliveredCents', 'growth', 'payment', 'tags', 'stockQty')
        full, own = self.row(self.month(), 10), self.row(self.month(agent=2), 10)
        for k in keys:
            self.assertEqual(full[k], own[k], k)

    # Mijoz boshqa agentga o'tkazilganda
    def test_transferred_client_keeps_operation_history_with_old_agent(self):
        self.client(10, agent=2)
        self.ev(10, 'delivery', 5, T(2026, 10, 2), agent=2)
        self.ev(10, 'sold', 2, T(2026, 10, 3), agent=2)
        self.db.execute('UPDATE clients SET agent=3 WHERE id=10')
        self.ev(10, 'sold', 1, T(2026, 10, 7), agent=3)
        old = self.month(agent=2)
        self.assertEqual([c['id'] for c in old['clients']], [])
        self.assertEqual(old['agents'][0]['operations']['realizationCents'], 20000)
        new = self.month(agent=3)
        self.assertEqual(self.row(new, 10)['realizationCents'], 30000)       # portfel: mijozning to'liq tarixi
        self.assertEqual(new['agents'][0]['operations']['realizationCents'], 10000)
        full = {a['agentId']: a for a in self.month()['agents']}
        self.assertEqual(full[2]['operations']['realizationCents'], 20000)
        self.assertEqual(full[2]['clients'], 0)
        self.assertEqual(full[3]['realizationCents'], 30000)

    # Davr chegaralari va Toshkent vaqti
    def test_period_boundaries_use_tashkent_time(self):
        self.client(10)
        self.ev(10, 'delivery', 10, T(2026, 9, 1))
        self.ev(10, 'sold', 1, T(2026, 9, 30, 23, 59))      # sentabr
        self.ev(10, 'sold', 2, T(2026, 10, 1, 0, 30))       # oktabr (UTC bo'yicha hali 30-sentabr)
        self.assertEqual(self.row(self.month(), 10)['realizationCents'], 20000)
        sep = analytics.insights(self.db, 'custom', '2026-09-01', '2026-09-30', now=NOW)
        self.assertEqual(self.row(sep, 10)['realizationCents'], 10000)
        b = analytics.period_bounds('month', now=NOW)
        self.assertEqual(b['start'], T(2026, 10, 1, 0, 0))
        self.assertEqual(b['prevStart'], T(2026, 9, 1, 0, 0))
        self.assertEqual(b['prevEnd'] - b['prevStart'], b['end'] - b['start'])
        self.assertTrue(b['equalCompare'])
        self.assertFalse(b['complete'])
        self.assertIn('kalendar hafta emas', analytics.period_bounds('week', now=NOW)['label'])
        t = analytics.period_bounds('today', now=NOW)
        self.assertEqual((t['start'], t['prevStart'], t['prevEnd']), (T(2026, 10, 9, 0, 0), T(2026, 10, 8, 0, 0), T(2026, 10, 8, 15, 0) + 1))

    def test_sold_without_price_is_flagged(self):
        self.client(10)
        self.db.execute("""INSERT INTO events(actor,agent,client,kind,pack,qty,amount,amount_usd,note,ts,source)
            VALUES(2,2,10,'delivery',1,5,0,0,'',?,9001)""", (T(2026, 9, 1),))
        self.db.execute("""INSERT INTO events(actor,agent,client,kind,pack,qty,amount,amount_usd,note,ts,source)
            VALUES(2,2,10,'sold',1,2,0,0,'',?,9002)""", (T(2026, 10, 2),))
        out = self.month()
        r = self.row(out, 10)
        self.assertEqual(r['realizationCents'], 0)
        self.assertTrue(r['realizationPartial'])
        self.assertEqual(out['quality']['soldWithoutPriceQty'], 2)

    def test_placeholder_shop_name_uses_person(self):
        self.client(10, shop='Йўқ', person='Анвар ака')
        self.client(11, shop='', person='-')
        out = self.month()
        self.assertEqual(self.row(out, 10)['name'], 'Анвар ака')
        self.assertEqual(self.row(out, 11)['name'], 'Mijoz #11')

    # Bugun kimga
    def test_today_plan_independent_of_period_filter(self):
        self.client(10)
        self.ev(10, 'delivery', 5, NOW - 20 * DAY)
        before = analytics.today_plan(self.db, agent=2, now=NOW)
        for period in ('today', 'week', 'month'):
            analytics.insights(self.db, period, agent=2, now=NOW)
        analytics.insights(self.db, 'custom', '2026-01-01', '2026-03-31', agent=2, now=NOW)
        self.assertEqual(analytics.today_plan(self.db, agent=2, now=NOW), before)

    def test_today_plan_priorities_not_driven_by_debt_size(self):
        self.client(10, shop='Katta qarz')
        self.client(11, shop='Kelishilgan')
        self.client(12, shop='Rejada', region='Rishton')
        self.ev(10, 'delivery', 50, NOW - 30 * DAY)                  # 5 000 $ qarz, 30 kun tashrif yo'q
        self.ev(11, 'delivery', 1, NOW - 3 * DAY)
        self.db.execute("UPDATE clients SET payment_due='2026-10-09' WHERE id=11")
        self.ev(12, 'delivery', 3, NOW - 30 * DAY)
        self.db.execute("""INSERT INTO client_visits(client,actor,status,note,followup,ts)
            VALUES(12,2,'waiting','keyin keling','2026-10-12',?)""", (NOW - 20 * DAY,))
        plan = analytics.today_plan(self.db, agent=2, now=NOW)
        order = [i['clientId'] for i in plan['items']]
        self.assertEqual(order[0], 11)
        self.assertEqual(plan['items'][0]['reasons'][0]['code'], 'agreed_payment')
        self.assertIn(10, order)
        self.assertNotIn(12, order)              # kelishilgan kelajak sana — bezovta qilinmaydi
        item10 = next(i for i in plan['items'] if i['clientId'] == 10)
        self.assertEqual({r['code'] for r in item10['reasons']}, {'visit_due', 'stock_check'})
        self.assertTrue(all('since' in r for i in plan['items'] for r in i['reasons']))

    def test_today_plan_sales_drop_and_prospect(self):
        self.client(10)
        self.client(11, map_only=1)
        self.ev(10, 'delivery', 20, NOW - 70 * DAY)
        self.ev(10, 'sold', 10, NOW - 40 * DAY)
        self.ev(10, 'sold', 2, NOW - 2 * DAY)
        self.db.execute('UPDATE clients SET created_ts=? WHERE id=11', (NOW - 30 * DAY,))
        plan = {i['clientId']: i for i in analytics.today_plan(self.db, agent=2, now=NOW)['items']}
        self.assertEqual(plan[10]['reasons'][0]['code'], 'sales_drop')
        self.assertEqual(plan[11]['reasons'][0]['code'], 'prospect')


class PgInsightsTests(InsightsTests):
    """Xuddi shu holatlar PostgreSQL'da (TEST_DATABASE_URL bo'lsa)."""
    URL = os.getenv('TEST_DATABASE_URL')

    @classmethod
    def setUpClass(cls):
        if not cls.URL:
            raise unittest.SkipTest('TEST_DATABASE_URL berilmagan')

    def make_db(self):
        self.schema = 't_' + uuid.uuid4().hex[:12]
        os.environ['DB_SCHEMA'] = self.schema
        return core.connect(self.URL)

    def tearDown(self):
        try:
            self.db.rollback()
            self.db.execute(f'DROP SCHEMA "{self.schema}" CASCADE')
            self.db.commit()
        finally:
            self.db.close()
            os.environ.pop('DB_SCHEMA', None)


if __name__ == '__main__':
    unittest.main()
