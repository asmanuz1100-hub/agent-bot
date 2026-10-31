"""Login + password for the Rahbar web panel (computer browser, no Telegram).

The admin gets a login and a one-time password from the bot (/webparol) and can
change the password in the panel. Passwords are stored as PBKDF2-SHA256 hashes; the
browser keeps a random session token and only its SHA-256 is stored here.
"""
import hashlib
import hmac
import re
import secrets
import time
from core import PostgresDB

SESSION_DAYS=30
MAX_FAILS=5
LOCK_SECONDS=15*60
TOUCH_SECONDS=300
OTP_SECONDS=5*60
OTP_TRIES=5
DEVICE_DAYS=30
_LOGIN=re.compile(r'[a-z0-9][a-z0-9._-]{2,31}')
_ALPHABET='abcdefghjkmnpqrstuvwxyz23456789'

SCHEMA='''
CREATE TABLE IF NOT EXISTS web_accounts(user_id INTEGER PRIMARY KEY, login TEXT NOT NULL UNIQUE, pw_hash TEXT NOT NULL, updated_ts INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS web_sessions(token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL, created_ts INTEGER NOT NULL, expires_ts INTEGER NOT NULL, last_ts INTEGER NOT NULL DEFAULT 0, agent TEXT NOT NULL DEFAULT '');
CREATE INDEX IF NOT EXISTS idx_web_sessions_user ON web_sessions(user_id);
CREATE TABLE IF NOT EXISTS web_login_fails(login TEXT PRIMARY KEY, fails INTEGER NOT NULL DEFAULT 0, locked_until INTEGER NOT NULL DEFAULT 0, ts INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS web_otp(challenge_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL, code_hash TEXT NOT NULL, expires_ts INTEGER NOT NULL, tries INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS web_devices(device_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL, expires_ts INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS idx_web_devices_user ON web_devices(user_id);
'''
PG_SCHEMA=SCHEMA.replace('INTEGER PRIMARY KEY','BIGINT PRIMARY KEY').replace('user_id INTEGER','user_id BIGINT').replace('_ts INTEGER','_ts BIGINT').replace('locked_until INTEGER','locked_until BIGINT').replace('expires_ts INTEGER','expires_ts BIGINT').replace(' ts INTEGER',' ts BIGINT')


def init(db):
    if isinstance(db,PostgresDB):
        for stmt in PG_SCHEMA.split(';'):
            if stmt.strip():db.execute(stmt)
    else:
        db.executescript(SCHEMA)


def _now(now):
    return int(time.time() if now is None else now)


PBKDF2_ROUNDS=310_000


def hash_password(password,salt=None,rounds=PBKDF2_ROUNDS):
    salt=salt or secrets.token_bytes(16)
    digest=hashlib.pbkdf2_hmac('sha256',password.encode('utf-8'),salt,rounds)
    return f'pbkdf2_sha256${rounds}${salt.hex()}${digest.hex()}'


def check_password(password,stored):
    try:
        algo,rounds,salt,digest=stored.split('$')
        if algo!='pbkdf2_sha256':return False
        got=hashlib.pbkdf2_hmac('sha256',password.encode('utf-8'),bytes.fromhex(salt),int(rounds))
        return hmac.compare_digest(got.hex(),digest)
    except (ValueError,TypeError,AttributeError):
        return False


def _token_hash(token):
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def new_password():
    return '-'.join(''.join(secrets.choice(_ALPHABET) for _ in range(4)) for _ in range(3))


def _validate_new(password):
    if not isinstance(password,str) or not 8<=len(password)<=128:
        raise ValueError('Parol 8–128 belgidan iborat bo‘lsin.')
    if password.strip()!=password:
        raise ValueError('Parol boshida yoki oxirida bo‘sh joy bo‘lmasin.')


def account(db,uid):
    return db.execute('SELECT user_id,login,updated_ts FROM web_accounts WHERE user_id=?',(int(uid),)).fetchone()


