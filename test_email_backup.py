"""Har kunlik Gmail backup: sozlama, kunni band qilish, xat tarkibi (haqiqiy SMTP'siz)."""
import os
import tempfile
import threading
import unittest
import zipfile
from unittest import mock

import core
import email_backup

ENV={'BACKUP_EMAIL_TO':'a@example.com, b@example.com','SMTP_USER':'bot@gmail.com','SMTP_PASSWORD':'abcd efgh ijkl mnop'}


class EmailBackupTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=os.path.join(self.tmp.name,'b.sqlite3')
        self.db=core.connect(self.path)
        self.db.execute("INSERT INTO users(id,role,name) VALUES(1,'admin','Rahbar')")
        self.db.commit()

    def tearDown(self):
        self.db.close();self.tmp.cleanup()

    def test_config_needs_all_three_settings(self):
        self.assertIsNone(email_backup.config({}))
        self.assertIsNone(email_backup.config({**ENV,'SMTP_PASSWORD':''}))
        cfg=email_backup.config(ENV)
        self.assertEqual(cfg['to'],['a@example.com','b@example.com'])
        self.assertEqual((cfg['password'],cfg['host'],cfg['port'],cfg['hour']),('abcdefghijklmnop','smtp.gmail.com',465,3))

    def test_day_is_claimed_once(self):
        self.assertTrue(email_backup.claim_day(self.db,'2026-10-28'))
        self.assertFalse(email_backup.claim_day(self.db,'2026-10-28'))
        email_backup.release_day(self.db,'2026-10-28')
        self.assertTrue(email_backup.claim_day(self.db,'2026-10-28'))
        self.assertTrue(email_backup.claim_day(self.db,'2026-10-29'))

    def test_message_has_data_zip_without_photos_or_secrets(self):
        sent=[]
        with mock.patch.object(email_backup,'send',lambda cfg,msg:sent.append(msg)):
            email_backup.run_once(self.db,email_backup.config(ENV),'2026-10-28')
        msg=sent[0]
        self.assertEqual(msg['Subject'],'ASMAN backup 2026-10-28')
        self.assertEqual(msg['To'],'a@example.com, b@example.com')
        att=[p for p in msg.iter_attachments()]
        self.assertEqual(len(att),1)
        data=att[0].get_payload(decode=True)
        with tempfile.NamedTemporaryFile(suffix='.zip') as f:
            f.write(data);f.flush()
            names=zipfile.ZipFile(f.name).namelist()
        self.assertTrue(any('users' in n for n in names),names)
        self.assertFalse(any(n.startswith('photos/') for n in names))
        self.assertFalse(any('web_accounts' in n for n in names))

    def test_failed_send_releases_day_for_retry(self):
        cfg={**email_backup.config(ENV),'hour':0}
        stop=threading.Event()
        def boom(*a):
            stop.set();raise OSError('smtp down')
        with mock.patch.object(email_backup,'send',boom):
            email_backup.loop(lambda:core.connect(self.path,initialize=False),cfg,stop=stop,tick=0)
        self.assertIsNone(self.db.execute('SELECT value FROM meta WHERE key=?',(email_backup.META_KEY,)).fetchone())


if __name__=='__main__':
    unittest.main()
