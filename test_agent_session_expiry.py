import hashlib
import hmac
import json
import time
import unittest
from urllib.parse import urlencode

import agent_api
import manager_api

TOKEN = '123456:TEST-TOKEN'


def signed_init_data(user_id, auth_date):
    fields = {'auth_date': str(auth_date), 'query_id': 'AAE', 'user': json.dumps({'id': user_id, 'first_name': 'T'})}
    check = '\n'.join(f'{k}={v}' for k, v in sorted(fields.items()))
    key = hmac.new(b'WebAppData', TOKEN.encode(), hashlib.sha256).digest()
    fields['hash'] = hmac.new(key, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(fields)


class AgentSessionExpiryTests(unittest.TestCase):
    """Agents keep the Mini App open for a whole shift; a 1-hour session silently broke it."""

    def setUp(self):
        self.now = int(time.time())

    def test_agent_session_lasts_a_work_day(self):
        self.assertEqual(agent_api.AGENT_MAX_AUTH_AGE, 12 * 3600)
        for hours in (0, 1.5, 5, 11.9):
            raw = signed_init_data(77, self.now - int(hours * 3600))
            self.assertEqual(agent_api.verify_init_data(raw, TOKEN, self.now), 77, hours)

    def test_agent_session_still_expires(self):
        raw = signed_init_data(77, self.now - 12 * 3600 - 5)
        with self.assertRaisesRegex(ValueError, 'muddati'):
            agent_api.verify_init_data(raw, TOKEN, self.now)

    def test_manager_and_cashier_keep_one_hour(self):
        raw = signed_init_data(5, self.now - 2 * 3600)
        with self.assertRaisesRegex(ValueError, 'muddati'):
            manager_api.verify_init_data(raw, TOKEN, self.now)
        self.assertEqual(manager_api.verify_init_data(signed_init_data(5, self.now - 600), TOKEN, self.now), 5)

    def test_signature_still_required(self):
        raw = signed_init_data(77, self.now - 3600).replace('first_name', 'first_namX')
        with self.assertRaises(ValueError):
            agent_api.verify_init_data(raw, TOKEN, self.now)

    def test_env_override_is_clamped(self):
        import os
        from unittest.mock import patch
        with patch.dict(os.environ, {'AGENT_SESSION_HOURS': '100'}):
            self.assertEqual(agent_api._agent_session_seconds(), 24 * 3600)
        with patch.dict(os.environ, {'AGENT_SESSION_HOURS': '0'}):
            self.assertEqual(agent_api._agent_session_seconds(), 3600)
        with patch.dict(os.environ, {'AGENT_SESSION_HOURS': 'abc'}):
            self.assertEqual(agent_api._agent_session_seconds(), 12 * 3600)

    def test_agent_miniapp_handles_expired_session(self):
        html = open('miniapps/agent/index.html', encoding='utf-8').read()
        self.assertIn('if(r.status===401){serverError.sessionExpired=true;markSessionExpired()}', html)
        self.assertIn('err.sessionExpired===true', html)          # expired writes go to the offline queue
        self.assertIn('canSync:function(){return !sessionExpired', html)  # no sync with a dead session
        self.assertIn('if(data&&!sessionExpired&&', html)          # polling stops
        self.assertIn('Telegram sessiyasi tugadi', html)


if __name__ == '__main__':
    unittest.main()
