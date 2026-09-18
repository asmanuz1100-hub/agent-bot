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
 def test_unique_shops_and_visits(self):
  self.add('visit','2026-09-12');self.add('visit','2026-09-13');self.add('visit','2026-09-18',client=2)
  self.add('visit','2026-09-11',client=2);self.add('delivery','2026-09-14',8)
  text,rows=reports.weekly(self.db,1,2,datetime(2026,9,18,12,tzinfo=reports.TZ))
  self.assertIn('Алоҳида дўконлар: 2',text);self.assertIn('ташрифлар: 3',text);self.assertEqual(len(rows),4)
 def test_report_permissions(self):
  for uid in (3,4,99):
   with self.assertRaises(ValueError):reports.reconciliation(self.db,uid,1,'2026-09-01','2026-09-18')
   with self.assertRaises(ValueError):reports.weekly(self.db,uid,2)
 def test_period_validation(self):
  with self.assertRaises(ValueError):reports.dates('2026-09-20','2026-09-18')
  with self.assertRaises(ValueError):reports.dates('bad','2026-09-18')
 def test_empty_and_advance(self):
  self.add('payment','2026-09-01',amount=1000)
  r=reports.reconciliation(self.db,1,1,'2026-09-01','2026-09-18')
  self.assertEqual(r['closing'],-1000)
 def test_handover_accept_time(self):
  self.add('payment','2026-09-01',amount=1000)
  old=int(datetime(2026,9,1,tzinfo=reports.TZ).timestamp());new=int(datetime(2026,9,15,tzinfo=reports.TZ).timestamp())
  self.db.execute("INSERT INTO handovers(agent,amount,status,ts,accepted_ts) VALUES(2,500,'accepted',?,?)",(old,new))
  text,_=reports.weekly(self.db,1,2,datetime(2026,9,18,12,tzinfo=reports.TZ))
  self.assertIn('Кассир қабул қилган: 5.00',text)
 def test_agent_report_flow_no_other_agent(self):
  def msg(i,t):return {'update_id':i,'message':{'message_id':i,'date':100,'from':{'id':2},'chat':{'id':2,'type':'private'},'text':t}}
  with patch.object(bot,'send'),patch.object(bot,'document'):
   bot.handle(self.db,msg(1,'📈 Ҳафталик таҳлил'))
   self.assertEqual(bot.state(self.db,2)['values']['agent'],2)
   bot.handle(self.db,msg(2,'✅ Тасдиқлаш'))
   self.assertIsNone(bot.state(self.db,2))

if __name__=='__main__':unittest.main()
