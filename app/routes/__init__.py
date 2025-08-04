"""
라우트 패키지
"""
from .main import bp as main_bp
from .auth import bp as auth_bp
from .admin import bp as admin_bp
from .servers import bp as servers_bp
from .api import bp as api_bp

# 블루프린트를 직접 import하여 app/__init__.py에서 사용할 수 있도록 함
main = main_bp
auth = auth_bp
admin = admin_bp
servers = servers_bp
api = api_bp

__all__ = ['main', 'auth', 'admin', 'servers', 'api']

def register_blueprints(app):
    """블루프린트 등록"""
    from app.routes import auth, admin, servers, api

    app.register_blueprint(auth)
    app.register_blueprint(admin)
    app.register_blueprint(servers)
    app.register_blueprint(api) 