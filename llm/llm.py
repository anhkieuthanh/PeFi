"""
LLM Module - Kết nối với local LLM server và database
"""

import json
import logging
from datetime import date
from typing import Any, Dict, List, Optional

from src.utils.http_session import get_session

# Load config (works both when running from src/ and repo root)
try:
    import config
except Exception:
    from src import config

logger = logging.getLogger(__name__)


class LocalLLMClient:
    """Client để kết nối với local LLM server (LM Studio, Ollama, etc.)"""

    def __init__(self, base_url: str = "http://localhost:1234/v1", timeout: int = 120):
        """
        Initialize LLM client

        Args:
            base_url: Base URL của LLM server (OpenAI-compatible)
            timeout: Timeout cho requests (seconds), default 120s cho insights generation
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.headers = {"Content-Type": "application/json"}
        logger.info(f"Initialized LocalLLMClient with base_url: {self.base_url}")

    def test_connection(self) -> bool:
        """
        Test connection đến LLM server

        Returns:
            True nếu kết nối thành công
        """
        try:
            session = get_session()
            response = session.get(f"{self.base_url}/models", headers=self.headers, timeout=5)
            if response.status_code == 200:
                models = response.json()
                logger.info(f"✓ Connected to LLM server. Available models: {models}")
                return True
            else:
                logger.warning(f"LLM server responded with status {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"Failed to connect to LLM server: {e}")
            return False

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str = "local-model",
        temperature: float = 0.1,
        max_tokens: int = 1000,
        timeout: Optional[int] = None,  # Allow override timeout per request
    ) -> Optional[str]:
        """
        Gửi chat completion request đến LLM

        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Model name (tùy LLM server)
            temperature: Sampling temperature (0-1)
            max_tokens: Maximum tokens to generate
            timeout: Optional timeout override for this request (seconds)

        Returns:
            Generated text hoặc None nếu lỗi
        """
        try:
            payload = {"model": model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens}

            # Use per-request timeout if provided, else use default
            request_timeout = timeout if timeout is not None else self.timeout

            session = get_session()
            response = session.post(
                f"{self.base_url}/chat/completions", headers=self.headers, json=payload, timeout=request_timeout
            )

            if response.status_code == 200:
                result = response.json()
                content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                return content
            else:
                logger.error(f"LLM request failed: {response.status_code} - {response.text}")
                return None

        except Exception as e:
            logger.exception(f"Error in chat_completion: {e}")
            return None

    def parse_transaction_text(self, raw_text: str) -> Dict[str, Any]:
        """
        Parse Vietnamese transaction text thành structured data

        Args:
            raw_text: Raw transaction text

        Returns:
            Dictionary với transaction info hoặc {"raw": "Invalid"}
        """
        system_prompt = """Bạn là hệ thống trích xuất thông tin giao dịch tài chính.
Phân tích text tiếng Việt và trả về JSON với các trường:
- merchant_name: Tên cửa hàng/người nhận (string, dùng "Payment" nếu không rõ)
- total_amount: Tổng số tiền (integer, không dấu phẩy)
- bill_date: Ngày giao dịch YYYY-MM-DD (string, dùng null nếu không có)
- category_name: Danh mục từ danh sách (string)
- category_type: 0 cho chi tiêu, 1 cho thu nhập (integer)
- note: Mô tả ngắn (string)

Danh mục chi tiêu (0): Ăn uống, Xe cộ, Mua sắm, Học tập, Y tế, Du lịch, Điện, Nước, Internet,
Thuê nhà, Giải trí, Thú cưng, Dịch vụ, Sửa chữa, Quà tặng, Chi tiêu khác
Danh mục thu nhập (1): Lương, Tiền lãi đầu tư, Tiền cho thuê nhà, Thu nhập khác

Trả về ONLY JSON, không có text khác."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Phân tích giao dịch: {raw_text}"},
        ]

        response = self.chat_completion(messages, temperature=0.1, max_tokens=500)

        if not response:
            return {"raw": "Invalid"}

        try:
            # Strip markdown code blocks nếu có
            cleaned = response.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

            data = json.loads(cleaned)

            # Validate và set defaults
            if not isinstance(data, dict) or data.get("total_amount") is None:
                return {"raw": "Invalid"}

            # Set user_id (sẽ được override bởi caller)
            data["user_id"] = 2

            # Set bill_date nếu không có
            if not data.get("bill_date"):
                data["bill_date"] = date.today().isoformat()

            return data

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            logger.error(f"Raw response: {response[:500]}")
            return {"raw": "Invalid"}
        except Exception as e:
            logger.exception(f"Error parsing transaction: {e}")
            return {"raw": "Invalid"}


