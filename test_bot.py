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
   self.assertIn('Янги админ қўшилди',send.call_args.args[1])
   bot.handle(self.db,msg(15005,123456789,'/start'))
   self.assertIn('Амални танланг',send.call_args.args[1])
   with self.assertRaises(ValueError):
    bot.handle(self.db,msg(15006,123456789,'🔐 Админ қўшиш'))
   self.assertIsNone(self.db.execute('SELECT 1 FROM users WHERE id=123456790').fetchone())


 def test_test_agent_bootstrap_never_downgrades_existing_admin(self):
  uid=1037158726
  self.db.execute('INSERT INTO users(id,role,name) VALUES(?,?,?)',(uid,'admin','Secondary admin'))
  with patch.object(bot,'ADMINS',{1}),patch.object(bot,'TEST_AGENTS',{uid,2,999999}):
   bot.bootstrap_users(self.db)
  self.assertEqual(bot.role(self.db,uid),'admin')
  self.assertEqual(bot.role(self.db,2),'agent')
  self.assertEqual(bot.role(self.db,999999),'agent')
  self.db.execute("UPDATE users SET role='cashier' WHERE id=?",(999999,))
  with patch.object(bot,'ADMINS',{1}),patch.object(bot,'TEST_AGENTS',{uid,999999}):
   bot.bootstrap_users(self.db)
  self.assertEqual(bot.role(self.db,uid),'admin')
  self.assertEqual(bot.role(self.db,999999),'cashier')

 def test_secondary_admin_role_lock_survives_test_agent_bootstrap_and_self_heals(self):
  uid=1037158726
  self.db.execute('INSERT INTO users(id,role,name) VALUES(?,?,?)',(uid,'admin','Offes'))
  with patch.object(bot,'ADMINS',{1}),patch.object(bot,'TEST_AGENTS',{uid,2}):
   bot.bootstrap_users(self.db)
   self.assertEqual(bot.role(self.db,uid),'admin')
   self.assertIsNotNone(self.db.execute('SELECT 1 FROM meta WHERE key=? AND value=?',
                                       (f'secondary_admin:{uid}','1')).fetchone())
   self.db.execute("UPDATE users SET role='agent' WHERE id=?",(uid,))
   self.assertEqual(self.db.execute('SELECT role FROM users WHERE id=?',(uid,)).fetchone()[0],'agent')
   self.assertEqual(bot.role(self.db,uid),'admin')
   self.assertEqual(self.db.execute('SELECT role FROM users WHERE id=?',(uid,)).fetchone()[0],'admin')
   self.db.execute("UPDATE users SET role='agent' WHERE id=?",(uid,))
   bot.bootstrap_users(self.db)
   self.assertEqual(self.db.execute('SELECT role FROM users WHERE id=?',(uid,)).fetchone()[0],'admin')

 def test_existing_disabled_agent_can_be_promoted_to_secondary_admin(self):
  uid=1037158726
  self.db.execute('INSERT INTO users(id,role,name) VALUES(?,?,?)',(uid,'disabled','Эски агент'))
  self.db.execute('INSERT INTO shifts(agent,start,end) VALUES(?,?,?)',(uid,int(time.time())-7200,int(time.time())-3600))
  before=self.db.execute('SELECT COUNT(*) FROM shifts WHERE agent=?',(uid,)).fetchone()[0]
  now=int(time.time())
  def msg(i,t,actor=1):
   return {'update_id':i,'message':{'message_id':i,'date':now,'from':{'id':actor},'chat':{'id':actor,'type':'private'},'text':t}}
  with patch.object(bot,'ADMINS',{1}),patch.object(bot,'send') as send:
   for i,t in enumerate(['🔐 Админ қўшиш',str(uid),'Янги админ','✅ Тасдиқлаш'],15050):
    bot.handle(self.db,msg(i,t))
   self.assertEqual(bot.role(self.db,uid),'admin')
   self.assertEqual(self.db.execute('SELECT name FROM users WHERE id=?',(uid,)).fetchone()[0],'Янги админ')
   self.assertIn('Мавжуд аккаунт админга ўтказилди',send.call_args.args[1])
   self.assertEqual(self.db.execute('SELECT COUNT(*) FROM shifts WHERE agent=?',(uid,)).fetchone()[0],before)
   audit=self.db.execute("SELECT actor,old_id,new_id,action FROM role_audit WHERE new_id=?",(uid,)).fetchone()
   self.assertEqual(tuple(audit),(1,uid,uid,'admin_promoted_from_disabled'))
   self.assertTrue(bot.allowed(self.db,uid,'analytics'))
   self.assertFalse(bot.allowed(self.db,uid,'admin_add'))
   bot.handle(self.db,msg(15060,'/start',actor=uid))
   self.assertIn('🗺 Умумий таҳлил',[x for row in send.call_args.args[2] for x in row])
   with self.assertRaises(ValueError):
    bot.handle(self.db,msg(15061,'🔐 Админ қўшиш',actor=uid))

 def test_existing_agent_with_stock_or_clients_cannot_be_promoted(self):
  with patch.object(bot,'ADMINS',{1}),patch.object(bot,'send'):
   with self.assertRaisesRegex(ValueError,'мижозлар'):
    bot.finish(self.db,1,{'action':'admin_add','values':{'id':2,'name':'Bad promotion'}},15100)
   self.assertEqual(bot.role(self.db,2),'agent')
   self.db.execute('INSERT INTO users(id,role,name) VALUES(?,?,?)',(123456010,'agent','Inventory'))
   core.record(self.db,1,123456010,None,'load',1,5,source=15101)
   with self.assertRaisesRegex(ValueError,'товар қолдиғи'):
    bot.finish(self.db,1,{'action':'admin_add','values':{'id':123456010,'name':'Inventory'}},15102)
   self.assertEqual(bot.role(self.db,123456010),'agent')
   self.db.execute('INSERT INTO users(id,role,name) VALUES(?,?,?)',(123456011,'disabled','Old session'))
   self.db.execute('INSERT INTO shifts(agent,start) VALUES(?,?)',(123456011,int(time.time())-100))
   with self.assertRaisesRegex(ValueError,'очиқ смена'):
    bot.finish(self.db,1,{'action':'admin_add','values':{'id':123456011,'name':'Old session'}},15103)
   self.assertEqual(bot.role(self.db,123456011),'disabled')
   self.assertEqual(self.db.execute('SELECT COUNT(*) FROM role_audit WHERE new_id IN (?,?)',(123456010,123456011)).fetchone()[0],0)

 def test_existing_admin_cannot_be_added_twice_and_secondary_cannot_promote(self):
  with patch.object(bot,'ADMINS',{1}),patch.object(bot,'send'):
   self.db.execute('INSERT INTO users(id,role,name) VALUES(?,?,?)',(550,'admin','Secondary'))
   self.db.execute('INSERT INTO users(id,role,name) VALUES(?,?,?)',(551,'disabled','Disabled'))
   with self.assertRaisesRegex(ValueError,'аллақачон админ'):
    bot.finish(self.db,1,{'action':'admin_add','values':{'id':550,'name':'Duplicate'}},15110)
   with self.assertRaises(ValueError):
    bot.finish(self.db,550,{'action':'admin_add','values':{'id':551,'name':'Unauthorized'}},15111)
   self.assertEqual(bot.role(self.db,551),'disabled')

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

 def test_return_uses_original_delivery_prices_with_allocation(self):
  core.set_product_price(self.db,1,1,core.money('2.00'))
  self.rec('load',12,actor=1)
  core.record(self.db,2,2,1,'delivery',1,4,source=30001,currency='USD')
  core.set_product_price(self.db,1,1,core.money('3.00'))
  core.record(self.db,2,2,1,'delivery',1,4,source=30002,currency='USD')
  self.assertEqual(core.client_debt_usd(self.db,1),core.money('20.00'))
  core.record(self.db,2,2,1,'return',1,5,source=30003,currency='USD')
  self.assertEqual(core.client_debt_usd(self.db,1),core.money('9.00'))
  rows=self.db.execute('SELECT qty,amount_usd FROM return_allocations ORDER BY delivery_event').fetchall()
  self.assertEqual([(x['qty'],x['amount_usd']) for x in rows],[(4,core.money('8.00')),(1,core.money('3.00'))])
  core.record(self.db,2,2,1,'return',1,1,source=30004,currency='USD')
  self.assertEqual(core.client_debt_usd(self.db,1),core.money('6.00'))
  self.assertEqual(sum(x[0] for x in self.db.execute('SELECT qty FROM return_allocations')),6)
  with self.assertRaises(ValueError):
   core.record(self.db,2,2,1,'return',1,3,source=30005,currency='USD')

 def test_sold_goods_cannot_be_credited_as_returned_from_older_usd_lot(self):
  core.set_product_price(self.db,1,1,core.money('2.00'))
  self.rec('load',12,actor=1)
  core.record(self.db,2,2,1,'delivery',1,4,source=44001,currency='USD')
  core.set_product_price(self.db,1,1,core.money('3.00'))
  core.record(self.db,2,2,1,'delivery',1,4,source=44002,currency='USD')
  core.record(self.db,2,2,1,'sold',1,4,source=44003,currency='USD')
  core.record(self.db,2,2,1,'return',1,1,source=44004,currency='USD')
  allocated=self.db.execute(
   'SELECT a.delivery_event,a.qty,a.amount_usd FROM return_allocations a '
   'JOIN events e ON e.id=a.delivery_event WHERE a.return_event=(SELECT id FROM events WHERE source=44004)'
  ).fetchone()
  newer=self.db.execute('SELECT id FROM events WHERE source=44002').fetchone()[0]
  self.assertEqual(tuple(allocated),(newer,1,core.money('3.00')))
  self.assertEqual(core.client_debt_usd(self.db,1),core.money('17.00'))
  core.record(self.db,2,2,1,'return',1,2,source=44005,currency='USD')
  self.assertEqual(core.client_debt_usd(self.db,1),core.money('11.00'))

 def test_request_logs_redact_webhook_and_signed_map_links(self):
  webhook='POST /telegram/abcdefABCDEF123456 HTTP/1.1'
  self.assertNotIn('abcdefABCDEF123456',bot.redact_access_log_arg(webhook))
  signature='a'*32
  paths=[
   'GET /map/overall/1789967211/'+signature+' HTTP/1.1',
   'GET /map/agent/123456/1789967211/'+signature+' HTTP/1.1'
  ]
  for path in paths:
   self.assertNotIn(signature,bot.redact_access_log_arg(path))
   self.assertNotIn('1789967211',bot.redact_access_log_arg(path))

 def test_access_log_formatting_keeps_integer_placeholders(self):
  self.assertEqual(
   bot.format_access_log('code %d, message %s',501,"Unsupported method ('HEAD')"),
   "code 501, message Unsupported method ('HEAD')"
  )
  raw='GET /map/agent/123456/1789967211/'+'a'*32+' HTTP/1.1'
  self.assertNotIn('1789967211',bot.format_access_log('"%s" %s %s',raw,200,'-'))
  source=__import__('inspect').getsource(bot.serve_webhook)
  self.assertIn('def do_HEAD(self):',source)

 def test_failed_update_is_persisted_for_admin_review(self):
  up={'update_id':30010,'message':{'from':{'id':2}}}
  with patch.object(bot,'send') as send:
   self.assertEqual(bot._register_failure(self.db,30010,RuntimeError('boom'),up),1)
   self.assertEqual(bot._register_failure(self.db,30010,RuntimeError('boom'),up),2)
   self.assertEqual(bot._register_failure(self.db,30010,RuntimeError('boom'),up),3)
   bot._skip_failed_update(self.db,30010,RuntimeError('boom'))
   row=self.db.execute('SELECT actor,attempts,status FROM failed_updates WHERE update_id=30010').fetchone()
   self.assertEqual(tuple(row),(2,3,'skipped'))
   self.assertIsNotNone(self.db.execute('SELECT 1 FROM processed WHERE id=30010').fetchone())
   msg={'update_id':30011,'message':{'message_id':30011,'date':int(time.time()),'from':{'id':1},'chat':{'id':1,'type':'private'},'text':'/failed'}}
   bot.handle(self.db,msg)
   self.assertIn('30010',send.call_args.args[1])
   self.assertIn('skipped',send.call_args.args[1])

 def test_transfer_account_preserves_balances_and_disables_old_id(self):
  self.rec('load',10,actor=1)
  core.set_product_price(self.db,1,1,core.money('2.00'))
  core.record(self.db,2,2,1,'delivery',1,4,source=30101,currency='USD')
  core.record(self.db,2,2,1,'payment',value=core.money('1.00'),source=30102,currency='USD')
  core.set_agent_feature(self.db,1,2,'order',False)
  with patch.object(bot,'ADMINS',{1}),patch.object(bot,'send'):
   bot.finish(self.db,1,{'action':'agent_transfer','values':{'agent':2,'id':123456999}},30103)
  self.assertEqual(bot.role(self.db,2),'disabled')
  self.assertEqual(bot.role(self.db,123456999),'agent')
  self.assertEqual(self.db.execute('SELECT agent FROM clients WHERE id=1').fetchone()[0],123456999)
  self.assertEqual(core.agent_stock(self.db,123456999,1),6)
  self.assertEqual(core.client_debt_usd(self.db,1),core.money('7.00'))
  self.assertEqual(core.cash_usd(self.db,123456999),core.money('1.00'))
  self.assertFalse(core.feature_enabled(self.db,123456999,'order'))
  self.assertEqual(self.db.execute('SELECT action FROM role_audit WHERE old_id=2 AND new_id=123456999').fetchone()[0],'agent_transfer')
  self.assertFalse(bot.allowed(self.db,2,'delivery'))
  with patch.object(bot,'send') as send:
   msg={'update_id':30104,'message':{'message_id':30104,'date':int(time.time()),'from':{'id':2},'chat':{'id':2,'type':'private'},'text':'/start'}}
   bot.handle(self.db,msg)
   self.assertIn('ёпилган',send.call_args.args[1])

 def test_transfer_denied_if_shift_open_or_destination_registered(self):
  with patch.object(bot,'ADMINS',{1}),patch.object(bot,'send'):
   with self.assertRaises(ValueError):
    bot.finish(self.db,1,{'action':'agent_transfer','values':{'agent':2,'id':4}},30200)
   self.db.execute('INSERT INTO shifts(agent,start) VALUES(2,?)',(int(time.time()),))
   with self.assertRaises(ValueError):
    bot.finish(self.db,1,{'action':'agent_transfer','values':{'agent':2,'id':123456998}},30201)
   self.assertEqual(bot.role(self.db,2),'agent')
   self.assertIsNone(self.db.execute('SELECT role FROM users WHERE id=123456998').fetchone())

 def test_http_server_selection_matches_database_backend(self):
  self.assertIsInstance(self.db,core.sqlite3.Connection)
  from http.server import HTTPServer,ThreadingHTTPServer
  self.assertFalse(isinstance(self.db,core.PostgresDB))
  self.assertIsNot(HTTPServer,ThreadingHTTPServer)
  self.assertIn('ThreadingHTTPServer if postgres else HTTPServer',
                __import__('inspect').getsource(bot.serve_webhook))
  self.assertIn('return connect(database_url,initialize=False) if postgres else db',
                __import__('inspect').getsource(bot.serve_webhook))

 def test_admin_can_open_all_customer_map_and_agent_link_routes_match(self):
  import ast,inspect,re
  core.set_product_price(self.db,1,1,core.money('2.00'))
  core.record(self.db,1,2,None,'load',1,10,currency='USD')
  core.record(self.db,2,2,1,'delivery',1,3,currency='USD')
  def msg(i,u,txt):
   return {'update_id':i,'message':{'message_id':i,'date':int(time.time()),
      'from':{'id':u},'chat':{'id':u,'type':'private'},'text':txt}}
  with patch.object(bot,'ADMINS',{1}),patch.dict(bot.os.environ,{'WEBHOOK_BASE_URL':'https://example.test'}),patch.object(bot,'send'),patch.object(bot,'send_inline') as inline:
   self.assertTrue(bot.allowed(self.db,1,'agent_clients_map'))
   self.assertTrue(bot.allowed(self.db,2,'agent_clients_map'))
   self.assertFalse(bot.allowed(self.db,3,'agent_clients_map'))
   self.assertIn('🗺 Мижозлар харитаси',[x for row in bot.menu(self.db,1) for x in row])
   bot.handle(self.db,msg(987001,1,'🗺 Мижозлар харитаси'))
   admin_url=inline.call_args.args[2][0][1]
   self.assertIn('/map/admin-clients/1/',admin_url)
   self.assertNotIn('start=',admin_url)
   bot.handle(self.db,msg(987002,2,'🗺 Мижозлар харитаси'))
   agent_url=inline.call_args.args[2][0][1]
   self.assertIn('/map/agent-clients/2/',agent_url)
   source=ast.parse(inspect.getsource(bot.serve_webhook))
   patterns=[n.value for n in ast.walk(source) if isinstance(n,ast.Constant)
             and isinstance(n.value,str) and '/map/' in n.value
             and ('admin-clients/' in n.value or 'agent-clients/' in n.value)
             and n.value.startswith('/map/')]
   self.assertEqual(len(patterns),2)
   self.assertTrue(any(re.fullmatch(p,admin_url.replace('https://example.test','')) for p in patterns))
   self.assertTrue(any(re.fullmatch(p,agent_url.replace('https://example.test','')) for p in patterns))
   self.assertFalse(bot._map_valid('admin-clients/2',admin_url.split('/')[-2],admin_url.split('/')[-1]))

 def test_agent_customer_map_link_and_signed_payment_return(self):
  core.set_product_price(self.db,1,1,core.money('2.00'))
  core.record(self.db,1,2,None,'load',1,10,currency='USD')
  core.record(self.db,2,2,1,'delivery',1,4,currency='USD')
  now=int(time.time())
  self.db.execute('INSERT INTO shifts(agent,start) VALUES(2,?)',(now-10,))
  core.point(self.db,2,{'message_id':99701,'date':now,
      'location':{'latitude':40,'longitude':71,'live_period':3600}})
  def msg(i,uid,txt):
   return {'update_id':i,'message':{'message_id':i,'date':int(time.time()),
      'from':{'id':uid},'chat':{'id':uid,'type':'private'},'text':txt}}
  with patch.object(bot,'BOT_USERNAME','asman_agent_test_bot'),patch.dict(bot.os.environ,{'WEBHOOK_BASE_URL':'https://example.test'}),patch.object(bot,'send'),patch.object(bot,'send_inline') as inline:
   self.assertIn('🗺 Мижозлар харитаси',[x for row in bot.menu(self.db,2) for x in row])
   self.assertNotIn('🗺 Мижозлар харитаси',[x for row in bot.menu(self.db,4) for x in row] if not core.feature_enabled(self.db,4,'clients') else [])
   bot.handle(self.db,msg(99702,2,'🗺 Мижозлар харитаси'))
   self.assertIn('/map/agent-clients/2/',inline.call_args.args[2][0][1])
   self.assertNotIn('token=',inline.call_args.args[2][0][1])
   payload=bot.agent_action_payload('p',2,1)
   self.assertLessEqual(len(payload),64)
   with self.assertRaises(ValueError):bot.handle(self.db,msg(99703,4,'/start '+payload))
   with self.assertRaises(ValueError):bot.handle(self.db,msg(99704,2,'/start '+payload[:-1]+'0' if payload[-1]!='0' else '/start '+payload[:-1]+'1'))
   with self.assertRaises(ValueError):bot.handle(self.db,msg(99705,2,'/start '+bot.agent_action_payload('p',2,1,ttl=-10)))
   bot.handle(self.db,msg(99706,2,'/start '+payload))
   self.assertEqual(bot.state(self.db,2)['values']['client'],1)
   self.assertEqual(bot.state(self.db,2)['action'],'payment')
   for i,t in enumerate(['3.00','✅ Тасдиқлаш'],99707):bot.handle(self.db,msg(i,2,t))
   self.assertEqual(core.client_debt_usd(self.db,1),core.money('5.00'))
   self.assertEqual(core.cash_usd(self.db,2),core.money('3.00'))
   bot.handle(self.db,msg(99709,2,'/start '+bot.agent_action_payload('r',2,1)))
   self.assertEqual(bot.state(self.db,2)['action'],'return')
   self.assertEqual(bot.state(self.db,2)['values']['client'],1)
   for i,t in enumerate(['Грунтовка 7/1 — 1 кг','Дона','1','✅ Тасдиқлаш'],99710):
    bot.handle(self.db,msg(i,2,t))
   self.assertEqual(core.client_stock(self.db,2,1,1),3)
   self.assertEqual(core.client_debt_usd(self.db,1),core.money('3.00'))
   core.set_agent_feature(self.db,1,2,'payment',False)
   with self.assertRaises(ValueError):bot.handle(self.db,msg(99715,2,'/start '+bot.agent_action_payload('p',2,1)))

 def test_customer_map_transactions_require_fresh_gps_at_confirmation(self):
  core.set_product_price(self.db,1,1,core.money('2.00'))
  core.record(self.db,1,2,None,'load',1,3,currency='USD')
  core.record(self.db,2,2,1,'delivery',1,2,currency='USD')
  now=int(time.time())
  self.db.execute('INSERT INTO shifts(agent,start) VALUES(2,?)',(now-10,))
  core.point(self.db,2,{'message_id':99720,'date':now,
      'location':{'latitude':40,'longitude':71,'live_period':3600}})
  def msg(i,txt):return {'update_id':i,'message':{'message_id':i,'date':int(time.time()),
           'from':{'id':2},'chat':{'id':2,'type':'private'},'text':txt}}
  with patch.object(bot,'send'):
   bot.handle(self.db,msg(99721,'/start '+bot.agent_action_payload('p',2,1)))
   bot.handle(self.db,msg(99722,'1.00'))
   self.db.execute('UPDATE shifts SET end=? WHERE agent=2 AND end IS NULL',(now,))
   with self.assertRaises(ValueError):bot.handle(self.db,msg(99723,'✅ Тасдиқлаш'))
  self.assertEqual(core.cash_usd(self.db,2),0)
  self.assertEqual(core.client_debt_usd(self.db,1),core.money('4.00'))

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
  self.rec('load',25,actor=1)
  now=int(time.time())
  self.db.execute('INSERT INTO shifts(agent,start) VALUES(2,?)',(now-10,))
  self.assertTrue(core.point(self.db,2,{'message_id':90,'date':now,'location':{'latitude':40,'longitude':71,'live_period':3600}}))
  def msg(i,t):return {'update_id':i,'message':{'message_id':i,'date':int(time.time()),'from':{'id':2},'chat':{'id':2,'type':'private'},'text':t}}
  with patch.object(bot,'send'):
   for i,t in enumerate(['📦 Товар бериш','1 · Мижоз','1','Блок','2'],100):bot.handle(self.db,msg(i,t))
   self.assertEqual(core.agent_stock(self.db,2,1),25)
   bot.handle(self.db,msg(105,'✅ Тасдиқлаш'))
   self.assertEqual(core.agent_stock(self.db,2,1),5)
   bot.handle(self.db,msg(106,'✅ Тасдиқлаш'))
   self.assertEqual(core.agent_stock(self.db,2,1),5)
 def test_client_onboarding_location_first_and_delivery(self):
  core.set_product_price(self.db,1,1,core.money('2.00'))
  self.rec('load',25,actor=1)
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
   bot.handle(self.db,msg(202,photo='photo-file-id'))
   bot.handle(self.db,msg(203,'+998901234567, +998911234567 / +998931234567'))
   bot.handle(self.db,msg(204,'Алишер'))
   bot.handle(self.db,msg(205,'ASMAN SHOP'))
   bot.handle(self.db,msg(206,'Қўқон, Марказ'))
   bot.handle(self.db,msg(207,'1 кг грунтовкадан кўпроқ олишни хоҳлади'))
   bot.handle(self.db,msg(208,'2026-09-25'))
   bot.handle(self.db,msg(209,'1'))
   bot.handle(self.db,msg(210,'Блок'))
   bot.handle(self.db,msg(211,'2'))
   bot.handle(self.db,msg(212,'✅ Тасдиқлаш'))
  row=self.db.execute("SELECT name,shop_name,phone,address,photo,comment,payment_due FROM clients WHERE name='Алишер'").fetchone()
  self.assertEqual((row['name'],row['shop_name'],row['phone'],row['address']),
                   ('Алишер','ASMAN SHOP','+998901234567 / +998911234567 / +998931234567','Қўқон, Марказ'))
  self.assertEqual(row['photo'],'photo-file-id')
  self.assertIn('грунтовка',row['comment'])
  self.assertEqual(row['payment_due'],'2026-09-25')
  cid=self.db.execute("SELECT id FROM clients WHERE name='Алишер'").fetchone()[0]
  self.assertEqual(core.client_stock(self.db,2,cid,1),20)
  self.assertEqual(core.agent_stock(self.db,2,1),5)

 def test_parse_one_to_three_phone_numbers(self):
  self.assertEqual(bot.parse_phones('90 123-45-67'),['+998901234567'])
  self.assertEqual(bot.parse_phones('+998 90 123 45 67 / 998911234567'),
                   ['+998901234567','+998911234567'])
  self.assertEqual(bot.parse_phones('+998901234567, +998911234567\n+998931234567'),
                   ['+998901234567','+998911234567','+998931234567'])
  with self.assertRaisesRegex(ValueError,'3 та'):
   bot.parse_phones('+998901234567,+998911234567,+998931234567,+998941234567')

 def test_block_pack_sizes_and_multi_product_same_client(self):
  for pack,mult in ((1,10),(3,6),(5,2)):
   self.assertEqual(core.units_per_block(pack),mult)
   core.set_product_price(self.db,1,pack,core.money(str(pack)))
   core.record(self.db,1,2,None,'load',pack,mult)
  now=int(time.time())
  self.db.execute('INSERT INTO shifts(agent,start) VALUES(2,?)',(now-10,))
  self.assertTrue(core.point(self.db,2,{'message_id':540,'date':now,'location':{'latitude':40,'longitude':71,'live_period':3600}}))
  def msg(i,text):
   return {'update_id':i,'message':{'message_id':i,'date':now,'from':{'id':2},'chat':{'id':2,'type':'private'},'text':text}}
  with patch.object(bot,'send') as send:
   for n,t in enumerate(['📦 Товар бериш','1','Грунтовка 7/1 — 1 кг','Блок','1'],541):
    bot.handle(self.db,msg(n,t))
   self.assertEqual(core.client_stock(self.db,2,1,1),0)
   self.assertIn('➕ Яна маҳсулот қўшиш',[x for row in send.call_args.args[2] for x in row])
   bot.handle(self.db,msg(550,'➕ Яна маҳсулот қўшиш'))
   self.assertEqual(bot.state(self.db,2)['values']['client'],1)
   self.assertEqual(bot.state(self.db,2)['step'],1)
   bot.handle(self.db,msg(551,'Грунтовка 7/1 — 3 кг'))
   self.assertIn('1 блок = 6 дона',send.call_args.args[1])
   for n,t in enumerate(['Блок','1'],552):bot.handle(self.db,msg(n,t))
   self.assertEqual(core.client_stock(self.db,2,1,3),0)
   bot.handle(self.db,msg(560,'➕ Яна маҳсулот қўшиш'))
   bot.handle(self.db,msg(561,'Грунтовка 7/1 — 5 кг'))
   self.assertIn('1 блок = 2 дона',send.call_args.args[1])
   for n,t in enumerate(['Блок','1'],562):bot.handle(self.db,msg(n,t))
   self.assertEqual(core.client_stock(self.db,2,1,5),0)
   bot.handle(self.db,msg(570,'✅ Тасдиқлаш'))
   self.assertEqual(core.client_stock(self.db,2,1,1),10)
   self.assertEqual(core.client_stock(self.db,2,1,3),6)
   self.assertEqual(core.client_stock(self.db,2,1,5),2)
   self.assertEqual(core.client_debt_usd(self.db,1),core.money('38.00'))
  for pack in (1,3,5):
   self.assertEqual(core.agent_stock(self.db,2,pack),0)

 def test_client_photo_is_sent_with_customer_card(self):
  self.db.execute("UPDATE clients SET photo='tg-photo-file-id' WHERE id=1")
  with patch.object(bot,'send') as send,patch.object(bot,'api') as api:
   bot.report_clients(self.db,2)
   self.assertIn('мижозни танланг',send.call_args.args[1])
   bot.show_client_card(self.db,2,1)
   self.assertIn('МИЖОЗ #1',send.call_args.args[1])
  api.assert_called_once()
  self.assertEqual(api.call_args.args[0],'sendPhoto')
  self.assertEqual(api.call_args.kwargs['photo'],'tg-photo-file-id')

 def test_period_analytics_selector_and_signed_map_links(self):
  now=int(time.time())
  def msg(i,t,uid=1):
   return {'update_id':i,'message':{'message_id':i,'date':now,'from':{'id':uid},'chat':{'id':uid,'type':'private'},'text':t}}
  with patch.object(bot,'send') as send,patch.object(bot,'send_inline') as inline,\
       patch.object(bot.reports,'overall',return_value=('ҲИСОБОТ',b'<html></html>')) as overall,\
       patch.object(bot,'map_link',return_value='https://example.test/period') as link:
   bot.handle(self.db,msg(61001,'🗺 Умумий таҳлил'))
   options=[x for row in send.call_args.args[2] for x in row]
   self.assertIn('📅 1 кунлик таҳлил',options)
   self.assertIn('📅 1 ҳафталик таҳлил',options)
   self.assertIn('📅 1 ойлик таҳлил',options)
   for i,label,period in [(61002,'📅 1 кунлик таҳлил','day'),
                          (61003,'📅 1 ҳафталик таҳлил','week'),
                          (61004,'📅 1 ойлик таҳлил','month')]:
    bot.handle(self.db,msg(i,label))
    self.assertEqual(overall.call_args.kwargs['period'],period)
    self.assertEqual(link.call_args.args[0],'overall/'+period)
    self.assertIn('ҲИСОБОТ',send.call_args.args[1])
    self.assertTrue(inline.called)
   self.assertFalse(bot.allowed(self.db,2,'analytics_week'))
  with patch.dict(bot.os.environ,{'RENDER_EXTERNAL_URL':'https://example.test'}):
   url=bot.map_link('overall/week')
   expires,sig=url.split('/')[-2:]
   self.assertTrue(bot._map_valid('overall/week',expires,sig))
   self.assertFalse(bot._map_valid('overall/month',expires,sig))
   self.assertNotIn(sig,bot.redact_access_log_arg('GET '+url+' HTTP/1.1'))


 def test_all_agents_see_every_customer_in_clients_section_only(self):
  self.db.execute("INSERT INTO clients(id,agent,name,phone,shop_name,address) VALUES(42,4,'Бошқа мижоз','+998900000042','Бошқа дўкон','Фарғона')")
  now=int(time.time())
  def msg(i,t,uid=2):
   return {'update_id':i,'message':{'message_id':i,'date':now,'from':{'id':uid},'chat':{'id':uid,'type':'private'},'text':t}}
  with patch.object(bot,'send') as send:
   bot.handle(self.db,msg(89001,'👥 Мижозлар',uid=2))
   choices=' '.join(str(v) for row in send.call_args.args[2] for v in row)
   self.assertIn('1 ·',choices)
   self.assertIn('42 ·',choices)
   bot.handle(self.db,msg(89002,'42',uid=2))
   self.assertIn('МИЖОЗ #42',send.call_args.args[1])
   self.assertIn('Бириктирилган агент: D',send.call_args.args[1])
   self.assertNotIn('✏️ Мижоз маълумотини ўзгартириш',
                    [v for row in send.call_args.args[2] for v in row])
   with self.assertRaises(ValueError):
    bot.show_client_edit_fields(self.db,2,42)
   self.assertEqual(bot.role(self.db,2),'agent')
   bot.handle(self.db,msg(89003,'⬅️ Мижозлар',uid=2))
   bot.handle(self.db,msg(89004,'Бошқа',uid=2))
   options=' '.join(str(v) for row in send.call_args.args[2] for v in row)
   self.assertIn('42 ·',options)
   self.assertNotIn('1 ·',options)
   bot.handle(self.db,msg(89005,'42',uid=2))
   self.assertIn('МИЖОЗ #42',send.call_args.args[1])
   bot.handle(self.db,msg(89006,'👥 Мижозлар',uid=4))
   options=' '.join(str(v) for row in send.call_args.args[2] for v in row)
   self.assertIn('1 ·',options)
   self.assertIn('42 ·',options)
   bot.handle(self.db,msg(89007,'1',uid=4))
   self.assertIn('МИЖОЗ #1',send.call_args.args[1])
   self.assertNotIn('✏️ Мижоз маълумотини ўзгартириш',
                    [v for row in send.call_args.args[2] for v in row])
   bot.handle(self.db,msg(89008,'👥 Мижозлар',uid=1))
   bot.handle(self.db,msg(89009,'42',uid=1))
   self.assertIn('✏️ Мижоз маълумотини ўзгартириш',
                 [v for row in send.call_args.args[2] for v in row])

 def test_clients_section_paginates_without_hiding_older_customers(self):
  rows=[(i,4,f'Мижоз {i}',f'+99890{i:07d}',f'Дўкон {i}') for i in range(10,55)]
  self.db.executemany('INSERT INTO clients(id,agent,name,phone,shop_name) VALUES(?,?,?,?,?)',rows)
  now=int(time.time())
  def msg(i,t):
   return {'update_id':i,'message':{'message_id':i,'date':now,'from':{'id':2},'chat':{'id':2,'type':'private'},'text':t}}
  with patch.object(bot,'send') as send:
   bot.handle(self.db,msg(89100,'👥 Мижозлар'))
   first=' '.join(str(v) for row in send.call_args.args[2] for v in row)
   self.assertIn('54 ·',first);self.assertNotIn('10 ·',first)
   self.assertIn('Кейинги 20 ➡️',first)
   self.assertIn('Жами 46 та мижоз · 1–20',send.call_args.args[1])
   bot.handle(self.db,msg(89101,'Кейинги 20 ➡️'))
   second=' '.join(str(v) for row in send.call_args.args[2] for v in row)
   self.assertIn('34 ·',second);self.assertNotIn('54 ·',second)
   self.assertIn('⬅️ Олдинги 20',second);self.assertIn('Кейинги 20 ➡️',second)
   bot.handle(self.db,msg(89102,'Кейинги 20 ➡️'))
   third=' '.join(str(v) for row in send.call_args.args[2] for v in row)
   self.assertIn('10 ·',third);self.assertIn('1 ·',third)
   self.assertNotIn('Кейинги 20 ➡️',third)

 def test_cross_agent_financial_flows_remain_restricted(self):
  self.db.execute("INSERT INTO clients(id,agent,name,phone,shop_name) VALUES(42,4,'Бошқа мижоз','+998900000042','Бошқа дўкон')")
  with patch.object(bot,'send') as send:
   bot.prompt(self.db,2,{'action':'delivery','step':0,'values':{}})
   choices=' '.join(str(v) for row in send.call_args.args[2] for v in row)
   self.assertIn('1 ·',choices)
   self.assertNotIn('42 ·',choices)
   now=int(time.time())
   msg={'update_id':89010,'message':{'message_id':89010,'date':now,'from':{'id':2},'chat':{'id':2,'type':'private'},'text':'42'}}
   with self.assertRaises(ValueError):
    bot.handle(self.db,msg)
   self.assertIsNone(self.db.execute('SELECT 1 FROM events WHERE client=42').fetchone())
  core.set_agent_feature(self.db,1,2,'clients',False)
  with self.assertRaises(ValueError):bot.report_clients(self.db,2)
  with self.assertRaises(ValueError):bot.show_client_card(self.db,2,42)

 def test_client_selection_edit_and_photo_preserve_accounting(self):
  core.record(self.db,1,2,None,'load',1,5)
  core.set_product_price(self.db,1,1,core.money('2.00'))
  core.record(self.db,2,2,1,'delivery',1,2,source=87001,currency='USD')
  now=int(time.time())
  def msg(i,text=None,uid=2,photo=None,location=None):
   m={'message_id':i,'date':now,'from':{'id':uid},'chat':{'id':uid,'type':'private'}}
   if text is not None:m['text']=text
   if photo is not None:m['photo']=[{'file_id':photo}]
   if location is not None:m['location']=location
   return {'update_id':i,'message':m}
  initial=core.client_debt_usd(self.db,1)
  with patch.object(bot,'send') as send,patch.object(bot,'api') as api:
   bot.handle(self.db,msg(87010,'👥 Мижозлар'))
   self.assertIn('мижозни танланг',send.call_args.args[1])
   bot.handle(self.db,msg(87011,'1'))
   self.assertIn('МИЖОЗ #1',send.call_args.args[1])
   bot.handle(self.db,msg(87012,'✏️ Мижоз маълумотини ўзгартириш'))
   bot.handle(self.db,msg(87013,'🏪 Дўкон номи'))
   bot.handle(self.db,msg(87014,'Янги дўкон'))
   self.assertIn('Тасдиқлайсизми?',send.call_args.args[1])
   self.assertEqual(self.db.execute('SELECT shop_name FROM clients WHERE id=1').fetchone()[0],'Тест дўкон')
   bot.handle(self.db,msg(87015,'✅ Ўзгаришни сақлаш'))
   self.assertEqual(self.db.execute('SELECT shop_name FROM clients WHERE id=1').fetchone()[0],'Янги дўкон')
   self.assertIn('Янги дўкон',send.call_args_list[-1].args[1])
   bot.handle(self.db,msg(87016,'✏️ Мижоз маълумотини ўзгартириш'))
   bot.handle(self.db,msg(87017,'📷 Фото'))
   bot.handle(self.db,msg(87018,photo='new-telegram-file-id'))
   bot.handle(self.db,msg(87019,'✅ Ўзгаришни сақлаш'))
   self.assertEqual(self.db.execute('SELECT photo FROM clients WHERE id=1').fetchone()[0],'new-telegram-file-id')
   self.assertTrue(any(call.args[0]=='sendPhoto' for call in api.call_args_list))
   bot.handle(self.db,msg(87020,'✏️ Мижоз маълумотини ўзгартириш'))
   bot.handle(self.db,msg(87021,'📍 Дўкон локацияси'))
   bot.handle(self.db,msg(87022,location={'latitude':40.55,'longitude':71.55}))
   bot.handle(self.db,msg(87023,'✅ Ўзгаришни сақлаш'))
   point=self.db.execute('SELECT lat,lon FROM clients WHERE id=1').fetchone()
   self.assertEqual(tuple(point),(40.55,71.55))
  self.assertEqual(core.client_debt_usd(self.db,1),initial)
  self.assertEqual(core.client_stock(self.db,2,1,1),2)
  audited=self.db.execute('SELECT field FROM client_edits WHERE client=1 ORDER BY id').fetchall()
  self.assertEqual([x[0] for x in audited],['shop_name','photo','lat','lon'])

 def test_client_edit_guards_agent_scope_and_duplicate_phone(self):
  self.db.execute("INSERT INTO clients(id,agent,name,phone) VALUES(20,4,'Бошқа мижоз','+998901234567')")
  with self.assertRaises(ValueError):core.edit_client(self.db,2,20,{'name':'Чет мижоз'})
  with self.assertRaises(ValueError):core.edit_client(self.db,2,1,{'agent':4})
  with self.assertRaises(ValueError):
   core.edit_client(self.db,2,1,{'phone':'+998901234567'})
  self.assertEqual(self.db.execute('SELECT phone FROM clients WHERE id=1').fetchone()[0],'+998900000001')
  self.assertEqual(self.db.execute('SELECT COUNT(*) FROM client_edits').fetchone()[0],0)

 def test_agent_add_then_deactivate_preserves_all_existing_records(self):
  now=int(time.time())
  def msg(i,t,uid=1):
   return {'update_id':i,'message':{'message_id':i,'date':now,'from':{'id':uid},'chat':{'id':uid,'type':'private'},'text':t}}
  with patch.object(bot,'ADMINS',{1}),patch.object(bot,'send') as send:
   bot.handle(self.db,msg(87101,'👥 Агентлар бошқаруви'))
   self.assertIn('➕ Агент қўшиш',[x for row in send.call_args.args[2] for x in row])
   for i,t in enumerate(['➕ Агент қўшиш','123456789','Янги агент','✅ Тасдиқлаш'],87102):
    bot.handle(self.db,msg(i,t))
   self.assertEqual(bot.role(self.db,123456789),'agent')
   self.assertIn('қўшилди',send.call_args.args[1])
   core.record(self.db,1,123456789,None,'load',1,10,source=87110)
   self.db.execute("INSERT INTO clients(id,agent,name,phone) VALUES(30,123456789,'Client','+998900000030')")
   core.set_product_price(self.db,1,1,core.money('2.00'))
   core.record(self.db,123456789,123456789,30,'delivery',1,2,source=87111,currency='USD')
   debt=core.client_debt_usd(self.db,30)
   self.db.execute('INSERT INTO shifts(agent,start) VALUES(?,?)',(123456789,now-5))
   with self.assertRaises(ValueError):core.deactivate_agent(self.db,1,123456789)
   self.db.execute('UPDATE shifts SET end=? WHERE agent=?',(now,123456789))
   for i,t in enumerate(['🗑 Агент ҳисобини ёпиш','123456789','✅ Тасдиқлаш'],87120):
    bot.handle(self.db,msg(i,t))
   self.assertEqual(bot.role(self.db,123456789),'disabled')
   self.assertFalse(bot.allowed(self.db,123456789,'delivery'))
   self.assertEqual(core.client_debt_usd(self.db,30),debt)
   self.assertEqual(core.agent_stock(self.db,123456789,1),8)
   self.assertEqual(self.db.execute('SELECT agent FROM clients WHERE id=30').fetchone()[0],123456789)
   self.assertEqual(self.db.execute("SELECT action FROM role_audit WHERE old_id=123456789").fetchone()[0],'agent_deactivated')
   bot.handle(self.db,msg(87130,'/start',uid=123456789))
   self.assertIn('ёпилган',send.call_args.args[1])
  with patch.object(bot,'ADMINS',{1}):
   self.db.execute("INSERT INTO users(id,role,name) VALUES(500,'admin','Иккинчи админ')")
   self.assertFalse(bot.allowed(self.db,500,'agent_deactivate'))
   self.assertTrue(bot.allowed(self.db,500,'agent_add'))

 def test_reconcile_menu_is_all_time_and_summary_button_removed(self):
  self.assertNotIn('📋 Умумий ҳисоб',[x for row in bot.menu(self.db,1) for x in row])
  self.assertEqual([x[0] for x in bot.FLOW['reconcile_client_pdf']],['client'])
  admin_menu=[x for row in bot.menu(self.db,1) for x in row]
  agent_menu=[x for row in bot.menu(self.db,2) for x in row]
  self.assertIn('📄 Акт сверка',admin_menu);self.assertIn('📄 Акт сверка',agent_menu)
  self.assertNotIn('📊 Барча мижозлар — Excel',admin_menu)
  self.assertNotIn('📄 Барча мижозлар — PDF',agent_menu)
  self.assertTrue(bot.allowed(self.db,2,'reconcile_all_xlsx'))
  self.assertTrue(bot.allowed(self.db,2,'reconcile_all_pdf'))
  self.assertFalse(bot.allowed(self.db,1,'summary'))
  self.assertEqual(core.units_per_block(1),10)
  self.assertEqual(core.units_per_block(3),6)
  self.assertEqual(core.units_per_block(5),2)

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

 def test_customer_card_links_are_scoped_expiring_and_redacted(self):
  from urllib.parse import urlparse
  import inspect
  with patch.object(bot,'TOKEN','local-test-token'),patch.dict(bot.os.environ,{'RENDER_EXTERNAL_URL':'https://example.test','WEBHOOK_BASE_URL':''}):
   for scope in ('client/1','client-photo/1'):
    url=bot.map_link(scope)
    path=urlparse(url).path
    expires,signature=path.split('/')[-2:]
    self.assertTrue(bot._map_valid(scope,expires,signature))
    self.assertFalse(bot._map_valid('client/2',expires,signature))
    self.assertFalse(bot._map_valid('client-photo/2',expires,signature))
    self.assertFalse(bot._map_valid(scope,expires,signature,int(expires)+1))
    self.assertNotIn(signature,bot.redact_access_log_arg('GET '+path+' HTTP/1.1'))
    self.assertNotIn(expires,bot.redact_access_log_arg('GET '+path+' HTTP/1.1'))
    self.assertTrue(path.startswith('/map/client/') or path.startswith('/map/client-photo/'))
   source=inspect.getsource(bot.serve_webhook)
   self.assertIn('reports.client_card_html(local,actor,cid,photo_url=photo_url)',source)
   self.assertIn('photo_data=customer_photo_bytes',source)

 def test_customer_photo_proxy_validates_telegram_file(self):
  import io
  jpeg=bytes([255,216,255])+b'test-image'
  with patch.object(bot,'TOKEN','local-test-token'),patch.object(bot,'api',return_value={'file_path':'photos/file_12.jpg','file_size':len(jpeg)}) as api,patch.object(bot.urllib.request,'urlopen',return_value=io.BytesIO(jpeg)) as urlopen:
   self.assertEqual(bot.customer_photo_bytes('telegram-file-id'),jpeg)
   api.assert_called_once_with('getFile',file_id='telegram-file-id')
   self.assertIn('/file/botlocal-test-token/photos/file_12.jpg',urlopen.call_args.args[0])
  with patch.object(bot,'api',return_value={'file_path':'../secret.txt','file_size':3}):
   with self.assertRaises(ValueError):bot.customer_photo_bytes('bad-file')
  with patch.object(bot,'api',return_value={'file_path':'photos/file_1.jpg','file_size':8_000_001}):
   with self.assertRaises(ValueError):bot.customer_photo_bytes('large-file')

 def test_map_links_expire(self):
  with patch.dict(bot.os.environ,{'RENDER_EXTERNAL_URL':'https://example.test'},clear=False),patch.object(bot.time,'time',return_value=2_000_000_000):
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
   for i,t in enumerate(['📄 Акт сверка','👤 Битта мижоз — PDF','1','✅ Тасдиқлаш'],730):bot.handle(self.db,dmsg(i,t))
   document.assert_called_once()
   self.assertEqual(document.call_args.args[1],'ASMAN-mijoz-1-akt-sverka.pdf')

 def test_back_button_preserves_previous_client_data(self):
  self.rec('load',12,actor=1)
  now=int(time.time());self.db.execute('INSERT INTO shifts(agent,start) VALUES(2,?)',(now-10,))
  self.assertTrue(core.point(self.db,2,{'message_id':800,'date':now,'location':{'latitude':40,'longitude':71,'live_period':3600}}))
  def msg(i,text=None,loc=None,photo=None):
   m={'message_id':i,'date':int(time.time()),'from':{'id':2},'chat':{'id':2,'type':'private'}}
   if text is not None:m['text']=text
   if loc is not None:m['location']=loc
   if photo is not None:m['photo']=[{'file_id':photo}]
   return {'update_id':i,'message':m}
  with patch.object(bot,'send') as send:
   bot.handle(self.db,msg(801,'🏪 Мижоз қўшиш'))
   bot.handle(self.db,msg(802,loc={'latitude':40.5,'longitude':71.5}))
   bot.handle(self.db,msg(803,photo='shop-photo'))
   self.assertEqual(bot.state(self.db,2)['step'],2)
   bot.handle(self.db,msg(804,'⬅️ Орқага'))
   s=bot.state(self.db,2)
   self.assertEqual(s['step'],1)
   self.assertNotIn('photo',s['values'])
   self.assertEqual(s['values']['lat'],40.5);self.assertEqual(s['values']['lon'],71.5)
   self.assertIn('расмини',send.call_args.args[1])

 def test_validation_error_repeats_current_question(self):
  self.rec('load',12,actor=1)
  now=int(time.time());self.db.execute('INSERT INTO shifts(agent,start) VALUES(2,?)',(now-10,))
  self.assertTrue(core.point(self.db,2,{'message_id':810,'date':now,'location':{'latitude':40,'longitude':71,'live_period':3600}}))
  def msg(i,text=None,loc=None,photo=None):
   m={'message_id':i,'date':int(time.time()),'from':{'id':2},'chat':{'id':2,'type':'private'}}
   if text is not None:m['text']=text
   if loc is not None:m['location']=loc
   if photo is not None:m['photo']=[{'file_id':photo}]
   return {'update_id':i,'message':m}
  with patch.object(bot,'send') as send:
   bot.process_update(self.db,msg(811,'🏪 Мижоз қўшиш'))
   bot.process_update(self.db,msg(812,loc={'latitude':40.5,'longitude':71.5}))
   bot.process_update(self.db,msg(813,photo='shop-photo'))
   send.reset_mock()
   bot.process_update(self.db,msg(814,'123'))
   texts=[call.args[1] for call in send.call_args_list]
   self.assertTrue(any('Телефонни +998' in x for x in texts))
   self.assertTrue(any('1–3 та телефон' in x for x in texts))
   self.assertEqual(bot.state(self.db,2)['step'],2)

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

 def test_delivery_correction_updates_stock_debt_and_audit(self):
  core.set_product_price(self.db,1,1,core.money('2.00'))
  core.set_product_price(self.db,1,3,core.money('5.00'))
  core.record(self.db,1,2,None,'load',1,20,source=91001)
  core.record(self.db,1,2,None,'load',3,12,source=91002)
  core.record(self.db,2,2,1,'delivery',1,10,source=91003,currency='USD')
  event=self.db.execute('SELECT id FROM events WHERE source=91003').fetchone()[0]
  self.assertEqual(core.client_debt_usd(self.db,1),core.money('20.00'))
  plan=core.correct_delivery(self.db,2,event,1,6)
  self.assertEqual(plan['new_amount_usd'],core.money('12.00'))
  self.assertEqual(core.client_debt_usd(self.db,1),core.money('12.00'))
  self.assertEqual(core.client_stock(self.db,2,1,1),6)
  self.assertEqual(core.agent_stock(self.db,2,1),14)
  audit=self.db.execute('SELECT old_pack,new_pack,old_qty,new_qty,old_amount_usd,new_amount_usd FROM delivery_edits WHERE delivery_event=?',(event,)).fetchone()
  self.assertEqual(tuple(audit),(1,1,10,6,core.money('20.00'),core.money('12.00')))
  core.correct_delivery(self.db,2,event,3,6)
  self.assertEqual(core.client_stock(self.db,2,1,1),0)
  self.assertEqual(core.client_stock(self.db,2,1,3),6)
  self.assertEqual(core.agent_stock(self.db,2,1),20)
  self.assertEqual(core.agent_stock(self.db,2,3),6)
  self.assertEqual(core.client_debt_usd(self.db,1),core.money('30.00'))
  self.assertEqual(self.db.execute('SELECT COUNT(*) FROM delivery_edits WHERE delivery_event=?',(event,)).fetchone()[0],2)

 def test_delivery_correction_rejects_downstream_history_cross_agent_and_negative_debt(self):
  core.set_product_price(self.db,1,1,core.money('2.00'))
  core.record(self.db,1,2,None,'load',1,20,source=91101)
  core.record(self.db,2,2,1,'delivery',1,10,source=91102,currency='USD')
  event=self.db.execute('SELECT id FROM events WHERE source=91102').fetchone()[0]
  with self.assertRaisesRegex(ValueError,'рухсат'):
   core.correct_delivery(self.db,4,event,1,8)
  core.record(self.db,2,2,1,'payment',value=core.money('19.00'),source=91103,currency='USD')
  with self.assertRaisesRegex(ValueError,'манфий'):
   core.correct_delivery(self.db,2,event,1,5)
  core.record(self.db,2,2,1,'sold',1,1,source=91104,currency='USD')
  with self.assertRaisesRegex(ValueError,'сотув ёки қайтариш'):
   core.correct_delivery(self.db,2,event,1,9)
  self.assertEqual(self.db.execute('SELECT qty FROM events WHERE id=?',(event,)).fetchone()[0],10)
  self.assertEqual(self.db.execute('SELECT COUNT(*) FROM delivery_edits').fetchone()[0],0)

 def test_agent_can_correct_delivered_goods_from_customer_edit_menu(self):
  core.set_product_price(self.db,1,1,core.money('2.00'))
  core.record(self.db,1,2,None,'load',1,20,source=91201)
  core.record(self.db,2,2,1,'delivery',1,10,source=91202,currency='USD')
  event=self.db.execute('SELECT id FROM events WHERE source=91202').fetchone()[0]
  now=int(time.time())
  def msg(i,text):
   return {'update_id':i,'message':{'message_id':i,'date':now,'from':{'id':2},'chat':{'id':2,'type':'private'},'text':text}}
  with patch.object(bot,'send') as send:
   bot.show_client_card(self.db,2,1)
   bot.handle(self.db,msg(91210,'✏️ Мижоз маълумотини ўзгартириш'))
   self.assertIn(bot.DELIVERY_EDIT_LABEL,[x for row in send.call_args.args[2] for x in row])
   bot.handle(self.db,msg(91211,bot.DELIVERY_EDIT_LABEL))
   choices=[x for row in send.call_args.args[2] for x in row]
   delivery_choice=next(x for x in choices if str(x).startswith('#'+str(event)+' ·'))
   bot.handle(self.db,msg(91212,delivery_choice))
   bot.handle(self.db,msg(91213,core.product_name(1)))
   bot.handle(self.db,msg(91214,'Дона'))
   bot.handle(self.db,msg(91215,'6'))
   self.assertIn('Эски:',send.call_args.args[1])
   self.assertIn('Янги:',send.call_args.args[1])
   self.assertIn('12.00 USD',send.call_args.args[1])
   bot.handle(self.db,msg(91216,'✅ Товар тузатишни сақлаш'))
   self.assertEqual(core.client_stock(self.db,2,1,1),6)
   self.assertEqual(core.client_debt_usd(self.db,1),core.money('12.00'))
   self.assertIn('Қарз ва қолдиқ қайта ҳисобланди',send.call_args_list[-2].args[1])
   self.assertEqual(self.db.execute('SELECT actor FROM delivery_edits WHERE delivery_event=?',(event,)).fetchone()[0],2)

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
