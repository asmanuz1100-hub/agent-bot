import unittest
from datetime import datetime
from unittest.mock import patch
import core,reports,bot

class ReportsTests(unittest.TestCase):
 def setUp(self):
  self.db=core.connect(':memory:')
  self.db.executemany('INSERT INTO users VALUES(?,?,?)',[(1,'admin','A'),(2,'agent','B'),(3,'cashier','C'),(4,'agent','D')])
  self.db.executemany('INSERT INTO clients(id,agent,name,phone,address) VALUES(?,?,?,?,?)',[(1,2,'<script>','+998900000001','Address'),(2,2,'Shop two','+998900000002','Other')])
 def tearDown(self):self.db.close()
 def add(self,kind,day,qty=0,amount=0,client=1):
  ts=int(datetime.fromisoformat(day).replace(tzinfo=reports.TZ).timestamp())
  self.db.execute('INSERT INTO events(actor,agent,client,kind,pack,qty,amount,ts) VALUES(2,2,?,?,1,?,?,?)',(client,kind,qty,amount,ts))
 def test_opening_turnover_closing_and_stock(self):
  self.add('delivery','2026-09-01',12);self.add('sold','2026-09-02',2,20000);self.add('payment','2026-09-02',amount=10000)
  self.add('sold','2026-09-12',3,30000);self.add('return','2026-09-13',2);self.add('payment','2026-09-18T23:59:59',amount=25000)
  self.add('payment','2026-09-19',amount=999999)
  r=reports.reconciliation(self.db,2,1,'2026-09-12','2026-09-18')
  self.assertEqual((r['opening'],r['sales'],r['payments'],r['closing']),(10000,30000,25000,15000))
  self.assertEqual(r['opening_stock'][1],10);self.assertEqual(r['closing_stock'][1],5)
  self.assertEqual(len(r['rows']),3)
  html=reports.reconciliation_html(r).decode();self.assertIn('&lt;script&gt;',html);self.assertNotIn('<script>',html)
 def test_report_permissions(self):
  self.assertEqual(reports.reconciliation(self.db,4,1,'2026-09-01','2026-09-18')['client']['id'],1)
  for uid in (3,99):
   with self.assertRaises(ValueError):reports.reconciliation(self.db,uid,1,'2026-09-01','2026-09-18')
 def test_period_validation(self):
  with self.assertRaises(ValueError):reports.dates('2026-09-20','2026-09-18')
  with self.assertRaises(ValueError):reports.dates('bad','2026-09-18')
 def test_empty_and_advance(self):
  self.add('payment','2026-09-01',amount=1000)
  r=reports.reconciliation(self.db,1,1,'2026-09-01','2026-09-18')
  self.assertEqual(r['closing'],-1000)
 def test_route_map_and_overall_analysis(self):
  self.db.execute("UPDATE clients SET shop_name='Shop one',lat=40.0,lon=71.0 WHERE id=1")
  start=int(datetime(2026,9,18,9,tzinfo=reports.TZ).timestamp())
  self.db.execute('INSERT INTO shifts(agent,start,end,live_id) VALUES(2,?,?,10)',(start,start+1200))
  shift=self.db.execute('SELECT id FROM shifts WHERE agent=2').fetchone()[0]
  self.db.executemany('INSERT INTO points(shift,ts,lat,lon,accuracy) VALUES(?,?,?,?,?)',[
   (shift,start,40.0,71.0,10),(shift,start+300,40.01,71.01,10),(shift,start+600,40.02,71.02,10)
  ])
  self.add('visit','2026-09-18T09:05:00',client=1)
  html,stats,active=reports.route_map_html(self.db,1,2)
  txt=html.decode('utf-8')
  self.assertIn('L.polyline',txt);self.assertIn('Shop one',txt);self.assertGreater(stats['km'],0);self.assertEqual(active,1)
  self.assertIn('tile.openstreetmap.de/',txt)
  self.assertNotIn('maplibre-gl-leaflet',txt)
  self.assertNotIn('tiles.openfreemap.org',txt)
  self.assertNotIn('tile.openstreetmap.org',txt)
  self.assertIn('tile.openstreetmap.fr/hot/',txt)
  self.assertNotIn('cartocdn.com',txt)
  self.assertIn('map-status',txt)
  self.assertIn('Навигаторда очиш',txt)
  text,overall_html=reports.overall(self.db,1,datetime(2026,9,18,12,tzinfo=reports.TZ))
  self.assertIn('Жами масофа:',text);self.assertIn('GPS нуқталари: 3',text);self.assertIn('L.polyline',overall_html.decode('utf-8'))
  with self.assertRaises(ValueError):reports.route_map_html(self.db,2,2)
  with self.assertRaises(ValueError):reports.overall(self.db,2,datetime(2026,9,18,12,tzinfo=reports.TZ))

 def test_map_customer_pin_opens_signed_card_and_card_is_read_only(self):
  import re,json
  self.db.execute("UPDATE clients SET lat=40.111,lon=71.222,shop_name='<img src=x onerror=alert(1)>',photo='tg-file-id' WHERE id=1")
  self.db.execute("INSERT INTO events(actor,agent,client,kind,pack,qty,amount_usd,ts) VALUES(2,2,1,'delivery',1,3,600,?)",(int(datetime(2026,9,18,9,tzinfo=reports.TZ).timestamp()),))
  self.db.execute("INSERT INTO events(actor,agent,client,kind,pack,qty,amount_usd,ts) VALUES(2,2,1,'payment',0,0,125,?)",(int(datetime(2026,9,18,10,tzinfo=reports.TZ).timestamp()),))
  card_url=lambda cid:f'https://example.test/map/client/{cid}/2000000000/'+('a'*32)
  now=datetime(2026,9,18,12,tzinfo=reports.TZ)
  for period in ('day','week','month'):
   if period!='day':
    self.db.execute("UPDATE clients SET created_ts=? WHERE id=1",(int(datetime(2026,9,18,8,tzinfo=reports.TZ).timestamp()),))
   summary,page=reports.overall(self.db,1,now,period=period,card_url=card_url)
   html=page.decode()
   self.assertIn('Мижоз карточкасини очиш',html)
   payload=re.search(r'<script id="data" type="application/json">(.*?)</script>',html,re.S)
   self.assertIsNotNone(payload)
   data=json.loads(payload.group(1))
   shop=next(x for x in data['shops'] if x['id']==1)
   self.assertEqual(shop['card_url'],card_url(1))
   self.assertNotIn('tg-file-id',html)
   self.assertNotIn('+998900000001',html)
  card=reports.client_card_html(self.db,1,1,
      photo_url='https://example.test/map/client-photo/1/2000000000/'+('b'*32)).decode()
  self.assertIn('МИЖОЗ #1',card)
  self.assertIn('4.75 USD',card)
  self.assertIn('3 дона',card)
  self.assertIn('+998900000001',card)
  self.assertIn('МИЖОЗ',card)
  self.assertIn('client-photo/1',card)
  self.assertIn('&lt;img src=x onerror=alert(1)&gt;',card)
  self.assertNotIn('<img src=x onerror=alert(1)>',card)
  self.assertNotIn('tg-file-id',card)
  self.assertIn('Карточка фақат кўриш учун',card)
  with self.assertRaises(ValueError):reports.client_card_html(self.db,2,1)
  with self.assertRaises(ValueError):reports.client_card_html(self.db,1,999)

 def test_admin_map_sees_all_agents_and_is_read_only(self):
  import re,json
  self.db.execute("UPDATE clients SET lat=40.111,lon=71.222,shop_name='<script>alert(1)</script>' WHERE id=1")
  self.db.execute("INSERT INTO events(actor,agent,client,kind,pack,qty,amount_usd,ts) VALUES(2,2,1,'delivery',1,3,600,?)",(int(datetime(2026,9,18,9,tzinfo=reports.TZ).timestamp()),))
  self.db.execute("INSERT INTO events(actor,agent,client,kind,pack,qty,amount_usd,ts) VALUES(2,2,2,'delivery',1,1,200,?)",(int(datetime(2026,9,18,9,tzinfo=reports.TZ).timestamp()),))
  self.db.execute("INSERT INTO clients(id,agent,name,phone,address,lat,lon,shop_name) VALUES(3,4,'Other agent','+998900000003','Private',40.5,71.5,'Other shop')")
  self.db.execute("INSERT INTO events(actor,agent,client,kind,pack,qty,amount_usd,ts) VALUES(4,4,3,'delivery',1,1,200,?)",(int(datetime(2026,9,18,9,tzinfo=reports.TZ).timestamp()),))
  url=lambda cid:'https://example.test/map/client/'+str(cid)+'/2000000000/'+'a'*32
  html=reports.admin_clients_map_html(self.db,1,card_url=url).decode()
  self.assertIn('Админ · Мижозлар харитаси',html)
  self.assertIn('Навигаторда очиш',html)
  self.assertIn('Агент:',html)
  self.assertNotIn('<script>alert(1)</script>',html)
  self.assertNotIn('+998900000001',html)
  found=re.search(r'<script id="data" type="application/json">(.*?)</script>',html,re.S)
  data=json.loads(found.group(1))
  self.assertEqual({x['id'] for x in data['shops']},{1,3})
  self.assertEqual({x['owner'] for x in data['shops']},{'B','D'})
  self.assertEqual(sum(x['stock'] for x in data['shops']),4)
  self.assertEqual(sum(float(x['debt']) for x in data['shops']),8.0)
  self.assertTrue(all('pay_url' not in x and 'return_url' not in x for x in data['shops']))
  self.assertTrue(all(x['card_url']==url(x['id']) for x in data['shops']))
  self.assertIn('Локациясиз',html)
  for uid in (2,3,4,99):
   with self.assertRaises(ValueError):reports.admin_clients_map_html(self.db,uid)

 def test_agent_shared_customer_map_and_private_quick_actions(self):
  import json,re
  self.db.execute("UPDATE clients SET lat=40.111,lon=71.222,shop_name='<img onerror=alert(1)>' WHERE id=1")
  self.db.execute("INSERT INTO events(actor,agent,client,kind,pack,qty,amount_usd,ts) VALUES(2,2,1,'delivery',1,3,600,?)",(int(datetime(2026,9,18,9,tzinfo=reports.TZ).timestamp()),))
  self.db.execute("INSERT INTO events(actor,agent,client,kind,pack,qty,amount_usd,ts) VALUES(2,2,2,'delivery',1,2,400,?)",(int(datetime(2026,9,18,9,tzinfo=reports.TZ).timestamp()),))
  self.db.execute("INSERT INTO clients(id,agent,name,phone,address,lat,lon,shop_name) VALUES(3,4,'Other agent','+998900000003','Private',40.5,71.5,'Other shop')")
  self.db.execute("INSERT INTO events(actor,agent,client,kind,pack,qty,amount_usd,ts) VALUES(4,4,3,'delivery',1,1,200,?)",(int(datetime(2026,9,18,9,tzinfo=reports.TZ).timestamp()),))
  html=reports.agent_clients_map_html(self.db,2,action_url=lambda verb,cid:'https://t.me/asman_agent_test_bot?start='+verb+'_'+str(cid)).decode()
  self.assertIn('Мижозлар харитаси',html)
  self.assertIn('Навигаторда очиш',html)
  self.assertIn('Пул олиш',html)
  self.assertIn('Товар қайтариш',html)
  self.assertIn('Товар бериш',html)
  self.assertNotIn('+998900000001',html)
  self.assertIn('Other shop',html)
  self.assertNotIn('<img onerror=alert(1)>',html)
  found=re.search(r'<script id="data" type="application/json">(.*?)</script>',html,re.S)
  data=json.loads(found.group(1))
  self.assertTrue(data['agent_clients'])
  self.assertEqual({x['id'] for x in data['shops']},{1,3})
  by_id={x['id']:x for x in data['shops']}
  self.assertEqual(by_id[1]['stock'],3)
  self.assertEqual(by_id[1]['debt'],'6.00')
  self.assertEqual(by_id[3]['stock'],1)
  self.assertEqual(by_id[3]['owner'],'D')
  self.assertIn('start=pay_1',by_id[1]['pay_url'])
  self.assertIn('start=return_1',by_id[1]['return_url'])
  self.assertIn('start=delivery_3',by_id[3]['delivery_url'])
  self.assertIn('Локациясиз',html)
  same=reports.agent_clients_map_html(self.db,4,action_url=lambda verb,cid:'x').decode()
  self.assertIn('Other shop',same)
  for agent in (1,3):
   with self.assertRaises(ValueError):reports.agent_clients_map_html(self.db,agent)

 def test_multiple_shifts_one_agent_one_daily_route_and_summary(self):
  import json,re
  start=int(datetime(2026,9,18,9,tzinfo=reports.TZ).timestamp())
  self.db.execute('INSERT INTO shifts(agent,start,end,live_id) VALUES(2,?,?,11)',(start,start+240))
  s1=self.db.execute('SELECT id FROM shifts WHERE agent=2 ORDER BY id DESC LIMIT 1').fetchone()[0]
  self.db.execute('INSERT INTO shifts(agent,start,end,live_id) VALUES(2,?,?,12)',(start+240,start+480))
  s2=self.db.execute('SELECT id FROM shifts WHERE agent=2 ORDER BY id DESC LIMIT 1').fetchone()[0]
  self.db.executemany('INSERT INTO points(shift,ts,lat,lon,accuracy) VALUES(?,?,?,?,?)',[
   (s1,start,40.0,71.0,10),(s1,start+120,40.001,71.001,10),
   (s1,start+240,40.002,71.002,10),(s2,start+240,40.002,71.002,10),
   (s2,start+360,40.003,71.003,10)
  ])
  self.db.execute("INSERT INTO events(actor,agent,client,kind,pack,qty,amount,amount_usd,ts) VALUES(2,2,1,'delivery',1,4,0,800,?)",(start+30,))
  self.db.execute("INSERT INTO events(actor,agent,client,kind,pack,qty,amount,amount_usd,ts) VALUES(2,2,1,'payment',0,0,0,200,?)",(start+300,))
  summary=reports.shift_summary(self.db,2,s2)
  self.assertEqual(summary['shift_count'],2)
  self.assertEqual(summary['duration'],480)
  self.assertEqual(summary['gps_points'],4)
  self.assertEqual(summary['sold_amount'],800)
  self.assertEqual(summary['payments'],200)
  self.assertIn('сменалар: 2 та',summary['text'])
  text,html=reports.overall(self.db,1,datetime(2026,9,18,10,tzinfo=reports.TZ))
  match=re.search(r'<script id="data" type="application/json">(.*?)</script>',html.decode('utf-8'),re.S)
  self.assertIsNotNone(match)
  data=json.loads(match.group(1))
  self.assertEqual(len(data['routes']),1)
  self.assertEqual(len(data['routes'][0]['segments']),2)
  self.assertEqual(len(data['routes'][0]['points']),4)
  self.assertIn('GPS нуқталари: 4',text)
  self.assertIn('Навигаторда очиш',html.decode('utf-8'))

 def test_week_and_month_maps_only_show_new_customers_not_agent_tracks(self):
  import json,re
  tz=reports.TZ
  at=lambda y,m,d,h=9: int(datetime(y,m,d,h,tzinfo=tz).timestamp())
  self.db.execute("UPDATE clients SET lat=41.111,lon=70.111,created_ts=? WHERE id=1",(at(2026,8,15),))
  self.db.execute("UPDATE clients SET lat=41.222,lon=70.222,created_ts=? WHERE id=2",(at(2026,9,3),))
  self.db.execute("INSERT INTO clients(id,agent,name,phone,shop_name,address,lat,lon,created_ts) VALUES(10,2,'New Shop','+998900000010','New Shop','New Address',41.333,70.333,?)",(at(2026,9,16),))
  start=at(2026,9,18)
  self.db.execute('INSERT INTO shifts(agent,start,end) VALUES(?,?,?)',(2,start,start+3600))
  shift=self.db.execute('SELECT id FROM shifts WHERE agent=2').fetchone()[0]
  self.db.executemany('INSERT INTO points(shift,ts,lat,lon,accuracy) VALUES(?,?,?,?,?)',[
   (shift,start,40.888,71.888,10),(shift,start+100,40.889,71.889,10)
  ])
  self.db.execute("INSERT INTO events(actor,agent,client,kind,pack,qty,amount_usd,ts) VALUES(2,2,10,'sold',1,2,1234,?)",(start+100,))
  self.db.execute("INSERT INTO events(actor,agent,client,kind,pack,qty,amount_usd,ts) VALUES(2,2,10,'delivery',1,2,2000,?)",(start+50,))
  now=datetime(2026,9,18,12,tzinfo=tz)
  for period,expected in (('week',[10]),('month',[2,10])):
   text,html=reports.overall(self.db,1,now,period=period)
   txt=html.decode('utf-8')
   match=re.search(r'<script id="data" type="application/json">(.*?)</script>',txt,re.S)
   self.assertIsNotNone(match)
   data=json.loads(match.group(1))
   self.assertEqual(data['routes'],[])
   self.assertTrue(data['points_only'])
   self.assertEqual(sorted(x['id'] for x in data['shops']),expected)
   self.assertNotIn('40.888',match.group(1))
   self.assertNotIn('40.889',match.group(1))
   self.assertIn('Жами иш соати: 1 соат 0 дақиқа',text)
   self.assertIn('Янги мижозлар:',text)
   self.assertIn('Берилган товарнинг умумий суммаси: 20.00 USD',text)
   self.assertIn('Олинган пулнинг умумий суммаси: 0.00 USD',text)
   self.assertIn('сотув қиймати: 12.34 USD',text)
   self.assertIn('Берилган товар жами</span><strong>20.00 USD',txt)
   self.assertIn('Жами иш вақти</span><strong>1 соат 0 дақиқа',txt)
   self.assertIn('Агентлар иш вақти',txt)
   self.assertIn('tile.openstreetmap.de/',txt)
   self.assertIn('tile.openstreetmap.de/',txt)
   self.assertNotIn('maplibreGL',txt)
   self.assertTrue(data['agent_work'])
   agent=next(x for x in data['agent_work'] if x['name']=='B')
   self.assertEqual(agent['hours'],'1 соат 0 дақиқа')
   self.assertIn('Олинган пул жами</span><strong>0.00 USD',txt)
   self.assertIn('берилган товар 20.00 USD',data['summary'])
   self.assertIn('траекторияси чизилмайди',text)
  day_text,day_html=reports.overall(self.db,1,now,period='day')
  day_json=re.search(r'<script id="data" type="application/json">(.*?)</script>',day_html.decode(),re.S)
  self.assertTrue(json.loads(day_json.group(1))['routes'])
  self.assertIn('1 КУНЛИК',day_text)
  self.assertIn('Жами иш вақти</span><strong>1 соат 0 дақиқа',day_html.decode('utf-8'))
  self.assertIn('Агентлар иш вақти',day_html.decode('utf-8'))

 def test_empty_weekly_and_monthly_map_still_has_basemap_and_hours(self):
  import json,re
  now=datetime(2026,9,18,12,tzinfo=reports.TZ)
  for period in ('week','month'):
   summary,page=reports.overall(self.db,1,now,period=period)
   txt=page.decode('utf-8')
   data=json.loads(re.search(r'<script id="data" type="application/json">(.*?)</script>',txt,re.S).group(1))
   self.assertEqual(data['routes'],[])
   self.assertEqual(data['shops'],[])
   self.assertTrue(data['points_only'])
   self.assertIn('Шу даврда локацияси киритилган янги мижоз йўқ',txt)
   self.assertIn('tile.openstreetmap.de',txt)
   self.assertIn('Жами иш вақти</span><strong>0 соат 0 дақиқа',txt)
   self.assertIn('Жами иш соати: 0 соат 0 дақиқа',summary)

 def test_weekly_gross_delivery_and_payment_include_archived_agent_history(self):
  begin=int(datetime(2026,9,18,9,tzinfo=reports.TZ).timestamp())
  self.db.execute("UPDATE users SET role='disabled' WHERE id=4")
  self.db.execute("INSERT INTO clients(id,agent,name,phone,created_ts,lat,lon) VALUES(30,4,'Архив мижоз','+998900000030',?,?,?)",(begin,40.5,71.5))
  self.db.execute("INSERT INTO events(actor,agent,client,kind,pack,qty,amount_usd,ts) VALUES(4,4,30,'delivery',1,3,1500,?)",(begin+40,))
  self.db.execute("INSERT INTO events(actor,agent,client,kind,pack,qty,amount_usd,ts) VALUES(4,4,30,'payment',0,0,550,?)",(begin+80,))
  self.db.execute("INSERT INTO events(actor,agent,client,kind,pack,qty,amount_usd,ts) VALUES(4,4,30,'sold',1,1,0,?)",(begin+120,))
  summary,html=reports.overall(self.db,1,datetime(2026,9,18,11,tzinfo=reports.TZ),period='week')
  self.assertIn('Берилган товарнинг умумий суммаси: 15.00 USD',summary)
  self.assertIn('Олинган пулнинг умумий суммаси: 5.50 USD',summary)
  self.assertIn('D (4):',summary)
  self.assertIn('сотув қиймати: 0.00 USD',summary)
  self.assertIn('USD баҳоси сақланмаган',summary)
  import re,json
  match=re.search(r'<script id="data" type="application/json">(.*?)</script>',html.decode('utf-8'),re.S)
  data=json.loads(match.group(1))
  self.assertEqual(data['routes'],[])
  self.assertIn(30,[x['id'] for x in data['shops']])

 def test_all_time_reconciliation_without_dates(self):
  self.add('delivery','2026-09-01',4)
  self.add('sold','2026-09-02',2,20000)
  self.add('payment','2026-09-18',amount=10000)
  self.db.execute("INSERT INTO events(actor,agent,client,kind,pack,qty,amount_usd,ts) VALUES(2,2,1,'delivery',1,4,800,?)",
                  (int(datetime(2026,9,1,9,tzinfo=reports.TZ).timestamp()),))
  result=reports.reconciliation(self.db,1,1)
  self.assertEqual(result['start'],'Барча давр')
  self.assertEqual(result['usd_closing'],800)
  self.assertEqual(result['closing'],10000)
  self.assertIn('Барча давр',reports.reconciliation_html(result).decode('utf-8'))

 def test_shift_daily_summary(self):
  start=int(datetime(2026,9,18,9,tzinfo=reports.TZ).timestamp());end=start+3600
  self.db.execute('INSERT INTO shifts(agent,start,end,live_id) VALUES(2,?,?,99)',(start,end))
  shift=self.db.execute('SELECT id FROM shifts WHERE agent=2 ORDER BY id DESC LIMIT 1').fetchone()[0]
  self.db.executemany('INSERT INTO points(shift,ts,lat,lon,accuracy) VALUES(?,?,?,?,?)',[
   (shift,start+10,40.0,71.0,10),(shift,start+200,40.01,71.01,10),(shift,start+400,40.02,71.02,10)
  ])
  self.db.execute("INSERT INTO clients(id,agent,name,phone,address,created_ts) VALUES(10,2,'New client','+998900000010','A',?)",(start+100,))
  self.db.execute("INSERT INTO events(actor,agent,client,kind,pack,qty,amount,amount_usd,ts) VALUES(2,2,10,'delivery',1,4,0,2000000,?)",(start+200,))
  self.db.execute("INSERT INTO events(actor,agent,client,kind,pack,qty,amount,ts) VALUES(2,2,10,'sold',1,2,0,?)",(start+300,))
  self.db.execute("INSERT INTO events(actor,agent,client,kind,pack,qty,amount,amount_usd,ts) VALUES(2,2,10,'payment',0,0,0,500000,?)",(start+400,))
  self.db.execute("INSERT INTO events(actor,agent,client,kind,pack,qty,amount,ts) VALUES(2,2,10,'visit',0,0,0,?)",(start+500,))
  r=reports.shift_summary(self.db,2,shift)
  self.assertEqual(r['new_clients'],1);self.assertEqual(r['active_clients'],1);self.assertEqual(r['visits'],1)
  self.assertEqual(r['sold_qty'],2);self.assertEqual(r['sold_amount'],2000000);self.assertEqual(r['payments'],500000)
  self.assertEqual(r['duration'],3600);self.assertGreater(r['km'],0);self.assertEqual(r['gps_points'],3)
  self.assertIn('КУНЛИК ФАОЛИЯТ',r['text']);self.assertIn('Янги мижоз: 1 та',r['text']);self.assertIn('20 000.00 USD',r['text'])
  self.assertNotIn('Бошланиш локацияси',r['text'])
  self.assertNotIn('Охирги локация',r['text'])
  self.assertNotIn('https://www.google.com/maps',r['text'])
  self.assertNotIn('GPS',r['text'])
  self.assertNotIn('Тахминий йўл',r['text'])
  self.assertIsNotNone(r['first']);self.assertIsNotNone(r['last'])

 def test_agent_can_open_shared_reconciliation_reports(self):
  def msg(i,t):return {'update_id':i,'message':{'message_id':i,'date':100,'from':{'id':2},'chat':{'id':2,'type':'private'},'text':t}}
  self.assertTrue(bot.allowed(self.db,2,'reconcile'))

 def test_all_clients_reconciliation_exports(self):
  self.db.execute("UPDATE clients SET shop_name='Дўкон',address='Манзил' WHERE id=1")
  self.db.execute("INSERT INTO events(actor,agent,client,kind,pack,qty,amount_usd,ts,source) VALUES(2,2,1,'delivery',1,10,25000,1,9001)")
  self.db.execute("INSERT INTO events(actor,agent,client,kind,amount_usd,ts,source) VALUES(2,2,1,'payment',5000,2,9002)")
  rows=reports.all_clients_statement_rows(self.db,1)
  self.assertEqual(rows[0]['products'],[(core.product_name(1),10)])
  self.assertEqual(rows[0]['debt'],20000)
  self.assertTrue(reports.all_clients_xlsx(self.db,1).startswith(b'PK'))
  self.assertTrue(reports.all_clients_pdf(self.db,1).startswith(b'%PDF'))
  self.assertEqual(len(reports.all_clients_statement_rows(self.db,2)),2)
  act=reports.reconciliation(self.db,2,1)
  self.assertTrue(reports.reconciliation_xlsx(act).startswith(b'PK'))
  self.assertTrue(reports.reconciliation_pdf(act).startswith(b'%PDF'))
  with self.assertRaises(ValueError):reports.all_clients_statement_rows(self.db,3)

 def test_reconciliation_export_permissions(self):
  self.assertTrue(bot.allowed(self.db,1,'reconcile_all_xlsx'))
  self.assertTrue(bot.allowed(self.db,1,'reconcile_all_pdf'))
  self.assertTrue(bot.allowed(self.db,2,'reconcile_all_xlsx'))
  self.assertTrue(bot.allowed(self.db,2,'reconcile_all_pdf'))
  self.assertTrue(bot.allowed(self.db,2,'reconcile_client_xlsx'))
  self.assertTrue(bot.allowed(self.db,2,'reconcile_client_pdf'))

if __name__=='__main__':unittest.main()
