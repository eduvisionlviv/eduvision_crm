# services/test_mail_tool.py
from __future__ import annotations

import re
import datetime as dt
from typing import List

from flask import Blueprint, request, jsonify, render_template_string, abort

from api.coreapiserver import get_client_for_table
from services.gmail import send_email

bp = Blueprint("test_mail_tool", __name__, url_prefix="/api/testmail")

COOKIE_NAME = "edu_session"
EMAIL_RX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
ALLOWED_USER_IDS = {1, 2}  # ✅ кнопка/доступ лише для user_id 1 і 2


def _now_iso():
    return dt.datetime.utcnow().replace(microsecond=0).isoformat() + "+00:00"


def _resolve_user_by_cookie():
    """Повертає рядок користувача з contacts за валідною кукою, або None."""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    contacts = get_client_for_table("contacts")
    try:
        row = (
            contacts.table("contacts")
            .select("user_id,user_name,user_email,user_phone")
            .eq("auth_tokens", token)
            .gt("expires_at", _now_iso())
            .single()
            .execute()
            .data
        )
    except Exception:
        row = None
    return row


def _normalize_emails(raw) -> List[str]:
    if not raw:
        return []
    text = raw if isinstance(raw, str) else ",".join(map(str, raw))
    parts = re.split(r"[,\s;]+", text)
    seen, out = set(), []
    for p in parts:
        e = (p or "").strip()
        if not e or not EMAIL_RX.match(e) or e.lower() in seen:
            continue
        seen.add(e.lower())
        out.append(e)
    return out[:30]  # запобіжний ліміт


# ───────────────── UI сторінка з формою
_FORM_HTML = """<!doctype html>
<html lang="uk">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>Тестова розсилка</title>
<style>
 body{font-family:system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif;margin:24px;}
 .wrap{max-width:760px;margin:auto}
 .card{border:1px solid #e5e7eb;border-radius:12px;padding:16px 18px}
 label{display:block;margin:12px 0 6px;color:#374151}
 input,textarea{width:100%;box-sizing:border-box;font:inherit;border:1px solid #d1d5db;border-radius:8px;padding:10px}
 textarea{min-height:140px}
 .row{margin-top:10px}
 .btn{background:#2563eb;color:#fff;border:0;border-radius:10px;padding:10px 16px;cursor:pointer}
 .muted{color:#6b7280}
 .msg{margin-top:12px;padding:10px;border-radius:8px}
 .ok{background:#ecfdf5;border:1px solid #10b981}
 .err{background:#fef2f2;border:1px solid #ef4444;white-space:pre-wrap}
</style>
</head>
<body>
  <div class="wrap">
    <h2>Тимчасова розсилка</h2>
    <p class="muted">Доступно лише для користувачів з ID у списку: {{ allowed }}. Адреси розділяйте комою/пробілом/крапкою з комою.</p>
    <div class="card">
      <form id="f">
        <label>Кому (через кому):</label>
        <textarea name="emails" placeholder="a@ex.com, b@ex.com"></textarea>

        <label>Тема листа:</label>
        <input name="subject" value="Тестова розсилка" />

        <label>Текст:</label>
        <textarea name="text" placeholder="Введіть текст листа…">Тест багатоадресної розсилки (plain)</textarea>

        <div class="row">
          <button class="btn" type="submit">Надіслати</button>
          <span id="msg" class="msg" style="display:none"></span>
        </div>
      </form>
    </div>
  </div>
<script>
document.getElementById('f').addEventListener('submit', async (e) => {
  e.preventDefault();
  const fd = new FormData(e.target);
  const emails = (fd.get('emails') || '').toString();
  const subject = (fd.get('subject') || '').toString();
  const text = (fd.get('text') || '').toString();
  const msg = document.getElementById('msg'); msg.style.display='block'; msg.className='msg';
  msg.textContent='Надсилаю…';

  try{
    const r = await fetch('/api/testmail/send', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      credentials:'include',
      body:JSON.stringify({ emails, subject, text })
    });
    const data = await r.json().catch(()=>({}));
    if(r.ok && data.ok){
      msg.classList.add('ok'); msg.textContent = '✅ Надіслано: ' + (data.sent || 0) + '\\n' + (data.recipients || []).join(', ');
    }else{
      msg.classList.add('err'); msg.textContent = '❌ ' + (data.message || data.error || ('HTTP '+r.status));
    }
  }catch(err){
    msg.classList.add('err'); msg.textContent = '❌ ' + err;
  }
});
</script>
</body>
</html>
"""

@bp.get("/ui")
def ui_page():
    me = _resolve_user_by_cookie()
    if not me or int(me.get("user_id") or 0) not in ALLOWED_USER_IDS:
        abort(403)
    return render_template_string(_FORM_HTML, allowed=sorted(ALLOWED_USER_IDS))


# ───────────────── API: відправити
@bp.post("/send")
def send_test_mail():
    me = _resolve_user_by_cookie()
    if not me:
        return jsonify(error="unauthorized"), 401
    if int(me.get("user_id") or 0) not in ALLOWED_USER_IDS:
        return jsonify(error="forbidden", message="Недостатньо прав"), 403

    body = request.get_json(silent=True) or {}
    recipients = _normalize_emails(body.get("emails"))
    subject = (body.get("subject") or "Без теми").strip()[:200]
    text = (body.get("text") or "").strip()

    if not recipients:
        return jsonify(error="validation_error", message="Дайте 1+ коректних email"), 400
    if not text:
        return jsonify(error="validation_error", message="Текст листа порожній"), 400

    # Генеруємо простий HTML із plain-тексту
    html = "<div style='white-space:pre-wrap;font:inherit'>" + (
        text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    ) + "</div>"

    try:
        send_email(recipients, subject, html, text)  # використовує твій наявний services.gmail.send_email
    except Exception as exc:
        return jsonify(error="delivery_failed", message=str(exc)), 500

    return jsonify(ok=True, sent=len(recipients), recipients=recipients)
