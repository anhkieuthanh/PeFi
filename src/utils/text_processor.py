import json
import logging
import time
from google.api_core.exceptions import DeadlineExceeded
from datetime import date
from typing import Any, Dict
import re

from .path_setup import setup_project_root
from .promt import get_prompt_path, read_promt_file

# Standardize import of config across run contexts
try:
    import config  # when running from src/
except Exception:
    setup_project_root(__file__)
    from src import config  # when running from repo root

logger = logging.getLogger(__name__)


def parse_text_for_info(raw_text: str) -> Dict[str, Any]:
    try:
        prompt = read_promt_file(get_prompt_path("text_input.txt"))
        model = config.get_text_model()

        # Use generation_config to enforce JSON output
        generation_config = {"temperature": 0.1, "response_mime_type": "application/json"}

        # Call Gemini with retries on DeadlineExceeded (504)
        def _call_generate():
            return model.generate_content(
                [prompt, raw_text], generation_config=generation_config, request_options={"timeout": 60}
            )

        max_retries = 3
        backoff = 1
        response = None
        for attempt in range(1, max_retries + 1):
            try:
                response = _call_generate()
                break
            except DeadlineExceeded as e:
                logger.warning(f"Gemini DeadlineExceeded (attempt {attempt}/{max_retries}): {e}")
                if attempt == max_retries:
                    logger.error("Gemini requests timed out after retries")
                    return {"raw": "Invalid"}
                time.sleep(backoff)
                backoff *= 2
        if response is None:
            logger.error("No response from Gemini after retries")
            return {"raw": "Invalid"}
        result_str = response.text if response.text else ""
        logger.info(f"Gemini text response: {result_str[:200]}...")  # Log first 200 chars

        if not result_str or not result_str.strip():
            logger.warning("Gemini returned empty response")
            return {"raw": "Invalid"}

        # Try to extract JSON if wrapped in markdown code blocks
        cleaned_str = result_str.strip()
        if cleaned_str.startswith("```json"):
            cleaned_str = cleaned_str[7:]  # Remove ```json
        if cleaned_str.startswith("```"):
            cleaned_str = cleaned_str[3:]  # Remove ```
        if cleaned_str.endswith("```"):
            cleaned_str = cleaned_str[:-3]  # Remove trailing ```
        cleaned_str = cleaned_str.strip()

        data = json.loads(cleaned_str)

        if not isinstance(data, dict):
            logger.warning(f"Gemini response is not a dict: {type(data)}")
            return {"raw": "Invalid"}

        if data.get("total_amount") is None:
            logger.warning("Gemini response missing total_amount")
            return {"raw": "Invalid"}

        # For testing, set a fixed user_id; in real use get from context/session
        data["user_id"] = 2
        if not data.get("bill_date"):
            data["bill_date"] = date.today().isoformat()
        return data

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse Gemini response as JSON: {e}")
        logger.error(f"Raw response was: {result_str[:200]}...")
        return {"raw": "Invalid"}
    except Exception as e:
        logger.exception(f"Error in parse_text_for_info: {e}")
        return {"raw": "Invalid"}


def preprocess_text(raw_text: str) -> str:
    """Lightweight text normalization used before classification/parsing.

    - Trim leading/trailing whitespace
    - Collapse multiple internal whitespace/newlines to single spaces
    - Preserve case information (don't lowercase) because amounts/dates may be case-sensitive
    """
    if not isinstance(raw_text, str):
        return ""
    # Replace newlines/tabs with spaces, then collapse multi-space sequences
    cleaned = raw_text.replace("\n", " ").replace("\r", " ").replace("\t", " ")
    # collapse multiple spaces
    cleaned = " ".join(cleaned.split())
    return cleaned.strip()


