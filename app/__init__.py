"""
Proxmox Manager Flask Application Factory
"""
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
import logging
import os
from logging.handlers import RotatingFileHandler

# 전역 객체들
db = SQLAlchemy()
login_manager = LoginManager()

def create_app(config_name='development'):
    """Flask 애플리케이션 팩토리"""
    app = Flask(__name__)
    
    # 설정 로드
    from config import config
    app.config.from_object(config[config_name])
    
    # 데이터베이스 초기화
    db.init_app(app)
    
    # 로그인 매니저 초기화
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = '이 페이지에 접근하려면 로그인이 필요합니다.'
    
    # 로깅 설정
    setup_logging(app)
    
    # 블루프린트 등록
    register_blueprints(app)
    
    # 에러 핸들러 등록
    register_error_handlers(app)
    
    # 보안 헤더 설정
    setup_security_headers(app)
    
    return app

def setup_logging(app):
    """로깅 설정"""
    if not app.debug and not app.testing:
        # 로그 디렉토리 생성
        if not os.path.exists('logs'):
            os.mkdir('logs')
        
        # 파일 핸들러 설정
        file_handler = RotatingFileHandler(
            'logs/proxmox_manager.log', 
            maxBytes=10240000, 
            backupCount=10
        )
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        
        app.logger.setLevel(logging.INFO)
        app.logger.info('Proxmox Manager startup')

def register_blueprints(app):
    """블루프린트 등록"""
    from app.routes import auth, admin, servers, api
    
    app.register_blueprint(auth.bp)
    app.register_blueprint(admin.bp)
    app.register_blueprint(servers.bp)
    app.register_blueprint(api.bp)

def register_error_handlers(app):
    """에러 핸들러 등록"""
    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('errors/404.html'), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return render_template('errors/500.html'), 500

def setup_security_headers(app):
    """보안 헤더 설정"""
    @app.after_request
    def add_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        return response 