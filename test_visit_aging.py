import json
import re
import time
import unittest
from datetime import datetime,timedelta

import core
import customer_status as cs
import reports


class VisitAgingTests(unittest.TestCase):
    def setUp(self):
        self.db=core.connect(':memory:')
        self.db.executemany('INSERT INTO users(id,role,name) VALUES(?,?,?)',[
            (1,'admin','Admin'),(2,'agent','Agent')])

    def tearDown(self):
        self.db.close()

    def shop(self,cid,days,status='interested',followup=None):
        now=int(time.time());ts=now-days*86400
        self.db.execute("""INSERT INTO clients(id,agent,name,phone,address,lat,lon,photo,shop_name,comment,payment_due,created_ts,map_only)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,1)""",
            (cid,2,f'Client {cid}',f'+9989000000{cid:02d}','Kokand',40.5+cid/1000,71.2,'',f'Shop {cid}','','',ts))
        self.db.execute('INSERT INTO client_visits(client,actor,status,note,followup,ts) VALUES(?,?,?,?,?,?)',
                        (cid,2,status,'Test visit',followup,ts))
        return now

    @staticmethod
    def shops(html):
        m=re.search(r'<script id="data" type="application/json">(.*?)</script>',html.decode(),re.S)
        return json.loads(m.group(1))['shops']

    def test_exact_thresholds(self):
        now=self.shop(1,0)
        for days,level in ((2,'fresh'),(3,'yellow'),(4,'yellow'),(5,'red'),(8,'red')):
            ts=now-days*86400
            self.db.execute('UPDATE clients SET created_ts=? WHERE id=1',(ts,))
            self.db.execute('UPDATE client_visits SET ts=? WHERE client=1',(ts,))
            self.assertEqual(cs.visit_attention(self.db,1,True,now=now)['level'],level)

    def test_future_waiting_date_overrides_old_visit_warning(self):
        future=(datetime.now(cs.TZ).date()+timedelta(days=20)).isoformat()
        now=self.shop(2,10,'waiting',future)
        attention=cs.visit_attention(self.db,2,True,now=now)
        self.assertEqual(attention['level'],'scheduled')
        self.assertIn(future,attention['label'])

    def test_agent_and_admin_maps_expose_yellow_and_red_priorities(self):
        self.shop(3,4)
        self.shop(4,9)
        agent=self.shops(reports.agent_clients_map_html(self.db,2))
        by_id={s['id']:s for s in agent}
        self.assertEqual(by_id[3]['visit_level'],'yellow')
        self.assertEqual(by_id[4]['visit_level'],'red')
        self.assertEqual(by_id[3]['visit_color'],'#b45309')
        self.assertEqual(by_id[4]['visit_color'],'#dc2626')
        admin=self.shops(reports.admin_clients_map_html(self.db,1))
        self.assertEqual({s['visit_level'] for s in admin},{'yellow','red'})
        html=reports.agent_clients_map_html(self.db,2).decode()
        self.assertIn('3–4 кун · ташриф керак',html)
        self.assertIn('5+ кун · устувор ташриф',html)
        self.assertIn('🟡 3–4 кун',html)
        self.assertIn('🔴 5+ кун',html)


if __name__=='__main__':
    unittest.main()
