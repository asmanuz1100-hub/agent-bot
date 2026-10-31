"""Har kuni korxona ma'lumotlari backup'ini Gmail'ga yuborish.

Faqat ma'lumotlar ZIP'i (jadvallar; full_backup.build_archives, rasmsiz) — dastur kodi yo'q.
Sozlash (Render env):
  BACKUP_EMAIL_TO     — qabul qiluvchi manzil(lar), vergul bilan
  SMTP_USER           — yuboruvchi Gmail manzili
  SMTP_PASSWORD       — Gmail "App password" (oddiy parol emas, 16 belgi)
  SMTP_HOST/SMTP_PORT — standart: smtp.gmail.com / 465
  BACKUP_HOUR         — Toshkent vaqti bilan soat, standart 3
Bir nechta server nusxasi bo'lsa ham kuniga bitta xat: kun meta jadvalida band qilinadi.
"""
import logging
import os
import smtplib
import ssl
import threading
import time
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path
from zoneinfo import ZoneInfo

import full_backup

TZ=ZoneInfo('Asia/Tashkent')
MAX_ATTACH=20*1024*1024        # Gmail cheklovi 25 MB; base64 hajmni ~33% oshiradi
META_KEY='email_backup_day'
RETRY_SECONDS=3600


def config(env=None):
    env=os.environ if env is None else env
    to=[x.strip() for x in (env.get('BACKUP_EMAIL_TO') or '').split(',') if x.strip()]
    user=(env.get('SMTP_USER') or '').strip()
    password=(env.get('SMTP_PASSWORD') or '').replace(' ','')
    if not (to and user and password):return None
    return {'to':to,'user':user,'password':password,
            'host':(env.get('SMTP_HOST') or 'smtp.gmail.com').strip(),
            'port':int(env.get('SMTP_PORT') or 465),
            'hour':min(23,max(0,int(env.get('BACKUP_HOUR') or 3)))}


def claim_day(db,day):
    """Bugungi backup'ni band qiladi; boshqa nusxa allaqachon olgan bo'lsa False."""
    cur=db.execute('''INSERT INTO meta(key,value) VALUES(?,?)
        ON CONFLICT(key) DO UPDATE SET value=excluded.value WHERE meta.value<>excluded.value''',(META_KEY,day))
    db.commit()
    return cur.rowcount==1


def release_day(db,day):
    db.execute('DELETE FROM meta WHERE key=? AND value=?',(META_KEY,day));db.commit()


def build_message(cfg,path,summary,day):
    msg=EmailMessage()
    msg['Subject']=f'ASMAN backup {day}'
    msg['From']=cfg['user'];msg['To']=', '.join(cfg['to'])
    data=Path(path).read_bytes()
    rows={k:v for k,v in (summary.get('tables') or {}).items() if isinstance(v,int)}
    lines=[f'Korxona ma’lumotlari backup’i — {day} (Toshkent vaqti).',
           f'Jadvallar: {len(rows)}, yozuvlar: {sum(int(v or 0) for v in rows.values())}.' if rows else '',
           'Rasmlar va dastur kodi kiritilmagan. Parollar va maxfiy kalitlar arxivda yo‘q.']
    if len(data)>MAX_ATTACH:
        lines.append(f'⚠️ Arxiv {len(data)//1048576} MB — Gmail chegarasidan katta, ilova qilinmadi. Rahbar panelidan yuklab oling.')
        msg.set_content('\n'.join(x for x in lines if x))
    else:
        msg.set_content('\n'.join(x for x in lines if x))
        msg.add_attachment(data,maintype='application',subtype='zip',filename=Path(path).name)
    return msg


def send(cfg,msg):
    with smtplib.SMTP_SSL(cfg['host'],cfg['port'],context=ssl.create_default_context(),timeout=60) as smtp:
        smtp.login(cfg['user'],cfg['password'])
        smtp.send_message(msg)


def run_once(db,cfg,day):
    paths,summary=full_backup.build_archives(db,None)
    try:
        send(cfg,build_message(cfg,paths[0],summary,day))
    finally:
        full_backup.cleanup(paths)


def loop(open_db,cfg,stop=None,tick=600):
    stop=stop or threading.Event()
    while not stop.is_set():
        now=datetime.now(TZ)
        wait=tick
        if now.hour>=cfg['hour']:
            day=now.strftime('%Y-%m-%d')
            db=None
            try:
                db=open_db()
                if claim_day(db,day):
                    try:
                        run_once(db,cfg,day)
                        logging.info('Email backup sent day=%s',day)
                    except Exception:
                        logging.exception('Email backup failed day=%s',day)
                        try:release_day(db,day)
                        except Exception:logging.exception('Email backup release failed')
                        wait=RETRY_SECONDS
            except Exception:
                logging.exception('Email backup tick failed')
            finally:
                if db is not None:
                    try:db.close()
                    except Exception:pass
        stop.wait(wait)


def start(open_db):
    cfg=config()
    if not cfg:
        logging.info('Email backup off: BACKUP_EMAIL_TO / SMTP_USER / SMTP_PASSWORD not set')
        return None
    t=threading.Thread(target=loop,args=(open_db,cfg),daemon=True,name='email-backup')
    t.start()
    return t
