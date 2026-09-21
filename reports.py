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
    data=_safe_json({'title':title,'routes':routes,'shops':shops,'summary':summary,'points_only':points_only})
    if points_only:
        metrics=summary_metrics or {}
        cards=[
            ('Агентлар',metrics.get('agents',0)),
            ('Жами йўл',f"{metrics.get('km',0)} км"),
            ('Янги мижозлар',len(shops)),
            ('Савдо суммаси',f"{m(metrics.get('sales',0))} USD"),
        ]
    else:
        cards=[
            ('Агентлар',len({r.get('agent') for r in routes if r.get('agent')})),
            ('Жами йўл',f'{total_km} км'),
            ('GPS нуқталар',gps_points),
            ('Фаол нуқталар',active_shops),
        ]
    cards_html=''.join(f'<div class="kpi"><span>{escape(str(k))}</span><strong>{escape(str(v))}</strong></div>' for k,v in cards)
    return f'''<!doctype html><html lang="uz"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(title)}</title><link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"><link rel="stylesheet" href="https://unpkg.com/maplibre-gl@5/dist/maplibre-gl.css">
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
.leaflet-popup-content{{font-size:13px;line-height:1.45}} #map-status{{position:absolute;top:10px;left:58px;right:10px;z-index:1000;display:none;padding:11px 14px;border-radius:10px;background:#fff7ed;border:1px solid #fdba74;color:#9a3412;font-size:13px;line-height:1.4;box-shadow:var(--shadow)}}
@media(max-width:820px){{.kpis{{grid-template-columns:repeat(2,1fr)}}.body{{grid-template-columns:1fr;grid-template-rows:auto 1fr}}.side{{max-height:220px}}#map{{min-height:520px}}}}
</style></head>
<body><div class="app"><section class="top"><div class="head"><div class="title">{escape(title)}</div><div class="badge">ИЧКИ ФОЙДАЛАНИШ · ТЕСТ</div></div><div class="kpis">{cards_html}</div></section>
<section class="body"><aside class="side"><h3>Қисқа таҳлил</h3><div id="summary" class="summary"></div><div id="legend" class="legend"></div><div class="hint">{escape('Ҳафталик ва ойлик харитада агент траекторияси кўрсатилмайди — фақат шу даврда қўшилган янги мижозлар жойлашуви.' if points_only else 'Маршрут GPS нуқталари асосида қурилади. Масофа ва тўхташлар тахминий. Савдо нуқталари агент киритган мижоз локацияларидан олинади.')}</div></aside><div class="mapwrap"><div id="map"></div><div id="map-status" role="status"></div></div></section></div>
<script id="data" type="application/json">{data}</script><script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script><script src="https://unpkg.com/maplibre-gl@5/dist/maplibre-gl.js"></script><script src="https://unpkg.com/@maplibre/maplibre-gl-leaflet/leaflet-maplibre-gl.js"></script>
<script>
const D=JSON.parse(document.getElementById('data').textContent), map=L.map('map',{{zoomControl:true}});
// OpenFreeMap vector basemap: the volunteer-run OSM raster tile server must not be used here.
const status=document.getElementById('map-status');
function mapWarning(){{status.style.display='block';status.textContent='Фон харитани юклаб бўлмади. GPS маршрути ва нуқталар мавжуд; харитадаги охирги нуқтани босиб навигаторда очишингиз мумкин.';}}
try{{
  if(typeof L.maplibreGL!=='function'){{mapWarning();}}
  else{{
    const basemap=L.maplibreGL({{style:'https://tiles.openfreemap.org/styles/liberty',attribution:'© OpenFreeMap · © OpenStreetMap contributors'}});
    basemap.addTo(map);
    if(typeof basemap.getMaplibreMap==='function'){{
      const vectorMap=basemap.getMaplibreMap();
      if(vectorMap)vectorMap.on('error',e=>{{if(e&&e.error){{console.warn('Basemap error',e.error.message||e.error);mapWarning();}}}});
    }}
  }}
}}catch(e){{console.warn('Map background unavailable',e);mapWarning();}}
const bounds=[]; const colors=['#2563eb','#f59e0b','#16a34a','#7c3aed','#e11d48','#0891b2','#9333ea','#475569'];
function esc(s){{return String(s??'').replace(/[&<>"']/g,m=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[m]));}}
const legend=document.getElementById('legend');
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
   .addTo(map).bindPopup('<b>'+esc(s.shop||s.name)+'</b><br>'+esc(s.name)+'<br>'+esc(s.address)+'<br>'+(D.points_only?'🆕 Янги мижоз':(s.active?'✅ Фаол савдо нуқтаси':'Қайд этилган савдо нуқтаси'))+'<br><a target="_blank" rel="noreferrer" href="https://www.google.com/maps/dir/?api=1&destination='+p[0]+','+p[1]+'">Навигаторда очиш</a>');
}});
document.getElementById('summary').textContent=D.summary||'Маълумот йўқ';
if(bounds.length)map.fitBounds(bounds,{{padding:[35,35],maxZoom:16}});else map.setView([41.3,69.24],7);setTimeout(()=>map.invalidateSize(),250);
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

def route_map_html(db,actor,agent):
    admin_only(db,actor)
    shift=db.execute('SELECT * FROM shifts WHERE agent=? ORDER BY id DESC LIMIT 1',(agent,)).fetchone()
    if not shift:raise ValueError('Бу агент ҳали иш бошламаган.')
    route,shops,stats,active=shift_route_data(db,agent,shift)
    summary=f"{stats['km']} км · {active} фаол савдо нуқтаси · {len(stats['stops'])} тўхташ · {len(stats['gaps'])} узилиш"
    return _map_html(f'Агент {agent} · смена #{shift["id"]}',[route],shops,summary),stats,active

def overall(db,actor,now=None,period='day'):
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
    routes=[];all_shops=[];total_km=0;stops=gaps=0;gps_points=0
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
    summary=f"{worked} иш · {round(total_km,2)} км · {total_new} янги мижоз · {m(total_sales)} USD сотув"
    html=_map_html(f'{label} · {map_label}',routes if period=='day' else [],all_shops,summary,
                   points_only=(period!='day'),summary_metrics={'agents':len(details),'km':round(total_km,2),'sales':total_sales})
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

def m(x):return f'{x/100:,.2f}'.replace(',',' ')

def reconciliation_html(r):
    c=r['client'];esc=lambda x:escape(str(x),quote=True)
    stock=''.join(f'<tr><td>{escape(product_name(p))}</td><td>{r["opening_stock"][p]}</td><td>{r["closing_stock"][p]}</td></tr>' for p in (1,3,5))
    rows=''.join('<tr>'+''.join(f'<td>{esc(v)}</td>' for v in [x['id'],x['time'],x['kind'],product_name(x['pack']) if x['pack'] else '—',x['qty'] or '—',m(x['usd_charge']),m(x['usd_credit']),m(x['usd_balance'])])+'</tr>' for x in r['rows'])
    return f'''<!doctype html><html lang="uz"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Ички ҳисоб — акт сверка</title><style>
