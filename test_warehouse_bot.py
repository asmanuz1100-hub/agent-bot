import unittest, time
from unittest.mock import patch
import core, bot, warehouse

def msg(i,uid,text):
    return {'update_id':i,'message':{'message_id':i,'date':int(time.time()),'from':{'id':uid},
            'chat':{'id':uid,'type':'private'},'text':text}}

def buttons(db,uid):
    return [b for row in bot.menu(db,uid) for b in row]

class WarehouseBotTests(unittest.TestCase):
    def setUp(self):
        self.db=core.connect(':memory:')
        self.db.executemany('INSERT INTO users VALUES(?,?,?)',[(1,'admin','A'),(2,'agent','B'),(3,'cashier','C'),(5,'warehouse','W')])
        self.pack=next(iter(core.PRODUCTS))
    def tearDown(self):self.db.close()

    def test_hidden_and_closed_when_test_mode_off(self):
        with patch.object(bot,'WAREHOUSE_TEST_MODE',False),patch.object(bot,'send'):
            self.assertNotIn('🏬 Омбор (ТЕСТ)',buttons(self.db,1))
            with self.assertRaises(ValueError):bot.handle(self.db,msg(1,1,'/wh'))
            with self.assertRaises(ValueError):bot.handle(self.db,msg(2,1,f'/wh_in {self.pack} 10'))
        self.assertEqual(warehouse.stock(self.db,self.pack),0)

    def test_only_admin_in_test_mode(self):
        with patch.object(bot,'WAREHOUSE_TEST_MODE',True),patch.object(bot,'send'):
            self.assertIn('🏬 Омбор (ТЕСТ)',buttons(self.db,1))
            for uid in (2,3,5):
                self.assertNotIn('🏬 Омбор (ТЕСТ)',buttons(self.db,uid))
                with self.assertRaises(ValueError):bot.handle(self.db,msg(10+uid,uid,'🏬 Омбор (ТЕСТ)'))
                with self.assertRaises(ValueError):bot.handle(self.db,msg(20+uid,uid,f'/wh_in {self.pack} 10'))
        self.assertEqual(warehouse.stock(self.db,self.pack),0)

    def test_admin_receive_issue_and_decide(self):
        with patch.object(bot,'WAREHOUSE_TEST_MODE',True),patch.object(bot,'send') as send:
            bot.handle(self.db,msg(1,1,'🏬 Омбор (ТЕСТ)'))
            self.assertIn('ОМБОР ҚОЛДИҒИ',send.call_args.args[1])
            bot.handle(self.db,msg(2,1,f'/wh_in {self.pack} 10 харид'))
            bot.handle(self.db,msg(3,1,f'/wh_issue 2 {self.pack} 4'))
            self.assertEqual(warehouse.stock(self.db,self.pack),6)
            self.assertEqual(core.agent_stock(self.db,2,self.pack),4)
            rid=warehouse.create_request(self.db,2,'return',self.pack,3)
            bot.handle(self.db,msg(4,1,f'/wh_ok {rid}'))
            self.assertEqual(warehouse.stock(self.db,self.pack),9)
            self.assertEqual(core.agent_stock(self.db,2,self.pack),1)
            bot.handle(self.db,msg(5,1,f'/wh_off {self.pack} 2 синган'))
            self.assertEqual(warehouse.stock(self.db,self.pack),7)
            with self.assertRaises(ValueError):bot.handle(self.db,msg(6,1,f'/wh_issue 2 {self.pack} 100'))
            with self.assertRaises(ValueError):bot.handle(self.db,msg(7,1,'/wh_in abc 1'))

    def test_agent_app_stock_counts_warehouse_return(self):
        import agent_api
        with patch.object(bot,'WAREHOUSE_TEST_MODE',True),patch.object(bot,'send'):
            bot.handle(self.db,msg(1,1,f'/wh_in {self.pack} 10'))
            bot.handle(self.db,msg(2,1,f'/wh_issue 2 {self.pack} 5 эрталабки юк'))
            rid=warehouse.create_request(self.db,2,'return',self.pack,3)
            bot.handle(self.db,msg(3,1,f'/wh_ok {rid}'))
        self.assertEqual(core.agent_stock(self.db,2,self.pack),2)
        shown={p['pack']:p['agentStock'] for p in agent_api._products(self.db,2)}
        self.assertEqual(shown[self.pack],2)
        note=self.db.execute("SELECT note FROM warehouse_moves WHERE kind='issue'").fetchone()[0]
        self.assertEqual(note,'эрталабки юк')

    def test_admin_adds_new_product_from_warehouse(self):
        with patch.object(bot,'WAREHOUSE_TEST_MODE',True),patch.object(bot,'send') as send:
            bot.handle(self.db,msg(1,1,'/wh_new Эмаль оқ — 3 кг | 3 | 12.50 | 6'))
            pack=max(core.PRODUCTS)
            self.assertEqual(core.PRODUCTS[pack],'Эмаль оқ — 3 кг')
            self.assertEqual(core.block_units(pack),6)
            self.assertEqual(core.product_price(self.db,pack),1250)
            self.assertIn(f'код {pack}',send.call_args.args[1])
            bot.handle(self.db,msg(2,1,f'/wh_in {pack} 12'))
            self.assertEqual(warehouse.stock(self.db,pack),12)
            bot.handle(self.db,msg(3,1,'🏬 Омбор (ТЕСТ)'))
            self.assertIn('Эмаль оқ — 3 кг: 12 дона (2 блок + 0 дона)',send.call_args.args[1])
            for bad in ('/wh_new Эмаль', '/wh_new Эмаль | 3 | 0', '/wh_new Эмаль оқ — 3 кг | 3 | 5'):
                with self.assertRaises(ValueError):bot.handle(self.db,msg(9,1,bad))
            with self.assertRaises(ValueError):bot.handle(self.db,msg(10,2,'/wh_new Бошқа | 1 | 2'))

if __name__=='__main__':unittest.main()