def issue_password(db,uid,login=None,now=None,password=None):
    """Create or reset the web account of `uid`. Returns (login, plain password).

    Every existing browser session of this user is signed out."""
    now=_now(now)
    current=account(db,uid)
    login=(login or (current['login'] if current else '') or f'rahbar{int(uid)}').strip().lower()
    if not _LOGIN.fullmatch(login):
        raise ValueError('Login 3–32 belgi: lotin harflari, raqam, nuqta, chiziqcha.')
    taken=db.execute('SELECT user_id FROM web_accounts WHERE login=?',(login,)).fetchone()
    if taken and int(taken['user_id'])!=int(uid):
        raise ValueError('Bu login band. Boshqasini tanlang.')
    if password:_validate_new(password)          # rahbar o'zi bergan parol
    else:password=new_password()
    db.execute('''INSERT INTO web_accounts(user_id,login,pw_hash,updated_ts) VALUES(?,?,?,?)
        ON CONFLICT(user_id) DO UPDATE SET login=excluded.login,pw_hash=excluded.pw_hash,updated_ts=excluded.updated_ts''',
        (int(uid),login,hash_password(password),now))
    db.execute('DELETE FROM web_sessions WHERE user_id=?',(int(uid),))
    db.execute('DELETE FROM web_devices WHERE user_id=?',(int(uid),))
    db.execute('DELETE FROM web_login_fails WHERE login=?',(login,))
    return login,password


def revoke(db,uid):
    """Remove the web account and sign out every browser of `uid`."""
    db.execute('DELETE FROM web_sessions WHERE user_id=?',(int(uid),))
    db.execute('DELETE FROM web_devices WHERE user_id=?',(int(uid),))
    return db.execute('DELETE FROM web_accounts WHERE user_id=?',(int(uid),)).rowcount


def login(db,login_name,password,agent='',now=None):
    """Check login/password and return (user_id, session token). Raises ValueError."""
    uid=check_login(db,login_name,password,now)
    return uid,open_session(db,uid,agent,now)


