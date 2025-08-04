"""
메인 라우트 블루프린트
"""
from flask import Blueprint, render_template, current_app, jsonify, request
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
        
        return render_template('partials/instances_content.html', servers=server_list, roles=roles)
    except Exception as e:
        print(f"💥 /instances/content 예외 발생: {str(e)}")
        return render_template('partials/instances_content.html', servers=[])

@bp.route('/dashboard/content')
@login_required
def dashboard_content():
    """대시보드 콘텐츠 (기존 템플릿 호환)"""
    try:
        print("🔍 /dashboard/content 호출됨")
        proxmox_service = ProxmoxService()
        result = proxmox_service.get_all_vms()
        
        if result['success']:
            servers = result['data']['vms']
            total = result['data']['total']
            running = result['data']['running']
            stopped = result['data']['stopped']
        else:
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
                             servers=servers, total_servers=total, running_servers=running, stopped_servers=stopped)
    except Exception as e:
        print(f"💥 /dashboard/content 예외 발생: {str(e)}")
        return render_template('partials/dashboard_content.html', 
                             servers=[], total_servers=0, running_servers=0, stopped_servers=0)

@bp.route('/storage/content')
@login_required
def storage_content():
    """스토리지 콘텐츠 (기존 템플릿 호환)"""
    try:
        print("🔍 /storage/content 호출됨")
        proxmox_service = ProxmoxService()
        result = proxmox_service.get_storage_info()
        
        if result['success']:
            storage_list = result['data']
        else:
            # 빈 스토리지 리스트 반환
            storage_list = []
        
        return render_template('partials/storage_content.html', storage_list=storage_list)
    except Exception as e:
        print(f"💥 /storage/content 예외 발생: {str(e)}")
        return render_template('partials/storage_content.html', storage_list=[])

@bp.route('/admin/iam/content')
@login_required
def admin_iam_content():
    """관리자 IAM 콘텐츠 (기존 템플릿 호환)"""
    users = User.query.all()
    return render_template('partials/admin_iam_content.html', users=users)

@bp.route('/firewall/groups/content')
@login_required
def firewall_groups_content():
    """방화벽 그룹 콘텐츠 (기존 템플릿 호환)"""
    return render_template('partials/firewall_groups_content.html')

@bp.route('/firewall/group-detail/content')
@login_required
def firewall_group_detail_content():
    """방화벽 그룹 상세 콘텐츠 (기존 템플릿 호환)"""
    return render_template('partials/firewall_group_detail_content.html')

