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
    # Provide a sane default for user_id so callers that don't map users still succeed
    bill_data.setdefault("user_id", 2)

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


def get_transactions_summary(user_id: int = 2, start_date: Optional[str] = None, end_date: Optional[str] = None, tx_type: str = "both") -> Dict[str, Any]:
    """Return aggregated transaction summary for a user between start_date and end_date.

    start_date and end_date are required (ISO format YYYY-MM-DD).

    tx_type: 'thu' | 'chi' | 'both'

    Returns dict with keys:
      - total_income
      - total_expense
      - transaction_count
      - largest_transaction: dict or None
      - top_category: dict or None
      - save_percentage
      - daily_average_expense
      - per_category: list of dicts
    """
    # Enforce required parameters
    if not start_date or not end_date:
        return {"error": "start_date and end_date are required and must be provided in YYYY-MM-DD format"}

    try:
        # Defensive: if caller passed the literal string 'None' or empty strings, treat as missing
        if isinstance(start_date, str) and start_date.strip().lower() in ("none", ""):
            return {"error": "start_date and end_date are required and must be provided in YYYY-MM-DD format"}
        if isinstance(end_date, str) and end_date.strip().lower() in ("none", ""):
            return {"error": "start_date and end_date are required and must be provided in YYYY-MM-DD format"}

        # Compute daily average expense using provided start/end dates
        try:
            from datetime import datetime

            d1 = datetime.strptime(start_date, "%Y-%m-%d").date()
            d2 = datetime.strptime(end_date, "%Y-%m-%d").date()
            days = (d2 - d1).days + 1 if d2 >= d1 else 1
        except Exception:
            days = 1

        with connect_to_heroku_db() as connection:
            cursor = connection.cursor()

            # Build WHERE clause
            where_parts = ["user_id = %s", "bill_date BETWEEN %s AND %s"]
            params = [user_id, start_date, end_date]

            # Apply type filter
            if tx_type == "thu":
                where_parts.append("category_type::text = '1'")
            elif tx_type == "chi":
                where_parts.append("category_type::text <> '1'")

            where_clause = " AND ".join(where_parts)

            # Optimized single query using CTEs to get all data at once
            # Note: We use the same WHERE clause 3 times, so we need params repeated 3 times
            sql = f"""
            WITH totals AS (
                SELECT 
                    SUM(CASE WHEN category_type::text = '1' THEN total_amount ELSE 0 END) AS total_income,
                    SUM(CASE WHEN category_type::text <> '1' THEN total_amount ELSE 0 END) AS total_expense,
                    COUNT(*) AS transaction_count
                FROM bills WHERE {where_clause}
            ),
            largest AS (
                SELECT bill_id, bill_date, merchant_name, total_amount
                FROM bills WHERE {where_clause}
                ORDER BY total_amount DESC LIMIT 1
            ),
            top_cat AS (
                SELECT category_name, SUM(total_amount) AS total
                FROM bills WHERE {where_clause}
                GROUP BY category_name ORDER BY total DESC LIMIT 1
            )
            SELECT 
                t.total_income, t.total_expense, t.transaction_count,
                l.bill_id, l.bill_date, l.merchant_name, l.total_amount,
                tc.category_name, tc.total
            FROM totals t
            LEFT JOIN largest l ON true
            LEFT JOIN top_cat tc ON true;
            """
            
            # We use the WHERE clause 3 times in the CTEs, so repeat params 3 times
            all_params = params * 3
            cursor.execute(sql, all_params)
            row = cursor.fetchone()
            
            # Extract main aggregates
            total_income = float(row[0]) if row and row[0] is not None else 0.0
            total_expense = float(row[1]) if row and row[1] is not None else 0.0
            transaction_count = int(row[2]) if row and row[2] is not None else 0
            
            # Largest transaction
            largest = None
            if row and row[3] is not None:
                largest = {
                    "bill_id": row[3],
                    "bill_date": row[4].isoformat() if hasattr(row[4], "isoformat") else str(row[4]),
                    "merchant_name": row[5],
                    "amount": float(row[6]),
                }
            
            # Top category
            top_category = None
            if row and row[7] is not None:
                top_category = {"category_name": row[7], "total": float(row[8])}
            
            # Per-category breakdown (separate query since it returns multiple rows)
            sql_per_cat = f"""
                SELECT category_name, SUM(total_amount) AS total
                FROM bills WHERE {where_clause}
                GROUP BY category_name ORDER BY total DESC LIMIT 10
            """
            cursor.execute(sql_per_cat, params)
            rows = cursor.fetchall()
            per_category = []
            for r in rows:
                per_category.append({"category_name": r[0], "total": float(r[1]) if r[1] is not None else 0.0})

            cursor.close()

            # Calculate derived metrics
            save_percentage = (total_income - total_expense) / total_income * 100 if total_income > 0 else 0.0
            daily_average_expense = total_expense / days if days > 0 else 0.0

            return {
                "total_income": total_income,
                "total_expense": total_expense,
                "transaction_count": transaction_count,
                "largest_transaction": largest,
                "top_category": top_category,
                "per_category": per_category,
                "save_percentage": save_percentage,
                "daily_average_expense": daily_average_expense,
            }

    except Exception:
        logger.exception("Error querying transactions summary")
        return {"error": "Database error when summarizing transactions"}
