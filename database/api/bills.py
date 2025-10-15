from flask import Blueprint, request, jsonify, current_app
# Robust import of DB connector regardless of CWD
try:
    from app.database import connect_to_heroku_db
except Exception:
    import sys
    from pathlib import Path
    db_root = Path(__file__).resolve().parents[1]  # .../database
    if str(db_root) not in sys.path:
        sys.path.insert(0, str(db_root))
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
    required_fields = ['user_id', 'total_amount', 'category_name', 'category_type', 'bill_date','note','merchant_name']
    if not data or not all(field in data for field in required_fields):
        return jsonify({"error": "Thiếu trường bắt buộc"}), 400

    # Idempotency: if header provided, store/check to avoid duplicates
    idem_key = request.headers.get('Idempotency-Key')

    # Use %s placeholders for psycopg2 parameters (psycopg2 will adapt types)
    sql = """
    INSERT INTO bills (user_id, total_amount, category_name, category_type, bill_date, note, merchant_name)
    VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING *;
    """
    values = (
        data['user_id'],
        data['total_amount'],
        data['category_name'],
        data['category_type'],
        data['bill_date'],
        data['note'],
        data['merchant_name']
    )

    connection = None
    try:
        connection = connect_to_heroku_db()
        if not connection:
            return jsonify({"error": "Lỗi kết nối database"}), 500
        cursor = connection.cursor()
        if idem_key:
            try:
                cursor.execute("SELECT key FROM idempotency_keys WHERE key = %s;", (idem_key,))
                exists = cursor.fetchone()
                if exists:
                    # Already processed, return a friendly 200
                    cursor.close()
                    connection.close()
                    return jsonify({"message": "Đã ghi nhận hóa đơn trước đó (idempotent)", "idempotency_key": idem_key}), 200
            except Exception as e:
                # If table doesn't exist or another error occurred, rollback and try to create table
                try:
                    connection.rollback()
                except Exception:
                    pass
                try:
                    cursor = connection.cursor()
                    cursor.execute(
                        "CREATE TABLE IF NOT EXISTS idempotency_keys (key TEXT PRIMARY KEY, created_at TIMESTAMP DEFAULT NOW());"
                    )
                    connection.commit()
                except Exception:
                    try:
                        connection.rollback()
                    except Exception:
                        pass
                    # continue without idempotency
                finally:
                    try:
                        cursor.close()
                    except Exception:
                        pass
                    cursor = connection.cursor()
        cursor.execute(sql, values)
        new_bill = cursor.fetchone()

        connection.commit()
        if cursor.description is None or new_bill is None:
            cursor.close()
            return jsonify({"error": "Không thể tạo hóa đơn"}), 500

        bill_columns = [desc[0] for desc in cursor.description]
        bill_json = dict(zip(bill_columns, new_bill))
        
        try:
            amount = bill_json.get('total_amount')
            merchant = bill_json.get('merchant_name')
            category_name = bill_json.get('category_name')
            category_type = bill_json.get('category_type')
            bdate = bill_json.get('bill_date')
            transaction_info = f"{category_name} ({category_type}) - {amount} tại {merchant} vào {bdate}"
        except Exception:
            transaction_info = None

        # record idempotency key after successful creation
        if idem_key:
            try:
                cursor.execute("INSERT INTO idempotency_keys(key) VALUES(%s) ON CONFLICT (key) DO NOTHING;", (idem_key,))
                connection.commit()
            except Exception:
                try:
                    connection.rollback()
                except Exception:
                    pass

        cursor.close()
        # Emit realtime event to clients
        try:
            socketio = current_app.config.get('socketio_instance')
            if socketio:
                socketio.emit('bills_updated', {
                    'action': 'created',
                    'bill': bill_json,
                })
        except Exception:
            pass

        # Return the created bill and include the transaction_info field
        resp = {**bill_json}
        if transaction_info:
            resp['transaction_info'] = transaction_info
        # 201 for new, 200 if idempotent existed (handled above), here is new
        return jsonify(resp), 201
    except psycopg2.IntegrityError as e:
        # Handle foreign key violation (e.g., invalid user_id)
        if getattr(e, 'pgcode', None) == '23503':
            return jsonify({"error": "Dữ liệu không hợp lệ", "details": "user_id không tồn tại"}), 400
        logger.exception("Integrity error while adding bill")
        return jsonify({"error": "Lỗi database", "details": str(e)}), 500
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
    
    if cursor.description is None:
        # Fallback column names if description is unexpectedly None
        bill_json = {
            "bill_id": bill[0],
            "bill_date": bill[1],
            "user_id": bill[2],
            "merchant_name": bill[3],
            "category_name": bill[4],
            "total_amount": bill[5],
            "note": bill[6],
        }
    else:
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
    for key in ['user_id', 'total_amount', 'category_name', 'category_type', 'bill_date', 'note', 'merchant_name']:
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
            connection.commit()
            cursor.close()
            return jsonify({"error": "Không tìm thấy hóa đơn để cập nhật"}), 404

        connection.commit()
        if cursor.description is None:
            cursor.close()
            return jsonify({"error": "Lỗi khi cập nhật hóa đơn"}), 500

        bill_columns = [desc[0] for desc in cursor.description]
        bill_json = dict(zip(bill_columns, updated_bill))
        
        cursor.close()
        # Emit realtime event to clients
        try:
            socketio = current_app.config.get('socketio_instance')
            if socketio:
                socketio.emit('bills_updated', {
                    'action': 'updated',
                    'bill': bill_json,
                })
        except Exception:
            pass
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
        # Emit realtime event to clients
        try:
            socketio = current_app.config.get('socketio_instance')
            if socketio:
                socketio.emit('bills_updated', {
                    'action': 'deleted',
                    'bill_id': deleted_bill[0],
                })
        except Exception:
            pass
        return jsonify({"message": f"Hóa đơn với ID {deleted_bill[0]} đã bị xóa."}), 200
    except psycopg2.Error as e:
        return jsonify({"error": "Lỗi database"}), 500
    finally:
        if connection:
            connection.close()