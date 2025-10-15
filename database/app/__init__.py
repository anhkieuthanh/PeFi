# __init__.py

from flask import Flask, render_template, jsonify, request
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
    CORS(app) # Cho phép CORS để frontend có thể gọi

    # Đăng ký các blueprint API (nếu bạn vẫn muốn dùng CRUD riêng)
    from api.users import users_bp
    from api.bills import bills_bp
    app.register_blueprint(users_bp, url_prefix='/api/v1')
    app.register_blueprint(bills_bp, url_prefix='/api/v1')

    @app.route('/')
    def index():
        # Serve the dashboard page
        return render_template('index.html')

    @app.route('/dashboard_data')
    def dashboard_data():
        """
        Endpoint tổng hợp dữ liệu, được điều chỉnh để hoạt động với timeframe.
        """
        # --- THAY ĐỔI 1: Lấy timeframe và user_id từ request ---
        timeframe = request.args.get('timeframe', '1M') # Mặc định là 1 tháng
        user_id = request.args.get('user_id')
        page = int(request.args.get('page', '1'))
        page_size = int(request.args.get('page_size', '10'))

        if not user_id:
            return jsonify({"error": "Thiếu user_id"}), 400

        # --- THAY ĐỔI 2: Tính toán ngày bắt đầu/kết thúc từ timeframe ---
        end_date = datetime.date.today()
        start_date = end_date
        tf_upper = str(timeframe).upper()
        if tf_upper == 'ALL':
            # Cover all historical data
            start_date = datetime.date(1970, 1, 1)
            unit = 'A'
            value = 0
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
                # Handle Feb 29 on non-leap year
                start_date = end_date.replace(month=2, day=28, year=end_date.year - value)

        try:
            from app.database import connect_to_heroku_db
            conn = connect_to_heroku_db()
            if not conn:
                raise RuntimeError('Không thể kết nối DB')

            cursor = conn.cursor()

            # Query tất cả giao dịch, lấy category_type từ bảng categories nếu có
            sql_all_tx = """
                SELECT 
                    b.bill_date::date AS bill_date,
                    b.total_amount::float AS total_amount,
                    COALESCE(c.category_type,
                        CASE WHEN lower(b.category_name) LIKE '%thu%'
                               OR lower(b.category_name) LIKE '%income%'
                               OR lower(b.category_name) LIKE '%salary%'
                             THEN 'income' ELSE 'expense' END
                    ) AS category_type,
                    b.category_name,
                    b.merchant_name
                FROM bills b
                LEFT JOIN categories c
                  ON c.user_id = b.user_id AND c.category_name = b.category_name
                WHERE b.user_id = %s AND b.bill_date BETWEEN %s AND %s
                ORDER BY b.bill_date DESC;
            """
            try:
                cursor.execute(sql_all_tx, (user_id, start_date, end_date))
            except Exception:
                # Fallback if categories table is missing; select from bills only
                cursor.execute(
                    """
                    SELECT b.bill_date::date,
                           b.total_amount::float,
                           b.category_type,
                           b.category_name,
                           b.merchant_name
                    FROM bills b
                    WHERE b.user_id = %s AND b.bill_date BETWEEN %s AND %s
                    ORDER BY b.bill_date DESC;
                    """,
                    (user_id, start_date, end_date),
                )
                rows = cursor.fetchall()
                transactions_as_dict = []
                for r in rows:
                    cat_type = r[2]
                    cat = r[3]
                    # normalize type from fallback (could be '1'/'0', 1/0, income/expense)
                    def _norm(v):
                        if v in (1, '1', True): return 'income'
                        if v in (0, '0', False): return 'expense'
                        s = (str(v).strip().lower() if v is not None else '')
                        if s in ('income','thu','thu nhập','thu nhap','in'): return 'income'
                        if s in ('expense','chi','chi tiêu','chi tieu','out'): return 'expense'
                        return 'expense'
                    norm_type = _norm(cat_type)
                    transactions_as_dict.append({
                        'bill_date': r[0],
                        'total_amount': float(r[1]),
                        'category_type': norm_type,
                        'category_name': cat,
                        'merchant_name': r[4],
                    })
            else:
                rows = cursor.fetchall()
                if cursor.description is None:
                    # Unexpected, but guard anyway
                    transactions_as_dict = [
                        {
                            'bill_date': r[0],
                            'total_amount': float(r[1]),
                            'category_type': r[2],
                            'category_name': r[3],
                            'merchant_name': r[4],
                        } for r in rows
                    ]
                else:
                    cols = [desc[0] for desc in cursor.description]
                    transactions_as_dict = [dict(zip(cols, row)) for row in rows]

            # Chuẩn hóa category_type: DB có thể trả về 1/0, True/False hoặc 'income'/'expense'
            def _normalize_type(v):
                if v in (1, '1', True):
                    return 'income'
                if v in (0, '0', False):
                    return 'expense'
                s = (str(v).strip().lower() if v is not None else '')
                if s in ('income', 'thu', 'thu nhập', 'thu nhap', 'in'):
                    return 'income'
                if s in ('expense', 'chi', 'chi tiêu', 'chi tieu', 'out'):
                    return 'expense'
                # Mặc định coi là expense nếu không xác định rõ
                return 'expense'

            for tx in transactions_as_dict:
                tx['category_type'] = _normalize_type(tx.get('category_type'))

            # --- Bắt đầu tính toán, tổng hợp dữ liệu ---

            # 1. Tổng thu/chi trong kỳ
            total_income = sum(tx['total_amount'] for tx in transactions_as_dict if tx['category_type'] == 'income')
            total_expense = sum(tx['total_amount'] for tx in transactions_as_dict if tx['category_type'] == 'expense')

            # 2. Dữ liệu Timeseries tổng hợp (tsChart)
            delta = end_date - start_date
            all_days = [(start_date + datetime.timedelta(days=i)) for i in range(delta.days + 1)]
            all_days_str = [d.strftime("%Y-%m-%d") for d in all_days]

            daily_totals = defaultdict(lambda: {'income': 0.0, 'expense': 0.0})
            for tx in transactions_as_dict:
                tx_date_str = tx['bill_date'].strftime("%Y-%m-%d")
                daily_totals[tx_date_str][tx['category_type']] += float(tx['total_amount'])

            timeseries_income = [daily_totals[day]['income'] for day in all_days_str]
            timeseries_expense = [daily_totals[day]['expense'] for day in all_days_str]
            
            # --- THAY ĐỔI 3: Thêm logic để tạo 'category_timeseries' ---
            expense_tx = [tx for tx in transactions_as_dict if tx['category_type'] == 'expense']
            expense_categories = sorted(list({tx['category_name'] for tx in expense_tx}))
            
            category_daily_expense = {cat: defaultdict(float) for cat in expense_categories}
            for tx in expense_tx:
                tx_date_str = tx['bill_date'].strftime("%Y-%m-%d")
                category_daily_expense[tx['category_name']][tx_date_str] += float(tx['total_amount'])
                
            category_datasets = []
            for category in expense_categories:
                data_points = [category_daily_expense[category][day] for day in all_days_str]
                category_datasets.append({"label": category, "data": data_points})

            # 4. Tổng hợp theo danh mục (by_category)
            by_category_totals = defaultdict(float)
            for tx in expense_tx:
                by_category_totals[tx['category_name']] += float(tx['total_amount'])
            by_category = [{"category": name, "amount": amount} for name, amount in by_category_totals.items()]

            # 5. Dữ liệu bảng giao dịch (phân trang)
            total_items = len(transactions_as_dict)
            total_pages = math.ceil(total_items / page_size)
            start_index = (page - 1) * page_size
            end_index = start_index + page_size
            paginated_tx = transactions_as_dict[start_index:end_index]
            
            transactions_for_fe = [
                {
                    "date": tx['bill_date'].strftime("%Y-%m-%d"),
                    "merchant": tx['merchant_name'],
                    "category": tx['category_name'],
                    "amount": float(tx['total_amount']),
                    "type": tx['category_type']
                } for tx in paginated_tx
            ]
            
            cursor.close()
            conn.close()

            # --- THAY ĐỔI 4: Thêm 'category_timeseries' vào JSON trả về ---
            return jsonify({
                'monthly': {'income': total_income, 'expense': total_expense},
                'timeseries': {'labels': all_days_str, 'income': timeseries_income, 'expense': timeseries_expense},
                'category_timeseries': {'labels': all_days_str, 'datasets': category_datasets}, # ĐÃ THÊM
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
            # Fallback/sample data when DB not available or any error occurs
            app.logger.exception('Lỗi dashboard_data, trả về dữ liệu mẫu (fallback)')
            # build sample labels according to timeframe window
            delta = end_date - start_date
            all_days = [(start_date + datetime.timedelta(days=i)) for i in range(max(0, delta.days) + 1)]
            all_days_str = [d.strftime('%Y-%m-%d') for d in all_days]
            # simple saw pattern for demo
            income_series = [(i % 5) * 100000 for i in range(len(all_days_str))]
            expense_series = [((i+2) % 5) * 80000 for i in range(len(all_days_str))]
            total_income = sum(income_series)
            total_expense = sum(expense_series)
            by_category = [
                {"category": "Ăn uống", "amount": 350000},
                {"category": "Di chuyển", "amount": 240000},
                {"category": "Giải trí", "amount": 180000},
            ]
            # few sample transactions
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