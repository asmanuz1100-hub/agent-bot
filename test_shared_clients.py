import json
import re
import unittest
from unittest.mock import patch

import bot
import core
import customer_status as cs
import reports


class SharedClientsTests(unittest.TestCase):
    def setUp(self):
        self.db=core.connect(':memory:')
        self.db.executemany('INSERT INTO users(id,role,name) VALUES(?,?,?)',[
            (1,'admin','Admin'),(2,'agent','Old Agent'),(3,'agent','New Agent')])
        self.db.execute("""INSERT INTO clients(
            id,agent,name,phone,address,lat,lon,photo,shop_name,comment,payment_due,created_ts,map_only
        ) VALUES(1,2,'Client','+998900001111','Old address',40.5,71.2,'','Old Shop','First contact','Аниқ эмас',1000,0)""")
        core.set_product_price(self.db,1,1,core.money('2.00'))
        core.record(self.db,1,2,None,'load',1,10,source=1,currency='USD')
        core.record(self.db,2,2,1,'delivery',1,4,source=2,currency='USD')
        core.record(self.db,1,3,None,'load',1,5,source=3,currency='USD')

    def tearDown(self):
        self.db.close()

    @staticmethod
    def map_data(html):
        match=re.search(r'<script id="data" type="application/json">(.*?)</script>',html.decode(),re.S)
        return json.loads(match.group(1))

    def test_new_agent_sees_old_clients_in_lists_card_and_map(self):
        with patch.object(bot,'send') as send:
            bot.report_clients(self.db,3)
            self.assertIn('1 ·',str(send.call_args.args[2]))
        with patch.object(bot,'send') as send:
            bot.show_client_card(self.db,3,1)
            self.assertIn('Old Shop',send.call_args.args[1])
            self.assertIn('Мижозни қўшган агент: Old Agent',send.call_args.args[1])
            self.assertIn('✏️ Мижоз маълумотини ўзгартириш',str(send.call_args.args[2]))
        with patch.object(bot,'send') as send:
            bot.show_client_edit_fields(self.db,3,1)
            self.assertIn('🏠 Манзил',str(send.call_args.args[2]))
            self.assertNotIn(bot.DELIVERY_EDIT_LABEL,str(send.call_args.args[2]))
        data=self.map_data(reports.agent_clients_map_html(
            self.db,3,action_url=lambda verb,cid:f'{verb}-{cid}'))
        shop=next(x for x in data['shops'] if x['id']==1)
        self.assertEqual(shop['owner'],'Old Agent')
        self.assertEqual(shop['stock'],4)
        self.assertEqual(shop['delivery_url'],'delivery-1')
        self.assertEqual(shop['pay_url'],'pay-1')
        self.assertEqual(shop['return_url'],'return-1')
        self.assertEqual(shop['visit_url'],'visit-1')

    def test_new_agent_can_edit_visit_collect_return_and_deliver(self):
        core.edit_client(self.db,3,1,{'address':'Updated by new agent'})
        self.assertEqual(self.db.execute('SELECT address FROM clients WHERE id=1').fetchone()[0],
                         'Updated by new agent')
        cs.add_visit(self.db,3,1,'interested','New agent follow-up')
        last=cs.history(self.db,1,1)[0]
        self.assertEqual(last['actor'],3)

        self.assertEqual(core.client_debt_usd(self.db,1),core.money('8.00'))
        core.record(self.db,3,3,1,'payment',value=core.money('1.00'),source=4,currency='USD')
        self.assertEqual(core.cash_usd(self.db,3),core.money('1.00'))

        core.record(self.db,3,3,1,'return',1,1,source=5,currency='USD')
        self.assertEqual(core.agent_stock(self.db,3,1),6)
        self.assertEqual(core.client_stock_total(self.db,1,1),3)

        core.record(self.db,3,3,1,'delivery',1,2,source=6,currency='USD')
        self.assertEqual(core.agent_stock(self.db,3,1),4)
        self.assertEqual(core.client_stock_total(self.db,1,1),5)
        self.assertEqual(core.client_debt_usd(self.db,1),core.money('9.00'))

        actors=[tuple(x) for x in self.db.execute(
            "SELECT actor,agent,kind FROM events WHERE client=1 AND kind IN ('payment','return','delivery') ORDER BY id"
        ).fetchall()]
        self.assertIn((3,3,'payment'),actors)
        self.assertIn((3,3,'return'),actors)
        self.assertIn((3,3,'delivery'),actors)

    def test_old_agent_prospect_is_visible_to_new_agent_but_finance_waits_for_delivery(self):
        self.db.execute("""INSERT INTO clients(
            id,agent,name,phone,address,lat,lon,photo,shop_name,comment,payment_due,created_ts,map_only
        ) VALUES(2,2,'Prospect','+998900002222','Prospect address',40.6,71.3,'','Prospect Shop','Later','Аниқ эмас',1000,1)""")
        cs.add_visit(self.db,2,2,'waiting','Next month','2099-01-01')
        data=self.map_data(reports.agent_clients_map_html(
            self.db,3,action_url=lambda verb,cid:f'{verb}-{cid}'))
        shop=next(x for x in data['shops'] if x['id']==2)
        self.assertTrue(shop['prospect'])
        self.assertEqual(shop['delivery_url'],'delivery-2')
        self.assertEqual(shop['visit_url'],'visit-2')
        self.assertNotIn('pay_url',shop)
        self.assertNotIn('return_url',shop)


if __name__=='__main__':
    unittest.main()
