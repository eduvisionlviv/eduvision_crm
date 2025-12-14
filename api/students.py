"""
API для управління учнями
"""
import logging
from flask import Blueprint, request, jsonify
from api.coreapiserver import get_client_for_table, clear_cache

bp = Blueprint("students", __name__, url_prefix="/api/students")
log = logging.getLogger("students")


@bp.route("", methods=["GET"])
def list_students():
    """Список всіх учнів"""
    try:
        client = get_client_for_table("student")
        query = client.table("student").select("user_id, user_name, user_email, user_phone")
        query = query.order("user_name")
        response = query.execute()
        
        return jsonify(students=response.data), 200
    except Exception as e:
        log.error(f"Error listing students: {e}")
        return jsonify(error="server_error", message="Не вдалося отримати список учнів"), 500


@bp.route("/<int:student_id>", methods=["GET"])
def get_student(student_id):
    """Отримати дані учня з групами"""
    try:
        client = get_client_for_table("student")
        student_response = client.table("student").select("*").eq("user_id", student_id).single().execute()
        
        if not student_response.data:
            return jsonify(error="not_found", message="Учня не знайдено"), 404
        
        # Отримати групи учня
        groups_client = get_client_for_table("group_students")
        groups_response = groups_client.table("group_students").select(
            "*, groups(id, name, room, schedule, courses(name))"
        ).eq("student_id", student_id).eq("status", "active").execute()
        
        student_data = student_response.data
        student_data["groups"] = groups_response.data or []
        
        return jsonify(student=student_data), 200
    except Exception as e:
        log.error(f"Error getting student {student_id}: {e}")
        return jsonify(error="server_error", message="Не вдалося отримати дані учня"), 500


@bp.route("/<int:student_id>/attendance", methods=["GET"])
def get_student_attendance(student_id):
    """Отримати відвідуваність учня"""
    try:
        client = get_client_for_table("attendance")
        query = client.table("attendance").select(
            "*, lessons(id, scheduled_at, topic, groups(name, courses(name)))"
        ).eq("student_id", student_id)
        
        # Фільтрація за датою
        date_from = request.args.get("date_from")
        if date_from:
            query = query.gte("lessons.scheduled_at", date_from)
        
        date_to = request.args.get("date_to")
        if date_to:
            query = query.lte("lessons.scheduled_at", date_to)
        
        query = query.order("lessons.scheduled_at", desc=True)
        response = query.execute()
        
        return jsonify(attendance=response.data), 200
    except Exception as e:
        log.error(f"Error getting attendance for student {student_id}: {e}")
        return jsonify(error="server_error", message="Не вдалося отримати дані відвідуваності"), 500


@bp.route("/<int:student_id>/payments", methods=["GET"])
def get_student_payments(student_id):
    """Отримати платежі учня"""
    try:
        client = get_client_for_table("payments")
        query = client.table("payments").select("*").eq("student_id", student_id)
        query = query.order("paid_at", desc=True)
        response = query.execute()
        
        return jsonify(payments=response.data), 200
    except Exception as e:
        log.error(f"Error getting payments for student {student_id}: {e}")
        return jsonify(error="server_error", message="Не вдалося отримати дані про платежі"), 500
