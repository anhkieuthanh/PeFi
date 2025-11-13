from typing import Any, Dict, List, Optional
import logging
import json
from datetime import date

try:
    # Prefer the project's config which reads config.yaml
    from src import config
except Exception:
    import config
try:
    # prompt helpers
    from src.utils.promt import get_prompt_path, read_promt_file
except Exception:
    from utils.promt import get_prompt_path, read_promt_file

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def get_summary(user_id: int, start_date: Optional[str], end_date: Optional[str], tx_type: str = "both") -> Dict[str, Any]:
    try:
        # import lazily to avoid import-time DB initialization
        try:
            from database.db_operations import get_transactions_summary as db_get_summary
        except Exception:
            # allow importing via package path when running from src/
            from src.database.db_operations import get_transactions_summary as db_get_summary

        summary = db_get_summary(user_id, start_date, end_date, tx_type)
        # ensure keys exist for downstream code
        if not summary or summary.get("error"):
            return {"error": "Database error when summarizing transactions"}

        # reporting module expects per_category and top_category; db helper now provides per_category
        return summary
    except Exception:
        logger.exception("Error delegating get_summary to db_operations")
        return {"error": "Internal error while preparing summary"}


def generate_report(summary: Dict[str, Any], period_text: str = "", tx_type: str = "both") -> Dict[str, Any]:
    # Build JSON context for the LLM. Also try to extract explicit start/end dates
    # from the period_text if available (format like 'YYYY-MM-DD đến YYYY-MM-DD').
    start_date = ""
    end_date = ""
    try:
        if isinstance(period_text, str) and "đến" in period_text:
            parts = [p.strip() for p in period_text.split("đến", 1)]
            if len(parts) == 2:
                start_date, end_date = parts[0], parts[1]
    except Exception:
        start_date = ""
        end_date = ""

    top_cat = summary.get("top_category") or {}
    top_cat_name = top_cat.get("category_name") if isinstance(top_cat, dict) else str(top_cat)
    top_cat_amount = top_cat.get("total") if isinstance(top_cat, dict) else None

    context = {
        "period": period_text,
        "start_date": start_date,
        "end_date": end_date,
        "total_income": summary.get("total_income", 0.0),
        "total_expense": summary.get("total_expense", 0.0),
        "transaction_count": summary.get("transaction_count", 0),
        "top_category": top_cat_name,
        "top_category_amount": top_cat_amount,
        "save_percentage": summary.get("save_percentage", 0.0),
        "daily_average_expense": summary.get("daily_average_expense", 0.0),
    }

    # Load prompt template and provide both placeholders used in the file.
    try:
        prompt_template = read_promt_file(get_prompt_path("report_generation.txt"))
    except Exception:
        # fallback simple template
        prompt_template = (
            "INPUT JSON:\n{INPUT_JSON}\n\n{TEMPLATE_FRAGMENT}\n\nProduce a concise Markdown report in Vietnamese."
        )

    # Provide a small template fragment depending on tx_type if needed; keep empty otherwise.
    template_fragment = ""
    if tx_type == "thu":
        template_fragment = "# Báo cáo thu"
    elif tx_type == "chi":
        template_fragment = "# Báo cáo chi"

    try:
        prompt = prompt_template.format(INPUT_JSON=json.dumps(context, ensure_ascii=False), TEMPLATE_FRAGMENT=template_fragment)
    except Exception:
        # If formatting fails, fallback to injecting only the JSON
        prompt = prompt_template.replace("{INPUT_JSON}", json.dumps(context, ensure_ascii=False))

    # Use project's Gemini model helper
    model = config.get_text_model()

    # Try LLM generation with one retry and increased timeout on failure.
    generation_config = {"temperature": 0.2}
    try:
        resp = model.generate_content([prompt], generation_config=generation_config, request_options={"timeout": 20})
        text = getattr(resp, "text", "").strip()
        return {"text": text, "used_fallback": False}
    except Exception:
        logger.exception("LLM generation failed; falling back to deterministic report")

    # Fallback deterministic report (basic Markdown) with two algorithmic tips
    ti = context.get("total_income", 0.0) or 0.0
    te = context.get("total_expense", 0.0) or 0.0
    tx_count = context.get("transaction_count", 0) or 0
    save_pct = context.get("save_percentage", 0.0) or 0.0
    daily_avg = context.get("daily_average_expense", 0.0) or 0.0
    
    lines = []
    lines.append(f"# Báo cáo tài chính — {context.get('period') or 'N/A'}")
    lines.append("")
    lines.append(f"- Tổng thu: {int(ti):,} VND")
    lines.append(f"- Tổng chi: {int(te):,} VND")
    lines.append(f"- Chênh lệch: {int(ti - te):,} VND")
    lines.append(f"- Số giao dịch: {tx_count}")
    lines.append(f"- Tỉ lệ tiết kiệm: {int(save_pct)}%")
    lines.append(f"- Trung bình chi/ngày: {int(daily_avg):,} VND")
    
    if top_cat_name:
        if top_cat_amount:
            lines.append(f"- Danh mục nhiều nhất: {top_cat_name} — {int(top_cat_amount):,} VND")
        else:
            lines.append(f"- Danh mục nhiều nhất: {top_cat_name}")

    # Simple heuristic tips
    tips = []
    total = ti + te
    if total > 0:
        if save_pct < 10:
            tips.append("• Xem xét giảm các khoản chi không thiết yếu để tăng tỉ lệ tiết kiệm; bắt đầu bằng việc đặt giới hạn cho danh mục chi lớn.")
        else:
            tips.append("• Duy trì thói quen tiết kiệm hiện tại và cân nhắc tự động chuyển một phần tiền sang quỹ tiết kiệm hàng tháng.")
    else:
        tips.append("• Không đủ dữ liệu tài chính để đưa ra khuyến nghị cụ thể. Hãy ghi chép thêm giao dịch để có phân tích chính xác hơn.")

    # second tip: if a single category dominates
    if top_cat_amount and te > 0 and (top_cat_amount / te) > 0.5:
        tips.append(f"• Danh mục '{top_cat_name}' chiếm phần lớn chi tiêu; xem xét rà soát và cắt giảm các khoản trong danh mục này.")
    else:
        tips.append("• Theo dõi chi tiêu đều đặn hàng tuần để phát hiện biến động và điều chỉnh kịp thời.")

    lines.append("")
    lines.append("## Lời khuyên")
    for t in tips[:2]:
        lines.append(t)  # Tips already have bullets

    return {"text": "\n".join(lines), "used_fallback": True}

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