def classify_user_intent(raw_text: str) -> Dict[str, Any]:
    """Classify the user's intent into one of: summarize_expenses, record_transaction, unclear.

    Uses the project's configured Gemini text model (`config.get_text_model()`). Returns a
    dict with keys: intent (str), confidence (float 0-1), explanation (str).

    This function mirrors the retry/backoff behavior used in `parse_text_for_info` to
    handle transient DeadlineExceeded errors from Gemini.
    """
    try:
        text = preprocess_text(raw_text)
        if not text:
            return {"intent": "unclear", "confidence": 0.0, "explanation": "empty input"}

        # All classification should use Gemini per project policy; do not short-circuit with heuristics.

        model = config.get_text_model()

        # Load prompt from prompts/classifier_intent.txt
        try:
            prompt = read_promt_file(get_prompt_path("classifier_intent.txt"))
        except Exception:
            # fallback to the inline prompt if reading fails
            prompt = (
                "You are a classifier that maps user requests into one of three intents:"
                " 'summarize_expenses' (user asks for a summary/overview of spending),"
                " 'record_transaction' (user wants to log a payment/expense),"
                " 'unclear' (cannot determine intent)."
                "\n\nRespond ONLY with a JSON object with keys: intent, confidence (0-1), explanation."
                "\nExamples:\nUser: 'Show me my expenses for last month' -> summarize_expenses\n"
                "User: 'I spent 200k on food today' -> record_transaction\n"
            )

        generation_config = {"temperature": 0.0, "response_mime_type": "application/json"}

        def _call_generate():
            return model.generate_content([prompt, text], generation_config=generation_config, request_options={"timeout": 20})

        max_retries = 2
        backoff = 1
        response = None
        for attempt in range(1, max_retries + 1):
            try:
                response = _call_generate()
                break
            except DeadlineExceeded as e:
                logger.warning(f"Gemini DeadlineExceeded during classification (attempt {attempt}/{max_retries}): {e}")
                if attempt == max_retries:
                    logger.error("Gemini classification timed out after retries")
                    return {"intent": "unclear", "confidence": 0.0, "explanation": "gemini timeout"}
                time.sleep(backoff)
                backoff *= 2

        if response is None or not getattr(response, "text", None):
            logger.error("No response text from Gemini classifier")
            return {"intent": "unclear", "confidence": 0.0, "explanation": "no response"}

        result_str = response.text.strip()
        # strip markdown code fences if present
        if result_str.startswith("```json"):
            result_str = result_str[7:]
        if result_str.startswith("```"):
            result_str = result_str[3:]
        if result_str.endswith("```"):
            result_str = result_str[:-3]
        result_str = result_str.strip()

        try:
            parsed = json.loads(result_str)
            intent = parsed.get("intent") if isinstance(parsed.get("intent"), str) else "unclear"
            confidence = float(parsed.get("confidence", 0.0)) if parsed.get("confidence") is not None else 0.0
            explanation = parsed.get("explanation", "")
            # sanitize
            if intent not in {"summarize_expenses", "record_transaction", "unclear"}:
                logger.warning(f"Unknown intent from Gemini: {intent}")
                intent = "unclear"
            confidence = max(0.0, min(1.0, confidence))
            return {"intent": intent, "confidence": confidence, "explanation": explanation}
        except json.JSONDecodeError:
            logger.warning("Failed to parse Gemini classification response as JSON; returning 'unclear'")
            logger.debug(f"Raw classifier output: {result_str[:200]}...")
            return {"intent": "unclear", "confidence": 0.0, "explanation": "invalid json from classifier"}
    except Exception as e:
        logger.exception(f"Error in classify_user_intent: {e}")
        return {"intent": "unclear", "confidence": 0.0, "explanation": "internal error"}


def preprocess_and_classify_text(raw_text: str) -> Dict[str, Any]:
    """Convenience wrapper: normalize text and return classification result along with normalized_text."""
    normalized = preprocess_text(raw_text)
    cls = classify_user_intent(normalized)
    return {"normalized_text": normalized, "classification": cls}


def generate_user_response(raw_text: str) -> Dict[str, Any]:
    """Produce the user-facing response based on classification.

    Returns a dict with keys:
      - loai_yeu_cau: one of 'Ghi nhận giao dịch', 'Báo cáo', or 'Không hợp lệ'
      - reply_text: the message text to send back to the user (Vietnamese)
      - classification: the raw classification dict from Gemini
      - normalized_text: the preprocessed text

    Behavior rules:
      - If intent is 'summarize_expenses' -> loai_yeu_cau = 'Báo cáo' and reply_text = 'Tôi đã gửi cho bạn'
      - If intent is 'record_transaction' -> loai_yeu_cau = 'Ghi nhận giao dịch' and reply_text acknowledges the record
      - Otherwise -> reply_text = 'Yêu cầu không hợp lệ. Vui lòng gửi lại yêu cầu' and loai_yeu_cau = 'Không hợp lệ'
    """
    normalized = preprocess_text(raw_text)
    classification = classify_user_intent(normalized)

    intent = classification.get("intent") if isinstance(classification, dict) else None

    if intent == "summarize_expenses":
        loai = "Báo cáo"
        reply = "Tôi đã gửi cho bạn"
    elif intent == "record_transaction":
        loai = "Ghi nhận giao dịch"
        reply = "Ghi nhận giao dịch của bạn đã được lưu."
    else:
        loai = "Không hợp lệ"
        reply = "Yêu cầu không hợp lệ. Vui lòng gửi lại yêu cầu"

    return {
        "loai_yeu_cau": loai,
        "reply_text": reply,
        "classification": classification,
        "normalized_text": normalized,
    }


