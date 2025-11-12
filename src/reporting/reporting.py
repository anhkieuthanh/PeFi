from typing import Any, Dict, List, Optional
import logging
import json
from datetime import date

import psycopg2

try:
    # Prefer the project's config which reads config.yaml
    from src import config
except Exception:
    import config

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def _get_conn():
    """Return a psycopg2 connection using `config.DATABASE_URL`.

    Expects `config.DATABASE_URL` to be set in `config.yaml`.
    """
    db_url = getattr(config, "DATABASE_URL", None)
    if not db_url:
        raise RuntimeError("DATABASE_URL is not configured in config.yaml")
    return psycopg2.connect(db_url)


def get_summary(user_id: int, start_date: Optional[str], end_date: Optional[str], tx_type: str = "both") -> Dict[str, Any]:
    """Query DB and compute aggregated summary for a user between start_date and end_date.

    Classification rule (SQL):
      - 'Thu' if category_name ILIKE 'Lương' OR category_name ILIKE '%thu nhập%'
      - 'Chi' otherwise

    Returns JSON dict with keys:
      - total_income
      - total_expense
      - transaction_count
      - per_category: list of {category_name, total}
      - top_category: {category_name, total} or None
    """
    # Build dynamic WHERE clause. tx_type may be 'thu', 'chi' or 'both'.
    where_parts: List[str] = ["user_id = %s"]
    params: List[Any] = [user_id]
    if start_date and end_date:
        where_parts.append("bill_date BETWEEN %s AND %s")
        params.extend([start_date, end_date])
    elif start_date:
        where_parts.append("bill_date >= %s")
        params.append(start_date)
    elif end_date:
        where_parts.append("bill_date <= %s")
        params.append(end_date)

    where_clause = " AND ".join(where_parts)

    # Apply tx_type filter: classify by category_name text
    # - 'thu' when category_name lower = 'lương' OR LIKE '%thu nhập%'
    # - 'chi' otherwise
    if tx_type == "thu":
        where_clause = where_clause + " AND (lower(category_name) = %s OR lower(category_name) LIKE %s)"
        params.extend(["lương", "%thu nhập%"])
    elif tx_type == "chi":
        where_clause = where_clause + " AND NOT (lower(category_name) = %s OR lower(category_name) LIKE %s)"
        params.extend(["lương", "%thu nhập%"])

    # Totals query: compute income and expense using CASE
    # Parameterize LIKE patterns to avoid raw '%' in the SQL string which can confuse
    # DB-API formatting. We'll pass the pattern as parameters.
    sql_totals = (
        "SELECT\n"
        "  SUM(CASE WHEN lower(category_name) = %s OR lower(category_name) LIKE %s THEN total_amount ELSE 0 END) AS total_income,\n"
        "  SUM(CASE WHEN NOT (lower(category_name) = %s OR lower(category_name) LIKE %s) THEN total_amount ELSE 0 END) AS total_expense,\n"
        "  COUNT(*) AS transaction_count\n"
        "FROM bills WHERE "
        + where_clause
        + ";"
    )

    # Per-category breakdown for expenses (Chi)
    sql_per_cat = (
        "SELECT category_name, SUM(total_amount) as total FROM bills WHERE "
        + where_clause
        + " GROUP BY category_name ORDER BY total DESC;"
    )

    conn = _get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                # SQL places the CASE placeholders before the WHERE placeholders,
                # so the params must be in the same order: patterns first, then
                # the WHERE params (user_id, start, end)
                totals_params = [
                    "lương",
                    "%thu nhập%",
                    "lương",
                    "%thu nhập%",
                ] + list(params)
                logger.info("Executing totals SQL: %s | params=%s", sql_totals, totals_params)
                cur.execute(sql_totals, totals_params)
                totals = cur.fetchone()

                total_income = float(totals[0]) if totals and totals[0] is not None else 0.0
                total_expense = float(totals[1]) if totals and totals[1] is not None else 0.0
                transaction_count = int(totals[2]) if totals and totals[2] is not None else 0

                # per-category
                logger.info("Executing per-category SQL: %s | params=%s", sql_per_cat, params)
                cur.execute(sql_per_cat, params)
                rows = cur.fetchall()
                per_category = []
                for r in rows:
                    per_category.append({"category_name": r[0], "total": float(r[1]) if r[1] is not None else 0.0})

                top_category = per_category[0] if per_category else None

                return {
                    "total_income": total_income,
                    "total_expense": total_expense,
                    "transaction_count": transaction_count,
                    "per_category": per_category,
                    "top_category": top_category,
                }
    finally:
        conn.close()


