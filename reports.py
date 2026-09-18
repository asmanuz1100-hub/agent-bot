"""Deterministic reconciliation and seven-day activity reports."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from html import escape
import io,csv,json,time
from core import route_stats
TZ=ZoneInfo('Asia/Tashkent')
NAMES={'delivery':'Реализацияга берилди','sold':'Сотилди','payment':'Нақд пул олинди','return':'Сотилмаган товар қайтди','order':'Буюртма','visit':'Ташриф / таклиф'}

def rowdict(r):
    return {k:r[k] for k in r.keys()}

def admin_only(db,actor):
    r=db.execute('SELECT role FROM users WHERE id=?',(actor,)).fetchone()
    if not r or r[0]!='admin':raise ValueError('Фақат админ.')

def _safe_json(obj):
    return json.dumps(obj,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')

def _map_html(title, routes, shops, summary):
    total_km=round(sum(float(r.get('km') or 0) for r in routes),2)
    gps_points=sum(len(r.get('points') or []) for r in routes)
    active_shops=sum(1 for s in shops if s.get('active'))
    data=_safe_json({'title':title,'routes':routes,'shops':shops,'summary':summary})
    cards=[
        ('Агентлар',len({r.get('agent') for r in routes if r.get('agent')})),
        ('Жами йўл',f'{total_km} км'),
        ('GPS нуқталар',gps_points),
        ('Фаол нуқталар',active_shops),
    ]
    cards_html=''.join(f'<div class="kpi"><span>{escape(str(k))}</span><strong>{escape(str(v))}</strong></div>' for k,v in cards)
    return f'''<!doctype html><html lang="uz"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(title)}</title><link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<style>
:root{{--bg:#f4f7fb;--panel:#ffffff;--text:#14213d;--muted:#6b7280;--line:#e6ebf2;--accent:#2563eb;--shadow:0 12px 34px rgba(15,23,42,.10)}}
*{{box-sizing:border-box}} html,body{{height:100%;margin:0;font-family:Inter,Arial,sans-serif;background:var(--bg);color:var(--text)}}
.app{{height:100%;display:grid;grid-template-rows:auto 1fr}}
.top{{padding:18px 22px 14px;background:var(--panel);border-bottom:1px solid var(--line);z-index:1001}}
.head{{display:flex;align-items:center;justify-content:space-between;gap:14px;flex-wrap:wrap}}
.title{{font-size:22px;font-weight:800;letter-spacing:-.02em}} .badge{{font-size:12px;padding:6px 10px;border-radius:999px;background:#eef2ff;color:#3730a3;font-weight:700}}
.kpis{{display:grid;grid-template-columns:repeat(4,minmax(120px,1fr));gap:10px;margin-top:14px}}
.kpi{{background:#f8fafc;border:1px solid var(--line);border-radius:14px;padding:12px 14px}}
.kpi span{{display:block;color:var(--muted);font-size:12px;margin-bottom:5px}} .kpi strong{{font-size:18px}}
.body{{min-height:0;display:grid;grid-template-columns:310px 1fr;gap:14px;padding:14px}}
.side{{background:var(--panel);border:1px solid var(--line);border-radius:18px;box-shadow:var(--shadow);padding:16px;overflow:auto}}
.side h3{{margin:0 0 10px;font-size:15px}} .summary{{font-size:13px;line-height:1.45;color:var(--muted);padding:10px 12px;background:#f8fafc;border-radius:12px}}
.legend{{margin-top:14px;display:flex;flex-direction:column;gap:9px}} .legend-row{{display:flex;align-items:center;gap:9px;font-size:13px}}
.dot{{width:10px;height:10px;border-radius:50%;flex:none}} .hint{{margin-top:14px;padding-top:12px;border-top:1px solid var(--line);font-size:12px;color:var(--muted);line-height:1.45}}
.mapwrap{{position:relative;min-height:0;background:var(--panel);border:1px solid var(--line);border-radius:18px;overflow:hidden;box-shadow:var(--shadow)}} #map{{height:100%;min-height:520px}}
.leaflet-popup-content{{font-size:13px;line-height:1.45}}
@media(max-width:820px){{.kpis{{grid-template-columns:repeat(2,1fr)}}.body{{grid-template-columns:1fr;grid-template-rows:auto 1fr}}.side{{max-height:220px}}#map{{min-height:520px}}}}
</style></head>
<body><div class="app"><section class="top"><div class="head"><div class="title">{escape(title)}</div><div class="badge">ИЧКИ ФОЙДАЛАНИШ · ТЕСТ</div></div><div class="kpis">{cards_html}</div></section>
<section class="body"><aside class="side"><h3>Қисқа таҳлил</h3><div id="summary" class="summary"></div><div id="legend" class="legend"></div><div class="hint">Маршрут GPS нуқталари асосида қурилади. Масофа ва тўхташлар тахминий. Савдо нуқталари агент киритган мижоз локацияларидан олинади.</div></aside><div class="mapwrap"><div id="map"></div></div></section></div>
<script id="data" type="application/json">{data}</script><script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
const D=JSON.parse(document.getElementById('data').textContent), map=L.map('map',{zoomControl:true});
L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png',{{maxZoom:19,attribution:'© OpenStreetMap'}}).addTo(map);
const bounds=[]; const colors=['#2563eb','#f59e0b','#16a34a','#7c3aed','#e11d48','#0891b2','#9333ea','#475569'];
function esc(s){{return String(s??'').replace(/[&<>"']/g,m=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[m]));}}
const legend=document.getElementById('legend');
D.routes.forEach((r,i)=>{{const pts=(r.points||[]).map(p=>[p.lat,p.lon]);const color=colors[i%colors.length];
  if(pts.length){{L.polyline(pts,{{weight:5,color,opacity:.9}}).addTo(map).bindTooltip(esc(r.agent));pts.forEach(x=>bounds.push(x));
    L.circleMarker(pts[0],{{radius:6,color,fillOpacity:1}}).addTo(map).bindPopup('Бошланиш · '+esc(r.agent));
    L.circleMarker(pts[pts.length-1],{{radius:6,color,fillOpacity:1}}).addTo(map).bindPopup('Охирги нуқта · '+esc(r.agent));}}
  const row=document.createElement('div');row.className='legend-row';row.innerHTML='<span class="dot" style="background:'+color+'"></span><span>'+esc(r.agent)+' · '+esc(r.km||0)+' км</span>';legend.appendChild(row);
}});
D.shops.forEach(s=>{{if(s.lat==null||s.lon==null)return; const p=[s.lat,s.lon];bounds.push(p);
  L.circleMarker(p,{{radius:s.active?9:6,weight:s.active?3:1,color:s.active?'#0f766e':'#64748b',fillColor:s.active?'#14b8a6':'#cbd5e1',fillOpacity:s.active?.9:.65}})
   .addTo(map).bindPopup('<b>'+esc(s.shop||s.name)+'</b><br>'+esc(s.name)+'<br>'+esc(s.address)+'<br>'+(s.active?'✅ Фаол савдо нуқтаси':'Қайд этилган савдо нуқтаси'));
}});
document.getElementById('summary').textContent=D.summary||'Маълумот йўқ';
if(bounds.length)map.fitBounds(bounds,{{padding:[35,35],maxZoom:16}});else map.setView([41.3,69.24],7);
</script></body></html>'''.encode('utf-8')

def shift_route_data(db,agent,shift):
    end=shift['end'] or int(time.time())
    points=db.execute('SELECT * FROM points WHERE shift=? ORDER BY ts',(shift['id'],)).fetchall()
    stats=route_stats(points,shift['start'],end)
    active={r[0] for r in db.execute('SELECT DISTINCT client FROM events WHERE agent=? AND client IS NOT NULL AND ts BETWEEN ? AND ?',(agent,shift['start'],end)).fetchall()}
    shops=[]
    for s in db.execute('SELECT * FROM clients WHERE agent=? AND lat IS NOT NULL AND lon IS NOT NULL',(agent,)).fetchall():
        shops.append({'id':s['id'],'name':s['name'],'shop':s['shop_name'],'address':s['address'],'lat':s['lat'],'lon':s['lon'],'active':s['id'] in active})
    route={'agent':str(agent),'shift':shift['id'],'km':stats['km'],'points':[{'lat':p['lat'],'lon':p['lon'],'ts':p['ts']} for p in points]}
    return route,shops,stats,len(active)

def route_map_html(db,actor,agent):
    admin_only(db,actor)
    shift=db.execute('SELECT * FROM shifts WHERE agent=? ORDER BY id DESC LIMIT 1',(agent,)).fetchone()
    if not shift:raise ValueError('Бу агент ҳали иш бошламаган.')
    route,shops,stats,active=shift_route_data(db,agent,shift)
    summary=f"{stats['km']} км · {active} фаол савдо нуқтаси · {len(stats['stops'])} тўхташ · {len(stats['gaps'])} узилиш"
    return _map_html(f'Агент {agent} · смена #{shift["id"]}',[route],shops,summary),stats,active

def overall(db,actor,now=None):
    admin_only(db,actor)
    now=now or datetime.now(TZ);now=now.astimezone(TZ)
    start=now.replace(hour=0,minute=0,second=0,microsecond=0)
    a=int(start.timestamp());b=int(now.timestamp())+1
    agents=db.execute("SELECT id,name FROM users WHERE role='agent' ORDER BY name").fetchall()
    routes=[];all_shops=[];seen_shops=set();total_km=0;stops=gaps=0;gps_points=0
    details=[]
    for ag in agents:
        aid=ag[0]
        shifts=db.execute('SELECT * FROM shifts WHERE agent=? AND start<? AND (end IS NULL OR end>=?) ORDER BY start',(aid,b,a)).fetchall()
        akm=0;astops=agaps=0
        for sh in shifts:
            route,shops,stats,_=shift_route_data(db,aid,sh)
            route['agent']=ag[1] or str(aid);routes.append(route);akm+=stats['km'];astops+=len(stats['stops']);agaps+=len(stats['gaps']);gps_points+=len(route['points'])
            for s in shops:
                if s['id'] not in seen_shops:all_shops.append(s);seen_shops.add(s['id'])
        ev=db.execute('SELECT * FROM events WHERE agent=? AND ts>=? AND ts<?',(aid,a,b)).fetchall()
        active={x['client'] for x in ev if x['client'] is not None}
        sold=sum(x['amount'] for x in ev if x['kind']=='sold');paid=sum(x['amount'] for x in ev if x['kind']=='payment')
        details.append(f"{ag[1]} ({aid}): {round(akm,2)} км · {len(active)} нуқта · сотув {m(sold)} сўм · тўлов {m(paid)} сўм")
        total_km+=akm;stops+=astops;gaps+=agaps
    events=db.execute('SELECT * FROM events WHERE ts>=? AND ts<?',(a,b)).fetchall()
    active_all={x['client'] for x in events if x['client'] is not None}
    sold_qty=sum(x['qty'] for x in events if x['kind']=='sold');sold=sum(x['amount'] for x in events if x['kind']=='sold')
    delivered=sum(x['qty'] for x in events if x['kind']=='delivery');paid=sum(x['amount'] for x in events if x['kind']=='payment')
    text=(f"УМУМИЙ ТАҲЛИЛ · {now:%d.%m.%Y %H:%M}\n"
          f"Жами агент: {len(agents)}\nЖами йўл: {round(total_km,2)} км\nGPS нуқталари: {gps_points}\n"
          f"Фаол савдо нуқталари: {len(active_all)}\nТўхташлар: {stops}\nЛокация узилишлари (>5 дақ.): {gaps}\n"
          f"Берилган товар: {delivered} дона\nСотилган: {sold_qty} дона / {m(sold)} сўм\nОлинган пул: {m(paid)} сўм\n\n"
          +"Агентлар:\n"+("\n".join(details) if details else "Агент йўқ"))
    if gps_points==0:text+='\n\n⚠️ Бугун GPS нуқталари сақланмаган. Агент сменани бошлаб Telegram жонли локациясини юбориши керак.'
    summary=f"{round(total_km,2)} км · {len(active_all)} фаол нуқта · {m(sold)} сўм сотув"
    return text,_map_html(f'Умумий маршрут · {now:%d.%m.%Y}',routes,all_shops,summary)

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
    return {'client':rowdict(c),'start':start,'end':end,'opening':opening,'closing':balance,'sales':sales,'payments':payments,'opening_stock':initial,'closing_stock':stocks,'rows':rows}

def m(x):return f'{x/100:,.2f}'.replace(',',' ')

def reconciliation_html(r):
    c=r['client'];esc=lambda x:escape(str(x),quote=True)
    stock=''.join(f'<tr><td>Грунтовка 7/1 · {p} кг</td><td>{r["opening_stock"][p]}</td><td>{r["closing_stock"][p]}</td></tr>' for p in (1,3,5))
    rows=''.join('<tr>'+''.join(f'<td>{esc(v)}</td>' for v in [x['id'],x['time'],x['kind'],str(x['pack'])+' кг' if x['pack'] else '—',x['qty'] or '—',m(x['charge']),m(x['credit']),m(x['balance'])])+'</tr>' for x in r['rows'])
    return f'''<!doctype html><html lang="uz"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ASMAN — акт сверка</title><style>
body{{font:14px Arial,sans-serif;color:#15243b;background:#eef3f8;margin:0;padding:24px}}main{{max-width:1000px;margin:auto;background:white;padding:36px}}h1{{color:#174e87;margin:8px 0}}.muted{{color:#52647a}}.cards{{display:flex;flex-wrap:wrap;gap:16px;margin:24px 0}}.card{{padding:16px;background:#edf4fb;flex:1;min-width:160px}}strong{{display:block;font-size:20px;margin-top:8px}}table{{border-collapse:collapse;width:100%;font-size:12px;margin:18px 0}}th{{background:#174e87;color:white}}td,th{{padding:9px;border:1px solid #d3dce8;text-align:left}}.scroll{{overflow:auto}}footer{{margin-top:32px}}@media print{{body{{background:white;padding:0}}main{{padding:0}}thead{{display:table-header-group}}tr{{break-inside:avoid}}button{{display:none}}}}@page{{size:A4 landscape;margin:14mm}}
</style><main><p class="muted">ИЧКИ САВДО НАЗОРАТИ · ТЕСТ ҲИСОБОТИ</p><h1>Ўзаро ҳисоб-китобларни солиштириш далолатномаси</h1><p>{esc(r['start'])} — {esc(r['end'])} · Тошкент вақти</p><h2>{esc(c['name'])}</h2><p>{esc(c['phone'])} · {esc(c['address'])}</p><div class="cards"><div class="card">Бошланғич баланс<strong>{m(r['opening'])} сўм</strong></div><div class="card">Сотилган товар<strong>{m(r['sales'])} сўм</strong></div><div class="card">Олинган пул<strong>{m(r['payments'])} сўм</strong></div><div class="card">Якуний баланс<strong>{m(r['closing'])} сўм</strong></div></div><p>Мусбат баланс — сотилган товар учун тўлов қолдиғи. Манфий баланс — мижоз аванси. Сотилмаган реализация товари пул қарзига қўшилмаган.</p><h2>Операциялар</h2><div class="scroll"><table><thead><tr><th>№</th><th>Сана</th><th>Амал</th><th>Қадоқ</th><th>Дона</th><th>Сотув, сўм</th><th>Тўлов, сўм</th><th>Баланс, сўм</th></tr></thead><tbody>{rows or '<tr><td colspan="8">Бу даврда операция йўқ</td></tr>'}</tbody></table></div><h2>Мижоздаги сотилмаган товар</h2><table><thead><tr><th>Маҳсулот</th><th>Давр бошида, дона</th><th>Давр охирида, дона</th></tr></thead><tbody>{stock}</tbody></table><footer><p>Ҳисобот ботга тасдиқлаб киритилган маълумотлар асосида тузилди. Иккинчи томон ҳали тасдиқламаган.</p><p>ASMAN вакили: ____________________ &nbsp;&nbsp; Мижоз: ____________________</p></footer></main></html>'''.encode()

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
