import random
import datetime
from typing import List, Tuple

from app.database import connect_to_heroku_db

# Configuration
USER_ID = 2
USER_NAME = "User 2"
START_DATE = datetime.date(datetime.date.today().year, 9, 1)
END_DATE = datetime.date.today()

# Categories per prompts
EXPENSE_CATEGORIES: List[str] = [
    "Ăn uống", "Xe cộ", "Mua sắm", "Học tập", "Đầu tư", "Y tế", "Du lịch",
    "Điện", "Nước", "Mạng Internet", "Thuê Nhà", "Giải trí", "Thú cưng",
    "Dịch vụ", "Sửa chữa", "Quà tặng", "Chi tiêu khác"
]
INCOME_CATEGORIES: List[str] = [
    "Lương", "Tiền lãi đầu tư", "Tiền cho thuê nhà", "Thu nhập khác"
]

# Some merchant/name pools
MERCHANTS = {
    "Ăn uống": ["Highlands Coffee", "The Coffee House", "Phở 24", "Bún Chả", "KFC"],
    "Xe cộ": ["Grab", "Be", "Gara Thành Công", "VietinBank Fuel"],
    "Mua sắm": ["Shopee", "Lazada", "Tiki", "Circle K"],
    "Học tập": ["Udemy", "Coursera", "Nhà sách Fahasa"],
    "Đầu tư": ["SSI", "VNDIRECT", "TCBS"],
    "Y tế": ["Pharmacity", "Bệnh viện Q."],
    "Du lịch": ["Vietjet", "Bamboo Airways", "Agoda", "Booking.com"],
    "Điện": ["EVN"],
    "Nước": ["Cấp Nước"],
    "Mạng Internet": ["VNPT", "Viettel"],
    "Thuê Nhà": ["Chủ nhà"],
    "Giải trí": ["Netflix", "Spotify", "CGV"],
    "Thú cưng": ["Pet Mart"],
    "Dịch vụ": ["Thợ điện", "Bee Clean"],
    "Sửa chữa": ["Sửa xe", "Thợ sửa"],
    "Quà tặng": ["Hoa tươi", "Shopee"],
    "Chi tiêu khác": ["Payment"],

    # Income merchants
    "Lương": ["CÔNG TY ABC"],
    "Tiền lãi đầu tư": ["TCBS", "SSI"],
    "Tiền cho thuê nhà": ["Người thuê"],
    "Thu nhập khác": ["Payment"],
}

# Amount ranges per category (VND)
AMOUNT_RANGES = {
    # Expenses typical
    "Ăn uống": (30000, 250000),
    "Xe cộ": (15000, 200000),
    "Mua sắm": (50000, 3000000),
    "Học tập": (100000, 3000000),
    "Đầu tư": (100000, 5000000),
    "Y tế": (50000, 2000000),
    "Du lịch": (200000, 7000000),
    "Điện": (300000, 2000000),
    "Nước": (50000, 500000),
    "Mạng Internet": (150000, 500000),
    "Thuê Nhà": (2000000, 15000000),
    "Giải trí": (50000, 1000000),
    "Thú cưng": (50000, 1000000),
    "Dịch vụ": (50000, 1500000),
    "Sửa chữa": (100000, 3000000),
    "Quà tặng": (50000, 2000000),
    "Chi tiêu khác": (20000, 2000000),

    # Incomes typical
    "Lương": (15000000, 40000000),
    "Tiền lãi đầu tư": (50000, 3000000),
    "Tiền cho thuê nhà": (1000000, 10000000),
    "Thu nhập khác": (100000, 5000000),
}


def rand_amount(cat: str) -> int:
    lo, hi = AMOUNT_RANGES.get(cat, (50000, 2000000))
    return int(random.uniform(lo, hi)) // 1000 * 1000  # round to thousands


def ensure_user(conn, user_id: int, name: str):
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM users WHERE user_id=%s", (user_id,))
        if not cur.fetchone():
            cur.execute("INSERT INTO users(user_id, user_name) VALUES (%s, %s)", (user_id, name))
    conn.commit()


def delete_existing_range(conn, user_id: int, start: datetime.date, end: datetime.date):
    with conn.cursor() as cur:
        cur.execute("DELETE FROM bills WHERE user_id=%s AND bill_date BETWEEN %s AND %s", (user_id, start, end))
    conn.commit()


