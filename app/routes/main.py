"""
메인 라우트 블루프린트
"""

"""랜더링 용"""
from flask import Blueprint, render_template, current_app, jsonify, request, send_from_directory
from flask_login import login_required, current_user
from app.models import User, Server, Notification
from app.services import ProxmoxService
import json

bp = Blueprint('main', __name__)

@bp.route('/')
@login_required
def index():
    """메인 페이지"""
    return render_template('index.html')

@bp.route('/dashboard')
@login_required
def dashboard():
    """대시보드"""
    servers = Server.query.all()
    return render_template('dashboard.html', servers=servers)

@bp.route('/servers')
@login_required
def servers():
    """서버 목록"""
    servers = Server.query.all()
    return render_template('servers/index.html', servers=servers)

@bp.route('/admin')
@login_required
def admin():
    """관리자 페이지"""
    users = User.query.all()
    servers = Server.query.all()
    notifications = Notification.query.order_by(Notification.created_at.desc()).limit(5).all()
    return render_template('admin/index.html', users=users, servers=servers, notifications=notifications)

# 기존 템플릿과 호환성을 위한 라우트들
@bp.route('/instances/content')
@login_required
def instances_content():
    """인스턴스 콘텐츠 (기존 템플릿 호환)"""
    try:
        print("🔍 /instances/content 호출됨")
        proxmox_service = ProxmoxService()
        result = proxmox_service.get_all_vms()
        
        if result['success']:
            servers = result['data']['servers']
            # 서버 목록을 템플릿에서 사용할 수 있는 형식으로 변환
            server_list = []
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
                    'ip_addresses': server_info.get('ip_addresses', [])
                }
                server_list.append(vm_info)
        else:
            # 데이터베이스에서 직접 조회
            with proxmox_service._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT name, vmid, status, ip_address, role, os_type, cpu, memory, firewall_group
                    FROM servers
                ''')
                db_servers = cursor.fetchall()
                
                server_list = []
                for db_server in db_servers:
                    vm_info = {
                        'vmid': db_server['vmid'],
                        'name': db_server['name'],
                        'status': db_server['status'] or 'unknown',
                        'cpu': db_server['cpu'] or 0,
                        'mem': 0,
                        'maxmem': db_server['memory'] or 0,
                        'disk': 0,
                        'maxdisk': 0,
                        'uptime': 0,
                        'ip_address': db_server['ip_address'],
                        'role': db_server['role'],
                        'firewall_group': db_server['firewall_group'],
                        'os_type': db_server['os_type']
                    }
                    server_list.append(vm_info)
        
        # roles 변수 준비 (기존 app.py와 동일)
        roles = {
            'web': {'name': '웹서버', 'description': '웹 서비스 제공'},
            'was': {'name': 'WAS', 'description': '애플리케이션 서버'},
            'java': {'name': 'JAVA', 'description': '자바 서버'},
            'search': {'name': '검색', 'description': '검색 서버'},
            'ftp': {'name': 'FTP', 'description': '파일 서버'},
            'db': {'name': 'DB', 'description': '데이터베이스 서버'}
        }
        
        return render_template('partials/instances_content.html', servers=server_list, roles=roles, server_data=servers)
    except Exception as e:
        print(f"💥 /instances/content 예외 발생: {str(e)}")
        return render_template('partials/instances_content.html', servers=[], server_data={})

@bp.route('/dashboard/content')
@login_required
def dashboard_content():
    """대시보드 콘텐츠 (기존 템플릿 호환)"""
    try:
        print("🔍 /dashboard/content 호출됨")
        proxmox_service = ProxmoxService()
        result = proxmox_service.get_all_vms()
        
        print(f"🔍 get_all_vms 결과: {result}")
        
        if result['success']:
            servers = result['data']['servers']
            stats = result['data']['stats']
            total = stats.get('total_servers', 0)
            running = stats.get('running_servers', 0)
            stopped = stats.get('stopped_servers', 0)
            
            print(f"🔍 서버 수: {len(servers)}")
            print(f"🔍 통계: total={total}, running={running}, stopped={stopped}")
        else:
            print(f"❌ get_all_vms 실패: {result.get('message', '알 수 없는 오류')}")
            # 데이터베이스에서 직접 조회
            with proxmox_service._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT name, vmid, status, ip_address, role, os_type, cpu, memory, firewall_group
                    FROM servers
                ''')
                db_servers = cursor.fetchall()
                
                servers = []
                for db_server in db_servers:
                    vm_info = {
                        'vmid': db_server['vmid'],
                        'name': db_server['name'],
                        'status': db_server['status'] or 'unknown',
                        'cpu': db_server['cpu'] or 0,
                        'mem': 0,
                        'maxmem': db_server['memory'] or 0,
                        'disk': 0,
                        'maxdisk': 0,
                        'uptime': 0,
                        'ip_address': db_server['ip_address'],
                        'role': db_server['role'],
                        'firewall_group': db_server['firewall_group'],
                        'os_type': db_server['os_type']
                    }
                    servers.append(vm_info)
                
                total = len(servers)
                running = len([s for s in servers if s['status'] == 'running'])
                stopped = len([s for s in servers if s['status'] == 'stopped'])
        
        return render_template('partials/dashboard_content.html', 
                             servers=servers, total=total, running=running, stopped=stopped)
    except Exception as e:
        print(f"💥 /dashboard/content 예외 발생: {str(e)}")
        import traceback
        traceback.print_exc()
        return render_template('partials/dashboard_content.html', servers=[], total=0, running=0, stopped=0)

