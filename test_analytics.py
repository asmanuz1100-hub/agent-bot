"""Sodda hisobotning biznes qoidalari: qarz/avans, davrlar, mijoz KPI, mahsulotlar, "Bugun kimga".
Kutilgan qiymatlar qo'lda hisoblangan. TEST_DATABASE_URL berilsa PgInsightsTests PostgreSQL'da yuradi.
"""
import os
import unittest
import uuid
from datetime import datetime
from fractions import Fraction
from zoneinfo import ZoneInfo

import analytics
import core

TZ = ZoneInfo('Asia/Tashkent')
DAY = 86400


def T(y, m, d, h=12, mi=0):
    return int(datetime(y, m, d, h, mi, tzinfo=TZ).timestamp())


NOW = T(2026, 10, 9, 15, 0)          # 09.10.2026 15:00 Toshkent
PRICE = 10000                        # 1 dona = 100.00 $


class GrowthRulesTests(unittest.TestCase):
    def test_growth_points_boundaries_do_not_overlap(self):
        prev = 10000
        cases = [(12000, 15), (11999, 12), (10500, 12), (10499, 8), (10000, 8), (9500, 8),
                 (9499, 4), (8000, 4), (7999, 0), (0, 0)]
        for cur, pts in cases:
            self.assertEqual(analytics.growth_points(cur, prev), pts, cur)
        self.assertIsNone(analytics.growth_points(500, 0))

    def test_activity_and_groups(self):
        self.assertEqual(analytics.activity_points(True, True), 30)
        self.assertEqual(analytics.activity_points(True, False), 20)
        self.assertEqual(analytics.activity_points(False, True), 10)
        self.assertEqual(analytics.activity_points(False, False), 0)
        self.assertEqual(analytics.kpi_group(Fraction(70))[0], 'active')
        self.assertEqual(analytics.kpi_group(Fraction(6999, 100))[0], 'low')
        self.assertEqual(analytics.kpi_group(Fraction(40))[0], 'low')
        self.assertEqual(analytics.kpi_group(Fraction(3999, 100))[0], 'passive')

    def test_growth_texts_keep_zero_and_unknown_apart(self):
        self.assertEqual(analytics.growth(500, 0)['kind'], 'started')
        self.assertEqual(analytics.growth(0, 0)['kind'], 'zero')
        self.assertEqual(analytics.growth(0, 0, known=False)['kind'], 'unknown')
        self.assertEqual(analytics.growth(12500, 10000)['pct'], 25.0)


