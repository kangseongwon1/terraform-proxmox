"""
인증 관련 라우트
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from app.models.user import User
from app.services.notification_service import NotificationService
import logging

logger = logging.getLogger(__name__)

bp = Blueprint('auth', __name__, url_prefix='/auth')

@bp.route('/login', methods=['GET', 'POST'])
def login():
    """로그인"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if not username or not password:
            flash('사용자명과 비밀번호를 입력해주세요.', 'error')
            return render_template('auth/login.html')
        
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password) and user.is_active:
            login_user(user)
            user.update_user_login()
            
            # 세션에 권한 정보 추가
            permissions = [perm.permission for perm in user.permissions]
            session['permissions'] = permissions
            session['user_role'] = user.role
            session['user_id'] = user.id
            session['username'] = user.username
            
            # 로그인 알림 생성
            NotificationService.create_user_notification(
                user_id=user.id,
                title='로그인 성공',
                message=f'{user.username}님이 로그인했습니다.',
                severity='info'
            )
            
            flash('로그인되었습니다.', 'success')
            return redirect(url_for('main.index'))
        else:
            flash('잘못된 사용자명 또는 비밀번호입니다.', 'error')
    
    return render_template('auth/login.html')

@bp.route('/logout')
@login_required
def logout():
    """로그아웃"""
    logout_user()
    
    # 세션 정보 정리
    session.pop('permissions', None)
    session.pop('user_role', None)
    session.pop('user_id', None)
    session.pop('username', None)
    
    flash('로그아웃되었습니다.', 'info')
    return redirect(url_for('auth.login'))

@bp.route('/change-password', methods=['POST'])
@login_required
def change_password():
    """비밀번호 변경"""
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')
    
    if not current_password or not new_password or not confirm_password:
        flash('모든 필드를 입력해주세요.', 'error')
        return redirect(url_for('main.profile'))
    
    if new_password != confirm_password:
        flash('새 비밀번호가 일치하지 않습니다.', 'error')
        return redirect(url_for('main.profile'))
    
    if not current_user.check_password(current_password):
        flash('현재 비밀번호가 올바르지 않습니다.', 'error')
        return redirect(url_for('main.profile'))
    
    if len(new_password) < 8:
        flash('비밀번호는 최소 8자 이상이어야 합니다.', 'error')
        return redirect(url_for('main.profile'))
    
    try:
        current_user.set_password(new_password)
        from app import db
        db.session.commit()
        
        # 비밀번호 변경 알림
        NotificationService.create_user_notification(
            user_id=current_user.id,
            title='비밀번호 변경',
            message='비밀번호가 성공적으로 변경되었습니다.',
            severity='success'
        )
        
        flash('비밀번호가 변경되었습니다.', 'success')
    except Exception as e:
        logger.error(f"비밀번호 변경 실패: {e}")
        flash('비밀번호 변경 중 오류가 발생했습니다.', 'error')
    
    return redirect(url_for('main.profile'))

@bp.route('/profile')
@login_required
def profile():
    """프로필 페이지"""
    return render_template('auth/profile.html', user=current_user) 