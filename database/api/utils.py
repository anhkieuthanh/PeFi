from datetime import datetime, date
import re


def parse_bill_date(value):
    """Parse various incoming date formats into a date object.

    Accepts:
      - date/datetime objects (returned as date)
      - strings like 'YYYY-MM-DD', 'DD/MM/YYYY', 'DD-MM-YYYY', 'MM/DD/YYYY', '27 Sep 2025'

    Returns a datetime.date or raises ValueError.
    """
    if value is None:
        raise ValueError("bill_date is required")
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        val = value.strip()
        # remove commas and ordinal suffixes like '1st', '2nd', '3rd', '4th'
        val = val.replace(',', '')
        val = re.sub(r"(\d)(st|nd|rd|th)\b", r"\1", val, flags=re.IGNORECASE)

        # common formats to try (including month names)
        formats = [
            "%Y-%m-%d",
            "%d/%m/%Y",
            "%d-%m-%Y",
            "%m/%d/%Y",
            "%Y/%m/%d",
            "%d %b %Y",   # 27 Sep 2025
            "%d %B %Y",   # 27 September 2025
        ]
        for fmt in formats:
            try:
                return datetime.strptime(val, fmt).date()
            except ValueError:
                continue

        # try ISO with time
        try:
            return datetime.fromisoformat(val).date()
        except Exception:
            pass

        # fallback: try dateutil if installed (more flexible)
        try:
            from dateutil import parser as _parser
            return _parser.parse(val).date()
        except Exception:
            pass
    raise ValueError(f"Không thể phân tích bill_date: {value}")
