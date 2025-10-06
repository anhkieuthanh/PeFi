from flask import Blueprint, request, jsonify
from app.database import connect_to_heroku_db # Import hàm kết nối
import psycopg2
from psycopg2 import errorcodes

# 1. Tạo một Blueprint mới
users_bp = Blueprint('users_api', __name__)

@users_bp.route('/users', methods=['POST'])
def create_user():
    data = request.get_json()
    if not data or 'user_name' not in data:
        return jsonify({"error": "Thiếu trường 'user_name'"}), 400

    sql = "INSERT INTO users (user_name) VALUES (%s) RETURNING *;"
    connection = None
    try:
        connection = connect_to_heroku_db()
        cursor = connection.cursor()
        cursor.execute(sql, (data['user_name'],))
        new_user = cursor.fetchone()
        connection.commit()
        user_columns = [desc[0] for desc in cursor.description]
        new_user_json = dict(zip(user_columns, new_user))
        cursor.close()
        return jsonify(new_user_json), 201
    except psycopg2.Error as e:
        if e.pgcode == errorcodes.UNIQUE_VIOLATION:
            return jsonify({"error": "Tên người dùng đã tồn tại"}), 409
        return jsonify({"error": "Lỗi database"}), 500
    finally:
        if connection:
            connection.close()

@users_bp.route('/users/<int:user_id>', methods=['GET'])
def get_user(user_id):
    sql = "SELECT * FROM users WHERE user_id = %s;"
    connection = connect_to_heroku_db()
    if not connection:
        return jsonify({"error": "Lỗi kết nối database"}), 500
    
    cursor = connection.cursor()
    cursor.execute(sql, (user_id,))
    user = cursor.fetchone()
    
    if user is None:
        return jsonify({"error": "Không tìm thấy người dùng"}), 404
    
    user_columns = [desc[0] for desc in cursor.description]
    user_json = dict(zip(user_columns, user))
    
    cursor.close()
    connection.close()
    return jsonify(user_json), 200

@users_bp.route('/users/<int:user_id>', methods=['PUT'])
def update_user(user_id):
    data = request.get_json()
    if not data or 'user_name' not in data:
        return jsonify({"error": "Thiếu trường 'user_name'"}), 400

    sql = "UPDATE users SET user_name = %s WHERE user_id = %s RETURNING *;"
    connection = None
    try:
        connection = connect_to_heroku_db()
        cursor = connection.cursor()
        cursor.execute(sql, (data['user_name'], user_id))
        updated_user = cursor.fetchone()
        if updated_user is None:
            return jsonify({"error": "Không tìm thấy người dùng"}), 404
        connection.commit()
        user_columns = [desc[0] for desc in cursor.description]
        updated_user_json = dict(zip(user_columns, updated_user))
        cursor.close()
        return jsonify(updated_user_json), 200
    except psycopg2.Error as e:
        if e.pgcode == errorcodes.UNIQUE_VIOLATION:
            return jsonify({"error": "Tên người dùng đã tồn tại"}), 409
        return jsonify({"error": "Lỗi database"}), 500
    finally:
        if connection:
            connection.close()
            
@users_bp.route('/users/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    sql = "DELETE FROM users WHERE user_id = %s RETURNING *;"
    connection = None
    try:
        connection = connect_to_heroku_db()
        cursor = connection.cursor()
        cursor.execute(sql, (user_id,))
        deleted_user = cursor.fetchone()
        if deleted_user is None:
            return jsonify({"error": "Không tìm thấy người dùng"}), 404
        connection.commit()
        user_columns = [desc[0] for desc in cursor.description]
        deleted_user_json = dict(zip(user_columns, deleted_user))
        cursor.close()
        return jsonify(deleted_user_json), 200
    except psycopg2.Error:
        return jsonify({"error": "Lỗi database"}), 500
    finally:
        if connection:
            connection.close()