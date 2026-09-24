"""Sales visit status and follow-up dates; no effect on inventory or debt."""
import time
from datetime import date, datetime
from zoneinfo import ZoneInfo

TZ=ZoneInfo('Asia/Tashkent')

LABELS={'declined':'❌ Ҳозирча олмайди','waiting':'⏳ Кутишда','interested':'🟠 Таклиф берилган','active':'🟢 Товар олган'}
ICONS={'declined':'❌','waiting':'⏳','interested':'🟠','active':'🟢'}

def normalize(status, followup=None):
    if status not in LABELS:
        raise ValueError('Мижоз мақоми нотўғри.')
    if status=='waiting':
        if not followup:
            raise ValueError('Қайта бориш санасини YYYY-MM-DD кўринишида киритинг.')
        try:
            planned=date.fromisoformat(followup)
        except (ValueError, TypeError):
            raise ValueError('Сана: YYYY-MM-DD. Масалан, 2026-10-01.')
        if planned<date.today():
            raise ValueError('Қайта бориш санаси ўтган бўлмаслиги керак.')
        if planned.year>date.today().year+5:
            raise ValueError('Қайта бориш санаси жуда узоқ.')
        return followup
    return None

def add_visit(db,actor,client,status,note,followup=None):
    person=db.execute('SELECT agent FROM clients WHERE id=?',(client,)).fetchone()
    who=db.execute('SELECT role FROM users WHERE id=?',(actor,)).fetchone()
    if not person or not who or who[0] not in ('admin','agent'):
        raise ValueError('Бу дўконнинг ташрифини қайд этишга рухсат йўқ.')
    note=str(note or '').strip()
    if not note or len(note)>1000:
        raise ValueError('Суҳбат ҳақида 1–1000 белги ёзинг.')
    followup=normalize(status,followup)
    db.execute('INSERT INTO client_visits(client,actor,status,note,followup,ts) VALUES(?,?,?,?,?,?)',
               (client,actor,status,note,followup,int(time.time())))

def history(db,client,limit=5):
    return db.execute("""SELECT v.status,v.note,v.followup,v.ts,v.actor,u.name AS actor_name
        FROM client_visits v LEFT JOIN users u ON u.id=v.actor
        WHERE v.client=? ORDER BY v.id DESC LIMIT ?""",(client,limit)).fetchall()

def summary(db,client,map_only=False):
    rows=history(db,client,1)
    if rows:
        v=rows[0];status=v['status']
        return {'status':status,'icon':ICONS[status],'label':LABELS[status],
                'note':v['note'],'followup':v['followup'],
                'actor':v['actor_name'] or str(v['actor']),'ts':v['ts']}
    status='interested' if map_only else 'active'
    return {'status':status,'icon':ICONS[status],'label':LABELS[status],
            'note':'','followup':None,'actor':'','ts':None}

def last_contact_ts(db,client):
    """Best available physical-contact timestamp for visit planning."""
    values=[]
    row=db.execute('SELECT MAX(ts) FROM client_visits WHERE client=?',(client,)).fetchone()
    if row and row[0]:values.append(int(row[0]))
    row=db.execute("""SELECT MAX(ts) FROM events WHERE client=?
        AND kind IN ('visit','delivery','payment','return')""",(client,)).fetchone()
    if row and row[0]:values.append(int(row[0]))
    row=db.execute('SELECT created_ts FROM clients WHERE id=?',(client,)).fetchone()
    if row and row[0]:values.append(int(row[0]))
    return max(values) if values else None

def visit_attention(db,client,map_only=False,now=None):
    """Map urgency: fresh <3d, yellow 3–4d, red 5+d.

    A future explicit follow-up date keeps a waiting customer in scheduled mode
    so the agent is not pushed back to the shop before the agreed date.
    """
    now=int(time.time() if now is None else now)
    status=summary(db,client,map_only)
    last=last_contact_ts(db,client)
    current_date=datetime.fromtimestamp(now,TZ).date()
    followup=status.get('followup')
    if followup:
        try:planned=date.fromisoformat(followup)
        except ValueError:planned=None
        if planned and planned>current_date:
            days_until=(planned-current_date).days
            return {'level':'scheduled','days':None if last is None else max(0,(now-last)//86400),
                    'last_ts':last,'color':'#0284c7','background':'#e0f2fe',
                    'label':f'⏳ Режада: {followup} ({days_until} кундан кейин)'}
    if last is None:
        return {'level':'unknown','days':None,'last_ts':None,'color':'#64748b',
                'background':'#f8fafc','label':'⚪ Ташриф санаси аниқ эмас'}
    days=max(0,(now-last)//86400)
    if days>=5:
        return {'level':'red','days':days,'last_ts':last,'color':'#dc2626',
                'background':'#fee2e2','label':f'🔴 {days} кундан бери ташриф йўқ'}
    if days>=3:
        return {'level':'yellow','days':days,'last_ts':last,'color':'#b45309',
                'background':'#fde68a','label':f'🟠 {days} кундан бери ташриф йўқ'}
    return {'level':'fresh','days':days,'last_ts':last,'color':'#16a34a',
            'background':'#f0fdf4','label':f'🟢 Охирги ташриф: {days} кун олдин'}

def timeline_text(db,client,limit=5):
    rows=history(db,client,limit)
    if not rows:return 'Ташрифлар тарихи ҳали йўқ.'
    return '\n'.join(f"{datetime.fromtimestamp(v['ts']).strftime('%Y-%m-%d %H:%M')} · "
                     f"{v['actor_name'] or v['actor']} · {LABELS[v['status']]}\n"
                     f"📝 {v['note']}"
                     +(f"\n📅 Қайта бориш: {v['followup']}" if v['followup'] else '')
                     for v in rows)
