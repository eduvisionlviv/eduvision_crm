"""
API для управління курсами
"""
import logging
from flask import Blueprint, request, jsonify
from api.coreapiserver import get_client_for_table, clear_cache

bp = Blueprint("courses", __name__, url_prefix="/api/courses")
log = logging.getLogger("courses")


@bp.route("", methods=["GET"])
def list_courses():
    """Список всіх курсів"""
    try:
        client = get_client_for_table("courses")
        query = client.table("courses").select("*")
        
        # Фільтрація за статусом
        is_active = request.args.get("is_active")
        if is_active is not None:
            query = query.eq("is_active", is_active.lower() in ("true", "1"))
        
        query = query.order("name")
        response = query.execute()
        
        return jsonify(courses=response.data), 200
    except Exception as e:
        log.error(f"Error listing courses: {e}")
        return jsonify(error="server_error", message="Не вдалося отримати список курсів"), 500


@bp.route("/<int:course_id>", methods=["GET"])
def get_course(course_id):
    """Отримати курс за ID"""
    try:
        client = get_client_for_table("courses")
        response = client.table("courses").select("*").eq("id", course_id).single().execute()
        
        if not response.data:
            return jsonify(error="not_found", message="Курс не знайдено"), 404
        
        return jsonify(course=response.data), 200
    except Exception as e:
        log.error(f"Error getting course {course_id}: {e}")
        return jsonify(error="server_error", message="Не вдалося отримати дані курсу"), 500


@bp.route("", methods=["POST"])
def create_course():
    """Створити новий курс"""
    try:
        data = request.get_json() or {}
        
        # Валідація
        name = (data.get("name") or "").strip()
        if not name:
            return jsonify(error="validation_error", message="Назва курсу обов'язкова"), 400
        
        course_data = {
            "name": name,
            "description": data.get("description"),
            "duration_months": data.get("duration_months"),
            "age_min": data.get("age_min"),
            "age_max": data.get("age_max"),
            "price": data.get("price"),
            "is_active": data.get("is_active", True),
        }
        
        client = get_client_for_table("courses")
        response = client.table("courses").insert(course_data).execute()
        clear_cache("courses")
        
        return jsonify(course=response.data[0]), 201
    except Exception as e:
        log.error(f"Error creating course: {e}")
        return jsonify(error="server_error", message="Не вдалося створити курс"), 500


@bp.route("/<int:course_id>", methods=["PUT", "PATCH"])
def update_course(course_id):
    """Оновити курс"""
    try:
        data = request.get_json() or {}
        
        update_data = {}
        if "name" in data:
            name = (data["name"] or "").strip()
            if not name:
                return jsonify(error="validation_error", message="Назва курсу не може бути порожньою"), 400
            update_data["name"] = name
        
        for field in ["description", "duration_months", "age_min", "age_max", "price", "is_active"]:
            if field in data:
                update_data[field] = data[field]
        
        if not update_data:
            return jsonify(error="validation_error", message="Немає даних для оновлення"), 400
        
        client = get_client_for_table("courses")
        response = client.table("courses").update(update_data).eq("id", course_id).execute()
        clear_cache("courses")
        
        if not response.data:
            return jsonify(error="not_found", message="Курс не знайдено"), 404
        
        return jsonify(course=response.data[0]), 200
    except Exception as e:
        log.error(f"Error updating course {course_id}: {e}")
        return jsonify(error="server_error", message="Не вдалося оновити курс"), 500


@bp.route("/<int:course_id>", methods=["DELETE"])
def delete_course(course_id):
    """Видалити курс (м'яке видалення - деактивація)"""
    try:
        client = get_client_for_table("courses")
        response = client.table("courses").update({"is_active": False}).eq("id", course_id).execute()
        clear_cache("courses")
        
        if not response.data:
            return jsonify(error="not_found", message="Курс не знайдено"), 404
        
        return jsonify(message="Курс деактивовано"), 200
    except Exception as e:
        log.error(f"Error deleting course {course_id}: {e}")
        return jsonify(error="server_error", message="Не вдалося видалити курс"), 500
