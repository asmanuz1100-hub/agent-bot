"""Deterministic reconciliation, route maps, and daily analytics."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from html import escape
import io,csv,json,time
from core import route_stats,product_name,distance
TZ=ZoneInfo('Asia/Tashkent')
NAMES={'delivery':'Товар топширилди (USD қарз)','sold':'Сотилган миқдор қайд этилди','payment':'USD тўлов олинди','return':'Товар қайтарилди (USD қарз камайди)','order':'Буюртма','visit':'Ташриф / таклиф'}

def rowdict(r):
    return {k:r[k] for k in r.keys()}

def admin_only(db,actor):
    r=db.execute('SELECT role FROM users WHERE id=?',(actor,)).fetchone()
    if not r or r[0]!='admin':raise ValueError('Фақат админ.')

def _safe_json(obj):
    return json.dumps(obj,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')

def _map_html(title, routes, shops, summary,points_only=False,summary_metrics=None):
    total_km=round(sum(float(r.get('km') or 0) for r in routes),2)
    gps_points=sum(len(r.get('points') or []) for r in routes)
    active_shops=sum(1 for s in shops if s.get('active'))
    metrics=summary_metrics or {}
    data=_safe_json({'title':title,'routes':routes,'shops':shops,'summary':summary,
                     'points_only':points_only,'agent_work':metrics.get('agent_work',[])})
    if points_only:
        cards=[
            ('Агентлар',metrics.get('agents',0)),
            ('Жами йўл',f"{metrics.get('km',0)} км"),
            ('Янги мижозлар',len(shops)),
            ('Берилган товар жами',f"{m(metrics.get('delivered',0))} USD"),
            ('Олинган пул жами',f"{m(metrics.get('payments',0))} USD"),
        ]
    else:
        cards=[
            ('Агентлар',len({r.get('agent') for r in routes if r.get('agent')})),
            ('Жами йўл',f'{total_km} км'),
            ('GPS нуқталар',gps_points),
            ('Фаол нуқталар',active_shops),
        ]
    # Total working time is shown prominently in every period, including day
    # maps whose route is empty because Telegram GPS was not shared.
    duration=max(0,int(metrics.get('work_seconds',0)))
    cards.insert(1,('Жами иш вақти',f'{duration//3600} соат {(duration%3600)//60} дақиқа'))
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
.kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(165px,1fr));gap:10px;margin-top:14px}}
.kpi{{background:#f8fafc;border:1px solid var(--line);border-radius:14px;padding:12px 14px}}
.kpi span{{display:block;color:var(--muted);font-size:12px;margin-bottom:5px}} .kpi strong{{font-size:18px}}
.body{{min-height:0;display:grid;grid-template-columns:310px 1fr;gap:14px;padding:14px}}
.side{{background:var(--panel);border:1px solid var(--line);border-radius:18px;box-shadow:var(--shadow);padding:16px;overflow:auto}}
.side h3{{margin:0 0 10px;font-size:15px}} .summary{{font-size:13px;line-height:1.45;color:var(--muted);padding:10px 12px;background:#f8fafc;border-radius:12px}}
.legend{{margin-top:14px;display:flex;flex-direction:column;gap:9px}} .legend-row{{display:flex;align-items:center;gap:9px;font-size:13px}} .work-panel{{margin-top:14px;padding-top:12px;border-top:1px solid var(--line)}} .work-panel h3{{margin-bottom:8px}} .work-row{{padding:8px 0;font-size:13px;line-height:1.5;border-bottom:1px solid var(--line)}} .work-row strong{{display:block;color:var(--text)}}
.dot{{width:10px;height:10px;border-radius:50%;flex:none}} .hint{{margin-top:14px;padding-top:12px;border-top:1px solid var(--line);font-size:12px;color:var(--muted);line-height:1.45}}
.mapwrap{{position:relative;min-height:0;background:var(--panel);border:1px solid var(--line);border-radius:18px;overflow:hidden;box-shadow:var(--shadow)}} #map{{height:100%;min-height:520px}}
.leaflet-popup-content{{font-size:13px;line-height:1.45}} #map-status{{position:absolute;top:10px;left:58px;right:10px;z-index:1000;display:none;padding:11px 14px;border-radius:10px;background:#fff7ed;border:1px solid #fdba74;color:#9a3412;font-size:13px;line-height:1.4;box-shadow:var(--shadow)}}
@media(max-width:820px){{html,body{{height:auto;min-height:100vh;overflow-y:auto}}.app{{height:auto;min-height:100vh;display:block}}.top{{padding:12px}}.title{{font-size:18px}}.kpis{{grid-template-columns:repeat(2,minmax(0,1fr))}}.body{{display:flex;flex-direction:column;padding:10px;gap:10px;min-height:auto}}.mapwrap{{order:0;min-height:55vh;height:55vh}}#map{{height:55vh;min-height:55vh}}.side{{order:1;max-height:none;overflow:visible}}}}
</style></head>
<body><div class="app"><section class="top"><div class="head"><div class="title">{escape(title)}</div><div class="badge">ИЧКИ ФОЙДАЛАНИШ · ТЕСТ</div></div><div class="kpis">{cards_html}</div></section>
<section class="body"><aside class="side"><h3>Қисқа таҳлил</h3><div id="summary" class="summary"></div><div id="agent-work" class="work-panel"></div><div id="legend" class="legend"></div><div class="hint">{escape('Ҳафталик ва ойлик харитада агент траекторияси кўрсатилмайди — фақат шу даврда қўшилган янги мижозлар жойлашуви.' if points_only else 'Маршрут GPS нуқталари асосида қурилади. Масофа ва тўхташлар тахминий. Савдо нуқталари агент киритган мижоз локацияларидан олинади.')}</div></aside><div class="mapwrap"><div id="map"></div><div id="map-status" role="status"></div></div></section></div>
<script id="data" type="application/json">{data}</script><script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
const D=JSON.parse(document.getElementById('data').textContent), map=L.map('map',{{zoomControl:true}});
// OpenFreeMap vector basemap: the volunteer-run OSM raster tile server must not be used here.
const status=document.getElementById('map-status');
function mapWarning(){{status.style.display='block';status.textContent='Фон харитани юклаб бўлмади. Интернетни текширинг ва саҳифани янгиланг.';}}
let fallbackStarted=false;
function addFallbackTiles(){{
  if(fallbackStarted)return;
  fallbackStarted=true;
  try{{
    const fallback=L.tileLayer('https://{{s}}.tile.openstreetmap.fr/hot/{{z}}/{{x}}/{{y}}.png',{{
      maxZoom:19,subdomains:'abc',
      attribution:'© OpenStreetMap contributors · HOT'
    }});
    fallback.on('tileerror',mapWarning);
    fallback.on('load',()=>{{status.style.display='none';}});
    fallback.addTo(map);
  }}catch(e){{console.warn('Fallback map unavailable',e);mapWarning();}}
}}
try{{
  const basemap=L.tileLayer('https://tile.openstreetmap.de/{{z}}/{{x}}/{{y}}.png',{{
    maxZoom:19,
    attribution:'© OpenStreetMap contributors'
  }});
  let errors=0;
  basemap.on('tileerror',()=>{{errors+=1;if(errors>=2)addFallbackTiles();}});
  basemap.on('load',()=>{{status.style.display='none';}});
  basemap.addTo(map);
  setTimeout(()=>{{if(!map._loaded)addFallbackTiles();}},5000);
}}catch(e){{console.warn('Primary map unavailable',e);addFallbackTiles();}}
const bounds=[]; const colors=['#2563eb','#f59e0b','#16a34a','#7c3aed','#e11d48','#0891b2','#9333ea','#475569'];
function esc(s){{return String(s??'').replace(/[&<>"']/g,m=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[m]));}}
const legend=document.getElementById('legend');
const workPanel=document.getElementById('agent-work');
if(D.agent_work.length){{
  const heading=document.createElement('h3');heading.textContent='Агентлар иш вақти';workPanel.appendChild(heading);
  D.agent_work.forEach(a=>{{
    const line=document.createElement('div');line.className='work-row';
    const who=document.createElement('strong');who.textContent=a.name+' · '+a.hours;
    const totals=document.createElement('span');totals.textContent=a.km+' км · '+a.new_clients+' янги мижоз';
    line.appendChild(who);line.appendChild(totals);workPanel.appendChild(line);
  }});
}}
D.routes.forEach((r,i)=>{{const color=colors[i%colors.length];
  const segments=r.segments||[r.points||[]];let first=null,last=null;
  segments.forEach(seg=>{{const pts=seg.map(p=>[p.lat,p.lon]);if(!pts.length)return;
    L.polyline(pts,{{weight:5,color,opacity:.9}}).addTo(map).bindTooltip(esc(r.agent));
    pts.forEach(x=>bounds.push(x));if(!first)first=pts[0];last=pts[pts.length-1];
  }});
  if(first)L.circleMarker(first,{{radius:6,color,fillOpacity:1}}).addTo(map).bindPopup('Бошланиш · '+esc(r.agent));
  if(last){{L.circleMarker(last,{{radius:7,color,fillOpacity:1}}).addTo(map).bindPopup('Охирги GPS нуқта · '+esc(r.agent)+'<br><a rel="noreferrer" target="_blank" href="https://www.google.com/maps/dir/?api=1&destination='+last[0]+','+last[1]+'">Навигаторда очиш</a>');}}
  const row=document.createElement('div');row.className='legend-row';row.innerHTML='<span class="dot" style="background:'+color+'"></span><span>'+esc(r.agent)+' · '+esc(r.km||0)+' км · '+esc(segments.length)+' смена</span>';legend.appendChild(row);
}});
D.shops.forEach(s=>{{if(s.lat==null||s.lon==null)return; const p=[s.lat,s.lon];if(D.points_only||(!bounds.length&&s.active))bounds.push(p);
  L.circleMarker(p,{{radius:s.active?9:6,weight:s.active?3:1,color:s.active?'#0f766e':'#64748b',fillColor:s.active?'#14b8a6':'#cbd5e1',fillOpacity:s.active?.9:.65}})
   .addTo(map).bindPopup('<b>'+esc(s.shop||s.name)+'</b><br>'+esc(s.name)+'<br>'+esc(s.address)+'<br>'+(D.points_only?'🆕 Янги мижоз':(s.active?'✅ Фаол савдо нуқтаси':'Қайд этилган савдо нуқтаси'))+(s.card_url?'<br><a target="_blank" rel="noopener noreferrer" href="'+esc(s.card_url)+'">👤 Мижоз карточкасини очиш</a>':'')+'<br><a target="_blank" rel="noopener noreferrer" href="https://www.google.com/maps/dir/?api=1&destination='+p[0]+','+p[1]+'">Навигаторда очиш</a>');
}});
document.getElementById('summary').textContent=D.summary||'Маълумот йўқ';
if(D.points_only&&!D.shops.length){{
  const note=document.createElement('div');note.className='work-row';
  note.textContent='Шу даврда локацияси киритилган янги мижоз йўқ. Харита фон сифатида очиқ, янги мижоз қўшилганда нуқта пайдо бўлади.';
  workPanel.appendChild(note);
}}
if(bounds.length)map.fitBounds(bounds,{{padding:[35,35],maxZoom:16}});else map.setView([41.3,69.24],7);setTimeout(()=>map.invalidateSize(),250);
</script></body></html>'''.encode('utf-8')

def client_card_html(db,actor,client_id,photo_url=None):
    """Read-only customer card for administrators holding a short-lived URL.

    Card endpoints verify their own signature before calling this function.
    No Telegram credentials or user-supplied HTML are embedded in the page.
    """
    admin_only(db,actor)
    customer=db.execute('SELECT * FROM clients WHERE id=?',(client_id,)).fetchone()
    if not customer:raise ValueError('Мижоз топилмади.')
    from core import client_debt_usd,legacy_debt_uzs,client_stock
    owner=db.execute('SELECT name FROM users WHERE id=?',(customer['agent'],)).fetchone()
    owner_name=(owner[0] if owner else None) or str(customer['agent'])
    e=lambda value:escape(str(value if value is not None else ''),quote=True)
    name=e(customer['name'] or 'Номсиз мижоз')
    shop=e(customer['shop_name'] or 'Дўкон номи киритилмаган')
    full_name=e(owner_name)
    phone=e(customer['phone'] or 'Телефон киритилмаган')
    address=e(customer['address'] or 'Манзил киритилмаган')
    comment=e(customer['comment'] or 'Изоҳ киритилмаган')
    due=e(customer['payment_due'] or 'Аниқ эмас')
    products=''.join('<tr><td>'+e(product_name(pack))+'</td><td>'+
                     str(int(client_stock(db,customer['agent'],client_id,pack)))+
                     ' дона</td></tr>' for pack in (1,3,5))
    debt=client_debt_usd(db,client_id)
    old=legacy_debt_uzs(db,client_id)
    legacy=('<div class="field">Эски сўм ҳисоби: <strong>'+f'{old/100:,.2f} сўм'+'</strong></div>') if old else ''
    loc=''
    if customer['lat'] is not None and customer['lon'] is not None:
        lat=float(customer['lat']);lon=float(customer['lon'])
        loc='<a class="action" rel="noopener noreferrer" target="_blank" href="https://www.google.com/maps/dir/?api=1&destination='+str(lat)+','+str(lon)+'">📍 Навигаторда очиш</a>'
    photo=('<img class="photo" src="'+e(photo_url)+'" alt="Мижозга бириктирилган фото" loading="lazy">' if customer['photo'] and photo_url else
           '<div class="subtle">Фото ботдаги мижоз карточкасида мавжуд.</div>' if customer['photo'] else
           '<div class="subtle">Фото бириктирилмаган.</div>')
    content=f"""<!doctype html><html lang="uz"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Мижоз #{int(client_id)} · {shop}</title>
