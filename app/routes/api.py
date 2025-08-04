"""
API 라우트 블루프린트
"""
from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user
from functools import wraps
from app.models import User, Server, Notification
from app.services import ProxmoxService, TerraformService, AnsibleService, NotificationService
import json
import os
import subprocess
import threading
import time
import uuid

bp = Blueprint('api', __name__, url_prefix='/api')

# 권한 데코레이터
def permission_required(permission):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return jsonify({'error': '로그인이 필요합니다.'}), 401
            
            # 관리자는 모든 권한을 가짐
            if current_user.is_admin:
                return f(*args, **kwargs)
            
            # 사용자 권한 확인
            user_permissions = [p.name for p in current_user.permissions]
            if permission not in user_permissions:
                return jsonify({'error': '권한이 없습니다.'}), 403
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# 전역 작업 상태 dict
tasks = {}

def create_task(status, type, message):
    task_id = str(uuid.uuid4())
    tasks[task_id] = {'status': status, 'type': type, 'message': message}
    return task_id

def update_task(task_id, status, message=None):
    if task_id in tasks:
        tasks[task_id]['status'] = status
        if message:
            tasks[task_id]['message'] = message

@bp.route('/tasks/status')
def get_task_status():
    task_id = request.args.get('task_id')
    if not task_id or task_id not in tasks:
        return jsonify({'error': 'Invalid task_id'}), 404
    return jsonify(tasks[task_id])

# 서버 관련 API
@bp.route('/servers', methods=['GET'])
@permission_required('view_all')
def list_servers():
    """서버 목록 조회"""
    try:
        servers = Server.query.all()
        server_list = []
        for server in servers:
            server_list.append({
                'id': server.id,
                'name': server.name,
                'status': server.status,
                'role': server.role,
                'cpu': server.cpu,
                'memory_gb': server.memory_gb,
                'ip_address': server.ip_address,
                'created_at': server.created_at.isoformat() if server.created_at else None
            })
        return jsonify({'servers': server_list})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/servers', methods=['POST'])
