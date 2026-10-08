import unittest

import core
import profiles


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.db=core.connect(':memory:')
        self.db.executemany('INSERT INTO users(id,role,name) VALUES(?,?,?)',[(2,'agent','Ali'),(3,'cashier','Kassir')])

    def tearDown(self):
        self.db.close()

    def test_defaults_and_save(self):
        p=profiles.get(self.db,2)
        self.assertEqual((p['name'],p['phone'],p['hasPhoto'],p['roleLabel']),('Ali','',False,'Agent'))
        p=profiles.save(self.db,2,{'name':'  Ali   Valiyev ','phone':'+998 90 123 45 67'},photo_file='FILE_1',now=10)
        self.assertEqual((p['name'],p['phone'],p['hasPhoto'],p['updatedTs']),('Ali Valiyev','+998 90 123 45 67',True,10))
        self.assertEqual(profiles.photo_file_id(self.db,2),'FILE_1')
        self.assertEqual(profiles.photo_ids(self.db),{2})
        p=profiles.save(self.db,2,{'phone':''},now=11)
        self.assertEqual(p['phone'],'');self.assertTrue(p['hasPhoto'])
        p=profiles.save(self.db,2,{'removePhoto':True},now=12)
        self.assertFalse(p['hasPhoto']);self.assertEqual(profiles.photo_ids(self.db),set())

    def test_validation(self):
        with self.assertRaises(ValueError):profiles.save(self.db,3,{'name':'A'})
        with self.assertRaises(ValueError):profiles.save(self.db,3,{'phone':'abc'})
        with self.assertRaises(ValueError):profiles.get(self.db,99)


class PhotoThumbTests(unittest.TestCase):
    def test_thumbnail_is_small_jpeg_and_cached(self):
        import io
        from unittest.mock import patch
        from PIL import Image
        import bot
        buf=io.BytesIO();Image.new('RGB',(1600,1200),(40,120,200)).save(buf,'PNG');big=buf.getvalue()
        bot._THUMB_CACHE.clear()
        with patch.object(bot,'customer_photo_bytes',return_value=big) as fetch:
            t=bot.photo_response('file-x','t=1')
            self.assertEqual(bot.photo_content_type(t),'image/jpeg')
            self.assertLessEqual(max(Image.open(io.BytesIO(t)).size),320)
            self.assertEqual(bot.photo_response('file-x','t=1'),t)
            self.assertEqual(fetch.call_count,1)
            self.assertEqual(bot.photo_response('file-x',''),big)

    def test_user_photo_link_is_signed_and_stable(self):
        from unittest.mock import patch
        from urllib.parse import urlparse
        import bot
        with patch.object(bot,'TOKEN','local-test-token'),patch.dict(bot.os.environ,{'RENDER_EXTERNAL_URL':'https://example.test','WEBHOOK_BASE_URL':''}):
            a=bot.user_photo_link(7,now=1000);b=bot.user_photo_link(7,now=1000+3600)
            self.assertEqual(a,b)
            exp,sig=urlparse(a).path.split('/')[-2:]
            self.assertTrue(bot._map_valid('user-photo/7',exp,sig,1000))
            self.assertFalse(bot._map_valid('user-photo/8',exp,sig,1000))


class ProfileApiTests(unittest.TestCase):
    def setUp(self):
        self.db=core.connect(':memory:')
        self.db.executemany('INSERT INTO users(id,role,name) VALUES(?,?,?)',[(2,'agent','Ali'),(3,'cashier','Kassir')])

    def tearDown(self):
        self.db.close()

    def test_profile_save_uploads_photo_and_attaches_links(self):
        import base64,io
        from unittest.mock import patch
        from PIL import Image
        import bot
        buf=io.BytesIO();Image.new('RGB',(400,300),(200,80,40)).save(buf,'JPEG');data='data:image/jpeg;base64,'+base64.b64encode(buf.getvalue()).decode()
        with patch.object(bot,'TOKEN','local-test-token'),patch.dict(bot.os.environ,{'RENDER_EXTERNAL_URL':'https://example.test','WEBHOOK_BASE_URL':''}),\
             patch.object(bot,'upload_agent_camera_photo',return_value='FILE_9') as up:
            r=bot.profile_action(self.db,2,'profile_save',{'imageData':data,'profile':{'phone':'+998901112233'}})
            self.assertEqual(up.call_args[0][0],2)
            self.assertTrue(r['profile']['hasPhoto']);self.assertIn('/map/user-photo/2/',r['profile']['photoUrl'])
            self.assertEqual(r['profile']['phone'],'+998901112233')
            r=bot.profile_action(self.db,3,'profile',{})
            self.assertIsNone(r['profile']['photoUrl'])
            data={'agents':[{'id':2,'name':'Ali'},{'id':4,'name':'X'}],'agent':{'id':2}}
            bot.attach_staff_photos(self.db,data)
            self.assertIn('user-photo/2',data['agents'][0]['photoUrl']);self.assertNotIn('photoUrl',data['agents'][1])
            self.assertIn('photoUrl',data['agent'])

    def test_thumb_persists_in_database(self):
        import io
        from unittest.mock import patch
        from PIL import Image
        import bot
        buf=io.BytesIO();Image.new('RGB',(900,900),(10,10,10)).save(buf,'PNG');big=buf.getvalue()
        bot._THUMB_CACHE.clear()
        with patch.object(bot,'customer_photo_bytes',return_value=big) as fetch:
            t=bot.photo_response('file-db','t=1',self.db)
            bot._THUMB_CACHE.clear()
            self.assertEqual(bot.photo_response('file-db','t=1',self.db),t)
            self.assertEqual(fetch.call_count,1)


if __name__=='__main__':
    unittest.main()
