"""
API 전용 라우트 블루프린트
"""
from flask import Blueprint, request, jsonify, current_app, send_from_directory
from flask_login import login_required, current_user
from app.models import User, Server, Notification, UserPermission
from app.services import ProxmoxService, TerraformService, AnsibleService, NotificationService
from app.routes.auth import permission_required
import json
import os
import subprocess
import threading
import time
import uuid
from datetime import datetime

bp = Blueprint('api', __name__, url_prefix='/api')

# 기존 템플릿에서 호출하는 API 엔드포인트들

# 호환성을 위한 API 엔드포인트들 (실제 로직은 servers.py에서 처리)
@bp.route('/api/all_server_status', methods=['GET'])
@login_required
def get_all_server_status_compat():
    """모든 서버 상태 조회 (호환성)"""
    try:
        from app.routes.servers import get_all_server_status
        return get_all_server_status()
    except Exception as e:
        print(f"💥 /all_server_status 호환성 엔드포인트 오류: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/users', methods=['GET'])
@login_required
def get_users_compat():
    """사용자 목록 조회 (호환성)"""
    try:
        from app.routes.admin import get_users
        return get_users()
    except Exception as e:
        print(f"💥 /users 호환성 엔드포인트 오류: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/users', methods=['POST'])
@login_required
def create_user_compat():
    """사용자 생성 (호환성)"""
    try:
        from app.routes.admin import create_user
        return create_user()
    except Exception as e:
        print(f"💥 /users POST 호환성 엔드포인트 오류: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/current-user', methods=['GET'])
@login_required
def get_current_user_compat():
    """현재 사용자 정보 조회 (호환성)"""
    try:
        from app.routes.admin import get_current_user
        return get_current_user()
    except Exception as e:
        print(f"💥 /current-user 호환성 엔드포인트 오류: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/profile/api', methods=['GET'])
@login_required
def get_profile_api_compat():
    """프로필 정보 API (호환성)"""
    try:
        from app.routes.auth import get_profile_api
        return get_profile_api()
    except Exception as e:
        print(f"💥 /profile/api 호환성 엔드포인트 오류: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/notifications', methods=['GET'])
@login_required
def get_notifications_compat():
    """알림 목록 조회 (호환성)"""
    try:
        from app.routes.notification import get_notifications
        return get_notifications()
    except Exception as e:
        print(f"💥 알림 목록 조회 오류: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/notifications/<int:notification_id>/read', methods=['POST'])
@login_required
def mark_notification_read_compat(notification_id):
    """알림 읽음 표시 (호환성)"""
    try:
        from app.routes.notification import mark_notification_read
        return mark_notification_read(notification_id)
    except Exception as e:
        print(f"💥 알림 읽음 표시 오류: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/notifications/unread-count', methods=['GET'])
@login_required
def get_unread_notification_count_compat():
    """읽지 않은 알림 개수 (호환성)"""
    try:
        from app.routes.notification import get_unread_notification_count
        return get_unread_notification_count()
    except Exception as e:
        print(f"💥 읽지 않은 알림 개수 조회 오류: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/notifications/<int:notification_id>/delete', methods=['POST'])
@login_required
def delete_notification_compat(notification_id):
    """알림 삭제 (호환성)"""
    try:
        from app.models import Notification
        notification = Notification.query.filter_by(id=notification_id, user_id=current_user.id).first()
        if not notification:
            return jsonify({'error': '알림을 찾을 수 없습니다.'}), 404
        
        from app import db
        db.session.delete(notification)
        db.session.commit()
        
        return jsonify({'success': True, 'message': '알림이 삭제되었습니다.'})
    except Exception as e:
        print(f"💥 알림 삭제 오류: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/notifications/clear-all', methods=['POST'])
@login_required
def clear_all_notifications_compat():
    """모든 알림 삭제 (호환성)"""
    try:
        from app.routes.notification import clear_all_notifications
        return clear_all_notifications()
    except Exception as e:
        print(f"💥 모든 알림 삭제 오류: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/firewall/groups', methods=['GET'])
@login_required
def get_firewall_groups_compat():
    """방화벽 그룹 목록 조회 (호환성)"""
    try:
        from app.routes.firewall import get_firewall_groups
        return get_firewall_groups()
    except Exception as e:
        print(f"💥 방화벽 그룹 조회 오류: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/create_server', methods=['POST'])
@login_required
def create_server_compat():
    """서버 생성 (호환성)"""
    try:
        # servers.py의 create_server 함수를 직접 호출
        from app.routes.servers import create_server
        return create_server()
    except Exception as e:
        print(f"💥 서버 생성 호환성 엔드포인트 오류: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/servers', methods=['POST'])
@login_required
def create_server_servers_compat():
    """서버 생성 (/api/servers 호환성)"""
    try:
        from app.routes.servers import create_server
        return create_server()
    except Exception as e:
        print(f"💥 서버 생성 (/api/servers) 호환성 엔드포인트 오류: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/create_servers_bulk', methods=['POST'])
@login_required
def create_servers_bulk_compat():
    """다중 서버 생성 (호환성)"""
    try:
        from app.routes.servers import create_servers_bulk
        return create_servers_bulk()
    except Exception as e:
        print(f"💥 다중 서버 생성 호환성 엔드포인트 오류: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/servers/bulk_action', methods=['POST'])
@login_required
def bulk_server_action_compat():
    """일괄 서버 작업 (호환성)"""
    try:
        from app.routes.servers import bulk_server_action
        return bulk_server_action()
    except Exception as e:
        print(f"💥 일괄 서버 작업 호환성 엔드포인트 오류: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/admin/iam', methods=['GET'])
@login_required
def admin_iam_compat():
    """관리자 IAM (호환성)"""
    try:
        from app.routes.admin import admin_iam_api
        return admin_iam_api()
    except Exception as e:
        print(f"💥 관리자 IAM 호환성 엔드포인트 오류: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/users/<username>', methods=['DELETE'])
@login_required
def delete_user_compat(username):
    """사용자 삭제 (호환성)"""
    try:
        from app.routes.admin import delete_user
        return delete_user(username)
    except Exception as e:
        print(f"💥 사용자 삭제 호환성 엔드포인트 오류: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/users/<username>/password', methods=['POST'])
@login_required
def change_user_password_compat(username):
    """사용자 비밀번호 변경 (호환성)"""
    try:
        from app.routes.admin import change_user_password
        return change_user_password(username)
    except Exception as e:
        print(f"💥 사용자 비밀번호 변경 호환성 엔드포인트 오류: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/admin/iam/<username>/permissions', methods=['POST'])
@login_required
def update_user_permissions_compat(username):
    """사용자 권한 업데이트 (호환성)"""
    try:
        from app.routes.admin import update_user_permissions
        return update_user_permissions(username)
    except Exception as e:
        print(f"💥 사용자 권한 업데이트 호환성 엔드포인트 오류: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/server_status/<server_name>', methods=['GET'])
@login_required
def get_server_status_compat(server_name):
    """서버 상태 조회 (호환성)"""
    try:
        from app.services.proxmox_service import ProxmoxService
        proxmox_service = ProxmoxService()
        result = proxmox_service.get_server_status(server_name)
        
        if result['success']:
            return jsonify(result['data'])
        else:
            return jsonify({'error': result['message']}), 500
    except Exception as e:
        print(f"💥 서버 상태 조회 호환성 엔드포인트 오류: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/servers/<server_name>/start', methods=['POST'])
@login_required
def start_server_compat(server_name):
    """서버 시작 (호환성)"""
    try:
        from app.routes.servers import start_server
        return start_server(server_name)
    except Exception as e:
        print(f"💥 서버 시작 호환성 엔드포인트 오류: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/servers/<server_name>/stop', methods=['POST'])
@login_required
def stop_server_compat(server_name):
    """서버 중지 (호환성)"""
    try:
        from app.routes.servers import stop_server
        return stop_server(server_name)
    except Exception as e:
        print(f"💥 서버 중지 호환성 엔드포인트 오류: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/servers/<server_name>/reboot', methods=['POST'])
@login_required
def reboot_server_compat(server_name):
    """서버 재부팅 (호환성)"""
    try:
        from app.routes.servers import reboot_server
        return reboot_server(server_name)
    except Exception as e:
        print(f"💥 서버 재부팅 호환성 엔드포인트 오류: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/servers/<server_name>/delete', methods=['POST'])
@login_required
def delete_server_compat(server_name):
    """서버 삭제 (호환성)"""
    try:
        from app.routes.servers import delete_server
        return delete_server(server_name)
    except Exception as e:
        print(f"💥 서버 삭제 호환성 엔드포인트 오류: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/assign_role/<server_name>', methods=['POST'])
@login_required
def assign_role_compat(server_name):
    """역할 할당 (호환성)"""
    try:
        from app.routes.servers import assign_role
        return assign_role(server_name)
    except Exception as e:
        print(f"💥 역할 할당 호환성 엔드포인트 오류: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/remove_role/<server_name>', methods=['POST'])
@login_required
def remove_role_compat(server_name):
    """역할 제거 (호환성)"""
    try:
        from app.routes.servers import remove_role
        return remove_role(server_name)
    except Exception as e:
        print(f"💥 역할 제거 호환성 엔드포인트 오류: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/roles/available', methods=['GET'])
@login_required
def get_available_roles_compat():
    """사용 가능한 역할 목록 조회 (호환성)"""
    try:
        from app.routes.servers import get_available_roles
        return get_available_roles()
    except Exception as e:
        print(f"💥 사용 가능한 역할 목록 조회 호환성 엔드포인트 오류: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/roles/validate/<role_name>', methods=['GET'])
@login_required
def validate_role_compat(role_name):
    """역할 유효성 검사 (호환성)"""
    try:
        from app.routes.servers import validate_role
        return validate_role(role_name)
    except Exception as e:
        print(f"💥 역할 유효성 검사 호환성 엔드포인트 오류: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/ansible/status', methods=['GET'])
@login_required
def check_ansible_status_compat():
    """Ansible 설치 상태 확인 (호환성)"""
    try:
        from app.routes.servers import check_ansible_status
        return check_ansible_status()
    except Exception as e:
        print(f"💥 Ansible 상태 확인 호환성 엔드포인트 오류: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/roles/assign_bulk', methods=['POST'])
@login_required
def assign_roles_bulk_compat():
    """일괄 역할 할당 (호환성)"""
    try:
        from app.routes.servers import assign_roles_bulk
        return assign_roles_bulk()
    except Exception as e:
        print(f"💥 일괄 역할 할당 호환성 엔드포인트 오류: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/firewall/assign_bulk', methods=['POST'])
@login_required
def assign_security_groups_bulk_compat():
    """일괄 보안그룹 할당 (호환성)"""
    try:
        from app.routes.servers import assign_security_groups_bulk
        return assign_security_groups_bulk()
    except Exception as e:
        print(f"💥 일괄 보안그룹 할당 호환성 엔드포인트 오류: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/assign_firewall_group/<server_name>', methods=['POST'])
@login_required
def assign_firewall_group_compat(server_name):
    """방화벽 그룹 할당 (호환성)"""
    try:
        from app.routes.firewall import assign_firewall_group
        return assign_firewall_group(server_name)
    except Exception as e:
        print(f"💥 방화벽 그룹 할당 호환성 엔드포인트 오류: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/remove_firewall_group/<server_name>', methods=['POST'])
@login_required
def remove_firewall_group_compat(server_name):
    """방화벽 그룹 제거 (호환성)"""
    try:
        from app.routes.firewall import remove_firewall_group
        return remove_firewall_group(server_name)
    except Exception as e:
        print(f"💥 방화벽 그룹 제거 호환성 엔드포인트 오류: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/instances/multi-server-summary')
@login_required
def multi_server_summary():
    """멀티 서버 요약 (호환성)"""
    try:
        from flask import render_template
        return render_template('partials/multi_server_summary.html')
    except Exception as e:
        print(f"💥 멀티 서버 요약 호환성 엔드포인트 오류: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/favicon.ico')
def favicon():
    """파비콘"""
    return send_from_directory('static', 'favicon.ico')

@bp.route('/api/proxmox_storage', methods=['GET'])
@login_required
def proxmox_storage_compat():
    """Proxmox 스토리지 정보 (호환성)"""
    try:
        from app.routes.servers import proxmox_storage
        return proxmox_storage()
    except Exception as e:
        print(f"💥 Proxmox 스토리지 호환성 엔드포인트 오류: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/sync_servers', methods=['POST'])
@login_required
def sync_servers_compat():
    """서버 동기화 (호환성)"""
    try:
        from app.routes.servers import sync_servers as api_sync_servers
        return api_sync_servers()
    except Exception as e:
        print(f"💥 서버 동기화 호환성 엔드포인트 오류: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/tasks/status')
def get_task_status_compat():
    """Task 상태 조회 (호환성)"""
    try:
        from app.routes.servers import get_task_status
        return get_task_status()
    except Exception as e:
        print(f"💥 Task 상태 조회 호환성 엔드포인트 오류: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/tasks/config')
def get_task_config_compat():
    """Task 설정 정보 (호환성)"""
    try:
        from app.routes.servers import get_task_config
        return get_task_config()
    except Exception as e:
        print(f"💥 Task 설정 조회 호환성 엔드포인트 오류: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/debug/user-info', methods=['GET'])
@login_required
def debug_user_info_compat():
    """디버깅용 사용자 정보 (호환성)"""
    try:
        from app.routes.admin import debug_user_info
        return debug_user_info()
    except Exception as e:
        print(f"💥 /debug/user-info 호환성 엔드포인트 오류: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/debug/servers', methods=['GET'])
@login_required
def debug_servers_compat():
    """서버 디버그 정보 (호환성)"""
    try:
        from app.routes.servers import debug_servers
        return debug_servers()
    except Exception as e:
        print(f"💥 서버 디버그 호환성 엔드포인트 오류: {str(e)}")
        return jsonify({'error': str(e)}), 500

# 세션 관련 호환성 엔드포인트들
@bp.route('/session/check', methods=['GET'])
def check_session_compat():
    """세션 상태 확인 (호환성)"""
    try:
        from app.routes.auth import check_session
        return check_session()
    except Exception as e:
        print(f"💥 세션 상태 확인 호환성 엔드포인트 오류: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/session/refresh', methods=['POST'])
@login_required
def refresh_session_compat():
    """세션 갱신 (호환성)"""
    try:
        from app.routes.auth import refresh_session
        return refresh_session()
    except Exception as e:
        print(f"💥 세션 갱신 호환성 엔드포인트 오류: {str(e)}")
        return jsonify({'error': str(e)}), 500 

        
 