body{{font:14px Arial,sans-serif;color:#15243b;background:#eef3f8;margin:0;padding:24px}}main{{max-width:1000px;margin:auto;background:white;padding:36px}}h1{{color:#174e87;margin:8px 0}}.muted{{color:#52647a}}.cards{{display:flex;flex-wrap:wrap;gap:16px;margin:24px 0}}.card{{padding:16px;background:#edf4fb;flex:1;min-width:160px}}strong{{display:block;font-size:20px;margin-top:8px}}table{{border-collapse:collapse;width:100%;font-size:12px;margin:18px 0}}th{{background:#174e87;color:white}}td,th{{padding:9px;border:1px solid #d3dce8;text-align:left}}.scroll{{overflow:auto}}footer{{margin-top:32px}}@media print{{body{{background:white;padding:0}}main{{padding:0}}thead{{display:table-header-group}}tr{{break-inside:avoid}}button{{display:none}}}}@page{{size:A4 landscape;margin:14mm}}
</style><main><p class="muted">ИЧКИ САВДО НАЗОРАТИ · ТЕСТ ҲИСОБОТИ</p><h1>Ўзаро ҳисоб-китобларни солиштириш далолатномаси</h1><p>{esc(r['start'])} — {esc(r['end'])} · Тошкент вақти</p><h2>{esc(c['name'])}</h2><p>{esc(c['phone'])} · {esc(c['address'])}</p><div class="cards"><div class="card">Бошланғич қарз<strong>{m(r['usd_opening'])} USD</strong></div><div class="card">Топширилган товар<strong>{m(r['usd_sales'])} USD</strong></div><div class="card">Қайтарилган товар<strong>{m(r['usd_returns'])} USD</strong></div><div class="card">Олинган тўлов<strong>{m(r['usd_payments'])} USD</strong></div><div class="card">Якуний қарз<strong>{m(r['usd_closing'])} USD</strong></div></div><p>Товар топширилганда USD қарз ёзилади, қайтариш ва тўлов қарзни камайтиради. Сотилди деган қайд қарзни қайта оширмайди. Манфий баланс — аванс.</p><p>Эски UZS операциялари алоҳида: бошланғич {m(r['opening'])} сўм, сотув {m(r['sales'])} сўм, тўлов {m(r['payments'])} сўм, қолдиқ {m(r['closing'])} сўм. Бу суммалар USD билан қўшилмайди.</p><h2>Операциялар</h2><div class="scroll"><table><thead><tr><th>№</th><th>Сана</th><th>Амал</th><th>Қадоқ</th><th>Дона</th><th>Топширилган, USD</th><th>Тўлов/қайтариш, USD</th><th>Қарз, USD</th></tr></thead><tbody>{rows or '<tr><td colspan="8">Бу даврда операция йўқ</td></tr>'}</tbody></table></div><h2>Мижоздаги сотилмаган товар</h2><table><thead><tr><th>Маҳсулот</th><th>Давр бошида, дона</th><th>Давр охирида, дона</th></tr></thead><tbody>{stock}</tbody></table><footer><p>Ҳисобот ботга тасдиқлаб киритилган маълумотлар асосида тузилди. Иккинчи томон ҳали тасдиқламаган.</p><p>Масъул ходим: ____________________ &nbsp;&nbsp; Мижоз: ____________________</p></footer></main></html>'''.encode()
