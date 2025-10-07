from flask import Blueprint, request, jsonify
from app.database import connect_to_heroku_db
import psycopg2
from .request_utils import parse_json_request
import logging
import traceback

logger = logging.getLogger(__name__)
from .utils import parse_bill_date

bills_bp = Blueprint('bills_api', __name__)
# Thêm bill với các trường merchant_name, total_amount, bill_date, category_name, note, user_id
@bills_bp.route('/bills', methods=['POST'])
def add_bill():
    """Thêm một hóa đơn mới."""
    data = parse_json_request()
    print("request data:", data)
    required_fields = ['user_id', 'total_amount', 'category_name', 'bill_date','note','merchant_name']
    if not data or not all(field in data for field in required_fields):
        return jsonify({"error": "Thiếu trường bắt buộc"}), 400

    # Use %s placeholders for psycopg2 parameters (psycopg2 will adapt types)
    sql = """
    INSERT INTO bills (user_id, total_amount, category_name, bill_date, note, merchant_name)
    VALUES (%s, %s, %s, %s, %s, %s) RETURNING *;
    """
    values = (
        data['user_id'],
        data['total_amount'],
        data['category_name'],
        parse_bill_date(data['bill_date']).isoformat(),
        data['note'],
        data['merchant_name']
    )

    connection = None
    try:
        connection = connect_to_heroku_db()
        if not connection:
            return jsonify({"error": "Lỗi kết nối database"}), 500
        cursor = connection.cursor()
        cursor.execute(sql, values)
        new_bill = cursor.fetchone()

        connection.commit()
        if cursor.description is None or new_bill is None:
            cursor.close()
            return jsonify({"error": "Không thể tạo hóa đơn"}), 500

        bill_columns = [desc[0] for desc in cursor.description]
        bill_json = dict(zip(bill_columns, new_bill))

        # Compose a human-readable summary so clients (like the Telegram bot)
        # can display a friendly message without additional parsing.
        try:
            amount = bill_json.get('total_amount')
            merchant = bill_json.get('merchant_name')
            category = bill_json.get('category_name')
            bdate = bill_json.get('bill_date')
            transaction_info = f"{category} - {amount} tại {merchant} vào {bdate}"
        except Exception:
            transaction_info = None

        cursor.close()
        # Return the created bill and include the transaction_info field
        resp = {**bill_json}
        if transaction_info:
            resp['transaction_info'] = transaction_info
        return jsonify(resp), 201
    except psycopg2.Error as e:
        logger.exception("Database error while adding bill")
        return jsonify({"error": "Lỗi database", "details": str(e)}), 500
    except Exception as e:
        # Catch-all to help debug unexpected 500s
        tb = traceback.format_exc()
        logger.error("Unexpected error in add_bill: %s\n%s", e, tb)
        return jsonify({"error": "Unexpected server error", "details": str(e), "trace": tb}), 500
    finally:
        if connection:
            connection.close()

@bills_bp.route('/bills/<int:bill_id>', methods=['GET'])
def get_bill(bill_id):
    """Lấy thông tin một hóa đơn theo ID."""
    sql = "SELECT * FROM bills WHERE bill_id = %s;"
    connection = connect_to_heroku_db()
    if not connection:
        return jsonify({"error": "Lỗi kết nối database"}), 500
    
    cursor = connection.cursor()
    cursor.execute(sql, (bill_id,))
    bill = cursor.fetchone()
    
    if bill is None:
        return jsonify({"error": "Không tìm thấy hóa đơn"}), 404
    
    bill_columns = [desc[0] for desc in cursor.description]
    bill_json = dict(zip(bill_columns, bill))
    
    cursor.close()
    connection.close()
    return jsonify(bill_json), 200

@bills_bp.route('/bills/<int:bill_id>', methods=['PUT'])
def update_bill(bill_id):
    """Cập nhật thông tin một hóa đơn."""
    data = parse_json_request()

    if not data:
        return jsonify({"error": "Dữ liệu cập nhật trống"}), 400

    fields = []
    values = []
    for key in ['user_id', 'total_amount', 'category_name', 'bill_date', 'note', 'merchant_name']:
        if key in data:
            fields.append(f"{key} = %s")
            if key == 'bill_date':
                # normalize date formats
                try:
                    values.append(parse_bill_date(data[key]).isoformat())
                except Exception as e:
                    return jsonify({"error": str(e)}), 400
            else:
                values.append(data[key])
    
    if not fields:
        return jsonify({"error": "Không có trường hợp lệ để cập nhật"}), 400

    sql = f"UPDATE bills SET {', '.join(fields)} WHERE bill_id = %s RETURNING *;"
    values.append(bill_id)

    connection = None
    try:
        connection = connect_to_heroku_db()
        if not connection:
            return jsonify({"error": "Lỗi kết nối database"}), 500
        cursor = connection.cursor()
        cursor.execute(sql, tuple(values))
        updated_bill = cursor.fetchone()

        if updated_bill is None:
            return jsonify({"error": "Không tìm thấy hóa đơn để cập nhật"}), 404

        connection.commit()
        if cursor.description is None:
            cursor.close()
            return jsonify({"error": "Lỗi khi cập nhật hóa đơn"}), 500

        bill_columns = [desc[0] for desc in cursor.description]
        bill_json = dict(zip(bill_columns, updated_bill))
        
        cursor.close()
        return jsonify(bill_json), 200
    except psycopg2.Error as e:
        return jsonify({"error": "Lỗi database"}), 500
    finally:
        if connection:
            connection.close()

@bills_bp.route('/bills/<int:bill_id>', methods=['DELETE'])
def delete_bill(bill_id):
    """Xóa một hóa đơn."""
    sql = "DELETE FROM bills WHERE bill_id = %s RETURNING bill_id;"
    connection = None
    try:
        connection = connect_to_heroku_db()
        if not connection:
            return jsonify({"error": "Lỗi kết nối database"}), 500
        cursor = connection.cursor()
        cursor.execute(sql, (bill_id,))
        deleted_bill = cursor.fetchone()
        
        if deleted_bill is None:
            return jsonify({"error": "Không tìm thấy hóa đơn để xóa"}), 404
            
        connection.commit()
        cursor.close()
        return jsonify({"message": f"Hóa đơn với ID {deleted_bill[0]} đã bị xóa."}), 200
    except psycopg2.Error as e:
        return jsonify({"error": "Lỗi database"}), 500
    finally:
        if connection:
            connection.close()