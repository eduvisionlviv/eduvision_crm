"""
API для управління групами та зарахуванням учнів
"""
import logging
from flask import Blueprint, request, jsonify
from api.coreapiserver import get_client_for_table, clear_cache

bp = Blueprint("groups", __name__, url_prefix="/api/groups")
log = logging.getLogger("groups")


@bp.route("", methods=["GET"])
def list_groups():
    """Список всіх груп"""
    try:
        client = get_client_for_table("groups")
        query = client.table("groups").select("*, courses(name)")
        
        # Фільтрація
        is_active = request.args.get("is_active")
        if is_active is not None:
            query = query.eq("is_active", is_active.lower() in ("true", "1"))
        
        course_id = request.args.get("course_id")
        if course_id:
            query = query.eq("course_id", int(course_id))
        
        teacher_id = request.args.get("teacher_id")
        if teacher_id:
            query = query.eq("teacher_id", int(teacher_id))
        
        query = query.order("name")
        response = query.execute()
        
        return jsonify(groups=response.data), 200
    except Exception as e:
        log.error(f"Error listing groups: {e}")
        return jsonify(error="server_error", message="Не вдалося отримати список груп"), 500


@bp.route("/<int:group_id>", methods=["GET"])
def get_group(group_id):
    """Отримати групу за ID з інформацією про учнів"""
    try:
        client = get_client_for_table("groups")
        group_response = client.table("groups").select("*, courses(name)").eq("id", group_id).single().execute()
        
        if not group_response.data:
            return jsonify(error="not_found", message="Групу не знайдено"), 404
        
        # Отримати учнів групи
        students_client = get_client_for_table("group_students")
        students_response = students_client.table("group_students").select(
            "*, student(user_id, user_name, user_email, user_phone)"
        ).eq("group_id", group_id).eq("status", "active").execute()
        
        group_data = group_response.data
        group_data["students"] = students_response.data or []
        group_data["current_students"] = len(students_response.data or [])
        
        return jsonify(group=group_data), 200
    except Exception as e:
        log.error(f"Error getting group {group_id}: {e}")
        return jsonify(error="server_error", message="Не вдалося отримати дані групи"), 500


@bp.route("", methods=["POST"])
def create_group():
    """Створити нову групу"""
    try:
        data = request.get_json() or {}
        
        # Валідація
        name = (data.get("name") or "").strip()
        if not name:
            return jsonify(error="validation_error", message="Назва групи обов'язкова"), 400
        
        course_id = data.get("course_id")
        if not course_id:
            return jsonify(error="validation_error", message="Курс обов'язковий"), 400
        
        group_data = {
            "name": name,
            "course_id": course_id,
            "teacher_id": data.get("teacher_id"),
            "max_students": data.get("max_students", 10),
            "schedule": data.get("schedule"),
            "room": data.get("room"),
            "is_active": data.get("is_active", True),
        }
        
        client = get_client_for_table("groups")
        response = client.table("groups").insert(group_data).execute()
        clear_cache("groups")
        
        return jsonify(group=response.data[0]), 201
    except Exception as e:
        log.error(f"Error creating group: {e}")
        return jsonify(error="server_error", message="Не вдалося створити групу"), 500


@bp.route("/<int:group_id>", methods=["PUT", "PATCH"])
def update_group(group_id):
    """Оновити групу"""
    try:
        data = request.get_json() or {}
        
        update_data = {}
        if "name" in data:
            name = (data["name"] or "").strip()
            if not name:
                return jsonify(error="validation_error", message="Назва групи не може бути порожньою"), 400
            update_data["name"] = name
        
        for field in ["course_id", "teacher_id", "max_students", "schedule", "room", "is_active"]:
            if field in data:
                update_data[field] = data[field]
        
        if not update_data:
            return jsonify(error="validation_error", message="Немає даних для оновлення"), 400
        
        client = get_client_for_table("groups")
        response = client.table("groups").update(update_data).eq("id", group_id).execute()
        clear_cache("groups")
        
        if not response.data:
            return jsonify(error="not_found", message="Групу не знайдено"), 404
        
        return jsonify(group=response.data[0]), 200
    except Exception as e:
        log.error(f"Error updating group {group_id}: {e}")
        return jsonify(error="server_error", message="Не вдалося оновити групу"), 500


@bp.route("/<int:group_id>", methods=["DELETE"])
def delete_group(group_id):
    """Видалити групу (м'яке видалення - деактивація)"""
    try:
        client = get_client_for_table("groups")
        response = client.table("groups").update({"is_active": False}).eq("id", group_id).execute()
        clear_cache("groups")
        
        if not response.data:
            return jsonify(error="not_found", message="Групу не знайдено"), 404
        
        return jsonify(message="Групу деактивовано"), 200
    except Exception as e:
        log.error(f"Error deleting group {group_id}: {e}")
        return jsonify(error="server_error", message="Не вдалося видалити групу"), 500


@bp.route("/<int:group_id>/students", methods=["POST"])
def enroll_student(group_id):
    """Зарахувати учня до групи"""
    try:
        data = request.get_json() or {}
        student_id = data.get("student_id")
        
        if not student_id:
            return jsonify(error="validation_error", message="ID учня обов'язковий"), 400
        
        # Перевірка чи не переповнена група
        client = get_client_for_table("groups")
        group = client.table("groups").select("max_students").eq("id", group_id).single().execute()
        
        if not group.data:
            return jsonify(error="not_found", message="Групу не знайдено"), 404
        
        students_client = get_client_for_table("group_students")
        current_students = students_client.table("group_students").select("id").eq("group_id", group_id).eq("status", "active").execute()
        
        if len(current_students.data or []) >= group.data["max_students"]:
            return jsonify(error="group_full", message="Група переповнена"), 400
        
        # Зарахування
        enrollment_data = {
            "group_id": group_id,
            "student_id": student_id,
            "status": "active"
        }
        
        response = students_client.table("group_students").insert(enrollment_data).execute()
        clear_cache("group_students")
        
        return jsonify(enrollment=response.data[0]), 201
    except Exception as e:
        if "duplicate key value violates unique constraint" in str(e):
            return jsonify(error="already_enrolled", message="Учень вже зарахований до цієї групи"), 409
        log.error(f"Error enrolling student to group {group_id}: {e}")
        return jsonify(error="server_error", message="Не вдалося зарахувати учня"), 500


@bp.route("/<int:group_id>/students/<int:student_id>", methods=["DELETE"])
def remove_student(group_id, student_id):
    """Відрахувати учня з групи"""
    try:
        client = get_client_for_table("group_students")
        response = client.table("group_students").update({"status": "inactive"}).eq("group_id", group_id).eq("student_id", student_id).execute()
        clear_cache("group_students")
        
        if not response.data:
            return jsonify(error="not_found", message="Запис про зарахування не знайдено"), 404
        
        return jsonify(message="Учня відраховано з групи"), 200
    except Exception as e:
        log.error(f"Error removing student {student_id} from group {group_id}: {e}")
        return jsonify(error="server_error", message="Не вдалося відрахувати учня"), 500
