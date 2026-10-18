import base64
import io
import json
import os
import unittest
from unittest.mock import MagicMock, patch

from PIL import Image

import bot
import core
from test_manager_api import signed_data

MANAGER_ORIGIN = 'https://asman-manager-miniapp-test.onrender.com'


def jpeg_data_url():
    out = io.BytesIO()
    Image.new('RGB', (64, 48), (200, 40, 40)).save(out, 'JPEG')
    return 'data:image/jpeg;base64,' + base64.b64encode(out.getvalue()).decode()


class ProductPhotoTests(unittest.TestCase):
    """Mahsulot rasmi: rahbar/omborchi qo'yadi, agent, omborchi va rahbar ilovalarida ko'rinadi."""

    def setUp(self):
        self.db = core.connect(':memory:')
        self.db.executemany('INSERT INTO users(id,role,name) VALUES(?,?,?)',
                            [(1, 'admin', 'Rahbar'), (2, 'agent', 'Ali'), (3, 'cashier', 'Kassir'), (5, 'warehouse', 'Omborchi')])
        self.db.commit()
        self.pack = next(iter(core.PRODUCTS))
        env = patch.dict(os.environ, {'WEBHOOK_BASE_URL': 'https://bot.example.test'})
        env.start()
        self.addCleanup(env.stop)

    def tearDown(self):
        self.db.close()

    def test_only_admin_and_keeper_set_photo(self):
        self.assertGreater(core.set_product_photo(self.db, 1, self.pack, 'FILE-A', ts=100), 0)
        core.set_product_photo(self.db, 5, self.pack, 'FILE-B', ts=200)
        self.assertEqual(core.product_photo_file(self.db, self.pack), 'FILE-B')
        self.assertEqual(core.product_photo_versions(self.db), {self.pack: 200})
        for uid in (2, 3, 999):
            with self.assertRaises(ValueError):
                core.set_product_photo(self.db, uid, self.pack, 'FILE-X')
        with self.assertRaises(ValueError):
            core.set_product_photo(self.db, 1, 987654, 'FILE-X')
        core.set_product_photo(self.db, 1, self.pack, '')
        self.assertEqual(core.product_photo_versions(self.db), {})

    def test_photo_urls_attached_to_nested_products(self):
        core.set_product_photo(self.db, 1, self.pack, 'FILE-A', ts=321)
        other = next(p for p in core.PRODUCTS if p != self.pack)
        data = {'products': [{'pack': self.pack, 'name': 'A'}, {'pack': other, 'name': 'B'}],
                'warehouse': {'catalog': [{'pack': self.pack, 'name': 'A'}]}, 'moves': [{'pack': self.pack}]}
        bot.attach_product_photo_urls(self.db, data)
        url = data['products'][0]['photoUrl']
        self.assertIn('/map/product-photo/%d/' % self.pack, url)
        self.assertTrue(url.endswith('?v=321'))
        self.assertEqual(data['products'][0]['thumbUrl'], url + '&t=1')
        self.assertEqual(data['warehouse']['catalog'][0]['photoUrl'], url)
        self.assertNotIn('photoUrl', data['products'][1])
        self.assertNotIn('photoUrl', data['moves'][0])
        expires, sig = url.split('?')[0].rsplit('/', 2)[-2:]
        self.assertTrue(bot._map_valid('product-photo/%d' % self.pack, expires, sig))
        self.assertFalse(bot._map_valid('product-photo/%d' % other, expires, sig))

    def test_agent_dashboard_products_get_photo(self):
        import agent_api
        core.set_product_photo(self.db, 1, self.pack, 'FILE-A', ts=50)
        data = bot.attach_product_photo_urls(self.db, agent_api.dashboard(self.db, 2))
        shown = {p['pack']: p for p in data['products']}
        self.assertIn('photoUrl', shown[self.pack])

    def _handler(self):
        captured = {}

        def server(address, handler):
            captured['handler'] = handler
            return MagicMock()
        with patch.object(bot, 'HTTPServer', side_effect=server), patch.object(bot, 'api'), patch.object(bot, 'TOKEN', 'test-token'):
            bot.serve_webhook(self.db, 'https://example.test')
        return captured['handler']

    def _post(self, handler, path, payload, origin=None):
        raw = json.dumps(payload).encode()
        h = object.__new__(handler)
        h.path = path
        h.headers = {'Content-Length': str(len(raw))}
        if origin:
            h.headers['Origin'] = origin
        h.rfile = io.BytesIO(raw)
        result = {}
        h._reply = lambda code, body, ctype=None, extra_headers=None: result.update(code=code, data=json.loads(body))
        with patch.object(bot, 'TOKEN', 'test-token'):
            h.do_POST()
        return result

    def test_keeper_uploads_from_ombor_app_and_agent_cannot(self):
        handler = self._handler()
        image = jpeg_data_url()
        with patch.object(bot, 'upload_agent_camera_photo', return_value='TG-FILE-1') as upload:
            r = self._post(handler, '/api/warehouse', {'initData': signed_data('test-token', 5), 'action': 'product_photo',
                                                      'pack': self.pack, 'imageData': image})
            self.assertEqual(r['code'], 200, r)
            self.assertEqual(core.product_photo_file(self.db, self.pack), 'TG-FILE-1')
            shown = {p['pack']: p for p in r['data']['products']}
            self.assertIn('photoUrl', shown[self.pack])
            denied = self._post(handler, '/api/warehouse', {'initData': signed_data('test-token', 2), 'action': 'product_photo',
                                                           'pack': self.pack, 'imageData': image})
            self.assertEqual(denied['code'], 400)
            self.assertEqual(upload.call_count, 1)  # refused role never reaches Telegram
        big = self._post(handler, '/api/warehouse', {'initData': signed_data('test-token', 5), 'action': 'dashboard',
                                                    'pad': 'x' * 30000})
        self.assertEqual(big['code'], 401)

    def test_admin_uploads_and_removes_from_rahbar_app(self):
        handler = self._handler()
        admin = {'initData': signed_data('test-token', 1)}
        with patch.object(bot, 'upload_agent_camera_photo', return_value='TG-FILE-2'):
            r = self._post(handler, '/api/manager', {**admin, 'action': 'product_photo', 'pack': self.pack,
                                                    'imageData': jpeg_data_url()}, MANAGER_ORIGIN)
        self.assertEqual(r['code'], 200, r)
        cat = {p['pack']: p for p in r['data']['warehouse']['catalog']}
        self.assertIn('photoUrl', cat[self.pack])
        r = self._post(handler, '/api/manager', {**admin, 'action': 'product_photo', 'pack': self.pack, 'remove': True}, MANAGER_ORIGIN)
        self.assertEqual(r['code'], 200, r)
        self.assertEqual(core.product_photo_file(self.db, self.pack), '')
        big = self._post(handler, '/api/manager', {**admin, 'action': 'dashboard', 'pad': 'x' * 20000}, MANAGER_ORIGIN)
        self.assertEqual(big['code'], 400)

    def test_upload_trims_transparent_border_to_square_icon(self):
        # Mahsulot rasmlari 2000x2000, shaffof fonda, atrofi bo'sh: ikonkada mahsulot yirik ko'rinishi kerak.
        im = Image.new('RGBA', (2000, 2000), (0, 0, 0, 0))
        im.paste((30, 80, 160, 255), (700, 600, 1300, 1400))
        out = io.BytesIO()
        im.save(out, 'PNG')
        trimmed = Image.open(io.BytesIO(bot.trim_product_image(out.getvalue())))
        self.assertEqual(trimmed.format, 'JPEG')
        self.assertEqual(trimmed.width, trimmed.height)
        self.assertLessEqual(trimmed.width, 1080)
        rgb = trimmed.convert('RGB')
        self.assertGreater(min(rgb.getpixel((5, 5))), 240)  # transparent corner became white
        self.assertLess(rgb.getpixel((trimmed.width // 2, trimmed.height // 2))[0], 80)
        dark = sum(1 for p in rgb.getdata() if p[0] < 100)
        self.assertGreater(dark / (trimmed.width * trimmed.height), 0.6)  # object fills the icon
        with patch.object(bot, 'upload_agent_camera_photo', return_value='TG-TRIM') as upload:
            bot.product_photo_action(self.db, 1, {'pack': self.pack, 'imageData': jpeg_data_url()})
        sent = Image.open(io.BytesIO(upload.call_args.args[1]))
        self.assertEqual(sent.width, sent.height)

    def test_photo_route_serves_signed_image(self):
        handler = self._handler()
        core.set_product_photo(self.db, 1, self.pack, 'TG-FILE-3', ts=77)
        self.db.commit()
        url = bot.product_photo_link(self.pack, 77)
        path = url.split('bot.example.test', 1)[1]
        jpeg = base64.b64decode(jpeg_data_url().split(',', 1)[1])

        def get(p):
            h = object.__new__(handler)
            h.path = p
            h.headers = {}
            result = {}
            h._reply = lambda code, body=b'', ctype=None, extra_headers=None: result.update(code=code, body=body, ctype=ctype)
            h.do_GET()
            return result
        with patch.object(bot, 'customer_photo_bytes', return_value=jpeg) as fetch:
            r = get(path)
            self.assertEqual(r['code'], 200)
            self.assertEqual(r['ctype'], 'image/jpeg')
            fetch.assert_called_with('TG-FILE-3')
        self.assertEqual(get(path.replace('/%d/' % self.pack, '/%d/' % (self.pack + 1), 1))['code'], 410)


class ProductPhotoUiTests(unittest.TestCase):
    def read(self, rel):
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), rel), encoding='utf-8') as f:
            return f.read()

    def test_apps_show_and_upload_photos(self):
        manage = self.read('miniapps/rahbar-premium/manage.js')
        self.assertIn("api('product_photo'", manage)
        self.assertIn('prodImg(p)', manage)
        ombor = self.read('miniapps/ombor/index.html')
        self.assertIn("act('product_photo'", ombor)
        self.assertIn('pimg(p,col)', ombor)
        agent = self.read('miniapps/agent/index.html')
        self.assertIn('syncProdThumbs()', agent)
        self.assertIn('prodThumb(p)', agent)


if __name__ == '__main__':
    unittest.main()
