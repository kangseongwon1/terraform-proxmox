"""
API 전용 라우트 블루프린트
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
            user_permissions = [perm.permission for perm in current_user.permissions]
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
    print(f"🔧 Task 생성: {task_id} - {status} - {message}")
    return task_id

def update_task(task_id, status, message=None):
    if task_id in tasks:
        tasks[task_id]['status'] = status
        if message:
            tasks[task_id]['message'] = message
        print(f"🔧 Task 업데이트: {task_id} - {status} - {message}")
    else:
        print(f"❌ Task를 찾을 수 없음: {task_id}")

@bp.route('/tasks/status')
def get_task_status():
    task_id = request.args.get('task_id')
    print(f"🔍 Task 상태 조회: {task_id}")
    print(f"📋 현재 Tasks: {list(tasks.keys())}")
    
    if not task_id:
        return jsonify({'error': 'task_id가 필요합니다.'}), 400
    
    if task_id not in tasks:
        print(f"❌ Task를 찾을 수 없음 (404): {task_id}")
        # 404 에러 시 task를 자동으로 종료 상태로 변경
        tasks[task_id] = {
            'status': 'failed', 
            'type': 'unknown', 
            'message': 'Task를 찾을 수 없어 자동 종료됨'
        }
        print(f"🔧 Task 자동 종료 처리: {task_id}")
        return jsonify(tasks[task_id])
    
    return jsonify(tasks[task_id])

# 서버 관련 API
@bp.route('/api/servers', methods=['GET'])
@permission_required('view_all')
def list_servers():
    """서버 목록 조회"""
    try:
        servers = Server.query.all()
        server_data = []
        for server in servers:
            server_dict = {
                'id': server.id,
                'name': server.name,
                'status': server.status,
                'role': server.role,
                'created_at': server.created_at.isoformat() if server.created_at else None
            }
            server_data.append(server_dict)
        
        return jsonify({'servers': server_data})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/api/debug/servers', methods=['GET'])
@login_required
def debug_servers():
    """서버 디버깅 정보"""
    try:
        servers = Server.query.all()
        server_info = []
        for server in servers:
            server_info.append({
                'id': server.id,
                'name': server.name,
                'status': server.status,
                'role': server.role,
                'created_at': server.created_at.isoformat() if server.created_at else None,
                'updated_at': server.updated_at.isoformat() if server.updated_at else None
            })
        
        return jsonify({
            'total_servers': len(servers),
            'servers': server_info
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/api/servers', methods=['POST'])
@permission_required('create_server')
def create_server():
    """서버 생성"""
    try:
        data = request.get_json()
        print(f"🔧 서버 생성 요청: {data}")
        
        # 서버 이름 중복 체크
        existing_server = Server.query.filter_by(name=data['name']).first()
        if existing_server:
            error_msg = f'서버 이름 "{data["name"]}"이 이미 존재합니다.'
            print(f"❌ 서버 이름 중복: {error_msg}")
            return jsonify({'error': error_msg}), 400
        
        # 새 서버 생성
        new_server = Server(
            name=data['name'],
            status='creating',
            role=data.get('role', '')
        )
        
        from app import db
        db.session.add(new_server)
        db.session.commit()
        print(f"✅ 서버 DB 생성 완료: {new_server.name}")
        
        # 백그라운드에서 서버 생성 작업 실행
        task_id = create_task('running', 'create_server', '서버 생성 중...')
        print(f"🔧 백그라운드 작업 시작: {task_id}")
        
        def create_server_task():
            try:
                print(f"🔧 Terraform 서비스 호출 시작: {task_id}")
                # Terraform 서비스 호출
                from app.services.terraform_service import TerraformService
                terraform_service = TerraformService()
                result = terraform_service.create_server(data)
                
                if result['success']:
                    update_task(task_id, 'completed', '서버 생성 완료')
                    print(f"✅ 서버 생성 성공: {task_id}")
                else:
                    update_task(task_id, 'failed', f'서버 생성 실패: {result["message"]}')
                    print(f"❌ 서버 생성 실패: {task_id} - {result['message']}")
            except Exception as e:
                error_msg = f'서버 생성 중 오류: {str(e)}'
                update_task(task_id, 'failed', error_msg)
                print(f"💥 서버 생성 예외: {task_id} - {error_msg}")
        
        import threading
        thread = threading.Thread(target=create_server_task)
        thread.daemon = True
        thread.start()
        
        response = {'success': True, 'message': '서버 생성이 시작되었습니다.', 'task_id': task_id}
        print(f"✅ 서버 생성 응답: {response}")
        return jsonify(response)
    except Exception as e:
        error_msg = f'서버 생성 요청 처리 중 오류: {str(e)}'
        print(f"💥 서버 생성 요청 예외: {error_msg}")
        return jsonify({'error': error_msg}), 500

@bp.route('/api/servers/<server_name>/start', methods=['POST'])
@permission_required('start_server')
def start_server(server_name):
    """서버 시작"""
    try:
        # Proxmox 서비스 사용
        from app.services.proxmox_service import ProxmoxService
        proxmox_service = ProxmoxService()
        result = proxmox_service.start_server(server_name)
        
        if result['success']:
            return jsonify({'success': True, 'message': f'서버 {server_name}이 시작되었습니다.'})
        else:
            return jsonify({'error': result['message']}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/api/servers/<server_name>/stop', methods=['POST'])
@permission_required('stop_server')
def stop_server(server_name):
    """서버 중지"""
    try:
        # Proxmox 서비스 사용
        from app.services.proxmox_service import ProxmoxService
        proxmox_service = ProxmoxService()
        result = proxmox_service.stop_server(server_name)
        
        if result['success']:
            return jsonify({'success': True, 'message': f'서버 {server_name}이 중지되었습니다.'})
        else:
            return jsonify({'error': result['message']}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/api/servers/<server_name>/reboot', methods=['POST'])
@permission_required('reboot_server')
def reboot_server(server_name):
    """서버 재부팅"""
    try:
        # Proxmox 서비스 사용
        from app.services.proxmox_service import ProxmoxService
        proxmox_service = ProxmoxService()
        result = proxmox_service.reboot_server(server_name)
        
        if result['success']:
            return jsonify({'success': True, 'message': f'서버 {server_name}이 재부팅되었습니다.'})
        else:
            return jsonify({'error': result['message']}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/api/servers/<server_name>/delete', methods=['POST'])
@permission_required('delete_server')
def delete_server(server_name):
    """서버 삭제"""
    try:
        # 백그라운드에서 서버 삭제 작업 실행
        task_id = create_task('running', 'delete_server', '서버 삭제 중...')
        
        def delete_server_task():
            try:
                # Terraform 서비스 사용
                from app.services.terraform_service import TerraformService
                terraform_service = TerraformService()
                result = terraform_service.destroy_server(server_name)
                
                if result['success']:
                    update_task(task_id, 'completed', '서버 삭제 완료')
                else:
                    update_task(task_id, 'failed', f'서버 삭제 실패: {result["message"]}')
            except Exception as e:
                update_task(task_id, 'failed', f'서버 삭제 중 오류: {str(e)}')
        
        import threading
        thread = threading.Thread(target=delete_server_task)
        thread.daemon = True
        thread.start()
        
        return jsonify({'success': True, 'message': '서버 삭제가 시작되었습니다.', 'task_id': task_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# 대시보드 API
@bp.route('/api/all_server_status', methods=['GET'])
@login_required
def get_all_server_status():
    """모든 서버 상태 조회"""
    try:
        print("🔍 /api/all_server_status 호출됨 (API)")
        proxmox_service = ProxmoxService()
        result = proxmox_service.get_all_vms()
        
        if result['success']:
            # 새로운 API 응답 형식에 맞게 변환
            data = result['data']
            servers = data.get('servers', {})
            stats = data.get('stats', {})
            
            # 기존 UI와 호환되는 형식으로 변환
            vms = []
            for server_name, server_info in servers.items():
                vm_info = {
                    'vmid': server_info.get('vmid'),
                    'name': server_name,
                    'status': server_info.get('status', 'unknown'),
                    'cpu': server_info.get('cpu', 0),
                    'mem': server_info.get('memory', 0),
                    'maxmem': server_info.get('maxmem', 0),
                    'disk': server_info.get('disk', 0),
                    'maxdisk': server_info.get('maxdisk', 0),
                    'uptime': server_info.get('uptime', 0),
                    'role': server_info.get('role', 'unknown'),
                    'network_devices': server_info.get('ip_addresses', [])
                }
                vms.append(vm_info)
            
            response_data = {
                'servers': servers,  # JavaScript에서 기대하는 형식
                'vms': vms,  # 호환성을 위해 추가
                'total': stats.get('total_servers', 0),
                'running': stats.get('running_servers', 0),
                'stopped': stats.get('stopped_servers', 0),
                'stats': stats  # 통계 정보 포함
            }
            
            return jsonify(response_data)
        else:
            print(f"❌ get_all_vms 실패: {result['message']}")
            return jsonify({'error': result['message']}), 500
    except Exception as e:
        print(f"💥 /api/all_server_status 예외 발생: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/proxmox_storage', methods=['GET'])
def proxmox_storage():
    """Proxmox 스토리지 정보 조회"""
    try:
        from app.services.proxmox_service import ProxmoxService
        proxmox_service = ProxmoxService()
        result = proxmox_service.get_storage_info()
        
        if result['success']:
            return jsonify({'storages': result['data']})
        else:
            return jsonify({'error': result['message']}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# 알림 API
@bp.route('/api/notifications', methods=['GET'])
@login_required
def get_notifications():
    """알림 목록 조회"""
    try:
        from app.models import Notification
        notifications = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_at.desc()).all()
        
        notification_data = []
        for notification in notifications:
            notification_data.append({
                'id': notification.id,
                'title': notification.title,
                'message': notification.message,
                'severity': notification.severity,
                'is_read': notification.is_read,
                'created_at': notification.created_at.isoformat() if notification.created_at else None
            })
        
        return jsonify({'notifications': notification_data})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/api/notifications/<int:notification_id>/read', methods=['POST'])
@login_required
def mark_notification_read(notification_id):
    """알림 읽음 표시"""
    try:
        from app.models import Notification
        notification = Notification.query.filter_by(id=notification_id, user_id=current_user.id).first()
        
        if not notification:
            return jsonify({'error': '알림을 찾을 수 없습니다.'}), 404
        
        notification.is_read = True
        from app import db
        db.session.commit()
        
        return jsonify({'success': True, 'message': '알림이 읽음으로 표시되었습니다.'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/api/notifications/unread-count', methods=['GET'])
@login_required
def get_unread_notification_count():
    """읽지 않은 알림 개수"""
    try:
        from app.models import Notification
        count = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
        return jsonify({'count': count})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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
        return jsonify({'error': str(e)}), 500

@bp.route('/api/users', methods=['POST'])
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
        
        return jsonify({'success': True, 'message': '사용자가 삭제되었습니다.'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/api/assign_role/<server_name>', methods=['POST'])
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

@bp.route('/api/remove_role/<server_name>', methods=['POST'])
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

@bp.route('/api/assign_firewall_group/<server_name>', methods=['POST'])
@permission_required('assign_firewall_group')
def assign_firewall_group(server_name):
    """서버에 방화벽 그룹 할당"""
    try:
        data = request.get_json()
        firewall_group = data.get('firewall_group')
        
        server = Server.query.filter_by(name=server_name).first()
        if not server:
            return jsonify({'error': '서버를 찾을 수 없습니다.'}), 404
        
        server.firewall_group = firewall_group
        from app import db
        db.session.commit()
        
        return jsonify({'success': True, 'message': f'서버 {server_name}에 방화벽 그룹 {firewall_group}이 할당되었습니다.'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/api/remove_firewall_group/<server_name>', methods=['POST'])
@permission_required('remove_firewall_group')
def remove_firewall_group(server_name):
    """서버에서 방화벽 그룹 제거"""
    try:
        server = Server.query.filter_by(name=server_name).first()
        if not server:
            return jsonify({'error': '서버를 찾을 수 없습니다.'}), 404
        
        server.firewall_group = None
        from app import db
        db.session.commit()
        
        return jsonify({'success': True, 'message': f'서버 {server_name}에서 방화벽 그룹이 제거되었습니다.'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/api/start_server/<server_name>', methods=['POST'])
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

@bp.route('/api/stop_server/<server_name>', methods=['POST'])
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

@bp.route('/api/reboot_server/<server_name>', methods=['POST'])
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

@bp.route('/api/delete_server/<server_name>', methods=['POST'])
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
@bp.route('/api/admin/iam', methods=['GET'])
def admin_iam_api():
    """관리자 IAM API"""
    try:
        from app.models import User, UserPermission
        users = User.query.all()
        
        # 모든 권한 목록 생성 (실제로는 별도 테이블이 없으므로 하드코딩)
        all_permissions = [
            'view_all', 'create_server', 'delete_server', 'start_server', 
            'stop_server', 'manage_users', 'manage_roles', 'view_logs', 
            'manage_storage', 'manage_network', 'assign_roles', 'remove_role',
            'assign_firewall_group', 'remove_firewall_group'
        ]
        
        user_data = []
        for user in users:
            user_dict = {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'role': user.role,
                'is_active': user.is_active,
                'permissions': [perm.permission for perm in user.permissions]
            }
            user_data.append(user_dict)
        
        return jsonify({
            'users': user_data,
            'permissions': all_permissions
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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
        user.permissions.clear()
        
        # 새 권한 추가
        for perm_name in permissions:
            user_perm = UserPermission(user_id=user.id, permission=perm_name)
            db.session.add(user_perm)
        
        from app import db
        db.session.commit()
        
        return jsonify({'success': True, 'message': '권한이 업데이트되었습니다.'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/api/admin/iam/<username>/role', methods=['POST'])
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
        
        return jsonify({'success': True, 'message': '역할이 업데이트되었습니다.'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# 방화벽 그룹 API
@bp.route('/api/firewall/groups', methods=['GET'])
def get_firewall_groups():
    """방화벽 그룹 목록 조회"""
    try:
        # 임시 데이터 (실제로는 데이터베이스에서 조회)
        groups = [
            {'name': 'web', 'description': '웹 서버 방화벽', 'instance_count': 2},
            {'name': 'db', 'description': '데이터베이스 방화벽', 'instance_count': 1}
        ]
        return jsonify({'groups': groups})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/api/firewall/groups', methods=['POST'])
def add_firewall_group():
    """방화벽 그룹 추가"""
    try:
        data = request.get_json()
        # 실제로는 데이터베이스에 저장
        return jsonify({'success': True, 'message': '방화벽 그룹이 추가되었습니다.'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/api/firewall/groups/<group_name>', methods=['DELETE'])
def delete_firewall_group(group_name):
    """방화벽 그룹 삭제"""
    try:
        # 실제로는 데이터베이스에서 삭제
        return jsonify({'success': True, 'message': f'방화벽 그룹 {group_name}이 삭제되었습니다.'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/api/firewall/groups/<group_name>/rules', methods=['GET'])
def get_firewall_group_rules(group_name):
    """방화벽 그룹 규칙 조회"""
    try:
        # 임시 데이터
        group = {'name': group_name, 'description': f'{group_name} 방화벽 그룹'}
        rules = [
            {'id': 1, 'direction': 'in', 'protocol': 'tcp', 'port': '80', 'source': '', 'description': 'HTTP'},
            {'id': 2, 'direction': 'in', 'protocol': 'tcp', 'port': '443', 'source': '', 'description': 'HTTPS'}
        ]
        return jsonify({'group': group, 'rules': rules})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/api/firewall/groups/<group_name>/rules', methods=['POST'])
def add_firewall_group_rule(group_name):
    """방화벽 그룹 규칙 추가"""
    try:
        data = request.get_json()
        # 실제로는 데이터베이스에 저장
        return jsonify({'success': True, 'message': '방화벽 규칙이 추가되었습니다.'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/api/firewall/groups/<group_name>/rules/<int:rule_id>', methods=['DELETE'])
def delete_firewall_group_rule(group_name, rule_id):
    """방화벽 그룹 규칙 삭제"""
    try:
        # 실제로는 데이터베이스에서 삭제
        return jsonify({'success': True, 'message': '방화벽 규칙이 삭제되었습니다.'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# 알림 API
@bp.route('/api/notifications/clear-all', methods=['POST'])
@login_required
def clear_all_notifications():
    """모든 알림 삭제"""
    try:
        from app.models import Notification
        Notification.query.filter_by(user_id=current_user.id).delete()
        from app import db
        db.session.commit()
        
        return jsonify({'success': True, 'message': '모든 알림이 삭제되었습니다.'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500 