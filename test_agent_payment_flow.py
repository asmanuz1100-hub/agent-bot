"""Agent custody, atomic mixed currency receipt, orders and immutable handover history."""
import unittest
import test_uzs_card_payments as fixture
import agent_api
import cashier_api
import core

class AgentPaymentFlowTests(unittest.TestCase):
    setUp=fixture.UzsAndCardPaymentTests.setUp
    tearDown=fixture.UzsAndCardPaymentTests.tearDown
    pay=fixture.UzsAndCardPaymentTests.pay

    def test_card_is_held_and_only_owner_can_send(self):
        out=self.pay('held',currency='USD',amount='50',method='card')
        pid=out['cardPaymentId']
        self.assertNotIn('_notify',out)
        self.assertEqual(cashier_api.dashboard(self.db,3)['cardPending'],[])
        self.assertTrue(agent_api._uzs_cash_state(self.db,2)[2][0]['heldByAgent'])
        self.assertEqual(agent_api._period_totals(self.db,2,0,self.now)['cardPendingCount'],0)
        with self.assertRaises(ValueError):
            agent_api.mutate(self.db,4,'card_handover',{'paymentId':pid},'wrong_owner_01',self.now)
        with self.assertRaises(ValueError):core.decide_card_payment(self.db,3,pid)
        sent=agent_api.mutate(self.db,2,'card_handover',{'paymentId':pid},'send_held_0001',self.now)
        self.assertEqual(sent['_notify']['paymentId'],pid)
        self.assertEqual(len(cashier_api.dashboard(self.db,3)['cardPending']),1)
        again=agent_api.mutate(self.db,2,'card_handover',{'paymentId':pid},'send_held_0002',self.now)
        self.assertNotIn('_notify',again)
        core.decide_card_payment(self.db,3,pid)
        self.assertEqual(core.client_debt_usd(self.db,self.cid),95000)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM cashier_incomes').fetchone()[0],1)

    def test_mixed_cash_is_one_atomic_request_and_retry_is_safe(self):
        p={'clientId':self.cid,'parts':[{'currency':'USD','amount':'50','method':'cash'},
            {'currency':'UZS','amount':'120000','usd':'10','method':'cash'}]}
        out=agent_api.mutate(self.db,2,'payment',p,'mixed_cash_0001',self.now)
        self.assertEqual(len(out['_notify']['items']),2)
        self.assertEqual((core.cash_usd(self.db,2),core.cash_som(self.db,2)),(5000,120000))
        self.assertEqual(core.client_debt_usd(self.db,self.cid),94000)
        self.assertTrue(agent_api.mutate(self.db,2,'payment',p,'mixed_cash_0001',self.now)['duplicate'])
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM events WHERE kind='payment'").fetchone()[0],2)

    def test_invalid_second_part_leaves_no_first_payment(self):
        p={'clientId':self.cid,'parts':[{'currency':'USD','amount':'50'}, {'currency':'UZS','amount':'-5','usd':'10'}]}
        with self.assertRaises(ValueError):agent_api.mutate(self.db,2,'payment',p,'invalid_mixed_01',self.now)
        self.assertEqual(core.client_debt_usd(self.db,self.cid),100000)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM events WHERE kind='payment'").fetchone()[0],0)

    def test_mixed_card_preserves_shared_receipt_and_stays_held(self):
        p={'clientId':self.cid,'photoFileId':'AgACAgIAAxkBAAEreceipt01','parts':[
            {'currency':'USD','amount':'50','method':'card'},
            {'currency':'UZS','amount':'120000','usd':'10','method':'card'}]}
        agent_api.mutate(self.db,2,'payment',p,'mixed_card_0001',self.now)
        rows=self.db.execute('SELECT agent_held,photo FROM card_payments').fetchall()
        self.assertEqual(len(rows),2)
        self.assertTrue(all(r['agent_held'] and r['photo']==p['photoFileId'] for r in rows))
        self.assertEqual(cashier_api.dashboard(self.db,3)['cardPending'],[])

    def test_som_equivalent_and_dollars_are_not_double_booked(self):
        self.pay('som_review',currency='UZS',amount='3249000',usd='275.40',method='cash')
        self.pay('usd_review',currency='USD',amount='200',method='cash')
        som=agent_api.mutate(self.db,2,'handover',{'currency':'UZS','amount':'3249000'},'som_review_handover',self.now)
        dollars=agent_api.mutate(self.db,2,'handover',{'currency':'USD','amount':'200'},'usd_review_handover',self.now)
        self.assertEqual(core.cashier_balance_usd(self.db),0)
        for out in (som,dollars):
            hid=out['handoverId']
            cashier_api.review(self.db,3,hid)
            cashier_api.review(self.db,3,hid)
            core.accept(self.db,3,hid)
            with self.assertRaises(ValueError):core.accept(self.db,3,hid)
        flows=core.cashier_flows(self.db)
        self.assertEqual(flows['in_cash_uzs'],3249000)
        self.assertEqual(flows['in_cash_usd'],20000)
        self.assertEqual(core.cashier_balance_usd(self.db),47540)
        self.assertEqual((core.cash_som(self.db,2),core.cash_usd(self.db,2)),(0,0))
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM cashier_incomes').fetchone()[0],0)

    def test_orders_are_visible_to_the_creator_only(self):
        core.create_order(self.db,2,self.cid,[{'pack':1,'qty':2}],source=777001)
        self.assertEqual(len(agent_api._my_orders(self.db,2)),1)
        self.assertEqual(agent_api._my_orders(self.db,4),[])
        self.assertEqual(len(agent_api.quick_snapshot(self.db,2)['orders']),1)

    def test_accepted_handover_detail_is_read_only(self):
        self.pay('history',currency='USD',amount='50',method='cash')
        out=agent_api.mutate(self.db,2,'handover',{'currency':'USD','amount':'50'},'history_handover_1',self.now)
        hid=out['handoverId'];core.accept(self.db,3,hid,True)
        before=core.cashier_balance_usd(self.db)
        d=cashier_api.handover_detail(self.db,3,hid)
        self.assertEqual(d['handover']['status'],'accepted')
        self.assertIn('50.00',d['context'])
        self.assertEqual(core.cashier_balance_usd(self.db),before)
        with self.assertRaises(ValueError):cashier_api.handover_detail(self.db,2,hid)
        with self.assertRaises(ValueError):cashier_api.review(self.db,3,hid)

