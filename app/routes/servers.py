"""
서버 관리 관련 라우트
"""
from flask import Blueprint, request, jsonify, render_template, current_app
from flask_login import login_required, current_user
from functools import wraps
from app.models import Server, User, UserPermission
from app.services import ProxmoxService, TerraformService, AnsibleService, NotificationService
from app.utils.os_classifier import classify_os_type, get_default_username, get_default_password
from app import db
import json
import os
import subprocess
import threading
import time
import uuid
import logging
from datetime import datetime
from app.routes.auth import permission_required

# 로거 설정
logger = logging.getLogger(__name__)

bp = Blueprint('servers', __name__)


# 전역 작업 상태 dict
tasks = {}

def _remove_from_known_hosts(ip_address: str) -> bool:
    """SSH known_hosts 파일에서 특정 IP 제거"""
    try:
        # 사용자 홈 디렉토리의 .ssh/known_hosts 파일 경로
        home_dir = os.path.expanduser('~')
        known_hosts_path = os.path.join(home_dir, '.ssh', 'known_hosts')
        
        if not os.path.exists(known_hosts_path):
            logger.info(f"known_hosts 파일이 존재하지 않음: {known_hosts_path}")
            return True
        
        # ssh-keygen 명령어로 해당 IP의 키 제거
        try:
            result = subprocess.run([
                'ssh-keygen', '-R', ip_address
            ], capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                logger.info(f"ssh-keygen으로 {ip_address} 제거 성공")
                return True
            else:
                logger.warning(f"ssh-keygen 실행 결과: {result.stderr}")
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            logger.warning(f"ssh-keygen 실행 실패: {e}")
        
        # ssh-keygen이 실패하면 수동으로 파일 편집
        try:
            logger.info(f"🔧 수동으로 known_hosts에서 {ip_address} 제거 시도...")
            
            # 백업 파일 생성
            backup_path = f"{known_hosts_path}.backup.{int(time.time())}"
            subprocess.run(['cp', known_hosts_path, backup_path], check=True)
            
            # 해당 IP가 포함된 라인 제거
            with open(known_hosts_path, 'r') as f:
                lines = f.readlines()
            
            # IP가 포함되지 않은 라인들만 유지
            filtered_lines = []
            removed_count = 0
            
            for line in lines:
                if ip_address not in line:
                    filtered_lines.append(line)
                else:
                    removed_count += 1
                    logger.info(f"🗑️ 제거된 라인: {line.strip()}")
            
            # 수정된 내용을 파일에 쓰기
            with open(known_hosts_path, 'w') as f:
                f.writelines(filtered_lines)
            
            logger.info(f"known_hosts 수동 편집 완료: {removed_count}개 라인 제거")
            return True
            
        except Exception as manual_error:
            logger.error(f"known_hosts 수동 편집 실패: {manual_error}")
            return False
            
    except Exception as e:
        logger.error(f"known_hosts 제거 중 오류: {e}")
        return False

def create_task(status, type, message):
    task_id = str(uuid.uuid4())
    tasks[task_id] = {
        'status': status, 
        'type': type, 
        'message': message,
        'created_at': time.time(),
        'timeout': 18000  # 5시간 타임아웃
    }
    logger.info(f"🔧 Task 생성: {task_id} - {status} - {message}")
    return task_id

def update_task(task_id, status, message=None):
    if task_id in tasks:
        tasks[task_id]['status'] = status
        if message:
            tasks[task_id]['message'] = message
        logger.info(f"🔧 Task 업데이트: {task_id} - {status} - {message}")
    else:
        logger.error(f"Task를 찾을 수 없음: {task_id}")

def check_task_timeout():
    """Task 타임아웃 체크"""
    current_time = time.time()
    for task_id, task_info in list(tasks.items()):
        if task_info['status'] == 'running':
            elapsed_time = current_time - task_info['created_at']
            if elapsed_time > task_info['timeout']:
                timeout_hours = task_info['timeout'] / 3600
                logger.info(f"⏰ Task 타임아웃: {task_id} (경과시간: {elapsed_time:.1f}초, 설정된 타임아웃: {timeout_hours:.1f}시간)")
                update_task(task_id, 'failed', f'작업 타임아웃 ({timeout_hours:.1f}시간 초과)')

@bp.route('/api/tasks/status')
def get_task_status():
    task_id = request.args.get('task_id')
    logger.info(f"🔍 Task 상태 조회: {task_id}")
    logger.info(f"📋 현재 Tasks: {list(tasks.keys())}")
    
    # 타임아웃 체크
    check_task_timeout()
    
    if not task_id:
        return jsonify({'error': 'task_id가 필요합니다.'}), 400
    
    if task_id not in tasks:
        logger.error(f"Task를 찾을 수 없음 (404): {task_id}")
        # 404 에러 시 task를 자동으로 종료 상태로 변경
        tasks[task_id] = {
            'status': 'failed', 
            'type': 'unknown', 
            'message': 'Task를 찾을 수 없어 자동 종료됨',
            'created_at': time.time(),
            'timeout': 18000
        }
        logger.info(f"🔧 Task 자동 종료 처리: {task_id}")
        return jsonify(tasks[task_id])
    
    return jsonify(tasks[task_id])

@bp.route('/api/tasks/config')
def get_task_config():
    """Task 설정 정보 제공 (타임아웃 등)"""
    return jsonify({
        'timeout': 18000,  # 5시간 (초 단위)
        'timeout_hours': 5,  # 5시간 (시간 단위)
        'polling_interval': 5000  # 폴링 간격 (밀리초 단위)
    })

@bp.route('/api/servers', methods=['GET'])
@permission_required('view_all')
def list_servers():
    """서버 목록 조회"""
    try:
        servers = Server.query.all()
        return jsonify({
            'success': True,
            'servers': [server.to_dict() for server in servers]
        })
    except Exception as e:
        logger.error(f"서버 목록 조회 실패: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/servers/brief', methods=['GET'])
@permission_required('view_all')
def get_servers_brief():
    """지정한 서버들의 경량 정보(역할/보안그룹/OS/IP)만 반환"""
    try:
        names_param = request.args.get('names', '')
        if not names_param:
            return jsonify({'success': True, 'servers': {}})
        names = [n.strip() for n in names_param.split(',') if n.strip()]
        if not names:
            return jsonify({'success': True, 'servers': {}})

        servers = Server.query.filter(Server.name.in_(names)).all()
        result = {}
        for s in servers:
            result[s.name] = {
                'name': s.name,
                'role': s.role or '',
                'firewall_group': s.firewall_group,
                'os_type': s.os_type,
                'ip_addresses': [s.ip_address] if s.ip_address else []
            }
        return jsonify({'success': True, 'servers': result})
    except Exception as e:
        logger.error(f"경량 서버 정보 조회 실패: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/debug/servers', methods=['GET'])
@login_required
def debug_servers():
    """서버 디버깅 정보"""
    try:
        servers = Server.query.all()
        debug_info = []
        for server in servers:
            debug_info.append({
                'id': server.id,
                'name': server.name,
                'vmid': server.vmid,
                'status': server.status,
                'role': server.role,
                'firewall_group': server.firewall_group,
                'created_at': str(server.created_at) if server.created_at else None,
                'updated_at': str(server.updated_at) if server.updated_at else None
            })
        return jsonify({
            'success': True,
            'servers': debug_info
        })
    except Exception as e:
        logger.error(f"서버 디버깅 정보 조회 실패: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/servers', methods=['POST'])
@permission_required('create_server')
def create_server():
    """서버 생성"""
    try:
        data = request.get_json()
        server_name = data.get('name')
        cpu = data.get('cpu', 2)
        memory = data.get('memory', 2048)
        role = data.get('role', '')
        disks = data.get('disks', [])
        network_devices = data.get('network_devices', [])
        template_vm_id = data.get('template_vm_id', 8000)
        vm_username = data.get('vm_username', 'rocky')
        vm_password = data.get('vm_password', 'rocky123')
        
        # IP 주소를 network_devices에서 추출
        ip_address = ''
        if network_devices:
            ip_addresses = [device.get('ip_address', '') for device in network_devices if device.get('ip_address')]
            ip_address = ', '.join(ip_addresses) if ip_addresses else ''
        
        if not server_name:
            return jsonify({'error': '서버 이름이 필요합니다.'}), 400
        
        # 서버 이름 중복 확인
        existing_server = Server.query.filter_by(name=server_name).first()
        if existing_server:
            return jsonify({'error': '이미 존재하는 서버 이름입니다.'}), 400
        
        # Task 생성
        task_id = create_task('running', 'create_server', f'서버 {server_name} 생성 중...')
        
        def create_server_task():
            try:
                from app import create_app
                app = create_app()
                with app.app_context():
                    logger.info(f"🔧 서버 생성 작업 시작: {server_name}")
                    
                    # Terraform 서비스 초기화
                    terraform_service = TerraformService()
                    
                    # Proxmox 서비스 초기화
                    proxmox_service = ProxmoxService()
                    
                    # 템플릿 이름 가져오기 (template_vm_id가 있는 경우)
                    template_name = 'rocky-9-template'  # 기본값
                    if template_vm_id:
                        try:
                            # Proxmox에서 템플릿 정보 조회
                            headers, error = proxmox_service.get_proxmox_auth()
                            if not error:
                                vms, vm_error = proxmox_service.get_proxmox_vms(headers)
                                if not vm_error:
                                    for vm in vms:
                                        if vm.get('vmid') == template_vm_id:
                                            template_name = vm.get('name', 'rocky-9-template')
                                            break
                        except Exception as e:
                            logger.warning(f"템플릿 정보 조회 실패: {e}")
                            template_name = 'rocky-9-template'
                    
                    # OS 타입 동적 분류
                    os_type = classify_os_type(template_name)
                    
                    # 기본 사용자명/비밀번호 설정 (사용자가 입력하지 않은 경우)
                    current_vm_username = vm_username if vm_username else get_default_username(os_type)
                    current_vm_password = vm_password if vm_password else get_default_password(os_type)
                    
                    # 서버 설정 생성
                    # .env 파일을 직접 읽어오는 함수
                    def load_env_file():
                        """프로젝트 루트의 .env 파일을 직접 읽어서 딕셔너리로 반환"""
                        env_vars = {}
                        try:
                            # 프로젝트 루트 경로 찾기 (app/routes/servers.py -> app -> project_root)
                            current_dir = os.path.dirname(os.path.abspath(__file__))
                            project_root = os.path.dirname(os.path.dirname(current_dir))
                            env_file = os.path.join(project_root, '.env')
                            
                            if os.path.exists(env_file):
                                with open(env_file, 'r', encoding='utf-8') as f:
                                    for line in f:
                                        line = line.strip()
                                        if line and not line.startswith('#') and '=' in line:
                                            key, value = line.split('=', 1)
                                            env_vars[key.strip()] = value.strip()
                                print(f"🔧 .env 파일 로드 성공: {env_file}")
                            else:
                                print(f"⚠️ .env 파일을 찾을 수 없습니다: {env_file}")
                            
                            return env_vars
                        except Exception as e:
                            print(f"⚠️ .env 파일 읽기 실패: {e}")
                            return {}

                    # 사용법
                    env_vars = load_env_file()
                    hdd_datastore = env_vars.get('PROXMOX_HDD_DATASTORE')
                    ssd_datastore = env_vars.get('PROXMOX_SSD_DATASTORE')

                    logger.info(f"🔧 .env에서 읽은 datastore 설정:")
                    logger.info(f"   PROXMOX_HDD_DATASTORE: {hdd_datastore}")
                    logger.info(f"   PROXMOX_SSD_DATASTORE: {ssd_datastore}")

                    # 디스크 설정 전 상태 로그
                    logger.info(f"🔧 디스크 설정 전 상태:")
                    for i, disk in enumerate(disks):
                        logger.info(f"   디스크 {i}: {disk}")

                    # 디스크 설정에 datastore 자동 설정
                    for i, disk in enumerate(disks):
                        logger.info(f"🔧 디스크 {i} 처리 시작: {disk}")
                        
                        if 'disk_type' not in disk:
                            disk['disk_type'] = 'hdd'
                            logger.info(f"🔧 디스크 {i}: disk_type을 'hdd'로 설정")
                        if 'file_format' not in disk:
                            disk['file_format'] = 'auto'
                            logger.info(f"🔧 디스크 {i}: file_format을 'auto'로 설정")
                        
                        # datastore_id가 없으면 "auto"로 설정 (Terraform에서 환경변수 사용)
                        if 'datastore_id' not in disk:
                            disk['datastore_id'] = 'auto'
                            logger.info(f"🔧 디스크 {i}: datastore_id를 'auto'로 설정 (Terraform에서 환경변수 사용)")
                        elif disk['datastore_id'] == 'local-lvm':
                            # local-lvm은 기본값이므로 auto로 변경하여 환경변수 사용
                            disk['datastore_id'] = 'auto'
                            logger.info(f"🔧 디스크 {i}: local-lvm을 auto로 변경 (환경변수 사용)")
                        else:
                            logger.info(f"🔧 디스크 {i}: datastore_id가 이미 설정됨: {disk['datastore_id']}")

                    # 디스크 설정 후 상태 로그
                    logger.info(f"🔧 디스크 설정 후 상태:")
                    for i, disk in enumerate(disks):
                        logger.info(f"   디스크 {i}: {disk}")
                    
                    server_data = {
                        'name': server_name,
                        'cpu': cpu,
                        'memory': memory,
                        'role': role,
                        'os_type': os_type,  # 동적으로 분류된 OS 타입
                        'disks': disks,
                        'network_devices': network_devices,
                        'template_vm_id': template_vm_id,
                        'vm_username': current_vm_username,
                        'vm_password': current_vm_password
                    }
                    logger.info(f"🔧 서버 설정 생성 시작: {json.dumps(server_data, indent=2)}")
                    
                    try:
                        config_success = terraform_service.create_server_config(server_data)
                        logger.info(f"🔧 서버 설정 생성 결과: {config_success}")
                        
                        if not config_success:
                            error_msg = '서버 설정 생성 실패'
                            logger.error(f"{error_msg}")
                            update_task(task_id, 'failed', error_msg)
                            return
                    except Exception as config_error:
                        error_msg = f'서버 설정 생성 중 예외 발생: {str(config_error)}'
                        logger.error(f"{error_msg}")
                        import traceback
                        traceback.print_exc()
                        update_task(task_id, 'failed', error_msg)
                        return
                    
                    # 인프라 배포
                    logger.info(f"🔧 인프라 배포 시작: {server_name}")
                    try:
                        deploy_success, deploy_message = terraform_service.deploy_infrastructure()
                        logger.info(f"🔧 인프라 배포 결과: success={deploy_success}, message={deploy_message}")
                        
                        if not deploy_success:
                            logger.error(f"인프라 배포 실패: {deploy_message}")
                            update_task(task_id, 'failed', f'인프라 배포 실패: {deploy_message}')
                            return
                    except Exception as deploy_error:
                        error_msg = f"인프라 배포 중 예외 발생: {str(deploy_error)}"
                        logger.error(f"{error_msg}")
                        import traceback
                        traceback.print_exc()
                        update_task(task_id, 'failed', error_msg)
                        return
                    
                    # Proxmox에서 실제 VM 생성 확인
                    proxmox_service = ProxmoxService()
                    vm_exists = proxmox_service.check_vm_exists(server_name)
                    
                    if not vm_exists:
                        update_task(task_id, 'failed', 'Proxmox에서 VM을 찾을 수 없습니다.')
                        return
                    
                    # VM ID 가져오기
                    vm_id = None
                    try:
                        # Terraform output에서 VM ID 가져오기
                        terraform_output = terraform_service.output()
                        logger.info(f"🔍 Terraform output 전체: {terraform_output}")
                        
                        if 'vm_ids' in terraform_output:
                            vm_ids_data = terraform_output['vm_ids']
                            logger.info(f"🔍 vm_ids 데이터: {vm_ids_data}")
                            
                            # Terraform output 구조: {"vm_ids": {"value": {"test1": 110}}}
                            if 'value' in vm_ids_data and server_name in vm_ids_data['value']:
                                vm_id = vm_ids_data['value'][server_name]
                                logger.info(f"🔍 Terraform output에서 VM ID 조회: {server_name} = {vm_id}")
                        
                        # VM ID가 없으면 Proxmox API에서 조회
                        if not vm_id:
                            vm_exists, vm_info = proxmox_service.check_vm_exists(server_name)
                            if vm_exists and vm_info:
                                vm_id = vm_info.get('vmid')
                                logger.info(f"🔍 Proxmox API에서 VM ID 조회: {server_name} = {vm_id}")
                    except Exception as e:
                        logger.warning(f"VM ID 조회 실패: {e}")
                        import traceback
                        traceback.print_exc()
                    
                    # IP 주소 처리 (리스트인 경우 문자열로 변환)
                    ip_address_str = ip_address
                    if isinstance(ip_address, list):
                        ip_address_str = ', '.join(ip_address) if ip_address else ''
                    
                    # DB에 서버 정보 저장 (VM ID 포함)
                    new_server = Server(
                        name=server_name,
                        vmid=vm_id,  # VM ID 추가
                        ip_address=ip_address_str,  # IP 주소 추가 (문자열로 변환)
                        role=role,  # 역할 정보 추가
                        status='stopped',  # 초기 상태는 중지됨
                        cpu=cpu,
                        memory=memory,
                        os_type=os_type  # OS 타입 추가
                    )
                    db.session.add(new_server)
                    db.session.commit()
                    logger.info(f"DB에 서버 저장 완료: {server_name} (ID: {new_server.id}, VM ID: {vm_id})")
                    
                    # Node Exporter 자동 설치 (모니터링용)
                    ansible_service = AnsibleService()
                    node_exporter_installed = False
                    try:
                        # IP 주소에서 첫 번째 IP 추출 (Node Exporter 설치용)
                        server_ip = ip_address_str.split(',')[0].strip() if ip_address_str else ''
                        if server_ip:
                            logger.info(f"🔧 Node Exporter 자동 설치 시작: {server_name} ({server_ip})")
                            node_exporter_installed = ansible_service._install_node_exporter_if_needed(server_name, server_ip)
                            if node_exporter_installed:
                                logger.info(f"Node Exporter 설치 완료: {server_name}")
                            else:
                                logger.warning(f"Node Exporter 설치 실패: {server_name}")
                        else:
                            logger.warning(f"IP 주소가 없어 Node Exporter 설치 스킵: {server_name}")
                    except Exception as e:
                        logger.warning(f"Node Exporter 설치 중 오류: {e}")
                    
                    # Ansible을 통한 역할별 소프트웨어 설치 (Node Exporter는 별도 설치)
                    if role and role != 'none':
                        logger.info(f"🔧 Ansible 역할 할당 시작: {server_name} - {role}")
                        try:
                            # 서버 생성 시에는 역할만 설치 (Node Exporter는 위에서 별도 설치)
                            ansible_success, ansible_message = ansible_service.run_playbook(
                                role=role,
                                extra_vars={},  # Node Exporter 설치 변수 제거
                                target_server=server_ip
                            )
                            
                            if ansible_success:
                                logger.info(f"Ansible 역할 할당 성공: {server_name} - {role}")
                                update_task(task_id, 'completed', f'서버 {server_name} 생성 및 {role} 역할 할당 완료')
                                # 성공 알림 생성
                                NotificationService.create_server_notification(
                                    server_name, 'create', 'success', 
                                    f'서버 {server_name} 생성 및 {role} 역할 할당이 완료되었습니다. Node Exporter: {"설치됨" if node_exporter_installed else "설치 안됨"}'
                                )
                            else:
                                logger.warning(f"Ansible 역할 할당 실패: {server_name} - {role}, 메시지: {ansible_message}")
                                update_task(task_id, 'completed', f'서버 {server_name} 생성 완료 (Ansible 실패: {ansible_message})')
                                # 부분 성공 알림 생성
                                NotificationService.create_server_notification(
                                    server_name, 'create', 'warning', 
                                    f'서버 {server_name} 생성 완료 (Ansible 실패: {ansible_message})'
                                )
                        except Exception as ansible_error:
                            logger.warning(f"Ansible 실행 중 오류: {str(ansible_error)}")
                            update_task(task_id, 'completed', f'서버 {server_name} 생성 완료 (Ansible 오류: {str(ansible_error)})')
                            # 부분 성공 알림 생성
                            NotificationService.create_server_notification(
                                server_name, 'create', 'warning', 
                                f'서버 {server_name} 생성 완료 (Ansible 오류: {str(ansible_error)})'
                            )
                    else:
                        update_task(task_id, 'completed', f'서버 {server_name} 생성 완료')
                        # 성공 알림 생성
                        NotificationService.create_server_notification(
                            server_name, 'create', 'success', 
                            f'서버 {server_name} 생성이 완료되었습니다.'
                        )
                    
                    # Prometheus 설정 업데이트 (서버 생성 완료 후)
                    try:
                        from app.services.prometheus_service import PrometheusService
                        prometheus_service = PrometheusService()
                        prometheus_updated = prometheus_service.update_prometheus_config()
                        
                        if prometheus_updated:
                            logger.info(f"Prometheus 설정 업데이트 완료: {server_name}")
                        else:
                            logger.warning(f"Prometheus 설정 업데이트 실패: {server_name}")
                            print(prometheus_service.get_manual_setup_instructions())
                    except Exception as e:
                        logger.warning(f"Prometheus 설정 업데이트 중 오류: {e}")
                        logger.info("🔧 Prometheus 수동 설정이 필요할 수 있습니다.")
                    
                    # Node Exporter 설치 성공 여부와 관계없이 Prometheus 설정 업데이트
                    if not node_exporter_installed and server_ip:
                        logger.info(f"🔧 Node Exporter 설치 실패했지만 Prometheus 설정은 업데이트: {server_ip}")
                        try:
                            from app.services.prometheus_service import PrometheusService
                            prometheus_service = PrometheusService()
                            prometheus_updated = prometheus_service.update_prometheus_config()
                            if prometheus_updated:
                                logger.info(f"Prometheus 설정 업데이트 완료 (Node Exporter 실패 후): {server_ip}")
                        except Exception as e:
                            logger.warning(f"Prometheus 설정 업데이트 중 오류 (Node Exporter 실패 후): {e}")
                    
                    logger.info(f"서버 생성 완료: {server_name}")
                    
            except Exception as e:
                logger.error(f"서버 생성 작업 실패: {str(e)}")
                update_task(task_id, 'failed', f'서버 생성 중 오류: {str(e)}')
                
                # 실패 알림 생성
                try:
                    NotificationService.create_server_notification(
                        server_name, 'create', 'error', 
                        f'서버 {server_name} 생성 중 오류가 발생했습니다: {str(e)}'
                    )
                except Exception as notif_error:
                    logger.warning(f"실패 알림 생성 실패: {str(notif_error)}")
                
                # 실패 시 정리 작업
                try:
                    # tfvars에서 설정 제거
                    terraform_service = TerraformService()
                    terraform_service.remove_server_config(server_name)
                    
                    # DB에서 서버 삭제
                    failed_server = Server.query.filter_by(name=server_name).first()
                    if failed_server:
                        db.session.delete(failed_server)
                        db.session.commit()
                except Exception as cleanup_error:
                    logger.error(f"정리 작업 실패: {str(cleanup_error)}")
        
        # 백그라운드에서 서버 생성 작업 실행
        thread = threading.Thread(target=create_server_task)
        thread.start()
        
        return jsonify({
            'success': True,
            'task_id': task_id,
            'message': f'서버 {server_name} 생성이 시작되었습니다.'
        })
        
    except Exception as e:
        logger.error(f"서버 생성 실패: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/create_servers_bulk', methods=['POST'])
@permission_required('create_server')
def create_servers_bulk():
    """다중 서버 생성"""
    try:
        data = request.get_json()
        servers_data = data.get('servers', [])
        
        if not servers_data:
            return jsonify({'error': '서버 데이터가 필요합니다.'}), 400
        
        # 서버 이름 중복 확인
        server_names = [server.get('name') for server in servers_data if server.get('name')]
        for server_name in server_names:
            existing_server = Server.query.filter_by(name=server_name).first()
            if existing_server:
                return jsonify({'error': f'이미 존재하는 서버 이름입니다: {server_name}'}), 400
        
        # Task 생성
        task_id = create_task('running', 'create_servers_bulk', f'{len(servers_data)}개 서버 생성 중...')
        
        def create_servers_bulk_task():
            try:
                from app import create_app
                app = create_app()
                with app.app_context():
                    logger.info(f"🔧 다중 서버 생성 작업 시작: {len(servers_data)}개 서버")
                    
                    # Terraform 서비스 초기화
                    terraform_service = TerraformService()
                    
                    # 기존 tfvars 로드
                    try:
                        tfvars = terraform_service.load_tfvars()
                        logger.info(f"🔧 기존 tfvars 로드 완료: {len(tfvars.get('servers', {}))}개 서버")
                    except Exception as e:
                        logger.error(f"기존 tfvars 로드 실패: {e}")
                        # 기본 구조 생성
                        tfvars = {
                            'servers': {},
                            'proxmox_endpoint': current_app.config.get('PROXMOX_ENDPOINT'),
                            'proxmox_username': current_app.config.get('PROXMOX_USERNAME'),
                            'proxmox_password': current_app.config.get('PROXMOX_PASSWORD'),
                            'proxmox_node': current_app.config.get('PROXMOX_NODE'),
                            'vm_username': current_app.config.get('VM_USERNAME', 'rocky'),
                            'vm_password': current_app.config.get('VM_PASSWORD', 'rocky123'),
                            'ssh_keys': current_app.config.get('SSH_KEYS', '')
                        }
                    
                    # 서버 설정 추가
                    for server_data in servers_data:
                        server_name = server_data.get('name')
                        if not server_name:
                            continue
                        
                        # 서버별 기본값 설정
                        server_config = {
                            'name': server_name,
                            'cpu': server_data.get('cpu', 2),
                            'memory': server_data.get('memory', 2048),
                            'role': server_data.get('role', ''),
                            'os_type': server_data.get('os_type', ''), 
                            'disks': server_data.get('disks', []),
                            'network_devices': server_data.get('network_devices', []),
                            'template_vm_id': server_data.get('template_vm_id', 8000),
                            'vm_username': server_data.get('vm_username', tfvars.get('vm_username', 'rocky')),
                            'vm_password': server_data.get('vm_password', tfvars.get('vm_password', 'rocky123'))
                        }
                        
                        # 디스크 설정에 기본값 추가 및 datastore 자동 설정
                        import os
                        # 환경변수에서 직접 datastore 설정 가져오기
                        hdd_datastore = os.environ.get('PROXMOX_HDD_DATASTORE')
                        ssd_datastore = os.environ.get('PROXMOX_SSD_DATASTORE')
                        
                        for disk in server_config['disks']:
                            if 'disk_type' not in disk:
                                disk['disk_type'] = 'hdd'
                            if 'file_format' not in disk:
                                disk['file_format'] = 'auto'
                            # datastore_id가 "auto"이거나 없으면 환경변수에서 가져온 datastore 사용
                            if 'datastore_id' not in disk or disk['datastore_id'] == 'auto':
                                if disk['disk_type'] == 'hdd':
                                    disk['datastore_id'] = hdd_datastore if hdd_datastore else 'local-lvm'
                                elif disk['disk_type'] == 'ssd':
                                    disk['datastore_id'] = ssd_datastore if ssd_datastore else 'local'
                                else:
                                    disk['datastore_id'] = hdd_datastore if hdd_datastore else 'local-lvm'
                                
                                logger.info(f"🔧 {server_name}: {disk['disk_type']} 디스크 datastore 자동 설정: {disk['datastore_id']}")
                        
                        tfvars['servers'][server_name] = server_config
                        logger.info(f"🔧 서버 설정 추가: {server_name}")
                    
                    # tfvars 파일 저장
                    try:
                        save_success = terraform_service.save_tfvars(tfvars)
                        if not save_success:
                            error_msg = 'tfvars 파일 저장 실패'
                            logger.error(f"{error_msg}")
                            update_task(task_id, 'failed', error_msg)
                            return
                        logger.info(f"tfvars 파일 저장 완료: {len(tfvars['servers'])}개 서버")
                    except Exception as save_error:
                        error_msg = f'tfvars 파일 저장 중 예외 발생: {str(save_error)}'
                        logger.error(f"{error_msg}")
                        import traceback
                        traceback.print_exc()
                        update_task(task_id, 'failed', error_msg)
                        return
                    
                    # 새로 생성될 서버들에 대한 targeted apply 실행
                    logger.info(f"🔧 Targeted Terraform apply 시작: {len(servers_data)}개 서버")
                    try:
                        # 새로 생성될 서버들만 대상으로 targeted apply 실행
                        new_server_targets = []
                        for server_data in servers_data:
                            server_name = server_data.get('name')
                            if server_name:
                                # Terraform 모듈 리소스 타겟 형식: module.server["서버이름"]
                                target = f'module.server["{server_name}"]'
                                new_server_targets.append(target)
                        
                        logger.info(f"🔧 Targeted apply 대상: {new_server_targets}")
                        apply_success, apply_message = terraform_service.apply(targets=new_server_targets)
                        logger.info(f"🔧 Terraform apply 결과: success={apply_success}, message_length={len(apply_message) if apply_message else 0}")
                        
                        if not apply_success:
                            logger.error(f"Terraform apply 실패: {apply_message}")
                            update_task(task_id, 'failed', f'Terraform apply 실패: {apply_message}')
                            return
                    except Exception as apply_error:
                        error_msg = f"Terraform apply 중 예외 발생: {str(apply_error)}"
                        logger.error(f"{error_msg}")
                        import traceback
                        traceback.print_exc()
                        update_task(task_id, 'failed', error_msg)
                        return
                    
                    # Proxmox에서 실제 VM 생성 확인
                    proxmox_service = ProxmoxService()
                    created_servers = []
                    failed_servers = []
                    
                    # 템플릿 정보를 한 번에 조회 (효율성 향상)
                    template_cache = {}
                    try:
                        headers, error = proxmox_service.get_proxmox_auth()
                        if not error:
                            vms, vm_error = proxmox_service.get_proxmox_vms(headers)
                            if not vm_error:
                                for vm in vms:
                                    template_cache[vm.get('vmid')] = vm.get('name', 'rocky-9-template')
                    except Exception as e:
                        logger.warning(f"템플릿 정보 조회 실패: {e}")
                    
                    for server_data in servers_data:
                        server_name = server_data.get('name')
                        if not server_name:
                            continue
                        
                        vm_exists = proxmox_service.check_vm_exists(server_name)
                        if vm_exists:
                            created_servers.append(server_name)
                            
                            # IP 주소를 network_devices에서 추출 (이미 위에서 처리했지만 다시 확인)
                            ip_address_str = ''
                            network_devices = server_data.get('network_devices', [])
                            if network_devices:
                                ip_addresses = [device.get('ip_address', '') for device in network_devices if device.get('ip_address')]
                                ip_address_str = ', '.join(ip_addresses) if ip_addresses else ''
                            
                            # OS 타입 동적 분류 (캐시된 정보 사용)
                            template_vm_id = server_data.get('template_vm_id', 8000)
                            template_name = template_cache.get(template_vm_id, 'rocky-9-template')
                            os_type = classify_os_type(template_name)
                            
                            # VM ID 가져오기
                            vm_id = None
                            try:
                                # Terraform output에서 VM ID 가져오기
                                terraform_output = terraform_service.output()
                                logger.info(f"🔍 Terraform output 전체: {terraform_output}")
                                
                                if 'vm_ids' in terraform_output:
                                    vm_ids_data = terraform_output['vm_ids']
                                    logger.info(f"🔍 vm_ids 데이터: {vm_ids_data}")
                                    
                                    # Terraform output 구조: {"vm_ids": {"value": {"test1": 110}}}
                                    if 'value' in vm_ids_data and server_name in vm_ids_data['value']:
                                        vm_id = vm_ids_data['value'][server_name]
                                        logger.info(f"🔍 Terraform output에서 VM ID 조회: {server_name} = {vm_id}")
                                
                                # VM ID가 없으면 Proxmox API에서 조회
                                if not vm_id:
                                    vm_exists, vm_info = proxmox_service.check_vm_exists(server_name)
                                    if vm_exists and vm_info:
                                        vm_id = vm_info.get('vmid')
                                        logger.info(f"🔍 Proxmox API에서 VM ID 조회: {server_name} = {vm_id}")
                            except Exception as e:
                                logger.warning(f"VM ID 조회 실패: {e}")
                                import traceback
                                traceback.print_exc()
                            
                            # DB에 서버 정보 저장 (VM ID 포함)
                            new_server = Server(
                                name=server_name,
                                vmid=vm_id,  # VM ID 추가
                                ip_address=ip_address_str,  # IP 주소 추가
                                cpu=server_data.get('cpu', 2),
                                memory=server_data.get('memory', 2048),
                                role=server_data.get('role', ''),
                                status='running',
                                os_type=os_type,  # OS 타입 추가
                                created_at=datetime.utcnow()
                            )
                            
                            try:
                                db.session.add(new_server)
                                db.session.commit()
                                logger.info(f"서버 DB 저장 완료: {server_name}")
                            except Exception as db_error:
                                logger.warning(f"서버 DB 저장 실패: {server_name} - {db_error}")
                                db.session.rollback()
                        else:
                            failed_servers.append(server_name)
                            logger.error(f"VM 생성 확인 실패: {server_name}")
                    
                    # Node Exporter 자동 설치 (생성된 서버들에 대해)
                    if created_servers:
                        logger.info(f"🔧 생성된 서버들에 Node Exporter 자동 설치 시작: {len(created_servers)}개")
                        ansible_service = AnsibleService()
                        
                        # 서버 IP 수집
                        server_ips = []
                        for server_name in created_servers:
                            try:
                                server = Server.query.filter_by(name=server_name).first()
                                if server and server.ip_address:
                                    server_ip = server.ip_address.split(',')[0].strip()
                                    server_ips.append(server_ip)
                                    logger.info(f"🔧 Node Exporter 설치 대상: {server_name} ({server_ip})")
                                else:
                                    logger.warning(f"서버 IP 정보 없음: {server_name}")
                            except Exception as e:
                                logger.warning(f"서버 IP 수집 중 오류 ({server_name}): {e}")
                        
                        # 일괄 설치 실행 (Node Exporter 포함)
                        if server_ips:
                            logger.info(f"🔧 Node Exporter 일괄 설치 시작: {len(server_ips)}개 서버")
                            success, result = ansible_service.run_playbook(
                                role='node_exporter',
                                extra_vars={'install_node_exporter': True},
                                limit_hosts=','.join(server_ips)
                            )
                            
                            if success:
                                logger.info(f"Node Exporter 일괄 설치 성공: {len(server_ips)}개 서버")
                            else:
                                logger.error(f"Node Exporter 일괄 설치 실패: {result}")
                        else:
                            logger.warning(f"Node Exporter 설치할 유효한 서버 IP가 없음")
                    
                    # Prometheus 설정 업데이트 (대량 서버 생성 완료 후)
                    try:
                        from app.services.prometheus_service import PrometheusService
                        prometheus_service = PrometheusService()
                        prometheus_updated = prometheus_service.update_prometheus_config()
                        
                        if prometheus_updated:
                            logger.info(f"Prometheus 설정 업데이트 완료: {len(created_servers)}개 서버")
                        else:
                            logger.warning(f"Prometheus 설정 업데이트 실패")
                    except Exception as e:
                        logger.warning(f"Prometheus 설정 업데이트 중 오류: {e}")
                    
                    # 결과 메시지 생성
                    if created_servers and not failed_servers:
                        success_msg = f'모든 서버 생성 완료: {", ".join(created_servers)}'
                        update_task(task_id, 'completed', success_msg)
                        logger.info(f"{success_msg}")
                        # 성공 알림 생성
                        for server_name in created_servers:
                            try:
                                NotificationService.create_server_notification(
                                    server_name, 'create', 'success', 
                                    f'서버 {server_name} 생성이 완료되었습니다.'
                                )
                            except Exception as notif_error:
                                logger.warning(f"알림 생성 실패: {str(notif_error)}")
                    elif created_servers and failed_servers:
                        partial_msg = f'일부 서버 생성 완료. 성공: {", ".join(created_servers)}, 실패: {", ".join(failed_servers)}'
                        update_task(task_id, 'completed', partial_msg)
                        logger.warning(f"{partial_msg}")
                        # 부분 성공 알림 생성
                        for server_name in created_servers:
                            try:
                                NotificationService.create_server_notification(
                                    server_name, 'create', 'success', 
                                    f'서버 {server_name} 생성이 완료되었습니다.'
                                )
                            except Exception as notif_error:
                                logger.warning(f"알림 생성 실패: {str(notif_error)}")
                        for server_name in failed_servers:
                            try:
                                NotificationService.create_server_notification(
                                    server_name, 'create', 'error', 
                                    f'서버 {server_name} 생성에 실패했습니다.'
                                )
                            except Exception as notif_error:
                                logger.warning(f"알림 생성 실패: {str(notif_error)}")
                    else:
                        error_msg = f'모든 서버 생성 실패: {", ".join(failed_servers)}'
                        update_task(task_id, 'failed', error_msg)
                        logger.error(f"{error_msg}")
                        # 실패 알림 생성
                        for server_name in failed_servers:
                            try:
                                NotificationService.create_server_notification(
                                    server_name, 'create', 'error', 
                                    f'서버 {server_name} 생성에 실패했습니다.'
                                )
                            except Exception as notif_error:
                                logger.warning(f"알림 생성 실패: {str(notif_error)}")
                    
                    # Prometheus 설정 업데이트 (다중 서버 생성 완료 후)
                    if created_servers:
                        try:
                            from app.services.prometheus_service import PrometheusService
                            prometheus_service = PrometheusService()
                            prometheus_updated = prometheus_service.update_prometheus_config()
                            
                            if prometheus_updated:
                                logger.info(f"Prometheus 설정 업데이트 완료: {len(created_servers)}개 서버")
                            else:
                                logger.warning(f"Prometheus 설정 업데이트 실패")
                                print(prometheus_service.get_manual_setup_instructions())
                        except Exception as e:
                            logger.warning(f"Prometheus 설정 업데이트 중 오류: {e}")
                            logger.info("🔧 Prometheus 수동 설정이 필요할 수 있습니다.")
                    
            except Exception as e:
                error_msg = f'다중 서버 생성 작업 중 예외 발생: {str(e)}'
                logger.error(f"{error_msg}")
                import traceback
                traceback.print_exc()
                update_task(task_id, 'failed', error_msg)
        
        # 백그라운드에서 작업 실행
        thread = threading.Thread(target=create_servers_bulk_task)
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'success': True,
            'message': f'{len(servers_data)}개 서버 생성 작업이 시작되었습니다.',
            'task_id': task_id
        })
        
    except Exception as e:
        logger.error(f"다중 서버 생성 API 오류: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/servers/bulk_action', methods=['POST'])
@permission_required('manage_server')
def bulk_server_action():
    """대량 서버 작업 처리"""
    try:
        data = request.get_json()
        server_names = data.get('server_names', [])
        action = data.get('action')  # start, stop, reboot, delete
        
        if not server_names:
            return jsonify({'error': '서버 목록이 필요합니다.'}), 400
            
        if not action:
            return jsonify({'error': '작업 유형이 필요합니다.'}), 400
            
        if action not in ['start', 'stop', 'reboot', 'delete']:
            return jsonify({'error': '지원하지 않는 작업입니다.'}), 400
        
        logger.info(f"🔧 대량 서버 작업: {action} - {len(server_names)}개 서버")
        
        # Task 생성
        task_id = create_task('running', 'bulk_server_action', f'{len(server_names)}개 서버 {action} 작업 중...')
        
        def bulk_action_task():
            try:
                from app import create_app
                app = create_app()
                with app.app_context():
                    logger.info(f"🔧 대량 서버 작업 시작: {action} - {server_names}")
                    
                    # 삭제 작업은 Terraform 기반으로 처리
                    if action == 'delete':
                        success_servers, failed_servers = process_bulk_delete_terraform(server_names)
                    else:
                        # 기존 Proxmox API 기반 작업 (start, stop, reboot)
                        success_servers, failed_servers = process_bulk_proxmox_action(server_names, action)
                    
                    # 결과 메시지 생성
                    action_names = {
                        'start': '시작',
                        'stop': '중지', 
                        'reboot': '재시작',
                        'delete': '삭제'
                    }
                    action_name = action_names.get(action, action)
                    
                    if success_servers and not failed_servers:
                        success_msg = f'모든 서버 {action_name} 완료: {", ".join(success_servers)}'
                        update_task(task_id, 'completed', success_msg)
                        logger.info(f"{success_msg}")
                    elif success_servers and failed_servers:
                        partial_msg = f'일부 서버 {action_name} 완료. 성공: {", ".join(success_servers)}, 실패: {len(failed_servers)}개'
                        update_task(task_id, 'completed', partial_msg)
                        logger.warning(f"{partial_msg}")
                        logger.warning(f"실패 상세: {failed_servers}")
                    else:
                        error_msg = f'모든 서버 {action_name} 실패: {len(failed_servers)}개'
                        update_task(task_id, 'failed', error_msg)
                        logger.error(f"{error_msg}")
                        logger.error(f"실패 상세: {failed_servers}")
                        
            except Exception as e:
                error_msg = f'대량 서버 작업 중 예외 발생: {str(e)}'
                logger.error(f"{error_msg}")
                import traceback
                traceback.print_exc()
                update_task(task_id, 'failed', error_msg)
        
        # 백그라운드에서 작업 실행
        thread = threading.Thread(target=bulk_action_task)
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'success': True,
            'message': f'{len(server_names)}개 서버 {action} 작업이 시작되었습니다.',
            'task_id': task_id
        })
        
    except Exception as e:
        logger.error(f"대량 서버 작업 API 오류: {str(e)}")
        return jsonify({'error': str(e)}), 500

def process_bulk_delete_terraform(server_names):
    """Terraform 기반 대량 서버 삭제"""
    success_servers = []
    failed_servers = []
    
    try:
        logger.info(f"🗑️ Terraform 기반 대량 삭제 시작: {server_names}")
        
        # 1. 서버 존재 확인 및 유효성 검사
        valid_servers = []
        for server_name in server_names:
            server = Server.query.filter_by(name=server_name).first()
            if not server:
                failed_servers.append(f"{server_name}: 서버를 찾을 수 없음")
                continue
            valid_servers.append(server_name)
        
        if not valid_servers:
            logger.info("❌ 유효한 서버가 없습니다.")
            return success_servers, failed_servers
        
        # 2. Proxmox API를 통해 서버들을 먼저 중지 (shutdown 대신 stop 사용)
        from app.services.proxmox_service import ProxmoxService
        import time
        proxmox_service = ProxmoxService()
        
        logger.info(f"🛑 서버 중지 단계 시작: {valid_servers}")
        for server_name in valid_servers:
            try:
                logger.info(f"🛑 {server_name} 중지 중...")
                stop_result = proxmox_service.stop_vm(server_name)
                if stop_result['success']:
                    logger.info(f"{server_name} 중지 성공")
                else:
                    logger.warning(f"{server_name} 중지 실패: {stop_result['message']}")
                    # 중지 실패해도 계속 진행 (이미 중지된 상태일 수 있음)
            except Exception as e:
                logger.warning(f"{server_name} 중지 중 예외 발생: {e}")
                # 예외 발생해도 계속 진행
        
        # 서버 중지 후 잠시 대기 (완전히 중지되도록)
        logger.info("⏳ 서버 중지 완료 대기 중... (5초)")
        time.sleep(5)
        
        # 3. Terraform 설정에서 삭제할 서버들 제거
        terraform_service = TerraformService()
        tfvars = terraform_service.load_tfvars()
        
        deleted_from_tfvars = []
        for server_name in valid_servers:
            if 'servers' in tfvars and server_name in tfvars['servers']:
                del tfvars['servers'][server_name]
                deleted_from_tfvars.append(server_name)
                logger.info(f"🗑️ tfvars.json에서 {server_name} 제거")
        
        if not deleted_from_tfvars:
            logger.info("❌ tfvars.json에서 삭제할 서버를 찾을 수 없습니다.")
            for server_name in valid_servers:
                failed_servers.append(f"{server_name}: tfvars.json에서 찾을 수 없음")
            return success_servers, failed_servers
        
        # 4. tfvars.json 저장
        terraform_service.save_tfvars(tfvars)
        logger.info(f"💾 tfvars.json 업데이트 완료: {len(deleted_from_tfvars)}개 서버 제거")
        
        # 5. Terraform destroy with targeted resources
        destroy_targets = []
        for server_name in deleted_from_tfvars:
            target = f'module.server["{server_name}"]'
            destroy_targets.append(target)
        
        logger.info(f"🔥 Terraform destroy 실행 - 대상: {destroy_targets}")
        destroy_success, destroy_message = terraform_service.destroy_targets(destroy_targets)
        
        if destroy_success:
            logger.info(f"Terraform destroy 성공: {deleted_from_tfvars}")
            
            # 5. SSH known_hosts 정리 (삭제된 서버들의 IP 제거)
            try:
                for server_name in deleted_from_tfvars:
                    server = Server.query.filter_by(name=server_name).first()
                    if server and server.ip_address:
                        # IP 주소에서 첫 번째 IP 추출
                        first_ip = server.ip_address.split(',')[0].strip()
                        if first_ip:
                            _remove_from_known_hosts(first_ip)
                            logger.info(f"🧹 SSH known_hosts에서 {first_ip} 제거 완료")
            except Exception as e:
                logger.warning(f"SSH known_hosts 정리 중 오류: {e}")
            
            # 6. Prometheus 설정 업데이트 (삭제된 서버들 제거)
            try:
                from app.services.prometheus_service import PrometheusService
                prometheus_service = PrometheusService()
                prometheus_updated = prometheus_service.update_prometheus_config()
                
                if prometheus_updated:
                    logger.info(f"Prometheus 설정 업데이트 완료: {len(deleted_from_tfvars)}개 서버 제거")
                else:
                    logger.warning(f"Prometheus 설정 업데이트 실패")
            except Exception as e:
                logger.warning(f"Prometheus 설정 업데이트 중 오류: {e}")
            
            # 6. DB에서 서버 제거
            for server_name in deleted_from_tfvars:
                server = Server.query.filter_by(name=server_name).first()
                if server:
                    db.session.delete(server)
                    logger.info(f"🗑️ DB에서 {server_name} 제거")
            
            db.session.commit()
            success_servers.extend(deleted_from_tfvars)
            
        else:
            logger.error(f"Terraform destroy 실패: {destroy_message}")
            # destroy 실패 시 tfvars.json 복원
            for server_name in deleted_from_tfvars:
                server = Server.query.filter_by(name=server_name).first()
                if server:
                    # 서버 정보를 다시 tfvars에 추가 (복원)
                    if 'servers' not in tfvars:
                        tfvars['servers'] = {}
                    tfvars['servers'][server_name] = {
                        'cores': server.cores,
                        'memory': server.memory,
                        'disk': server.disk,
                        'role': server.role or 'web'
                    }
                failed_servers.append(f"{server_name}: Terraform destroy 실패")
            
            # tfvars.json 복원
            terraform_service.save_tfvars(tfvars)
            logger.info("🔄 tfvars.json 복원 완료")
        
    except Exception as e:
        error_msg = f"대량 삭제 중 예외 발생: {str(e)}"
        logger.error(f"{error_msg}")
        for server_name in server_names:
            if server_name not in success_servers:
                failed_servers.append(f"{server_name}: {error_msg}")
    
    return success_servers, failed_servers

def process_bulk_proxmox_action(server_names, action):
    """Proxmox API 기반 대량 서버 작업 (start, stop, reboot)"""
    success_servers = []
    failed_servers = []
    
    try:
        proxmox_service = ProxmoxService()
        
        for server_name in server_names:
            try:
                logger.info(f"🔧 서버 작업 처리: {server_name} - {action}")
                
                # 서버 존재 확인
                server = Server.query.filter_by(name=server_name).first()
                if not server:
                    failed_servers.append(f"{server_name}: 서버를 찾을 수 없음")
                    continue
                
                # Proxmox API 호출
                if action == 'start':
                    result = proxmox_service.start_vm(server_name)
                elif action == 'stop':
                    result = proxmox_service.stop_vm(server_name)
                elif action == 'reboot':
                    result = proxmox_service.reboot_vm(server_name)
                else:
                    failed_servers.append(f"{server_name}: 지원하지 않는 작업")
                    continue
                
                if result.get('success', False):
                    success_servers.append(server_name)
                    
                    # DB 상태 업데이트
                    if action == 'start':
                        server.status = 'running'
                    elif action == 'stop':
                        server.status = 'stopped'
                    # reboot는 상태를 running으로 유지
                    
                    db.session.commit()
                    logger.info(f"{server_name} {action} 성공")
                else:
                    error_msg = result.get('message', '알 수 없는 오류')
                    failed_servers.append(f"{server_name}: {error_msg}")
                    logger.error(f"{server_name} {action} 실패: {error_msg}")
                    
            except Exception as server_error:
                error_msg = f"{server_name}: {str(server_error)}"
                failed_servers.append(error_msg)
                logger.error(f"{server_name} 처리 중 오류: {server_error}")
    
    except Exception as e:
        error_msg = f"대량 Proxmox 작업 중 예외 발생: {str(e)}"
        logger.error(f"{error_msg}")
        for server_name in server_names:
            if server_name not in success_servers:
                failed_servers.append(f"{server_name}: {error_msg}")
    
    return success_servers, failed_servers

@bp.route('/api/servers/<server_name>/start', methods=['POST'])
@permission_required('start_server')
def start_server(server_name):
    """서버 시작"""
    try:
        from app.services.proxmox_service import ProxmoxService
        proxmox_service = ProxmoxService()
        
        server = Server.query.filter_by(name=server_name).first()
        if not server:
            return jsonify({'error': '서버를 찾을 수 없습니다.'}), 404
        
        if proxmox_service.start_server(server_name):
            server.status = 'running'
            db.session.commit()
            return jsonify({'success': True, 'message': f'서버 {server_name}가 시작되었습니다.'})
        else:
            return jsonify({'error': f'서버 {server_name} 시작에 실패했습니다.'}), 500
    except Exception as e:
        logger.error(f"서버 시작 실패: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/servers/<server_name>/stop', methods=['POST'])
@permission_required('stop_server')
def stop_server(server_name):
    """서버 중지"""
    try:
        from app.services.proxmox_service import ProxmoxService
        proxmox_service = ProxmoxService()
        
        server = Server.query.filter_by(name=server_name).first()
        if not server:
            return jsonify({'error': '서버를 찾을 수 없습니다.'}), 404
        
        if proxmox_service.stop_server(server_name):
            server.status = 'stopped'
            db.session.commit()
            return jsonify({'success': True, 'message': f'서버 {server_name}가 중지되었습니다.'})
        else:
            return jsonify({'error': f'서버 {server_name} 중지에 실패했습니다.'}), 500
    except Exception as e:
        logger.error(f"서버 중지 실패: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/servers/<server_name>/reboot', methods=['POST'])
@permission_required('reboot_server')
def reboot_server(server_name):
    """서버 재부팅"""
    try:
        from app.services.proxmox_service import ProxmoxService
        proxmox_service = ProxmoxService()
        
        server = Server.query.filter_by(name=server_name).first()
        if not server:
            return jsonify({'error': '서버를 찾을 수 없습니다.'}), 404
        
        if proxmox_service.reboot_server(server_name):
            return jsonify({'success': True, 'message': f'서버 {server_name}가 재부팅되었습니다.'})
        else:
            return jsonify({'error': f'서버 {server_name} 재부팅에 실패했습니다.'}), 500
    except Exception as e:
        logger.error(f"서버 재부팅 실패: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/servers/<server_name>/delete', methods=['POST'])
@permission_required('delete_server')
def delete_server(server_name):
    """서버 삭제"""
    try:
        server = Server.query.filter_by(name=server_name).first()
        if not server:
            return jsonify({'error': '서버를 찾을 수 없습니다.'}), 404
        
        logger.info(f"🔧 서버 삭제 시작: {server_name}")
        
        # 동기적으로 서버 삭제 실행
        success_servers, failed_servers = process_bulk_delete_terraform([server_name])
        
        if success_servers and server_name in success_servers:
            logger.info(f"서버 삭제 완료: {server_name}")
            return jsonify({
                'success': True,
                'message': f'서버 {server_name}가 삭제되었습니다.'
            })
        else:
            # 실패 원인 메시지 추출
            failure_reason = "알 수 없는 오류"
            for failed in failed_servers:
                if server_name in failed:
                    failure_reason = failed.split(": ", 1)[1] if ": " in failed else failed
                    break
            
            logger.error(f"서버 삭제 실패: {failure_reason}")
            return jsonify({
                'success': False,
                'error': f'서버 삭제 실패: {failure_reason}'
            }), 500
        
    except Exception as e:
        logger.error(f"서버 삭제 실패: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/all_server_status', methods=['GET'])
@login_required
def get_all_server_status():
    """모든 서버 상태 조회"""
    try:
        from app.services.proxmox_service import ProxmoxService
        proxmox_service = ProxmoxService()
        
        # get_all_vms 함수 사용 (통계 정보 포함)
        result = proxmox_service.get_all_vms()
        
        if result['success']:
            # 기존 구조와 호환성을 위해 데이터 변환
            servers = result['data']['servers']
            stats = result['data']['stats']
            
            # DB에서 서버 정보 가져와서 병합 (역할, 방화벽 그룹 정보)
            db_servers = Server.query.all()
            db_server_map = {s.name: s for s in db_servers}
            
            # Proxmox 데이터에 DB 정보 병합
            for vm_key, server_data in servers.items():
                server_name = server_data.get('name')
                if server_name and server_name in db_server_map:
                    db_server = db_server_map[server_name]
                    # DB의 역할과 방화벽 그룹 정보를 Proxmox 데이터에 추가
                    server_data['role'] = db_server.role
                    server_data['firewall_group'] = db_server.firewall_group
                    server_data['os_type'] = db_server.os_type
                    logger.info(f"🔧 서버 '{server_name}' DB 정보 병합: role={db_server.role}, firewall_group={db_server.firewall_group}")
            
            # 통계 정보를 포함하여 반환
            return jsonify({
                'success': True,
                'servers': servers,
                'stats': stats
            })
        else:
            # 실패 시 기본 구조로 반환
            return jsonify({
                'success': False,
                'servers': {},
                'stats': {
                    'total_servers': 0,
                    'running_servers': 0,
                    'stopped_servers': 0,
                    'node_total_cpu': 0,
                    'node_total_memory_gb': 0,
                    'vm_total_cpu': 0,
                    'vm_total_memory_gb': 0,
                    'vm_used_cpu': 0,
                    'vm_used_memory_gb': 0,
                    'cpu_usage_percent': 0,
                    'memory_usage_percent': 0
                }
            })
        
    except Exception as e:
        logger.error(f"서버 상태 조회 실패: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/proxmox_storage', methods=['GET'])
def proxmox_storage():
    """Proxmox 스토리지 정보 조회"""
    try:
        from app.services.proxmox_service import ProxmoxService
        proxmox_service = ProxmoxService()
        
        storage_info = proxmox_service.get_storage_info()
        
        return jsonify({
            'success': True,
            'data': storage_info.get('data', [])  # storage 키 대신 data 키로 반환
        })
    except Exception as e:
        logger.error(f"스토리지 정보 조회 실패: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/sync_servers', methods=['POST'])
@login_required
def sync_servers():
    """기존 서버를 DB에 동기화"""
    try:
        logger.info("🔧 서버 동기화 시작")
        from app.services.proxmox_service import ProxmoxService
        proxmox_service = ProxmoxService()
        
        # Proxmox에서 서버 목록 가져오기
        vm_list = proxmox_service.get_vm_list()
        logger.info(f"🔧 Proxmox에서 가져온 서버: {[vm['name'] for vm in vm_list]}")
        
        synced_count = 0
        
        for vm in vm_list:
            # DB에서 서버 확인
            existing_server = Server.query.filter_by(name=vm['name']).first()
            if not existing_server:
                # 새 서버 생성
                new_server = Server(
                    name=vm['name'],
                    vmid=vm['vmid'],
                    status=vm['status'],
                    ip_address=vm.get('ip_addresses', [None])[0] if vm.get('ip_addresses') else None
                )
                db.session.add(new_server)
                synced_count += 1
                logger.info(f"서버 동기화: {vm['name']}")
            else:
                # 기존 서버 정보 업데이트
                existing_server.vmid = vm['vmid']
                existing_server.status = vm['status']
                existing_server.ip_address = vm.get('ip_addresses', [None])[0] if vm.get('ip_addresses') else None
                logger.info(f"🔄 서버 정보 업데이트: {vm['name']}")
        
        db.session.commit()
        logger.info(f"서버 동기화 완료: {synced_count}개 서버 추가됨")
        
        return jsonify({
            'success': True, 
            'message': f'{synced_count}개 서버가 DB에 동기화되었습니다.'
        })
        
    except Exception as e:
        logger.error(f"서버 동기화 실패: {str(e)}")
        return jsonify({'error': str(e)}), 500

# 기존 서버 관련 라우트들 (호환성 유지)
@bp.route('/')
@login_required
@permission_required('view_all')
def index():
    """서버 목록 페이지"""
    servers = Server.query.all()
    return render_template('servers/index.html', servers=servers)

@bp.route('/create', methods=['GET', 'POST'])
@login_required
@permission_required('create_server')
def create():
    """서버 생성 페이지"""
    if request.method == 'POST':
        data = request.get_json()
        server_name = data.get('name')
        cpu = data.get('cpu', 2)
        memory = data.get('memory', 2048)
        
        if not server_name:
            return jsonify({'error': '서버 이름이 필요합니다.'}), 400
        
        # 서버 이름 중복 확인
        existing_server = Server.query.filter_by(name=server_name).first()
        if existing_server:
            return jsonify({'error': '이미 존재하는 서버 이름입니다.'}), 400
        
        # Task 생성
        task_id = create_task('running', 'create_server', f'서버 {server_name} 생성 중...')
        
        def create_server_background():
            try:
                from app import create_app
                app = create_app()
                with app.app_context():
                    logger.info(f"🔧 서버 생성 작업 시작: {server_name}")
                    
                    # Terraform 서비스 초기화
                    terraform_service = TerraformService()
                    
                    # 서버 설정 생성
                    server_data = {
                        'name': server_name,
                        'cpu': cpu,
                        'memory': memory
                    }
                    config_success = terraform_service.create_server_config(server_data)
                    
                    if not config_success:
                        update_task(task_id, 'failed', f'서버 설정 생성 실패')
                        return
                    
                    # 인프라 배포
                    deploy_success, deploy_message = terraform_service.deploy_infrastructure()
                    
                    if not deploy_success:
                        update_task(task_id, 'failed', f'인프라 배포 실패: {deploy_message}')
                        return
                    
                    # Proxmox에서 실제 VM 생성 확인
                    proxmox_service = ProxmoxService()
                    vm_exists = proxmox_service.check_vm_exists(server_name)
                    
                    if not vm_exists:
                        update_task(task_id, 'failed', 'Proxmox에서 VM을 찾을 수 없습니다.')
                        return
                    
                    # VM ID 가져오기
                    vm_id = None
                    try:
                        # Terraform output에서 VM ID 가져오기
                        terraform_output = terraform_service.output()
                        logger.info(f"🔍 Terraform output 전체: {terraform_output}")
                        
                        if 'vm_ids' in terraform_output:
                            vm_ids_data = terraform_output['vm_ids']
                            logger.info(f"🔍 vm_ids 데이터: {vm_ids_data}")
                            
                            # Terraform output 구조: {"vm_ids": {"value": {"test1": 110}}}
                            if 'value' in vm_ids_data and server_name in vm_ids_data['value']:
                                vm_id = vm_ids_data['value'][server_name]
                                logger.info(f"🔍 Terraform output에서 VM ID 조회: {server_name} = {vm_id}")
                        
                        # VM ID가 없으면 Proxmox API에서 조회
                        if not vm_id:
                            vm_exists, vm_info = proxmox_service.check_vm_exists(server_name)
                            if vm_exists and vm_info:
                                vm_id = vm_info.get('vmid')
                                logger.info(f"🔍 Proxmox API에서 VM ID 조회: {server_name} = {vm_id}")
                    except Exception as e:
                        logger.warning(f"VM ID 조회 실패: {e}")
                        import traceback
                        traceback.print_exc()
                    
                    # 기본값 설정 (이 함수에서는 role, os_type, ip_address가 정의되지 않음)
                    role = ''  # 기본값
                    os_type = 'rocky'  # 기본값
                    ip_address_str = ''  # 기본값
                    
                    # DB에 서버 정보 저장 (VM ID 포함)
                    new_server = Server(
                        name=server_name,
                        vmid=vm_id,  # VM ID 추가
                        ip_address=ip_address_str,  # IP 주소 추가 (문자열로 변환)
                        role=role,  # 역할 정보 추가
                        status='stopped',  # 초기 상태는 중지됨
                        cpu=cpu,
                        memory=memory,
                        os_type=os_type  # OS 타입 추가
                    )
                    db.session.add(new_server)
                    db.session.commit()
                    logger.info(f"DB에 서버 저장 완료: {server_name} (ID: {new_server.id}, VM ID: {vm_id})")
                    
                    # Node Exporter 자동 설치 (모니터링용) - IP가 없는 경우 스킵
                    ansible_service = AnsibleService()
                    node_exporter_installed = False
                    if ip_address_str:
                        try:
                            server_ip = ip_address_str.split(',')[0].strip()
                            logger.info(f"🔧 Node Exporter 자동 설치 시작: {server_name} ({server_ip})")
                            node_exporter_installed = ansible_service._install_node_exporter_if_needed(server_name, server_ip)
                            if node_exporter_installed:
                                logger.info(f"Node Exporter 설치 완료: {server_name}")
                            else:
                                logger.warning(f"Node Exporter 설치 실패: {server_name}")
                        except Exception as e:
                            logger.warning(f"Node Exporter 설치 중 오류: {e}")
                    else:
                        logger.warning(f"IP 주소가 없어 Node Exporter 설치 스킵: {server_name}")
                    
                    # Ansible을 통한 역할별 소프트웨어 설치 (Node Exporter 포함)
                    if role and role != 'none':
                        logger.info(f"🔧 Ansible 역할 할당 시작: {server_name} - {role}")
                        try:
                            ansible_service = AnsibleService()
                            # 서버 생성 시에는 Node Exporter도 함께 설치
                            ansible_success, ansible_message = ansible_service.run_playbook(
                                role=role,
                                extra_vars={'install_node_exporter': True},
                                target_server=ip_address_str
                            )
                            
                            if ansible_success:
                                logger.info(f"Ansible 역할 할당 성공: {server_name} - {role}")
                            else:
                                logger.warning(f"Ansible 역할 할당 실패: {server_name} - {role}, 메시지: {ansible_message}")
                        except Exception as ansible_error:
                            logger.warning(f"Ansible 실행 중 오류: {str(ansible_error)}")
                    
                    update_task(task_id, 'completed', f'서버 {server_name} 생성 완료')
                    logger.info(f"서버 생성 완료: {server_name}")
                    
            except Exception as e:
                logger.error(f"서버 생성 작업 실패: {str(e)}")
                update_task(task_id, 'failed', f'서버 생성 중 오류: {str(e)}')
        
        thread = threading.Thread(target=create_server_background)
        thread.start()
        
        return jsonify({
            'success': True,
            'task_id': task_id,
            'message': f'서버 {server_name} 생성이 시작되었습니다.'
        })
    
    return render_template('servers/create.html')

@bp.route('/<int:server_id>')
@login_required
@permission_required('view_all')
def detail(server_id):
    """서버 상세 페이지"""
    server = Server.query.get_or_404(server_id)
    return render_template('servers/detail.html', server=server)



@bp.route('/status')
@login_required
@permission_required('view_all')
def status():
    """서버 상태 조회"""
    servers = Server.query.all()
    return jsonify([server.to_dict() for server in servers]) 


@bp.route('/api/ansible/status', methods=['GET'])
@login_required
def check_ansible_status():
    """Ansible 설치 상태 확인"""
    try:
        ansible_service = AnsibleService()
        is_installed, message = ansible_service.check_ansible_installation()
        
        return jsonify({
            'success': True,
            'installed': is_installed,
            'message': message
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'installed': False,
            'message': f'Ansible 상태 확인 실패: {str(e)}'
        }), 500

@bp.route('/api/assign_role/<server_name>', methods=['POST'])
@login_required
@permission_required('assign_roles')
def assign_role_to_server(server_name):
    """서버에 역할 할당 (DB 기반 + Ansible 실행)"""
    try:
        logger.info(f"🔧 역할 할당 요청: {server_name}")
        
        data = request.get_json()
        role = data.get('role')
        logger.info(f"🔧 할당할 역할: {role}")
        
        # 빈 문자열도 허용 (역할 제거)
        if role is None:
            return jsonify({'error': '역할(role)을 지정해야 합니다.'}), 400
        
        # AnsibleService를 통해 역할 할당 (DB 업데이트 + Ansible 실행)
        ansible_service = AnsibleService()
        success, message = ansible_service.assign_role_to_server(server_name, role)
        
        if success:
            return jsonify({
                'success': True,
                'message': message
            })
        else:
            return jsonify({'error': message}), 500
            
    except Exception as e:
        logger.error(f"역할 할당 실패: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@bp.route('/api/remove_role/<server_name>', methods=['POST'])
@permission_required('remove_role')
def remove_role(server_name):
    """서버에서 역할 제거"""
    try:
        from app import db
        server = Server.query.filter_by(name=server_name).first()
        if not server:
            return jsonify({'error': '서버를 찾을 수 없습니다.'}), 404
        
        server.role = None
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': f'서버 {server_name}에서 역할이 제거되었습니다.'
        })
    except Exception as e:
        logger.error(f"역할 제거 실패: {str(e)}")
        return jsonify({'error': str(e)}), 500



@bp.route('/api/server/config/<server_name>', methods=['GET'])
@permission_required('view_all')
def get_server_config(server_name):
    """서버 설정 조회"""
    try:
        from app.services.proxmox_service import ProxmoxService
        proxmox_service = ProxmoxService()
        
        result = proxmox_service.get_server_config(server_name)
        if result['success']:
            return jsonify(result)
        else:
            return jsonify({'error': result.get('message', '서버 설정 조회 실패')}), 500
            
    except Exception as e:
        logger.error(f"서버 설정 조회 실패: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/server/config/<server_name>', methods=['PUT'])
@permission_required('view_all')
def update_server_config(server_name):
    """서버 설정 업데이트"""
    try:
        data = request.get_json()
        
        from app.services.proxmox_service import ProxmoxService
        proxmox_service = ProxmoxService()
        
        result = proxmox_service.update_server_config(server_name, data)
        if result['success']:
            return jsonify(result)
        else:
            return jsonify({'error': result.get('message', '서버 설정 업데이트 실패')}), 500
            
    except Exception as e:
        logger.error(f"서버 설정 업데이트 실패: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/server/logs/<server_name>', methods=['GET'])
@permission_required('view_all')
def get_server_logs(server_name):
    """서버 로그 조회"""
    try:
        from app.services.proxmox_service import ProxmoxService
        proxmox_service = ProxmoxService()
        
        result = proxmox_service.get_server_logs(server_name)
        if result['success']:
            return jsonify(result)
        else:
            return jsonify({'error': result.get('message', '서버 로그 조회 실패')}), 500
            
    except Exception as e:
        logger.error(f"서버 로그 조회 실패: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/server/disk/<server_name>', methods=['POST'])
@permission_required('view_all')
def add_server_disk(server_name):
    """서버 디스크 추가"""
    try:
        data = request.get_json()
        
        from app.services.proxmox_service import ProxmoxService
        proxmox_service = ProxmoxService()
        
        result = proxmox_service.add_server_disk(server_name, data)
        if result['success']:
            return jsonify(result)
        else:
            return jsonify({'error': result.get('message', '디스크 추가 실패')}), 500
            
    except Exception as e:
        logger.error(f"디스크 추가 실패: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/server/disk/<server_name>/<device>', methods=['DELETE'])
@permission_required('view_all')
def remove_server_disk(server_name, device):
    """서버 디스크 제거"""
    try:
        from app.services.proxmox_service import ProxmoxService
        proxmox_service = ProxmoxService()
        
        result = proxmox_service.remove_server_disk(server_name, device)
        if result['success']:
            return jsonify(result)
        else:
            return jsonify({'error': result.get('message', '디스크 제거 실패')}), 500
            
    except Exception as e:
        logger.error(f"디스크 제거 실패: {str(e)}")
        return jsonify({'error': str(e)}), 500    

@bp.route('/api/roles/assign_bulk', methods=['POST'])
@permission_required('assign_roles')
def assign_role_bulk():
    """다중 서버에 역할 할당"""
    try:
        logger.info(f"🔧 다중 서버 역할 할당 요청")
        
        data = request.get_json()
        server_names = data.get('server_names', [])
        role = data.get('role')
        
        logger.info(f"🔧 대상 서버들: {server_names}")
        logger.info(f"🔧 할당할 역할: {role}")
        
        if not server_names:
            return jsonify({'error': '서버 목록을 지정해야 합니다.'}), 400
        
        if not role or role == '':
            return jsonify({'error': '역할(role)을 지정해야 합니다.'}), 400
        
        # "none" 값을 역할 해제로 처리
        if role == 'none':
            logger.info(f"🔧 역할 해제 요청으로 변환: none → None")
            role = None
        
        # AnsibleService를 통해 한 번에 역할 할당 (동적 인벤토리 + --limit)
        ansible_service = AnsibleService()
        # DB에서 대상 서버 정보 수집 (IP 필수)
        db_servers = Server.query.filter(Server.name.in_(server_names)).all()
        target_servers = []
        missing = []
        for s in db_servers:
            if s.ip_address:
                target_servers.append({'ip_address': s.ip_address})
            else:
                missing.append(s.name)
        
        # 역할 해제인 경우 별도 처리 (Ansible 실행 없이 DB만 업데이트)
        if role is None:
            logger.info(f"🔧 역할 해제: DB에서만 역할 제거")
            updated_count = 0
            for server in db_servers:
                server.role = None
                updated_count += 1
            
            from app import db
            db.session.commit()
            
            return jsonify({
                'success': True,
                'message': f'{updated_count}개 서버에서 역할이 해제되었습니다.',
                'targets': [s.name for s in db_servers],
                'missing_ip': missing
            })
        
        if not target_servers:
            return jsonify({'error': '선택된 서버들에 유효한 IP가 없습니다.'}), 400
        
        success, message = ansible_service.run_role_for_multiple_servers(target_servers, role)
        logger.info(f"🔧 일괄 역할 실행 결과: success={success}")

        # 실행 결과 반영: DB 업데이트 및 알림 생성
        try:
            from app import db
            from app.models.notification import Notification

            if success:
                # DB에 역할 반영
                updated = 0
                for s in db_servers:
                    # 대상에 포함된 서버만
                    if s.ip_address and any(t['ip_address'] == s.ip_address for t in target_servers):
                        s.role = role
                        updated += 1
                        # 성공 알림 생성
                        n = Notification.create_notification(
                            type='ansible_role',
                            title=f"서버 {s.name} 역할 할당 완료",
                            message=f"역할 '{role}'이 성공적으로 적용되었습니다.",
                            # Ansible stdout(성공 로그)을 details로 저장 (길면 그대로 저장, UI에서 모달로 표시)
                            details=message,
                            severity='success'
                        )
                        logger.info(f"알림 생성: id={n.id} 서버={s.name}")
                db.session.commit()
                logger.info(f"일괄 역할 DB 업데이트 완료: {updated}개 서버")
            else:
                # 실패 알림(요약)
                for s in db_servers:
                    n = Notification.create_notification(
                        type='ansible_role',
                        title=f"서버 {s.name} 역할 할당 실패",
                        message="Ansible 실행 중 오류가 발생했습니다.",
                        details=message,
                        severity='error'
                    )
                    logger.info(f"알림 생성: id={n.id} 서버={s.name} (실패)")
        except Exception as notify_err:
            logger.warning(f"일괄 역할 알림/DB 반영 중 오류: {notify_err}")

        return jsonify({
            'success': success,
            'message': message,
            'targets': [s['ip_address'] for s in target_servers],
            'missing_ip': missing
        })
        
    except Exception as e:
        logger.error(f"다중 서버 역할 할당 실패: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# 누락된 API 엔드포인트들 추가

@bp.route('/api/server_status/<server_name>', methods=['GET'])
@login_required
def get_server_status(server_name):
    """서버 상태 조회"""
    try:
        from app.services.proxmox_service import ProxmoxService
        proxmox_service = ProxmoxService()
        result = proxmox_service.get_server_status(server_name)
        
        if result['success']:
            return jsonify(result['data'])
        else:
            return jsonify({'error': result['message']}), 500
    except Exception as e:
        logger.error(f"서버 상태 조회 실패: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/roles/available', methods=['GET'])
@login_required
def get_available_roles():
    """사용 가능한 역할 목록 조회"""
    try:
        roles = {
            'web': {'name': '웹서버', 'description': '웹 서비스 제공'},
            'was': {'name': 'WAS', 'description': '애플리케이션 서버'},
            'db': {'name': 'DB', 'description': '데이터베이스 서버'},
            'java': {'name': 'JAVA', 'description': '자바 서버'},
            'search': {'name': '검색', 'description': '검색 서버'},
            'ftp': {'name': 'FTP', 'description': '파일 서버'}
        }
        
        return jsonify({
            'success': True,
            'roles': roles
        })
        
    except Exception as e:
        logger.error(f"역할 목록 조회 실패: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/roles/validate/<role_name>', methods=['GET'])
@login_required
def validate_role(role_name):
    """역할 유효성 검사"""
    try:
        valid_roles = ['web', 'was', 'db', 'java', 'search', 'ftp']
        
        if role_name in valid_roles:
            return jsonify({
                'success': True,
                'valid': True,
                'message': f'역할 "{role_name}"은 유효합니다'
            })
        else:
            return jsonify({
                'success': True,
                'valid': False,
                'message': f'역할 "{role_name}"은 유효하지 않습니다'
            })
            
    except Exception as e:
        logger.error(f"역할 유효성 검사 실패: {str(e)}")
        return jsonify({'error': str(e)}), 500 

@bp.route('/api/datastores', methods=['GET'])
@login_required
def get_datastores():
    """사용 가능한 datastore 목록 조회"""
    try:
        # Proxmox에서 datastore 목록 가져오기
        proxmox_service = ProxmoxService()
        datastores = proxmox_service.get_datastores()
        
        # 환경변수에서 기본 datastore 설정 가져오기
        env_vars = load_env_file()
        hdd_datastore = env_vars.get('PROXMOX_HDD_DATASTORE', 'local-lvm')
        ssd_datastore = env_vars.get('PROXMOX_SSD_DATASTORE', 'local')
        
        # datastore 목록을 포맷팅
        formatted_datastores = []
        for datastore in datastores:
            formatted_datastores.append({
                'id': datastore['id'],
                'name': datastore['id'],  # ID를 이름으로 사용
                'type': datastore.get('type', 'unknown'),
                'size': datastore.get('size', 0),
                'used': datastore.get('used', 0),
                'available': datastore.get('available', 0),
                'is_default_hdd': datastore['id'] == hdd_datastore,
                'is_default_ssd': datastore['id'] == ssd_datastore
            })
        
        return jsonify({
            'success': True,
            'datastores': formatted_datastores,
            'default_hdd': hdd_datastore,
            'default_ssd': ssd_datastore
        })
        
    except Exception as e:
        logger.error(f"Datastore 목록 조회 실패: {str(e)}")
        return jsonify({'error': str(e)}), 500        