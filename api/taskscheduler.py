# api/taskscheduler.py
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple, List

from flask import Blueprint, jsonify, request
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.executors.pool import ThreadPoolExecutor

from api.coreapiserver import get_client_for_table

bp = Blueprint("taskscheduler", __name__)

# ──────────────────────────────────────────────────────────────
# APScheduler — лише «тикалка»; бізнес-логіка живе у БД/хендлерах
# ──────────────────────────────────────────────────────────────
executors = {"default": ThreadPoolExecutor(2)}
scheduler = BackgroundScheduler(executors=executors, timezone="UTC")

def start_scheduler_once():
    """Запускає APScheduler тільки якщо він ще не працює."""
    if not scheduler.running:
        scheduler.start()
        print("✅ APScheduler started")

DUE_CHECK_SECONDS = 60  # як часто опитувати чергу

# ──────────────────────────────────────────────────────────────
# Утиліти
# ──────────────────────────────────────────────────────────────
INTERVAL_RE = re.compile(
    r"^\s*(\d+)\s*(second|seconds|minute|minutes|hour|hours|day|days)\s*$",
    re.I,
)

def _now_utc() -> datetime:
    return datetime.now(timezone.utc)

def _parse_repeat_rule(rule: Optional[str]) -> Tuple[Optional[timedelta], List[str]]:
    """
    Повертає (інтервал, [тригери]).
    Приклади: "10 minutes", "on_server_start", "1 day,on_order_created".
    """
    if not rule:
        return None, []
    parts = [p.strip() for p in rule.split(",") if p.strip()]
    interval: Optional[timedelta] = None
    triggers: List[str] = []
    for p in parts:
        m = INTERVAL_RE.match(p)
        if m:
            n = int(m.group(1))
            unit = m.group(2).lower()
            if unit.startswith("second"):
                interval = timedelta(seconds=n)
            elif unit.startswith("minute"):
                interval = timedelta(minutes=n)
            elif unit.startswith("hour"):
                interval = timedelta(hours=n)
            elif unit.startswith("day"):
                interval = timedelta(days=n)
        else:
            triggers.append(p)
    return interval, triggers

def _as_bool_text(val) -> bool:
    return str(val).strip().lower() in ("true", "1", "yes")

# ──────────────────────────────────────────────────────────────
# Handlers (виконавці задач)
# ──────────────────────────────────────────────────────────────
def _cleanup_reserve_handler(params: dict) -> None:
    """
    Очистка резерву(ів) і повернення кількості на склад.
    params: {"reserve_id": "..." } або {"reserve_ids": ["...","..."]}
    """
    sb_reserve = get_client_for_table("reserve")
    sb_sklad = get_client_for_table("sklad")

    ids = []
    if "reserve_id" in params:
        ids = [str(params["reserve_id"])]
    elif "reserve_ids" in params and isinstance(params["reserve_ids"], list):
        ids = [str(x) for x in params["reserve_ids"]]

    if not ids:
        print("⚠️ cleanup_reserve: нема reserve_id/reserve_ids у params")
        return

    for rid in ids:
        res = sb_reserve.table("reserve").select("*").eq("id_reserve", rid).execute()
        row = (res.data or [None])[0]
        if not row:  # уже оброблено
            print(f"ℹ️ cleanup_reserve: резерв {rid} відсутній")
            continue

        id_prod = str(row.get("id_prod") or "")
        qty = int(row.get("quantity") or 0)

        # Видаляємо резерв
        sb_reserve.table("reserve").delete().eq("id_reserve", rid).execute()

        # Повертаємо на склад
        srow = sb_sklad.table("sklad").select("*").eq("id_prod", id_prod).execute().data
        if not srow:
            print(f"⚠️ cleanup_reserve: товар {id_prod} не знайдено у sklad")
            continue
        current = srow[0]
        free = int(current.get("free") or 0)
        reserv = int(current.get("reserv") or 0)

        sb_sklad.table("sklad").update({
            "free": str(free + qty),
            "reserv": str(max(reserv - qty, 0))
        }).eq("id_prod", id_prod).execute()

        print(f"✅ cleanup_reserve: {rid} очищено, +{qty} до free для товару {id_prod}")

def _update_currency_handler(params: dict) -> None:
    """
    task_type: update_currency
    params: {"update_prices": true|false} (за замовчуванням true)
    """
    update_prices = _as_bool_text(params.get("update_prices", "true"))
    try:
        from api.currency_update import update_currency_now
        update_currency_now(update_prices=update_prices)
        print("✅ Курс валют оновлено через taskscheduler")
    except Exception as e:
        print(f"❌ Помилка оновлення курсу валют: {e}")

