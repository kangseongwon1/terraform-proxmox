"""
인증 관련 라우트
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
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
            
            return redirect(url_for('main.index'))
        else:
            # 로그인 실패 시 세션 정리
            session.pop('permissions', None)
            session.pop('user_role', None)
            session.pop('user_id', None)
            session.pop('username', None)
            
            # 실패 원인에 따른 구체적인 메시지
            if not user:
                error_msg = '존재하지 않는 사용자명입니다.'
            elif not user.check_password(password):
                error_msg = '비밀번호가 올바르지 않습니다.'
            elif not user.is_active:
                error_msg = '비활성화된 계정입니다.'
            else:
                error_msg = '잘못된 사용자명 또는 비밀번호입니다.'
            
            # JavaScript alert를 위한 세션에 오류 메시지 저장
            session['login_error'] = error_msg
    
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

@bp.route('/clear-login-error', methods=['POST'])
def clear_login_error():
    """로그인 오류 메시지 제거"""
    session.pop('login_error', None)
    return '', 204

@bp.route('/profile')
@login_required
def profile():
    """프로필 페이지"""
    return render_template('auth/profile.html', user=current_user)

@bp.route('/profile/api')
@login_required
def get_profile_api():
    """프로필 정보 API"""
    try:
        user_data = {
            'id': current_user.id,
            'username': current_user.username,
            'name': current_user.name or '',
            'email': current_user.email or '',
            'role': current_user.role,
            'is_active': current_user.is_active,
            'created_at': current_user.created_at.isoformat() if current_user.created_at else None,
            'last_login': current_user.last_login.isoformat() if current_user.last_login else None,
            'permissions': [perm.permission for perm in current_user.permissions]
        }
        return jsonify(user_data)
    except Exception as e:
        print(f"💥 프로필 API 오류: {str(e)}")
        return jsonify({'error': str(e)}), 500 