<style>
*{{box-sizing:border-box}}body{{margin:0;background:#f3f6fb;color:#15243b;font-family:Arial,sans-serif}}
main{{max-width:780px;margin:32px auto;padding:0 14px}}article{{background:white;border:1px solid #e4eaf3;border-radius:20px;padding:24px;box-shadow:0 12px 35px #1c365010}}
h1{{margin:0 0 8px;font-size:24px}}.subtle{{color:#64748b;font-size:13px;margin:8px 0 18px}}.field{{margin:13px 0;line-height:1.5}}
.tag{{display:inline-block;background:#eaf3ff;padding:6px 11px;border-radius:24px;color:#1d4ed8;font-weight:600}}
.photo{{width:100%;max-height:380px;object-fit:contain;border:1px solid #e4eaf3;border-radius:14px;margin:14px 0}}
table{{border-collapse:collapse;width:100%;margin:12px 0}}td{{border-bottom:1px solid #e4eaf3;padding:12px 5px}}td:last-child{{text-align:right;font-weight:600}}
.action{{display:inline-block;margin:16px 0;padding:11px 16px;background:#1d4ed8;color:#fff;text-decoration:none;border-radius:10px}}
</style></head><body><main><article><span class="tag">👤 МИЖОЗ #{int(client_id)}</span>
<h1>{shop}</h1><div class="subtle">{name}</div>{photo}
<div class="field">👨‍💼 Бириктирилган агент: <strong>{full_name}</strong></div>
<div class="field">📞 Телефон: <strong>{phone}</strong></div>
<div class="field">🏠 Манзил: {address}</div>
<div class="field">📝 Изоҳ: {comment}</div>
<div class="field">📅 Тўлов санаси: {due}</div>
<h2>📦 Мижоздаги товар</h2><table>{products}</table>
<div class="field">💵 Мижоз қарзи: <strong>{debt/100:,.2f} USD</strong></div>
{legacy}{loc}<p class="subtle">Карточка фақат кўриш учун. Маълумотни ўзгартириш — ботнинг «👥 Мижозлар» бўлимида.</p>
</article></main></body></html>"""
    return content.encode('utf-8')

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
    end=int(shift['end'] or time.time())
    day=datetime.fromtimestamp(end,TZ).replace(hour=0,minute=0,second=0,microsecond=0)
    day_start=int(day.timestamp())
    # Summarize the whole work day once, not each shift as an additional daily total.
    # Ignore shifts that happened after the shift being reported.
    shifts=db.execute("""SELECT * FROM shifts WHERE agent=? AND start<=?
        AND (end IS NULL OR end>=?) ORDER BY start,id""",(agent,end,day_start)).fetchall()
    start=min(max(int(s['start']),day_start) for s in shifts)
    user=db.execute('SELECT name FROM users WHERE id=?',(agent,)).fetchone()
    name=(user[0] if user else str(agent)) or str(agent)
    km=0;gaps=[];seen=set();points=[];duration=0
    for sh in shifts:
        lo=max(day_start,int(sh['start']));hi=min(end,int(sh['end'] or end))
        if hi<lo:continue
        duration+=max(0,hi-lo)
        pts=[]
        for p in db.execute('SELECT * FROM points WHERE shift=? AND ts>=? AND ts<=? ORDER BY ts,id',
                            (sh['id'],lo,hi)).fetchall():
            key=(p['ts'],round(float(p['lat']),6),round(float(p['lon']),6))
            if key not in seen:
                seen.add(key);pts.append(p);points.append(p)
        if pts:
            segment=route_stats(pts,lo,hi)
            km+=segment['km'];gaps.extend(segment['gaps'])
    points.sort(key=lambda x:x['ts'])
    metric=db.execute("""SELECT
        COUNT(DISTINCT client),
        COALESCE(SUM(CASE WHEN kind='visit' THEN 1 ELSE 0 END),0),
        COALESCE(SUM(CASE WHEN kind='sold' THEN qty ELSE 0 END),0),
        COALESCE(SUM(CASE WHEN kind='delivery' THEN amount_usd WHEN kind='return' THEN -amount_usd ELSE 0 END),0),
        COALESCE(SUM(CASE WHEN kind='payment' THEN amount_usd ELSE 0 END),0),
        COALESCE(SUM(CASE WHEN kind='delivery' THEN qty ELSE 0 END),0),
        COALESCE(SUM(CASE WHEN kind='order' THEN qty ELSE 0 END),0),
        COALESCE(SUM(CASE WHEN kind='return' THEN qty ELSE 0 END),0)
        FROM events WHERE agent=? AND ts>=? AND ts<=?""",(agent,day_start,end)).fetchone()
    new_clients=db.execute(
        'SELECT COUNT(*) FROM clients WHERE agent=? AND created_ts IS NOT NULL AND created_ts>=? AND created_ts<=?',
        (agent,day_start,end)
    ).fetchone()[0]
    active_clients=int(metric[0] or 0);visits=int(metric[1] or 0)
    sold_qty=int(metric[2] or 0);sold_amount=int(metric[3] or 0)
    payments=int(metric[4] or 0);delivered=int(metric[5] or 0)
    orders=int(metric[6] or 0);returns=int(metric[7] or 0)
    hours=duration//3600;minutes=(duration%3600)//60
    first=points[0] if points else None;last=points[-1] if points else None
    stats={'km':round(km,2),'gaps':gaps}
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
        f"⏱ Жами иш вақти: {hours} соат {minutes} дақиқа · сменалар: {len(shifts)} та\n"
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
        'duration':duration,'shift_count':len(shifts),'km':stats['km'],'gps_points':len(points),'gaps':len(stats['gaps']),
        'new_clients':int(new_clients),'active_clients':active_clients,'visits':visits,
        'sold_qty':sold_qty,'sold_amount':sold_amount,'payments':payments,
        'delivered':delivered,'orders':orders,'returns':returns,
        'first':rowdict(first) if first else None,'last':rowdict(last) if last else None,
        'text':text
    }

def route_map_html(db,actor,agent,card_url=None):
    admin_only(db,actor)
    shift=db.execute('SELECT * FROM shifts WHERE agent=? ORDER BY id DESC LIMIT 1',(agent,)).fetchone()
    if not shift:raise ValueError('Бу агент ҳали иш бошламаган.')
    route,shops,stats,active=shift_route_data(db,agent,shift)
    if card_url:
        for shop in shops:shop['card_url']=card_url(int(shop['id']))
    summary=f"{stats['km']} км · {active} фаол савдо нуқтаси · {len(stats['stops'])} тўхташ · {len(stats['gaps'])} узилиш"
    return _map_html(f'Агент {agent} · смена #{shift["id"]}',[route],shops,summary),stats,active

def overall(db,actor,now=None,period='day',card_url=None):
    """Summarize a calendar day/week/month (Tashkent time).

    Day map contains actual GPS trajectories. Week/month maps contain ONLY
    locations of clients first registered during the requested period.
    """
    admin_only(db,actor)
    now=now or datetime.now(TZ)
    now=now.astimezone(TZ)
    if period not in ('day','week','month'):
        raise ValueError('Таҳлил даври нотўғри.')
    midnight=now.replace(hour=0,minute=0,second=0,microsecond=0)
    if period=='day':
        start=midnight;label='1 КУНЛИК';map_label='кунлик маршрут'
    elif period=='week':
        start=midnight-timedelta(days=now.weekday());label='1 ҲАФТАЛИК';map_label='ҳафталик янги савдо нуқталари'
    else:
        start=midnight.replace(day=1);label='1 ОЙЛИК';map_label='ойлик янги савдо нуқталари'
    a=int(start.timestamp());b=int(now.timestamp())+1
    agents=db.execute("SELECT id,name,role FROM users WHERE role IN ('agent','disabled') ORDER BY name").fetchall()
    routes=[];all_shops=[];total_km=0;stops=gaps=0;gps_points=0;agent_work=[]
    total_hours=0;total_new=0;total_sales=0;unpriced=0;unpriced_deliveries=0
    details=[]
    for ag in agents:
        aid=int(ag[0]);name=ag[1] or str(aid)
        if ag[2]=='disabled':
            historically_active=db.execute("""SELECT 1 FROM events WHERE agent=? AND ts>=? AND ts<?
                UNION SELECT 1 FROM shifts WHERE agent=? AND start<? AND (end IS NULL OR end>=?)
                UNION SELECT 1 FROM clients WHERE agent=? AND created_ts>=? AND created_ts<? LIMIT 1""",
                (aid,a,b,aid,b,a,aid,a,b)).fetchone()
            if not historically_active:continue
        shifts=db.execute('SELECT * FROM shifts WHERE agent=? AND start<? AND (end IS NULL OR end>=?) ORDER BY start,id',(aid,b,a)).fetchall()
        akm=0;astops=agaps=0;segments=[];seen_points=set();worked=0
        for sh in shifts:
            lo=max(a,int(sh['start']));hi=min(b-1,int(sh['end'] or b-1))
            if hi<lo:continue
            worked+=max(0,hi-lo)
            raw=db.execute('SELECT * FROM points WHERE shift=? AND ts>=? AND ts<=? ORDER BY ts,id',(sh['id'],lo,hi)).fetchall()
            pts=[]
            for p in raw:
                key=(int(p['ts']),round(float(p['lat']),6),round(float(p['lon']),6))
                if key in seen_points:continue
                seen_points.add(key);pts.append(p)
            if not pts:continue
            stats=route_stats(pts,lo,hi);akm+=stats['km']
            astops+=len(stats['stops']);agaps+=len(stats['gaps']);gps_points+=len(pts)
            if period!='day':continue
            seg=[];prev=None
            for p in pts:
                if (p['accuracy'] or 0)>100:
                    if seg:segments.append(seg);seg=[]
                    prev=None;continue
                if prev and (p['ts']-prev['ts']>300 or p['ts']<=prev['ts'] or
                    distance(prev,p)/max(1,p['ts']-prev['ts'])>55):
                    if seg:segments.append(seg)
                    seg=[]
                seg.append({'lat':p['lat'],'lon':p['lon'],'ts':p['ts']})
                prev=p
            if seg:segments.append(seg)
        if period=='day':
            active={r[0] for r in db.execute(
                'SELECT DISTINCT client FROM events WHERE agent=? AND client IS NOT NULL AND ts>=? AND ts<?',
                (aid,a,b)).fetchall()}
            shops=db.execute('SELECT id,name,shop_name,address,lat,lon FROM clients WHERE agent=? AND lat IS NOT NULL AND lon IS NOT NULL',(aid,)).fetchall()
            for shop in shops:
                all_shops.append({'id':shop['id'],'name':shop['name'],'shop':shop['shop_name'],
                    'address':shop['address'],'lat':shop['lat'],'lon':shop['lon'],'active':shop['id'] in active})
            if segments:
                routes.append({'agent':name,'agent_id':aid,'km':round(akm,2),
                    'points':[p for seg in segments for p in seg],'segments':segments})
        else:
            # New shops only: old customers and every GPS track stay out of
            # the weekly/monthly map's JSON and HTML.
            shops=db.execute("""SELECT id,name,shop_name,address,lat,lon FROM clients
                WHERE agent=? AND created_ts>=? AND created_ts<? AND lat IS NOT NULL AND lon IS NOT NULL
                ORDER BY created_ts,id""",(aid,a,b)).fetchall()
            for shop in shops:
                all_shops.append({'id':shop['id'],'name':shop['name'],'shop':shop['shop_name'],
                    'address':shop['address'],'lat':shop['lat'],'lon':shop['lon'],'active':True})
        metric=db.execute("""SELECT
            COUNT(DISTINCT client),
            COALESCE(SUM(CASE WHEN kind='sold' THEN qty ELSE 0 END),0),
            COALESCE(SUM(CASE WHEN kind='sold' THEN amount_usd ELSE 0 END),0),
            COALESCE(SUM(CASE WHEN kind='delivery' THEN amount_usd ELSE 0 END),0),
            COALESCE(SUM(CASE WHEN kind='payment' THEN amount_usd ELSE 0 END),0),
            COALESCE(SUM(CASE WHEN kind='sold' AND amount_usd=0 THEN qty ELSE 0 END),0),
            COALESCE(SUM(CASE WHEN kind='delivery' AND amount_usd=0 THEN qty ELSE 0 END),0)
            FROM events WHERE agent=? AND ts>=? AND ts<?""",(aid,a,b)).fetchone()
        active_count=int(metric[0] or 0);sold_qty=int(metric[1] or 0)
        sold=int(metric[2] or 0);delivered=int(metric[3] or 0)
        paid=int(metric[4] or 0);missing=int(metric[5] or 0);delivery_missing=int(metric[6] or 0)
        new=int(db.execute('SELECT COUNT(*) FROM clients WHERE agent=? AND created_ts>=? AND created_ts<?',
                           (aid,a,b)).fetchone()[0])
        total_hours+=worked;total_new+=new;total_sales+=sold;unpriced+=missing;unpriced_deliveries+=delivery_missing
        hours=worked//3600;minutes=(worked%3600)//60
        agent_work.append({'name':name,'hours':f'{hours} соат {minutes} дақиқа',
                           'km':round(akm,2),'new_clients':new})
        details.append(f"{name} ({aid}): иш {hours} соат {minutes} дақиқа · {round(akm,2)} км · "
                       f"янги мижоз {new} та · сотув {sold_qty} дона / {m(sold)} USD · "
                       f"берилган товар жами {m(delivered)} USD · олинган пул жами {m(paid)} USD")
        total_km+=akm;stops+=astops;gaps+=agaps
    total_sold=db.execute("""SELECT COALESCE(SUM(CASE WHEN kind='sold' THEN qty ELSE 0 END),0),
        COALESCE(SUM(CASE WHEN kind='delivery' THEN amount_usd ELSE 0 END),0),
        COALESCE(SUM(CASE WHEN kind='payment' THEN amount_usd ELSE 0 END),0)
        FROM events WHERE ts>=? AND ts<?""",(a,b)).fetchone()
    worked=f"{total_hours//3600} соат {(total_hours%3600)//60} дақиқа"
    text=(f"📊 {label} УМУМИЙ ТАҲЛИЛ · {start:%d.%m.%Y} — {now:%d.%m.%Y %H:%M}\n"
          f"Жами агент: {len(agents)}\nЖами иш соати: {worked}\nЖами масофа: {round(total_km,2)} км\n"
          f"Янги мижозлар: {total_new} та\n"
          f"📦 Берилган товарнинг умумий суммаси: {m(int(total_sold[1] or 0))} USD\n"
          f"💰 Олинган пулнинг умумий суммаси: {m(int(total_sold[2] or 0))} USD\n"
          f"Сотилган товар: {int(total_sold[0] or 0)} дона · сотув қиймати: {m(total_sales)} USD\n"
          + (f"⚠️ Олдинги версиядаги {unpriced} дона сотувнинг USD баҳоси сақланмаган — сотув қиймати жамига кирмаган.\n" if unpriced else '')
          + (f"⚠️ {unpriced_deliveries} дона аввалги топшириш USD нархисиз сақланган: берилган товар жамига тахминий қўшилмади.\n" if unpriced_deliveries else '')
          + ("\nАгентлар:\n"+"\n".join(details) if details else "\nАгент йўқ."))
    if period=='day':
        text+=f"\nGPS нуқталари: {gps_points} · тўхташ: {stops} · узилиш: {gaps}"
        if not gps_points:text+='\n⚠️ Бугун GPS нуқталари сақланмаган.'
    else:
        text+='\n🗺 Харитада фақат шу даврда қўшилган янги мижозлар кўринади; агент траекторияси чизилмайди.'
    delivered_total=int(total_sold[1] or 0)
    payments_total=int(total_sold[2] or 0)
    if card_url:
        for shop in all_shops:shop['card_url']=card_url(int(shop['id']))
    summary=(f"{worked} иш · {round(total_km,2)} км · {total_new} янги мижоз · "
             f"берилган товар {m(delivered_total)} USD · олинган пул {m(payments_total)} USD")
    html=_map_html(f'{label} · {map_label}',routes if period=='day' else [],all_shops,summary,
                   points_only=(period!='day'),summary_metrics={'agents':len(details),
                   'km':round(total_km,2),'delivered':delivered_total,'payments':payments_total,
                   'work_seconds':total_hours,'agent_work':agent_work})
    return text,html

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

def reconciliation(db,actor,client,start=None,end=None):
    c=db.execute('SELECT * FROM clients WHERE id=?',(client,)).fetchone()
    if not c:raise ValueError('Мижоз топилмади.')
    auth(db,actor,c['agent'])
    if start is None and end is None:
        a,b=0,int(time.time())+1
        start,end='Барча давр','Ҳозиргача'
    elif start is not None and end is not None:a,b=dates(start,end)
    else:raise ValueError('Иккала санани ҳам киритинг ёки умумий акт сверкадан фойдаланинг.')
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


def all_clients_statement_rows(db,actor):
    """Return the manager-only all-customer reconciliation table."""
    admin_only(db,actor)
    clients=db.execute("""SELECT c.id,c.name,c.shop_name,c.address,c.phone,c.agent,
        COALESCE(u.name,CAST(c.agent AS TEXT)) AS agent_name
        FROM clients c LEFT JOIN users u ON u.id=c.agent
        ORDER BY c.id""").fetchall()
    result=[]
    for c in clients:
        products=db.execute("""SELECT pack,COALESCE(SUM(qty),0) AS qty
            FROM events WHERE client=? AND kind='delivery' AND qty>0
            GROUP BY pack ORDER BY pack""",(c['id'],)).fetchall()
        debt=db.execute("""SELECT COALESCE(SUM(CASE WHEN kind='delivery' THEN amount_usd
            WHEN kind IN ('payment','return') THEN -amount_usd ELSE 0 END),0)
            FROM events WHERE client=?""",(c['id'],)).fetchone()[0]
        result.append({
            'id':int(c['id']),'name':c['name'] or 'Номсиз',
            'shop_name':c['shop_name'] or '—','address':c['address'] or '—',
            'phone':c['phone'] or '—','agent_name':c['agent_name'] or str(c['agent']),
            'products':[(product_name(p['pack']),int(p['qty'] or 0)) for p in products],
            'debt':int(debt or 0)
        })
    return result

def all_clients_xlsx(db,actor):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment,Font,PatternFill,Border,Side
    rows=all_clients_statement_rows(db,actor)
    wb=Workbook();ws=wb.active;ws.title='Барча мижозлар'
    ws.merge_cells('A1:H1');ws['A1']='ASMAN SILICAT — БАРЧА МИЖОЗЛАР АКТ СВЕРКА'
    ws['A1'].font=Font(bold=True,size=15,color='FFFFFF');ws['A1'].fill=PatternFill('solid',fgColor='123747')
    ws['A1'].alignment=Alignment(horizontal='center',vertical='center');ws.row_dimensions[1].height=28
    headers=['№','Мижоз номи','Магазин номи','Манзил','Телефон','Агент','Олган товарлари','Қарзи, USD']
    for col,title in enumerate(headers,1):
        cell=ws.cell(3,col,title);cell.font=Font(bold=True,color='FFFFFF');cell.fill=PatternFill('solid',fgColor='087F8C');cell.alignment=Alignment(horizontal='center',vertical='center',wrap_text=True)
    thin=Side(style='thin',color='D8E2E7')
    for number,row in enumerate(rows,1):
        products='\n'.join(f'{name} — {qty} дона' for name,qty in row['products']) or 'Товар берилмаган'
        values=[number,row['name'],row['shop_name'],row['address'],row['phone'],row['agent_name'],products,row['debt']/100]
        excel_row=number+3
        for col,value in enumerate(values,1):
            cell=ws.cell(excel_row,col,value);cell.alignment=Alignment(vertical='top',wrap_text=True)
            cell.border=Border(bottom=thin)
        ws.cell(excel_row,8).number_format='#,##0.00'
        ws.row_dimensions[excel_row].height=max(30,15*(products.count('\n')+1))
    total_row=len(rows)+4
    ws.merge_cells(start_row=total_row,start_column=1,end_row=total_row,end_column=7)
    ws.cell(total_row,1,'Жами қарздорлик');ws.cell(total_row,8,sum(x['debt'] for x in rows)/100)
    for col in range(1,9):
        cell=ws.cell(total_row,col);cell.font=Font(bold=True,color='9C2631');cell.fill=PatternFill('solid',fgColor='FDECEF')
    ws.cell(total_row,8).number_format='#,##0.00'
    widths=[7,24,24,35,20,22,42,16]
    for idx,width in enumerate(widths,1):ws.column_dimensions[chr(64+idx)].width=width
    ws.freeze_panes='A4';ws.auto_filter.ref=f'A3:H{max(3,total_row-1)}';ws.sheet_view.showGridLines=False
    out=io.BytesIO();wb.save(out);return out.getvalue()

def _pdf_font():
    import os
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    candidates=[os.getenv('PDF_FONT_PATH',''),'/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf','/usr/share/fonts/dejavu/DejaVuSans.ttf']
    for path in candidates:
        if path and os.path.exists(path):
            if 'ASMANDejaVu' not in pdfmetrics.getRegisteredFontNames():pdfmetrics.registerFont(TTFont('ASMANDejaVu',path))
            return 'ASMANDejaVu'
    raise RuntimeError('PDF учун кирилл шрифти топилмади.')

def all_clients_pdf(db,actor):
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER,TA_RIGHT
    from reportlab.lib.pagesizes import A4,landscape
    from reportlab.lib.styles import ParagraphStyle,getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate,Table,TableStyle,Paragraph,Spacer
    rows=all_clients_statement_rows(db,actor);font=_pdf_font();out=io.BytesIO()
    doc=SimpleDocTemplate(out,pagesize=landscape(A4),leftMargin=9*mm,rightMargin=9*mm,topMargin=10*mm,bottomMargin=10*mm,
                          title='ASMAN SILICAT — Барча мижозлар акт сверка')
    styles=getSampleStyleSheet();title=ParagraphStyle('AsmanTitle',parent=styles['Title'],fontName=font,fontSize=15,leading=19,textColor=colors.HexColor('#123747'),alignment=TA_CENTER)
    normal=ParagraphStyle('AsmanNormal',parent=styles['BodyText'],fontName=font,fontSize=7.4,leading=10)
    right=ParagraphStyle('AsmanRight',parent=normal,alignment=TA_RIGHT)
    esc=lambda value:escape(str(value or '—'),quote=True)
    data=[[Paragraph(f'<b>{esc(x)}</b>',normal) for x in ['№','Мижоз номи','Магазин номи','Манзил','Телефон','Агент','Олган товарлари','Қарзи, USD']]]
    for number,row in enumerate(rows,1):
        products='<br/>'.join(f'{esc(name)} — {qty} дона' for name,qty in row['products']) or 'Товар берилмаган'
        data.append([Paragraph(str(number),normal),Paragraph(esc(row['name']),normal),Paragraph(esc(row['shop_name']),normal),Paragraph(esc(row['address']),normal),Paragraph(esc(row['phone']),normal),Paragraph(esc(row['agent_name']),normal),Paragraph(products,normal),Paragraph(m(row['debt']),right)])
    data.append([Paragraph('<b>Жами қарздорлик</b>',normal),'','','','','','',Paragraph(f'<b>{m(sum(x["debt"] for x in rows))}</b>',right)])
    table=Table(data,colWidths=[8*mm,29*mm,29*mm,43*mm,27*mm,27*mm,68*mm,22*mm],repeatRows=1)
    table.setStyle(TableStyle([('FONTNAME',(0,0),(-1,-1),font),('BACKGROUND',(0,0),(-1,0),colors.HexColor('#087F8C')),('TEXTCOLOR',(0,0),(-1,0),colors.white),('VALIGN',(0,0),(-1,-1),'TOP'),('GRID',(0,0),(-1,-2),0.25,colors.HexColor('#D8E2E7')),('BACKGROUND',(0,-1),(-1,-1),colors.HexColor('#FDECEF')),('SPAN',(0,-1),(6,-1)),('ALIGN',(7,1),(7,-1),'RIGHT'),('LEFTPADDING',(0,0),(-1,-1),4),('RIGHTPADDING',(0,0),(-1,-1),4),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5)]))
    generated=datetime.now(TZ).strftime('%d.%m.%Y %H:%M')
    story=[Paragraph('ASMAN SILICAT — БАРЧА МИЖОЗЛАР АКТ СВЕРКА',title),Spacer(1,4*mm),table,Spacer(1,3*mm),Paragraph(f'Мижозлар: {len(rows)} та · Тузилган вақт: {generated} · Тошкент вақти',normal)]
    doc.build(story);return out.getvalue()

def m(x):return f'{x/100:,.2f}'.replace(',',' ')

def reconciliation_html(r):
    c=r['client'];esc=lambda x:escape(str(x),quote=True)
    stock=''.join(f'<tr><td>{escape(product_name(p))}</td><td>{r["opening_stock"][p]}</td><td>{r["closing_stock"][p]}</td></tr>' for p in (1,3,5))
    rows=''.join('<tr>'+''.join(f'<td>{esc(v)}</td>' for v in [x['id'],x['time'],x['kind'],product_name(x['pack']) if x['pack'] else '—',x['qty'] or '—',m(x['usd_charge']),m(x['usd_credit']),m(x['usd_balance'])])+'</tr>' for x in r['rows'])
    return f'''<!doctype html><html lang="uz"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Ички ҳисоб — акт сверка</title><style>
body{{font:14px Arial,sans-serif;color:#15243b;background:#eef3f8;margin:0;padding:24px}}main{{max-width:1000px;margin:auto;background:white;padding:36px}}h1{{color:#174e87;margin:8px 0}}.muted{{color:#52647a}}.cards{{display:flex;flex-wrap:wrap;gap:16px;margin:24px 0}}.card{{padding:16px;background:#edf4fb;flex:1;min-width:160px}}strong{{display:block;font-size:20px;margin-top:8px}}table{{border-collapse:collapse;width:100%;font-size:12px;margin:18px 0}}th{{background:#174e87;color:white}}td,th{{padding:9px;border:1px solid #d3dce8;text-align:left}}.scroll{{overflow:auto}}footer{{margin-top:32px}}@media print{{body{{background:white;padding:0}}main{{padding:0}}thead{{display:table-header-group}}tr{{break-inside:avoid}}button{{display:none}}}}@page{{size:A4 landscape;margin:14mm}}
</style><main><p class="muted">ИЧКИ САВДО НАЗОРАТИ · ТЕСТ ҲИСОБОТИ</p><h1>Ўзаро ҳисоб-китобларни солиштириш далолатномаси</h1><p>{esc(r['start'])} — {esc(r['end'])} · Тошкент вақти</p><h2>{esc(c['name'])}</h2><p>{esc(c['phone'])} · {esc(c['address'])}</p><div class="cards"><div class="card">Бошланғич қарз<strong>{m(r['usd_opening'])} USD</strong></div><div class="card">Топширилган товар<strong>{m(r['usd_sales'])} USD</strong></div><div class="card">Қайтарилган товар<strong>{m(r['usd_returns'])} USD</strong></div><div class="card">Олинган тўлов<strong>{m(r['usd_payments'])} USD</strong></div><div class="card">Якуний қарз<strong>{m(r['usd_closing'])} USD</strong></div></div><p>Товар топширилганда USD қарз ёзилади, қайтариш ва тўлов қарзни камайтиради. Сотилди деган қайд қарзни қайта оширмайди. Манфий баланс — аванс.</p><p>Эски UZS операциялари алоҳида: бошланғич {m(r['opening'])} сўм, сотув {m(r['sales'])} сўм, тўлов {m(r['payments'])} сўм, қолдиқ {m(r['closing'])} сўм. Бу суммалар USD билан қўшилмайди.</p><h2>Операциялар</h2><div class="scroll"><table><thead><tr><th>№</th><th>Сана</th><th>Амал</th><th>Қадоқ</th><th>Дона</th><th>Топширилган, USD</th><th>Тўлов/қайтариш, USD</th><th>Қарз, USD</th></tr></thead><tbody>{rows or '<tr><td colspan="8">Бу даврда операция йўқ</td></tr>'}</tbody></table></div><h2>Мижоздаги сотилмаган товар</h2><table><thead><tr><th>Маҳсулот</th><th>Давр бошида, дона</th><th>Давр охирида, дона</th></tr></thead><tbody>{stock}</tbody></table><footer><p>Ҳисобот ботга тасдиқлаб киритилган маълумотлар асосида тузилди. Иккинчи томон ҳали тасдиқламаган.</p><p>Масъул ходим: ____________________ &nbsp;&nbsp; Мижоз: ____________________</p></footer></main></html>'''.encode()
