import os
import time
import threading
from typing import Any, Optional, Tuple
from flask import request
from supabase import create_client, Client
import logging
from threading import Lock

log = logging.getLogger("coreapiserver")

update_lock = Lock()

# ───────────────────────────────
# 🔐 ПІДКЛЮЧЕННЯ ДО SUPABASE (відкладене)
# ───────────────────────────────
_supabase_main = None
_supabase_stock = None

def get_supabase_clients():
    global _supabase_main, _supabase_stock

    if _supabase_main and _supabase_stock:
        return _supabase_main, _supabase_stock

    url1 = os.getenv("SUPABASE_URL1")
    key1 = os.getenv("HDD")
    url2 = os.getenv("SUPABASE_URL2")
    key2 = os.getenv("HDD2")

    if not url1 or not key1 or not url2 or not key2:
        raise ValueError("❌ Не вистачає даних для підключення до Supabase!")

    _supabase_main = create_client(url1, key1)
    _supabase_stock = create_client(url2, key2)
    return _supabase_main, _supabase_stock

# ───────────────────────────────
# 🗺️ МАПА ТАБЛИЦЬ ДО БАЗ
# ───────────────────────────────
TABLE_DB_MAP = {
    # Main DB
    "carriers": "main",
    "contacts": "main",
    "delivery_address": "main",
    "order": "main",
    "register": "main",
    "rekvisit": "main",
    "black_list": "main",
    "menu": "main",
    "price_reserve": "main",
    "sklad_moves": "main",
    "sklad_move_name": "main",

    # Stock DB
    "courses": "stock",
    "calendar": "stock",
    "type_calendar": "stock",
    "reserve": "stock",
    "sklad": "stock",
    "rozrahunky": "stock",
    "rozrahunky_type": "stock",
    "uni_base": "stock",
    "scheduled_tasks": "stock",
    "invoice": "stock",
    "return": "stock",
    "parents": "stock",
    "student": "stock",
}

def get_client_for_table(table_name: str) -> Client:
    main, stock = get_supabase_clients()
    db_target = TABLE_DB_MAP.get(table_name, "main")
    return stock if db_target == "stock" else main

# ───────────────────────────────
# 🔁 IN-MEMORY КЕШУВАННЯ
# ───────────────────────────────
CACHE_TTL = 1800  # 30 хвилин
cache: dict[Tuple[str, str], Tuple[float, Any]] = {}

def get_cache_key(table: str, column: Optional[str] = None) -> Tuple[str, str]:
    return (table, column if column else "all")

def get_from_cache(table: str, column: Optional[str] = None) -> Optional[Any]:
    key = get_cache_key(table, column)
    entry = cache.get(key)
    if entry:
        timestamp, data = entry
        if time.time() - timestamp < CACHE_TTL:
            return data
        cache.pop(key, None)
    return None

def set_cache(table: str, data: Any, column: Optional[str] = None):
    key = get_cache_key(table, column)
    cache[key] = (time.time(), data)

def clear_cache(table: str, column: Optional[str] = None):
    key = get_cache_key(table, column)
    cache.pop(key, None)

# ───────────────────────────────
# 🔒 ГЛОБАЛЬНИЙ LOCK
# ───────────────────────────────
update_lock = threading.Lock()

# 🔁 Обмежити блокування лише для обраних маршрутів
LOCKED_PATHS = [
    "/api/rozrahunky",
    "/api/go_reserve",
    "/api/go_fin_order",
    "/api/save-smart"
]

# ───────────────────────────────
# 🔌 Flask middleware для lock
# ───────────────────────────────
def with_global_lock(app):
    @app.before_request
    def acquire_lock():
        if not LOCKED_PATHS or request.path in LOCKED_PATHS:
            request._lock = update_lock
            request._lock.acquire()

    @app.after_request
    def release_lock(response):
        if hasattr(request, "_lock"):
            request._lock.release()
        return response
    
    log.info("✅ Global lock middleware activated (coreapiserver)")
