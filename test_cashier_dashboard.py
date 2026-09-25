import time
import unittest
from unittest.mock import patch

import bot
import core


class CashierDashboardTests(unittest.TestCase):
    def setUp(self):
        self.db=core.connect(':memory:')
        self.db.executemany('INSERT INTO users(id,role,name) VALUES(?,?,?)',[
            (1,'admin','Admin'),(2,'agent','Ali Agent'),(3,'cashier','Malika Kassir'),(4,'cashier','Ikkinchi Kassir')])
        self.db.execute("""INSERT INTO clients(agent,name,phone,address,lat,lon,photo,shop_name,comment,payment_due,created_ts,map_only)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,0)""",(2,'Vali','+998901112233','Kokand',40.5,71.2,'','Baraka dokon','','',int(time.time())))

    def tearDown(self):
        self.db.close()

    def message(self,uid,text,number=9000):
        return {'update_id':number,'message':{'message_id':number,'date':int(time.time()),
            'from':{'id':uid},'chat':{'id':uid,'type':'private'},'text':text}}

    def test_admin_and_cashier_can_open_cashbox_with_customer_payment_detail(self):
        self.assertTrue(bot.allowed(self.db,1,'cashbox'))
        self.assertTrue(bot.allowed(self.db,3,'cashbox'))
        core.record(self.db,2,2,1,'payment',value=core.money('12.50'),source=70001,currency='USD')
        core.handover(self.db,2,core.money('10.00'),70002,currency='USD')
        with patch.object(bot,'send') as send:
            bot.cashbox_report(self.db,1)
            text=send.call_args.args[1]
            self.assertIn('КАССА НАЗОРАТИ',text)
            self.assertIn('12.50 USD',text)
            self.assertIn('10.00 USD',text)
            self.assertIn('Ali Agent',text)
            self.assertIn('Baraka dokon',text)
            self.assertNotIn('/accept 1',text)
        with patch.object(bot,'send') as send:
            bot.cashbox_report(self.db,3)
            self.assertIn('/review 1',send.call_args.args[1])

    def test_payment_finish_notifies_every_cashier_with_agent_and_customer(self):
        state={'action':'payment','values':{'client':1,'amount':'5.00'}}
        with patch.object(bot,'live_ready',return_value=(True,'')),patch.object(bot,'send') as send:
            bot.finish(self.db,2,state,71001)
        calls=[(c.args[0],c.args[1]) for c in send.call_args_list]
        cashier=[text for uid,text in calls if uid in (3,4)]
        self.assertEqual(len(cashier),2)
        self.assertTrue(all('Ali Agent' in text for text in cashier))
        self.assertTrue(all('Baraka dokon' in text for text in cashier))
        self.assertTrue(all('5.00 USD' in text for text in cashier))
        self.assertEqual(core.cash_usd(self.db,2),core.money('5.00'))

    def test_handover_notification_and_cashier_accept_notifies_agent_and_admin(self):
        core.record(self.db,2,2,1,'payment',value=core.money('20.00'),source=72001,currency='USD')
        state={'action':'handover','values':{'amount':'15.00'}}
        with patch.object(bot,'send') as send:
            bot.finish(self.db,2,state,72002)
        calls=[(call.args[0],call.args[1]) for call in send.call_args_list]
        self.assertTrue(any(uid==3 and 'КАССАГА ПУЛ ТОПШИРИШ' in text and '15.00 USD' in text for uid,text in calls))
        self.assertTrue(any(uid==4 and 'КАССАГА ПУЛ ТОПШИРИШ' in text for uid,text in calls))
        cashier_calls=[call for call in send.call_args_list if call.args[0] in (3,4)
                       and 'КАССАГА ПУЛ ТОПШИРИШ' in call.args[1]]
        self.assertTrue(cashier_calls)
        self.assertTrue(all(any('🔎 Кўриб чиқиш #' in button for row in call.args[2] for button in row)
                            for call in cashier_calls))
        hid=self.db.execute("SELECT id FROM handovers WHERE status='pending'").fetchone()[0]
        with patch.object(bot,'send') as send,patch.object(bot,'ADMINS',{1}):
            bot.handle(self.db,self.message(3,f'/review {hid}',72003))
            bot.handle(self.db,self.message(3,f'/accept {hid}',72004))
        row=self.db.execute('SELECT status,cashier,accepted_ts FROM handovers WHERE id=?',(hid,)).fetchone()
        self.assertEqual(row['status'],'accepted')
        self.assertEqual(row['cashier'],3)
        self.assertIsNotNone(row['accepted_ts'])
        calls=[(c.args[0],c.args[1]) for c in send.call_args_list]
        self.assertTrue(any(uid==2 and 'ҚАБУЛ ҚИЛИНДИ' in text and 'Malika Kassir' in text for uid,text in calls))
        self.assertTrue(any(uid==1 and 'КАССА ҲАРАКАТИ' in text and '15.00 USD' in text for uid,text in calls))
        self.assertEqual(core.cash_usd(self.db,2),core.money('5.00'))


if __name__=='__main__':
    unittest.main()
