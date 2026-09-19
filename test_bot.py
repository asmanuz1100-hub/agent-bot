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
 def test_primary_admin_can_add_secondary_admin(self):
  def msg(i,uid,text):
   return {'update_id':i,'message':{'message_id':i,'date':int(time.time()),'from':{'id':uid},'chat':{'id':uid,'type':'private'},'text':text}}
  with patch.object(bot,'ADMINS',{1}),patch.object(bot,'send') as send:
   buttons=[b for row in bot.menu(self.db,1) for b in row]
   self.assertIn('🔐 Админ қўшиш',buttons)
   bot.handle(self.db,msg(15001,1,'🔐 Админ қўшиш'))
   bot.handle(self.db,msg(15002,1,'123456789'))
   bot.handle(self.db,msg(15003,1,'Янги админ'))
   self.assertIn('Текширинг:',send.call_args.args[1])
   bot.handle(self.db,msg(15004,1,'✅ Тасдиқлаш'))
   self.assertEqual(bot.role(self.db,123456789),'admin')
   self.assertTrue(bot.allowed(self.db,123456789,'analytics'))
   self.assertFalse(bot.allowed(self.db,123456789,'admin_add'))
   self.assertNotIn('🔐 Админ қўшиш',[b for row in bot.menu(self.db,123456789) for b in row])
   self.assertIn('админ сифатида қўшилди',send.call_args.args[1])
   bot.handle(self.db,msg(15005,123456789,'/start'))
   self.assertIn('Амални танланг',send.call_args.args[1])
   bot.handle(self.db,msg(15006,123456789,'🔐 Админ қўшиш'))
   self.assertIsNone(self.db.execute('SELECT 1 FROM users WHERE id=123456790').fetchone())

 def test_secondary_admin_cannot_escalate_via_saved_wizard(self):
  with patch.object(bot,'ADMINS',{1}),patch.object(bot,'send'):
   self.db.execute("INSERT INTO users(id,role,name) VALUES(123456789,'admin','Secondary')")
   self.assertFalse(bot.allowed(self.db,123456789,'admin_add'))
   with self.assertRaises(ValueError):
    bot.finish(self.db,123456789,{'action':'admin_add','step':2,'values':{'id':123456790,'name':'Other'}},15007)
   self.assertIsNone(self.db.execute('SELECT 1 FROM users WHERE id=123456790').fetchone())
   with self.assertRaises(ValueError):
    bot.finish(self.db,1,{'action':'admin_add','step':2,'values':{'id':2,'name':'Agent'}},15008)
   self.assertEqual(bot.role(self.db,2),'agent')

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
  core.set_product_price(self.db,1,1,core.money('2.00'))
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
  core.set_product_price(self.db,1,1,core.money('2.00'))
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
   self.assertIn('Текширинг:',text)
   self.assertIn('2 дона',text)
   self.assertNotIn('сўмда',text)

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

 def test_map_links_expire(self):
  with patch.dict(bot.os.environ,{'RENDER_EXTERNAL_URL':'https://example.test'},clear=False), patch.object(bot.time,'time',return_value=2_000_000_000):
   link=bot.map_link('overall')
  parts=link.rstrip('/').split('/')
  expires=int(parts[-2]);sig=parts[-1]
  self.assertEqual(expires,2_000_000_000+bot.MAP_TTL_SECONDS)
  self.assertTrue(bot._map_valid('overall',expires,sig,2_000_000_000))
  self.assertFalse(bot._map_valid('overall',expires,sig,expires+1))
  self.assertFalse(bot._map_valid('agent/2',expires,sig,2_000_000_000))

 def test_repeated_unexpected_update_can_be_skipped(self):
  err=RuntimeError('boom')
  self.assertEqual(bot._register_failure(self.db,900,err),1)
  self.assertEqual(bot._register_failure(self.db,900,err),2)
  self.assertEqual(bot._register_failure(self.db,900,err),3)
  with patch.object(bot,'send'):
   bot._skip_failed_update(self.db,900,err,True)
  self.assertIsNotNone(self.db.execute('SELECT 1 FROM processed WHERE id=900').fetchone())
  self.assertEqual(self.db.execute("SELECT value FROM meta WHERE key='offset'").fetchone()[0],'901')
  self.assertIsNone(self.db.execute('SELECT value FROM meta WHERE key=?',(bot._failure_key(900),)).fetchone())

 def test_client_search_finds_older_clients(self):
  rows=[]
  for i in range(60):
   rows.append((10+i,2,f'Client {i:02d}',f'+99891{i:07d}',f'Address {i}',40,71,None,f'Shop {i:02d}'))
  self.db.executemany('INSERT INTO clients(id,agent,name,phone,address,lat,lon,photo,shop_name) VALUES(?,?,?,?,?,?,?,?,?)',rows)
  self.rec('load',20,actor=1)
  now=int(time.time());self.db.execute('INSERT INTO shifts(agent,start) VALUES(2,?)',(now-10,))
  self.assertTrue(core.point(self.db,2,{'message_id':600,'date':now,'location':{'latitude':40,'longitude':71,'live_period':3600}}))
  def msg(i,t):return {'update_id':i,'message':{'message_id':i,'date':int(time.time()),'from':{'id':2},'chat':{'id':2,'type':'private'},'text':t}}
  with patch.object(bot,'send') as send:
   bot.handle(self.db,msg(601,'📦 Товар бериш'))
   bot.handle(self.db,msg(602,'🔎 Мижоз қидириш'))
   bot.handle(self.db,msg(603,'Client 05'))
   keys=send.call_args.args[2]
  flat=[x for row in keys for x in row]
  self.assertTrue(any('Client 05' in x for x in flat))

 def test_full_sale_return_payment_and_reconcile_ui(self):
  core.set_product_price(self.db,1,1,core.money('2.00'))
  self.rec('load',12,actor=1)
  core.record(self.db,2,2,1,'delivery',1,6,currency='USD')
  now=int(time.time());self.db.execute('INSERT INTO shifts(agent,start) VALUES(2,?)',(now-10,))
  self.assertTrue(core.point(self.db,2,{'message_id':700,'date':now,'location':{'latitude':40,'longitude':71,'live_period':3600}}))
  def amsg(i,t):return {'update_id':i,'message':{'message_id':i,'date':int(time.time()),'from':{'id':2},'chat':{'id':2,'type':'private'},'text':t}}
  with patch.object(bot,'send'):
   seq=['💵 Сотилган товар','1','Грунтовка 7/1 — 1 кг','Дона','2','✅ Тасдиқлаш']
   for i,t in enumerate(seq,701):bot.handle(self.db,amsg(i,t))
   self.assertEqual(core.client_stock(self.db,2,1,1),4)
   self.assertEqual(core.amount(self.db,2,['sold'],1,field='amount'),0)
   seq=['↩️ Товар қайтариш','1','Грунтовка 7/1 — 1 кг','Дона','1','✅ Тасдиқлаш']
   for i,t in enumerate(seq,710):bot.handle(self.db,amsg(i,t))
   self.assertEqual(core.client_stock(self.db,2,1,1),3)
   self.assertEqual(core.client_debt_usd(self.db,1),core.money('10.00'))
   seq=['💰 Пул олиш','1','5000','✅ Тасдиқлаш']
   for i,t in enumerate(seq,720):bot.handle(self.db,amsg(i,t))
   self.assertEqual(core.cash_usd(self.db,2),core.money('5000'))
  day=bot.datetime.fromtimestamp(int(time.time()),bot.TZ).strftime('%Y-%m-%d')
  def dmsg(i,t):return {'update_id':i,'message':{'message_id':i,'date':int(time.time()),'from':{'id':1},'chat':{'id':1,'type':'private'},'text':t}}
  with patch.object(bot,'send'),patch.object(bot,'document') as document:
   for i,t in enumerate(['📄 Акт сверка','1',day,day,'✅ Тасдиқлаш'],730):bot.handle(self.db,dmsg(i,t))
   document.assert_called_once()
   self.assertIn('akt-sverka-1-',document.call_args.args[1])

 def test_back_button_preserves_previous_client_data(self):
  self.rec('load',12,actor=1)
  now=int(time.time());self.db.execute('INSERT INTO shifts(agent,start) VALUES(2,?)',(now-10,))
  self.assertTrue(core.point(self.db,2,{'message_id':800,'date':now,'location':{'latitude':40,'longitude':71,'live_period':3600}}))
  def msg(i,text=None,loc=None):
   m={'message_id':i,'date':int(time.time()),'from':{'id':2},'chat':{'id':2,'type':'private'}}
   if text is not None:m['text']=text
   if loc is not None:m['location']=loc
   return {'update_id':i,'message':m}
  with patch.object(bot,'send') as send:
   bot.handle(self.db,msg(801,'🏪 Мижоз қўшиш'))
   bot.handle(self.db,msg(802,loc={'latitude':40.5,'longitude':71.5}))
   bot.handle(self.db,msg(803,'Алишер'))
   self.assertEqual(bot.state(self.db,2)['step'],2)
   bot.handle(self.db,msg(804,'⬅️ Орқага'))
   s=bot.state(self.db,2)
   self.assertEqual(s['step'],1)
   self.assertNotIn('name',s['values'])
   self.assertEqual(s['values']['lat'],40.5);self.assertEqual(s['values']['lon'],71.5)
   self.assertIn('Мижоз исми',send.call_args.args[1])

 def test_validation_error_repeats_current_question(self):
  self.rec('load',12,actor=1)
  now=int(time.time());self.db.execute('INSERT INTO shifts(agent,start) VALUES(2,?)',(now-10,))
  self.assertTrue(core.point(self.db,2,{'message_id':810,'date':now,'location':{'latitude':40,'longitude':71,'live_period':3600}}))
  def msg(i,text=None,loc=None):
   m={'message_id':i,'date':int(time.time()),'from':{'id':2},'chat':{'id':2,'type':'private'}}
   if text is not None:m['text']=text
   if loc is not None:m['location']=loc
   return {'update_id':i,'message':m}
  with patch.object(bot,'send') as send:
   bot.process_update(self.db,msg(811,'🏪 Мижоз қўшиш'))
   bot.process_update(self.db,msg(812,loc={'latitude':40.5,'longitude':71.5}))
   bot.process_update(self.db,msg(813,'Алишер'))
   bot.process_update(self.db,msg(814,'Дўкон'))
   send.reset_mock()
   bot.process_update(self.db,msg(815,'123'))
   texts=[call.args[1] for call in send.call_args_list]
   self.assertTrue(any('Телефонни +998' in x for x in texts))
   self.assertTrue(any('Мижоз телефон рақами' in x for x in texts))
   self.assertEqual(bot.state(self.db,2)['step'],3)

 def test_location_help_does_not_cancel_current_wizard(self):
  self.rec('load',12,actor=1)
  now=int(time.time());self.db.execute('INSERT INTO shifts(agent,start) VALUES(2,?)',(now-10,))
  self.assertTrue(core.point(self.db,2,{'message_id':820,'date':now,'location':{'latitude':40,'longitude':71,'live_period':3600}}))
  def msg(i,t):return {'update_id':i,'message':{'message_id':i,'date':int(time.time()),'from':{'id':2},'chat':{'id':2,'type':'private'},'text':t}}
  with patch.object(bot,'send') as send:
   bot.handle(self.db,msg(821,'📦 Товар бериш'))
   before=bot.state(self.db,2)
   bot.handle(self.db,msg(822,'ℹ️ Локация ёрдами'))
   after=bot.state(self.db,2)
   self.assertEqual(before,after)
   self.assertIn('ЖОНЛИ ЛОКАЦИЯ БЎЙИЧА ЁРДАМ',send.call_args.args[1])

 def test_end_shift_sends_daily_summary_to_agent_and_admin(self):
  now=int(time.time());start=now-120
  self.db.execute('INSERT INTO shifts(agent,start,live_id) VALUES(2,?,55)',(start,))
  shift=self.db.execute('SELECT id FROM shifts WHERE agent=2 AND end IS NULL').fetchone()[0]
  self.db.executemany('INSERT INTO points(shift,ts,lat,lon,accuracy) VALUES(?,?,?,?,?)',[
   (shift,start+5,40.0,71.0,10),(shift,now-5,40.01,71.01,10)
  ])
  self.db.execute("INSERT INTO clients(id,agent,name,phone,address,created_ts) VALUES(20,2,'Today','+998900000020','Today address',?)",(start+10,))
  self.db.execute("INSERT INTO events(actor,agent,client,kind,pack,qty,amount,ts) VALUES(2,2,20,'sold',1,2,3000000,?)",(now-20,))
  def msg(i,t):return {'update_id':i,'message':{'message_id':i,'date':now,'from':{'id':2},'chat':{'id':2,'type':'private'},'text':t}}
  with patch.object(bot,'ADMINS',{1}),patch.object(bot,'send') as send,patch.object(bot,'send_inline'),patch.object(bot,'map_link',return_value='https://example.test/map'):
   bot.handle(self.db,msg(900,'⏹ Ишни тугатиш'))
  closed=self.db.execute('SELECT end FROM shifts WHERE id=?',(shift,)).fetchone()[0]
  self.assertEqual(closed,now)
  messages=[call.args for call in send.call_args_list]
  self.assertTrue(any(args[0]==2 and 'КУНЛИК ФАОЛИЯТ' in args[1] for args in messages))
  self.assertTrue(any(args[0]==1 and 'Агент ишни тугатди' in args[1] for args in messages))

 def test_usd_prices_without_converting_uzs_ledger(self):
  core.set_product_price(self.db,1,1,core.money('2.50'))
  with patch.object(bot,'send') as send:
   bot.report_prices(self.db,1)
   self.assertIn('2.50 USD / дона',send.call_args.args[1])
   self.assertIn('USD ҳисобда юритилади',send.call_args.args[1])
   bot.handle(self.db,{'update_id':9991,'message':{'message_id':9991,'date':int(time.time()),'from':{'id':1},'chat':{'id':1,'type':'private'},'text':'✏️ Нарх киритиш'}})
   bot.handle(self.db,{'update_id':9992,'message':{'message_id':9992,'date':int(time.time()),'from':{'id':1},'chat':{'id':1,'type':'private'},'text':'Грунтовка 7/1 — 1 кг'}})
   self.assertIn('USD',send.call_args.args[1])
  self.assertEqual(core.product_price(self.db,1),core.money('2.50'))
  # The product catalog uses USD cents, but cash and existing balances stay in UZS cents.
  self.rec('payment',value=core.money('15000'))
  self.assertEqual(core.cash(self.db,2),core.money('15000'))

 def test_agent_is_informed_about_admin_gps_monitoring(self):
  now=int(time.time())
  def msg(i,t):return {'update_id':i,'message':{'message_id':i,'date':now,'from':{'id':2},'chat':{'id':2,'type':'private'},'text':t}}
  with patch.object(bot,'send') as send:
   bot.handle(self.db,msg(10001,'▶️ Ишни бошлаш'))
   self.assertIn('Админ',send.call_args.args[1])
   self.assertIn('жойлашувингиз',send.call_args.args[1])
   bot.handle(self.db,msg(10002,'ℹ️ Локация ёрдами'))
   self.assertIn('кузатиши мумкин',send.call_args.args[1])
   location={'update_id':10003,'message':{'message_id':10003,'date':now,'from':{'id':2},'chat':{'id':2,'type':'private'},'location':{'latitude':40.0,'longitude':71.0,'live_period':3600}}}
   bot.handle(self.db,location)
   self.assertIn('админ',send.call_args.args[1])

 def test_usd_delivery_debt_sale_return_payment_and_cashier(self):
  core.set_product_price(self.db,1,1,core.money('2.00'))
  self.rec('load',12,actor=1)
  core.record(self.db,2,2,1,'delivery',1,4,source=20001,currency='USD')
  self.assertEqual(core.client_debt_usd(self.db,1),core.money('8.00'))
  self.assertEqual(core.amount(self.db,2,['delivery'],1,field='amount'),0)
  core.record(self.db,2,2,1,'sold',1,1,source=20002,currency='USD')
  self.assertEqual(core.client_debt_usd(self.db,1),core.money('8.00'))
  core.record(self.db,2,2,1,'return',1,1,source=20003,currency='USD')
  self.assertEqual(core.client_debt_usd(self.db,1),core.money('6.00'))
  core.record(self.db,2,2,1,'payment',value=core.money('1.50'),source=20004,currency='USD')
  self.assertEqual(core.client_debt_usd(self.db,1),core.money('4.50'))
  self.assertEqual(core.cash_usd(self.db,2),core.money('1.50'))
  self.assertEqual(core.cash(self.db,2),0)
  core.handover(self.db,2,core.money('1.00'),20005,currency='USD')
  core.accept(self.db,3,1)
  self.assertEqual(core.cash_usd(self.db,2),core.money('0.50'))
  today=bot.datetime.fromtimestamp(int(time.time()),bot.TZ).strftime('%Y-%m-%d')
  result=bot.reports.reconciliation(self.db,1,1,today,today)
  self.assertEqual((result['usd_sales'],result['usd_returns'],result['usd_payments'],result['usd_closing']),
                   (core.money('8.00'),core.money('2.00'),core.money('1.50'),core.money('4.50')))
  self.assertEqual(result['closing'],0)
  self.assertIn('4.50 USD',bot.reports.reconciliation_html(result).decode())

 def test_usd_backfill_skips_clients_with_legacy_uzs_transactions(self):
  core.set_product_price(self.db,1,1,core.money('2.00'))
  self.db.execute('DELETE FROM meta WHERE key=?',('usd_delivery_backfill_v1',))
  self.db.execute("INSERT INTO events(actor,agent,client,kind,pack,qty,amount,amount_usd,ts) VALUES(2,2,1,'delivery',1,4,0,0,?)",(int(time.time()),))
  self.db.execute("INSERT INTO clients(id,agent,name,phone) VALUES(2,2,'Legacy','+998900000002')")
  self.db.execute("INSERT INTO events(actor,agent,client,kind,pack,qty,amount,amount_usd,ts) VALUES(2,2,2,'delivery',1,4,0,0,?)",(int(time.time()),))
  self.db.execute("INSERT INTO events(actor,agent,client,kind,pack,qty,amount,amount_usd,ts) VALUES(2,2,2,'sold',1,2,100000,0,?)",(int(time.time()),))
  core._backfill_unbilled_deliveries(self.db)
  self.assertEqual(core.client_debt_usd(self.db,1),core.money('8.00'))
  self.assertEqual(core.client_debt_usd(self.db,2),0)
  self.assertEqual(core.legacy_debt_uzs(self.db,2),100000)
  core._backfill_unbilled_deliveries(self.db)
  self.assertEqual(core.client_debt_usd(self.db,1),core.money('8.00'))

 def test_pg_sql_quotes_shift_end_but_preserves_case_end(self):
  q=core._pg_sql("SELECT COALESCE(SUM(CASE WHEN kind='sold' THEN amount ELSE 0 END),0) FROM events")
  self.assertIn("CASE WHEN kind='sold' THEN amount ELSE 0 END",q)
  self.assertNotIn('0 "end"',q)
  q=core._pg_sql("UPDATE shifts SET end=? WHERE agent=? AND end IS NULL")
  self.assertIn('SET "end"=%s',q)
  self.assertIn('AND "end" IS NULL',q)
  q=core._pg_sql("CREATE TABLE shifts(id BIGSERIAL, end BIGINT)")
  self.assertIn('"end" BIGINT',q)

 def test_nonprivate_ignored(self):
  with patch.object(bot,'send') as send:
   bot.handle(self.db,{'update_id':10,'message':{'chat':{'id':-1,'type':'group'},'from':{'id':1},'text':'📍 Агентлар'}})
   send.assert_not_called()

if __name__=='__main__':unittest.main()
