import logging
from typing import Any, Dict, Optional

import psycopg2
from psycopg2 import errorcodes

try:
    # Prefer local database module at database/database.py
    from .database import connect_to_heroku_db 
except Exception:
    import sys
    from pathlib import Path

    db_root = Path(__file__).resolve().parent
    if str(db_root) not in sys.path:
        sys.path.insert(0, str(db_root))
    from .database import connect_to_heroku_db 

logger = logging.getLogger(__name__)


def add_bill(bill_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Add a new bill to the database.

    Args:
        bill_data: Dictionary containing bill information:
            - user_id: int
            - total_amount: float
            - category_name: str
            - category_type: str ('0' for expense, '1' for income)
            - bill_date: str (ISO format YYYY-MM-DD)
            - note: str
            - merchant_name: str

    Returns:
        Dictionary containing:
            - success: bool
            - message: str
            - transaction_info: str (formatted transaction info)
            - bill_id: int (if successful)
    """
    required_fields = [
        "user_id",
        "total_amount",
        "category_name",
        "category_type",
        "bill_date",
        "note",
        "merchant_name",
    ]

    # Validate required fields
    for field in required_fields:
        if field not in bill_data:
            return {"success": False, "error": f"Thiếu trường bắt buộc: {field}"}

    sql = """
    INSERT INTO bills (user_id, total_amount, category_name, category_type, bill_date, note, merchant_name)
    VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING *;
    """

    values = (
        bill_data["user_id"],
        bill_data["total_amount"],
        bill_data["category_name"],
        bill_data["category_type"],
        bill_data["bill_date"],
        bill_data["note"],
        bill_data["merchant_name"],
    )

    try:
        with connect_to_heroku_db() as connection:
            cursor = connection.cursor()
            cursor.execute(sql, values)
            new_bill = cursor.fetchone()
            connection.commit()

        if cursor.description is None or new_bill is None:
            cursor.close()
            return {"success": False, "error": "Không thể thêm hóa đơn"}

        bill_columns = [desc[0] for desc in cursor.description]
        new_bill_dict = dict(zip(bill_columns, new_bill))
        cursor.close()

        # Format transaction info message
        category_type_text = (
            "Thu nhập" if str(bill_data["category_type"]).strip().lower() in ("1", "income") else "Chi tiêu"
        )
        transaction_info = (
            f"✅ Đã lưu giao dịch:\n"
            f"📅 Ngày: {bill_data['bill_date']}\n"
            f"🏪 Merchant: {bill_data['merchant_name']}\n"
            f"📂 Danh mục: {bill_data['category_name']}\n"
            f"💰 Số tiền: {bill_data['total_amount']:,.0f} VND\n"
            f"📝 Loại: {category_type_text}\n"
            f"📄 Ghi chú: {bill_data['note']}"
        )

        return {
            "success": True,
            "message": "Đã thêm hóa đơn thành công",
            "transaction_info": transaction_info,
            "bill_id": new_bill_dict.get("bill_id"),
        }

    except psycopg2.Error as e:
        logger.exception("Database error when adding bill")
        error_msg = "Lỗi database"
        if e.pgcode == errorcodes.UNIQUE_VIOLATION:
            error_msg = "Hóa đơn đã tồn tại"
        elif e.pgcode == errorcodes.FOREIGN_KEY_VIOLATION:
            error_msg = "user_id không tồn tại"

        return {"success": False, "error": error_msg}

    except Exception as e:
        logger.exception("Unexpected error when adding bill")
        return {"success": False, "error": f"Lỗi không xác định: {str(e)}"}
    # connection returned to pool by context manager


def create_user(user_name: str) -> Dict[str, Any]:
    """
    Create a new user in the database.

    Args:
        user_name: Name of the user

    Returns:
        Dictionary containing:
            - success: bool
            - user: dict (user data if successful)
            - error: str (if failed)
    """
    sql = "INSERT INTO users (user_name) VALUES (%s) RETURNING *;"
    try:
        with connect_to_heroku_db() as connection:
            cursor = connection.cursor()
            cursor.execute(sql, (user_name,))
            new_user = cursor.fetchone()
            connection.commit()

        if cursor.description is None or new_user is None:
            cursor.close()
            return {"success": False, "error": "Không thể tạo người dùng"}

        user_columns = [desc[0] for desc in cursor.description]
        new_user_dict = dict(zip(user_columns, new_user))
        cursor.close()

        return {"success": True, "user": new_user_dict}

    except psycopg2.Error as e:
        logger.exception("Database error when creating user")
        if e.pgcode == errorcodes.UNIQUE_VIOLATION:
            return {"success": False, "error": "Tên người dùng đã tồn tại"}
        return {"success": False, "error": "Lỗi database"}

    # connection returned to pool by context manager


def get_user_by_name(user_name: str) -> Optional[Dict[str, Any]]:
    """
    Get user by username.

    Args:
        user_name: Name of the user

    Returns:
        User dictionary if found, None otherwise
    """
    sql = "SELECT * FROM users WHERE user_name = %s;"
    try:
        with connect_to_heroku_db() as connection:
            cursor = connection.cursor()
            cursor.execute(sql, (user_name,))
            user = cursor.fetchone()

            if cursor.description is None or user is None:
                cursor.close()
                return None

            user_columns = [desc[0] for desc in cursor.description]
            user_dict = dict(zip(user_columns, user))
            cursor.close()

            return user_dict

    except Exception:
        logger.exception("Error getting user by name")
        return None

    # connection returned to pool by context manager