class PgAgentPaymentFlowTests(AgentPaymentFlowTests):
    @classmethod
    def setUpClass(cls):
        import os
        cls.url=os.getenv('TEST_DATABASE_URL')
        if not cls.url:raise unittest.SkipTest('TEST_DATABASE_URL not configured')

    def setUp(self):
        import os,uuid
        from unittest.mock import patch
        self.schema='agent_flow_'+uuid.uuid4().hex[:12]
        os.environ['DB_SCHEMA']=self.schema
        connect=core.connect
        with patch.object(core,'connect',side_effect=lambda _:connect(self.url)):
            super().setUp()

    def tearDown(self):
        import os
        try:
            self.db.rollback()
            self.db.execute(f'DROP SCHEMA "{self.schema}" CASCADE')
            self.db.commit()
        finally:
            self.db.close()
            os.environ.pop('DB_SCHEMA',None)

if __name__=='__main__':unittest.main()


class DuplicatePaymentGuardTests(unittest.TestCase):
    setUp=fixture.UzsAndCardPaymentTests.setUp
    tearDown=fixture.UzsAndCardPaymentTests.tearDown

    def _pay(self,nonce,now,**extra):
        p={'clientId':self.cid,'currency':'UZS','amount':'905000','usd':'76','method':'cash'}
        p.update(extra)
        return agent_api.mutate(self.db,2,'payment',p,nonce,now)

    def count(self):
        return self.db.execute("SELECT COUNT(*) FROM events WHERE kind='payment'").fetchone()[0]

    def test_same_payment_reentered_with_new_nonce_needs_confirmation(self):
        self._pay('dup_guard_0001',self.now)
        with self.assertRaises(agent_api.DuplicatePaymentError) as ctx:
            self.db.execute('SAVEPOINT t')
            try:self._pay('dup_guard_0002',self.now+60)
            finally:self.db.execute('ROLLBACK TO SAVEPOINT t')
        self.assertEqual(ctx.exception.code,'duplicate_payment')
        self.assertEqual(self.count(),1)
        self._pay('dup_guard_0002',self.now+60,confirmDuplicate=True)
        self.assertEqual(self.count(),2)

    def test_different_amount_or_old_payment_is_not_blocked(self):
        self._pay('dup_guard_0003',self.now)
        self.db.execute("UPDATE events SET ts=? WHERE kind='payment'",(self.now-agent_api.DUPLICATE_PAYMENT_WINDOW-1,))
        self._pay('dup_guard_0004',self.now,amount='900000')
        self._pay('dup_guard_0005',self.now)
        self.assertEqual(self.count(),3)

    def test_identical_parts_in_one_request_are_allowed(self):
        p={'clientId':self.cid,'parts':[{'currency':'USD','amount':'50','method':'cash'},
            {'currency':'USD','amount':'50','method':'cash'}]}
        agent_api.mutate(self.db,2,'payment',p,'dup_guard_0006',self.now)
        self.assertEqual(self.count(),2)


