from flask import Blueprint, request, jsonify
from app.database import connect_to_heroku_db
import psycopg2
from .request_utils import parse_json_request

categories_bp = Blueprint('categories_api', __name__)

#Lấy danh sách tất cả các danh mục của user_id
@categories_bp.route('/categories', methods=['GET'])
def get_categories():
    """Lấy tất cả danh mục của một người dùng."""
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({"error": "Thiếu tham số 'user_id'"}), 400

    sql = "SELECT * FROM categories WHERE user_id = %s;"
    connection = connect_to_heroku_db()
    if not connection:
        return jsonify({"error": "Lỗi kết nối database"}), 500
    
    cursor = connection.cursor()
    cursor.execute(sql, (user_id,))
    categories = cursor.fetchall()
    
    category_columns = [desc[0] for desc in cursor.description]
    categories_json = [dict(zip(category_columns, category)) for category in categories]
    
    cursor.close()
    connection.close()
    return jsonify(categories_json), 200
# Thêm 1 danh mục mới cho người dùng id user_id với category_type
@categories_bp.route('/categories', methods=['POST'])
def add_category():
    """Thêm một danh mục mới."""
    data = parse_json_request()
    required_fields = ['user_id', 'category_name', 'category_type']
    if not data or not all(field in data for field in required_fields):
        return jsonify({"error": f"Thiếu trường bắt buộc. Cần có: {', '.join(required_fields)}"}), 400

    sql = """
    INSERT INTO categories (user_id, category_name, category_type)
    VALUES (%s, %s, %s) RETURNING *;
    """
    connection = None
    try:
        connection = connect_to_heroku_db()
        if not connection:
            return jsonify({"error": "Lỗi kết nối database"}), 500
        cursor = connection.cursor()
        cursor.execute(sql, (
            data['user_id'],
            data['category_name'],
            data['category_type']
        ))
        new_category = cursor.fetchone()
        connection.commit()
        if cursor.description is None or new_category is None:
            cursor.close()
            return jsonify({"error": "Không thể tạo danh mục"}), 500

        category_columns = [desc[0] for desc in cursor.description]
        new_category_json = dict(zip(category_columns, new_category))
        cursor.close()
        return jsonify(new_category_json), 201
    except psycopg2.Error as e:
        return jsonify({"error": "Lỗi database"}), 500
    finally:
        if connection:
            connection.close()
# Cập nhật tên danh mục (Không cân, sẽ fix sẵn 1 số danh mục)
@categories_bp.route('/categories/<int:user_id>', methods=['PUT'])

# Xoá danh mục theo user_id và category_id
@categories_bp.route('/categories/<int:user_id>', methods=['DELETE'])
def delete_category(user_id):
    """Xóa một danh mục."""
    data = parse_json_request()
    if not data or 'category_id' not in data:
        return jsonify({"error": "Thiếu trường 'category_id'"}), 400

    sql = "DELETE FROM categories WHERE user_id = %s AND category_id = %s RETURNING category_id;"
    connection = None
    try:
        connection = connect_to_heroku_db()
        cursor = connection.cursor()
        cursor.execute(sql, (user_id, data['category_id']))
        deleted_category = cursor.fetchone()
        if deleted_category is None:
            return jsonify({"error": "Không tìm thấy danh mục để xóa"}), 404
        connection.commit()
        cursor.close()
        return jsonify({"message": "Xóa danh mục thành công", "category_id": deleted_category[0]}), 200
    except psycopg2.Error as e:
        return jsonify({"error": "Lỗi database"}), 500
    finally:
        if connection:
            connection.close()
# --- KẾT THÚC FILE categories.py ---            
