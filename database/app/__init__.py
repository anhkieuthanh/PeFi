from flask import Flask
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
    app = Flask(__name__)

    # Validate configuration on startup
    app_config.validate_config()

    from api.users import users_bp
    from api.bills import bills_bp
    from api.categories import categories_bp

    # Thêm tiền tố /api/v1 cho tất cả các route trong blueprint
    app.register_blueprint(users_bp, url_prefix='/api/v1')
    app.register_blueprint(bills_bp, url_prefix='/api/v1')
    app.register_blueprint(categories_bp, url_prefix='/api/v1')
    return app