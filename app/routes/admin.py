"""
관리자 관련 라우트
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app.models.user import User, UserPermission
from app.services.notification_service import NotificationService
from app.routes.auth import permission_required
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

# 사용자 관리 API
@bp.route('/api/users', methods=['GET'])
@permission_required('manage_users')
def get_users():
    """사용자 목록 조회 (기존 템플릿 호환)"""
    try:
        users = User.query.all()
        user_data = []
        for user in users:
            user_dict = {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'role': user.role,
                'is_admin': user.is_admin,
                'created_at': user.created_at.isoformat() if user.created_at else None
            }
            user_data.append(user_dict)
        
        return jsonify({'users': user_data})
    except Exception as e:
        print(f"💥 사용자 목록 조회 실패: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/current-user', methods=['GET'])
@login_required
def get_current_user():
    """현재 사용자 정보 조회"""
    try:
        user_data = {
            'id': current_user.id,
            'username': current_user.username,
            'name': current_user.name or '',
            'email': current_user.email or '',
            'role': current_user.role,
            'is_active': current_user.is_active,
            'is_admin': current_user.is_admin,  # 추가
            'created_at': current_user.created_at.isoformat() if current_user.created_at else None,
            'last_login': current_user.last_login.isoformat() if current_user.last_login else None,
            'permissions': [perm.permission for perm in current_user.permissions]
        }
        return jsonify(user_data)
    except Exception as e:
        print(f"💥 현재 사용자 정보 조회 실패: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/debug/user-info', methods=['GET'])
@login_required
def debug_user_info():
    """디버깅용 사용자 정보"""
    try:
        debug_info = {
            'user_id': current_user.id,
            'username': current_user.username,
            'role': current_user.role,
            'is_admin': current_user.is_admin,
            'is_authenticated': current_user.is_authenticated,
            'permissions_count': current_user.permissions.count(),
            'permissions_list': [perm.permission for perm in current_user.permissions],
            'has_manage_users': current_user.has_permission('manage_users') if hasattr(current_user, 'has_permission') else 'N/A'
        }
        return jsonify(debug_info)
    except Exception as e:
        print(f"💥 사용자 정보 디버깅 실패: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/users', methods=['POST'])
@permission_required('manage_users')
def create_user():
    """사용자 생성"""
    try:
        data = request.get_json()
        username = data.get('username')
        email = data.get('email')
        password = data.get('password')
        role = data.get('role', 'user')
        
        if not username or not email or not password:
            return jsonify({'error': '사용자명, 이메일, 비밀번호가 필요합니다.'}), 400
        
        # 사용자명 중복 확인
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            return jsonify({'error': '이미 존재하는 사용자명입니다.'}), 400
        
        # 새 사용자 생성
        from werkzeug.security import generate_password_hash
        new_user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password),
            role=role
        )
        
        from app import db
        db.session.add(new_user)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'사용자 {username}가 생성되었습니다.'
        })
        
    except Exception as e:
        print(f"💥 사용자 생성 실패: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/users/<username>/delete', methods=['POST'])
@permission_required('manage_users')
def delete_user(username):
    """사용자 삭제"""
    try:
        user = User.query.filter_by(username=username).first()
        if not user:
            return jsonify({'error': '사용자를 찾을 수 없습니다.'}), 404
        
        if user.is_admin:
            return jsonify({'error': '관리자는 삭제할 수 없습니다.'}), 400
        
        from app import db
        db.session.delete(user)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'사용자 {username}가 삭제되었습니다.'
        })
        
    except Exception as e:
        print(f"💥 사용자 삭제 실패: {str(e)}")
        return jsonify({'error': str(e)}), 500


@bp.route('/users', methods=['POST'])
@login_required
@admin_required
def create_user_form():
    """새 사용자 생성 (폼)"""
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

@bp.route('/api/admin/iam', methods=['GET'])
def admin_iam_api():
    """관리자 IAM API"""
    try:
        users = User.query.all()
        
        # 권한 목록을 중앙집중화된 설정에서 가져오기
        from app.permissions import get_all_permissions, get_permission_description
        all_permissions = get_all_permissions()
        
        # 권한 설명과 함께 반환
        permissions_with_descriptions = [
            {
                'name': perm,
                'description': get_permission_description(perm)
            }
            for perm in all_permissions
        ]
        
        user_data = []
        for user in users:
            user_permissions = [perm.permission for perm in user.permissions]
            user_data.append({
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'role': user.role,
                'permissions': user_permissions
            })
        
        return jsonify({
            'success': True,
            'users': user_data,
            'all_permissions': all_permissions,
            'permissions_with_descriptions': permissions_with_descriptions
        })
        
    except Exception as e:
        print(f"💥 관리자 IAM API 실패: {str(e)}")
        return jsonify({'error': str(e)}), 500


# 중복 라우트 제거 - admin_iam_set_permissions와 admin_iam_set_role을 사용

@bp.route('/iam')
@login_required
@admin_required
def iam():
    """IAM 관리"""
    users = User.query.all()
    return render_template('admin/iam.html', users=users)

@bp.route('/iam/<username>/permissions', methods=['POST'])
@login_required
@admin_required
def iam_set_permissions(username):
    """IAM 권한 설정"""
    user = User.query.filter_by(username=username).first()
    if not user:
        return jsonify({'error': '사용자를 찾을 수 없습니다.'}), 404
    
    permissions = request.json.get('permissions', [])
    
    try:
        user.set_permissions(permissions)
        return jsonify({'message': '권한이 설정되었습니다.'})
    except Exception as e:
        logger.error(f"IAM 권한 설정 실패: {e}")
        return jsonify({'error': '권한 설정 중 오류가 발생했습니다.'}), 500

@bp.route('/iam/<username>/role', methods=['POST'])
@login_required
@admin_required
def iam_set_role(username):
    """IAM 역할 설정"""
    user = User.query.filter_by(username=username).first()
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

@bp.route('/api/admin/iam/<username>/permissions', methods=['POST'])
def admin_iam_set_permissions(username):
    """사용자 권한 설정"""
    try:
        data = request.get_json()
        permissions = data.get('permissions', [])
        
        user = User.query.filter_by(username=username).first()
        if not user:
            return jsonify({'error': '사용자를 찾을 수 없습니다.'}), 404
        
        # 기존 권한 제거
        from app.models import UserPermission
        UserPermission.query.filter_by(user_id=user.id).delete()
        
        # 권한 유효성 검증
        from app.permissions import validate_permission
        invalid_permissions = [p for p in permissions if not validate_permission(p)]
        if invalid_permissions:
            return jsonify({'error': f'유효하지 않은 권한: {", ".join(invalid_permissions)}'}), 400
        
        # 새 권한 추가
        from app import db
        for permission in permissions:
            user_permission = UserPermission(user_id=user.id, permission=permission)
            db.session.add(user_permission)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'사용자 {username}의 권한이 업데이트되었습니다.'
        })
        
    except Exception as e:
        print(f"💥 사용자 권한 설정 실패: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/admin/iam/<username>/role', methods=['POST'])
def admin_iam_set_role(username):
    """사용자 역할 설정"""
    try:
        data = request.get_json()
        role = data.get('role')
        
        if not role:
            return jsonify({'error': '역할이 필요합니다.'}), 400
        
        user = User.query.filter_by(username=username).first()
        if not user:
            return jsonify({'error': '사용자를 찾을 수 없습니다.'}), 404
        
        user.role = role
        from app import db
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'사용자 {username}의 역할이 {role}로 변경되었습니다.'
        })
        
    except Exception as e:
        print(f"💥 사용자 역할 설정 실패: {str(e)}")
        return jsonify({'error': str(e)}), 500        

@bp.route('/api/users/<username>/password', methods=['POST'])
@login_required
@admin_required
def change_user_password(username):
    """사용자 비밀번호 변경"""
    try:
        data = request.get_json()
        new_password = data.get('new_password')
        confirm_password = data.get('confirm_password')
        
        if not new_password or not confirm_password:
            return jsonify({'error': '새 비밀번호와 확인을 입력해주세요.'}), 400
        
        if new_password != confirm_password:
            return jsonify({'error': '새 비밀번호가 일치하지 않습니다.'}), 400
        
        if len(new_password) < 6:
            return jsonify({'error': '새 비밀번호는 최소 6자 이상이어야 합니다.'}), 400
        
        user = User.query.filter_by(username=username).first()
        if not user:
            return jsonify({'error': '사용자를 찾을 수 없습니다.'}), 404
        
        # 비밀번호 해시 생성
        from werkzeug.security import generate_password_hash
        user.password_hash = generate_password_hash(new_password)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'사용자 {username}의 비밀번호가 변경되었습니다.'
        })
        
    except Exception as e:
        print(f"💥 사용자 비밀번호 변경 실패: {str(e)}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500        