import json
import re
import unittest
from datetime import datetime
from unittest.mock import patch

import bot
import client_ledger as ledger
import core
import reports


class CustomerFinanceCardTests(unittest.TestCase):
    def setUp(self):
        self.db = core.connect(':memory:')
        self.db.executemany('INSERT INTO users(id,role,name) VALUES(?,?,?)', [
            (1, 'admin', 'Admin'), (2, 'agent', 'First agent'),
            (3, 'agent', 'Second agent'),
        ])
        self.db.execute("""INSERT INTO clients(id,agent,name,phone,address,lat,lon,shop_name,map_only,created_ts)
             VALUES(1,2,'Customer','+998900000001','Address',40.5,71.2,'Test shop',0,1000)""")
        self.at = int(datetime(2026, 9, 23, 16, 15, tzinfo=ledger.TZ).timestamp())
        self.db.executemany("""INSERT INTO events(actor,agent,client,kind,pack,qty,amount,amount_usd,ts,source)
          VALUES(?,?,1,?,?,?,?,?,?,?)""", [
            (2,2,'delivery',1,10,0,2000,self.at-180,1001),
            (3,3,'payment',0,0,0,1700,self.at,1002),
            (2,2,'sold',1,4,0,800,self.at-100,1003),
            (3,3,'return',1,1,0,200,self.at+100,1004),
        ])

    def tearDown(self):
        self.db.close()

    def test_payment_and_deliveries_have_dates_and_actual_agent_across_owners(self):
        text = ledger.recent_text(self.db, 1, 20)
        self.assertIn('23.09.2026 16:15 · Second agent', text)
        self.assertIn('Пул олинди: 17.00 USD', text)
        self.assertIn('Берилди: Грунтовка 7/1 — 1 кг · 10 дона · 20.00 USD', text)
        self.assertIn('Сотилгани қайд этилди', text)
        summary = ledger.summary(self.db, 1)
        self.assertIn('Жами олинган пул: 17.00 USD', summary)
        self.assertIn('Жами берилган товар: 10 дона · 20.00 USD', summary)
        self.assertNotIn('28.00 USD', summary)

    def test_other_agent_sees_cash_and_goods_in_telegram_card_and_full_history(self):
        with patch.object(bot, 'send') as send:
            bot.show_client_card(self.db, 3, 1)
        msg = send.call_args.args[1]
        self.assertIn('Пул олинди: 17.00 USD', msg)
        self.assertIn('23.09.2026 16:15', msg)
        self.assertIn('Берилди:', msg)
        self.assertIn('📜 Барча товар ва пул тарихи', str(send.call_args.args[2]))
        with patch.object(bot, 'send') as send:
            bot.handle(self.db, {'update_id':1100, 'message': {
                'message_id':1100, 'date':self.at, 'from':{'id':3},
                'chat':{'id':3,'type':'private'}, 'text':'📜 Барча товар ва пул тарихи'}})
        self.assertIn('17.00 USD', send.call_args.args[1])
        self.assertIn('10 дона', send.call_args.args[1])

    def test_web_card_and_both_maps_include_dated_finance_history_without_html_injection(self):
        self.db.execute("UPDATE users SET name='<script>alert(1)</script>' WHERE id=3")
        card = reports.client_card_html(self.db, 1, 1).decode()
        self.assertIn('23.09.2026 16:15', card)
        self.assertIn('Пул олинди: 17.00 USD', card)
        self.assertIn('Берилди: Грунтовка 7/1 — 1 кг', card)
        self.assertNotIn('<script>alert(1)</script>', card)
        self.assertIn('&lt;script&gt;alert(1)&lt;/script&gt;', card)
        for render in (lambda: reports.agent_clients_map_html(self.db, 3),
                       lambda: reports.admin_clients_map_html(self.db, 1)):
            page = render().decode()
            match = re.search(r'<script id="data" type="application/json">(.*?)</script>', page, re.S)
            data = json.loads(match.group(1))
            item = data['shops'][0]
            self.assertIn('17.00 USD', item['finance'])
            self.assertIn('23.09.2026 16:15', item['finance'])
            self.assertNotIn('+998900000001', page)
            self.assertIn('Товар ва пул тарихи', page)

    def test_empty_history_and_legacy_uzs_not_mixed_into_usd(self):
        self.db.execute('DELETE FROM events')
        self.assertIn('Ҳали товар бериш', ledger.recent_text(self.db, 1))
        self.db.execute("""INSERT INTO events(actor,agent,client,kind,amount,amount_usd,ts,source)
           VALUES(2,2,1,'payment',12345,0,?,2001)""", (self.at,))
        text = ledger.summary(self.db, 1)
        self.assertIn('0.00 USD', text)
        self.assertIn('123.45 сўм', text)
        self.assertIn('123.45 сўм', ledger.recent_text(self.db, 1))


if __name__ == '__main__':
    unittest.main()
