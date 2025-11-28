# api/load_module_apis.py
import os
import importlib.util
from flask import jsonify

from api.blueprint_utils import register_blueprints

def load_module_apis(app):
    module_root = os.path.join(os.path.dirname(__file__), "..", "module")

    # ========== /api/modules без Blueprint ==========
    @app.route("/api/modules", methods=["GET"])
    def list_modules():
        modules = []
        for mod_name in os.listdir(module_root):
            mod_path = os.path.join(module_root, mod_name)
            install_path = os.path.join(mod_path, "install.txt")

            if os.path.isdir(mod_path) and os.path.isfile(install_path):
                try:
                    module_data = {}
                    with open(install_path, "r", encoding="utf-8") as f:
                        for line in f:
                            if "=" in line:
                                key, val = line.strip().split("=", 1)
                                module_data[key] = val
                    modules.append(module_data | {"id": mod_name})
                except Exception as e:
                    print(f"⚠️ Помилка у {mod_name}/install.txt: {e}")
        return jsonify(modules)

    # ========== Завантаження API модулів ==========
    for mod_name in os.listdir(module_root):
        mod_path = os.path.join(module_root, mod_name)
        install_path = os.path.join(mod_path, "install.txt")
        api_dir = os.path.join(mod_path, "api")

        if not os.path.isfile(install_path):
            print(f"⏭️  Пропущено {mod_name}: немає install.txt")
            continue

        if os.path.isdir(api_dir):
            for file in os.listdir(api_dir):
                if file.endswith(".py"):
                    file_path = os.path.join(api_dir, file)
                    try:
                        spec = importlib.util.spec_from_file_location(f"module.{mod_name}.{file}", file_path)
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)

                        blueprints = []
                        if hasattr(module, "bp"):
                            blueprints.append(module.bp)
                        extra_bps = getattr(module, "bps", None)
                        if extra_bps:
                            if isinstance(extra_bps, (list, tuple, set)):
                                blueprints.extend(extra_bps)
                            else:
                                blueprints.append(extra_bps)

                        if not blueprints:
                            print(f"⚠️  {mod_name}/{file} has no `bp` to register.")
                        else:
                            register_blueprints(app, blueprints, f"module/{mod_name}/{file}")
                    except Exception as e:
                        print(f"❌ Error loading {mod_name}/{file}: {e}")
