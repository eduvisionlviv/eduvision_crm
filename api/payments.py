"""
API для управління оплатами
"""
import logging
from flask import Blueprint, request, jsonify
from api.coreapiserver import get_client_for_table, clear_cache

bp = Blueprint("payments", __name__, url_prefix="/api/payments")
log = logging.getLogger("payments")


@bp.route("", methods=["GET"])
def list_payments():
    """Список платежів"""
    try:
        client = get_client_for_table("payments")
        query = client.table("payments").select("*, student(user_name), parents(user_name)")
        
        # Фільтрація
        student_id = request.args.get("student_id")
        if student_id:
            query = query.eq("student_id", int(student_id))
        
        parent_id = request.args.get("parent_id")
        if parent_id:
            query = query.eq("parent_id", int(parent_id))
        
        status = request.args.get("status")
        if status:
            query = query.eq("status", status)
        
        date_from = request.args.get("date_from")
        if date_from:
            query = query.gte("paid_at", date_from)
        
        date_to = request.args.get("date_to")
        if date_to:
            query = query.lte("paid_at", date_to)
        
        query = query.order("paid_at", desc=True)
        response = query.execute()
        
        return jsonify(payments=response.data), 200
    except Exception as e:
        log.error(f"Error listing payments: {e}")
        return jsonify(error="server_error", message="Не вдалося отримати список платежів"), 500


@bp.route("/<int:payment_id>", methods=["GET"])
def get_payment(payment_id):
    """Отримати платіж за ID"""
    try:
        client = get_client_for_table("payments")
        response = client.table("payments").select(
            "*, student(user_name, user_email), parents(user_name, user_email)"
        ).eq("id", payment_id).single().execute()
        
        if not response.data:
            return jsonify(error="not_found", message="Платіж не знайдено"), 404
        
        return jsonify(payment=response.data), 200
    except Exception as e:
        log.error(f"Error getting payment {payment_id}: {e}")
        return jsonify(error="server_error", message="Не вдалося отримати дані платежу"), 500


@bp.route("", methods=["POST"])
def create_payment():
    """Створити новий платіж"""
    try:
        data = request.get_json() or {}
        
        # Валідація
        student_id = data.get("student_id")
        amount = data.get("amount")
        
        if not student_id or not amount:
            return jsonify(error="validation_error", message="ID учня та сума обов'язкові"), 400
        
        try:
            amount = float(amount)
            if amount <= 0:
                return jsonify(error="validation_error", message="Сума має бути більше 0"), 400
        except (TypeError, ValueError):
            return jsonify(error="validation_error", message="Невірний формат суми"), 400
        
        payment_data = {
            "student_id": student_id,
            "parent_id": data.get("parent_id"),
            "amount": amount,
            "paid_at": data.get("paid_at"),
            "period_start": data.get("period_start"),
            "period_end": data.get("period_end"),
            "status": data.get("status", "pending")
        }
        
        client = get_client_for_table("payments")
        response = client.table("payments").insert(payment_data).execute()
        clear_cache("payments")
        
        return jsonify(payment=response.data[0]), 201
    except Exception as e:
        log.error(f"Error creating payment: {e}")
        return jsonify(error="server_error", message="Не вдалося створити платіж"), 500


@bp.route("/<int:payment_id>", methods=["PUT", "PATCH"])
def update_payment(payment_id):
    """Оновити платіж"""
    try:
        data = request.get_json() or {}
        
        update_data = {}
        
        if "amount" in data:
            try:
                amount = float(data["amount"])
                if amount <= 0:
                    return jsonify(error="validation_error", message="Сума має бути більше 0"), 400
                update_data["amount"] = amount
            except (TypeError, ValueError):
                return jsonify(error="validation_error", message="Невірний формат суми"), 400
        
        for field in ["student_id", "parent_id", "paid_at", "period_start", "period_end", "status"]:
            if field in data:
                update_data[field] = data[field]
        
        if not update_data:
            return jsonify(error="validation_error", message="Немає даних для оновлення"), 400
        
        client = get_client_for_table("payments")
        response = client.table("payments").update(update_data).eq("id", payment_id).execute()
        clear_cache("payments")
        
        if not response.data:
            return jsonify(error="not_found", message="Платіж не знайдено"), 404
        
        return jsonify(payment=response.data[0]), 200
    except Exception as e:
        log.error(f"Error updating payment {payment_id}: {e}")
        return jsonify(error="server_error", message="Не вдалося оновити платіж"), 500


@bp.route("/<int:payment_id>", methods=["DELETE"])
def delete_payment(payment_id):
    """Видалити платіж"""
    try:
        client = get_client_for_table("payments")
        response = client.table("payments").delete().eq("id", payment_id).execute()
        clear_cache("payments")
        
        if not response.data:
            return jsonify(error="not_found", message="Платіж не знайдено"), 404
        
        return jsonify(message="Платіж видалено"), 200
    except Exception as e:
        log.error(f"Error deleting payment {payment_id}: {e}")
        return jsonify(error="server_error", message="Не вдалося видалити платіж"), 500


@bp.route("/stats", methods=["GET"])
def payment_stats():
    """Статистика платежів"""
    try:
        client = get_client_for_table("payments")
        
        # Всі платежі за період
        query = client.table("payments").select("amount, status, paid_at")
        
        date_from = request.args.get("date_from")
        if date_from:
            query = query.gte("paid_at", date_from)
        
        date_to = request.args.get("date_to")
        if date_to:
            query = query.lte("paid_at", date_to)
        
        response = query.execute()
        payments = response.data or []
        
        # Підрахунок статистики
        total_amount = sum(float(p.get("amount", 0)) for p in payments if p.get("status") == "paid")
        pending_amount = sum(float(p.get("amount", 0)) for p in payments if p.get("status") == "pending")
        total_count = len(payments)
        paid_count = sum(1 for p in payments if p.get("status") == "paid")
        pending_count = sum(1 for p in payments if p.get("status") == "pending")
        
        return jsonify(
            total_amount=total_amount,
            pending_amount=pending_amount,
            total_count=total_count,
            paid_count=paid_count,
            pending_count=pending_count
        ), 200
    except Exception as e:
        log.error(f"Error getting payment stats: {e}")
        return jsonify(error="server_error", message="Не вдалося отримати статистику"), 500