class AdminPaymentCancelTests(unittest.TestCase):
    setUp=fixture.UzsAndCardPaymentTests.setUp
    tearDown=fixture.UzsAndCardPaymentTests.tearDown

    def _pay(self,nonce,**extra):
        p={'clientId':self.cid,'currency':'UZS','amount':'905000','usd':'76','method':'cash','confirmDuplicate':True}
        p.update(extra)
        agent_api.mutate(self.db,2,'payment',p,nonce,self.now)
        return self.db.execute("SELECT MAX(id) FROM events WHERE kind='payment'").fetchone()[0]

    def test_duplicate_cash_payment_is_cancelled_with_trace(self):
        import corrections,manager_api
        self._pay('cancel_pay_0001');dup=self._pay('cancel_pay_0002')
        self.assertEqual(core.client_debt_usd(self.db,self.cid),100000-2*7600)
        self.assertEqual(core.cash_som(self.db,2),2*905000)
        detail=manager_api.client_detail(self.db,self.cid)
        self.assertTrue(all(e['canCancel'] for e in detail['events'] if e['kind']=='payment'))
        with self.assertRaises(ValueError):corrections.cancel_payment(self.db,2,dup,'agent o‘zi')
        corrections.cancel_payment(self.db,1,dup,'Takror kiritilgan')
        self.assertEqual(core.client_debt_usd(self.db,self.cid),100000-7600)
        self.assertEqual(core.cash_som(self.db,2),905000)
        self.assertEqual(self.db.execute("SELECT kind FROM events WHERE id=?",(dup,)).fetchone()[0],'cancelled_payment')
        self.assertTrue(corrections.is_voided(self.db,'payment',dup))
        with self.assertRaises(ValueError):corrections.cancel_payment(self.db,1,dup,'yana')
        self.assertNotIn(dup,[e['id'] for e in manager_api.client_detail(self.db,self.cid)['events']])

    def test_cannot_cancel_money_already_handed_to_cashier(self):
        import corrections
        eid=self._pay('cancel_pay_0003')
        self.db.execute("INSERT INTO handovers(agent,amount,amount_usd,status,source,ts) VALUES(2,?,0,'accepted',424242,?)",(905000*100,self.now))
        with self.assertRaises(ValueError):corrections.cancel_payment(self.db,1,eid,'Takror')
        self.assertEqual(self.db.execute("SELECT kind FROM events WHERE id=?",(eid,)).fetchone()[0],'payment')

    def test_manager_permission_for_payment_cancel(self):
        import perms
        self.assertEqual(perms.manager_perm('payment_cancel'),'cash.cancel')