def _parse_date_token(tok: str):
    """Try to parse a date token from common formats. Returns a date or None."""
    from datetime import datetime, date

    tok = tok.strip()
    for fmt in ("%d/%m/%Y", "%d/%m/%y", "%d/%m", "%Y-%m-%d", "%Y"):
        try:
            dt = datetime.strptime(tok, fmt)
            # If year missing in %d/%m, assume current year
            if fmt == "%d/%m":
                dt = dt.replace(year=date.today().year)
            return dt.date()
        except Exception:
            continue
    # fallback: try digits only (YYYYMMDD)
    m = re.match(r"^(\d{4})(\d{2})(\d{2})$", tok)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except Exception:
            return None
    return None


def extract_period_and_type(raw_text: str) -> Dict[str, Any]:
    """Extract start_date, end_date and tx type from a Vietnamese request.

    This is a deterministic, local parser (no LLM). It recognizes common patterns:
      - 'tháng N' or 'tháng N/YYYY' -> month range
      - 'tháng này', 'tháng trước'
      - 'N ngày' -> last N days
      - explicit dates like 'từ 01/11/2025 đến 30/11/2025'
      - type keywords: 'thu' (income), 'chi' (expense)

    Returns dict: {start_date: ISO or None, end_date: ISO or None, type: 'thu'|'chi'|'both', raw_period_text}
    If parsing fails, returns {}.
    """
    from datetime import date, timedelta, datetime

    txt = raw_text.lower()
    today = date.today()

    # default
    typ = "both"
    if re.search(r"\bthu\b|thu nhập|tổng thu|tổng tiền nhận", txt):
        typ = "thu"
    elif re.search(r"\bchi\b|chi tiêu|tiền chi|tổng chi", txt):
        typ = "chi"

    # explicit range: 'từ <date> đến <date>' or 'from <date> to <date>'
    m = re.search(r"từ\s*([\d/\-]+)\s*(?:đến|den|to)\s*([\d/\-]+)", txt)
    if m:
        d1 = _parse_date_token(m.group(1))
        d2 = _parse_date_token(m.group(2))
        if d1 and d2:
            return {"start_date": d1.isoformat(), "end_date": d2.isoformat(), "type": typ, "raw_period_text": m.group(0)}

    # month: 'tháng N' or 'tháng N/YYYY'
    m = re.search(r"tháng\s*(\d{1,2})(?:[\s\-/](\d{4}))?", txt)
    if m:
        month = int(m.group(1))
        year = int(m.group(2)) if m.group(2) else today.year
        start = date(year, month, 1)
        
        # compute last day of the month
        if month == 12:
            last_day_of_month = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            last_day_of_month = date(year, month + 1, 1) - timedelta(days=1)
        
        # If the requested month is the current month and hasn't finished yet,
        # use today as the end date instead of the last day of the month
        if year == today.year and month == today.month and today < last_day_of_month:
            end = today
        else:
            end = last_day_of_month
            
        return {"start_date": start.isoformat(), "end_date": end.isoformat(), "type": typ, "raw_period_text": m.group(0)}

    # 'tháng này'
    if "tháng này" in txt:
        start = today.replace(day=1)
        # For "this month", always use today as end date (not the last day of month)
        # since the month hasn't finished yet
        end = today
        return {"start_date": start.isoformat(), "end_date": end.isoformat(), "type": typ, "raw_period_text": "tháng này"}

    # 'tháng trước'
    if "tháng trước" in txt:
        if today.month == 1:
            y = today.year - 1
            mth = 12
        else:
            y = today.year
            mth = today.month - 1
        start = date(y, mth, 1)
        next_month = (start.replace(day=28) + timedelta(days=4)).replace(day=1)
        end = next_month - timedelta(days=1)
        return {"start_date": start.isoformat(), "end_date": end.isoformat(), "type": typ, "raw_period_text": "tháng trước"}

    # relative 'N ngày' -> last N days
    m = re.search(r"(\d+)\s*ngày", txt)
    if m:
        n = int(m.group(1))
        end = today
        start = today - timedelta(days=n - 1)
        return {"start_date": start.isoformat(), "end_date": end.isoformat(), "type": typ, "raw_period_text": f"{n} ngày qua"}

    # fallback: unable to parse
    return {}