# Реєстр типів задач → функції
TASK_HANDLERS = {
    "cleanup_reserve": _cleanup_reserve_handler,
    "update_currency": _update_currency_handler,
    # "send_invoice_pdf": _send_invoice_pdf_handler,
}

# ──────────────────────────────────────────────────────────────
# Основний цикл обробки due-задач
# ──────────────────────────────────────────────────────────────
def _process_due_tasks():
    """
    Раз на DUE_CHECK_SECONDS: беремо pending з run_at <= now().
    Атомарно «захоплюємо» (status=pending → running), виконуємо, далі:
    - repeat=false → DELETE
    - repeat=true з інтервалом → зсуваємо run_at на +інтервал
    - repeat=true без інтервалу (лише тригер) → лишаємо pending

    ДЕ-ДУПЛІКАЦІЯ:
    якщо існує кілька однакових задач (task_type+params+repeat+repeat_rule) з різним run_at,
    виконуємо лише останню (максимальний run_at), а старі дублікати прибираємо після успіху.
    """
    sb = get_client_for_table("scheduled_tasks")
    now_iso = _now_utc().isoformat()

    # 1) Беремо всі прострочені pending
    sel = sb.table("scheduled_tasks").select("*") \
        .lte("run_at", now_iso).eq("status", "pending").execute()
    tasks = sel.data or []
    if not tasks:
        return

    # 2) DE-DUPE: групуємо однакові задачі (task_type+params+repeat+repeat_rule)
    groups = {}       # key -> найсвіжіша задача (з найбільшим run_at)
    ignored_map = {}  # key -> [task_id, ...] старі дублікати
    for t in tasks:
        key = (
            str(t.get("task_type") or "").strip(),
            str(t.get("params") or "{}").strip(),
            "true" if _as_bool_text(t.get("repeat")) else "false",
            str(t.get("repeat_rule") or "").strip(),
        )
        run_at_str = t.get("run_at") or ""
        try:
            run_dt = datetime.fromisoformat(run_at_str.replace("Z", "+00:00"))
        except Exception:
            run_dt = _now_utc()

        prev = groups.get(key)
        if (not prev) or (run_dt >= prev["_run_dt"]):
            # новіша задача стає «основною»
            if prev:
                ignored_map.setdefault(key, []).append(prev["id"])
            t["_run_dt"] = run_dt
            groups[key] = t
        else:
            # поточна старіша → у «ігнор»
            ignored_map.setdefault(key, []).append(t["id"])

    unique_tasks = list(groups.values())

    # 3) Виконуємо лише унікальні «найсвіжіші» задачі
    for t in unique_tasks:
        task_id = t["id"]
        task_type = str(t.get("task_type") or "")
        params_raw = t.get("params") or "{}"
        repeat = _as_bool_text(t.get("repeat"))
        repeat_rule = str(t.get("repeat_rule") or "")
        run_at_str = t.get("run_at")
        key = (
            str(t.get("task_type") or "").strip(),
            str(t.get("params") or "{}").strip(),
            "true" if repeat else "false",
            str(t.get("repeat_rule") or "").strip(),
        )

        # Розбір params
        try:
            params = json.loads(params_raw) if isinstance(params_raw, str) else (params_raw or {})
        except Exception:
            params = {}

        handler = TASK_HANDLERS.get(task_type)
        if not handler:
            print(f"⚠️ Нема handler для task_type={task_type} → failed")
            sb.table("scheduled_tasks").update({"status": "failed"}).eq("id", task_id).execute()
            continue

        # 3.1) Атомарне «захоплення» задачі (захист від дублю запуску)
        claim = sb.table("scheduled_tasks").update({"status": "running"}) \
            .eq("id", task_id).eq("status", "pending").execute()
        if not (claim.data and len(claim.data) == 1):
            # хтось інший уже взяв або статус змінився — пропускаємо
            continue

        try:
            # 3.2) Викликаємо хендлер
            handler(params)

            # 3.3) Повторюваність/планування далі
            interval, _ = _parse_repeat_rule(repeat_rule)
            old_ids = ignored_map.get(key, [])

            if repeat and interval:
                # наступний запуск = base(run_at) + interval (зберігає "ритм")
                base_dt = _now_utc()
                try:
                    base_dt = datetime.fromisoformat(run_at_str.replace("Z", "+00:00"))
                except Exception:
                    pass
                next_dt = base_dt + interval

                sb.table("scheduled_tasks").update({
                    "run_at": next_dt.isoformat(),
                    "status": "pending",
                }).eq("id", task_id).execute()

                # дублікати цієї групи більше не потрібні
                if old_ids:
                    sb.table("scheduled_tasks").delete().in_("id", old_ids).execute()

            elif repeat and not interval:
                # повторюване лише по тригеру — лишаємо pending; дублікати видаляємо
                sb.table("scheduled_tasks").update({"status": "pending"}).eq("id", task_id).execute()
                if old_ids:
                    sb.table("scheduled_tasks").delete().in_("id", old_ids).execute()

            else:
                # разове — видаляємо основну
                sb.table("scheduled_tasks").delete().eq("id", task_id).execute()
                # і відповідні дублікати
                if old_ids:
                    sb.table("scheduled_tasks").delete().in_("id", old_ids).execute()

        except Exception as e:
            print(f"❌ Помилка виконання task_id={task_id}: {e}")
            sb.table("scheduled_tasks").update({"status": "failed"}).eq("id", task_id).execute()
            # У РАЗІ ПОМИЛКИ: дублікати не чіпаємо — хай лишаються pending як «страховка»

