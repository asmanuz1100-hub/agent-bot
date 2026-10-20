"""Rahbar paneli uchun AI yordamchi: biznes ma'lumotlari bo'yicha savollarga javob.

Server joriy holatdan ixcham hisobot (bugun, 7 kun, 30 kun, agentlar, ombor, qarz) yig'adi va
uni savol bilan birga Claude'ga yuboradi. Model faqat shu ma'lumotga tayanadi — raqam to'qimaydi.
Kalit: ANTHROPIC_API_KEY (server muhitida). Kalit bo'lmasa — aniq xato qaytariladi.
"""
import json
import logging
import os
import time

import executive
import manager_api

MODEL = os.getenv('AI_MODEL', 'claude-opus-5-5')
MAX_QUESTION = 600
MAX_HISTORY = 8

SYSTEM = """Siz kompaniya boshqaruv panelidagi AI tahlilchisiz. Rahbarga o'zbek tilida (lotin yozuvi) javob berasiz.
Faqat <data> ichidagi ma'lumotga tayaning. Unda yo'q narsani taxmin qilmang — "bu ma'lumot panelda yo'q" deng.
Pul USD da, so'm alohida (ularni qo'shmang). Avval qisqa aniq javob (1–2 gap, asosiy raqam bilan), keyin kerak bo'lsa
3–5 ta qisqa band: sabab, kim yaxshi/yomon ishlayapti, nimaga e'tibor berish kerak. Markdown jadval ishlatmang.
Javob ovoz bilan o'qilishi mumkin — qisqa va ravon yozing."""


def _round(v):
    return round(v, 2) if isinstance(v, float) else v


def _clean(obj):
    if isinstance(obj, dict):
        return {k: _clean(v) for k, v in obj.items() if k not in ('primaryAdmin', 'photoUrl', 'thumbUrl', 'calendar', 'options', 'series', 'catalog')}
    if isinstance(obj, list):
        return [_clean(v) for v in obj]
    return _round(obj)


def snapshot(db, now=None):
    """Savolga javob berish uchun ixcham biznes holati (JSON-ga tayyor)."""
    out = {'generated': time.strftime('%Y-%m-%d %H:%M', time.localtime(now or time.time()))}
    for period in ('today', 'week', 'month'):
        r = manager_api.period_report(db, period, None, None)
        out['report_' + period] = _clean({k: r.get(k) for k in (
            'label', 'deliveredUsd', 'deliveredQty', 'paymentsUsd', 'returnsUsd', 'soldQty', 'visits', 'newClients',
            'acceptedCashUsd', 'cashierExpensesUsd', 'workSeconds', 'distanceKm', 'topProduct', 'previous', 'agents')} |
            {'products': [p for p in r.get('products') or [] if p.get('deliveredQty') or p.get('deliveredUsd')][:25]})
    ex = executive.executive(db, 'today', None, None)
    out['today_overview'] = _clean({k: ex.get(k) for k in ('kpis', 'collections', 'debtAging', 'agentsCash', 'regionSales', 'advanceUsd')})
    wh = manager_api.warehouse(db, 'open')
    stock = wh.get('stock') or {}
    out['warehouse'] = _clean({
        'orderCounts': wh.get('counts'),
        'openOrders': [{k: o.get(k) for k in ('id', 'status', 'agentName', 'clientName', 'totalCents', 'ts')} for o in (wh.get('orders') or [])[:30]],
        'stock': {k: stock.get(k) for k in ('stockTotal', 'issuedToday', 'issuedMonth', 'returnedMonth', 'writeoffMonth', 'receivedMonth')},
        'stockByProduct': (stock.get('products') or [])[:40],
        'demand': (wh.get('demand') or [])[:20],
    })
    return out


def _history(raw):
    msgs = []
    for m in (raw or [])[-MAX_HISTORY:]:
        if isinstance(m, dict) and m.get('role') in ('user', 'assistant') and isinstance(m.get('text'), str):
            msgs.append({'role': m['role'], 'content': m['text'][:2000]})
    while msgs and msgs[0]['role'] != 'user':
        msgs.pop(0)
    return msgs


def ask(db, question, history=None, client=None):
    question = ' '.join(str(question or '').split())
    if not question:
        raise ValueError('Savolni yozing yoki ayting.')
    if len(question) > MAX_QUESTION:
        raise ValueError(f'Savol {MAX_QUESTION} belgidan oshmasin.')
    if client is None:
        if not os.getenv('ANTHROPIC_API_KEY'):
            raise ValueError('AI yordamchi sozlanmagan: serverga ANTHROPIC_API_KEY qo‘shilishi kerak.')
        import anthropic
        client = anthropic.Anthropic(max_retries=2, timeout=50.0)
    data = json.dumps(snapshot(db), ensure_ascii=False, default=float)
    messages = _history(history) + [{'role': 'user', 'content': f'<data>\n{data}\n</data>\n\nSavol: {question}'}]
    import anthropic
    try:
        resp = client.beta.messages.create(
            model=MODEL, max_tokens=2000, system=SYSTEM, messages=messages,
            output_config={'effort': 'low'},
            betas=['server-side-fallback-2026-07-01'], fallbacks='default')
    except anthropic.RateLimitError:
        raise ValueError('AI hozir band. Bir daqiqadan keyin qayta urinib ko‘ring.')
    except anthropic.AuthenticationError:
        raise ValueError('AI kaliti noto‘g‘ri. Server sozlamasini tekshiring.')
    except (anthropic.APIConnectionError, anthropic.APIStatusError) as e:
        logging.warning('AI request failed: %r', e)
        raise ValueError('AI xizmatiga ulanib bo‘lmadi. Qayta urinib ko‘ring.')
    if resp.stop_reason == 'refusal':
        raise ValueError('AI bu savolga javob bermadi. Savolni boshqacha yozing.')
    text = '\n'.join(b.text for b in resp.content if b.type == 'text').strip()
    return {'answer': text or 'Javob bo‘sh qaytdi.'}
