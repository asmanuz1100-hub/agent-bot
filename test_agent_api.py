"""Real Agent Mini App API tests: signed identity, ledger rules and idempotence."""
import hashlib,hmac,json,time,unittest
from urllib.parse import urlencode
import agent_api,core

TOKEN='unit-test-bot-token'
def signed(uid):
    fields={'auth_date':str(int(time.time())),'user':json.dumps({'id':uid})}
    key=hmac.new(b'WebAppData',TOKEN.encode(),hashlib.sha256).digest()
    check='\n'.join(k+'='+v for k,v in sorted(fields.items()))
    fields['hash']=hmac.new(key,check.encode(),hashlib.sha256).hexdigest()
    return urlencode(fields)


class AgentLiveApiTests(unittest.TestCase):
    def setUp(self):
        self.db=core.connect(':memory:')
        self.db.executemany('INSERT INTO users(id,role,name) VALUES(?,?,?)',
            [(1,'admin','Admin'),(2,'agent','Agent A'),(3,'agent','Agent B'),(4,'cashier','Cashier')])
        self.db.execute('UPDATE products SET price=250 WHERE pack=1')
        self.db.execute("""INSERT INTO clients(id,agent,name,shop_name,phone,address,lat,lon,created_ts)
          VALUES(5,3,'Buyer','Real shop','+998901234567','Qo‘qon',40.54,70.94,?)""",(int(time.time()),))
        self.db.commit()
    def tearDown(self):self.db.close()

    def write(self,action,nonce,**kwargs):
        with self.db:return agent_api.handle(self.db,2,action,dict(nonce=nonce,**kwargs))

    def test_only_signed_agent_can_enter(self):
        self.assertEqual(agent_api.authorize(self.db,signed(2),TOKEN)[0],2)
        for uid in (1,4,777):
            with self.assertRaises(PermissionError):
                agent_api.authorize(self.db,signed(uid),TOKEN)
        with self.assertRaises(ValueError):
            agent_api.authorize(self.db,signed(2).replace('id%22%3A+2','id%22%3A+3'),TOKEN)

    def test_snapshot_real_shared_clients_but_only_own_cash_and_shift(self):
        self.db.execute("INSERT INTO shifts(agent,start) VALUES(3,?)",(int(time.time())-100,))
        self.db.execute("INSERT INTO events(actor,agent,client,kind,amount_usd,ts) VALUES(3,3,5,'payment',1111,?)",(int(time.time()),))
        self.db.commit()
        snap=agent_api.snapshot(self.db,2,'Agent A')
        self.assertEqual(len(snap['clients']),1)
        self.assertEqual(snap['clients'][0]['name'],'Real shop')
        self.assertFalse(snap['me']['shiftOpen'])
        self.assertEqual(snap['summary']['cashOnHandUsd'],0)
        self.assertEqual(snap['events'],[])
        self.assertFalse(snap['me']['gps']['ts'])
        self.assertEqual(snap['products'][0]['priceUsd'],2.5)

    def test_shift_and_idempotency(self):
        self.write('shift_start','startnonce001')
        self.assertTrue(agent_api.snapshot(self.db,2,'A')['me']['shiftOpen'])
        self.assertTrue(self.write('shift_start','startnonce001')['duplicate'])
        with self.assertRaises(ValueError):
            self.write('shift_start','startnonce002')
        self.write('shift_end','endnonce0001')
        self.assertFalse(agent_api.snapshot(self.db,2,'A')['me']['shiftOpen'])
        self.assertEqual(len(self.db.execute('SELECT id FROM shifts WHERE agent=2').fetchall()),1)

    def test_real_delivery_payment_return_and_cash_handover(self):
        core.record(self.db,1,2,None,'load',1,10,currency='USD')
        self.write('delivery','delivernonce01',clientId=5,items=[{'pack':1,'qty':'4'}])
        self.assertEqual(core.client_debt_usd(self.db,5),1000)
        self.assertEqual(core.agent_stock(self.db,2,1),6)
        self.assertTrue(self.write('delivery','delivernonce01',clientId=5,items=[{'pack':1,'qty':'4'}])['duplicate'])
        with self.assertRaises(ValueError):
            self.write('payment','paymentbad01',clientId=5,amount='11')
        self.write('payment','paymentnonce01',clientId=5,amount='5.00')
        self.assertEqual(core.client_debt_usd(self.db,5),500)
        self.assertEqual(core.cash_usd(self.db,2),500)
        self.write('return','returnnonce001',clientId=5,items=[{'pack':1,'qty':'1'}])
        self.assertEqual(core.client_debt_usd(self.db,5),250)
        self.write('handover','handovernonce1',amount='3.00')
        self.assertEqual(self.db.execute("SELECT status FROM handovers WHERE agent=2").fetchone()[0],'pending')
        with self.assertRaises(ValueError):
            self.write('handover','handovernonce2',amount='3.00')

    def test_client_creation_does_not_clone_phone_and_visit_is_real(self):
        with self.assertRaises(ValueError):
            self.write('client','clientnonce001',shop='Copy',person='A',phone='+998 90 123 45 67',
             address='Street',lat=40.55,lon=70.95,note='Test',status='interested')
        added=self.write('client','clientnonce002',shop='New real shop',person='A',
          phone='+998 90 999 88 77',address='Street',lat=40.55,lon=70.95,
          note='Map visit',status='interested')
        self.assertTrue(added['clientId']>5)
        self.write('visit','visitnonce001',clientId=added['clientId'],status='interested',note='Revisited')
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM client_visits WHERE client=?",
                                         (added['clientId'],)).fetchone()[0],2)
        self.assertTrue(self.write('client','clientnonce002',shop='New real shop',person='A',
          phone='+998 90 999 88 77',address='Street',lat=40.55,lon=70.95,
          note='Map visit',status='interested')['duplicate'])


if __name__=='__main__':unittest.main()
