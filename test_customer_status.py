"""Customer visit outcome, follow-up date and history regression tests."""
import json
import re
import time
import unittest
from datetime import date,timedelta
from unittest.mock import patch
import bot
import core
import reports
import customer_status as cs

class CustomerStatusTests(unittest.TestCase):
    def setUp(self):
        self.db=core.connect(':memory:')
        self.db.executemany('INSERT INTO users(id,role,name) VALUES(?,?,?)',[(1,'admin','Admin'),(2,'agent','Old Agent'),(3,'agent','Other Agent')])
        self.db.execute('INSERT INTO shifts(agent,start) VALUES(2,?)',(int(time.time())-10,))
        core.point(self.db,2,{'message_id':500,'date':int(time.time()),'location':{'latitude':40.5,'longitude':71.4,'live_period':3600}})
    def tearDown(self):self.db.close()
    def msg(self,i,text=None,location=None,photo=None,uid=2):
        m={'message_id':i,'date':int(time.time()),'from':{'id':uid},'chat':{'id':uid,'type':'private'}}
        if text is not None:m['text']=text
        if location is not None:m['location']=location
        if photo is not None:m['photo']=[{'file_id':photo}]
        return {'update_id':i,'message':m}
    def new_shop(self,base,status,followup=None):
        inputs=[('🏪 Мижоз қўшиш',{}),(None,{'location':{'latitude':40.6,'longitude':71.3}}),
                (None,{'photo':'photo'}),('+99890123'+str(base)[-4:],{}),
                ('Исм '+str(base),{}),('Дўкон '+str(base),{}),('Манзил',{}),
                ('Мижоз билан таклиф ҳақида гаплашилди',{}),
                ('🗺 Товарсиз харитага сақлаш',{}),(cs.LABELS[status],{})]
        if followup:inputs.append((followup,{}))
        inputs.append(('✅ Тасдиқлаш',{}))
        with patch.object(bot,'send'):
            for i,(msg,kw) in enumerate(inputs,base):
                bot.handle(self.db,self.msg(i,msg,**kw))
        return self.db.execute('SELECT id FROM clients WHERE name=?',('Исм '+str(base),)).fetchone()[0]
    @staticmethod
    def shops(data):
        m=re.search(r'<script id="data" type="application/json">(.*?)</script>',data.decode(),re.S)
        return json.loads(m.group(1))['shops']
    def test_declined_and_waiting_visible_in_customer_list_and_maps(self):
        date_due=(date.today()+timedelta(days=8)).isoformat()
        with patch.object(bot,'ADMINS',{1}):
            declined=self.new_shop(5100,'declined')
            waiting=self.new_shop(5200,'waiting',date_due)
            self.assertEqual(cs.summary(self.db,declined,True)['icon'],'❌')
            self.assertEqual(cs.summary(self.db,waiting,True)['followup'],date_due)
            with patch.object(bot,'send') as send:
                bot.report_clients(self.db,2)
                buttons=' '.join(str(item) for row in send.call_args.args[2] for item in row)
                self.assertIn('❌',buttons)
                self.assertIn('⏳',buttons)
                bot.show_client_card(self.db,2,waiting)
                self.assertIn(date_due,send.call_args.args[1])
                self.assertIn('Мижоз билан таклиф',send.call_args.args[1])
            agent_map=self.shops(reports.agent_clients_map_html(self.db,2))
            self.assertEqual({s['icon'] for s in agent_map},{'❌','⏳'})
            self.assertIn(date_due,next(s for s in agent_map if s['id']==waiting)['followup'])
            self.assertEqual({s['icon'] for s in self.shops(reports.admin_clients_map_html(self.db,1))},{'❌','⏳'})
            for cid in (declined,waiting):
                self.assertEqual(core.client_debt_usd(self.db,cid),0)
                self.assertEqual(self.db.execute('SELECT COUNT(*) FROM events WHERE client=?',(cid,)).fetchone()[0],0)
    def test_followup_visit_records_conversation_and_preserves_agent_history(self):
        due=(date.today()+timedelta(days=12)).isoformat()
        with patch.object(bot,'ADMINS',{1}):
            cid=self.new_shop(5300,'declined')
            with patch.object(bot,'send'),patch.object(bot,'BOT_USERNAME','agent_bot_test'):
                payload=bot.agent_action_payload('v',2,cid)
                with self.assertRaises(ValueError):bot.open_agent_client_action(self.db,3,payload)
                bot.open_agent_client_action(self.db,2,payload)
                for i,t in enumerate([cs.LABELS['waiting'],'Янги ойдан олади',due,'✅ Тасдиқлаш'],5340):
                    bot.handle(self.db,self.msg(i,t))
            outcome=cs.summary(self.db,cid,True)
            self.assertEqual(outcome['status'],'waiting')
            self.assertEqual(outcome['followup'],due)
            self.assertIn('Янги ойдан олади',cs.timeline_text(self.db,cid))
            self.assertIn('Мижоз билан таклиф',cs.timeline_text(self.db,cid))
            self.assertEqual(self.db.execute('SELECT COUNT(*) FROM client_visits WHERE client=?',(cid,)).fetchone()[0],2)
            self.db.execute('UPDATE shifts SET end=? WHERE agent=? AND end IS NULL',(int(time.time()),2))
            core.transfer_agent_account(self.db,1,2,4)
            self.assertEqual(self.db.execute('SELECT agent FROM clients WHERE id=?',(cid,)).fetchone()[0],4)
            with patch.object(bot,'send') as send:
                bot.show_client_card(self.db,4,cid)
                self.assertIn('Old Agent',send.call_args.args[1])
                self.assertIn('Янги ойдан олади',send.call_args.args[1])
            self.assertEqual(core.client_debt_usd(self.db,cid),0)
    def test_waiting_requires_valid_followup_and_other_agent_cannot_edit(self):
        cid=self.new_shop(5400,'interested')
        with self.assertRaises(ValueError):cs.add_visit(self.db,2,cid,'waiting','Кейин',None)
        with self.assertRaises(ValueError):cs.add_visit(self.db,3,cid,'declined','Йўқ')
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM client_visits WHERE client=?',(cid,)).fetchone()[0],1)
        self.assertEqual(core.client_debt_usd(self.db,cid),0)
if __name__=='__main__':unittest.main()
