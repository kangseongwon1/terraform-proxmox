"""
서버 관리 관련 라우트
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app.models.server import Server
from app.services.proxmox_service import ProxmoxService
from app.services.terraform_service import TerraformService
from app.services.ansible_service import AnsibleService
from app.services.notification_service import NotificationService
from app import db
import logging
import threading
import time
from functools import wraps

logger = logging.getLogger(__name__)

bp = Blueprint('servers', __name__, url_prefix='/servers')

def permission_required(permission):
    """권한 확인 데코레이터"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('로그인이 필요합니다.', 'error')
                return redirect(url_for('auth.login'))
            
            if not current_user.has_permission(permission):
                flash('권한이 없습니다.', 'error')
                return redirect(url_for('main.index'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

@bp.route('/')
@login_required
@permission_required('view_all')
def index():
    """서버 목록"""
    servers = Server.query.all()
    return render_template('servers/index.html', servers=servers)

@bp.route('/create', methods=['GET', 'POST'])
@login_required
@permission_required('create_server')
def create():
    """서버 생성"""
    if request.method == 'POST':
        server_data = {
            'name': request.form.get('name'),
            'role': request.form.get('role'),
            'cpu': int(request.form.get('cpu', 2)),
            'memory': int(request.form.get('memory', 4096)),
            'os_type': request.form.get('os_type', 'ubuntu-22.04'),
            'template_vm_id': int(request.form.get('template_vm_id', 9000)),
            'disks': [{
                'size': int(request.form.get('disk_size', 50)),
                'interface': 'scsi0',
                'datastore_id': request.form.get('datastore_id', 'local-lvm')
            }],
            'network_devices': [{
                'bridge': 'vmbr0',
                'ip_address': request.form.get('ip_address'),
                'subnet': int(request.form.get('subnet', 24)),
                'gateway': request.form.get('gateway', '192.168.1.1')
            }]
        }
        
        # 서버 생성 작업을 백그라운드에서 실행
        def create_server_background():
            try:
                # Terraform 설정 생성
                terraform_service = TerraformService()
                if not terraform_service.create_server_config(server_data):
                    raise Exception("Terraform 설정 생성 실패")
                
                # 인프라 배포
                success, message = terraform_service.deploy_infrastructure()
                if not success:
                    raise Exception(f"인프라 배포 실패: {message}")
                
                # 서버 정보 저장
                server = Server(
                    name=server_data['name'],
                    role=server_data['role'],
                    cpu=server_data['cpu'],
                    memory=server_data['memory'],
                    os_type=server_data['os_type'],
                    status='creating'
                )
                db.session.add(server)
                db.session.commit()
                
                # Proxmox에서 VM 정보 동기화
                proxmox_service = ProxmoxService()
                proxmox_service.sync_vm_data()
                
                # 알림 생성
                NotificationService.create_server_notification(
                    server_data['name'], 'create', 'success'
                )
                
            except Exception as e:
                logger.error(f"서버 생성 실패: {e}")
                NotificationService.create_server_notification(
                    server_data['name'], 'create', 'error', str(e)
                )
        
        thread = threading.Thread(target=create_server_background)
        thread.start()
        
        flash('서버 생성이 시작되었습니다.', 'info')
        return redirect(url_for('servers.index'))
    
    return render_template('servers/create.html')

@bp.route('/<int:server_id>')
@login_required
@permission_required('view_all')
def detail(server_id):
    """서버 상세 정보"""
    server = Server.query.get_or_404(server_id)
    return render_template('servers/detail.html', server=server)

@bp.route('/<int:server_id>/start', methods=['POST'])
@login_required
@permission_required('start_server')
def start(server_id):
    """서버 시작"""
    server = Server.query.get_or_404(server_id)
    
    try:
        proxmox_service = ProxmoxService()
        if server.vmid and proxmox_service.vm_action(server.vmid, 'start'):
            server.update_status('running')
            NotificationService.create_server_notification(
                server.name, 'start', 'success'
            )
            return jsonify({'message': '서버가 시작되었습니다.'})
        else:
            raise Exception("서버 시작 실패")
    except Exception as e:
        logger.error(f"서버 시작 실패: {e}")
        NotificationService.create_server_notification(
            server.name, 'start', 'error', str(e)
        )
        return jsonify({'error': '서버 시작 중 오류가 발생했습니다.'}), 500

@bp.route('/<int:server_id>/stop', methods=['POST'])
@login_required
@permission_required('stop_server')
def stop(server_id):
    """서버 중지"""
    server = Server.query.get_or_404(server_id)
    
    try:
        proxmox_service = ProxmoxService()
        if server.vmid and proxmox_service.vm_action(server.vmid, 'stop'):
            server.update_status('stopped')
            NotificationService.create_server_notification(
                server.name, 'stop', 'success'
            )
            return jsonify({'message': '서버가 중지되었습니다.'})
        else:
            raise Exception("서버 중지 실패")
    except Exception as e:
        logger.error(f"서버 중지 실패: {e}")
        NotificationService.create_server_notification(
            server.name, 'stop', 'error', str(e)
        )
        return jsonify({'error': '서버 중지 중 오류가 발생했습니다.'}), 500

@bp.route('/<int:server_id>/reboot', methods=['POST'])
@login_required
@permission_required('reboot_server')
def reboot(server_id):
    """서버 재부팅"""
    server = Server.query.get_or_404(server_id)
    
    try:
        proxmox_service = ProxmoxService()
        if server.vmid and proxmox_service.vm_action(server.vmid, 'reset'):
            NotificationService.create_server_notification(
                server.name, 'reboot', 'success'
            )
            return jsonify({'message': '서버가 재부팅되었습니다.'})
        else:
            raise Exception("서버 재부팅 실패")
    except Exception as e:
        logger.error(f"서버 재부팅 실패: {e}")
        NotificationService.create_server_notification(
            server.name, 'reboot', 'error', str(e)
        )
        return jsonify({'error': '서버 재부팅 중 오류가 발생했습니다.'}), 500

@bp.route('/<int:server_id>/delete', methods=['POST'])
@login_required
@permission_required('delete_server')
def delete(server_id):
    """서버 삭제"""
    server = Server.query.get_or_404(server_id)
    
    def delete_server_background():
        try:
            # Terraform으로 인프라 삭제
            terraform_service = TerraformService()
            success, message = terraform_service.destroy_infrastructure(server.name)
            
            if success:
                # 데이터베이스에서 서버 삭제
                db.session.delete(server)
                db.session.commit()
                
                NotificationService.create_server_notification(
                    server.name, 'delete', 'success'
                )
            else:
                raise Exception(f"인프라 삭제 실패: {message}")
                
        except Exception as e:
            logger.error(f"서버 삭제 실패: {e}")
            NotificationService.create_server_notification(
                server.name, 'delete', 'error', str(e)
            )
    
    thread = threading.Thread(target=delete_server_background)
    thread.start()
    
    return jsonify({'message': '서버 삭제가 시작되었습니다.'})

@bp.route('/<int:server_id>/assign-role', methods=['POST'])
@login_required
@permission_required('assign_roles')
def assign_role(server_id):
    """서버 역할 할당"""
    server = Server.query.get_or_404(server_id)
    role = request.json.get('role')
    
    if not role:
        return jsonify({'error': '역할이 필요합니다.'}), 400
    
    try:
        server.role = role
        db.session.commit()
        
        # Ansible로 역할 적용
        ansible_service = AnsibleService()
        if server.ip_address:
            success, message = ansible_service.run_role_for_server(
                server.name, role
            )
            if success:
                NotificationService.create_notification(
                    'server_role', f'역할 할당 완료', 
                    f'서버 {server.name}에 {role} 역할이 적용되었습니다.',
                    severity='success'
                )
            else:
                NotificationService.create_notification(
                    'server_role', f'역할 적용 실패', 
                    f'서버 {server.name}에 {role} 역할 적용 중 오류가 발생했습니다.',
                    severity='error'
                )
        
        return jsonify({'message': '역할이 할당되었습니다.'})
    except Exception as e:
        logger.error(f"역할 할당 실패: {e}")
        return jsonify({'error': '역할 할당 중 오류가 발생했습니다.'}), 500

@bp.route('/status')
@login_required
@permission_required('view_all')
def status():
    """서버 상태 조회"""
    servers = Server.query.all()
    return jsonify([server.to_dict() for server in servers]) 