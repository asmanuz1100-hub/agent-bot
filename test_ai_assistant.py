"""Rahbar yordamchisi: savolni tushunish va javobni faqat tizim raqamlaridan tuzish (sun'iy intellektsiz)."""
import unittest

import ai_assistant
import test_executive  # faqat tayyor ma'lumot (setUp/seed)


class AssistantTests(unittest.TestCase):
    E = test_executive.ExecutiveTests
    setUp, ev, seed = E.setUp, E.ev, E.seed

    def ask(self, q):
        return ai_assistant.ask(self.db, q, now=self.now)['answer']

    def test_detect_topic_and_period(self):
        self.assertEqual(ai_assistant.detect('Bugun sotuv o‘sdimi?')[:2], ('sales', 'today'))
        self.assertEqual(ai_assistant.detect('Бугун савдо ўсдими')[:2], ('sales', 'today'))   # kirill
        self.assertEqual(ai_assistant.detect('haftalik tolovlar')[:2], ('payments', 'd7'))
        self.assertEqual(ai_assistant.detect('kecha qancha sotdik')[:2], ('sales', 'yesterday'))
        self.assertEqual(ai_assistant.detect('qarz qancha')[0], 'debt')
        self.assertEqual(ai_assistant.detect('ombor qoldig‘i')[0], 'stock')

    def test_sales_growth_yes_or_no_with_numbers(self):
        self.seed()   # bugun 70$, kecha shu soatgacha 100$
        a = self.ask('bugun sotuv o‘sdimi?')
        self.assertTrue(a.startswith('Yo‘q, kamaydi.'), a)
        self.assertIn('70 $', a)
        self.assertIn('-30.0%', a)
        self.assertIn('100 $', a)
        self.assertIn('To‘lovlar: 70 $', a)

    def test_debt_cash_agent(self):
        self.seed()
        self.assertIn('Umumiy qarz: 80 $', self.ask('qarz qancha?'))
        self.assertIn('Agentlardagi pul', self.ask('agentlardagi pul'))
        self.assertIn('Ali', self.ask('bugun eng yaxshi agent kim?'))

    def test_off_topic_and_errors(self):
        out = ai_assistant.ask(self.db, 'menga she’r yoz', now=self.now)
        self.assertTrue(out['offTopic'])
        self.assertEqual(out['answer'], ai_assistant.HELP)
        with self.assertRaises(ValueError):
            ai_assistant.ask(self.db, '  ')
        with self.assertRaises(ValueError):
            ai_assistant.ask(self.db, 'x' * 601)

    def test_every_topic_answers_on_empty_db(self):
        for q in ('bugun sotuv', 'tolovlar', 'tashriflar', 'yangi mijozlar', 'qarz', 'kassa', 'agentlar',
                  'eng kop sotilgan mahsulot', 'ombor', 'buyurtmalar', 'oylik savdo', 'kecha savdo'):
            self.assertTrue(self.ask(q), q)


if __name__ == '__main__':
    unittest.main()
