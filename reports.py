"""Deterministic reconciliation, route maps, and daily analytics."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from html import escape
import io,csv,json,time
from core import route_stats,product_name
TZ=ZoneInfo('Asia/Tashkent')
NAMES={'delivery':'Товар топширилди (USD қарз)','sold':'Сотилган миқдор қайд этилди','payment':'USD тўлов олинди','return':'Товар қайтарилди (USD қарз камайди)','order':'Буюртма','visit':'Ташриф / таклиф'}

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
const D=JSON.parse(document.getElementById('data').textContent), map=L.map('map',{{zoomControl:true}});
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


def shift_summary(db,agent,shift_id):
    shift=db.execute('SELECT * FROM shifts WHERE id=? AND agent=?',(shift_id,agent)).fetchone()
    if not shift:raise ValueError('Смена топилмади.')
    end=int(shift['end'] or time.time());start=int(shift['start'])
    user=db.execute('SELECT name FROM users WHERE id=?',(agent,)).fetchone()
    name=(user[0] if user else str(agent)) or str(agent)
    points=db.execute('SELECT * FROM points WHERE shift=? ORDER BY ts',(shift_id,)).fetchall()
    stats=route_stats(points,start,end)
    metric=db.execute("""SELECT
        COUNT(DISTINCT client),
        COALESCE(SUM(CASE WHEN kind='visit' THEN 1 ELSE 0 END),0),
        COALESCE(SUM(CASE WHEN kind='sold' THEN qty ELSE 0 END),0),
        COALESCE(SUM(CASE WHEN kind='delivery' THEN amount_usd WHEN kind='return' THEN -amount_usd ELSE 0 END),0),
        COALESCE(SUM(CASE WHEN kind='payment' THEN amount_usd ELSE 0 END),0),
        COALESCE(SUM(CASE WHEN kind='delivery' THEN qty ELSE 0 END),0),
        COALESCE(SUM(CASE WHEN kind='order' THEN qty ELSE 0 END),0),
        COALESCE(SUM(CASE WHEN kind='return' THEN qty ELSE 0 END),0)
        FROM events WHERE agent=? AND ts>=? AND ts<=?""",(agent,start,end)).fetchone()
    new_clients=db.execute(
        'SELECT COUNT(*) FROM clients WHERE agent=? AND created_ts IS NOT NULL AND created_ts>=? AND created_ts<=?',
        (agent,start,end)
    ).fetchone()[0]
    active_clients=int(metric[0] or 0);visits=int(metric[1] or 0)
    sold_qty=int(metric[2] or 0);sold_amount=int(metric[3] or 0)
    payments=int(metric[4] or 0);delivered=int(metric[5] or 0)
    orders=int(metric[6] or 0);returns=int(metric[7] or 0)
    duration=max(0,end-start);hours=duration//3600;minutes=(duration%3600)//60
    first=points[0] if points else None;last=points[-1] if points else None
    start_loc=(f"{first['lat']:.6f}, {first['lon']:.6f}" if first else 'GPS нуқтаси келмаган')
    end_loc=(f"{last['lat']:.6f}, {last['lon']:.6f}" if last else 'GPS нуқтаси келмаган')
    start_link=(f"https://www.google.com/maps?q={first['lat']},{first['lon']}" if first else '')
    end_link=(f"https://www.google.com/maps?q={last['lat']},{last['lon']}" if last else '')
    if sold_qty and new_clients:
        note=f"Кунда {new_clients} та янги мижоз қўшилди ва {sold_qty} дона товар сотилди."
    elif sold_qty:
        note=f"Кунда {sold_qty} дона товар сотилди; янги мижоз қайд этилмади."
    elif new_clients:
        note=f"{new_clients} та янги мижоз қўшилди, лекин сотув қайд этилмади."
    else:
        note="Янги мижоз ва сотув қайд этилмади."
    # GPS details remain available only in the admin tracking view, not in daily summaries.
    text=(
        f"📊 КУНЛИК ФАОЛИЯТ · {datetime.fromtimestamp(end,TZ):%d.%m.%Y}\n"
        f"👤 Агент: {name} ({agent})\n"
        f"🟢 Иш бошланди: {datetime.fromtimestamp(start,TZ):%H:%M}\n"
        f"🔴 Иш тугади: {datetime.fromtimestamp(end,TZ):%H:%M}\n"
        f"⏱ Иш вақти: {hours} соат {minutes} дақиқа\n"
        f"🆕 Янги мижоз: {int(new_clients)} та\n"
        f"🏪 Ишланган мижозлар: {active_clients} та · ташриф: {visits} та\n"
        f"📦 Реализацияга берилди: {delivered} дона · буюртма: {orders} дона · қайтди: {returns} дона\n"
        f"💵 Сотилган миқдор: {sold_qty} дона\n"
        f"📦 Топширилган товар ҳисоб-фактураси (қайтариш чегирилган): {m(sold_amount)} USD\n"
        f"💰 Олинган тўлов: {m(payments)} USD\n"
        f"📝 Қисқа хулоса: {note}"
    )
    return {
        'agent':agent,'name':name,'shift_id':shift_id,'start':start,'end':end,
        'duration':duration,'km':stats['km'],'gps_points':len(points),'gaps':len(stats['gaps']),
        'new_clients':int(new_clients),'active_clients':active_clients,'visits':visits,
        'sold_qty':sold_qty,'sold_amount':sold_amount,'payments':payments,
        'delivered':delivered,'orders':orders,'returns':returns,
        'first':rowdict(first) if first else None,'last':rowdict(last) if last else None,
        'text':text
    }

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
        metric=db.execute("""SELECT
            COUNT(DISTINCT client),
            COALESCE(SUM(CASE WHEN kind='delivery' THEN amount_usd WHEN kind='return' THEN -amount_usd ELSE 0 END),0),
            COALESCE(SUM(CASE WHEN kind='payment' THEN amount_usd ELSE 0 END),0)
            FROM events WHERE agent=? AND ts>=? AND ts<?""",(aid,a,b)).fetchone()
        active_count=int(metric[0] or 0);sold=int(metric[1] or 0);paid=int(metric[2] or 0)
        details.append(f"{ag[1]} ({aid}): {round(akm,2)} км · {active_count} нуқта · топширилди {m(sold)} USD · тўлов {m(paid)} USD")
        total_km+=akm;stops+=astops;gaps+=agaps
    metric=db.execute("""SELECT
        COUNT(DISTINCT client),
        COALESCE(SUM(CASE WHEN kind='sold' THEN qty ELSE 0 END),0),
        COALESCE(SUM(CASE WHEN kind='delivery' THEN amount_usd WHEN kind='return' THEN -amount_usd ELSE 0 END),0),
        COALESCE(SUM(CASE WHEN kind='delivery' THEN qty ELSE 0 END),0),
        COALESCE(SUM(CASE WHEN kind='payment' THEN amount_usd ELSE 0 END),0)
        FROM events WHERE ts>=? AND ts<?""",(a,b)).fetchone()
    active_all=int(metric[0] or 0);sold_qty=int(metric[1] or 0);sold=int(metric[2] or 0)
    delivered=int(metric[3] or 0);paid=int(metric[4] or 0)
    text=(f"УМУМИЙ ТАҲЛИЛ · {now:%d.%m.%Y %H:%M}\n"
          f"Жами агент: {len(agents)}\nЖами йўл: {round(total_km,2)} км\nGPS нуқталари: {gps_points}\n"
          f"Фаол савдо нуқталари: {active_all}\nТўхташлар: {stops}\nЛокация узилишлари (>5 дақ.): {gaps}\n"
          f"Берилган товар: {delivered} дона · Сотилган: {sold_qty} дона\nТовар ҳисоби: {m(sold)} USD\nОлинган тўлов: {m(paid)} USD\n\n"
          +"Агентлар:\n"+("\n".join(details) if details else "Агент йўқ"))
    if gps_points==0:text+='\n\n⚠️ Бугун GPS нуқталари сақланмаган. Агент сменани бошлаб Telegram жонли локациясини юбориши керак.'
    summary=f"{round(total_km,2)} км · {active_all} фаол нуқта · {m(sold)} USD товар"
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
    opening_row=db.execute("""SELECT
        COALESCE(SUM(CASE WHEN kind='sold' THEN amount WHEN kind='payment' THEN -amount ELSE 0 END),0),
        COALESCE(SUM(CASE WHEN pack=1 AND kind='delivery' THEN qty WHEN pack=1 AND kind IN ('sold','return') THEN -qty ELSE 0 END),0),
        COALESCE(SUM(CASE WHEN pack=3 AND kind='delivery' THEN qty WHEN pack=3 AND kind IN ('sold','return') THEN -qty ELSE 0 END),0),
        COALESCE(SUM(CASE WHEN pack=5 AND kind='delivery' THEN qty WHEN pack=5 AND kind IN ('sold','return') THEN -qty ELSE 0 END),0)
        FROM events WHERE client=? AND ts<?""",(client,a)).fetchone()
    opening=int(opening_row[0] or 0)
    stocks={1:int(opening_row[1] or 0),3:int(opening_row[2] or 0),5:int(opening_row[3] or 0)}
    events=db.execute("""SELECT id,ts,kind,pack,qty,amount,amount_usd FROM events
        WHERE client=? AND ts>=? AND ts<? AND kind IN ('delivery','sold','return','payment')
        ORDER BY ts,id""",(client,a,b)).fetchall()
    before_usd=db.execute("""SELECT COALESCE(SUM(CASE WHEN kind='delivery' THEN amount_usd
        WHEN kind IN ('payment','return') THEN -amount_usd ELSE 0 END),0)
        FROM events WHERE client=? AND ts<?""",(client,a)).fetchone()[0]
    usd_opening=int(before_usd or 0);usd_balance=usd_opening;usd_sales=usd_payments=usd_returns=0
    initial=stocks.copy();balance=opening;rows=[];sales=payments=0
    for e in events:
        k=e['kind']
        if k not in ('delivery','sold','return','payment'):continue
        if k in ('delivery','sold','return'):stocks[e['pack']]+=e['qty']*(1 if k=='delivery' else -1)
        charge=e['amount'] if k=='sold' else 0;credit=e['amount'] if k=='payment' else 0
        balance+=charge-credit;sales+=charge;payments+=credit
        usd_charge=e['amount_usd'] if k=='delivery' else 0
        usd_credit=e['amount_usd'] if k in ('payment','return') else 0
        usd_balance+=usd_charge-usd_credit;usd_sales+=usd_charge
        if k=='payment':usd_payments+=usd_credit
        if k=='return':usd_returns+=usd_credit
        rows.append({'id':e['id'],'time':datetime.fromtimestamp(e['ts'],TZ).strftime('%d.%m.%Y %H:%M'),'kind':NAMES[k],'pack':e['pack'],'qty':e['qty'],'charge':charge,'credit':credit,'balance':balance,'usd_charge':usd_charge,'usd_credit':usd_credit,'usd_balance':usd_balance})
    return {'client':rowdict(c),'start':start,'end':end,'opening':opening,'closing':balance,'sales':sales,'payments':payments,'usd_opening':usd_opening,'usd_closing':usd_balance,'usd_sales':usd_sales,'usd_payments':usd_payments,'usd_returns':usd_returns,'opening_stock':initial,'closing_stock':stocks,'rows':rows}

def m(x):return f'{x/100:,.2f}'.replace(',',' ')

def reconciliation_html(r):
    c=r['client'];esc=lambda x:escape(str(x),quote=True)
    stock=''.join(f'<tr><td>{escape(product_name(p))}</td><td>{r["opening_stock"][p]}</td><td>{r["closing_stock"][p]}</td></tr>' for p in (1,3,5))
    rows=''.join('<tr>'+''.join(f'<td>{esc(v)}</td>' for v in [x['id'],x['time'],x['kind'],product_name(x['pack']) if x['pack'] else '—',x['qty'] or '—',m(x['usd_charge']),m(x['usd_credit']),m(x['usd_balance'])])+'</tr>' for x in r['rows'])
    return f'''<!doctype html><html lang="uz"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Ички ҳисоб — акт сверка</title><style>
body{{font:14px Arial,sans-serif;color:#15243b;background:#eef3f8;margin:0;padding:24px}}main{{max-width:1000px;margin:auto;background:white;padding:36px}}h1{{color:#174e87;margin:8px 0}}.muted{{color:#52647a}}.cards{{display:flex;flex-wrap:wrap;gap:16px;margin:24px 0}}.card{{padding:16px;background:#edf4fb;flex:1;min-width:160px}}strong{{display:block;font-size:20px;margin-top:8px}}table{{border-collapse:collapse;width:100%;font-size:12px;margin:18px 0}}th{{background:#174e87;color:white}}td,th{{padding:9px;border:1px solid #d3dce8;text-align:left}}.scroll{{overflow:auto}}footer{{margin-top:32px}}@media print{{body{{background:white;padding:0}}main{{padding:0}}thead{{display:table-header-group}}tr{{break-inside:avoid}}button{{display:none}}}}@page{{size:A4 landscape;margin:14mm}}
</style><main><p class="muted">ИЧКИ САВДО НАЗОРАТИ · ТЕСТ ҲИСОБОТИ</p><h1>Ўзаро ҳисоб-китобларни солиштириш далолатномаси</h1><p>{esc(r['start'])} — {esc(r['end'])} · Тошкент вақти</p><h2>{esc(c['name'])}</h2><p>{esc(c['phone'])} · {esc(c['address'])}</p><div class="cards"><div class="card">Бошланғич қарз<strong>{m(r['usd_opening'])} USD</strong></div><div class="card">Топширилган товар<strong>{m(r['usd_sales'])} USD</strong></div><div class="card">Қайтарилган товар<strong>{m(r['usd_returns'])} USD</strong></div><div class="card">Олинган тўлов<strong>{m(r['usd_payments'])} USD</strong></div><div class="card">Якуний қарз<strong>{m(r['usd_closing'])} USD</strong></div></div><p>Товар топширилганда USD қарз ёзилади, қайтариш ва тўлов қарзни камайтиради. Сотилди деган қайд қарзни қайта оширмайди. Манфий баланс — аванс.</p><p>Эски UZS операциялари алоҳида: бошланғич {m(r['opening'])} сўм, сотув {m(r['sales'])} сўм, тўлов {m(r['payments'])} сўм, қолдиқ {m(r['closing'])} сўм. Бу суммалар USD билан қўшилмайди.</p><h2>Операциялар</h2><div class="scroll"><table><thead><tr><th>№</th><th>Сана</th><th>Амал</th><th>Қадоқ</th><th>Дона</th><th>Топширилган, USD</th><th>Тўлов/қайтариш, USD</th><th>Қарз, USD</th></tr></thead><tbody>{rows or '<tr><td colspan="8">Бу даврда операция йўқ</td></tr>'}</tbody></table></div><h2>Мижоздаги сотилмаган товар</h2><table><thead><tr><th>Маҳсулот</th><th>Давр бошида, дона</th><th>Давр охирида, дона</th></tr></thead><tbody>{stock}</tbody></table><footer><p>Ҳисобот ботга тасдиқлаб киритилган маълумотлар асосида тузилди. Иккинчи томон ҳали тасдиқламаган.</p><p>Масъул ходим: ____________________ &nbsp;&nbsp; Мижоз: ____________________</p></footer></main></html>'''.encode()
