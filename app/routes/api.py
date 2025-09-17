"""
API 전용 라우트 블루프린트
"""
from flask import Blueprint, request, jsonify, current_app, send_from_directory
from flask_login import login_required, current_user
from app.models import User, Server, UserPermission
from app.services import ProxmoxService, TerraformService, AnsibleService
from app.routes.auth import permission_required
import json
import os
import subprocess
import threading
import time
import uuid
import logging
from datetime import datetime

# 로거 설정
logger = logging.getLogger(__name__)

bp = Blueprint('api', __name__, url_prefix='/api')

@bp.route('/users', methods=['GET'])
@login_required
def get_users_compat():
    """사용자 목록 조회 (호환성)"""
    try:
        from app.routes.admin import get_users
        return get_users()
    except Exception as e:
        logger.error(f"/users 호환성 엔드포인트 오류: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/users', methods=['POST'])
@login_required
def create_user_compat():
    """사용자 생성 (호환성)"""
    try:
        from app.routes.admin import create_user
        return create_user()
    except Exception as e:
        logger.error(f"/users POST 호환성 엔드포인트 오류: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/current-user', methods=['GET'])
@login_required
def get_current_user_compat():
    """현재 사용자 정보 조회 (호환성)"""
    try:
        from app.routes.admin import get_current_user
        return get_current_user()
    except Exception as e:
        logger.error(f"/current-user 호환성 엔드포인트 오류: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/profile/api', methods=['GET'])
@login_required
def get_profile_api_compat():
    """프로필 정보 API (호환성)"""
    try:
        from flask_login import current_user
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
        logger.error(f"/profile/api 호환성 엔드포인트 오류: {str(e)}")
        return jsonify({'error': str(e)}), 500

# notification 관련 엔드포인트들은 notification.py로 이동됨
# @bp.route('/notifications', methods=['GET'])
# @bp.route('/notifications/<int:notification_id>/read', methods=['POST'])
# @bp.route('/notifications/unread-count', methods=['GET'])
# @bp.route('/notifications/<int:notification_id>/delete', methods=['POST'])
# @bp.route('/notifications/clear-all', methods=['POST'])

@bp.route('/firewall/groups', methods=['GET'])
@login_required
def get_firewall_groups_compat():
    """방화벽 그룹 목록 조회 (호환성)"""
    try:
        from app.routes.firewall import get_firewall_groups
        return get_firewall_groups()
    except Exception as e:
        logger.error(f"방화벽 그룹 조회 오류: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/admin/iam', methods=['GET'])
@login_required
def admin_iam_compat():
    """관리자 IAM (호환성)"""
    try:
        from app.routes.admin import admin_iam_api
        return admin_iam_api()
    except Exception as e:
        logger.error(f"관리자 IAM 호환성 엔드포인트 오류: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/users/<username>', methods=['DELETE'])
@login_required
def delete_user_compat(username):
    """사용자 삭제 (호환성)"""
    try:
        from app.routes.admin import delete_user
        return delete_user(username)
    except Exception as e:
        logger.error(f"사용자 삭제 호환성 엔드포인트 오류: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/users/<username>/password', methods=['POST'])
@login_required
def change_user_password_compat(username):
    """사용자 비밀번호 변경 (호환성)"""
    try:
        from app.routes.admin import change_user_password
        return change_user_password(username)
    except Exception as e:
        logger.error(f"사용자 비밀번호 변경 호환성 엔드포인트 오류: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/admin/iam/<username>/permissions', methods=['POST'])
@login_required
def update_user_permissions_compat(username):
    """사용자 권한 업데이트 (호환성)"""
    try:
        from app.routes.admin import admin_iam_set_permissions
        return admin_iam_set_permissions(username)
    except Exception as e:
        logger.error(f"사용자 권한 업데이트 호환성 엔드포인트 오류: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/firewall/assign_bulk', methods=['POST'])
@login_required
def assign_security_groups_bulk_compat():
    """일괄 보안그룹 할당 (호환성)"""
    try:
        from app.routes.servers import assign_security_groups_bulk
        return assign_security_groups_bulk()
    except Exception as e:
        logger.error(f"일괄 보안그룹 할당 호환성 엔드포인트 오류: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/assign_firewall_group/<server_name>', methods=['POST'])
@login_required
def assign_firewall_group_compat(server_name):
    """방화벽 그룹 할당 (호환성)"""
    try:
        from app.routes.firewall import assign_firewall_group
        return assign_firewall_group(server_name)
    except Exception as e:
        logger.error(f"방화벽 그룹 할당 호환성 엔드포인트 오류: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/remove_firewall_group/<server_name>', methods=['POST'])
@login_required
def remove_firewall_group_compat(server_name):
    """방화벽 그룹 제거 (호환성)"""
    try:
        from app.routes.firewall import remove_firewall_group
        return remove_firewall_group(server_name)
    except Exception as e:
        logger.error(f"방화벽 그룹 제거 호환성 엔드포인트 오류: {str(e)}")
        return jsonify({'error': str(e)}), 500


@bp.route('/favicon.ico')
def favicon():
    """파비콘"""
    return send_from_directory('static', 'favicon.ico')

@bp.route('/api/debug/user-info', methods=['GET'])
@login_required
def debug_user_info_compat():
    """디버깅용 사용자 정보 (호환성)"""
    try:
        from app.routes.admin import debug_user_info
        return debug_user_info()
    except Exception as e:
        logger.error(f"/debug/user-info 호환성 엔드포인트 오류: {str(e)}")
        return jsonify({'error': str(e)}), 500


# 세션 관련 호환성 엔드포인트들
@bp.route('/session/check', methods=['GET'])
def check_session_compat():
    """세션 상태 확인 (호환성)"""
    try:
        from app.routes.auth import check_session
        return check_session()
    except Exception as e:
        logger.error(f"세션 상태 확인 호환성 엔드포인트 오류: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/session/refresh', methods=['POST'])
@login_required
def refresh_session_compat():
    """세션 갱신 (호환성)"""
    try:
        from app.routes.auth import refresh_session
        return refresh_session()
    except Exception as e:
        logger.error(f"세션 갱신 호환성 엔드포인트 오류: {str(e)}")
        return jsonify({'error': str(e)}), 500 



        
 