def build_report_text(summary: Dict[str, Any], report_req: Dict[str, Any]) -> str:
    """Deterministic report text generator (no LLM).

    summary: output from get_transactions_summary
    report_req: dict returned by extract_period_and_type
    Returns: Vietnamese text message
    """
    try:
        parts = []
        period_text = report_req.get("raw_period_text") or f"{report_req.get('start_date')} đến {report_req.get('end_date')}"
        tx_type = report_req.get("type", "both")
        parts.append(f"📊 Báo cáo {period_text} — Loại: { 'Thu' if tx_type=='thu' else ('Chi' if tx_type=='chi' else 'Thu & Chi') }")
        parts.append("")
        total_income = summary.get("total_income", 0.0) or 0.0
        total_expense = summary.get("total_expense", 0.0) or 0.0
        transaction_count = summary.get("transaction_count", 0)
        parts.append(f"• Tổng thu: {total_income:,.0f} VND")
        parts.append(f"• Tổng chi: {total_expense:,.0f} VND")
        parts.append(f"• Số giao dịch: {transaction_count}")

        largest = summary.get("largest_transaction")
        if largest:
            parts.append(
                f"• Giao dịch lớn nhất: {largest.get('amount'):,.0f} VND — {largest.get('merchant_name') or 'Không rõ'} ({largest.get('bill_date')})"
            )

        top_cat = summary.get("top_category")
        if top_cat:
            parts.append(f"• Danh mục nhiều nhất: {top_cat.get('category_name')} — {top_cat.get('total'):,.0f} VND")

        if transaction_count == 0:
            parts.append("\nKhông tìm thấy giao dịch trong khoảng thời gian này.")
            return "\n".join(parts)

        # Simple observations
        obs = []
        total = total_income + total_expense
        if total > 0:
            expense_ratio = (total_expense / total) * 100
            obs.append(f"Tỷ lệ chi trên tổng: {expense_ratio:.0f}%.")
            if expense_ratio > 70:
                obs.append("Chi tiêu cao — cân nhắc cắt giảm các khoản không cần thiết.")
            elif expense_ratio < 30 and total_income > 0:
                obs.append("Tỷ lệ tiết kiệm tốt trong kỳ.")

        if top_cat and top_cat.get("category_name"):
            obs.append(f"Lưu ý: nhiều chi tiêu nhất vào danh mục '{top_cat.get('category_name')}'.")

        if obs:
            parts.append("")
            parts.append("Nhận xét:")
            for o in obs:
                parts.append(f"• {o}")

        return "\n".join(parts)
    except Exception:
        logger.exception("Error while building report text")
        return "Đã có lỗi khi tạo báo cáo. Vui lòng thử lại sau."


