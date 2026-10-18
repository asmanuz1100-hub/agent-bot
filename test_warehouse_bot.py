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

    def test_admin_views_but_movements_belong_to_keeper(self):
        # Tovar harakatini faqat omborchi kiritadi; rahbar bot'da faqat ko'radi.
        with patch.object(bot,'WAREHOUSE_TEST_MODE',True),patch.object(bot,'send') as send:
            warehouse.receive(self.db,5,self.pack,10,'харид')
            warehouse.issue(self.db,5,2,self.pack,4)
            bot.handle(self.db,msg(1,1,'🏬 Омбор (ТЕСТ)'))
            self.assertIn('ОМБОР ҚОЛДИҒИ',send.call_args.args[1])
            self.assertIn('Омборчи Mini App',send.call_args.args[1])
            for i,cmd in enumerate((f'/wh_in {self.pack} 1',f'/wh_issue 2 {self.pack} 1',f'/wh_off {self.pack} 1 синган')):
                with self.assertRaises(ValueError):bot.handle(self.db,msg(10+i,1,cmd))
        self.assertEqual(warehouse.stock(self.db,self.pack),6)
        self.assertEqual(core.agent_stock(self.db,2,self.pack),4)

    def test_agent_app_stock_counts_warehouse_return(self):
        import agent_api
        warehouse.receive(self.db,5,self.pack,10)
        warehouse.issue(self.db,5,2,self.pack,5)
        rid=warehouse.create_request(self.db,2,'return',self.pack,3)
        warehouse.decide(self.db,5,rid)
        self.assertEqual(core.agent_stock(self.db,2,self.pack),2)
        shown={p['pack']:p['agentStock'] for p in agent_api._products(self.db,2)}
        self.assertEqual(shown[self.pack],2)

    def test_admin_adds_new_product_from_warehouse(self):
        with patch.object(bot,'WAREHOUSE_TEST_MODE',True),patch.object(bot,'send') as send:
            bot.handle(self.db,msg(1,1,'/wh_new Эмаль оқ — 3 кг | 3 | 12.50 | 6'))
            pack=max(core.PRODUCTS)
            self.assertEqual(core.PRODUCTS[pack],'Эмаль оқ — 3 кг')
            self.assertEqual(core.block_units(pack),6)
            self.assertEqual(core.product_price(self.db,pack),1250)
            self.assertIn(f'код {pack}',send.call_args.args[1])
            warehouse.receive(self.db,5,pack,12)
            bot.handle(self.db,msg(3,1,'🏬 Омбор (ТЕСТ)'))
            self.assertIn('Эмаль оқ — 3 кг: 12 дона (2 блок + 0 дона)',send.call_args.args[1])
            for bad in ('/wh_new Эмаль', '/wh_new Эмаль | 3 | 0', '/wh_new Эмаль оқ — 3 кг | 3 | 5'):
                with self.assertRaises(ValueError):bot.handle(self.db,msg(9,1,bad))
            with self.assertRaises(ValueError):bot.handle(self.db,msg(10,2,'/wh_new Бошқа | 1 | 2'))

if __name__=='__main__':unittest.main()