def check_login(db,login_name,password,now=None):
    """Check login/password (with lockout) and return the user id. Raises ValueError."""
    now=_now(now)
    key=str(login_name or '').strip().lower()[:64]
    if not key or not isinstance(password,str) or not password or len(password)>128:
        raise ValueError('Login yoki parol noto‘g‘ri.')
    fail=db.execute('SELECT fails,locked_until FROM web_login_fails WHERE login=?',(key,)).fetchone()
    if fail and int(fail['locked_until'] or 0)>now:
        minutes=max(1,(int(fail['locked_until'])-now+59)//60)
        raise ValueError(f'Ko‘p marta noto‘g‘ri kiritildi. {minutes} daqiqadan keyin urinib ko‘ring.')
    row=db.execute('SELECT user_id,pw_hash FROM web_accounts WHERE login=?',(key,)).fetchone()
    if not row or not check_password(password,row['pw_hash']):
        fails=(int(fail['fails']) if fail else 0)+1
        locked=now+LOCK_SECONDS if fails>=MAX_FAILS else 0
        db.execute('''INSERT INTO web_login_fails(login,fails,locked_until,ts) VALUES(?,?,?,?)
            ON CONFLICT(login) DO UPDATE SET fails=excluded.fails,locked_until=excluded.locked_until,ts=excluded.ts''',
            (key,0 if locked else fails,locked,now))
        raise ValueError('Login yoki parol noto‘g‘ri.')
    db.execute('DELETE FROM web_login_fails WHERE login=?',(key,))
    return int(row['user_id'])


def open_session(db,uid,agent='',now=None):
    now=_now(now)
    db.execute('DELETE FROM web_sessions WHERE expires_ts<?',(now,))
    token=secrets.token_urlsafe(32)
    db.execute('INSERT INTO web_sessions(token_hash,user_id,created_ts,expires_ts,last_ts,agent) VALUES(?,?,?,?,?,?)',
               (_token_hash(token),int(uid),now,now+SESSION_DAYS*86400,now,str(agent or '')[:200]))
    return token


def session_user(db,token,now=None):
    """Return the user id of a valid session token, or raise ValueError."""
    now=_now(now)
    if not isinstance(token,str) or not 20<=len(token)<=100:
        raise ValueError('Sessiya tugagan. Qayta kiring.')
    th=_token_hash(token)
    row=db.execute('SELECT user_id,expires_ts,last_ts FROM web_sessions WHERE token_hash=?',(th,)).fetchone()
    if not row or int(row['expires_ts'])<now:
        raise ValueError('Sessiya tugagan. Qayta kiring.')
    if now-int(row['last_ts'] or 0)>TOUCH_SECONDS:
        db.execute('UPDATE web_sessions SET last_ts=? WHERE token_hash=?',(now,th))
    return int(row['user_id'])


def logout(db,token):
    if isinstance(token,str) and token:
        db.execute('DELETE FROM web_sessions WHERE token_hash=?',(_token_hash(token),))


def change_password(db,uid,old,new,keep_token=None,now=None):
    """Change own password; every other browser session is signed out."""
    now=_now(now)
    row=db.execute('SELECT pw_hash FROM web_accounts WHERE user_id=?',(int(uid),)).fetchone()
    if not row or not isinstance(old,str) or not check_password(old,row['pw_hash']):
        raise ValueError('Joriy parol noto‘g‘ri.')
    _validate_new(new)
    if new==old:raise ValueError('Yangi parol eskisidan farq qilsin.')
    db.execute('UPDATE web_accounts SET pw_hash=?,updated_ts=? WHERE user_id=?',(hash_password(new),now,int(uid)))
    keep=_token_hash(keep_token) if keep_token else ''
    db.execute('DELETE FROM web_sessions WHERE user_id=? AND token_hash<>?',(int(uid),keep))
    db.execute('DELETE FROM web_devices WHERE user_id=?',(int(uid),))


# --- Rahbar uchun 2-bosqich: yangi qurilmada Telegram'ga 6 xonali kod ---

def device_trusted(db,uid,device,now=None):
    if not isinstance(device,str) or not 20<=len(device)<=100:return False
    row=db.execute('SELECT user_id,expires_ts FROM web_devices WHERE device_hash=?',(_token_hash(device),)).fetchone()
    return bool(row) and int(row['user_id'])==int(uid) and int(row['expires_ts'])>=_now(now)


def trust_device(db,uid,now=None):
    """Remember this browser for DEVICE_DAYS; returns the device token to keep in the browser."""
    now=_now(now)
    db.execute('DELETE FROM web_devices WHERE expires_ts<?',(now,))
    device=secrets.token_urlsafe(32)
    db.execute('INSERT INTO web_devices(device_hash,user_id,expires_ts) VALUES(?,?,?)',
               (_token_hash(device),int(uid),now+DEVICE_DAYS*86400))
    return device


def start_otp(db,uid,now=None):
    """Returns (challenge, code). Only hashes are stored; an older pending code of uid is dropped."""
    now=_now(now)
    db.execute('DELETE FROM web_otp WHERE user_id=? OR expires_ts<?',(int(uid),now))
    challenge=secrets.token_urlsafe(24)
    code=f'{secrets.randbelow(1_000_000):06d}'
    db.execute('INSERT INTO web_otp(challenge_hash,user_id,code_hash,expires_ts,tries) VALUES(?,?,?,?,0)',
               (_token_hash(challenge),int(uid),_token_hash(challenge+':'+code),now+OTP_SECONDS))
    return challenge,code


def verify_otp(db,challenge,code,now=None):
    """Check the code for a challenge and return the user id. Raises ValueError."""
    now=_now(now)
    if not isinstance(challenge,str) or not challenge or len(challenge)>100:
        raise ValueError('Kod muddati tugagan. Qaytadan kiring.')
    th=_token_hash(challenge)
    row=db.execute('SELECT user_id,code_hash,expires_ts,tries FROM web_otp WHERE challenge_hash=?',(th,)).fetchone()
    if not row or int(row['expires_ts'])<now or int(row['tries'])>=OTP_TRIES:
        db.execute('DELETE FROM web_otp WHERE challenge_hash=?',(th,))
        raise ValueError('Kod muddati tugagan. Qaytadan kiring.')
    code=str(code or '').strip()
    if not re.fullmatch(r'\d{6}',code) or not hmac.compare_digest(_token_hash(challenge+':'+code),row['code_hash']):
        db.execute('UPDATE web_otp SET tries=tries+1 WHERE challenge_hash=?',(th,))
        left=OTP_TRIES-int(row['tries'])-1
        raise ValueError(f'Kod noto‘g‘ri. Yana {left} ta urinish qoldi.' if left>0 else 'Kod muddati tugagan. Qaytadan kiring.')
    db.execute('DELETE FROM web_otp WHERE challenge_hash=?',(th,))
    return int(row['user_id'])
