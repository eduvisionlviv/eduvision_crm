"""
API для управління відвідуваністю
"""
import logging
from flask import Blueprint, request, jsonify
from api.coreapiserver import get_client_for_table, clear_cache

bp = Blueprint("attendance", __name__, url_prefix="/api/attendance")
log = logging.getLogger("attendance")


@bp.route("/lessons", methods=["GET"])
def list_lessons():
    """Список занять"""
    try:
        client = get_client_for_table("lessons")
        query = client.table("lessons").select("*, groups(name, courses(name))")
        
        # Фільтрація
        group_id = request.args.get("group_id")
        if group_id:
            query = query.eq("group_id", int(group_id))
        
        date_from = request.args.get("date_from")
        if date_from:
            query = query.gte("scheduled_at", date_from)
        
        date_to = request.args.get("date_to")
        if date_to:
            query = query.lte("scheduled_at", date_to)
        
        status = request.args.get("status")
        if status:
            query = query.eq("status", status)
        
        query = query.order("scheduled_at", desc=True)
        response = query.execute()
        
        return jsonify(lessons=response.data), 200
    except Exception as e:
        log.error(f"Error listing lessons: {e}")
        return jsonify(error="server_error", message="Не вдалося отримати список занять"), 500


@bp.route("/lessons", methods=["POST"])
def create_lesson():
    """Створити заняття"""
    try:
        data = request.get_json() or {}
        
        group_id = data.get("group_id")
        scheduled_at = data.get("scheduled_at")
        
        if not group_id or not scheduled_at:
            return jsonify(error="validation_error", message="Група та дата обов'язкові"), 400
        
        lesson_data = {
            "group_id": group_id,
            "scheduled_at": scheduled_at,
            "topic": data.get("topic"),
            "homework": data.get("homework"),
            "status": data.get("status", "scheduled")
        }
        
        client = get_client_for_table("lessons")
        response = client.table("lessons").insert(lesson_data).execute()
        clear_cache("lessons")
        
        return jsonify(lesson=response.data[0]), 201
    except Exception as e:
        log.error(f"Error creating lesson: {e}")
        return jsonify(error="server_error", message="Не вдалося створити заняття"), 500


@bp.route("/lessons/<int:lesson_id>", methods=["GET"])
def get_lesson(lesson_id):
    """Отримати заняття з відвідуваністю"""
    try:
        lessons_client = get_client_for_table("lessons")
        lesson_response = lessons_client.table("lessons").select(
            "*, groups(name, courses(name))"
        ).eq("id", lesson_id).single().execute()
        
        if not lesson_response.data:
            return jsonify(error="not_found", message="Заняття не знайдено"), 404
        
        # Отримати відвідуваність
        attendance_client = get_client_for_table("attendance")
        attendance_response = attendance_client.table("attendance").select(
            "*, student(user_id, user_name)"
        ).eq("lesson_id", lesson_id).execute()
        
        lesson_data = lesson_response.data
        lesson_data["attendance"] = attendance_response.data or []
        
        return jsonify(lesson=lesson_data), 200
    except Exception as e:
        log.error(f"Error getting lesson {lesson_id}: {e}")
        return jsonify(error="server_error", message="Не вдалося отримати дані заняття"), 500


@bp.route("/lessons/<int:lesson_id>", methods=["PUT", "PATCH"])
def update_lesson(lesson_id):
    """Оновити заняття"""
    try:
        data = request.get_json() or {}
        
        update_data = {}
        for field in ["scheduled_at", "topic", "homework", "status"]:
            if field in data:
                update_data[field] = data[field]
        
        if not update_data:
            return jsonify(error="validation_error", message="Немає даних для оновлення"), 400
        
        client = get_client_for_table("lessons")
        response = client.table("lessons").update(update_data).eq("id", lesson_id).execute()
        clear_cache("lessons")
        
        if not response.data:
            return jsonify(error="not_found", message="Заняття не знайдено"), 404
        
        return jsonify(lesson=response.data[0]), 200
    except Exception as e:
        log.error(f"Error updating lesson {lesson_id}: {e}")
        return jsonify(error="server_error", message="Не вдалося оновити заняття"), 500


@bp.route("/mark", methods=["POST"])
def mark_attendance():
    """Відмітити відвідуваність"""
    try:
        data = request.get_json() or {}
        
        lesson_id = data.get("lesson_id")
        student_id = data.get("student_id")
        status = data.get("status")
        
        if not lesson_id or not student_id or not status:
            return jsonify(error="validation_error", message="Заняття, учень та статус обов'язкові"), 400
        
        if status not in ["present", "absent", "late", "excused"]:
            return jsonify(error="validation_error", message="Невірний статус відвідуваності"), 400
        
        attendance_data = {
            "lesson_id": lesson_id,
            "student_id": student_id,
            "status": status,
            "note": data.get("note")
        }
        
        client = get_client_for_table("attendance")
        
        # Спробувати оновити існуючий запис або створити новий
        existing = client.table("attendance").select("id").eq("lesson_id", lesson_id).eq("student_id", student_id).execute()
        
        if existing.data:
            response = client.table("attendance").update(attendance_data).eq("id", existing.data[0]["id"]).execute()
        else:
            response = client.table("attendance").insert(attendance_data).execute()
        
        clear_cache("attendance")
        
        return jsonify(attendance=response.data[0]), 200
    except Exception as e:
        log.error(f"Error marking attendance: {e}")
        return jsonify(error="server_error", message="Не вдалося відмітити відвідуваність"), 500


@bp.route("/bulk-mark", methods=["POST"])
def bulk_mark_attendance():
    """Масова відмітка відвідуваності для заняття"""
    try:
        data = request.get_json() or {}
        
        lesson_id = data.get("lesson_id")
        records = data.get("records", [])
        
        if not lesson_id or not records:
            return jsonify(error="validation_error", message="ID заняття та список учнів обов'язкові"), 400
        
        client = get_client_for_table("attendance")
        results = []
        
        for record in records:
            student_id = record.get("student_id")
            status = record.get("status")
            
            if not student_id or not status:
                continue
            
            attendance_data = {
                "lesson_id": lesson_id,
                "student_id": student_id,
                "status": status,
                "note": record.get("note")
            }
            
            # Спробувати оновити або створити
            existing = client.table("attendance").select("id").eq("lesson_id", lesson_id).eq("student_id", student_id).execute()
            
            if existing.data:
                response = client.table("attendance").update(attendance_data).eq("id", existing.data[0]["id"]).execute()
            else:
                response = client.table("attendance").insert(attendance_data).execute()
            
            if response.data:
                results.append(response.data[0])
        
        clear_cache("attendance")
        
        return jsonify(marked=len(results), records=results), 200
    except Exception as e:
        log.error(f"Error bulk marking attendance: {e}")
        return jsonify(error="server_error", message="Не вдалося відмітити відвідуваність"), 500
