"""
Proxmox Manager 실행 파일
"""
import os
import sys
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.main import app, db
from app.models import User, Server, Notification, Project
from flask_login import login_required
from flask import render_template

if __name__ == '__main__':
    # 데이터베이스 테이블 생성
    with app.app_context():
        db.create_all()
        
        # 기본 관리자 계정 생성 (없는 경우)
        admin_user = User.query.filter_by(username='admin').first()
        if not admin_user:
            admin_user = User(
                username='admin',
                name='시스템 관리자',
                email='admin@dmcmedia.co.kr',
                role='admin',
                is_active=True
            )
            admin_user.set_password('admin123!')
            db.session.add(admin_user)
            
            # 관리자에게 모든 권한 부여
            admin_permissions = [
                'view_all', 'create_server', 'start_server', 'stop_server', 
                'reboot_server', 'delete_server', 'assign_roles', 'remove_roles', 
                'manage_users', 'view_logs', 'manage_roles', 'manage_storage', 
                'manage_network', 'assign_firewall_group', 'remove_firewall_group'
            ]
            
            for permission in admin_permissions:
                admin_user.add_permission(permission)
            
            db.session.commit()
            print("기본 관리자 계정이 생성되었습니다.")
            print("사용자명: admin")
            print("비밀번호: admin123!")
            print("⚠️  보안을 위해 비밀번호를 변경하세요!")
    
    # 개발 서버 실행
    print("🚀 Proxmox Manager 시작 중...")
    print("📱 웹 인터페이스: http://localhost:5000")
    print("🔑 기본 로그인: admin / admin123!")
    
    app.run(
        debug=True, 
        host='0.0.0.0', 
        port=5000,
        use_reloader=True
    ) 