@permission_required('create_server')
def create_server():
    """서버 생성"""
    try:
        data = request.get_json()
        
        # 작업 생성
        task_id = create_task('pending', '서버 생성', '서버 생성 대기 중...')
        
        # 백그라운드에서 서버 생성 실행
        def create_server_task():
            try:
                # Terraform 서비스 사용
                terraform_service = TerraformService()
                result = terraform_service.create_server(data)
                
                if result['success']:
                    update_task(task_id, 'success', '서버가 성공적으로 생성되었습니다.')
                else:
                    update_task(task_id, 'error', result['message'])
            except Exception as e:
                update_task(task_id, 'error', f'서버 생성 중 오류: {str(e)}')
        
        thread = threading.Thread(target=create_server_task)
        thread.start()
        
        return jsonify({'task_id': task_id, 'message': '서버 생성이 시작되었습니다.'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/servers/<server_name>/start', methods=['POST'])
@permission_required('start_server')
def start_server(server_name):
    """서버 시작"""
    try:
        proxmox_service = ProxmoxService()
        result = proxmox_service.start_vm(server_name)
        
        if result['success']:
            return jsonify({'success': True, 'message': f'서버 {server_name}이(가) 시작되었습니다.'})
        else:
            return jsonify({'success': False, 'message': result['message']}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/servers/<server_name>/stop', methods=['POST'])
@permission_required('stop_server')
def stop_server(server_name):
    """서버 중지"""
    try:
        proxmox_service = ProxmoxService()
        result = proxmox_service.stop_vm(server_name)
        
        if result['success']:
            return jsonify({'success': True, 'message': f'서버 {server_name}이(가) 중지되었습니다.'})
        else:
            return jsonify({'success': False, 'message': result['message']}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/servers/<server_name>/reboot', methods=['POST'])
@permission_required('reboot_server')
def reboot_server(server_name):
    """서버 재부팅"""
    try:
        proxmox_service = ProxmoxService()
        result = proxmox_service.reboot_vm(server_name)
        
        if result['success']:
            return jsonify({'success': True, 'message': f'서버 {server_name}이(가) 재부팅되었습니다.'})
        else:
            return jsonify({'success': False, 'message': result['message']}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/servers/<server_name>/delete', methods=['POST'])
@permission_required('delete_server')
def delete_server(server_name):
    """서버 삭제"""
    try:
        # 작업 생성
        task_id = create_task('pending', '서버 삭제', f'서버 {server_name} 삭제 대기 중...')
        
        def delete_server_task():
            try:
                terraform_service = TerraformService()
                result = terraform_service.destroy_server(server_name)
                
                if result['success']:
                    update_task(task_id, 'success', f'서버 {server_name}이(가) 삭제되었습니다.')
                else:
                    update_task(task_id, 'error', result['message'])
            except Exception as e:
                update_task(task_id, 'error', f'서버 삭제 중 오류: {str(e)}')
        
        thread = threading.Thread(target=delete_server_task)
        thread.start()
        
        return jsonify({'task_id': task_id, 'message': f'서버 {server_name} 삭제가 시작되었습니다.'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# 대시보드 API
@bp.route('/all_server_status', methods=['GET'])
@login_required
def get_all_server_status():
    """모든 서버 상태 조회"""
    try:
        proxmox_service = ProxmoxService()
        result = proxmox_service.get_all_vms()
        
        if result['success']:
            return jsonify(result['data'])
        else:
            return jsonify({'error': result['message']}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/proxmox_storage', methods=['GET'])
def proxmox_storage():
    """Proxmox 스토리지 정보 조회"""
    try:
        proxmox_service = ProxmoxService()
        result = proxmox_service.get_storage_info()
        
        if result['success']:
            return jsonify(result['data'])
        else:
            return jsonify({'error': result['message']}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# 알림 API
@bp.route('/notifications', methods=['GET'])
@login_required
def get_notifications():
    """알림 목록 조회"""
    try:
        notifications = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_at.desc()).all()
        notification_list = []
        for notification in notifications:
            notification_list.append({
                'id': notification.id,
                'title': notification.title,
                'message': notification.message,
                'type': notification.type,
                'severity': notification.severity,
                'is_read': notification.is_read,
                'created_at': notification.created_at.isoformat() if notification.created_at else None
            })
        return jsonify({'notifications': notification_list})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/notifications/<int:notification_id>/read', methods=['POST'])
@login_required
def mark_notification_read(notification_id):
    """알림 읽음 처리"""
    try:
        notification = Notification.query.get(notification_id)
        if notification and notification.user_id == current_user.id:
            notification.is_read = True
            from app import db
            db.session.commit()
            return jsonify({'success': True})
        else:
            return jsonify({'error': '알림을 찾을 수 없습니다.'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/notifications/unread-count', methods=['GET'])
@login_required
def get_unread_notification_count():
    """읽지 않은 알림 개수 조회"""
    try:
        count = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
        return jsonify({'count': count})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# 사용자 관리 API
@bp.route('/users', methods=['GET'])
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
        return jsonify({'error': str(e)}), 500

@bp.route('/users', methods=['POST'])
@permission_required('manage_users')
def create_user():
    """사용자 생성"""
    try:
        data = request.get_json()
        
        # 기존 사용자 확인
        existing_user = User.query.filter_by(username=data['username']).first()
        if existing_user:
            return jsonify({'error': '이미 존재하는 사용자명입니다.'}), 400
        
        # 새 사용자 생성
        new_user = User(
            username=data['username'],
            email=data.get('email'),
            role=data.get('role', 'user')
        )
        new_user.set_password(data['password'])
        
        from app import db
        db.session.add(new_user)
        db.session.commit()
        
        return jsonify({'success': True, 'message': '사용자가 생성되었습니다.'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/users/<username>/delete', methods=['POST'])
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
        
        return jsonify({'success': True, 'message': '사용자가 삭제되었습니다.'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/assign_role/<server_name>', methods=['POST'])
@permission_required('assign_roles')
def assign_role(server_name):
    """서버에 역할 할당"""
    try:
        data = request.get_json()
        role = data.get('role')
        
        server = Server.query.filter_by(name=server_name).first()
        if not server:
            return jsonify({'error': '서버를 찾을 수 없습니다.'}), 404
        
        server.role = role
        from app import db
        db.session.commit()
        
        return jsonify({'success': True, 'message': f'서버 {server_name}에 역할 {role}이 할당되었습니다.'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/remove_role/<server_name>', methods=['POST'])
@permission_required('remove_role')
def remove_role(server_name):
    """서버에서 역할 제거"""
    try:
        server = Server.query.filter_by(name=server_name).first()
        if not server:
            return jsonify({'error': '서버를 찾을 수 없습니다.'}), 404
        
        server.role = None
        from app import db
        db.session.commit()
        
        return jsonify({'success': True, 'message': f'서버 {server_name}에서 역할이 제거되었습니다.'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/assign_firewall_group/<server_name>', methods=['POST'])
@permission_required('assign_firewall_group')
def assign_firewall_group(server_name):
    """서버에 방화벽 그룹 할당"""
    try:
        data = request.get_json()
        firewall_group = data.get('firewall_group')
        
        server = Server.query.filter_by(name=server_name).first()
        if not server:
            return jsonify({'error': '서버를 찾을 수 없습니다.'}), 404
        
        # 실제 구현에서는 방화벽 그룹 정보를 저장
        return jsonify({'success': True, 'message': f'서버 {server_name}에 방화벽 그룹 {firewall_group}이 할당되었습니다.'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/remove_firewall_group/<server_name>', methods=['POST'])
@permission_required('remove_firewall_group')
def remove_firewall_group(server_name):
    """서버에서 방화벽 그룹 제거"""
    try:
        server = Server.query.filter_by(name=server_name).first()
        if not server:
            return jsonify({'error': '서버를 찾을 수 없습니다.'}), 404
        
        # 실제 구현에서는 방화벽 그룹 정보를 제거
        return jsonify({'success': True, 'message': f'서버 {server_name}에서 방화벽 그룹이 제거되었습니다.'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/start_server/<server_name>', methods=['POST'])
@permission_required('start_server')
def start_server_legacy(server_name):
    """서버 시작 (기존 템플릿 호환)"""
    try:
        proxmox_service = ProxmoxService()
        result = proxmox_service.start_vm(server_name)
        
        if result['success']:
            return jsonify({'success': True, 'message': f'서버 {server_name}이(가) 시작되었습니다.'})
        else:
            return jsonify({'success': False, 'message': result['message']}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/stop_server/<server_name>', methods=['POST'])
@permission_required('stop_server')
def stop_server_legacy(server_name):
    """서버 중지 (기존 템플릿 호환)"""
    try:
        proxmox_service = ProxmoxService()
        result = proxmox_service.stop_vm(server_name)
        
        if result['success']:
            return jsonify({'success': True, 'message': f'서버 {server_name}이(가) 중지되었습니다.'})
        else:
            return jsonify({'success': False, 'message': result['message']}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/reboot_server/<server_name>', methods=['POST'])
@permission_required('reboot_server')
def reboot_server_legacy(server_name):
    """서버 재부팅 (기존 템플릿 호환)"""
    try:
        proxmox_service = ProxmoxService()
        result = proxmox_service.reboot_vm(server_name)
        
        if result['success']:
            return jsonify({'success': True, 'message': f'서버 {server_name}이(가) 재부팅되었습니다.'})
        else:
            return jsonify({'success': False, 'message': result['message']}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/delete_server/<server_name>', methods=['POST'])
@permission_required('delete_server')
def delete_server_legacy(server_name):
    """서버 삭제 (기존 템플릿 호환)"""
    try:
        # 작업 생성
        task_id = create_task('pending', '서버 삭제', f'서버 {server_name} 삭제 대기 중...')
        
        def delete_server_task():
            try:
                terraform_service = TerraformService()
                result = terraform_service.destroy_server(server_name)
                
                if result['success']:
                    update_task(task_id, 'success', f'서버 {server_name}이(가) 삭제되었습니다.')
                else:
                    update_task(task_id, 'error', result['message'])
            except Exception as e:
                update_task(task_id, 'error', f'서버 삭제 중 오류: {str(e)}')
        
        thread = threading.Thread(target=delete_server_task)
        thread.start()
        
        return jsonify({'task_id': task_id, 'message': f'서버 {server_name} 삭제가 시작되었습니다.'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# 관리자 IAM API
@bp.route('/admin/iam', methods=['GET'])
def admin_iam_api():
    """관리자 IAM API (기존 템플릿 호환)"""
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
        return jsonify({'error': str(e)}), 500

@bp.route('/admin/iam/<username>/permissions', methods=['POST'])
def admin_iam_set_permissions(username):
    """사용자 권한 설정"""
    try:
        data = request.get_json()
        permissions = data.get('permissions', [])
        
        user = User.query.filter_by(username=username).first()
        if not user:
            return jsonify({'error': '사용자를 찾을 수 없습니다.'}), 404
        
        # 실제 구현에서는 권한을 설정
        return jsonify({'success': True, 'message': f'사용자 {username}의 권한이 설정되었습니다.'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/admin/iam/<username>/role', methods=['POST'])
def admin_iam_set_role(username):
    """사용자 역할 설정"""
    try:
        data = request.get_json()
        role = data.get('role')
        
        user = User.query.filter_by(username=username).first()
        if not user:
            return jsonify({'error': '사용자를 찾을 수 없습니다.'}), 404
        
        user.role = role
        from app import db
        db.session.commit()
        
        return jsonify({'success': True, 'message': f'사용자 {username}의 역할이 {role}로 설정되었습니다.'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# 방화벽 그룹 API
@bp.route('/firewall/groups', methods=['GET'])
def get_firewall_groups():
    """방화벽 그룹 목록 조회"""
    try:
        # 임시 데이터 (실제로는 데이터베이스에서 조회)
        groups = [
            {'name': 'web-allow', 'description': '웹서버 허용', 'instances': 0},
            {'name': 'db-only', 'description': 'DB 접근만 허용', 'instances': 0}
        ]
        return jsonify({'groups': groups})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/firewall/groups', methods=['POST'])
def add_firewall_group():
    """방화벽 그룹 추가"""
    try:
        data = request.get_json()
        # 실제 구현에서는 데이터베이스에 저장
        return jsonify({'success': True, 'message': '방화벽 그룹이 추가되었습니다.'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/firewall/groups/<group_name>', methods=['DELETE'])
def delete_firewall_group(group_name):
    """방화벽 그룹 삭제"""
    try:
        # 실제 구현에서는 데이터베이스에서 삭제
        return jsonify({'success': True, 'message': f'방화벽 그룹 {group_name}이(가) 삭제되었습니다.'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500 

@bp.route('/firewall/groups/<group_name>/rules', methods=['GET'])
def get_firewall_group_rules(group_name):
    """방화벽 그룹 규칙 조회"""
    try:
        # 임시 데이터 (실제로는 데이터베이스에서 조회)
        rules = [
            {'id': 1, 'protocol': 'tcp', 'port': '80', 'action': 'allow'},
            {'id': 2, 'protocol': 'tcp', 'port': '443', 'action': 'allow'}
        ]
        return jsonify({'rules': rules})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/firewall/groups/<group_name>/rules', methods=['POST'])
def add_firewall_group_rule(group_name):
    """방화벽 그룹 규칙 추가"""
    try:
        data = request.get_json()
        # 실제 구현에서는 데이터베이스에 저장
        return jsonify({'success': True, 'message': '방화벽 규칙이 추가되었습니다.'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/firewall/groups/<group_name>/rules/<int:rule_id>', methods=['DELETE'])
def delete_firewall_group_rule(group_name, rule_id):
    """방화벽 그룹 규칙 삭제"""
    try:
        # 실제 구현에서는 데이터베이스에서 삭제
        return jsonify({'success': True, 'message': f'방화벽 규칙 {rule_id}이(가) 삭제되었습니다.'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# 알림 API
@bp.route('/notifications/clear-all', methods=['POST'])
@login_required
def clear_all_notifications():
    """모든 알림 삭제"""
    try:
        notifications = Notification.query.filter_by(user_id=current_user.id).all()
        for notification in notifications:
            from app import db
            db.session.delete(notification)
        db.session.commit()
        
        return jsonify({'success': True, 'message': '모든 알림이 삭제되었습니다.'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500 