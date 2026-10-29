"""Korxona bo'limlari: rahbar tayyor bo'limlarni yoqadi/o'chiradi.

Bo'lim o'chirilsa:
- web panel menyusi va amallari yashiriladi (frontend `modules` ro'yxatiga qaraydi);
- server ham yopadi: /api/manager amallari (ACTION_MODULE), Mini App API'lari
  (ENDPOINT_MODULE) va Telegram bot xodim rollari (ROLE_MODULE);
- ma'lumot va tarix o'chirilmaydi — qayta yoqilganda hammasi joyida.

Yoqilmaganlik standart holat emas: yozuv bo'lmasa bo'lim YOQIQ (eski korxonalar o'zgarishsiz ishlaydi).
Sozlamalar, Asosiy sahifa, Mijozlar va tizim foydalanuvchilari doim ochiq — tizimga qayta
kirish va sozlamani boshqarish tasodifan yopilib qolmasin.
"""
import time

MODULES={
    'sales':('Savdo','Savdo Mini App, web savdo, narxlar va savdo jamoasi'),
    'cash':('Kassa','Kassir ilovasi, kassa harakatlari, agent topshiriqlari'),
    'warehouse':('Ombor','Ombor ilovasi, buyurtmalar, katalog, ta’minot va xom ashyo'),
    'agents':('Agentlar va tashriflar','Agent ilovasi, GPS, smena, tashriflar'),
    'hr':('Xodimlar va oylik','Sex ishchilari, davomat, oylik va avans'),
    'reports':('Hisobot va tahlil','Davr hisobotlari, tahlil va yordamchi'),
}
# Bir bo'lim ichidagi amal boshqa bo'limga tayanadi: o'sha bo'lim o'chiq bo'lsa amal yopiladi,
# lekin bo'lim yashirincha yoqib yuborilmaydi.
NEEDS={('hr','pay_add'):'cash',('supply','pay'):'cash'}   # (/api/manager action, op) -> kerakli bo'lim

ACTION_MODULE={
    'sales':'sales','shop':'sales',
    'cash_period':'cash','cashbook':'cash','cashier_add':'cash','cashier_rename':'cash','cashier_transfer':'cash',
    'cashier_deactivate':'cash','cashier_activate':'cash',
    'warehouse':'warehouse','stock':'warehouse','supply':'warehouse','order_status':'warehouse',
    'product_add':'warehouse','product_update':'warehouse','product_photo':'warehouse','custom_map':'warehouse',
    'agent_management':'agents','agent_detail':'agents','agent_period_detail':'agents','agent_feature_set':'agents',
    'agent_add_preview':'agents','agent_add_commit':'agents','agent_rename_preview':'agents','agent_rename_commit':'agents',
    'agent_transfer_preview':'agents','agent_transfer_commit':'agents','agent_deactivate_preview':'agents',
    'agent_deactivate_commit':'agents','route':'agents',
    'hr':'hr',
    'period_report':'reports','insights':'reports','ai_ask':'reports',
}
ENDPOINT_MODULE={'/api/shop':'sales','/api/cashier':'cash','/api/warehouse':'warehouse','/api/agent':'agents'}
ROLE_MODULE={'sales':'sales','cashier':'cash','warehouse':'warehouse','agent':'agents'}
_KEY='module_enabled:'


def enabled(db,key):
    if key not in MODULES:return True
    row=db.execute('SELECT value FROM meta WHERE key=?',(_KEY+key,)).fetchone()
    return row is None or str(row[0])!='0'


def state(db):
    return {k:enabled(db,k) for k in MODULES}


def closed_message(key):
    return f"«{MODULES[key][0]}» bo‘limi korxonada o‘chirilgan. Sozlamalar → Korxona bo‘limlarida rahbar yoqishi mumkin."


def require(db,key):
    if key and not enabled(db,key):raise ModuleClosed(closed_message(key))


class ModuleClosed(ValueError):
    """Bo'lim o'chiq: foydalanuvchiga tushunarli matn, HTTP 403."""


def require_action(db,action,op=None):
    key=ACTION_MODULE.get(str(action or ''))
    require(db,key)
    need=NEEDS.get((str(action or ''),str(op or '')))
    if need and not enabled(db,need):
        raise ModuleClosed(f"Bu amal uchun «{MODULES[need][0]}» bo‘limi kerak — u o‘chirilgan. Avval uni Sozlamalarda yoqing.")


def set_enabled(db,actor,key,on,now=None):
    if key not in MODULES:raise ValueError('Bo‘lim noto‘g‘ri.')
    on=bool(on)
    if enabled(db,key)==on:return state(db)
    db.execute('INSERT INTO meta(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(_KEY+key,'1' if on else '0'))
    db.execute('INSERT INTO role_audit(actor,old_id,new_id,action,ts) VALUES(?,?,?,?,?)',
               (actor,None,None,f"module_{'on' if on else 'off'}:{key}",int(time.time() if now is None else now)))
    return state(db)


def history(db,limit=30):
    rows=db.execute("""SELECT ra.action,ra.ts,COALESCE(u.name,CAST(ra.actor AS TEXT)) AS who FROM role_audit ra
        LEFT JOIN users u ON u.id=ra.actor WHERE ra.action LIKE ? ORDER BY ra.ts DESC,ra.id DESC LIMIT ?""",('module_%',limit)).fetchall()
    out=[]
    for r in rows:
        act,_,key=str(r['action']).partition(':')
        out.append({'module':key,'label':MODULES.get(key,(key,))[0],'on':act=='module_on','who':r['who'],'ts':int(r['ts'])})
    return out


def view(db):
    st=state(db)
    # 'modules' kaliti har javobda {kalit: yoqiq} holat lug'ati uchun band (bot.py), shuning uchun ro'yxat 'items'.
    return {'items':[{'key':k,'label':v[0],'description':v[1],'enabled':st[k]} for k,v in MODULES.items()],
            'modules':st,'history':history(db)}
