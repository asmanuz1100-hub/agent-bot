import unittest, time
from unittest.mock import patch
import core, bot

class Tests(unittest.TestCase):
 def setUp(self):
  self.db=core.connect(':memory:')
  self.db.executemany('INSERT INTO users VALUES(?,?,?)',[(1,'admin','A'),(2,'agent','B'),(3,'cashier','C'),(4,'agent','D')])
  self.db.execute("INSERT INTO clients(id,agent,name,phone,address,lat,lon,photo,shop_name) VALUES(1,2,'Мижоз','+998900000001','Тест манзил',40,71,NULL,'Тест дўкон')")
 def tearDown(self):self.db.close()
 def rec(self,k,q=0,value=0,actor=2,source=None):
  core.record(self.db,actor,2,None if k=='load' else 1,k,1,q,value,source=source)
 def test_consignment_not_debt(self):
  self.rec('load',12,actor=1);self.rec('delivery',4)
  self.assertEqual(core.agent_stock(self.db,2,1),8)
  self.assertEqual(core.client_stock(self.db,2,1,1),4)
  self.assertEqual(core.amount(self.db,2,['sold'],1,field='amount'),0)
 def test_sale_and_payment(self):
  self.rec('load',12,actor=1);self.rec('delivery',4);self.rec('sold',2,1000000);self.rec('payment',value=700000)
  self.assertEqual(core.client_stock(self.db,2,1,1),2)
  self.assertEqual(core.cash(self.db,2),700000)
  self.assertEqual(core.amount(self.db,2,['sold'],1,field='amount')-core.amount(self.db,2,['payment'],1,field='amount'),300000)
 def test_insufficient_stock(self):
  with self.assertRaises(ValueError):self.rec('delivery',1)
  self.rec('load',1,actor=1);self.rec('delivery',1)
  with self.assertRaises(ValueError):self.rec('sold',2,100)
 def test_stock_permissions(self):
  with self.assertRaises(ValueError):self.rec('load',1)
  with self.assertRaises(ValueError):self.rec('delivery',1,actor=4)
 def test_return(self):
  self.rec('load',4,actor=1);self.rec('delivery',4);self.rec('return',2)
  self.assertEqual(core.agent_stock(self.db,2,1),2);self.assertEqual(core.client_stock(self.db,2,1,1),2)
 def test_cashier_double_accept_and_reservation(self):
  self.rec('payment',value=1000);core.handover(self.db,2,700,10)
  with self.assertRaises(ValueError):core.handover(self.db,2,500,11)
  with self.assertRaises(ValueError):core.accept(self.db,2,1)
  core.accept(self.db,3,1);self.assertEqual(core.cash(self.db,2),300)
  with self.assertRaises(ValueError):core.accept(self.db,3,1)
 def test_reject_frees_reservation(self):
  self.rec('payment',value=1000);core.handover(self.db,2,1000,10);core.accept(self.db,3,1,False)
  core.handover(self.db,2,1000,11);self.assertEqual(core.cash(self.db,2),1000)
 def test_money(self):
  self.assertEqual(core.money('12 000,50'),1200050)
  for v in ['NaN','-2','1.001','0','Infinity']:
   with self.assertRaises(ValueError):core.money(v)
 def test_privacy(self):
  self.assertFalse(bot.allowed(self.db,2,'tracking'));self.assertFalse(bot.allowed(self.db,3,'tracking'))
  with self.assertRaises(ValueError):bot.tracking(self.db,3,2)
 def test_tracking_shift_bounds(self):
  m={'message_id':20,'date':100,'location':{'latitude':40,'longitude':71,'live_period':3600}}
  self.assertFalse(core.point(self.db,2,m))
  self.db.execute('INSERT INTO shifts(agent,start) VALUES(2,100)')
  self.assertTrue(core.point(self.db,2,m))
  other={'message_id':21,'date':101,'location':{'latitude':40.1,'longitude':71.1,'live_period':3600}}
  self.assertFalse(core.point(self.db,2,other))
  m['edit_date']=110
  self.assertTrue(core.point(self.db,2,m,True))
  m['message_id']=21;self.assertFalse(core.point(self.db,2,m,True))
  self.db.execute('UPDATE shifts SET end=120');m['message_id']=20;m['edit_date']=130
  self.assertFalse(core.point(self.db,2,m,True))
  self.assertEqual(self.db.execute('SELECT COUNT(*) FROM points').fetchone()[0],2)
 def test_gap_not_distance(self):
  p=[{'lat':40,'lon':71,'ts':100,'accuracy':10},{'lat':42,'lon':73,'ts':1000,'accuracy':10}]
  r=core.route_stats(p,100,1500);self.assertEqual(r['km'],0);self.assertEqual(len(r['gaps']),2)
 def test_empty_and_stationary(self):
  self.assertEqual(core.route_stats([],100,1000)['gaps'],[(100,1000)])
  ps=[{'lat':40,'lon':71,'ts':x,'accuracy':10} for x in [100,200,300,400,500]]
  self.assertEqual(len(core.route_stats(ps,100,500)['stops']),1)
 def test_full_delivery_ui_and_confirmation(self):
  self.rec('load',12,actor=1)
  now=int(time.time())
  self.db.execute('INSERT INTO shifts(agent,start) VALUES(2,?)',(now-10,))
  self.assertTrue(core.point(self.db,2,{'message_id':90,'date':now,'location':{'latitude':40,'longitude':71,'live_period':3600}}))
  def msg(i,t):return {'update_id':i,'message':{'message_id':i,'date':int(time.time()),'from':{'id':2},'chat':{'id':2,'type':'private'},'text':t}}
  with patch.object(bot,'send'):
   for i,t in enumerate(['📦 Товар бериш','1 · Мижоз','1','Блок','2'],100):bot.handle(self.db,msg(i,t))
   self.assertEqual(core.agent_stock(self.db,2,1),12)
   bot.handle(self.db,msg(105,'✅ Тасдиқлаш'))
   self.assertEqual(core.agent_stock(self.db,2,1),4)
   bot.handle(self.db,msg(106,'✅ Тасдиқлаш'))
   self.assertEqual(core.agent_stock(self.db,2,1),4)
 def test_client_onboarding_location_first_and_delivery(self):
  self.rec('load',12,actor=1)
  now=int(time.time())
  self.db.execute('INSERT INTO shifts(agent,start) VALUES(2,?)',(now-10,))
  self.assertTrue(core.point(self.db,2,{'message_id':80,'date':now,'location':{'latitude':40,'longitude':71,'live_period':3600}}))
  def msg(i,text=None,loc=None,photo=None):
   m={'message_id':i,'date':int(time.time()),'from':{'id':2},'chat':{'id':2,'type':'private'}}
   if text is not None:m['text']=text
   if loc is not None:m['location']=loc
   if photo is not None:m['photo']=[{'file_id':photo}]
   return {'update_id':i,'message':m}
  with patch.object(bot,'send'):
   bot.handle(self.db,msg(200,'🏪 Мижоз қўшиш'))
   self.assertEqual(bot.state(self.db,2)['step'],0)
   bot.handle(self.db,msg(201,loc={'latitude':40.5,'longitude':71.5}))
   bot.handle(self.db,msg(202,'Алишер'))
   bot.handle(self.db,msg(203,'ASMAN SHOP'))
   bot.handle(self.db,msg(204,'+998901234567'))
   bot.handle(self.db,msg(205,'Қўқон, Марказ'))
   bot.handle(self.db,msg(206,photo='photo-file-id'))
   bot.handle(self.db,msg(207,'1 кг грунтовкадан кўпроқ олишни хоҳлади'))
   bot.handle(self.db,msg(208,'2026-09-25'))
   bot.handle(self.db,msg(209,'1'))
   bot.handle(self.db,msg(210,'Блок'))
   bot.handle(self.db,msg(211,'2'))
   bot.handle(self.db,msg(212,'✅ Тасдиқлаш'))
  row=self.db.execute("SELECT name,shop_name,phone,address,photo,comment,payment_due FROM clients WHERE name='Алишер'").fetchone()
  self.assertEqual((row['name'],row['shop_name'],row['phone'],row['address']),('Алишер','ASMAN SHOP','+998901234567','Қўқон, Марказ'))
  self.assertEqual(row['photo'],'photo-file-id')
  self.assertIn('грунтовка',row['comment'])
  self.assertEqual(row['payment_due'],'2026-09-25')
  cid=self.db.execute("SELECT id FROM clients WHERE name='Алишер'").fetchone()[0]
  self.assertEqual(core.client_stock(self.db,2,cid,1),8)
  self.assertEqual(core.agent_stock(self.db,2,1),4)

 def test_product_catalog_and_admin_price(self):
  self.assertEqual(core.product_name(1),'Грунтовка 7/1 — 1 кг')
  self.assertEqual(core.product_name(3),'Грунтовка 7/1 — 3 кг')
  self.assertEqual(core.product_name(5),'Грунтовка 7/1 — 5 кг')
  core.set_product_price(self.db,1,1,core.money('12000'))
  self.assertEqual(core.product_price(self.db,1),core.money('12000'))
  with self.assertRaises(ValueError):core.set_product_price(self.db,2,1,core.money('13000'))

 def test_admin_agent_management_and_price_flow(self):
  def msg(i,t):return {'update_id':i,'message':{'message_id':i,'date':int(time.time()),'from':{'id':1},'chat':{'id':1,'type':'private'},'text':t}}
  with patch.object(bot,'send') as send:
   bot.handle(self.db,msg(300,'👥 Агентлар бошқаруви'))
   self.assertIn('Агентларни бошқариш',send.call_args.args[1])
   bot.handle(self.db,msg(301,'✏️ Нарх киритиш'))
   bot.handle(self.db,msg(302,'Грунтовка 7/1 — 1 кг'))
   bot.handle(self.db,msg(303,'15000'))
   bot.handle(self.db,msg(304,'✅ Тасдиқлаш'))
  self.assertEqual(core.product_price(self.db,1),core.money('15000'))
  with patch.object(bot,'send'):
   bot.handle(self.db,msg(305,'✏️ Агент номини ўзгартириш'))
   bot.handle(self.db,msg(306,'2 · B'))
   bot.handle(self.db,msg(307,'Сардор'))
   bot.handle(self.db,msg(308,'✅ Тасдиқлаш'))
  self.assertEqual(self.db.execute('SELECT name FROM users WHERE id=2').fetchone()[0],'Сардор')

 def test_sale_prompt_uses_catalog_price(self):
  core.set_product_price(self.db,1,1,core.money('10000'))
  self.rec('load',8,actor=1);self.rec('delivery',4)
  now=int(time.time())
  self.db.execute('INSERT INTO shifts(agent,start) VALUES(2,?)',(now-10,))
  self.assertTrue(core.point(self.db,2,{'message_id':77,'date':now,'location':{'latitude':40,'longitude':71,'live_period':3600}}))
  def msg(i,t):return {'update_id':i,'message':{'message_id':i,'date':int(time.time()),'from':{'id':2},'chat':{'id':2,'type':'private'},'text':t}}
  with patch.object(bot,'send') as send:
   bot.handle(self.db,msg(400,'💵 Сотилган товар'))
   bot.handle(self.db,msg(401,'1 · Мижоз'))
   bot.handle(self.db,msg(402,'Грунтовка 7/1 — 1 кг'))
   bot.handle(self.db,msg(403,'Дона'))
   bot.handle(self.db,msg(404,'2'))
   text=send.call_args.args[1]
   self.assertIn('Каталог нархи: 10 000.00',text)
   self.assertIn('Ҳисобланган жами: 20 000.00',text)

 def test_agent_service_permissions(self):
  self.assertTrue(core.feature_enabled(self.db,2,'delivery'))
  self.assertTrue(bot.allowed(self.db,2,'delivery'))
  self.assertTrue(bot.allowed(self.db,2,'shift'))
  core.set_agent_feature(self.db,1,2,'delivery',False)
  self.assertFalse(core.feature_enabled(self.db,2,'delivery'))
  self.assertFalse(bot.allowed(self.db,2,'delivery'))
  self.assertTrue(bot.allowed(self.db,2,'shift'))
  flat=[x for row in bot.menu(self.db,2) for x in row]
  self.assertNotIn('📦 Товар бериш',flat)
  with self.assertRaises(ValueError):core.set_agent_feature(self.db,2,2,'delivery',True)

 def test_admin_agent_profile_toggle_flow(self):
  def msg(i,t):return {'update_id':i,'message':{'message_id':i,'date':int(time.time()),'from':{'id':1},'chat':{'id':1,'type':'private'},'text':t}}
  with patch.object(bot,'send') as send:
   bot.handle(self.db,msg(500,'👥 Агентлар бошқаруви'))
   self.assertIn('👤 Агент профили',[x for row in send.call_args.args[2] for x in row])
   bot.handle(self.db,msg(501,'👤 Агент профили'))
   bot.handle(self.db,msg(502,'2 · B'))
   self.assertEqual(bot.state(self.db,1)['action'],'agent_profile_view')
   self.assertIn('АГЕНТ ПРОФИЛИ',send.call_args.args[1])
   bot.handle(self.db,msg(503,'✅ 📦 Товар бериш'))
   self.assertFalse(core.feature_enabled(self.db,2,'delivery'))
   self.assertIn('❌ 📦 Товар бериш',send.call_args.args[1])
   bot.handle(self.db,msg(504,'❌ 📦 Товар бериш'))
   self.assertTrue(core.feature_enabled(self.db,2,'delivery'))

 def test_nonprivate_ignored(self):
  with patch.object(bot,'send') as send:
   bot.handle(self.db,{'update_id':10,'message':{'chat':{'id':-1,'type':'group'},'from':{'id':1},'text':'📍 Агентлар'}})
   send.assert_not_called()

if __name__=='__main__':unittest.main()