def gemini_parse_report_request(raw_text: str) -> Dict[str, Any]:
    """Use Gemini to extract structured report parameters from the user's Vietnamese request.

    Returns a dict with keys: start_date (ISO or None), end_date (ISO or None), type ('thu'|'chi'|'both'), raw_period_text.
    If Gemini fails or returns invalid JSON, returns an empty dict.
    """
    try:
        model = config.get_text_model()

        # Load prompt from prompts/report_request_parse.txt
        try:
            prompt = read_promt_file(get_prompt_path("report_request_parse.txt"))
        except Exception:
            prompt = (
                "You are an assistant that extracts structured report parameters from a user's Vietnamese request.\n"
                "Given a user message, return a JSON object with these keys:\n"
                "- start_date: ISO date (YYYY-MM-DD) or null if not specified\n"
                "- end_date: ISO date (YYYY-MM-DD) or null if not specified\n"
                "- type: one of 'thu' (income), 'chi' (expense), or 'both'\n"
                "- raw_period_text: the original substring describing the period\n\n"
                "Examples:\n"
                "User: 'Tổng hợp chi tiêu tháng này' -> {\"start_date\": null, \"end_date\": null, \"type\": \"chi\", \"raw_period_text\": \"tháng này\"}\n"
                "User: 'Tổng hợp thu tháng 10/2024' -> {\"start_date\": \"2024-10-01\", \"end_date\": \"2024-10-31\", \"type\": \"thu\", \"raw_period_text\": \"tháng 10/2024\"}\n"
                "User: 'Tổng hợp 30 ngày qua' -> {\"start_date\": null, \"end_date\": null, \"type\": \"both\", \"raw_period_text\": \"30 ngày qua\"}\n"
                "Now respond with only a valid JSON object (no extra text)."
            )

        generation_config = {"temperature": 0.0, "response_mime_type": "application/json"}

        def _call_generate():
            return model.generate_content([prompt, raw_text], generation_config=generation_config, request_options={"timeout": 20})

        max_retries = 2
        backoff = 1
        response = None
        for attempt in range(1, max_retries + 1):
            try:
                response = _call_generate()
                break
            except DeadlineExceeded as e:
                logger.warning(f"Gemini DeadlineExceeded parsing report request (attempt {attempt}/{max_retries}): {e}")
                if attempt == max_retries:
                    logger.error("Gemini timed out parsing report request")
                    return {}
                time.sleep(backoff)
                backoff *= 2

        if response is None or not getattr(response, "text", None):
            logger.error("No response text from Gemini for report parsing")
            return {}

        result_str = response.text.strip()
        # strip code fences
        if result_str.startswith("```json"):
            result_str = result_str[7:]
        if result_str.startswith("```"):
            result_str = result_str[3:]
        if result_str.endswith("```"):
            result_str = result_str[:-3]
        result_str = result_str.strip()

        parsed = json.loads(result_str)
        start = parsed.get("start_date")
        end = parsed.get("end_date")
        typ = parsed.get("type")
        rawp = parsed.get("raw_period_text", "")
        if typ not in ("thu", "chi", "both"):
            typ = "both"
        return {"start_date": start, "end_date": end, "type": typ, "raw_period_text": rawp}
    except Exception as e:
        logger.exception(f"Error in gemini_parse_report_request: {e}")
        return {}


# Removed run_report_query - it was just a wrapper around get_transactions_summary
# Use get_transactions_summary directly from database.db_operations instead
def generate_report_from_gemini_and_db(raw_text: str, user_id: int, use_gemini_writer: bool = False) -> Dict[str, Any]:
    """High-level helper: use Gemini to extract params, query DB, and build a report text.

    Returns dict: {success: bool, report_text: str, summary: dict, report_req: dict}
    """
    try:
        report_req = gemini_parse_report_request(raw_text)
        if not report_req:
            return {"success": False, "error": "Không thể trích xuất thông tin báo cáo từ yêu cầu"}

        start = report_req.get("start_date")
        end = report_req.get("end_date")
        typ = report_req.get("type", "both")

        # Prefer the central reporting.get_summary so both code paths use the same
        # DB aggregation and classification rules. If reporting module isn't
        # importable (running from different paths), fall back to the central
        # database helper directly.
        try:
            from src.reporting.reporting import get_summary as reporting_get_summary
        except Exception:
            reporting_get_summary = None

        if reporting_get_summary:
            summary = reporting_get_summary(user_id, start, end, typ)
        else:
            # Import the central DB helper directly
            try:
                from database.db_operations import get_transactions_summary as reporting_get_summary
            except Exception:
                from src.database.db_operations import get_transactions_summary as reporting_get_summary
            summary = reporting_get_summary(user_id, start, end, typ)
        if not summary or summary.get("error"):
            return {"success": False, "error": "Lỗi khi truy vấn dữ liệu"}

        # Build report text deterministically
        report_text = build_report_text(summary, report_req)

        return {"success": True, "report_text": report_text, "summary": summary, "report_req": report_req}
    except Exception:
        logger.exception("Error in generate_report_from_gemini_and_db")
        return {"success": False, "error": "Lỗi nội bộ khi tạo báo cáo"}
