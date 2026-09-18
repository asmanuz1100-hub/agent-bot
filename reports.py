"""Deterministic reconciliation and seven-day activity reports."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from html import escape
import io,csv
from core import route_stats
TZ=ZoneInfo('Asia/Tashkent')
NAMES={'delivery':'Реализацияга берилди','sold':'Сотилди','payment':'Нақд пул олинди','return':'Сотилмаган товар қайтди','order':'Буюртма','visit':'Ташриф / таклиф'}

def dates(start,end):
    try:
        a=datetime.strptime(start,'%Y-%m-%d').replace(tzinfo=TZ)
        b=datetime.strptime(end,'%Y-%m-%d').replace(tzinfo=TZ)+timedelta(days=1)
    except ValueError:raise ValueError('Санани ЙЙЙЙ-ОО-КК кўринишида киритинг: 2026-09-18')
    if b<=a:raise ValueError('Охирги сана биринчи санадан олдин бўлмасин.')
    return int(a.timestamp()),int(b.timestamp())

def auth(db,actor,agent):
    r=db.execute('SELECT role FROM users WHERE id=?',(actor,)).fetchone()
    if not r or not (r[0]=='admin' or (r[0]=='agent' and actor==agent)):raise ValueError('Ҳисоботга рухсат йўқ.')

def reconciliation(db,actor,client,start,end):
    c=db.execute('SELECT * FROM clients WHERE id=?',(client,)).fetchone()
    if not c:raise ValueError('Мижоз топилмади.')
    auth(db,actor,c['agent']);a,b=dates(start,end)
    before=db.execute('SELECT * FROM events WHERE client=? AND ts<? ORDER BY ts,id',(client,a)).fetchall()
    events=db.execute('SELECT * FROM events WHERE client=? AND ts>=? AND ts<? ORDER BY ts,id',(client,a,b)).fetchall()
    stocks={1:0,3:0,5:0};opening=0
    for e in before:
        if e['kind'] in ('delivery','sold','return'):stocks[e['pack']]+=e['qty']*(1 if e['kind']=='delivery' else -1)
        if e['kind']=='sold':opening+=e['amount']
        if e['kind']=='payment':opening-=e['amount']
    initial=stocks.copy();balance=opening;rows=[];sales=payments=0
    for e in events:
        k=e['kind']
        if k not in ('delivery','sold','return','payment'):continue
        if k in ('delivery','sold','return'):stocks[e['pack']]+=e['qty']*(1 if k=='delivery' else -1)
        charge=e['amount'] if k=='sold' else 0;credit=e['amount'] if k=='payment' else 0
        balance+=charge-credit;sales+=charge;payments+=credit
        rows.append({'id':e['id'],'time':datetime.fromtimestamp(e['ts'],TZ).strftime('%d.%m.%Y %H:%M'),'kind':NAMES[k],'pack':e['pack'],'qty':e['qty'],'charge':charge,'credit':credit,'balance':balance})
    return {'client':dict(c),'start':start,'end':end,'opening':opening,'closing':balance,'sales':sales,'payments':payments,'opening_stock':initial,'closing_stock':stocks,'rows':rows}

def m(x):return f'{x/100:,.2f}'.replace(',',' ')

def reconciliation_html(r):
    c=r['client'];esc=lambda x:escape(str(x),quote=True)
    stock=''.join(f'<tr><td>Грунтовка 7/1 · {p} кг</td><td>{r["opening_stock"][p]}</td><td>{r["closing_stock"][p]}</td></tr>' for p in (1,3,5))
    rows=''.join('<tr>'+''.join(f'<td>{esc(v)}</td>' for v in [x['id'],x['time'],x['kind'],str(x['pack'])+' кг' if x['pack'] else '—',x['qty'] or '—',m(x['charge']),m(x['credit']),m(x['balance'])])+'</tr>' for x in r['rows'])
    return f'''<!doctype html><html lang="uz"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ASMAN — акт сверка</title><style>
body{{font:14px Arial,sans-serif;color:#15243b;background:#eef3f8;margin:0;padding:24px}}main{{max-width:1000px;margin:auto;background:white;padding:36px}}h1{{color:#174e87;margin:8px 0}}.muted{{color:#52647a}}.cards{{display:flex;flex-wrap:wrap;gap:16px;margin:24px 0}}.card{{padding:16px;background:#edf4fb;flex:1;min-width:160px}}strong{{display:block;font-size:20px;margin-top:8px}}table{{border-collapse:collapse;width:100%;font-size:12px;margin:18px 0}}th{{background:#174e87;color:white}}td,th{{padding:9px;border:1px solid #d3dce8;text-align:left}}.scroll{{overflow:auto}}footer{{margin-top:32px}}@media print{{body{{background:white;padding:0}}main{{padding:0}}thead{{display:table-header-group}}tr{{break-inside:avoid}}button{{display:none}}}}@page{{size:A4 landscape;margin:14mm}}
</style><main><p class="muted">ASMAN SILICAT · АГЕНТ САВДОСИ · ТЕСТ ҲИСОБОТИ</p><h1>Ўзаро ҳисоб-китобларни солиштириш далолатномаси</h1><p>{esc(r['start'])} — {esc(r['end'])} · Тошкент вақти</p><h2>{esc(c['name'])}</h2><p>{esc(c['phone'])} · {esc(c['address'])}</p><div class="cards"><div class="card">Бошланғич баланс<strong>{m(r['opening'])} сўм</strong></div><div class="card">Сотилган товар<strong>{m(r['sales'])} сўм</strong></div><div class="card">Олинган пул<strong>{m(r['payments'])} сўм</strong></div><div class="card">Якуний баланс<strong>{m(r['closing'])} сўм</strong></div></div><p>Мусбат баланс — сотилган товар учун тўлов қолдиғи. Манфий баланс — мижоз аванси. Сотилмаган реализация товари пул қарзига қўшилмаган.</p><h2>Операциялар</h2><div class="scroll"><table><thead><tr><th>№</th><th>Сана</th><th>Амал</th><th>Қадоқ</th><th>Дона</th><th>Сотув, сўм</th><th>Тўлов, сўм</th><th>Баланс, сўм</th></tr></thead><tbody>{rows or '<tr><td colspan="8">Бу даврда операция йўқ</td></tr>'}</tbody></table></div><h2>Мижоздаги сотилмаган товар</h2><table><thead><tr><th>Маҳсулот</th><th>Давр бошида, дона</th><th>Давр охирида, дона</th></tr></thead><tbody>{stock}</tbody></table><footer><p>Ҳисобот ботга тасдиқлаб киритилган маълумотлар асосида тузилди. Иккинчи томон ҳали тасдиқламаган.</p><p>ASMAN вакили: ____________________ &nbsp;&nbsp; Мижоз: ____________________</p></footer></main></html>'''.encode()

def weekly(db,actor,agent,now=None):
    auth(db,actor,agent)
    now=now or datetime.now(TZ);now=now.astimezone(TZ)
    start=now.replace(hour=0,minute=0,second=0,microsecond=0)-timedelta(days=6)
    a=int(start.timestamp());b=int(now.timestamp())+1
    rows=db.execute('SELECT * FROM events WHERE agent=? AND ts>=? AND ts<? ORDER BY ts,id',(agent,a,b)).fetchall()
    visits=[r for r in rows if r['kind']=='visit'];shop_ids={r['client'] for r in visits}
    clients=db.execute('SELECT id,name FROM clients WHERE agent=?',(agent,)).fetchall();names={c[0]:c[1] for c in clients}
    counts={cid:sum(x['client']==cid for x in visits) for cid in shop_ids}
    totals={k:sum(x['qty'] for x in rows if x['kind']==k) for k in ('delivery','sold','return','order')}
    sold=sum(x['amount'] for x in rows if x['kind']=='sold');paid=sum(x['amount'] for x in rows if x['kind']=='payment')
    active_days=len({datetime.fromtimestamp(x['ts'],TZ).date() for x in visits})
    # Count balances as of report cutoff, not only this week's movements.
    history=db.execute('SELECT * FROM events WHERE agent=? AND ts<?',(agent,b)).fetchall()
    cash_in=sum(x['amount'] for x in history if x['kind']=='payment')
    accepted=db.execute("SELECT COALESCE(SUM(amount),0) FROM handovers WHERE agent=? AND status='accepted' AND COALESCE(accepted_ts,ts)<?",(agent,b)).fetchone()[0]
    cash_week=db.execute("SELECT COALESCE(SUM(amount),0) FROM handovers WHERE agent=? AND status='accepted' AND COALESCE(accepted_ts,ts)>=? AND COALESCE(accepted_ts,ts)<?",(agent,a,b)).fetchone()[0]
    due=sum(x['amount']*(1 if x['kind']=='sold' else -1) for x in history if x['kind'] in ('sold','payment'))
    shop_stock={p:sum(x['qty']*(1 if x['kind']=='delivery' else -1) for x in history if x['pack']==p and x['kind'] in ('delivery','sold','return')) for p in (1,3,5)}
    text=f'ҲАФТАЛИК ТАҲЛИЛ · агент {agent}\n{start:%d.%m.%Y} — {now:%d.%m.%Y %H:%M}\nБугун ва олдинги 6 календарь кун\n\nАлоҳида дўконлар: {len(shop_ids)}\nҚайд қилинган ташрифлар: {len(visits)}\nТашриф қайд қилинган кунлар: {active_days}\nБерилган товар: {totals["delivery"]} дона\nСотилган: {totals["sold"]} дона / {m(sold)} сўм\nҚайтарилган: {totals["return"]} дона\nБуюртма: {totals["order"]} дона\nОлинган нақд пул: {m(paid)} сўм\nКассир қабул қилган: {m(cash_week)} сўм\n\nЖорий қолдиқлар:\nАгентдаги пул: {m(cash_in-accepted)} сўм\nМижозлар умумий баланси: {m(due)} сўм\nМижозларда сотилмаган товар: '+', '.join(f'{p} кг: {q} дона' for p,q in shop_stock.items())
    text+='\n\nДўконлар бўйича ташрифлар:\n'+ ('\n'.join(f'{names.get(cid,cid)}: {counts[cid]} марта' for cid in sorted(shop_ids)) or 'Қайд қилинмаган')
    text+='\n\nДўкон саноғи «Ташриф / таклиф» ёзувлари бўйича. Мижоз қўшиш ёки товар бериш ўз-ўзидан ташриф саналмайди. Баланс манфий бўлса — аванс.'
    return text,rows

def weekly_csv(rows):
    out=io.StringIO();w=csv.writer(out);w.writerow(['ID','Tashkent time','Client ID','Action','Pack kg','Quantity','UZS','Note'])
    def safe(x):
        s=str(x);return "'"+s if s.lstrip().startswith(('=','+','-','@','\t','\r')) else s
    for r in rows:w.writerow([r['id'],datetime.fromtimestamp(r['ts'],TZ).isoformat(),r['client'],NAMES.get(r['kind'],r['kind']),r['pack'],r['qty'],m(r['amount']),safe(r['note'])])
    return out.getvalue().encode('utf-8-sig')
