"""
메인 애플리케이션 진입점
"""
from app import create_app, db
from app.models import User, Server, Notification, Project
from flask_login import LoginManager
import os

app = create_app()

# 로그인 매니저 설정
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'

@login_manager.user_loader
def load_user(user_id):
    """사용자 로더"""
    return User.query.get(int(user_id))

@app.route('/')
def index():
    """메인 페이지"""
    return render_template('index.html')

@app.route('/dashboard')
@login_required
def dashboard():
    """대시보드"""
    return render_template('dashboard.html')

@app.route('/servers')
@login_required
def servers():
    """서버 목록"""
    return render_template('servers/index.html')

@app.route('/admin')
@login_required
def admin():
    """관리자 페이지"""
    return render_template('admin/index.html')

if __name__ == '__main__':
    # 데이터베이스 테이블 생성
    with app.app_context():
        db.create_all()
    
    # 개발 서버 실행
    app.run(debug=True, host='0.0.0.0', port=5000) 