class LLMDatabaseAgent:
    """Agent để query database bằng natural language"""

    def __init__(self, llm_client: LocalLLMClient, db_getter):
        """
        Initialize agent

        Args:
            llm_client: LocalLLMClient instance
            db_getter: Callable contextmanager that yields a DB connection (e.g., connect_to_heroku_db)
        """
        self.llm = llm_client
        self.db_getter = db_getter
        self.schema_info = self._load_schema()
        logger.info("Initialized LLMDatabaseAgent")

    def _load_schema(self) -> str:
        """Load database schema information"""
        schema = """
Database Schema:

Table: users
- user_id (serial, primary key)
- user_name (varchar, unique)

Table: bills
- bill_id (serial, primary key)
- bill_date (date)
- user_id (integer, foreign key -> users.user_id)
- merchant_name (varchar)
- category_name (varchar)
- total_amount (decimal)
- note (text)
- category_type (smallint) -- 0: chi tiêu, 1: thu nhập
"""
        return schema

    def natural_language_query(self, question: str) -> Dict[str, Any]:
        """
        Trả lời câu hỏi về dữ liệu trong database

        Args:
            question: Câu hỏi bằng tiếng Việt

        Returns:
            Dictionary với answer và data (nếu có)
        """
        system_prompt = f"""Bạn là database query assistant.
Schema:
{self.schema_info}

User sẽ hỏi về dữ liệu. Bạn cần:
1. Tạo SQL query phù hợp (chỉ SELECT, không UPDATE/DELETE)
2. Trả về JSON với format:
{{
  "sql": "SELECT ... FROM ...",
  "explanation": "Giải thích ngắn về query"
}}

Chỉ trả về JSON, không có text khác."""

        messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": question}]

        response = self.llm.chat_completion(messages, temperature=0.1, max_tokens=500)

        if not response:
            return {"success": False, "error": "LLM không trả về response"}

        try:
            # Parse JSON response
            cleaned = response.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

            result = json.loads(cleaned)
            sql = result.get("sql", "")
            explanation = result.get("explanation", "")

            if not sql:
                return {"success": False, "error": "Không tạo được SQL query"}

            # Validate SQL (security check)
            sql_upper = sql.upper()
            if any(keyword in sql_upper for keyword in ["DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "CREATE"]):
                return {"success": False, "error": "Query không được phép (chỉ SELECT)"}

            # Execute query
            with self.db_getter() as conn:
                cursor = conn.cursor()
                cursor.execute(sql)
                rows = cursor.fetchall()
                columns = [desc[0] for desc in cursor.description] if cursor.description else []
                cursor.close()

            # Convert to list of dicts
            data = [dict(zip(columns, row)) for row in rows]

            return {"success": True, "sql": sql, "explanation": explanation, "data": data, "count": len(data)}

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM SQL response: {e}")
            return {"success": False, "error": f"Không parse được JSON: {e}"}
        except Exception as e:
            logger.exception(f"Error executing query: {e}")
            return {"success": False, "error": f"Lỗi database: {str(e)}"}

    def get_spending_insights(self, user_id: int, days: int = 30) -> str:
        """
        Tạo insights về chi tiêu của user

        Args:
            user_id: User ID
            days: Số ngày để phân tích

        Returns:
            Text insights từ LLM
        """
        try:
            # Get spending data
            sql = f"""
            SELECT
                category_name,
                category_type,
                SUM(total_amount) as total,
                COUNT(*) as count
            FROM bills
            WHERE user_id = %s
              AND bill_date >= CURRENT_DATE - INTERVAL '{days} days'
            GROUP BY category_name, category_type
            ORDER BY total DESC;
            """

            with self.db_getter() as conn:
                cursor = conn.cursor()
                cursor.execute(sql, (user_id,))
                rows = cursor.fetchall()
                columns = [desc[0] for desc in cursor.description]
                cursor.close()

            if not rows:
                return f"Không có dữ liệu chi tiêu trong {days} ngày qua."

            # Format data for LLM
            data_text = f"Dữ liệu chi tiêu của user_id={user_id} trong {days} ngày qua:\n\n"
            for row in rows:
                row_dict = dict(zip(columns, row))
                category_type = "Thu nhập" if row_dict["category_type"] == 1 else "Chi tiêu"
                data_text += (
                    f"- {row_dict['category_name']} ({category_type}): "
                    f"{row_dict['total']:,.0f} VND ({row_dict['count']} giao dịch)\n"
                )

            logger.info(f"Generating insights for {len(rows)} categories...")

            # Ask LLM for insights
            messages = [
                {
                    "role": "system",
                    "content": (
                        "Bạn là financial advisor. Phân tích dữ liệu chi tiêu và đưa ra "
                        "insights ngắn gọn (3-5 câu), lời khuyên cụ thể. Trả lời bằng tiếng Việt."
                    ),
                },
                {"role": "user", "content": f"{data_text}\n\nHãy phân tích ngắn gọn chi tiêu của tôi."},
            ]

            # Use shorter max_tokens and higher temperature for insights
            insights = self.llm.chat_completion(
                messages,
                temperature=0.4,
                max_tokens=300,  # Reduced from 800 to speed up generation
                timeout=180,  # 3 minutes for insights (longer than default)
            )

            if insights:
                logger.info("Insights generated successfully")
                return insights
            else:
                logger.warning("LLM returned empty insights")
                return "Không thể tạo insights lúc này."

        except Exception as e:
            logger.exception(f"Error getting insights: {e}")
            return f"Lỗi khi tạo insights: {str(e)}"

    def get_quick_summary(self, user_id: int, days: int = 30) -> str:
        """
        Tạo summary nhanh về chi tiêu (không cần LLM)

        Args:
            user_id: User ID
            days: Số ngày để phân tích

        Returns:
            Text summary
        """
        try:
            sql = f"""
            SELECT
                category_name,
                category_type,
                SUM(total_amount) as total,
                COUNT(*) as count
            FROM bills
            WHERE user_id = %s
              AND bill_date >= CURRENT_DATE - INTERVAL '{days} days'
            GROUP BY category_name, category_type
            ORDER BY total DESC
            LIMIT 5;
            """

            with self.db_getter() as conn:
                cursor = conn.cursor()
                cursor.execute(sql, (user_id,))
                rows = cursor.fetchall()
                columns = [desc[0] for desc in cursor.description]
                cursor.close()

            if not rows:
                return f"Không có dữ liệu chi tiêu trong {days} ngày qua."

            # Build summary
            summary = f"📊 Tóm tắt {days} ngày qua:\n\n"

            total_expense = 0
            total_income = 0

            for row in rows:
                row_dict = dict(zip(columns, row))
                amount = float(row_dict["total"])

                if row_dict["category_type"] == 0:  # Chi tiêu
                    total_expense += amount
                    summary += f"💰 {row_dict['category_name']}: {amount:,.0f} VND ({row_dict['count']} giao dịch)\n"
                else:  # Thu nhập
                    total_income += amount
                    summary += f"💵 {row_dict['category_name']}: {amount:,.0f} VND ({row_dict['count']} giao dịch)\n"

            summary += f"\n📈 Tổng thu nhập: {total_income:,.0f} VND"
            summary += f"\n📉 Tổng chi tiêu: {total_expense:,.0f} VND"

            balance = total_income - total_expense
            if balance > 0:
                summary += f"\n✅ Còn lại: +{balance:,.0f} VND"
            else:
                summary += f"\n⚠️  Vượt chi: {balance:,.0f} VND"

            return summary

        except Exception as e:
            logger.exception(f"Error getting summary: {e}")
            return f"Lỗi khi tạo summary: {str(e)}"


def create_llm_client(base_url: str = "http://localhost:1234/v1", timeout: Optional[int] = None) -> LocalLLMClient:
    """
    Factory function để tạo LLM client

    Args:
        base_url: URL của local LLM server
        timeout: Timeout cho requests (seconds)

    Returns:
        LocalLLMClient instance
    """
    if timeout is None:
        timeout = getattr(config, "LLM_DEFAULT_TIMEOUT", 120)
    return LocalLLMClient(base_url=base_url, timeout=timeout)


def create_llm_db_agent(base_url: str = "http://localhost:1234/v1", timeout: int = 120) -> Optional[LLMDatabaseAgent]:
    """
    Factory function để tạo LLM Database Agent

    Args:
        base_url: URL của local LLM server
        timeout: Timeout cho requests (seconds)

    Returns:
        LLMDatabaseAgent instance hoặc None nếu không connect được DB
    """
    try:
        from database.database import connect_to_heroku_db

        llm_client = LocalLLMClient(base_url=base_url, timeout=timeout)

        # Pass the contextmanager function into the agent so it can get pooled
        # connections for each operation.
        return LLMDatabaseAgent(llm_client, connect_to_heroku_db)

    except Exception as e:
        logger.exception(f"Error creating LLMDatabaseAgent: {e}")
        return None
