from flask import Flask, render_template, jsonify
from pathlib import Path
try:
    from src import config as app_config
except Exception:
    # Add project root to sys.path and retry
    import sys
    from pathlib import Path
    project_root = Path(__file__).resolve().parents[2]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    from src import config as app_config

def create_app():
    # ensure Flask knows where our templates live (templates/ is under database/)
    templates_dir = str(Path(__file__).resolve().parents[1] / 'templates')
    app = Flask(__name__, template_folder=templates_dir)

    # Validate configuration on startup
    app_config.validate_config()

    from api.users import users_bp
    from api.bills import bills_bp
    from api.categories import categories_bp

    # Thêm tiền tố /api/v1 cho tất cả các route trong blueprint
    app.register_blueprint(users_bp, url_prefix='/api/v1')
    app.register_blueprint(bills_bp, url_prefix='/api/v1')
    app.register_blueprint(categories_bp, url_prefix='/api/v1')

    # --- Minimal frontend routes (black & white Notion-like UI) ---
    @app.route('/')
    def index():
        return render_template('index.html')

    @app.route('/dashboard_data')
    def dashboard_data():
        """Return aggregated dashboard data.

        Query params supported:
        - start: YYYY-MM-DD (inclusive)
        - end: YYYY-MM-DD (inclusive)
        - type: income|expense|all
        - categories: comma-separated category names
        """
        from flask import request
        import datetime
        import psycopg2
        from typing import Any
        # Log request headers to help debug 403/requests
        try:
            app.logger.debug('dashboard_data request args: %s', request.args)
            app.logger.debug('dashboard_data headers: %s', dict(request.headers))
        except Exception:
            pass

        # parse params
        start = request.args.get('start')
        end = request.args.get('end')
        ttype = request.args.get('type', 'all')
        categories = request.args.get('categories')
        cats = [c.strip() for c in categories.split(',')] if categories else []
        # pagination
        try:
            page = max(1, int(request.args.get('page', '1')))
        except Exception:
            page = 1
        try:
            page_size = int(request.args.get('page_size', '10'))
        except Exception:
            page_size = 10
        page_size = max(1, min(100, page_size))
        offset = (page - 1) * page_size

        # default range: last 30 days
        if not end:
            end_date = datetime.date.today()
        else:
            end_date = datetime.date.fromisoformat(end)
        if not start:
            start_date = end_date - datetime.timedelta(days=29)
        else:
            start_date = datetime.date.fromisoformat(start)

        # Try to query the DB; if unavailable, return sample fallback
        try:
            from app.database import connect_to_heroku_db
            conn = connect_to_heroku_db()
            if not conn:
                raise RuntimeError('No DB')

            cur = conn.cursor()

            # by_category
            if cats:
                sql_by_cat = (
                    "SELECT category_name, SUM(total_amount) as amount "
                    "FROM bills WHERE bill_date::date BETWEEN %s AND %s AND category_name = ANY(%s) "
                    "GROUP BY category_name ORDER BY amount DESC LIMIT 20;"
                )
                params_by_cat = (start_date, end_date, cats)
            else:
                sql_by_cat = (
                    "SELECT category_name, SUM(total_amount) as amount "
                    "FROM bills WHERE bill_date::date BETWEEN %s AND %s "
                    "GROUP BY category_name ORDER BY amount DESC LIMIT 20;"
                )
                params_by_cat = (start_date, end_date)
            cur.execute(sql_by_cat, params_by_cat)
            by_cat_rows = cur.fetchall()
            by_category = [{'category': r[0], 'amount': float(r[1])} for r in by_cat_rows]

            # timeseries
            sql_ts = (
                "SELECT bill_date::date as day, "
                "SUM(CASE WHEN lower(category_name) LIKE %s OR lower(category_name) LIKE %s OR lower(category_name) LIKE %s THEN total_amount ELSE 0 END) AS income, "
                "SUM(CASE WHEN NOT (lower(category_name) LIKE %s OR lower(category_name) LIKE %s OR lower(category_name) LIKE %s) THEN total_amount ELSE 0 END) AS expense "
                "FROM bills WHERE bill_date::date BETWEEN %s AND %s "
                "GROUP BY day ORDER BY day;"
            )
            kw = ('%thu%', '%income%', '%salary%')
            params_ts = (kw[0], kw[1], kw[2], kw[0], kw[1], kw[2], start_date, end_date)
            cur.execute(sql_ts, params_ts)
            ts_rows = cur.fetchall()
            labels = [r[0].isoformat() for r in ts_rows]
            incomes = [float(r[1]) for r in ts_rows]
            expenses = [float(r[2]) for r in ts_rows]

            # transactions list with total count and pagination
            base_where = ["bill_date::date BETWEEN %s AND %s"]
            base_params: list[Any] = [start_date, end_date]
            if ttype in ('income','expense'):
                kw_parts = "(lower(category_name) LIKE %s OR lower(category_name) LIKE %s OR lower(category_name) LIKE %s)"
                if ttype == 'income':
                    base_where.append(kw_parts)
                else:
                    base_where.append("NOT " + kw_parts)
                base_params += ['%thu%', '%income%', '%salary%']
            if cats:
                base_where.append("category_name = ANY(%s)")
                base_params.append(tuple(cats))

            where_sql = " WHERE " + " AND ".join(base_where) if base_where else ""

            # total count for pagination
            sql_count = f"SELECT COUNT(*) FROM bills{where_sql};"
            cur.execute(sql_count, tuple(base_params))
            row = cur.fetchone() or (0,)
            total_count = int(row[0])

            sql_tx = (
                "SELECT bill_id, bill_date::date, merchant_name, category_name, total_amount::float FROM bills"
                f"{where_sql} ORDER BY bill_date DESC, bill_id DESC LIMIT %s OFFSET %s;"
            )
            params_tx = tuple(base_params + [page_size, offset])
            cur.execute(sql_tx, params_tx)
            tx_rows = cur.fetchall()
            transactions = []
            for r in tx_rows:
                cat = r[3]
                ttype_row = 'income' if any(k in (cat or '').lower() for k in ['thu','income','salary']) else 'expense'
                transactions.append({
                    'id': r[0],
                    'date': r[1].isoformat(),
                    'merchant': r[2],
                    'category': cat,
                    'amount': float(r[4]),
                    'type': ttype_row
                })

            # monthly totals
            total_income = sum(incomes)
            total_expense = sum(expenses)

            conn.close()

            return jsonify({
                'monthly': {'income': total_income, 'expense': total_expense},
                'by_category': by_category,
                'timeseries': {'labels': labels, 'income': incomes, 'expense': expenses},
                'transactions': transactions,
                'pagination': {
                    'page': page,
                    'page_size': page_size,
                    'total_count': total_count,
                    'total_pages': (total_count + page_size - 1) // page_size
                }
            })

        except Exception as e:
            # fallback/sample data when DB not available or error occurs
            app.logger.exception('dashboard_data: error querying DB, returning sample')
            sample = {
                "monthly": {"income": 2500000, "expense": 1850000},
                "by_category": [
                    {"category": "Ăn uống", "amount": 650000},
                    {"category": "Di chuyển", "amount": 300000},
                    {"category": "Giải trí", "amount": 200000},
                    {"category": "Mua sắm", "amount": 300000}
                ],
                "timeseries": {"labels": ["01","05","10","15","20","25","30"], "income": [200000,300000,250000,400000,300000,450000,450000], "expense": [150000,200000,180000,250000,200000,300000,520000]},
                "transactions": [
                    {"date":"2025-10-05","merchant":"LAC COFFEE","category":"Ăn uống","amount":102000,"type":"expense"},
                    {"date":"2025-10-04","merchant":"Salary","category":"Thu nhập","amount":2500000,"type":"income"},
                    {"date":"2025-10-03","merchant":"Grab","category":"Di chuyển","amount":300000,"type":"expense"},
                    {"date":"2025-10-02","merchant":"Cinema","category":"Giải trí","amount":200000,"type":"expense"}
                ]
            }
            # provide minimal pagination metadata for sample
            sample['pagination'] = {
                'page': 1,
                'page_size': len(sample.get('transactions', [])),
                'total_count': len(sample.get('transactions', [])),
                'total_pages': 1
            }
            return jsonify(sample)

    @app.route('/debug_headers', methods=['GET','POST'])
    def debug_headers():
        from flask import request
        hdrs = {k:v for k,v in request.headers.items()}
        return jsonify({'method': request.method, 'headers': hdrs, 'args': request.args}), 200

    @app.route('/ping')
    def ping():
        return 'ok', 200
    return app