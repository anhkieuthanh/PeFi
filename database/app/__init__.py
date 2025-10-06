from flask import Flask

def create_app():
    app = Flask(__name__)

    from api.users import users_bp
    from api.bills import bills_bp
    from api.categories import categories_bp

    # Thêm tiền tố /api/v1 cho tất cả các route trong blueprint
    app.register_blueprint(users_bp, url_prefix='/api/v1')
    app.register_blueprint(bills_bp, url_prefix='/api/v1')
    app.register_blueprint(categories_bp, url_prefix='/api/v1')
    return app