def pick_merchant(category: str) -> str:
    pool = MERCHANTS.get(category, ["Payment"])
    return random.choice(pool)


def seed_expenses_for_day(day: datetime.date) -> List[Tuple]:
    rows = []
    # 0-3 random expense transactions per day
    for _ in range(random.randint(0, 3)):
        cat = random.choice(EXPENSE_CATEGORIES)
        merchant = pick_merchant(cat)
        amount = rand_amount(cat)
        note = f"{cat} - {merchant}"
        rows.append((day, USER_ID, merchant, cat, '0', amount, note))
    return rows


def seed_incomes_for_month(day: datetime.date) -> List[Tuple]:
    # Generate incomes around certain days of month
    rows = []
    # Salary on 1st (or if day is the 1st)
    if day.day == 1:
        cat = "Lương"
        rows.append((day, USER_ID, pick_merchant(cat), cat, '1', rand_amount(cat), "Lương tháng"))
    # Rental on 5th
    if day.day == 5:
        cat = "Tiền cho thuê nhà"
        rows.append((day, USER_ID, pick_merchant(cat), cat, '1', rand_amount(cat), "Thu tiền thuê"))
    # Investment interest on 15th
    if day.day == 15:
        cat = "Tiền lãi đầu tư"
        rows.append((day, USER_ID, pick_merchant(cat), cat, '1', rand_amount(cat), "Lãi đầu tư"))
    # Other income occasionally on 20th
    if day.day == 20 and random.random() < 0.6:
        cat = "Thu nhập khác"
        rows.append((day, USER_ID, pick_merchant(cat), cat, '1', rand_amount(cat), "Thu khác"))
    return rows


def ensure_cover_all_categories(conn):
    """Insert at least one row for each category if missing in the seeded range."""
    with conn.cursor() as cur:
        # Build a set of categories already present in range
        cur.execute(
            """
            SELECT DISTINCT category_name FROM bills
            WHERE user_id=%s AND bill_date BETWEEN %s AND %s
            """,
            (USER_ID, START_DATE, END_DATE),
        )
        present = {r[0] for r in cur.fetchall()}
        missing_exp = [c for c in EXPENSE_CATEGORIES if c not in present]
        missing_inc = [c for c in INCOME_CATEGORIES if c not in present]

        rows = []
        if missing_exp:
            day = START_DATE + datetime.timedelta(days=1)
            for cat in missing_exp:
                rows.append((day, USER_ID, pick_merchant(cat), cat, '0', rand_amount(cat), f"Seed cover {cat}"))
        if missing_inc:
            day = START_DATE + datetime.timedelta(days=2)
            for cat in missing_inc:
                rows.append((day, USER_ID, pick_merchant(cat), cat, '1', rand_amount(cat), f"Seed cover {cat}"))
        if rows:
            cur.executemany(
                """
                INSERT INTO bills (bill_date, user_id, merchant_name, category_name, category_type, total_amount, note)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                rows,
            )
    conn.commit()


def main():
    random.seed(42)
    conn = connect_to_heroku_db()
    if not conn:
        raise RuntimeError("Cannot connect to DB. Please check DATABASE_URL in config or env.")

    ensure_user(conn, USER_ID, USER_NAME)
    delete_existing_range(conn, USER_ID, START_DATE, END_DATE)

    # Generate rows day by day
    current = START_DATE
    batch: List[Tuple] = []
    while current <= END_DATE:
        batch.extend(seed_expenses_for_day(current))
        batch.extend(seed_incomes_for_month(current))
        current += datetime.timedelta(days=1)

    with conn.cursor() as cur:
        if batch:
            cur.executemany(
                """
                INSERT INTO bills (bill_date, user_id, merchant_name, category_name, category_type, total_amount, note)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                batch,
            )
    conn.commit()

    ensure_cover_all_categories(conn)

    with conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM bills WHERE user_id=%s AND bill_date BETWEEN %s AND %s",
            (USER_ID, START_DATE, END_DATE),
        )
        row = cur.fetchone()
        total = row[0] if row and row[0] is not None else 0
    conn.close()
    print(f"Seeded {total} rows for user {USER_ID} from {START_DATE} to {END_DATE}")


if __name__ == "__main__":
    main()
