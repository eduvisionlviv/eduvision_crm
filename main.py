import os
import logging
import importlib.util
import pathlib
from flask import Flask, send_from_directory, jsonify
from flask_cors import CORS
from werkzeug.exceptions import HTTPException

# Імпорти для завантаження API (необхідні для роботи CRM)
from api.load_module_apis import load_module_apis
from api.blueprint_utils import register_blueprints

# ─────────────── Логування
logging.basicConfig(level=logging.INFO,
                    format="%(levelname)s:%(name)s: %(message)s")
log = logging.getLogger("main")

# ─────────────── Flask App + CORS
app = Flask(__name__, static_folder="web", static_url_path="")

# Налаштування CORS
allowed = os.getenv("crm_url", "http://localhost:5000")
CORS(app, resources={r"/api/*": {"origins": [d.strip() for d in allowed.split(",")]}})


# ─────────────── Глобальний JSON-обробник помилок
@app.errorhandler(Exception)
def json_error_handler(err):
    status_code = 500
    message = "Внутрішня помилка сервера"

    if isinstance(err, HTTPException):
        status_code = err.code or status_code
        message = err.description or message

    log.exception("Unhandled error: %s", err)
    return jsonify(error="server_error", message=message), status_code

# ─────────────── Динамічне завантаження API-модулів
# Це необхідно залишити, щоб працювали запити з фронтенду до бази даних
def load_api(app: Flask, folder: str = "api"):
    base = pathlib.Path(folder).resolve()
    for py in base.rglob("*.py"):
        if py.name.startswith("_"):
            continue
        mod_name = ".".join(("api",) + py.with_suffix("").parts)
        try:
            spec = importlib.util.spec_from_file_location(mod_name, py)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)             # type: ignore
            blueprints = []
            bp = getattr(mod, "bp", None)
            if bp:
                blueprints.append(bp)
            extra_bps = getattr(mod, "bps", None)
            if extra_bps:
                if isinstance(extra_bps, (list, tuple, set)):
                    blueprints.extend(extra_bps)
                else:
                    blueprints.append(extra_bps)

            register_blueprints(app, blueprints, str(py.relative_to(base)), logger=log)
        except Exception as exc:
            log.error("⚠️  Skip %s : %s", py.relative_to(base), exc)

# Ініціалізація API ендпоінтів
load_module_apis(app)
load_api(app)

# Перевірка, що критичні API піднялися. Якщо ні — валимося одразу,
# щоб не отримувати малозрозумілий 405 Method Not Allowed замість POST /api/login/join
# (це стається, якщо api/login/join.py не завантажився через помилки чи залежності).
def _assert_route(rule: str, method: str) -> None:
    for r in app.url_map.iter_rules():
        if r.rule == rule and method.upper() in (r.methods or set()):
            return
    raise RuntimeError(
        f"Маршрут {rule} для {method} не зареєстровано. Перевірте логи завантаження API"
    )


_assert_route("/api/login/join", "POST")

# ─────────────── Routes (Маршрутизація сайту)
@app.route("/")
def root():
    return app.send_static_file("index.html")

@app.route("/img/<path:filename>")
def img_static(filename):
    return send_from_directory("img", filename)

@app.route("/module/<path:filepath>")
def module_static(filepath):
    return send_from_directory("module", filepath)

@app.route("/templates/<path:filename>")
def template_static(filename):
    return send_from_directory("templates", filename)

# Fallback для SPA (Single Page Application)
@app.route("/<path:path>")
def static_or_fallback(path: str):
    file_path = pathlib.Path(app.static_folder) / path
    if file_path.is_file():
        return send_from_directory(app.static_folder, path)
    return app.send_static_file("index.html")

@app.route("/ping")
def ping():
    return jsonify(status="ok")

# ─────────────── Запуск сервера
if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    log.info(f"🚀 Starting CRM Server on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