class PeriodTests(unittest.TestCase):
    def check(self, now, trimmed, cmp_days):
        b = analytics.period_bounds('month', now=now)
        self.assertEqual(b['cmpEnd'] - b['cmpStart'], b['prevEnd'] - b['prevStart'])
        self.assertLessEqual(b['prevEnd'], b['start'])
        self.assertEqual(b['trimmed'], trimmed)
        if cmp_days is not None:
            self.assertEqual(b['cmpEnd'] - b['cmpStart'], cmp_days * DAY)
        return b

    def test_month_lengths_28_29_30_31(self):
        self.check(T(2027, 3, 31, 12), True, 28)    # fevral 28 kun
        self.check(T(2028, 3, 31, 12), True, 29)    # kabisa fevral
        self.check(T(2026, 5, 31, 12), True, 30)    # aprel 30 kun
        self.check(T(2026, 8, 31, 12), False, None)  # iyul 31 kun — qisqartirish shart emas
        b = self.check(T(2026, 10, 10, 9, 30), False, None)
        self.assertEqual(b['prevStart'], T(2026, 9, 1, 0, 0))
        self.assertEqual(b['prevEnd'], T(2026, 9, 10, 9, 30) + 1)   # 1–10 sentabr shu vaqtgacha

    def test_tashkent_day_start_and_week(self):
        b = analytics.period_bounds('today', now=NOW)
        self.assertEqual(b['start'], T(2026, 10, 9, 0, 0))
        self.assertEqual(b['prevStart'], T(2026, 10, 8, 0, 0))
        w = analytics.period_bounds('week', now=NOW)
        self.assertEqual(w['start'], T(2026, 10, 3, 0, 0))
        self.assertIn('Oxirgi 7 kun', w['label'])


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

    def client(self, cid, agent=2, shop='Do‘kon', region='Qo‘qon', map_only=0, created=None):
        self.db.execute("""INSERT INTO clients(id,agent,name,shop_name,region,phone,created_ts,map_only)
            VALUES(?,?,?,?,?,?,?,?)""", (cid, agent, 'Ism', shop, region, f'+99890{cid:07d}',
                                         created or T(2026, 1, 1), map_only))

    def ev(self, client, kind, qty=0, ts=None, value=0, agent=2):
        self.src += 1
        core.record(self.db, agent, agent, client, kind, 1, qty, value, '', self.src, currency='USD', ts=ts)

    def month(self, agent=None, now=NOW):
        return analytics.insights(self.db, 'month', agent=agent, now=now)

    def row(self, out, cid):
        return next(c for c in out['clients'] if c['id'] == cid)

    def test_debt_is_delivered_minus_returned_minus_paid(self):
        self.client(10)
        self.ev(10, 'delivery', 10, T(2026, 10, 2))         # 1000 $
        self.ev(10, 'return', 2, T(2026, 10, 4))            # 200 $
        self.ev(10, 'payment', ts=T(2026, 10, 5), value=30000)
        self.ev(10, 'sold', 3, T(2026, 10, 6))              # "Sotildi" hisobotga ta'sir qilmaydi
        r = self.row(self.month(), 10)
        self.assertEqual((r['deliveredCents'], r['returnedCents'], r['paidCents']), (100000, 20000, 30000))
        self.assertEqual(r['debtCents'], 50000)
        self.assertNotIn('realizationCents', r)

    def test_advance_does_not_reduce_other_clients_debt(self):
        self.client(10, region='Rishton')
        self.client(11, region='Rishton')
        self.ev(10, 'delivery', 5, T(2026, 10, 2))          # qarz 500 $
        self.ev(11, 'delivery', 1, T(2026, 10, 2))
        self.ev(11, 'payment', ts=T(2026, 10, 3), value=30000)   # avans 200 $
        out = self.month()
        self.assertEqual((out['summary']['debtCents'], out['summary']['advanceCents']), (50000, 20000))
        reg = next(r for r in out['regions'] if r['name'] == 'Rishton')
        self.assertEqual((reg['debtCents'], reg['advanceCents']), (50000, 20000))
        ag = out['agents'][0]
        self.assertEqual((ag['debtCents'], ag['advanceCents']), (50000, 20000))

    def test_later_payment_not_in_historical_report(self):
        self.client(10)
        self.ev(10, 'delivery', 10, T(2026, 9, 10))
        self.ev(10, 'payment', ts=T(2026, 10, 8), value=100)
        sep = analytics.insights(self.db, 'custom', '2026-09-01', '2026-09-30', now=NOW)
        r = self.row(sep, 10)
        self.assertEqual((r['debtCents'], r['paidCents'], r['debtNowCents']), (100000, 0, 99900))
        self.assertEqual(self.row(self.month(), 10)['debtCents'], 99900)

    def kpi_scenario(self):
        # Oldingi oyna: 01–09.09 15:00; joriy: 01–09.10 15:00.
        self.client(10, shop='Sobir')
        self.ev(10, 'delivery', 10, T(2026, 8, 1))           # boshlang'ich: 1000 $
        self.ev(10, 'delivery', 4, T(2026, 9, 3))            # oldingi: 400 $ tovar
        self.ev(10, 'payment', ts=T(2026, 9, 4), value=50000)   # oldingi: 500 $ to'lov
        self.ev(10, 'delivery', 5, T(2026, 10, 3))           # joriy: 500 $ (+25%)
        self.ev(10, 'payment', ts=T(2026, 10, 4), value=57500)  # joriy: 575 $ (+15%)

    def test_kpi_parts_score_and_group(self):
        self.kpi_scenario()
        k = self.row(self.month(), 10)['kpi']
        # A=30 (ikkala oynada olgan); B=40*1075/1900=22.63; C=15 (+25%) + 12 (+15%) = 27 → 79.63
        self.assertEqual(k['status'], 'rated')
        self.assertEqual(k['parts'], {'activity': 30, 'payment': 22.6, 'deliveryGrowth': 15, 'paymentGrowth': 12})
        self.assertEqual(k['score'], 80)
        self.assertEqual(k['group'], 'active')

    def test_rating_order_and_same_score_for_manager_and_agent(self):
        self.kpi_scenario()
        self.client(11, agent=3, shop='Kam')
        self.ev(11, 'delivery', 10, T(2026, 8, 1), agent=3)
        self.ev(11, 'delivery', 5, T(2026, 9, 3), agent=3)
        self.ev(11, 'payment', ts=T(2026, 9, 4), value=10000, agent=3)
        self.ev(11, 'delivery', 1, T(2026, 10, 3), agent=3)       # −80% → 0
        self.ev(11, 'payment', ts=T(2026, 10, 4), value=5000, agent=3)  # −50% → 0
        full = self.month()
        rated = [c['id'] for c in full['clients'] if c['kpi']['status'] == 'rated']
        self.assertEqual(rated, [10, 11])
        k11 = self.row(full, 11)['kpi']
        # A=30; B=40*150/1600=3.75; C=0 → 33.75 → passiv
        self.assertEqual((k11['score'], k11['group']), (34, 'passive'))
        self.assertEqual(self.row(self.month(agent=3), 11)['kpi'], k11)
        self.assertEqual(self.row(self.month(agent=2), 10)['kpi'], self.row(full, 10)['kpi'])

    def test_previous_zero_gives_provisional_score_without_growth(self):
        self.client(10)
        self.ev(10, 'delivery', 10, T(2026, 7, 1))
        self.ev(10, 'delivery', 2, T(2026, 10, 3))
        self.ev(10, 'payment', ts=T(2026, 10, 4), value=10000)
        r = self.row(self.month(), 10)
        k = r['kpi']
        # Faollik 30 + to'lov 40*100/1200=3.33 → 33.33 / 70 * 100 = 47.6 → 48, Faolligi past
        self.assertEqual((k['status'], k['provisional'], k['score'], k['group']), ('rated', True, 48, 'low'))
        self.assertIsNone(k['parts']['deliveryGrowth'])
        self.assertEqual(r['rank'], 1)
        self.assertEqual(r['deliveryGrowth']['text'], 'Bu davrda tovar oldi')
        self.assertEqual(r['paymentGrowth']['text'], 'Bu davrda to‘lov qildi')

    def test_unknown_comparison_when_client_did_not_exist(self):
        self.client(10, created=T(2026, 9, 20))
        self.ev(10, 'delivery', 2, T(2026, 9, 20))
        r = self.row(self.month(), 10)
        self.assertEqual(r['deliveryGrowth']['kind'], 'unknown')

    def test_new_and_prospect_clients_are_separate(self):
        self.client(10)
        self.client(11, map_only=1)
        self.client(12)
        self.ev(10, 'delivery', 2, NOW - 10 * DAY)   # 15 kundan yangi → "Yangi"
        self.ev(12, 'delivery', 10, T(2026, 7, 1))
        self.db.execute("UPDATE clients SET region='' WHERE id=12")
        out = self.month()
        self.assertEqual(self.row(out, 10)['kpi']['status'], 'new')
        self.assertEqual(self.row(out, 11)['kpi']['status'], 'prospect')
        self.assertNotIn('rank', self.row(out, 10))
        self.assertEqual(out['summary']['clients'], 3)
        self.assertEqual(out['summary']['prospects'], 1)
        self.assertIn('Belgilanmagan', [r['name'] for r in out['regions']])

    def test_new_client_threshold_is_15_days(self):
        self.client(10)
        self.client(11)
        self.ev(10, 'delivery', 2, NOW - 14 * DAY)
        self.ev(11, 'delivery', 2, NOW - 16 * DAY)
        out = self.month()
        self.assertEqual(analytics.KPI['new_days'], 15)
        self.assertEqual(self.row(out, 10)['kpi']['status'], 'new')
        self.assertEqual(self.row(out, 11)['kpi']['status'], 'rated')

    def test_no_base_when_everything_returned(self):
        self.client(10)
        self.ev(10, 'delivery', 2, T(2026, 7, 1))
        self.ev(10, 'return', 2, T(2026, 7, 5))
        self.assertEqual(self.row(self.month(), 10)['kpi']['status'], 'nobase')

    def test_products_have_no_payment_allocation(self):
        self.client(10)
        self.ev(10, 'delivery', 4, T(2026, 9, 3))
        self.ev(10, 'delivery', 5, T(2026, 10, 3))
        self.ev(10, 'return', 1, T(2026, 10, 5))
        self.ev(10, 'payment', ts=T(2026, 10, 6), value=20000)
        out = self.month()
        p = out['products'][0]
        self.assertEqual((p['deliveredQty'], p['deliveredCents'], p['returnedQty'], p['returnedCents']), (5, 50000, 1, 10000))
        self.assertEqual(p['qtyGrowth']['pct'], 25.0)
        self.assertEqual(p['amountGrowth']['pct'], 25.0)
        self.assertFalse(any('paid' in k.lower() or 'debt' in k.lower() for k in p))
        self.assertEqual(sum(x['deliveredCents'] for x in out['products']), out['summary']['deliveredCents'])

    def test_transferred_client_operations_stay_with_old_agent(self):
        self.client(10, agent=2)
        self.ev(10, 'delivery', 5, T(2026, 10, 2), agent=2)
        self.db.execute('UPDATE clients SET agent=3 WHERE id=10')
        self.ev(10, 'payment', ts=T(2026, 10, 7), value=10000, agent=3)
        full = {a['agentId']: a for a in self.month()['agents']}
        self.assertEqual(full[2]['operations']['deliveredCents'], 50000)
        self.assertEqual(full[2]['clients'], 0)
        self.assertEqual(full[3]['debtCents'], 40000)
        self.assertEqual([c['id'] for c in self.month(agent=2)['clients']], [])

    def test_legacy_uzs_records_are_counted_not_converted(self):
        self.client(10)
        self.ev(10, 'delivery', 2, T(2026, 10, 2))
        self.db.execute("""INSERT INTO events(actor,agent,client,kind,pack,qty,amount,amount_usd,note,ts,source)
            VALUES(2,2,10,'payment',0,0,1200000,0,'',?,9001)""", (T(2026, 10, 3),))
        out = self.month()
        self.assertEqual(self.row(out, 10)['paidCents'], 0)
        self.assertEqual(out['summary']['legacyEvents'], 1)

    # Bugun kimga
    def test_payment_does_not_update_visit_date(self):
        self.client(10)
        self.ev(10, 'delivery', 5, NOW - 10 * DAY)
        self.ev(10, 'payment', ts=NOW - DAY, value=1000)
        item = analytics.today_plan(self.db, agent=2, now=NOW)['items'][0]
        self.assertEqual(item['lastVisitTs'], NOW - 10 * DAY)
        self.assertEqual(item['lastPaymentTs'], NOW - DAY)
        self.assertEqual(item['reasons'][0]['text'], '10 kundan beri tashrif yo‘q')

    def test_today_plan_independent_and_prioritised(self):
        self.client(10, shop='Katta qarz')
        self.client(11, shop='Kelishilgan')
        self.client(12, shop='Rejada')
        self.ev(10, 'delivery', 50, NOW - 30 * DAY)
        self.ev(11, 'delivery', 1, NOW - 3 * DAY)
        self.db.execute("UPDATE clients SET payment_due='2026-10-09' WHERE id=11")
        self.ev(12, 'delivery', 3, NOW - 30 * DAY)
        self.db.execute("""INSERT INTO client_visits(client,actor,status,note,followup,ts)
            VALUES(12,2,'waiting','keyin','2026-10-12',?)""", (NOW - 20 * DAY,))
        before = analytics.today_plan(self.db, agent=2, now=NOW)
        for period in ('today', 'week', 'month'):
            analytics.insights(self.db, period, agent=2, now=NOW)
        self.assertEqual(analytics.today_plan(self.db, agent=2, now=NOW), before)
        order = [i['clientId'] for i in before['items']]
        self.assertEqual(order[0], 11)
        self.assertIn(10, order)
        self.assertNotIn(12, order)


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
