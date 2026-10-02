import importlib
import os
import unittest
from unittest.mock import patch

import bot


class SelfHostedMiniAppTests(unittest.TestCase):
    """Rahbar, Agent and Rahbar Premium Mini Apps are served by the bot itself under /app/<name>/."""

    def test_all_live_miniapps_are_in_repo(self):
        for app in ('rahbar', 'agent', 'rahbar-premium'):
            code, body, ctype, headers = bot.miniapp_response(f'/app/{app}/')
            self.assertEqual(code, 200, app)
            self.assertTrue(ctype.startswith('text/html'), app)
            self.assertEqual(headers['Cache-Control'], 'no-cache')
            self.assertIn(b'<html', body.lower())

    def test_miniapps_call_same_origin_api(self):
        for rel in ('agent/index.html', 'rahbar/index.html', 'rahbar-premium/real-data.js'):
            text = (bot.MINIAPP_DIR / rel).read_text(encoding='utf-8')
            self.assertNotIn('asman-agent-test.onrender.com', text, rel)
        self.assertIn('var API="/api/agent"', (bot.MINIAPP_DIR / 'agent/index.html').read_text(encoding='utf-8'))
        self.assertIn('var API="/api/manager"', (bot.MINIAPP_DIR / 'rahbar/index.html').read_text(encoding='utf-8'))

    def test_assets_and_content_types(self):
        code, body, ctype, headers = bot.miniapp_response('/app/agent/vendor/leaflet/leaflet.js')
        self.assertEqual((code, ctype), (200, 'application/javascript; charset=utf-8'))
        self.assertEqual(headers['Cache-Control'], 'public, max-age=3600')
        code, _, ctype, headers = bot.miniapp_response('/app/agent/sw.js')
        self.assertEqual((code, headers['Cache-Control']), (200, 'no-cache'))
        code, _, ctype, _ = bot.miniapp_response('/app/agent/vendor/leaflet/images/marker-icon.png')
        self.assertEqual((code, ctype), (200, 'image/png'))

    def test_redirect_adds_trailing_slash_and_keeps_query(self):
        code, _, _, headers = bot.miniapp_response('/app/agent', 'v=1')
        self.assertEqual(code, 301)
        self.assertEqual(headers['Location'], '/app/agent/?v=1')

    def test_path_traversal_and_hidden_files_are_blocked(self):
        for path in ('/app/agent/../../bot.py', '/app/agent/..%2f..%2fbot.py', '/app/../bot.py',
                     '/app/agent/.env', '/app/agent//index.html', '/app/agent/vendor/../../../core.py',
                     '/app/AGENT/', '/app/nope/', '/app/agent/missing.js', '/app/agent/\\..\\bot.py',
                     '/app/agent/index.html\x00.png'):
            self.assertEqual(bot.miniapp_response(path)[0], 404, path)

    def test_default_urls_point_to_this_service(self):
        base = bot.PUBLIC_BASE_URL
        self.assertTrue(bot.AGENT_MINIAPP_URL.startswith(base + '/app/agent/?v='))
        self.assertTrue(bot.MANAGER_MINIAPP_URL.startswith(base + '/app/rahbar/?v='))
        self.assertTrue(bot.MANAGER_PREMIUM_TEST_URL.startswith(base + '/app/rahbar-premium/?v='))
        self.assertIn(bot._url_origin(base), bot.SELF_MINIAPP_ORIGINS)

    def test_url_rules(self):
        env = {'RENDER_EXTERNAL_URL': 'https://asman-agent-test.onrender.com'}
        with patch.dict(os.environ, env, clear=False):
            for k in ('SELF_HOSTED_MINIAPPS', 'AGENT_MINIAPP_URL', 'WEBHOOK_BASE_URL'):
                os.environ.pop(k, None)
            # legacy static-site URL in env is redirected to the self-hosted copy
            os.environ['AGENT_MINIAPP_URL'] = 'https://asman-agent-miniapp-v2-test.onrender.com/?v=old'
            self.assertEqual(bot._miniapp_url('AGENT_MINIAPP_URL', 'x', 'agent', 'v9'),
                             'https://asman-agent-test.onrender.com/app/agent/?v=v9'
                             if bot.PUBLIC_BASE_URL == 'https://asman-agent-test.onrender.com'
                             else bot.PUBLIC_BASE_URL + '/app/agent/?v=v9')
            # any other explicit URL is respected
            os.environ['AGENT_MINIAPP_URL'] = 'https://example.org/agent/'
            self.assertEqual(bot._miniapp_url('AGENT_MINIAPP_URL', 'x', 'agent', 'v9'), 'https://example.org/agent/')
            # explicitly empty disables the button
            os.environ['AGENT_MINIAPP_URL'] = ''
            self.assertEqual(bot._miniapp_url('AGENT_MINIAPP_URL', 'x', 'agent', 'v9'), '')
            os.environ.pop('AGENT_MINIAPP_URL')

    def test_kill_switch_restores_old_static_sites(self):
        with patch.dict(os.environ, {'SELF_HOSTED_MINIAPPS': '0'}, clear=False):
            for k in ('AGENT_MINIAPP_URL', 'MANAGER_MINIAPP_URL', 'MANAGER_PREMIUM_TEST_URL'):
                os.environ.pop(k, None)
            reloaded = importlib.reload(bot)
            try:
                self.assertIn('asman-agent-miniapp-v2-test.onrender.com', reloaded.AGENT_MINIAPP_URL)
                self.assertIn('asman-manager-miniapp-test.onrender.com', reloaded.MANAGER_MINIAPP_URL)
                self.assertIn('asman-rahbar-uploaded-test.onrender.com', reloaded.MANAGER_PREMIUM_TEST_URL)
            finally:
                pass
        importlib.reload(bot)

    def test_legacy_static_origins_still_allowed_during_transition(self):
        src = open('bot.py', encoding='utf-8').read()
        for origin in ('https://asman-manager-miniapp-test.onrender.com', 'https://asman-rahbar-uploaded-test.onrender.com',
                       'https://asman-agent-miniapp-v2-test.onrender.com'):
            self.assertIn(origin, src)
        self.assertEqual(src.count('}|SELF_MINIAPP_ORIGINS'), 2)


if __name__ == '__main__':
    unittest.main()