def generate_report(summary: Dict[str, Any], period_text: str = "", tx_type: str = "both") -> Dict[str, Any]:
    """Send the aggregated summary to Gemini to generate a short Vietnamese report.

    IMPORTANT: The prompt instructs the LLM to NOT perform calculations. It must use the numbers
    provided in the JSON context. The LLM's job is only to produce human-friendly text.
    """
    # Build JSON context for the LLM
    context = {
        "period": period_text,
        "total_income": summary.get("total_income", 0.0),
        "total_expense": summary.get("total_expense", 0.0),
        "transaction_count": summary.get("transaction_count", 0),
        "top_category": summary.get("top_category"),
    }

    # Templates for the three report types. These are examples the LLM should follow
    # depending on tx_type: 'thu', 'chi', or 'both'. The prompt below instructs the
    # LLM to use the appropriate template and to NOT invent or change numbers.
    TEMPLATE_THA = (
        "# Báo cáo thu\n\n"
        "**Tóm tắt nhanh:** Trong kỳ, tổng thu là `{total_income} VND`.\n\n"
        "**Số liệu chính:**\n"
        "- Tổng thu: `{total_income} VND`\n"
        "- Số giao dịch thu: `{transaction_count} (thu)`\n\n"
        "**Top nguồn thu:**\n"
        "1. `{top_category}` — `{top_amount} VND`\n\n"
        "**Nhận xét và khuyến nghị:**\n"
        "- Đề xuất tối ưu hóa nguồn thu."
    )

    TEMPLATE_CHI = (
        "# Báo cáo chi\n\n"
        "**Tóm tắt nhanh:** Trong kỳ, tổng chi là `{total_expense} VND`.\n\n"
        "**Số liệu chính:**\n"
        "- Tổng chi: `{total_expense} VND`\n"
        "- Số giao dịch chi: `{transaction_count} (chi)`\n\n"
        "**Top danh mục chi tiêu:**\n"
        "1. `{top_category}` — `{top_amount} VND`\n\n"
        "**Nhận xét và khuyến nghị:**\n"
        "- Rà soát danh mục chi lớn để cắt giảm nếu cần."
    )

    TEMPLATE_BOTH = (
        "# Báo cáo thu & chi\n\n"
        "**Tóm tắt nhanh:** Tổng thu `{total_income} VND`, tổng chi `{total_expense} VND`.\n\n"
        "**Số liệu chính:**\n"
        "- Tổng thu: `{total_income} VND`\n"
        "- Tổng chi: `{total_expense} VND`\n"
        "- Số giao dịch: `{transaction_count}`\n\n"
        "**Top danh mục chi tiêu:**\n"
        "1. `{top_category}` — `{top_amount} VND`\n\n"
        "**Nhận xét và khuyến nghị:**\n"
        "- Đưa ra đề xuất cân bằng thu/chi."
    )

    # Compose prompt that asks the LLM to generate a rich, Markdown-formatted report.
    # Important constraints:
    #  - USE the numeric values in the JSON only. Do NOT recompute, modify, or infer new numbers.
    #  - Produce a professional, reader-friendly report in Vietnamese using Markdown.
    #  - Include: title, totals, a top-3 category table or list, ASCII bar chart visualization, short observations, and 1-2 actionable recommendations.
    #  - Keep numeric values exactly as provided (no rounding changes) and append 'VND'.
    # Choose template fragment to include in the prompt
    template_fragment = TEMPLATE_BOTH
    if tx_type == "thu":
        template_fragment = TEMPLATE_THA
    elif tx_type == "chi":
        template_fragment = TEMPLATE_CHI

    prompt = (
        "You are an expert Vietnamese financial-report writer and formatter.\n\n"
        "CONSTRAINTS:\n"
        "- Use ONLY the numeric values in the JSON context. Do NOT change, recompute, or summarize the numbers beyond showing them.\n"
        "- Output MUST be valid Markdown. Use headings, bullet lists, and a small ASCII bar chart for top categories.\n"
        "- Keep the language professional and concise. Aim for clarity and visual readability on messaging apps.\n\n"
    "INPUT JSON:\n"
    + json.dumps(context, ensure_ascii=False)
    + "\n\n"
    "Use this TEMPLATE as an exact formatting guideline (fill placeholders with values from JSON):\n\n"
    + template_fragment
        + "\n\nTASK:\n"
        "Produce a Markdown report in Vietnamese with these sections:\n"
        "1) H1 title with the period.\n"
        "2) A short 'Tóm tắt nhanh' paragraph (1-2 sentences) using the provided numbers only.\n"
        "3) A 'Số liệu chính' bullet list showing Tổng thu, Tổng chi, Số giao dịch (use exact values and append 'VND' where relevant).\n"
        "4) 'Top 3 danh mục' section: show a compact table or numbered list with category name, amount, and an ASCII bar (max width ~20).\n"
        "5) 'Nhận xét và khuyến nghị' 1-3 short bullet points (insightful, actionable).\n"
        "6) Keep total output length reasonably short (not more than ~800 characters), but prefer clarity over strict brevity.\n\n"
        "IMPORTANT: Under no circumstances should you invent additional numeric values or modify the provided numbers. If a value is 0, display '0 VND'.\n\n"
        "Now output only the Markdown report (no extra commentary)."
    )

    # Use project's Gemini model helper
    model = config.get_text_model()

    def _fmt_amount(x):
        try:
            return f"{int(round(x)):,} VND" if x is not None else "0 VND"
        except Exception:
            try:
                return f"{float(x):,.0f} VND"
            except Exception:
                return str(x)

    def _make_bar(value, max_value, width=20):
        try:
            if max_value <= 0:
                return ""
            ratio = float(value) / float(max_value)
            filled = int(round(ratio * width))
            return "█" * filled + "░" * (width - filled)
        except Exception:
            return ""

    def _format_summary_visual(summary: Dict[str, Any], period_text: str) -> str:
        ti = summary.get("total_income", 0.0) or 0.0
        te = summary.get("total_expense", 0.0) or 0.0
        tx_count = summary.get("transaction_count", 0) or 0
        per_cat = summary.get("per_category") or []
        top_cat = summary.get("top_category")

        lines = []
        lines.append(f"📊 BÁO CÁO TÀI CHÍNH — {period_text or 'N/A'}")
        lines.append("")
        lines.append(f"• Tổng thu: {_fmt_amount(ti)}")
        lines.append(f"• Tổng chi: {_fmt_amount(te)}")
        lines.append(f"• Số giao dịch: {tx_count}")
        lines.append("")

        # Top categories visualization
        if per_cat:
            lines.append("Phân bổ theo danh mục (top 3):")
            top3 = per_cat[:3]
            max_val = top3[0]["total"] if top3 else 0
            for idx, c in enumerate(top3, start=1):
                name = c.get("category_name")
                val = c.get("total", 0)
                pct = (val / (te if te > 0 else (ti + te or 1))) * 100 if (ti + te) > 0 else 0
                bar = _make_bar(val, max_val, width=20)
                lines.append(f"{idx}. {name}: {_fmt_amount(val)} | {bar} {pct:.0f}%")
            lines.append("")

        if top_cat:
            lines.append(f"Danh mục nhiều nhất: {top_cat.get('category_name')} — {_fmt_amount(top_cat.get('total'))}")
        else:
            lines.append("Không có danh mục nổi bật.")

        # Simple deterministic observation
        if tx_count == 0:
            lines.append("")
            lines.append("Không có giao dịch phát sinh trong kỳ.")
        else:
            lines.append("")
            # expense ratio
            total = ti + te
            if total > 0:
                expense_ratio = (te / total) * 100
                lines.append(f"Tỷ lệ chi so với tổng: {expense_ratio:.0f}%.")
                if expense_ratio > 70:
                    lines.append("Khuyến nghị: Chi tiêu cao trong kỳ — cân nhắc cắt giảm các khoản không thiết yếu.")
                elif expense_ratio < 30 and ti > 0:
                    lines.append("Khuyến nghị: Tỉ lệ tiết kiệm tốt — tiếp tục duy trì.")
            else:
                lines.append("Không có dữ liệu tài chính hữu ích để phân tích.")

        lines.append("")
        lines.append("— Kết thúc báo cáo —")
        return "\n".join(lines)

    # Try LLM generation with one retry and increased timeout on failure.
    generation_config = {"temperature": 0.2}
    try:
        resp = model.generate_content([prompt], generation_config=generation_config, request_options={"timeout": 20})
        text = getattr(resp, "text", "").strip()
        # Strip code fences
        if text.startswith("```"):
            text = text.strip("`\n ")
        visual = _format_summary_visual(summary, period_text)
        full_text = text + "\n\n" + visual
        return {"text": full_text, "used_fallback": False}
    except Exception as e:
        logger.warning("LLM generation failed on first attempt: %s. Retrying with longer timeout...", e)
        try:
            resp = model.generate_content([prompt], generation_config=generation_config, request_options={"timeout": 60})
            text = getattr(resp, "text", "").strip()
            if text.startswith("```"):
                text = text.strip("`\n ")
            visual = _format_summary_visual(summary, period_text)
            full_text = text + "\n\n" + visual
            return {"text": full_text, "used_fallback": False}
        except Exception as e2:
            logger.exception("LLM error while generating report (retry failed): %s", e2)
            # Fallback: deterministic template with a short user-visible note
            visual = _format_summary_visual(summary, period_text)
            note = "(Lưu ý: trình tạo ngôn ngữ không phản hồi, gửi báo cáo dạng văn bản cơ bản.)"
            return {"text": visual + "\n\n" + note, "used_fallback": True}


if __name__ == "__main__":
    # Example usage
    example_user_id = 2
    # Example: November 2025
    start = "2025-11-01"
    end = "2025-11-30"
    print(f"Querying summary for user_id={example_user_id}, {start} -> {end}")
    summary = get_summary(example_user_id, start, end)
    print("Summary data:", json.dumps(summary, ensure_ascii=False, indent=2))
    report_resp = generate_report(summary, period_text="2025-11-01 đến 2025-11-30")
    # report_resp is a dict {'text': str, 'used_fallback': bool}
    if isinstance(report_resp, dict):
        print("\nGenerated report:\n", report_resp.get("text"))
        if report_resp.get("used_fallback"):
            print("(Note: LLM fallback used - report is deterministic.)")
    else:
        # backward compatibility: if a plain string is returned
        print("\nGenerated report:\n", str(report_resp))
