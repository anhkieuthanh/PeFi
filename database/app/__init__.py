# __init__.py

from flask import Flask, render_template, jsonify, request, send_from_directory
from flask_socketio import SocketIO
from pathlib import Path
from flask_cors import CORS
import datetime
import psycopg2
from collections import defaultdict
import math
import calendar

# --- Phần setup và import giữ nguyên ---

def create_app():
    # Ensure Flask can find templates at database/templates (sibling of app/)
    templates_dir = str(Path(__file__).resolve().parents[1] / 'templates')
    app = Flask(__name__, template_folder=templates_dir)
    socketio = SocketIO(app, cors_allowed_origins="*")
    app.config['socketio_instance'] = socketio
    CORS(app)

    # Register API blueprints
    from api.users import users_bp
    from api.bills import bills_bp
    app.register_blueprint(users_bp, url_prefix='/api/v1')
    app.register_blueprint(bills_bp, url_prefix='/api/v1')

    def _ensure_indexes_now():
        try:
            from app.database import connect_to_heroku_db
            conn = connect_to_heroku_db()
            if not conn:
                return
            cur = conn.cursor()
            cur.execute("CREATE INDEX IF NOT EXISTS idx_bills_user_date ON bills(user_id, bill_date DESC);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_bills_user_category ON bills(user_id, category_name);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_bills_user_type_date ON bills(user_id, category_type, bill_date DESC);")
            conn.commit()
            cur.close()
            conn.close()
        except Exception:
            pass
    # Run once at startup
    _ensure_indexes_now()

    @app.route('/')
    def index():
        return render_template('index.html')

    # Serve icon assets located under templates/icon (to reuse existing trash.png)
    @app.route('/icon/<path:filename>')
    def serve_icon(filename: str):
        icon_dir = Path(__file__).resolve().parents[1] / 'templates' / 'icon'
        return send_from_directory(icon_dir, filename)

    @app.route('/dashboard_data')
    def dashboard_data():
        timeframe = request.args.get('timeframe', '1M')
        user_id = request.args.get('user_id')
        page = int(request.args.get('page', '1'))
        page_size = int(request.args.get('page_size', '10'))
        if not user_id:
            return jsonify({"error": "Thiếu user_id"}), 400

        end_date = datetime.date.today()
        start_date = end_date
        tf_upper = str(timeframe).upper()
        if tf_upper == 'ALL':
            start_date = datetime.date(1970, 1, 1)
        else:
            unit = timeframe[-1].upper()
            value = int(timeframe[:-1])
            def _sub_months(d: datetime.date, months: int) -> datetime.date:
                total = d.year * 12 + (d.month - 1) - months
                y = total // 12
                m = total % 12 + 1
                last_day = calendar.monthrange(y, m)[1]
                day = min(d.day, last_day)
                return datetime.date(y, m, day)
            if unit == 'W':
                start_date = end_date - datetime.timedelta(days=value * 7)
            elif unit == 'M':
                start_date = _sub_months(end_date, value)
            elif unit == 'Y':
                try:
                    start_date = end_date.replace(year=end_date.year - value)
                except ValueError:
                    start_date = end_date.replace(month=2, day=28, year=end_date.year - value)

        try:
            from app.database import connect_to_heroku_db
            conn = connect_to_heroku_db()
            if not conn:
                raise RuntimeError('Không thể kết nối DB')
            cursor = conn.cursor()

            # Timeseries thu/chi theo ngày (SQL)
            cursor.execute(
                """
                WITH days AS (
                  SELECT d::date AS day
                  FROM generate_series(%s::date, %s::date, interval '1 day') d
                )
                SELECT days.day,
                       COALESCE(SUM(CASE WHEN (b.category_type::text IN ('1','income')) THEN b.total_amount::float ELSE 0 END),0) AS income,
                       COALESCE(SUM(CASE WHEN (b.category_type::text IN ('0','expense')) THEN b.total_amount::float ELSE 0 END),0) AS expense
                FROM days
                LEFT JOIN bills b ON b.user_id = %s AND b.bill_date = days.day
                GROUP BY days.day
                ORDER BY days.day;
                """,
                (start_date, end_date, user_id)
            )
            ts_rows = cursor.fetchall()
            all_days_str = [r[0].strftime('%Y-%m-%d') for r in ts_rows]
            timeseries_income = [float(r[1]) for r in ts_rows]
            timeseries_expense = [float(r[2]) for r in ts_rows]
            total_income = float(sum(timeseries_income))
            total_expense = float(sum(timeseries_expense))

            # Tổng theo danh mục (expense)
            cursor.execute(
                """
                SELECT category_name, SUM(total_amount)::float AS amount
                FROM bills
                WHERE user_id = %s AND bill_date BETWEEN %s AND %s
                  AND category_type::text IN ('0','expense')
                GROUP BY category_name
                ORDER BY amount DESC;
                """,
                (user_id, start_date, end_date)
            )
            by_category_rows = cursor.fetchall()
            by_category = [{"category": r[0], "amount": float(r[1])} for r in by_category_rows if r[0] is not None]

            # Category timeseries (expense)
            cursor.execute(
                """
                SELECT b.category_name, d.day::date AS day, COALESCE(SUM(b.total_amount)::float, 0) AS amount
                FROM generate_series(%s::date, %s::date, interval '1 day') d(day)
                LEFT JOIN bills b
                  ON b.user_id=%s AND b.bill_date=d.day
                 AND b.category_type::text IN ('0','expense')
                GROUP BY b.category_name, d.day
                ORDER BY b.category_name, d.day;
                """,
                (start_date, end_date, user_id)
            )
            cat_ts_rows = cursor.fetchall()
            cat_map = defaultdict(lambda: {day: 0.0 for day in all_days_str})
            for cat, day, amt in cat_ts_rows:
                if cat is None:
                    continue
                day_str = day.strftime('%Y-%m-%d')
                cat_map[cat][day_str] = float(amt)
            category_datasets = [
                {"label": cat, "data": [cat_map[cat][d] for d in all_days_str]}
                for cat in sorted(cat_map.keys())
            ]

            # Transactions pagination tại DB
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM bills
                WHERE user_id=%s AND bill_date BETWEEN %s AND %s;
                """,
                (user_id, start_date, end_date)
            )
            row = cursor.fetchone()
            total_items = int(row[0]) if row and row[0] is not None else 0
            total_pages = max(1, math.ceil(total_items / page_size))
            offset = (page - 1) * page_size

            cursor.execute(
                """
                SELECT bill_id, bill_date::date, merchant_name, category_name, total_amount::float, category_type::text
                FROM bills
                WHERE user_id=%s AND bill_date BETWEEN %s AND %s
                ORDER BY bill_date DESC, bill_id DESC
                LIMIT %s OFFSET %s;
                """,
                (user_id, start_date, end_date, page_size, offset)
            )
            tx_rows = cursor.fetchall()
            transactions_for_fe = [
                {
                    "id": int(r[0]),
                    "date": r[1].strftime('%Y-%m-%d'),
                    "merchant": r[2],
                    "category": r[3],
                    "amount": float(r[4]),
                    "type": ('income' if str(r[5]).strip().lower() in ('1','income') else 'expense')
                } for r in tx_rows
            ]

            cursor.close()
            conn.close()

            return jsonify({
                'monthly': {'income': total_income, 'expense': total_expense},
                'timeseries': {'labels': all_days_str, 'income': timeseries_income, 'expense': timeseries_expense},
                'category_timeseries': {'labels': all_days_str, 'datasets': category_datasets},
                'by_category': by_category,
                'transactions': transactions_for_fe,
                'pagination': {
                    'page': page,
                    'page_size': page_size,
                    'total_items': total_items,
                    'total_pages': total_pages
                }
            })
        except Exception as e:
            app.logger.exception('Lỗi dashboard_data, trả về dữ liệu mẫu (fallback)')
            delta = end_date - start_date
            all_days = [(start_date + datetime.timedelta(days=i)) for i in range(max(0, delta.days) + 1)]
            all_days_str = [d.strftime('%Y-%m-%d') for d in all_days]
            income_series = [(i % 5) * 100000 for i in range(len(all_days_str))]
            expense_series = [((i+2) % 5) * 80000 for i in range(len(all_days_str))]
            total_income = sum(income_series)
            total_expense = sum(expense_series)
            by_category = [
                {"category": "Ăn uống", "amount": 350000},
                {"category": "Di chuyển", "amount": 240000},
                {"category": "Giải trí", "amount": 180000},
            ]
            transactions_for_fe = []
            for i in range(min(10, len(all_days_str))):
                transactions_for_fe.append({
                    "date": all_days_str[-(i+1)] if all_days_str else datetime.date.today().strftime('%Y-%m-%d'),
                    "merchant": ["Cafe", "Grab", "Cinema"][i % 3],
                    "category": ["Ăn uống", "Di chuyển", "Giải trí"][i % 3],
                    "amount": float([102000, 300000, 200000][i % 3]),
                    "type": "expense"
                })
            category_datasets = []
            for cat in ["Ăn uống", "Di chuyển", "Giải trí"]:
                category_datasets.append({
                    "label": cat,
                    "data": [v if (j % 3) == (0 if cat=="Ăn uống" else 1 if cat=="Di chuyển" else 2) else 0 for j, v in enumerate(expense_series)]
                })
            total_items = len(transactions_for_fe)
            total_pages = 1
            return jsonify({
                'monthly': {'income': total_income, 'expense': total_expense},
                'timeseries': {'labels': all_days_str, 'income': income_series, 'expense': expense_series},
                'category_timeseries': {'labels': all_days_str, 'datasets': category_datasets},
                'by_category': by_category,
                'transactions': transactions_for_fe,
                'pagination': {
                    'page': 1,
                    'page_size': 10,
                    'total_items': total_items,
                    'total_pages': total_pages
                }
            })

    return app