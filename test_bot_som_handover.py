"""Telegram bot: agent takes payment in so'm (+ agreed dollars) and hands so'm to the cashier."""
import time
import unittest
from unittest.mock import patch

import bot
import core


class BotSomHandoverTests(unittest.TestCase):
    def setUp(self):
        p = patch.object(bot, 'BOT_MINIAPP_ONLY', set()); p.start(); self.addCleanup(p.stop)
        self.db = core.connect(':memory:')
        self.db.executemany('INSERT INTO users(id,role,name) VALUES(?,?,?)',
                            [(1, 'admin', 'Admin'), (2, 'agent', 'Ali'), (3, 'cashier', 'Kassir')])
        self.db.execute("INSERT INTO clients(id,agent,name,map_only) VALUES(1,2,'Shop',0)")
        core.set_product_price(self.db, 1, 1, core.money('100.00'))
        core.record(self.db, 1, 2, None, 'load', 1, 5, currency='USD')
        core.record(self.db, 2, 2, 1, 'delivery', 1, 2, currency='USD')
        core.set_cashier_rate(self.db, 3, 12500, 9001)
        now = int(time.time())
        self.db.execute('INSERT INTO shifts(agent,start) VALUES(2,?)', (now - 10,))
        core.point(self.db, 2, {'message_id': 5, 'date': now, 'location': {'latitude': 40, 'longitude': 71, 'live_period': 3600}})
        self.db.commit()

    def msg(self, i, txt, uid=2):
        return {'update_id': i, 'message': {'message_id': i, 'date': int(time.time()), 'from': {'id': uid},
                                             'chat': {'id': uid, 'type': 'private'}, 'text': txt}}

    def run_seq(self, seq, start):
        with patch.object(bot, 'send'), patch.object(bot, '_safe_send_many'):
            for i, t in enumerate(seq, start):
                bot.handle(self.db, self.msg(i, t))

    def test_som_payment_then_som_handover(self):
        self.run_seq(['💰 Пул олиш', '1', '💴 Сўм', '1250000', '100', '✅ Тасдиқлаш'], 100)
        self.assertEqual(core.client_debt_usd(self.db, 1), core.money('100.00'))
        self.assertEqual((core.cash_som(self.db, 2), core.cash_usd(self.db, 2)), (1250000, 0))
        ev = self.db.execute("SELECT paid_uzs,fx_rate FROM events WHERE kind='payment'").fetchone()
        self.assertEqual(tuple(ev), (1250000, 12500))
        self.run_seq(['🏦 Кассага топшириш', '💴 Сўм', '1250000', '✅ Тасдиқлаш'], 200)
        h = self.db.execute('SELECT amount,amount_usd,status FROM handovers').fetchone()
        self.assertEqual(tuple(h), (125000000, 10000, 'pending'))
        core.accept(self.db, 3, 1, True)
        self.assertEqual(core.cashier_flows(self.db, 0, 2**62)['in_cash_uzs'], 1250000)

    def test_too_much_som_is_refused(self):
        self.run_seq(['💰 Пул олиш', '1', '💴 Сўм', '600000', '48', '✅ Тасдиқлаш'], 300)
        self.run_seq(['🏦 Кассага топшириш', '💴 Сўм'], 400)
        with patch.object(bot, 'send'), self.assertRaisesRegex(ValueError, '600,000'):
            bot.handle(self.db, self.msg(402, '700000'))
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM handovers').fetchone()[0], 0)


if __name__ == '__main__':
    unittest.main()
