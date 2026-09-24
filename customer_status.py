"""Sales visit status and follow-up dates; no effect on inventory or debt."""
import time
from datetime import date, datetime

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
    if not person or not who or not (who[0]=='admin' or (who[0]=='agent' and person[0]==actor)):
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

def timeline_text(db,client,limit=5):
    rows=history(db,client,limit)
    if not rows:return 'Ташрифлар тарихи ҳали йўқ.'
    return '\n'.join(f"{datetime.fromtimestamp(v['ts']).strftime('%Y-%m-%d %H:%M')} · "
                     f"{v['actor_name'] or v['actor']} · {LABELS[v['status']]}\n"
                     f"📝 {v['note']}"
                     +(f"\n📅 Қайта бориш: {v['followup']}" if v['followup'] else '')
                     for v in rows)
