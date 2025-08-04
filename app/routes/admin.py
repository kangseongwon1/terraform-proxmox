"""
관리자 관련 라우트
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app.models.user import User, UserPermission
from app.services.notification_service import NotificationService
from app import db
import logging

logger = logging.getLogger(__name__)

bp = Blueprint('admin', __name__, url_prefix='/admin')

def admin_required(f):
    """관리자 권한 데코레이터"""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('관리자 권한이 필요합니다.', 'error')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

@bp.route('/')
@login_required
@admin_required
def index():
    """관리자 대시보드"""
    return render_template('admin/index.html')

@bp.route('/users')
@login_required
@admin_required
def users():
    """사용자 관리"""
    users = User.query.all()
    return render_template('admin/users.html', users=users)

@bp.route('/users', methods=['POST'])
@login_required
@admin_required
def create_user():
    """새 사용자 생성"""
    username = request.form.get('username')
    password = request.form.get('password')
    name = request.form.get('name')
    email = request.form.get('email')
    role = request.form.get('role', 'developer')
    
    if not username or not password:
        flash('사용자명과 비밀번호는 필수입니다.', 'error')
        return redirect(url_for('admin.users'))
    
    if User.query.filter_by(username=username).first():
        flash('이미 존재하는 사용자명입니다.', 'error')
        return redirect(url_for('admin.users'))
    
    try:
        user = User(
            username=username,
            name=name,
            email=email,
            role=role,
            is_active=True
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        
        flash('사용자가 생성되었습니다.', 'success')
    except Exception as e:
        logger.error(f"사용자 생성 실패: {e}")
        flash('사용자 생성 중 오류가 발생했습니다.', 'error')
        db.session.rollback()
    
    return redirect(url_for('admin.users'))

@bp.route('/users/<int:user_id>', methods=['DELETE'])
@login_required
@admin_required
def delete_user(user_id):
    """사용자 삭제"""
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': '사용자를 찾을 수 없습니다.'}), 404
    
    if user.username == 'admin':
        return jsonify({'error': '관리자 계정은 삭제할 수 없습니다.'}), 400
    
    try:
        db.session.delete(user)
        db.session.commit()
        return jsonify({'message': '사용자가 삭제되었습니다.'})
    except Exception as e:
        logger.error(f"사용자 삭제 실패: {e}")
        db.session.rollback()
        return jsonify({'error': '사용자 삭제 중 오류가 발생했습니다.'}), 500

@bp.route('/users/<int:user_id>/permissions', methods=['POST'])
@login_required
@admin_required
def update_user_permissions(user_id):
    """사용자 권한 업데이트"""
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': '사용자를 찾을 수 없습니다.'}), 404
    
    permissions = request.json.get('permissions', [])
    
    try:
        user.set_permissions(permissions)
        return jsonify({'message': '권한이 업데이트되었습니다.'})
    except Exception as e:
        logger.error(f"권한 업데이트 실패: {e}")
        return jsonify({'error': '권한 업데이트 중 오류가 발생했습니다.'}), 500

@bp.route('/users/<int:user_id>/role', methods=['POST'])
@login_required
@admin_required
def update_user_role(user_id):
    """사용자 역할 업데이트"""
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': '사용자를 찾을 수 없습니다.'}), 404
    
    role = request.json.get('role')
    if not role:
        return jsonify({'error': '역할이 필요합니다.'}), 400
    
    try:
        user.role = role
        db.session.commit()
        return jsonify({'message': '역할이 업데이트되었습니다.'})
    except Exception as e:
        logger.error(f"역할 업데이트 실패: {e}")
        db.session.rollback()
        return jsonify({'error': '역할 업데이트 중 오류가 발생했습니다.'}), 500

@bp.route('/iam')
@login_required
@admin_required
def iam():
    """IAM 관리"""
    users = User.query.all()
    return render_template('admin/iam.html', users=users)

@bp.route('/iam/<int:user_id>/permissions', methods=['POST'])
@login_required
@admin_required
def iam_set_permissions(user_id):
    """IAM 권한 설정"""
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': '사용자를 찾을 수 없습니다.'}), 404
    
    permissions = request.json.get('permissions', [])
    
    try:
        user.set_permissions(permissions)
        return jsonify({'message': '권한이 설정되었습니다.'})
    except Exception as e:
        logger.error(f"IAM 권한 설정 실패: {e}")
        return jsonify({'error': '권한 설정 중 오류가 발생했습니다.'}), 500

@bp.route('/iam/<int:user_id>/role', methods=['POST'])
@login_required
@admin_required
def iam_set_role(user_id):
    """IAM 역할 설정"""
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': '사용자를 찾을 수 없습니다.'}), 404
    
    role = request.json.get('role')
    if not role:
        return jsonify({'error': '역할이 필요합니다.'}), 400
    
    try:
        user.role = role
        db.session.commit()
        return jsonify({'message': '역할이 설정되었습니다.'})
    except Exception as e:
        logger.error(f"IAM 역할 설정 실패: {e}")
        db.session.rollback()
        return jsonify({'error': '역할 설정 중 오류가 발생했습니다.'}), 500 