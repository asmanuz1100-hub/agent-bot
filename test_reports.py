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
  for uid in (3,4,99):
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
  text,overall_html=reports.overall(self.db,1,datetime(2026,9,18,12,tzinfo=reports.TZ))
  self.assertIn('Жами йўл:',text);self.assertIn('Фаол савдо нуқталари: 1',text);self.assertIn('L.polyline',overall_html.decode('utf-8'))
  with self.assertRaises(ValueError):reports.route_map_html(self.db,2,2)
  with self.assertRaises(ValueError):reports.overall(self.db,2,datetime(2026,9,18,12,tzinfo=reports.TZ))

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

 def test_agent_report_flow_no_other_agent(self):
  def msg(i,t):return {'update_id':i,'message':{'message_id':i,'date':100,'from':{'id':2},'chat':{'id':2,'type':'private'},'text':t}}
  self.assertFalse(bot.allowed(self.db,2,'reconcile'))

if __name__=='__main__':unittest.main()