# Запускаємо «тикалку»
scheduler.add_job(
    _process_due_tasks,
    "interval",
    seconds=DUE_CHECK_SECONDS,
    id="scheduled_tasks_poll",
    replace_existing=True,
)

# ──────────────────────────────────────────────────────────────
# Публічні ендпоінти
# ──────────────────────────────────────────────────────────────
@bp.route("/api/tasks", methods=["POST"])
def create_task():
    """
    Створити завдання.
    JSON:
      task_type: str        (обов'язково)
      params: dict|str      (JSON)
      run_at: ISO-UTC       (None → now)
      repeat: true|false
      repeat_rule: "1 day,on_server_start" / "10 minutes" / "on_new_order" / ""
    """
    data = request.get_json(silent=True) or {}
    task_type = str(data.get("task_type") or "").strip()
    if not task_type:
        return jsonify(error="task_type required"), 400

    params = data.get("params") or {}
    params_text = json.dumps(params, ensure_ascii=False) if isinstance(params, dict) else str(params)

    run_at = data.get("run_at") or _now_utc().isoformat()
    repeat = "true" if _as_bool_text(data.get("repeat")) else "false"
    repeat_rule = data.get("repeat_rule") or ""

    sb = get_client_for_table("scheduled_tasks")
    ins = sb.table("scheduled_tasks").insert({
        "task_type": task_type,
        "params": params_text,
        "run_at": run_at,
        "status": "pending",
        "repeat": repeat,
        "repeat_rule": repeat_rule,
    }).execute()

    return jsonify(success=True, task=(ins.data[0] if ins.data else None)), 200

@bp.route("/api/tasks/trigger/<trigger_name>", methods=["POST"])
def trigger_tasks(trigger_name: str):
    """
    Виконує НАРАЗ усі pending-задачі, чий repeat_rule містить <trigger_name>.
    Комбіновані (з інтервалом) лишаються за графіком; тригерні — чекають наступного тригера.
    """
    trigger_name = (trigger_name or "").strip()
    if not trigger_name:
        return jsonify(error="empty trigger"), 400

    sb = get_client_for_table("scheduled_tasks")
    sel = sb.table("scheduled_tasks").select("*").eq("status", "pending").eq("repeat", "true").execute()
    tasks = [t for t in (sel.data or []) if trigger_name in str(t.get("repeat_rule") or "")]

    executed = 0
    for t in tasks:
        task_id = t["id"]
        task_type = str(t.get("task_type") or "")
        params_raw = t.get("params") or "{}"
        repeat_rule = str(t.get("repeat_rule") or "")

        handler = TASK_HANDLERS.get(task_type)
        if not handler:
            continue

        try:
            params = json.loads(params_raw) if isinstance(params_raw, str) else (params_raw or {})
        except Exception:
            params = {}

        try:
            handler(params)
            executed += 1
            # статус не змінюємо (лишиться pending); run_at теж не чіпаємо
            sb.table("scheduled_tasks").update({"status": "pending"}).eq("id", task_id).execute()
        except Exception as e:
            print(f"❌ trigger {trigger_name} → task_id={task_id} failed: {e}")
            sb.table("scheduled_tasks").update({"status": "failed"}).eq("id", task_id).execute()

    return jsonify(success=True, executed=executed), 200
