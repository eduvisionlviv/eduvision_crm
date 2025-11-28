# api/universal_api.py
"""
Універсальний CRUD-ендпойнт із захистом (Whitelist).
Дозволяє доступ лише до таблиць, необхідних для роботи Frontend.
"""
from flask import Blueprint, request, jsonify
from api.coreapiserver import (
    get_client_for_table,
    get_from_cache,
    set_cache,
    clear_cache
)

bp = Blueprint("universal", __name__, url_prefix="/api")

# ────────────────────────────────────────────────────────────────
# 🛡️ БЕЗПЕКА: Список дозволених таблиць (Whitelist)
# ────────────────────────────────────────────────────────────────
ALLOWED_TABLES = {
    # Основні бізнес-дані
    "contacts", "order", "sklad", "rozrahunky", "rozrahunky_type",
    "price_reserve", "rekvisit", "invoice", "return",
    "courses", "menu",
    
    # Логістика та довідники
    "carriers", "delivery_address",
    
    # Службові таблиці для логіки (склад, блокування)
    "sklad_moves", "sklad_move_name",
    "uni_base",
    
    # Реєстрація та тимчасові дані
    "register", "black_list", "reserve",
    
    # Календар (якщо використовується)
    "calendar", "type_calendar"
}

# ────────────────────────────────────────────────────────────────
# 🔑 ОПТИМІЗАЦІЯ: Карта Primary Keys (щоб не гадати)
# ────────────────────────────────────────────────────────────────
PK_MAP = {
    "contacts": "user_id",
    "order": "id_order",
    "sklad": "id_prod",
    "reserve": "id_reserve",
    "menu": "id_menu",
    "courses": "id_course", # або name_short, залежно від структури, але id надійніше для delete
    "rozrahunky_type": "type_id",
    "rekvisit": "id", 
    "invoice": "id",
    # Для інших таблиць за замовчуванням буде 'id'
}

# ────────────────────────────────────────────────────────────────
# 1.  Підтримувані оператори Supabase
# ────────────────────────────────────────────────────────────────
SUPPORTED_OPERATORS = {
    "eq"   : "eq",
    "neq"  : "neq",
    "gt"   : "gt",
    "lt"   : "lt",
    "gte"  : "gte",
    "lte"  : "lte",
    "like" : "like",
    "ilike": "ilike",
    "in"   : "in_"
}

# ────────────────────────────────────────────────────────────────
# 2.  Фільтри
# ────────────────────────────────────────────────────────────────
def apply_filters(qry, params: dict):
    for col, raw in params.items():
        if "." not in raw:
            continue # Пропускаємо параметри без оператора (безпека)

        op, val = raw.split(".", 1)
        if op not in SUPPORTED_OPERATORS:
            continue # Пропускаємо невідомі оператори

        if op == "in":
            clean  = val.strip("()")
            values = [v.strip() for v in clean.split(",") if v.strip()]
            qry    = qry.in_(col, values)
        else:
            clean_val = val.strip('"') if val.startswith('"') and val.endswith('"') else val
            qry = getattr(qry, SUPPORTED_OPERATORS[op])(col, clean_val)

    return qry

# ────────────────────────────────────────────────────────────────
# 4.  /api/<table>   (GET, POST, PATCH, DELETE)
# ────────────────────────────────────────────────────────────────
@bp.route("/<table>", methods=["GET", "POST", "PATCH", "DELETE"])
def table_ops(table):
    # 🔒 ПЕРЕВІРКА ДОСТУПУ
    if table not in ALLOWED_TABLES:
        return jsonify({"error": f"Access denied to table '{table}'"}), 403

    db = get_client_for_table(table)

    try:
        # ---------- GET ----------
        if request.method == "GET":
            args = request.args
            # кешуємо тільки повне вибірку без фільтрів
            if not args:
                cached = get_from_cache(table)
                if cached is not None:
                    return jsonify(cached)

            qry = apply_filters(db.table(table).select("*"), args)
            res = qry.execute()
            if not args:
                set_cache(table, res.data)
            return jsonify(res.data)

        # ---------- POST ----------
        if request.method == "POST":
            payload = request.json or {}
            if not payload:
                return jsonify({"error": "❌ Порожній payload"}), 400
            res = db.table(table).insert(payload).execute()
            clear_cache(table)
            return jsonify(res.data), 201

        # ---------- PATCH / DELETE із довільними фільтрами ----------
        filters = request.args
        if not filters:
            return jsonify({"error": "❌ Потрібно вказати фільтри"}), 400

        if request.method == "PATCH":
            payload = request.json or {}
            if not payload:
                return jsonify({"error": "❌ PATCH без даних"}), 400
            res = apply_filters(db.table(table).update(payload), filters).execute()
        else:  # DELETE
            res = apply_filters(db.table(table).delete(), filters).execute()

        clear_cache(table)
        return jsonify(res.data)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ────────────────────────────────────────────────────────────────
# 5.  /api/<table>/<row_id>   (PATCH, DELETE)
# ────────────────────────────────────────────────────────────────
@bp.route("/<table>/<row_id>", methods=["PATCH", "DELETE"])
def row_ops(table, row_id):
    # 🔒 ПЕРЕВІРКА ДОСТУПУ
    if table not in ALLOWED_TABLES:
        return jsonify({"error": f"Access denied to table '{table}'"}), 403

    try:
        db = get_client_for_table(table)
        # Визначаємо Primary Key з мапи або беремо 'id'
        pk = PK_MAP.get(table, "id")

        if request.method == "PATCH":
            payload = request.json or {}
            if not payload:
                return jsonify({"error": "❌ PATCH без даних"}), 400
            res = db.table(table).update(payload).eq(pk, row_id).execute()
        else:  # DELETE
            res = db.table(table).delete().eq(pk, row_id).execute()

        clear_cache(table)
        return jsonify(res.data or {})

    except Exception as e:
        return jsonify({"error": str(e)}), 500
