import os
import unittest
import uuid

import core
import cashier_api


class CashierConversionTests(unittest.TestCase):
    def make_db(self):
        return core.connect(':memory:')

    def setUp(self):
        self.db=self.make_db()
        self.db.executemany("INSERT INTO users(id,role,name) VALUES(?,?,?)",
                           [(1,'admin','Test admin'),(2,'agent','Test agent'),(3,'cashier','Test cashier')])
        self.db.execute("INSERT INTO clients(id,agent,name) VALUES(1,2,'Test client')")
        self.db.execute("INSERT INTO meta(key,value) VALUES('cashier_pockets_since','0')")
        self.db.execute("""INSERT INTO handovers(agent,amount,amount_usd,status,cashier,source,ts,accepted_ts)
            VALUES(2,0,10000,'accepted',3,1,1,1)""")
        core.set_cashier_rate(self.db,3,12500,2)

    def tearDown(self):
        self.db.close()

    def convert(self, currency='USD', amount='100', source='cash', request='conversion-001'):
        payload=dict(action='convert',requestId=request,fromCurrency=currency,
                     amount=amount,rate='12500',payFrom=source,note='E2E TEST')
        return cashier_api.mutate(self.db,3,'convert',payload)

    def test_usd_to_uzs_and_back_preserves_cashbox_and_client_debt(self):
        before=core.client_debt_usd(self.db,1)
        self.convert()
        w=core.cashier_flows(self.db)
        self.assertEqual((w['cash_usd'],w['cash_uzs']),(0,1250000))
        self.assertEqual(core.cashier_balance_usd(self.db),10000)
        self.convert('UZS','1250000',request='conversion-002')
        w=core.cashier_flows(self.db)
        self.assertEqual((w['cash_usd'],w['cash_uzs']),(10000,0))
        self.assertEqual(core.client_debt_usd(self.db,1),before)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM cashier_expenses').fetchone()[0],0)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM events').fetchone()[0],0)

    def test_card_conversion_does_not_touch_cash(self):
        self.db.execute("""INSERT INTO cashier_incomes(cashier,amount_usd,category,source_name,source,ts)
            VALUES(3,5000,'Test','Test',3,1)""")
        self.convert(amount='50',source='card')
        w=core.cashier_flows(self.db)
        self.assertEqual((w['cash_usd'],w['cash_uzs'],w['card_usd'],w['card_uzs']),
                         (10000,0,0,625000))

    def test_selected_currency_and_source_must_have_enough_money(self):
        for currency,amount,source in [('USD','100.01','cash'),('USD','1','card'),('UZS','1250','cash')]:
            with self.assertRaisesRegex(ValueError,'етарли'):
                self.convert(currency,amount,source)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM cashier_conversions').fetchone()[0],0)

    def test_same_request_is_written_once(self):
        self.convert(amount='10')
        self.assertTrue(self.convert(amount='10')['duplicate'])
        with self.assertRaises(ValueError):
            self.convert(amount='20')
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM cashier_conversions').fetchone()[0],1)
        w=core.cashier_flows(self.db)
        self.assertEqual((w['cash_usd'],w['cash_uzs']),(9000,125000))

    def test_permissions_quote_rounding_and_invalid_inputs(self):
        self.assertEqual(core.cashier_conversion_quote('USD','0.01','12550'),(1,126,12550))
        self.assertEqual(core.cashier_conversion_quote('UZS','125','12500'),(125,1,12500))
        for currency,amount,rate in [('EUR','10','12500'),('USD','0','12500'),
                                      ('USD','1','0'),('UZS','1.5','12500')]:
            with self.assertRaises(ValueError):
                core.cashier_conversion_quote(currency,amount,rate)
        with self.assertRaises(ValueError):
            core.add_cashier_conversion(self.db,2,'cash','USD','10','12500','',100)
        self.assertEqual(core.cashier_rate(self.db),12500)

    def test_history_and_period_report_include_conversion(self):
        self.convert(amount='10')
        d=cashier_api.dashboard(self.db,3)
        self.assertEqual(len(d['conversions']),1)
        self.assertEqual(d['summary']['wallets']['cashUsd'],9000)
        self.assertEqual(d['summary']['wallets']['cashUzs'],125000)
        report=cashier_api.period_report(self.db,3,{'period':'today'})
        row=next(r for r in report['rows'] if r['kind']=='conversion')
        self.assertEqual((row['amountFrom'],row['amountTo'],row['rate']),(1000,125000,12500))
        self.assertEqual(report['flows']['out_expense_usd'],0)
        self.assertEqual(report['flows']['in_cash_usd'],0)

    def test_conversion_does_not_change_previous_period(self):
        self.convert()
        w=core.cashier_flows(self.db,0,2)
        self.assertEqual((w['cash_usd'],w['cash_uzs']),(10000,0))

    def test_legacy_opening_cash_is_convertible(self):
        self.db.execute("UPDATE meta SET value='2' WHERE key='cashier_pockets_since'")
        self.convert()
        w=core.cashier_flows(self.db)
        self.assertEqual(w['cash_usd']+w['opening_usd'],0)
        self.assertEqual(w['cash_uzs'],1250000)


class PgCashierConversionTests(CashierConversionTests):
    @classmethod
    def setUpClass(cls):
        cls.url=os.getenv('TEST_DATABASE_URL')
        if not cls.url:
            raise unittest.SkipTest('TEST_DATABASE_URL not configured')

    def make_db(self):
        self.schema='fx_'+uuid.uuid4().hex[:12]
        os.environ['DB_SCHEMA']=self.schema
        return core.connect(self.url)

    def test_parallel_cashiers_cannot_convert_the_same_money_twice(self):
        from concurrent.futures import ThreadPoolExecutor
        self.db.commit()
        def worker(actor):
            db=core.connect(self.url,initialize=False)
            try:
                cashier_api.mutate(db,actor,'convert',dict(action='convert',
                    requestId=f'parallel-conversion-{actor}',fromCurrency='USD',
                    amount='70',rate='12500',payFrom='cash'))
                db.commit()
                return 'ok'
            except ValueError:
                db.rollback()
                return 'insufficient'
            finally:
                db.close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(worker,(1,3)))
        self.assertCountEqual(results,['ok','insufficient'])
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM cashier_conversions').fetchone()[0],1)
        self.assertEqual(core.cashier_flows(self.db)['cash_usd'],3000)

    def tearDown(self):
        try:
            self.db.rollback()
            self.db.execute(f'DROP SCHEMA "{self.schema}" CASCADE')
            self.db.commit()
        finally:
            self.db.close()
            os.environ.pop('DB_SCHEMA',None)


if __name__=='__main__':
    unittest.main()
