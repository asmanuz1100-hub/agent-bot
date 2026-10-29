"""Yordamchi javobini o'zbekcha ovozga aylantirish (Azure Speech, uz-UZ neyron ovoz).

Kalit: AZURE_SPEECH_KEY va AZURE_SPEECH_REGION (server muhitida); ovoz: AZURE_VOICE (standart — Madina).
Kalit bo'lmasa audio qaytmaydi — ilova telefonning o'z ovozida o'qiydi (test rejimi).
"""
import base64
import logging
import os
import re
import urllib.error
import urllib.request
from xml.sax.saxutils import escape

MAX_TEXT = 1500
VOICES = ('uz-UZ-MadinaNeural', 'uz-UZ-SardorNeural')


def enabled():
    return bool(os.getenv('AZURE_SPEECH_KEY') and os.getenv('AZURE_SPEECH_REGION'))


def _plain(text):
    # Ovozda o'qilmaydigan belgilar: markdown yulduzchalari, band belgilari, emoji.
    text = re.sub(r'[*_#`>]+', ' ', str(text or ''))
    text = re.sub(r'^\s*[-•]\s*', '', text, flags=re.M)
    text = re.sub(r'[\U0001F000-\U0001FAFF☀-➿]', ' ', text)
    return ' '.join(text.split())[:MAX_TEXT]


def speak(text):
    """{'audio': base64 MP3 | None, 'voice': name | None}."""
    text = _plain(text)
    if not text:
        raise ValueError('O‘qiladigan matn yo‘q.')
    if not enabled():
        return {'audio': None, 'voice': None}
    voice = os.getenv('AZURE_VOICE') or VOICES[0]
    if voice not in VOICES:
        voice = VOICES[0]
    ssml = (f"<speak version='1.0' xml:lang='uz-UZ'><voice name='{voice}'>"
            f"{escape(text)}</voice></speak>")
    region = re.sub(r'[^a-z0-9]', '', os.environ['AZURE_SPEECH_REGION'].lower())
    req = urllib.request.Request(
        f'https://{region}.tts.speech.microsoft.com/cognitiveservices/v1', data=ssml.encode('utf-8'),
        headers={'Ocp-Apim-Subscription-Key': os.environ['AZURE_SPEECH_KEY'],
                 'Content-Type': 'application/ssml+xml',
                 'X-Microsoft-OutputFormat': 'audio-24khz-48kbitrate-mono-mp3',
                 'User-Agent': 'AIBI'})
    try:
        with urllib.request.urlopen(req, timeout=20) as res:
            audio = res.read(5_000_000)
    except (urllib.error.URLError, TimeoutError) as e:
        # Ovoz bo'lmasa ham javob matni ko'rinadi: ilova telefon ovoziga o'tadi.
        logging.warning('Azure TTS failed: %r', e)
        return {'audio': None, 'voice': None}
    return {'audio': base64.b64encode(audio).decode('ascii'), 'voice': voice}