@bp.route('/storage/content')
@login_required
def storage_content():
    """스토리지 콘텐츠 (기존 템플릿 호환)"""
    try:
        print("🔍 /storage/content 호출됨")
        proxmox_service = ProxmoxService()
        result = proxmox_service.get_storage_info()
        
        print(f"🔍 get_storage_info 결과: {result}")
        
        if result['success']:
            storages = result['data']
            print(f"🔍 스토리지 수: {len(storages)}")
        else:
            print(f"❌ get_storage_info 실패: {result.get('message', '알 수 없는 오류')}")
            storages = []
        
        return render_template('partials/storage_content.html', storages=storages)
    except Exception as e:
        print(f"💥 /storage/content 예외 발생: {str(e)}")
        import traceback
        traceback.print_exc()
        return render_template('partials/storage_content.html', storages=[])

@bp.route('/admin/iam/content')
@login_required
def admin_iam_content():
    """관리자 IAM 콘텐츠 (기존 템플릿 호환)"""
    try:
        print("🔍 /admin/iam/content 호출됨")
        users = User.query.all()
        return render_template('partials/admin_iam_content.html', users=users)
    except Exception as e:
        print(f"💥 /admin/iam/content 예외 발생: {str(e)}")
        return render_template('partials/admin_iam_content.html', users=[])

@bp.route('/firewall/groups/content')
@login_required
def firewall_groups_content():
    """방화벽 그룹 콘텐츠 (기존 템플릿 호환)"""
    try:
        print("🔍 /firewall/groups/content 호출됨")
        # 방화벽 그룹 데이터는 JavaScript에서 AJAX로 가져옴
        return render_template('partials/firewall_groups_content.html')
    except Exception as e:
        print(f"💥 /firewall/groups/content 예외 발생: {str(e)}")
        return render_template('partials/firewall_groups_content.html')

@bp.route('/firewall/group-detail/content')
@login_required
def firewall_group_detail_content():
    """방화벽 그룹 상세 콘텐츠 (기존 템플릿 호환)"""
    try:
        print("🔍 /firewall/group-detail/content 호출됨")
        group_name = request.args.get('group')
        return render_template('partials/firewall_group_detail_content.html', group_name=group_name)
    except Exception as e:
        print(f"💥 /firewall/group-detail/content 예외 발생: {str(e)}")
        return render_template('partials/firewall_group_detail_content.html', group_name='')

# 기존 템플릿에서 호출하는 API 엔드포인트들