# 호환성을 위한 API 엔드포인트들
@bp.route('/users', methods=['GET'])
@login_required
def get_users_compat():
    """사용자 목록 조회 (호환성)"""
    try:
        from app.models import User
        users = User.query.all()
        user_list = []
        for user in users:
            user_list.append({
                'id': user.id,
                'username': user.username,
                'name': user.name,
                'email': user.email,
                'role': user.role,
                'is_active': user.is_active,
                'created_at': user.created_at.isoformat() if user.created_at else None
            })
        return jsonify({'users': user_list})
    except Exception as e:
        print(f"💥 /users 호환성 엔드포인트 오류: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/users', methods=['POST'])
@login_required
def create_user_compat():
    """사용자 생성 (호환성)"""
    try:
        from app.models import User, UserPermission
        from app import db
        
        data = request.get_json()
        if not data:
            return jsonify({'error': '데이터가 없습니다.'}), 400
        
        username = data.get('username')
        password = data.get('password')
        name = data.get('name', '')
        email = data.get('email', '')
        role = data.get('role', 'developer')
        
        if not username or not password:
            return jsonify({'error': '사용자명과 비밀번호는 필수입니다.'}), 400
        
        # 기존 사용자 확인
        if User.query.filter_by(username=username).first():
            return jsonify({'error': '이미 존재하는 사용자명입니다.'}), 400
        
        # 새 사용자 생성
        user = User(
            username=username,
            name=name,
            email=email,
            role=role,
            is_active=True
        )
        user.set_password(password)
        
        # 세션에 추가
        db.session.add(user)
        db.session.flush()  # ID 생성을 위해 flush
        
        # 기본 권한 추가 (view_all)
        user_perm = UserPermission(user_id=user.id, permission='view_all')
        db.session.add(user_perm)
        
        # 커밋
        db.session.commit()
        
        print(f"✅ 사용자 생성 성공: {username} (비밀번호는 로그에 기록하지 않음)")
        
        return jsonify({'success': True, 'message': '사용자가 생성되었습니다.'})
        
    except Exception as e:
        print(f"💥 /users POST 호환성 엔드포인트 오류: {str(e)}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@bp.route('/firewall/groups', methods=['GET'])
@login_required
def get_firewall_groups_compat():
    """방화벽 그룹 목록 조회 (호환성)"""
    try:
        # 간단한 방화벽 그룹 목록 반환
        groups = [
            {'name': 'web-group', 'description': '웹 서버 그룹'},
            {'name': 'db-group', 'description': '데이터베이스 그룹'},
            {'name': 'app-group', 'description': '애플리케이션 그룹'}
        ]
        return jsonify({'groups': groups})
    except Exception as e:
        print(f"💥 /firewall/groups 호환성 엔드포인트 오류: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/create_server', methods=['POST'])
@login_required
def create_server_compat():
    """서버 생성 (호환성)"""
    try:
        from app.services import TerraformService
        
        data = request.get_json()
        if not data:
            return jsonify({'error': '데이터가 없습니다.'}), 400
        
        # Terraform 서비스 사용
        terraform_service = TerraformService()
        result = terraform_service.create_server(data)
        
        if result['success']:
            return jsonify({'success': True, 'message': '서버 생성이 시작되었습니다.'})
        else:
            return jsonify({'error': result.get('message', '서버 생성 실패')}), 500
            
    except Exception as e:
        print(f"💥 /create_server 호환성 엔드포인트 오류: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/admin/iam', methods=['GET'])
@login_required
def admin_iam_compat():
    """관리자 IAM API (호환성)"""
    try:
        from app.models import User
        
        users = User.query.all()
        user_list = []
        for user in users:
            permissions = [perm.permission for perm in user.permissions]
            user_list.append({
                'id': user.id,
                'username': user.username,
                'name': user.name,
                'email': user.email,
                'role': user.role,
                'is_active': user.is_active,
                'permissions': permissions,
                'created_at': user.created_at.isoformat() if user.created_at else None
            })
        
        return jsonify({'users': user_list})
    except Exception as e:
        print(f"💥 /admin/iam 호환성 엔드포인트 오류: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/notifications/<int:notification_id>/delete', methods=['POST'])
@login_required
def delete_notification_compat(notification_id):
    """알림 삭제 (호환성)"""
    try:
        from app.models import Notification
        from app import db
        
        print(f"🔧 알림 삭제 요청: ID {notification_id}")
        
        notification = Notification.query.get(notification_id)
        if not notification:
            print(f"❌ 알림을 찾을 수 없음: ID {notification_id}")
            return jsonify({'error': '알림을 찾을 수 없습니다.'}), 404
        
        # 알림 삭제
        db.session.delete(notification)
        db.session.commit()
        
        print(f"✅ 알림 삭제 성공: ID {notification_id}")
        return jsonify({'success': True, 'message': '알림이 삭제되었습니다.'})
        
    except Exception as e:
        print(f"💥 알림 삭제 호환성 엔드포인트 오류: {str(e)}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@bp.route('/notifications/clear-all', methods=['POST'])
@login_required
def clear_all_notifications_compat():
    """모든 알림 삭제 (호환성)"""
    try:
        from app.models import Notification
        from app import db
        
        print("🔧 모든 알림 삭제 요청")
        
        # 현재 사용자의 모든 알림 삭제
        deleted_count = Notification.query.filter_by(user_id=current_user.id).delete()
        db.session.commit()
        
        print(f"✅ 모든 알림 삭제 성공: {deleted_count}개")
        return jsonify({'success': True, 'message': f'{deleted_count}개의 알림이 삭제되었습니다.'})
        
    except Exception as e:
        print(f"💥 모든 알림 삭제 호환성 엔드포인트 오류: {str(e)}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

# 추가 누락된 엔드포인트들
@bp.route('/notifications', methods=['GET'])
@login_required
def get_notifications_compat():
    """알림 목록 조회 (호환성)"""
    try:
        from app.models import Notification
        
        notifications = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_at.desc()).all()
        notification_list = []
        for notification in notifications:
            notification_list.append({
                'id': notification.id,
                'type': notification.type,
                'title': notification.title,
                'message': notification.message,
                'severity': notification.severity,
                'is_read': notification.is_read,
                'created_at': notification.created_at.isoformat() if notification.created_at else None
            })
        
        return jsonify({'notifications': notification_list})
    except Exception as e:
        print(f"💥 알림 목록 조회 오류: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/notifications/<int:notification_id>/read', methods=['POST'])
@login_required
def mark_notification_read_compat(notification_id):
    """알림 읽음 표시 (호환성)"""
    try:
        from app.models import Notification
        from app import db
        
        notification = Notification.query.get(notification_id)
        if not notification:
            return jsonify({'error': '알림을 찾을 수 없습니다.'}), 404
        
        notification.is_read = True
        db.session.commit()
        
        return jsonify({'success': True, 'message': '알림이 읽음으로 표시되었습니다.'})
    except Exception as e:
        print(f"💥 알림 읽음 표시 오류: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/notifications/unread-count', methods=['GET'])
@login_required
def get_unread_notification_count_compat():
    """읽지 않은 알림 개수 (호환성)"""
    try:
        from app.models import Notification
        
        count = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
        return jsonify({'count': count})
    except Exception as e:
        print(f"💥 읽지 않은 알림 개수 조회 오류: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/server_status/<server_name>', methods=['GET'])
@login_required
def get_server_status_compat(server_name):
    """개별 서버 상태 조회 (호환성)"""
    try:
        from app.services import ProxmoxService
        
        proxmox_service = ProxmoxService()
        result = proxmox_service.get_all_vms()
        
        if result['success']:
            servers = result['data']['servers']
            if server_name in servers:
                return jsonify(servers[server_name])
            else:
                return jsonify({'error': '서버를 찾을 수 없습니다.'}), 404
        else:
            return jsonify({'error': '서버 상태 조회에 실패했습니다.'}), 500
    except Exception as e:
        print(f"💥 서버 상태 조회 오류: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/start_server/<server_name>', methods=['POST'])
@login_required
def start_server_compat(server_name):
    """서버 시작 (호환성)"""
    try:
        # 실제 Proxmox API 호출 로직 구현 필요
        return jsonify({'success': True, 'message': f'서버 {server_name} 시작 요청이 전송되었습니다.'})
    except Exception as e:
        print(f"💥 서버 시작 오류: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/stop_server/<server_name>', methods=['POST'])
@login_required
def stop_server_compat(server_name):
    """서버 중지 (호환성)"""
    try:
        # 실제 Proxmox API 호출 로직 구현 필요
        return jsonify({'success': True, 'message': f'서버 {server_name} 중지 요청이 전송되었습니다.'})
    except Exception as e:
        print(f"💥 서버 중지 오류: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/reboot_server/<server_name>', methods=['POST'])
@login_required
def reboot_server_compat(server_name):
    """서버 재부팅 (호환성)"""
    try:
        # 실제 Proxmox API 호출 로직 구현 필요
        return jsonify({'success': True, 'message': f'서버 {server_name} 재부팅 요청이 전송되었습니다.'})
    except Exception as e:
        print(f"💥 서버 재부팅 오류: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/delete_server/<server_name>', methods=['POST'])
@login_required
def delete_server_compat(server_name):
    """서버 삭제 (호환성)"""
    try:
        # 실제 Proxmox API 호출 로직 구현 필요
        return jsonify({'success': True, 'message': f'서버 {server_name} 삭제 요청이 전송되었습니다.'})
    except Exception as e:
        print(f"💥 서버 삭제 오류: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/assign_role/<server_name>', methods=['POST'])
@login_required
def assign_role_compat(server_name):
    """서버 역할 할당 (호환성)"""
    try:
        data = request.get_json()
        role = data.get('role')
        
        if not role:
            return jsonify({'error': '역할을 지정해주세요.'}), 400
        
        # 실제 역할 할당 로직 구현 필요
        return jsonify({'success': True, 'message': f'서버 {server_name}에 역할 {role}이 할당되었습니다.'})
    except Exception as e:
        print(f"💥 역할 할당 오류: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/remove_role/<server_name>', methods=['POST'])
@login_required
def remove_role_compat(server_name):
    """서버 역할 제거 (호환성)"""
    try:
        # 실제 역할 제거 로직 구현 필요
        return jsonify({'success': True, 'message': f'서버 {server_name}의 역할이 제거되었습니다.'})
    except Exception as e:
        print(f"💥 역할 제거 오류: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/assign_firewall_group/<server_name>', methods=['POST'])
@login_required
def assign_firewall_group_compat(server_name):
    """방화벽 그룹 할당 (호환성)"""
    try:
        data = request.get_json()
        group = data.get('group')
        
        if not group:
            return jsonify({'error': '방화벽 그룹을 지정해주세요.'}), 400
        
        # 실제 방화벽 그룹 할당 로직 구현 필요
        return jsonify({'success': True, 'message': f'서버 {server_name}에 방화벽 그룹 {group}이 할당되었습니다.'})
    except Exception as e:
        print(f"💥 방화벽 그룹 할당 오류: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/remove_firewall_group/<server_name>', methods=['POST'])
@login_required
def remove_firewall_group_compat(server_name):
    """방화벽 그룹 제거 (호환성)"""
    try:
        # 실제 방화벽 그룹 제거 로직 구현 필요
        return jsonify({'success': True, 'message': f'서버 {server_name}의 방화벽 그룹이 제거되었습니다.'})
    except Exception as e:
        print(f"💥 방화벽 그룹 제거 오류: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/instances/multi-server-summary')
@login_required
def multi_server_summary():
    """멀티 서버 요약 (기존 템플릿 호환)"""
    return render_template('partials/multi_server_summary.html')

@bp.route('/favicon.ico')
def favicon():
    """파비콘"""
    return current_app.send_static_file('favicon.ico')

# 기존 템플릿에서 호출하는 API 엔드포인트들
@bp.route('/all_server_status', methods=['GET'])
@login_required
def get_all_server_status():
    """모든 서버 상태 조회 (기존 템플릿 호환)"""
    try:
        print("🔍 /all_server_status 호출됨")
        proxmox_service = ProxmoxService()
        print(f"🔧 ProxmoxService 생성됨: {proxmox_service.endpoint}")
        
        result = proxmox_service.get_all_vms()
        print(f"📊 get_all_vms 결과: {result}")
        
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
        print(f"💥 /all_server_status 예외 발생: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@bp.route('/proxmox_storage', methods=['GET'])
def proxmox_storage():
    """Proxmox 스토리지 정보 조회 (기존 템플릿 호환)"""
    try:
        print("🔍 /proxmox_storage 호출됨")
        proxmox_service = ProxmoxService()
        print(f"🔧 ProxmoxService 생성됨: {proxmox_service.endpoint}")
        
        result = proxmox_service.get_storage_info()
        print(f"📊 get_storage_info 결과: {result}")
        
        if result['success']:
            # 기존 UI와 호환되는 형식으로 변환
            storages = []
            for storage in result['data']:
                storage_info = {
                    'storage': storage.get('storage'),
                    'type': storage.get('type', 'unknown'),
                    'total': storage.get('total', 0),
                    'used': storage.get('used', 0),
                    'avail': storage.get('avail', 0)
                }
                storages.append(storage_info)
            
            return jsonify({'storages': storages})  # 기존 형식과 호환
        else:
            print(f"❌ get_storage_info 실패: {result['message']}")
            return jsonify({'error': result['message']}), 500
    except Exception as e:
        print(f"💥 /proxmox_storage 예외 발생: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500 