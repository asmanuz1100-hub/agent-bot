"""Yordamchi ovozi (Azure uz-UZ): kalitsiz test rejimi va so'rov shakli (soxta tarmoq bilan)."""
import base64
import os
import unittest
import unittest.mock

import voice


class Res:
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def read(self, n): return b'ID3mp3'


class VoiceTests(unittest.TestCase):
    def test_without_key_returns_no_audio(self):
        with unittest.mock.patch.dict(os.environ, {'AZURE_SPEECH_KEY': '', 'AZURE_SPEECH_REGION': ''}):
            self.assertEqual(voice.speak('Labbay'), {'audio': None, 'voice': None})
        with self.assertRaises(ValueError):
            voice.speak('  ** ')

    def test_azure_request_uses_uzbek_voice_and_escapes_text(self):
        sent = {}

        def urlopen(req, timeout):
            sent['url'], sent['key'], sent['body'] = req.full_url, req.get_header('Ocp-apim-subscription-key'), req.data.decode()
            return Res()
        env = {'AZURE_SPEECH_KEY': 'k', 'AZURE_SPEECH_REGION': 'westeurope', 'AZURE_VOICE': 'uz-UZ-SardorNeural'}
        with unittest.mock.patch.dict(os.environ, env), unittest.mock.patch.object(voice.urllib.request, 'urlopen', urlopen):
            out = voice.speak('**Bugun** 16 dona <b> & 2 ta 🙂')
        self.assertEqual(base64.b64decode(out['audio']), b'ID3mp3')
        self.assertEqual(out['voice'], 'uz-UZ-SardorNeural')
        self.assertEqual(sent['url'], 'https://westeurope.tts.speech.microsoft.com/cognitiveservices/v1')
        self.assertEqual(sent['key'], 'k')
        self.assertIn("<voice name='uz-UZ-SardorNeural'>Bugun 16 dona &lt;b &amp; 2 ta</voice>", sent['body'])


if __name__ == '__main__':
    unittest.main()
