"""Rahbar Web brauzer testi uchun lokal server: vaqtinchalik SQLite, soxta ma'lumot, Telegram API o'chirilgan.

Ishga tushganda birinchi qatorda JSON chiqaradi: {"url": ..., "login": ..., "password": ...}.
Production ma'lumotlariga tegmaydi (har safar yangi vaqtinchalik baza).
"""
import json
import os
import random
import socket
import sys
import tempfile
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
with socket.socket() as s:
    s.bind(('127.0.0.1', 0))
    PORT = s.getsockname()[1]
os.environ.update({'WEBHOOK_SECRET': 'test', 'WEBHOOK_BASE_URL': f'http://127.0.0.1:{PORT}', 'PORT': str(PORT)})
E2E = os.getenv('RW_E2E') == '1'   # admin-e2e.cjs: asosiy Admin, savdo xodimi, ombor qoldig'i, ishchi
if E2E:
    os.environ['ADMIN_IDS'] = '1'

import bot  # noqa: E402
import core  # noqa: E402
import web_auth  # noqa: E402

bot.TOKEN = '123:TEST'
bot.api = lambda *a, **k: {}
DB = os.path.join(tempfile.mkdtemp(prefix='rahbar-web-'), 'test.sqlite3')
db = core.connect(DB)
random.seed(11)
now = int(time.time())
db.executemany('INSERT INTO users(id,role,name) VALUES(?,?,?)',
               [(1, 'admin', 'Test Rahbar'), (2, 'agent', 'Ali'), (3, 'agent', 'Vali'), (4, 'cashier', 'Kassir')])
regions = ['Qo‘qon', 'Rishton', 'Buvayda']
src = 1000
for cid in range(1, 41):
    agent = 2 if cid % 2 else 3
    db.execute("""INSERT INTO clients(id,agent,name,shop_name,phone,address,region,lat,lon,created_ts)
        VALUES(?,?,?,?,?,?,?,?,?,?)""", (cid, agent, f'Mijoz {cid}', f'Do‘kon {cid}', f'+99890{cid:07d}', f'Ko‘cha {cid}',
                                         regions[cid % 3], 40.4 + random.random() * .3, 71.3 + random.random() * .5, now - random.randint(1, 60) * 86400))
    for _ in range(random.randint(0, 3)):
        src += 1
        ts = now - random.randint(0, 50) * 86400 - random.randint(0, 20000)
        cents = random.randint(5, 40) * 500
        db.execute("""INSERT INTO events(actor,agent,client,kind,pack,qty,amount,amount_usd,note,ts,source)
            VALUES(?,?,?,'delivery',1,?,0,?,'',?,?)""", (agent, agent, cid, cents // 1250 or 1, cents, ts, src))
        if random.random() < .5:
            src += 1
            db.execute("""INSERT INTO events(actor,agent,client,kind,pack,qty,amount,amount_usd,note,ts,source,pay_method)
                VALUES(?,?,?,'payment',0,0,0,?,'',?,?,'cash')""", (agent, agent, cid, cents // 2, ts + 3600, src))
    if random.random() < .5:
        db.execute("INSERT INTO client_visits(client,actor,status,note,followup,ts) VALUES(?,?,'active','Test tashrif',NULL,?)",
                   (cid, agent, now - random.randint(0, 8) * 86400))
sid = db.execute('INSERT INTO shifts(agent,start,"end") VALUES(2,?,NULL)', (now - 4 * 3600,)).lastrowid
for k in range(20):
    db.execute('INSERT INTO points(shift,ts,lat,lon,accuracy) VALUES(?,?,?,?,8)', (sid, now - 4 * 3600 + k * 600, 40.5 + k * .001, 71.6 + k * .001))
for i, st in enumerate(('new', 'preparing', 'loaded', 'delivered', 'rejected', 'new')):
    oid = db.execute("INSERT INTO orders(agent,client,status,note,source,ts,updated_ts) VALUES(2,?,?,'',?,?,?)",
                     (i + 1, st, 9000 + i, now - i * 3600, now - i * 3600)).lastrowid
    db.execute("INSERT INTO order_items(order_id,pack,custom_name,qty) VALUES(?,1,'',5)", (oid,))
db.execute("INSERT INTO handovers(agent,amount,amount_usd,status,cashier,source,ts,accepted_ts) VALUES(2,0,2500,'accepted',4,9100,?,?)", (now - 7200, now - 7000))
db.execute("INSERT INTO handovers(agent,amount,amount_usd,status,cashier,source,ts) VALUES(3,0,1200,'pending',NULL,9101,?)", (now - 600,))
if E2E:
    import hr
    import shop
    import warehouse as wh
    db.execute("INSERT INTO users(id,role,name) VALUES(5,'sales','Sotuvchi'),(6,'warehouse','Omborchi')")
    db.execute("INSERT INTO meta(key,value) VALUES('cashier_uzs_per_usd','12500') ON CONFLICT(key) DO UPDATE SET value=excluded.value")
    db.execute("INSERT INTO handovers(agent,amount,amount_usd,status,cashier,source,ts,accepted_ts) VALUES(2,0,2000000,'accepted',4,9102,?,?)", (now - 7200, now - 7000))
    shop.set_staff(db, 1, 5, list(shop.SELLER_PERMS), 5)
    pack = list(core.PRODUCTS)[0]
    shop.set_price(db, 1, pack, '10', '8')
    wh.receive(db, 6, pack, 50, source=9200)
    wid = hr.add_worker(db, 1, {'name': 'Ketgan Usta', 'salary': '4000000', 'salaryFrom': hr.this_month()})
    hr.set_active(db, 1, wid, False)
PASSWORD = 'test-' + str(random.randint(100000, 999999))
web_auth.issue_password(db, 1, 'qa-rahbar')
db.execute("UPDATE web_accounts SET pw_hash=? WHERE user_id=1", (web_auth.hash_password(PASSWORD),))
db.commit()
db.close()
print(json.dumps({'url': f'http://127.0.0.1:{PORT}/app/rahbar-web/', 'login': 'qa-rahbar', 'password': PASSWORD}), flush=True)
bot.serve_webhook(core.connect(DB, initialize=False), f'http://127.0.0.1:{PORT}')