# 호환성을 위한 API 엔드포인트들 (실제 로직은 servers.py에서 처리)
@bp.route('/all_server_status', methods=['GET'])
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
        from app.routes.api import get_users
        return get_users()
    except Exception as e:
        print(f"💥 /users 호환성 엔드포인트 오류: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/users', methods=['POST'])
@login_required
def create_user_compat():
    """사용자 생성 (호환성)"""
    try:
        from app.routes.api import create_user
        return create_user()
    except Exception as e:
        print(f"💥 /users POST 호환성 엔드포인트 오류: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/current-user', methods=['GET'])
@login_required
def get_current_user_compat():
    """현재 사용자 정보 조회 (호환성)"""
    try:
        from app.routes.api import get_current_user
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
        from app.routes.api import get_notifications
        return get_notifications()
    except Exception as e:
        print(f"💥 알림 목록 조회 오류: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/notifications/<int:notification_id>/read', methods=['POST'])
@login_required
def mark_notification_read_compat(notification_id):
    """알림 읽음 표시 (호환성)"""
    try:
        from app.routes.api import mark_notification_read
        return mark_notification_read(notification_id)
    except Exception as e:
        print(f"💥 알림 읽음 표시 오류: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/notifications/unread-count', methods=['GET'])
@login_required
def get_unread_notification_count_compat():
    """읽지 않은 알림 개수 (호환성)"""
    try:
        from app.routes.api import get_unread_notification_count
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
        from app.routes.api import clear_all_notifications
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

@bp.route('/create_server', methods=['POST'])
@login_required
def create_server_compat():
    """서버 생성 (호환성)"""
    try:
        from app.routes.servers import create_server
        return create_server()
    except Exception as e:
        print(f"💥 서버 생성 호환성 엔드포인트 오류: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/admin/iam', methods=['GET'])
@login_required
def admin_iam_compat():
    """관리자 IAM (호환성)"""
    try:
        from app.routes.api import admin_iam_api
        return admin_iam_api()
    except Exception as e:
        print(f"💥 관리자 IAM 호환성 엔드포인트 오류: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/server_status/<server_name>', methods=['GET'])
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

@bp.route('/start_server/<server_name>', methods=['POST'])
@login_required
def start_server_compat(server_name):
    """서버 시작 (호환성)"""
    try:
        from app.routes.servers import start_server
        return start_server(server_name)
    except Exception as e:
        print(f"💥 서버 시작 호환성 엔드포인트 오류: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/stop_server/<server_name>', methods=['POST'])
@login_required
def stop_server_compat(server_name):
    """서버 중지 (호환성)"""
    try:
        from app.routes.servers import stop_server
        return stop_server(server_name)
    except Exception as e:
        print(f"💥 서버 중지 호환성 엔드포인트 오류: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/reboot_server/<server_name>', methods=['POST'])
@login_required
def reboot_server_compat(server_name):
    """서버 재부팅 (호환성)"""
    try:
        from app.routes.servers import reboot_server
        return reboot_server(server_name)
    except Exception as e:
        print(f"💥 서버 재부팅 호환성 엔드포인트 오류: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/delete_server/<server_name>', methods=['POST'])
@login_required
def delete_server_compat(server_name):
    """서버 삭제 (호환성)"""
    try:
        from app.routes.servers import delete_server
        return delete_server(server_name)
    except Exception as e:
        print(f"💥 서버 삭제 호환성 엔드포인트 오류: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/assign_role/<server_name>', methods=['POST'])
@login_required
def assign_role_compat(server_name):
    """역할 할당 (호환성)"""
    try:
        from app.routes.api import assign_role
        return assign_role(server_name)
    except Exception as e:
        print(f"💥 역할 할당 호환성 엔드포인트 오류: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/remove_role/<server_name>', methods=['POST'])
@login_required
def remove_role_compat(server_name):
    """역할 제거 (호환성)"""
    try:
        from app.routes.api import remove_role
        return remove_role(server_name)
    except Exception as e:
        print(f"💥 역할 제거 호환성 엔드포인트 오류: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/assign_firewall_group/<server_name>', methods=['POST'])
@login_required
def assign_firewall_group_compat(server_name):
    """방화벽 그룹 할당 (호환성)"""
    try:
        from app.routes.firewall import assign_firewall_group
        return assign_firewall_group(server_name)
    except Exception as e:
        print(f"💥 방화벽 그룹 할당 호환성 엔드포인트 오류: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/remove_firewall_group/<server_name>', methods=['POST'])
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
        from app.routes.servers import get_all_server_status
        return get_all_server_status()
    except Exception as e:
        print(f"💥 멀티 서버 요약 호환성 엔드포인트 오류: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/favicon.ico')
def favicon():
    """파비콘"""
    return send_from_directory('static', 'favicon.ico')

@bp.route('/proxmox_storage', methods=['GET'])
def proxmox_storage():
    """Proxmox 스토리지 정보 (호환성)"""
    try:
        from app.routes.servers import proxmox_storage as api_proxmox_storage
        return api_proxmox_storage()
    except Exception as e:
        print(f"💥 Proxmox 스토리지 호환성 엔드포인트 오류: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/sync_servers', methods=['POST'])
@login_required
def sync_servers_compat():
    """서버 동기화 (호환성)"""
    try:
        from app.routes.servers import sync_servers as api_sync_servers
        return api_sync_servers()
    except Exception as e:
        print(f"💥 서버 동기화 호환성 엔드포인트 오류: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/tasks/status')
def get_task_status_compat():
    """Task 상태 조회 (호환성)"""
    try:
        from app.routes.servers import get_task_status
        return get_task_status()
    except Exception as e:
        print(f"💥 Task 상태 조회 호환성 엔드포인트 오류: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/debug/user-info', methods=['GET'])
@login_required
def debug_user_info_compat():
    """디버깅용 사용자 정보 (호환성)"""
    try:
        from app.routes.api import debug_user_info
        return debug_user_info()
    except Exception as e:
        print(f"💥 /debug/user-info 호환성 엔드포인트 오류: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/debug/servers', methods=['GET'])
@login_required
def debug_servers_compat():
    """서버 디버깅 정보 (호환성)"""
    try:
        from app.routes.api import debug_servers
        return debug_servers()
    except Exception as e:
        print(f"💥 /debug/servers 호환성 엔드포인트 오류: {str(e)}")
        return jsonify({'error': str(e)}), 500 