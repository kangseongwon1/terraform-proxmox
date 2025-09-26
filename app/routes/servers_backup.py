"""
?�버 관�?관???�우??"""
from flask import Blueprint, request, jsonify, render_template, current_app
from flask_login import login_required, current_user
from functools import wraps
from app.models import Server, User, UserPermission
from app.services import ProxmoxService, TerraformService, AnsibleService, NotificationService
from app.utils.os_classifier import classify_os_type, get_default_username, get_default_password
from app.utils.redis_utils import redis_utils
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

# 로거 ?�정
logger = logging.getLogger(__name__)

bp = Blueprint('servers', __name__)


# ?�역 ?�업 ?�태 dict
tasks = {}

def _remove_from_known_hosts(ip_address: str) -> bool:
    """SSH known_hosts ?�일?�서 ?�정 IP ?�거"""
    try:
        # ?�용?????�렉?�리??.ssh/known_hosts ?�일 경로
        home_dir = os.path.expanduser('~')
        known_hosts_path = os.path.join(home_dir, '.ssh', 'known_hosts')
        
        if not os.path.exists(known_hosts_path):
            logger.info(f"known_hosts ?�일??존재?��? ?�음: {known_hosts_path}")
            return True
        
        # ssh-keygen 명령?�로 ?�당 IP?????�거
        try:
            result = subprocess.run([
                'ssh-keygen', '-R', ip_address
            ], capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                logger.info(f"ssh-keygen?�로 {ip_address} ?�거 ?�공")
                return True
            else:
                logger.warning(f"ssh-keygen ?�행 결과: {result.stderr}")
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            logger.warning(f"ssh-keygen ?�행 ?�패: {e}")
        
        # ssh-keygen???�패?�면 ?�동?�로 ?�일 ?�집
        try:
            logger.info(f"?�� ?�동?�로 known_hosts?�서 {ip_address} ?�거 ?�도...")
            
            # 백업 ?�일 ?�성
            backup_path = f"{known_hosts_path}.backup.{int(time.time())}"
            subprocess.run(['cp', known_hosts_path, backup_path], check=True)
            
            # ?�당 IP가 ?�함???�인 ?�거
            with open(known_hosts_path, 'r') as f:
                lines = f.readlines()
            
            # IP가 ?�함?��? ?��? ?�인?�만 ?��?
            filtered_lines = []
            removed_count = 0
            
            for line in lines:
                if ip_address not in line:
                    filtered_lines.append(line)
                else:
                    removed_count += 1
                    logger.info(f"?���??�거???�인: {line.strip()}")
            
            # ?�정???�용???�일???�기
            with open(known_hosts_path, 'w') as f:
                f.writelines(filtered_lines)
            
            logger.info(f"known_hosts ?�동 ?�집 ?�료: {removed_count}�??�인 ?�거")
            return True
            
        except Exception as manual_error:
            logger.error(f"known_hosts ?�동 ?�집 ?�패: {manual_error}")
            return False
            
    except Exception as e:
        logger.error(f"known_hosts ?�거 �??�류: {e}")
        return False

def create_task(status, type, message):
    task_id = str(uuid.uuid4())
    tasks[task_id] = {
        'status': status, 
        'type': type, 
        'message': message,
        'created_at': time.time(),
        'timeout': 18000  # 5?�간 ?�?�아??    }
    logger.info(f"?�� Task ?�성: {task_id} - {status} - {message}")
    return task_id

def update_task(task_id, status, message=None):
    if task_id in tasks:
        tasks[task_id]['status'] = status
        if message:
            tasks[task_id]['message'] = message
        logger.info(f"?�� Task ?�데?�트: {task_id} - {status} - {message}")
    else:
        logger.error(f"Task�?찾을 ???�음: {task_id}")

def check_task_timeout():
    """Task ?�?�아??체크"""
    current_time = time.time()
    for task_id, task_info in list(tasks.items()):
        if task_info['status'] == 'running':
            elapsed_time = current_time - task_info['created_at']
            if elapsed_time > task_info['timeout']:
                timeout_hours = task_info['timeout'] / 3600
                logger.info(f"??Task ?�?�아?? {task_id} (경과?�간: {elapsed_time:.1f}�? ?�정???�?�아?? {timeout_hours:.1f}?�간)")
                update_task(task_id, 'failed', f'?�업 ?�?�아??({timeout_hours:.1f}?�간 초과)')

@bp.route('/api/tasks/status')
def get_task_status():
    task_id = request.args.get('task_id')
    logger.info(f"?�� Task ?�태 조회: {task_id}")
    logger.info(f"?�� ?�재 Tasks: {list(tasks.keys())}")
    
    # ?�?�아??체크
    check_task_timeout()
    
    if not task_id:
        return jsonify({'error': 'task_id가 ?�요?�니??'}), 400
    
    if task_id not in tasks:
        logger.error(f"Task�?찾을 ???�음 (404): {task_id}")
        # 404 ?�러 ??task�??�동?�로 종료 ?�태�?변�?        tasks[task_id] = {
            'status': 'failed', 
            'type': 'unknown', 
            'message': 'Task�?찾을 ???�어 ?�동 종료??,
            'created_at': time.time(),
            'timeout': 18000
        }
        logger.info(f"?�� Task ?�동 종료 처리: {task_id}")
        return jsonify(tasks[task_id])
    
    return jsonify(tasks[task_id])

@bp.route('/api/tasks/config')
def get_task_config():
    """Task ?�정 ?�보 ?�공 (?�?�아????"""
    return jsonify({
        'timeout': 18000,  # 5?�간 (�??�위)
        'timeout_hours': 5,  # 5?�간 (?�간 ?�위)
        'polling_interval': 5000  # ?�링 간격 (밀리초 ?�위)
    })

@bp.route('/api/servers', methods=['GET'])
@permission_required('view_all')
def list_servers():
    """?�버 목록 조회"""
    try:
        servers = Server.query.all()
        return jsonify({
            'success': True,
            'servers': [server.to_dict() for server in servers]
        })
    except Exception as e:
        logger.error(f"?�버 목록 조회 ?�패: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/servers/brief', methods=['GET'])
@permission_required('view_all')
def get_servers_brief():
    """지?�한 ?�버?�의 경량 ?�보(??��/보안그룹/OS/IP)�?반환"""
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
        logger.error(f"경량 ?�버 ?�보 조회 ?�패: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/debug/servers', methods=['GET'])
@login_required
def debug_servers():
    """?�버 ?�버�??�보"""
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
        logger.error(f"?�버 ?�버�??�보 조회 ?�패: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/servers', methods=['POST'])
@permission_required('create_server')
def create_server():
    """?�버 ?�성"""
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
        
        # IP 주소�?network_devices?�서 추출
        ip_address = ''
        if network_devices:
            ip_addresses = [device.get('ip_address', '') for device in network_devices if device.get('ip_address')]
            ip_address = ', '.join(ip_addresses) if ip_addresses else ''
        
        if not server_name:
            return jsonify({'error': '?�버 ?�름???�요?�니??'}), 400
        
        # ?�버 ?�름 중복 ?�인
        existing_server = Server.query.filter_by(name=server_name).first()
        if existing_server:
            return jsonify({'error': '?��? 존재?�는 ?�버 ?�름?�니??'}), 400
        
        # Task ?�성
        task_id = create_task('running', 'create_server', f'?�버 {server_name} ?�성 �?..')
        
        def create_server_task():
            try:
                from app import create_app
                app = create_app()
                with app.app_context():
                    logger.info(f"?�� ?�버 ?�성 ?�업 ?�작: {server_name}")
                    
                    # Terraform ?�비??초기??                    terraform_service = TerraformService()
                    
                    # Proxmox ?�비??초기??                    proxmox_service = ProxmoxService()
                    
                    # ?�플�??�름 가?�오�?(template_vm_id가 ?�는 경우)
                    template_name = 'rocky-9-template'  # 기본�?                    if template_vm_id:
                        try:
                            # Proxmox?�서 ?�플�??�보 조회
                            headers, error = proxmox_service.get_proxmox_auth()
                            if not error:
                                vms, vm_error = proxmox_service.get_proxmox_vms(headers)
                                if not vm_error:
                                    for vm in vms:
                                        if vm.get('vmid') == template_vm_id:
                                            template_name = vm.get('name', 'rocky-9-template')
                                            break
                        except Exception as e:
                            logger.warning(f"?�플�??�보 조회 ?�패: {e}")
                            template_name = 'rocky-9-template'
                    
                    # OS ?�???�적 분류
                    os_type = classify_os_type(template_name)
                    
                    # 기본 ?�용?�명/비�?번호 ?�정 (?�용?��? ?�력?��? ?��? 경우)
                    current_vm_username = vm_username if vm_username else get_default_username(os_type)
                    current_vm_password = vm_password if vm_password else get_default_password(os_type)
                    
                    # ?�버 ?�정 ?�성
                    # .env ?�일??직접 ?�어?�는 ?�수
                    def load_env_file():
                        """?�로?�트 루트??.env ?�일??직접 ?�어???�셔?�리�?반환"""
                        env_vars = {}
                        try:
                            # ?�로?�트 루트 경로 찾기 (app/routes/servers.py -> app -> project_root)
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
                                print(f"?�� .env ?�일 로드 ?�공: {env_file}")
                            else:
                                print(f"?�️ .env ?�일??찾을 ???�습?�다: {env_file}")
                            
                            return env_vars
                        except Exception as e:
                            print(f"?�️ .env ?�일 ?�기 ?�패: {e}")
                            return {}

                    # ?�용�?                    env_vars = load_env_file()
                    hdd_datastore = env_vars.get('PROXMOX_HDD_DATASTORE')
                    ssd_datastore = env_vars.get('PROXMOX_SSD_DATASTORE')

                    logger.info(f"?�� .env?�서 ?��? datastore ?�정:")
                    logger.info(f"   PROXMOX_HDD_DATASTORE: {hdd_datastore}")
                    logger.info(f"   PROXMOX_SSD_DATASTORE: {ssd_datastore}")

                    # ?�스???�정 ???�태 로그
                    logger.info(f"?�� ?�스???�정 ???�태:")
                    for i, disk in enumerate(disks):
                        logger.info(f"   ?�스??{i}: {disk}")

                    # ?�스???�정??datastore ?�동 ?�정
                    for i, disk in enumerate(disks):
                        logger.info(f"?�� ?�스??{i} 처리 ?�작: {disk}")
                        
                        if 'disk_type' not in disk:
                            disk['disk_type'] = 'hdd'
                            logger.info(f"?�� ?�스??{i}: disk_type??'hdd'�??�정")
                        if 'file_format' not in disk:
                            disk['file_format'] = 'auto'
                            logger.info(f"?�� ?�스??{i}: file_format??'auto'�??�정")
                        
                        # datastore_id가 ?�으�?"auto"�??�정 (Terraform?�서 ?�경변???�용)
                        if 'datastore_id' not in disk:
                            disk['datastore_id'] = 'auto'
                            logger.info(f"?�� ?�스??{i}: datastore_id�?'auto'�??�정 (Terraform?�서 ?�경변???�용)")
                        elif disk['datastore_id'] == 'local-lvm':
                            # local-lvm?� 기본값이므�?auto�?변경하???�경변???�용
                            disk['datastore_id'] = 'auto'
                            logger.info(f"?�� ?�스??{i}: local-lvm??auto�?변�?(?�경변???�용)")
                        else:
                            logger.info(f"?�� ?�스??{i}: datastore_id가 ?��? ?�정?? {disk['datastore_id']}")

                    # ?�스???�정 ???�태 로그
                    logger.info(f"?�� ?�스???�정 ???�태:")
                    for i, disk in enumerate(disks):
                        logger.info(f"   ?�스??{i}: {disk}")
                    
                    server_data = {
                        'name': server_name,
                        'cpu': cpu,
                        'memory': memory,
                        'role': role,
                        'os_type': os_type,  # ?�적?�로 분류??OS ?�??                        'disks': disks,
                        'network_devices': network_devices,
                        'template_vm_id': template_vm_id,
                        'vm_username': current_vm_username,
                        'vm_password': current_vm_password
                    }
                    logger.info(f"?�� ?�버 ?�정 ?�성 ?�작: {json.dumps(server_data, indent=2)}")
                    
                    try:
                        config_success = terraform_service.create_server_config(server_data)
                        logger.info(f"?�� ?�버 ?�정 ?�성 결과: {config_success}")
                        
                        if not config_success:
                            error_msg = '?�버 ?�정 ?�성 ?�패'
                            logger.error(f"{error_msg}")
                            update_task(task_id, 'failed', error_msg)
                            return
                    except Exception as config_error:
                        error_msg = f'?�버 ?�정 ?�성 �??�외 발생: {str(config_error)}'
                        logger.error(f"{error_msg}")
                        import traceback
                        traceback.print_exc()
                        update_task(task_id, 'failed', error_msg)
                        return
                    
                    # ?�프??배포
                    logger.info(f"?�� ?�프??배포 ?�작: {server_name}")
                    try:
                        deploy_success, deploy_message = terraform_service.deploy_infrastructure()
                        logger.info(f"?�� ?�프??배포 결과: success={deploy_success}, message={deploy_message}")
                        
                        if not deploy_success:
                            logger.error(f"?�프??배포 ?�패: {deploy_message}")
                            update_task(task_id, 'failed', f'?�프??배포 ?�패: {deploy_message}')
                            return
                    except Exception as deploy_error:
                        error_msg = f"?�프??배포 �??�외 발생: {str(deploy_error)}"
                        logger.error(f"{error_msg}")
                        import traceback
                        traceback.print_exc()
                        update_task(task_id, 'failed', error_msg)
                        return
                    
                    # Proxmox?�서 ?�제 VM ?�성 ?�인
                    proxmox_service = ProxmoxService()
                    vm_exists = proxmox_service.check_vm_exists(server_name)
                    
                    if not vm_exists:
                        update_task(task_id, 'failed', 'Proxmox?�서 VM??찾을 ???�습?�다.')
                        return
                    
                    # VM ID 가?�오�?                    vm_id = None
                    try:
                        # Terraform output?�서 VM ID 가?�오�?                        terraform_output = terraform_service.output()
                        logger.info(f"?�� Terraform output ?�체: {terraform_output}")
                        
                        if 'vm_ids' in terraform_output:
                            vm_ids_data = terraform_output['vm_ids']
                            logger.info(f"?�� vm_ids ?�이?? {vm_ids_data}")
                            
                            # Terraform output 구조: {"vm_ids": {"value": {"test1": 110}}}
                            if 'value' in vm_ids_data and server_name in vm_ids_data['value']:
                                vm_id = vm_ids_data['value'][server_name]
                                logger.info(f"?�� Terraform output?�서 VM ID 조회: {server_name} = {vm_id}")
                        
                        # VM ID가 ?�으�?Proxmox API?�서 조회
                        if not vm_id:
                            vm_exists, vm_info = proxmox_service.check_vm_exists(server_name)
                            if vm_exists and vm_info:
                                vm_id = vm_info.get('vmid')
                                logger.info(f"?�� Proxmox API?�서 VM ID 조회: {server_name} = {vm_id}")
                    except Exception as e:
                        logger.warning(f"VM ID 조회 ?�패: {e}")
                        import traceback
                        traceback.print_exc()
                    
                    # IP 주소 처리 (리스?�인 경우 문자?�로 변??
                    ip_address_str = ip_address
                    if isinstance(ip_address, list):
                        ip_address_str = ', '.join(ip_address) if ip_address else ''
                    
                    # DB???�버 ?�보 ?�??(VM ID ?�함)
                    new_server = Server(
                        name=server_name,
                        vmid=vm_id,  # VM ID 추�?
                        ip_address=ip_address_str,  # IP 주소 추�? (문자?�로 변??
                        role=role,  # ??�� ?�보 추�?
                        status='stopped',  # 초기 ?�태??중�???                        cpu=cpu,
                        memory=memory,
                        os_type=os_type  # OS ?�??추�?
                    )
                    db.session.add(new_server)
                    db.session.commit()
                    logger.info(f"DB???�버 ?�???�료: {server_name} (ID: {new_server.id}, VM ID: {vm_id})")
                    
                    # Node Exporter ?�동 ?�치 (모니?�링??
                    ansible_service = AnsibleService()
                    node_exporter_installed = False
                    try:
                        # IP 주소?�서 �?번째 IP 추출 (Node Exporter ?�치??
                        server_ip = ip_address_str.split(',')[0].strip() if ip_address_str else ''
                        if server_ip:
                            logger.info(f"?�� Node Exporter ?�동 ?�치 ?�작: {server_name} ({server_ip})")
                            node_exporter_installed = ansible_service._install_node_exporter_if_needed(server_name, server_ip)
                            if node_exporter_installed:
                                logger.info(f"Node Exporter ?�치 ?�료: {server_name}")
                            else:
                                logger.warning(f"Node Exporter ?�치 ?�패: {server_name}")
                        else:
                            logger.warning(f"IP 주소가 ?�어 Node Exporter ?�치 ?�킵: {server_name}")
                    except Exception as e:
                        logger.warning(f"Node Exporter ?�치 �??�류: {e}")
                    
                    # Ansible???�한 ??���??�프?�웨???�치 (Node Exporter??별도 ?�치)
                    if role and role != 'none':
                        logger.info(f"?�� Ansible ??�� ?�당 ?�작: {server_name} - {role}")
                        try:
                            # ?�버 ?�성 ?�에????���??�치 (Node Exporter???�에??별도 ?�치)
                            ansible_success, ansible_message = ansible_service.run_playbook(
                                role=role,
                                extra_vars={},  # Node Exporter ?�치 변???�거
                                target_server=server_ip
                            )
                            
                            if ansible_success:
                                logger.info(f"Ansible ??�� ?�당 ?�공: {server_name} - {role}")
                                update_task(task_id, 'completed', f'?�버 {server_name} ?�성 �?{role} ??�� ?�당 ?�료')
                                # ?�공 ?�림 ?�성
                                NotificationService.create_server_notification(
                                    server_name, 'create', 'success', 
                                    f'?�버 {server_name} ?�성 �?{role} ??�� ?�당???�료?�었?�니?? Node Exporter: {"?�치?? if node_exporter_installed else "?�치 ?�됨"}'
                                )
                            else:
                                logger.warning(f"Ansible ??�� ?�당 ?�패: {server_name} - {role}, 메시지: {ansible_message}")
                                update_task(task_id, 'completed', f'?�버 {server_name} ?�성 ?�료 (Ansible ?�패: {ansible_message})')
                                # 부�??�공 ?�림 ?�성
                                NotificationService.create_server_notification(
                                    server_name, 'create', 'warning', 
                                    f'?�버 {server_name} ?�성 ?�료 (Ansible ?�패: {ansible_message})'
                                )
                        except Exception as ansible_error:
                            logger.warning(f"Ansible ?�행 �??�류: {str(ansible_error)}")
                            update_task(task_id, 'completed', f'?�버 {server_name} ?�성 ?�료 (Ansible ?�류: {str(ansible_error)})')
                            # 부�??�공 ?�림 ?�성
                            NotificationService.create_server_notification(
                                server_name, 'create', 'warning', 
                                f'?�버 {server_name} ?�성 ?�료 (Ansible ?�류: {str(ansible_error)})'
                            )
                    else:
                        update_task(task_id, 'completed', f'?�버 {server_name} ?�성 ?�료')
                        # ?�공 ?�림 ?�성
                        NotificationService.create_server_notification(
                            server_name, 'create', 'success', 
                            f'?�버 {server_name} ?�성???�료?�었?�니??'
                        )
                    
                    # Prometheus ?�정 ?�데?�트 (?�버 ?�성 ?�료 ??
                    try:
                        from app.services.prometheus_service import PrometheusService
                        prometheus_service = PrometheusService()
                        prometheus_updated = prometheus_service.update_prometheus_config()
                        
                        if prometheus_updated:
                            logger.info(f"Prometheus ?�정 ?�데?�트 ?�료: {server_name}")
                        else:
                            logger.warning(f"Prometheus ?�정 ?�데?�트 ?�패: {server_name}")
                            print(prometheus_service.get_manual_setup_instructions())
                    except Exception as e:
                        logger.warning(f"Prometheus ?�정 ?�데?�트 �??�류: {e}")
                        logger.info("?�� Prometheus ?�동 ?�정???�요?????�습?�다.")
                    
                    # Node Exporter ?�치 ?�공 ?��??� 관계없??Prometheus ?�정 ?�데?�트
                    if not node_exporter_installed and server_ip:
                        logger.info(f"?�� Node Exporter ?�치 ?�패?��?�?Prometheus ?�정?� ?�데?�트: {server_ip}")
                        try:
                            from app.services.prometheus_service import PrometheusService
                            prometheus_service = PrometheusService()
                            prometheus_updated = prometheus_service.update_prometheus_config()
                            if prometheus_updated:
                                logger.info(f"Prometheus ?�정 ?�데?�트 ?�료 (Node Exporter ?�패 ??: {server_ip}")
                        except Exception as e:
                            logger.warning(f"Prometheus ?�정 ?�데?�트 �??�류 (Node Exporter ?�패 ??: {e}")
                    
                    logger.info(f"?�버 ?�성 ?�료: {server_name}")
                    
            except Exception as e:
                logger.error(f"?�버 ?�성 ?�업 ?�패: {str(e)}")
                update_task(task_id, 'failed', f'?�버 ?�성 �??�류: {str(e)}')
                
                # ?�패 ?�림 ?�성
                try:
                    NotificationService.create_server_notification(
                        server_name, 'create', 'error', 
                        f'?�버 {server_name} ?�성 �??�류가 발생?�습?�다: {str(e)}'
                    )
                except Exception as notif_error:
                    logger.warning(f"?�패 ?�림 ?�성 ?�패: {str(notif_error)}")
                
                # ?�패 ???�리 ?�업
                try:
                    # tfvars?�서 ?�정 ?�거
                    terraform_service = TerraformService()
                    terraform_service.remove_server_config(server_name)
                    
                    # DB?�서 ?�버 ??��
                    failed_server = Server.query.filter_by(name=server_name).first()
                    if failed_server:
                        db.session.delete(failed_server)
                        db.session.commit()
                except Exception as cleanup_error:
                    logger.error(f"?�리 ?�업 ?�패: {str(cleanup_error)}")
        
        # 백그?�운?�에???�버 ?�성 ?�업 ?�행
        thread = threading.Thread(target=create_server_task)
        thread.start()
        
        return jsonify({
            'success': True,
            'task_id': task_id,
            'message': f'?�버 {server_name} ?�성???�작?�었?�니??'
        })
        
    except Exception as e:
        logger.error(f"?�버 ?�성 ?�패: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/create_servers_bulk', methods=['POST'])
@permission_required('create_server')
def create_servers_bulk():
    """?�중 ?�버 ?�성"""
    try:
        data = request.get_json()
        servers_data = data.get('servers', [])
        
        if not servers_data:
            return jsonify({'error': '?�버 ?�이?��? ?�요?�니??'}), 400
        
        # ?�버 ?�름 중복 ?�인
        server_names = [server.get('name') for server in servers_data if server.get('name')]
        for server_name in server_names:
            existing_server = Server.query.filter_by(name=server_name).first()
            if existing_server:
                return jsonify({'error': f'?��? 존재?�는 ?�버 ?�름?�니?? {server_name}'}), 400
        
        # Task ?�성
        task_id = create_task('running', 'create_servers_bulk', f'{len(servers_data)}�??�버 ?�성 �?..')
        
        def create_servers_bulk_task():
            try:
                from app import create_app
                app = create_app()
                with app.app_context():
                    logger.info(f"?�� ?�중 ?�버 ?�성 ?�업 ?�작: {len(servers_data)}�??�버")
                    
                    # Terraform ?�비??초기??                    terraform_service = TerraformService()
                    
                    # 기존 tfvars 로드
                    try:
                        tfvars = terraform_service.load_tfvars()
                        logger.info(f"?�� 기존 tfvars 로드 ?�료: {len(tfvars.get('servers', {}))}�??�버")
                    except Exception as e:
                        logger.error(f"기존 tfvars 로드 ?�패: {e}")
                        # 기본 구조 ?�성
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
                    
                    # ?�버 ?�정 추�?
                    for server_data in servers_data:
                        server_name = server_data.get('name')
                        if not server_name:
                            continue
                        
                        # ?�버�?기본�??�정
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
                        
                        # ?�스???�정??기본�?추�? �?datastore ?�동 ?�정
                        import os
                        # ?�경변?�에??직접 datastore ?�정 가?�오�?                        hdd_datastore = os.environ.get('PROXMOX_HDD_DATASTORE')
                        ssd_datastore = os.environ.get('PROXMOX_SSD_DATASTORE')
                        
                        for disk in server_config['disks']:
                            if 'disk_type' not in disk:
                                disk['disk_type'] = 'hdd'
                            if 'file_format' not in disk:
                                disk['file_format'] = 'auto'
                            # datastore_id가 "auto"?�거???�으�??�경변?�에??가?�온 datastore ?�용
                            if 'datastore_id' not in disk or disk['datastore_id'] == 'auto':
                                if disk['disk_type'] == 'hdd':
                                    disk['datastore_id'] = hdd_datastore if hdd_datastore else 'local-lvm'
                                elif disk['disk_type'] == 'ssd':
                                    disk['datastore_id'] = ssd_datastore if ssd_datastore else 'local'
                                else:
                                    disk['datastore_id'] = hdd_datastore if hdd_datastore else 'local-lvm'
                                
                                logger.info(f"?�� {server_name}: {disk['disk_type']} ?�스??datastore ?�동 ?�정: {disk['datastore_id']}")
                        
                        tfvars['servers'][server_name] = server_config
                        logger.info(f"?�� ?�버 ?�정 추�?: {server_name}")
                    
                    # tfvars ?�일 ?�??                    try:
                        save_success = terraform_service.save_tfvars(tfvars)
                        if not save_success:
                            error_msg = 'tfvars ?�일 ?�???�패'
                            logger.error(f"{error_msg}")
                            update_task(task_id, 'failed', error_msg)
                            return
                        logger.info(f"tfvars ?�일 ?�???�료: {len(tfvars['servers'])}�??�버")
                    except Exception as save_error:
                        error_msg = f'tfvars ?�일 ?�??�??�외 발생: {str(save_error)}'
                        logger.error(f"{error_msg}")
                        import traceback
                        traceback.print_exc()
                        update_task(task_id, 'failed', error_msg)
                        return
                    
                    # ?�로 ?�성???�버?�에 ?�??targeted apply ?�행
                    logger.info(f"?�� Targeted Terraform apply ?�작: {len(servers_data)}�??�버")
                    try:
                        # ?�로 ?�성???�버?�만 ?�?�으�?targeted apply ?�행
                        new_server_targets = []
                        for server_data in servers_data:
                            server_name = server_data.get('name')
                            if server_name:
                                # Terraform 모듈 리소???��??�식: module.server["?�버?�름"]
                                target = f'module.server["{server_name}"]'
                                new_server_targets.append(target)
                        
                        logger.info(f"?�� Targeted apply ?�?? {new_server_targets}")
                        apply_success, apply_message = terraform_service.apply(targets=new_server_targets)
                        logger.info(f"?�� Terraform apply 결과: success={apply_success}, message_length={len(apply_message) if apply_message else 0}")
                        
                        if not apply_success:
                            logger.error(f"Terraform apply ?�패: {apply_message}")
                            update_task(task_id, 'failed', f'Terraform apply ?�패: {apply_message}')
                            return
                    except Exception as apply_error:
                        error_msg = f"Terraform apply �??�외 발생: {str(apply_error)}"
                        logger.error(f"{error_msg}")
                        import traceback
                        traceback.print_exc()
                        update_task(task_id, 'failed', error_msg)
                        return
                    
                    # Proxmox?�서 ?�제 VM ?�성 ?�인
                    proxmox_service = ProxmoxService()
                    created_servers = []
                    failed_servers = []
                    
                    # ?�플�??�보�???번에 조회 (?�율???�상)
                    template_cache = {}
                    try:
                        headers, error = proxmox_service.get_proxmox_auth()
                        if not error:
                            vms, vm_error = proxmox_service.get_proxmox_vms(headers)
                            if not vm_error:
                                for vm in vms:
                                    template_cache[vm.get('vmid')] = vm.get('name', 'rocky-9-template')
                    except Exception as e:
                        logger.warning(f"?�플�??�보 조회 ?�패: {e}")
                    
                    for server_data in servers_data:
                        server_name = server_data.get('name')
                        if not server_name:
                            continue
                        
                        vm_exists = proxmox_service.check_vm_exists(server_name)
                        if vm_exists:
                            created_servers.append(server_name)
                            
                            # IP 주소�?network_devices?�서 추출 (?��? ?�에??처리?��?�??�시 ?�인)
                            ip_address_str = ''
                            network_devices = server_data.get('network_devices', [])
                            if network_devices:
                                ip_addresses = [device.get('ip_address', '') for device in network_devices if device.get('ip_address')]
                                ip_address_str = ', '.join(ip_addresses) if ip_addresses else ''
                            
                            # OS ?�???�적 분류 (캐시???�보 ?�용)
                            template_vm_id = server_data.get('template_vm_id', 8000)
                            template_name = template_cache.get(template_vm_id, 'rocky-9-template')
                            os_type = classify_os_type(template_name)
                            
                            # VM ID 가?�오�?                            vm_id = None
                            try:
                                # Terraform output?�서 VM ID 가?�오�?                                terraform_output = terraform_service.output()
                                logger.info(f"?�� Terraform output ?�체: {terraform_output}")
                                
                                if 'vm_ids' in terraform_output:
                                    vm_ids_data = terraform_output['vm_ids']
                                    logger.info(f"?�� vm_ids ?�이?? {vm_ids_data}")
                                    
                                    # Terraform output 구조: {"vm_ids": {"value": {"test1": 110}}}
                                    if 'value' in vm_ids_data and server_name in vm_ids_data['value']:
                                        vm_id = vm_ids_data['value'][server_name]
                                        logger.info(f"?�� Terraform output?�서 VM ID 조회: {server_name} = {vm_id}")
                                
                                # VM ID가 ?�으�?Proxmox API?�서 조회
                                if not vm_id:
                                    vm_exists, vm_info = proxmox_service.check_vm_exists(server_name)
                                    if vm_exists and vm_info:
                                        vm_id = vm_info.get('vmid')
                                        logger.info(f"?�� Proxmox API?�서 VM ID 조회: {server_name} = {vm_id}")
                            except Exception as e:
                                logger.warning(f"VM ID 조회 ?�패: {e}")
                                import traceback
                                traceback.print_exc()
                            
                            # DB???�버 ?�보 ?�??(VM ID ?�함)
                            new_server = Server(
                                name=server_name,
                                vmid=vm_id,  # VM ID 추�?
                                ip_address=ip_address_str,  # IP 주소 추�?
                                cpu=server_data.get('cpu', 2),
                                memory=server_data.get('memory', 2048),
                                role=server_data.get('role', ''),
                                status='running',
                                os_type=os_type,  # OS ?�??추�?
                                created_at=datetime.utcnow()
                            )
                            
                            try:
                                db.session.add(new_server)
                                db.session.commit()
                                logger.info(f"?�버 DB ?�???�료: {server_name}")
                            except Exception as db_error:
                                logger.warning(f"?�버 DB ?�???�패: {server_name} - {db_error}")
                                db.session.rollback()
                        else:
                            failed_servers.append(server_name)
                            logger.error(f"VM ?�성 ?�인 ?�패: {server_name}")
                    
                    # Node Exporter ?�동 ?�치 (?�성???�버?�에 ?�??
                    if created_servers:
                        logger.info(f"?�� ?�성???�버?�에 Node Exporter ?�동 ?�치 ?�작: {len(created_servers)}�?)
                        ansible_service = AnsibleService()
                        
                        # ?�버 IP ?�집
                        server_ips = []
                        for server_name in created_servers:
                            try:
                                server = Server.query.filter_by(name=server_name).first()
                                if server and server.ip_address:
                                    server_ip = server.ip_address.split(',')[0].strip()
                                    server_ips.append(server_ip)
                                    logger.info(f"?�� Node Exporter ?�치 ?�?? {server_name} ({server_ip})")
                                else:
                                    logger.warning(f"?�버 IP ?�보 ?�음: {server_name}")
                            except Exception as e:
                                logger.warning(f"?�버 IP ?�집 �??�류 ({server_name}): {e}")
                        
                        # ?�괄 ?�치 ?�행 (Node Exporter ?�함)
                        if server_ips:
                            logger.info(f"?�� Node Exporter ?�괄 ?�치 ?�작: {len(server_ips)}�??�버")
                            success, result = ansible_service.run_playbook(
                                role='node_exporter',
                                extra_vars={'install_node_exporter': True},
                                limit_hosts=','.join(server_ips)
                            )
                            
                            if success:
                                logger.info(f"Node Exporter ?�괄 ?�치 ?�공: {len(server_ips)}�??�버")
                            else:
                                logger.error(f"Node Exporter ?�괄 ?�치 ?�패: {result}")
                        else:
                            logger.warning(f"Node Exporter ?�치???�효???�버 IP가 ?�음")
                    
                    # Prometheus ?�정 ?�데?�트 (?�???�버 ?�성 ?�료 ??
                    try:
                        from app.services.prometheus_service import PrometheusService
                        prometheus_service = PrometheusService()
                        prometheus_updated = prometheus_service.update_prometheus_config()
                        
                        if prometheus_updated:
                            logger.info(f"Prometheus ?�정 ?�데?�트 ?�료: {len(created_servers)}�??�버")
                        else:
                            logger.warning(f"Prometheus ?�정 ?�데?�트 ?�패")
                    except Exception as e:
                        logger.warning(f"Prometheus ?�정 ?�데?�트 �??�류: {e}")
                    
                    # 결과 메시지 ?�성
                    if created_servers and not failed_servers:
                        success_msg = f'모든 ?�버 ?�성 ?�료: {", ".join(created_servers)}'
                        update_task(task_id, 'completed', success_msg)
                        logger.info(f"{success_msg}")
                        # ?�공 ?�림 ?�성
                        for server_name in created_servers:
                            try:
                                NotificationService.create_server_notification(
                                    server_name, 'create', 'success', 
                                    f'?�버 {server_name} ?�성???�료?�었?�니??'
                                )
                            except Exception as notif_error:
                                logger.warning(f"?�림 ?�성 ?�패: {str(notif_error)}")
                    elif created_servers and failed_servers:
                        partial_msg = f'?��? ?�버 ?�성 ?�료. ?�공: {", ".join(created_servers)}, ?�패: {", ".join(failed_servers)}'
                        update_task(task_id, 'completed', partial_msg)
                        logger.warning(f"{partial_msg}")
                        # 부�??�공 ?�림 ?�성
                        for server_name in created_servers:
                            try:
                                NotificationService.create_server_notification(
                                    server_name, 'create', 'success', 
                                    f'?�버 {server_name} ?�성???�료?�었?�니??'
                                )
                            except Exception as notif_error:
                                logger.warning(f"?�림 ?�성 ?�패: {str(notif_error)}")
                        for server_name in failed_servers:
                            try:
                                NotificationService.create_server_notification(
                                    server_name, 'create', 'error', 
                                    f'?�버 {server_name} ?�성???�패?�습?�다.'
                                )
                            except Exception as notif_error:
                                logger.warning(f"?�림 ?�성 ?�패: {str(notif_error)}")
                    else:
                        error_msg = f'모든 ?�버 ?�성 ?�패: {", ".join(failed_servers)}'
                        update_task(task_id, 'failed', error_msg)
                        logger.error(f"{error_msg}")
                        # ?�패 ?�림 ?�성
                        for server_name in failed_servers:
                            try:
                                NotificationService.create_server_notification(
                                    server_name, 'create', 'error', 
                                    f'?�버 {server_name} ?�성???�패?�습?�다.'
                                )
                            except Exception as notif_error:
                                logger.warning(f"?�림 ?�성 ?�패: {str(notif_error)}")
                    
                    # Prometheus ?�정 ?�데?�트 (?�중 ?�버 ?�성 ?�료 ??
                    if created_servers:
                        try:
                            from app.services.prometheus_service import PrometheusService
                            prometheus_service = PrometheusService()
                            prometheus_updated = prometheus_service.update_prometheus_config()
                            
                            if prometheus_updated:
                                logger.info(f"Prometheus ?�정 ?�데?�트 ?�료: {len(created_servers)}�??�버")
                            else:
                                logger.warning(f"Prometheus ?�정 ?�데?�트 ?�패")
                                print(prometheus_service.get_manual_setup_instructions())
                        except Exception as e:
                            logger.warning(f"Prometheus ?�정 ?�데?�트 �??�류: {e}")
                            logger.info("?�� Prometheus ?�동 ?�정???�요?????�습?�다.")
                    
            except Exception as e:
                error_msg = f'?�중 ?�버 ?�성 ?�업 �??�외 발생: {str(e)}'
                logger.error(f"{error_msg}")
                import traceback
                traceback.print_exc()
                update_task(task_id, 'failed', error_msg)
        
        # 백그?�운?�에???�업 ?�행
        thread = threading.Thread(target=create_servers_bulk_task)
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'success': True,
            'message': f'{len(servers_data)}�??�버 ?�성 ?�업???�작?�었?�니??',
            'task_id': task_id
        })
        
    except Exception as e:
        logger.error(f"?�중 ?�버 ?�성 API ?�류: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/servers/bulk_action', methods=['POST'])
@permission_required('manage_server')
def bulk_server_action():
    """?�???�버 ?�업 처리"""
    try:
        data = request.get_json()
        server_names = data.get('server_names', [])
        action = data.get('action')  # start, stop, reboot, delete
        
        if not server_names:
            return jsonify({'error': '?�버 목록???�요?�니??'}), 400
            
        if not action:
            return jsonify({'error': '?�업 ?�형???�요?�니??'}), 400
            
        if action not in ['start', 'stop', 'reboot', 'delete']:
            return jsonify({'error': '지?�하지 ?�는 ?�업?�니??'}), 400
        
        logger.info(f"?�� ?�???�버 ?�업: {action} - {len(server_names)}�??�버")
        
        # Task ?�성
        task_id = create_task('running', 'bulk_server_action', f'{len(server_names)}�??�버 {action} ?�업 �?..')
        
        def bulk_action_task():
            try:
                from app import create_app
                app = create_app()
                with app.app_context():
                    logger.info(f"?�� ?�???�버 ?�업 ?�작: {action} - {server_names}")
                    
                    # ??�� ?�업?� Terraform 기반?�로 처리
                    if action == 'delete':
                        success_servers, failed_servers = process_bulk_delete_terraform(server_names)
                    else:
                        # 기존 Proxmox API 기반 ?�업 (start, stop, reboot)
                        success_servers, failed_servers = process_bulk_proxmox_action(server_names, action)
                    
                    # 결과 메시지 ?�성
                    action_names = {
                        'start': '?�작',
                        'stop': '중�?', 
                        'reboot': '?�시??,
                        'delete': '??��'
                    }
                    action_name = action_names.get(action, action)
                    
                    if success_servers and not failed_servers:
                        success_msg = f'모든 ?�버 {action_name} ?�료: {", ".join(success_servers)}'
                        update_task(task_id, 'completed', success_msg)
                        logger.info(f"{success_msg}")
                        
                        # ?�???�업 ?�료 ???�버 ?�림 ?�성
                        from app.models.notification import Notification
                        notification = Notification(
                            type='bulk_server_action',
                            title='?�???�업',
                            message=success_msg,
                            severity='success',
                            details=f'?�업 ?�형: {action_name}\n?�공???�버: {", ".join(success_servers)}'
                        )
                        db.session.add(notification)
                        db.session.commit()
                        logger.info(f"?�� ?�???�업 ?�료 ?�림 ?�성: {success_msg}")
                        
                    elif success_servers and failed_servers:
                        partial_msg = f'?��? ?�버 {action_name} ?�료. ?�공: {", ".join(success_servers)}, ?�패: {len(failed_servers)}�?
                        update_task(task_id, 'completed', partial_msg)
                        logger.warning(f"{partial_msg}")
                        logger.warning(f"?�패 ?�세: {failed_servers}")
                        
                        # 부�??�공 ???�버 ?�림 ?�성
                        from app.models.notification import Notification
                        notification = Notification(
                            type='bulk_server_action',
                            title='?�???�업',
                            message=partial_msg,
                            severity='warning',
                            details=f'?�업 ?�형: {action_name}\n?�공???�버: {", ".join(success_servers)}\n?�패???�버: {len(failed_servers)}�?
                        )
                        db.session.add(notification)
                        db.session.commit()
                        logger.info(f"?�� ?�???�업 부�??�공 ?�림 ?�성: {partial_msg}")
                        
                    else:
                        error_msg = f'모든 ?�버 {action_name} ?�패: {len(failed_servers)}�?
                        update_task(task_id, 'failed', error_msg)
                        logger.error(f"{error_msg}")
                        logger.error(f"?�패 ?�세: {failed_servers}")
                        
                        # ?�패 ???�버 ?�림 ?�성
                        from app.models.notification import Notification
                        notification = Notification(
                            type='bulk_server_action',
                            title='?�???�업',
                            message=error_msg,
                            severity='error',
                            details=f'?�업 ?�형: {action_name}\n?�패???�버: {len(failed_servers)}�?
                        )
                        db.session.add(notification)
                        db.session.commit()
                        logger.info(f"?�� ?�???�업 ?�패 ?�림 ?�성: {error_msg}")
                        
            except Exception as e:
                error_msg = f'?�???�버 ?�업 �??�외 발생: {str(e)}'
                logger.error(f"{error_msg}")
                import traceback
                traceback.print_exc()
                update_task(task_id, 'failed', error_msg)
        
        # 백그?�운?�에???�업 ?�행
        thread = threading.Thread(target=bulk_action_task)
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'success': True,
            'message': f'{len(server_names)}�??�버 {action} ?�업???�작?�었?�니??',
            'task_id': task_id
        })
        
    except Exception as e:
        logger.error(f"?�???�버 ?�업 API ?�류: {str(e)}")
        return jsonify({'error': str(e)}), 500

def process_bulk_delete_terraform(server_names):
    """Terraform 기반 ?�???�버 ??��"""
    success_servers = []
    failed_servers = []
    
    try:
        logger.info(f"?���?Terraform 기반 ?�????�� ?�작: {server_names}")
        
        # 1. ?�버 존재 ?�인 �??�효??검??        valid_servers = []
        for server_name in server_names:
            server = Server.query.filter_by(name=server_name).first()
            if not server:
                failed_servers.append(f"{server_name}: ?�버�?찾을 ???�음")
                continue
            valid_servers.append(server_name)
        
        if not valid_servers:
            logger.info("???�효???�버가 ?�습?�다.")
            return success_servers, failed_servers
        
        # 2. Proxmox API�??�해 ?�버?�을 먼�? 중�? (shutdown ?�??stop ?�용)
        from app.services.proxmox_service import ProxmoxService
        import time
        proxmox_service = ProxmoxService()
        
        logger.info(f"?�� ?�버 중�? ?�계 ?�작: {valid_servers}")
        for server_name in valid_servers:
            try:
                logger.info(f"?�� {server_name} 중�? �?..")
                stop_result = proxmox_service.stop_vm(server_name)
                if stop_result['success']:
                    logger.info(f"{server_name} 중�? ?�공")
                else:
                    logger.warning(f"{server_name} 중�? ?�패: {stop_result['message']}")
                    # 중�? ?�패?�도 계속 진행 (?��? 중�????�태?????�음)
            except Exception as e:
                logger.warning(f"{server_name} 중�? �??�외 발생: {e}")
                # ?�외 발생?�도 계속 진행
        
        # ?�버 중�? ???�시 ?��?(?�전??중�??�도�?
        logger.info("???�버 중�? ?�료 ?��?�?.. (5�?")
        time.sleep(5)
        
        # 3. Terraform ?�정?�서 ??��???�버???�거
        terraform_service = TerraformService()
        tfvars = terraform_service.load_tfvars()
        
        deleted_from_tfvars = []
        for server_name in valid_servers:
            if 'servers' in tfvars and server_name in tfvars['servers']:
                del tfvars['servers'][server_name]
                deleted_from_tfvars.append(server_name)
                logger.info(f"?���?tfvars.json?�서 {server_name} ?�거")
        
        if not deleted_from_tfvars:
            logger.info("??tfvars.json?�서 ??��???�버�?찾을 ???�습?�다.")
            for server_name in valid_servers:
                failed_servers.append(f"{server_name}: tfvars.json?�서 찾을 ???�음")
            return success_servers, failed_servers
        
        # 4. tfvars.json ?�??        terraform_service.save_tfvars(tfvars)
        logger.info(f"?�� tfvars.json ?�데?�트 ?�료: {len(deleted_from_tfvars)}�??�버 ?�거")
        
        # 5. Terraform destroy with targeted resources
        destroy_targets = []
        for server_name in deleted_from_tfvars:
            target = f'module.server["{server_name}"]'
            destroy_targets.append(target)
        
        logger.info(f"?�� Terraform destroy ?�행 - ?�?? {destroy_targets}")
        destroy_success, destroy_message = terraform_service.destroy_targets(destroy_targets)
        
        if destroy_success:
            logger.info(f"Terraform destroy ?�공: {deleted_from_tfvars}")
            
            # 5. SSH known_hosts ?�리 (??��???�버?�의 IP ?�거)
            try:
                for server_name in deleted_from_tfvars:
                    server = Server.query.filter_by(name=server_name).first()
                    if server and server.ip_address:
                        # IP 주소?�서 �?번째 IP 추출
                        first_ip = server.ip_address.split(',')[0].strip()
                        if first_ip:
                            _remove_from_known_hosts(first_ip)
                            logger.info(f"?�� SSH known_hosts?�서 {first_ip} ?�거 ?�료")
            except Exception as e:
                logger.warning(f"SSH known_hosts ?�리 �??�류: {e}")
            
            # 6. Prometheus ?�정 ?�데?�트 (??��???�버???�거)
            try:
                from app.services.prometheus_service import PrometheusService
                prometheus_service = PrometheusService()
                prometheus_updated = prometheus_service.update_prometheus_config()
                
                if prometheus_updated:
                    logger.info(f"Prometheus ?�정 ?�데?�트 ?�료: {len(deleted_from_tfvars)}�??�버 ?�거")
                else:
                    logger.warning(f"Prometheus ?�정 ?�데?�트 ?�패")
            except Exception as e:
                logger.warning(f"Prometheus ?�정 ?�데?�트 �??�류: {e}")
            
            # 6. DB?�서 ?�버 ?�거
            for server_name in deleted_from_tfvars:
                server = Server.query.filter_by(name=server_name).first()
                if server:
                    db.session.delete(server)
                    logger.info(f"?���?DB?�서 {server_name} ?�거")
            
            db.session.commit()
            success_servers.extend(deleted_from_tfvars)
            
        else:
            logger.error(f"Terraform destroy ?�패: {destroy_message}")
            # destroy ?�패 ??tfvars.json 복원
            for server_name in deleted_from_tfvars:
                server = Server.query.filter_by(name=server_name).first()
                if server:
                    # ?�버 ?�보�??�시 tfvars??추�? (복원)
                    if 'servers' not in tfvars:
                        tfvars['servers'] = {}
                    tfvars['servers'][server_name] = {
                        'cores': server.cores,
                        'memory': server.memory,
                        'disk': server.disk,
                        'role': server.role or 'web'
                    }
                failed_servers.append(f"{server_name}: Terraform destroy ?�패")
            
            # tfvars.json 복원
            terraform_service.save_tfvars(tfvars)
            logger.info("?�� tfvars.json 복원 ?�료")
        
    except Exception as e:
        error_msg = f"?�????�� �??�외 발생: {str(e)}"
        logger.error(f"{error_msg}")
        for server_name in server_names:
            if server_name not in success_servers:
                failed_servers.append(f"{server_name}: {error_msg}")
    
    return success_servers, failed_servers

def process_bulk_proxmox_action(server_names, action):
    """Proxmox API 기반 ?�???�버 ?�업 (start, stop, reboot)"""
    success_servers = []
    failed_servers = []
    
    try:
        proxmox_service = ProxmoxService()
        
        for server_name in server_names:
            try:
                logger.info(f"?�� ?�버 ?�업 처리: {server_name} - {action}")
                
                # ?�버 존재 ?�인
                server = Server.query.filter_by(name=server_name).first()
                if not server:
                    failed_servers.append(f"{server_name}: ?�버�?찾을 ???�음")
                    continue
                
                # Proxmox API ?�출
                if action == 'start':
                    result = proxmox_service.start_vm(server_name)
                elif action == 'stop':
                    result = proxmox_service.stop_vm(server_name)
                elif action == 'reboot':
                    result = proxmox_service.reboot_vm(server_name)
                else:
                    failed_servers.append(f"{server_name}: 지?�하지 ?�는 ?�업")
                    continue
                
                if result.get('success', False):
                    success_servers.append(server_name)
                    
                    # DB ?�태 ?�데?�트
                    if action == 'start':
                        server.status = 'running'
                    elif action == 'stop':
                        server.status = 'stopped'
                    # reboot???�태�?running?�로 ?��?
                    
                    db.session.commit()
                    logger.info(f"{server_name} {action} ?�공")
                else:
                    error_msg = result.get('message', '?????�는 ?�류')
                    failed_servers.append(f"{server_name}: {error_msg}")
                    logger.error(f"{server_name} {action} ?�패: {error_msg}")
                    
            except Exception as server_error:
                error_msg = f"{server_name}: {str(server_error)}"
                failed_servers.append(error_msg)
                logger.error(f"{server_name} 처리 �??�류: {server_error}")
    
    except Exception as e:
        error_msg = f"?�??Proxmox ?�업 �??�외 발생: {str(e)}"
        logger.error(f"{error_msg}")
        for server_name in server_names:
            if server_name not in success_servers:
                failed_servers.append(f"{server_name}: {error_msg}")
    
    return success_servers, failed_servers

@bp.route('/api/servers/<server_name>/start', methods=['POST'])
@permission_required('start_server')
def start_server(server_name):
    """?�버 ?�작"""
    try:
        from app.services.proxmox_service import ProxmoxService
        proxmox_service = ProxmoxService()
        
        server = Server.query.filter_by(name=server_name).first()
        if not server:
            return jsonify({'error': '?�버�?찾을 ???�습?�다.'}), 404
        
        if proxmox_service.start_server(server_name):
            server.status = 'running'
            db.session.commit()
            return jsonify({'success': True, 'message': f'?�버 {server_name}가 ?�작?�었?�니??'})
        else:
            return jsonify({'error': f'?�버 {server_name} ?�작???�패?�습?�다.'}), 500
    except Exception as e:
        logger.error(f"?�버 ?�작 ?�패: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/servers/<server_name>/stop', methods=['POST'])
@permission_required('stop_server')
def stop_server(server_name):
    """?�버 중�?"""
    try:
        from app.services.proxmox_service import ProxmoxService
        proxmox_service = ProxmoxService()
        
        server = Server.query.filter_by(name=server_name).first()
        if not server:
            return jsonify({'error': '?�버�?찾을 ???�습?�다.'}), 404
        
        if proxmox_service.stop_server(server_name):
            server.status = 'stopped'
            db.session.commit()
            return jsonify({'success': True, 'message': f'?�버 {server_name}가 중�??�었?�니??'})
        else:
            return jsonify({'error': f'?�버 {server_name} 중�????�패?�습?�다.'}), 500
    except Exception as e:
        logger.error(f"?�버 중�? ?�패: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/servers/<server_name>/reboot', methods=['POST'])
@permission_required('reboot_server')
def reboot_server(server_name):
    """?�버 ?��???""
    try:
        from app.services.proxmox_service import ProxmoxService
        proxmox_service = ProxmoxService()
        
        server = Server.query.filter_by(name=server_name).first()
        if not server:
            return jsonify({'error': '?�버�?찾을 ???�습?�다.'}), 404
        
        if proxmox_service.reboot_server(server_name):
            return jsonify({'success': True, 'message': f'?�버 {server_name}가 ?��??�되?�습?�다.'})
        else:
            return jsonify({'error': f'?�버 {server_name} ?��??�에 ?�패?�습?�다.'}), 500
    except Exception as e:
        logger.error(f"?�버 ?��????�패: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/servers/<server_name>/delete', methods=['POST'])
@permission_required('delete_server')
def delete_server(server_name):
    """?�버 ??��"""
    try:
        server = Server.query.filter_by(name=server_name).first()
        if not server:
            return jsonify({'error': '?�버�?찾을 ???�습?�다.'}), 404
        
        logger.info(f"?�� ?�버 ??�� ?�작: {server_name}")
        
        # ?�기?�으�??�버 ??�� ?�행
        success_servers, failed_servers = process_bulk_delete_terraform([server_name])
        
        if success_servers and server_name in success_servers:
            logger.info(f"?�버 ??�� ?�료: {server_name}")
            return jsonify({
                'success': True,
                'message': f'?�버 {server_name}가 ??��?�었?�니??'
            })
        else:
            # ?�패 ?�인 메시지 추출
            failure_reason = "?????�는 ?�류"
            for failed in failed_servers:
                if server_name in failed:
                    failure_reason = failed.split(": ", 1)[1] if ": " in failed else failed
                    break
                        
            logger.error(f"?�버 ??�� ?�패: {failure_reason}")
            return jsonify({
                'success': False,
                'error': f'?�버 ??�� ?�패: {failure_reason}'
            }), 500
        
    except Exception as e:
        logger.error(f"?�버 ??�� ?�패: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/all_server_status', methods=['GET'])
@login_required
def get_all_server_status():
    """모든 ?�버 ?�태 조회 (Redis 캐싱 ?�용)"""
    try:
        # Redis 캐시 ?�인
        cache_key = "servers:all_status"
        cached_data = redis_utils.get_cache(cache_key)
        if cached_data:
            logger.info("?�� Redis 캐시?�서 ?�버 ?�태 ?�이??로드")
            return jsonify(cached_data)
        
        logger.info("?�� ?�버 ?�태 ?�이??조회 (캐시 미스)")
        from app.services.proxmox_service import ProxmoxService
        proxmox_service = ProxmoxService()
        
        # get_all_vms ?�수 ?�용 (?�계 ?�보 ?�함)
        result = proxmox_service.get_all_vms()
        
        if result['success']:
            # 기존 구조?� ?�환?�을 ?�해 ?�이??변??            servers = result['data']['servers']
            stats = result['data']['stats']
            
            # DB?�서 ?�버 ?�보 가?��???병합 (??��, 방화�?그룹 ?�보)
            db_servers = Server.query.all()
            db_server_map = {s.name: s for s in db_servers}
            
            # Proxmox ?�이?�에 DB ?�보 병합
            for vm_key, server_data in servers.items():
                server_name = server_data.get('name')
                if server_name and server_name in db_server_map:
                    db_server = db_server_map[server_name]
                    # DB????���?방화�?그룹 ?�보�?Proxmox ?�이?�에 추�?
                    server_data['role'] = db_server.role
                    server_data['firewall_group'] = db_server.firewall_group
                    server_data['os_type'] = db_server.os_type
                    logger.info(f"?�� ?�버 '{server_name}' DB ?�보 병합: role={db_server.role}, firewall_group={db_server.firewall_group}")
            
            # ?�계 ?�보�??�함?�여 반환
            response_data = {
                'success': True,
                'servers': servers,
                'stats': stats
            }
            
            # Redis??캐시 ?�??(2�?
            redis_utils.set_cache(cache_key, response_data, expire=120)
            logger.info("?�� ?�버 ?�태 ?�이?��? Redis??캐시 ?�??)
            
            return jsonify(response_data)
        else:
            # ?�패 ??기본 구조�?반환
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
        logger.error(f"?�버 ?�태 조회 ?�패: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/servers/async', methods=['POST'])
@permission_required('create_server')
def create_server_async_endpoint():
    """비동�??�버 ?�성"""
    try:
        # 지???�포?�로 ?�환 참조 방�?
        from app.tasks.server_tasks import create_server_async
        data = request.get_json()
        server_name = data.get('name')
        cpu = data.get('cpu', 2)
        memory = data.get('memory', 4)
        disk = data.get('disk', 20)
        os_type = data.get('os_type', 'ubuntu')
        role = data.get('role', '')
        firewall_group = data.get('firewall_group', '')
        
        if not server_name:
            return jsonify({'error': '?�버 ?�름???�요?�니??'}), 400
        
        # ?�버 ?�름 중복 ?�인
        existing_server = Server.query.filter_by(name=server_name).first()
        if existing_server:
            return jsonify({'error': '?��? 존재?�는 ?�버 ?�름?�니??'}), 400
        
        # ?�버 ?�정 구성
        server_config = {
            'name': server_name,
            'cpu': cpu,
            'memory': memory,
            'disk': disk,
            'os_type': os_type,
            'role': role,
            'firewall_group': firewall_group
        }
        
        # Celery ?�업 ?�행
        task = create_server_async.delay(server_config)
        
        logger.info(f"?? 비동�??�버 ?�성 ?�업 ?�작: {server_name} (Task ID: {task.id})")
        
        return jsonify({
            'success': True,
            'task_id': task.id,
            'message': f'?�버 {server_name} ?�성 ?�업???�작?�었?�니??',
            'status': 'queued'
        })
        
    except Exception as e:
        logger.error(f"비동�??�버 ?�성 ?�패: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/servers/bulk_action/async', methods=['POST'])
@permission_required('manage_server')
def bulk_server_action_async_endpoint():
    """비동�??�???�버 ?�업"""
    try:
        # 지???�포?�로 ?�환 참조 방�?
        from app.tasks.server_tasks import bulk_server_action_async
        data = request.get_json()
        server_names = data.get('server_names', [])
        action = data.get('action')
        
        if not server_names:
            return jsonify({'error': '?�버 목록???�요?�니??'}), 400
            
        if not action:
            return jsonify({'error': '?�업 ?�형???�요?�니??'}), 400
            
        if action not in ['start', 'stop', 'reboot', 'delete']:
            return jsonify({'error': '지?�하지 ?�는 ?�업?�니??'}), 400
        
        # Celery ?�업 ?�행
        task = bulk_server_action_async.delay(server_names, action)
        
        logger.info(f"?? 비동�??�???�버 ?�업 ?�작: {action} - {len(server_names)}�??�버 (Task ID: {task.id})")
        
        return jsonify({
            'success': True,
            'task_id': task.id,
            'message': f'{len(server_names)}�??�버 {action} ?�업???�작?�었?�니??',
            'status': 'queued'
        })
        
    except Exception as e:
        logger.error(f"비동�??�???�버 ?�업 ?�패: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/tasks/<task_id>/status', methods=['GET'])
@login_required
def get_task_status_async(task_id):
    """비동�??�업 ?�태 조회"""
    try:
        # Celery ?�업 ?�태 조회
        task = celery_app.AsyncResult(task_id)
        
        if task.state == 'PENDING':
            response = {
                'task_id': task_id,
                'status': 'pending',
                'message': '?�업 ?��?�?..',
                'progress': 0
            }
        elif task.state == 'PROGRESS':
            response = {
                'task_id': task_id,
                'status': 'running',
                'message': task.info.get('status', '?�업 진행 �?..'),
                'progress': task.info.get('current', 0),
                'total': task.info.get('total', 100)
            }
        elif task.state == 'SUCCESS':
            response = {
                'task_id': task_id,
                'status': 'completed',
                'message': task.info.get('message', '?�업 ?�료'),
                'result': task.result
            }
        elif task.state == 'FAILURE':
            response = {
                'task_id': task_id,
                'status': 'failed',
                'message': str(task.info),
                'error': str(task.info)
            }
        else:
            response = {
                'task_id': task_id,
                'status': task.state.lower(),
                'message': f'?�업 ?�태: {task.state}'
            }
        
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"?�업 ?�태 조회 ?�패: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/proxmox_storage', methods=['GET'])
def proxmox_storage():
    """Proxmox ?�토리�? ?�보 조회"""
    try:
        from app.services.proxmox_service import ProxmoxService
        proxmox_service = ProxmoxService()
        
        storage_info = proxmox_service.get_storage_info()
        
        return jsonify({
            'success': True,
            'data': storage_info.get('data', [])  # storage ???�??data ?�로 반환
        })
    except Exception as e:
        logger.error(f"?�토리�? ?�보 조회 ?�패: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/sync_servers', methods=['POST'])
@login_required
def sync_servers():
    """기존 ?�버�?DB???�기??""
    try:
        logger.info("?�� ?�버 ?�기???�작")
        from app.services.proxmox_service import ProxmoxService
        proxmox_service = ProxmoxService()
        
        # Proxmox?�서 ?�버 목록 가?�오�?        vm_list = proxmox_service.get_vm_list()
        logger.info(f"?�� Proxmox?�서 가?�온 ?�버: {[vm['name'] for vm in vm_list]}")
        
        synced_count = 0
        
        for vm in vm_list:
            # DB?�서 ?�버 ?�인
            existing_server = Server.query.filter_by(name=vm['name']).first()
            if not existing_server:
                # ???�버 ?�성
                new_server = Server(
                    name=vm['name'],
                    vmid=vm['vmid'],
                    status=vm['status'],
                    ip_address=vm.get('ip_addresses', [None])[0] if vm.get('ip_addresses') else None
                )
                db.session.add(new_server)
                synced_count += 1
                logger.info(f"?�버 ?�기?? {vm['name']}")
            else:
                # 기존 ?�버 ?�보 ?�데?�트
                existing_server.vmid = vm['vmid']
                existing_server.status = vm['status']
                existing_server.ip_address = vm.get('ip_addresses', [None])[0] if vm.get('ip_addresses') else None
                logger.info(f"?�� ?�버 ?�보 ?�데?�트: {vm['name']}")
        
        db.session.commit()
        logger.info(f"?�버 ?�기???�료: {synced_count}�??�버 추�???)
        
        return jsonify({
            'success': True, 
            'message': f'{synced_count}�??�버가 DB???�기?�되?�습?�다.'
        })
        
    except Exception as e:
        logger.error(f"?�버 ?�기???�패: {str(e)}")
        return jsonify({'error': str(e)}), 500

# 기존 ?�버 관???�우?�들 (?�환???��?)
@bp.route('/')
@login_required
@permission_required('view_all')
def index():
    """?�버 목록 ?�이지"""
    servers = Server.query.all()
    return render_template('servers/index.html', servers=servers)

@bp.route('/create', methods=['GET', 'POST'])
@login_required
@permission_required('create_server')
def create():
    """?�버 ?�성 ?�이지"""
    if request.method == 'POST':
        data = request.get_json()
        server_name = data.get('name')
        cpu = data.get('cpu', 2)
        memory = data.get('memory', 2048)
        
        if not server_name:
            return jsonify({'error': '?�버 ?�름???�요?�니??'}), 400
        
        # ?�버 ?�름 중복 ?�인
        existing_server = Server.query.filter_by(name=server_name).first()
        if existing_server:
            return jsonify({'error': '?��? 존재?�는 ?�버 ?�름?�니??'}), 400
        
        # Task ?�성
        task_id = create_task('running', 'create_server', f'?�버 {server_name} ?�성 �?..')
        
        def create_server_background():
            try:
                from app import create_app
                app = create_app()
                with app.app_context():
                    logger.info(f"?�� ?�버 ?�성 ?�업 ?�작: {server_name}")
                    
                    # Terraform ?�비??초기??                    terraform_service = TerraformService()
                    
                    # ?�버 ?�정 ?�성
                    server_data = {
                        'name': server_name,
                        'cpu': cpu,
                        'memory': memory
                    }
                    config_success = terraform_service.create_server_config(server_data)
                    
                    if not config_success:
                        update_task(task_id, 'failed', f'?�버 ?�정 ?�성 ?�패')
                        return
                    
                    # ?�프??배포
                    deploy_success, deploy_message = terraform_service.deploy_infrastructure()
                    
                    if not deploy_success:
                        update_task(task_id, 'failed', f'?�프??배포 ?�패: {deploy_message}')
                        return
                    
                    # Proxmox?�서 ?�제 VM ?�성 ?�인
                    proxmox_service = ProxmoxService()
                    vm_exists = proxmox_service.check_vm_exists(server_name)
                    
                    if not vm_exists:
                        update_task(task_id, 'failed', 'Proxmox?�서 VM??찾을 ???�습?�다.')
                        return
                    
                    # VM ID 가?�오�?                    vm_id = None
                    try:
                        # Terraform output?�서 VM ID 가?�오�?                        terraform_output = terraform_service.output()
                        logger.info(f"?�� Terraform output ?�체: {terraform_output}")
                        
                        if 'vm_ids' in terraform_output:
                            vm_ids_data = terraform_output['vm_ids']
                            logger.info(f"?�� vm_ids ?�이?? {vm_ids_data}")
                            
                            # Terraform output 구조: {"vm_ids": {"value": {"test1": 110}}}
                            if 'value' in vm_ids_data and server_name in vm_ids_data['value']:
                                vm_id = vm_ids_data['value'][server_name]
                                logger.info(f"?�� Terraform output?�서 VM ID 조회: {server_name} = {vm_id}")
                        
                        # VM ID가 ?�으�?Proxmox API?�서 조회
                        if not vm_id:
                            vm_exists, vm_info = proxmox_service.check_vm_exists(server_name)
                            if vm_exists and vm_info:
                                vm_id = vm_info.get('vmid')
                                logger.info(f"?�� Proxmox API?�서 VM ID 조회: {server_name} = {vm_id}")
                    except Exception as e:
                        logger.warning(f"VM ID 조회 ?�패: {e}")
                        import traceback
                        traceback.print_exc()
                    
                    # 기본�??�정 (???�수?�서??role, os_type, ip_address가 ?�의?��? ?�음)
                    role = ''  # 기본�?                    os_type = 'rocky'  # 기본�?                    ip_address_str = ''  # 기본�?                    
                    # DB???�버 ?�보 ?�??(VM ID ?�함)
                    new_server = Server(
                        name=server_name,
                        vmid=vm_id,  # VM ID 추�?
                        ip_address=ip_address_str,  # IP 주소 추�? (문자?�로 변??
                        role=role,  # ??�� ?�보 추�?
                        status='stopped',  # 초기 ?�태??중�???                        cpu=cpu,
                        memory=memory,
                        os_type=os_type  # OS ?�??추�?
                    )
                    db.session.add(new_server)
                    db.session.commit()
                    logger.info(f"DB???�버 ?�???�료: {server_name} (ID: {new_server.id}, VM ID: {vm_id})")
                    
                    # Node Exporter ?�동 ?�치 (모니?�링?? - IP가 ?�는 경우 ?�킵
                    ansible_service = AnsibleService()
                    node_exporter_installed = False
                    if ip_address_str:
                        try:
                            server_ip = ip_address_str.split(',')[0].strip()
                            logger.info(f"?�� Node Exporter ?�동 ?�치 ?�작: {server_name} ({server_ip})")
                            node_exporter_installed = ansible_service._install_node_exporter_if_needed(server_name, server_ip)
                            if node_exporter_installed:
                                logger.info(f"Node Exporter ?�치 ?�료: {server_name}")
                            else:
                                logger.warning(f"Node Exporter ?�치 ?�패: {server_name}")
                        except Exception as e:
                            logger.warning(f"Node Exporter ?�치 �??�류: {e}")
                    else:
                        logger.warning(f"IP 주소가 ?�어 Node Exporter ?�치 ?�킵: {server_name}")
                    
                    # Ansible???�한 ??���??�프?�웨???�치 (Node Exporter ?�함)
                    if role and role != 'none':
                        logger.info(f"?�� Ansible ??�� ?�당 ?�작: {server_name} - {role}")
                        try:
                            ansible_service = AnsibleService()
                            # ?�버 ?�성 ?�에??Node Exporter???�께 ?�치
                            ansible_success, ansible_message = ansible_service.run_playbook(
                                role=role,
                                extra_vars={'install_node_exporter': True},
                                target_server=ip_address_str
                            )
                            
                            if ansible_success:
                                logger.info(f"Ansible ??�� ?�당 ?�공: {server_name} - {role}")
                            else:
                                logger.warning(f"Ansible ??�� ?�당 ?�패: {server_name} - {role}, 메시지: {ansible_message}")
                        except Exception as ansible_error:
                            logger.warning(f"Ansible ?�행 �??�류: {str(ansible_error)}")
                    
                    update_task(task_id, 'completed', f'?�버 {server_name} ?�성 ?�료')
                    logger.info(f"?�버 ?�성 ?�료: {server_name}")
                    
            except Exception as e:
                logger.error(f"?�버 ?�성 ?�업 ?�패: {str(e)}")
                update_task(task_id, 'failed', f'?�버 ?�성 �??�류: {str(e)}')
        
        thread = threading.Thread(target=create_server_background)
        thread.start()
        
        return jsonify({
            'success': True,
            'task_id': task_id,
            'message': f'?�버 {server_name} ?�성???�작?�었?�니??'
        })
    
    return render_template('servers/create.html')

@bp.route('/<int:server_id>')
@login_required
@permission_required('view_all')
def detail(server_id):
    """?�버 ?�세 ?�이지"""
    server = Server.query.get_or_404(server_id)
    return render_template('servers/detail.html', server=server)



@bp.route('/status')
@login_required
@permission_required('view_all')
def status():
    """?�버 ?�태 조회"""
    servers = Server.query.all()
    return jsonify([server.to_dict() for server in servers]) 


@bp.route('/api/ansible/status', methods=['GET'])
@login_required
def check_ansible_status():
    """Ansible ?�치 ?�태 ?�인"""
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
            'message': f'Ansible ?�태 ?�인 ?�패: {str(e)}'
        }), 500

@bp.route('/api/assign_role/<server_name>', methods=['POST'])
@login_required
@permission_required('assign_roles')
def assign_role_to_server(server_name):
    """?�버????�� ?�당 (DB 기반 + Ansible ?�행)"""
    try:
        logger.info(f"?�� ??�� ?�당 ?�청: {server_name}")
        
        data = request.get_json()
        role = data.get('role')
        logger.info(f"?�� ?�당????��: {role}")
        
        # �?문자?�도 ?�용 (??�� ?�거)
        if role is None:
            return jsonify({'error': '??��(role)??지?�해???�니??'}), 400
        
        # AnsibleService�??�해 ??�� ?�당 (DB ?�데?�트 + Ansible ?�행)
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
        logger.error(f"??�� ?�당 ?�패: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@bp.route('/api/remove_role/<server_name>', methods=['POST'])
@permission_required('remove_role')
def remove_role(server_name):
    """?�버?�서 ??�� ?�거"""
    try:
        from app import db
        server = Server.query.filter_by(name=server_name).first()
        if not server:
            return jsonify({'error': '?�버�?찾을 ???�습?�다.'}), 404
        
        server.role = None
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': f'?�버 {server_name}?�서 ??��???�거?�었?�니??'
        })
    except Exception as e:
        logger.error(f"??�� ?�거 ?�패: {str(e)}")
        return jsonify({'error': str(e)}), 500



@bp.route('/api/server/config/<server_name>', methods=['GET'])
@permission_required('view_all')
def get_server_config(server_name):
    """?�버 ?�정 조회"""
    try:
        from app.services.proxmox_service import ProxmoxService
        proxmox_service = ProxmoxService()
        
        result = proxmox_service.get_server_config(server_name)
        if result['success']:
            return jsonify(result)
        else:
            return jsonify({'error': result.get('message', '?�버 ?�정 조회 ?�패')}), 500
            
    except Exception as e:
        logger.error(f"?�버 ?�정 조회 ?�패: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/server/config/<server_name>', methods=['PUT'])
@permission_required('view_all')
def update_server_config(server_name):
    """?�버 ?�정 ?�데?�트"""
    try:
        data = request.get_json()
        
        from app.services.proxmox_service import ProxmoxService
        proxmox_service = ProxmoxService()
        
        result = proxmox_service.update_server_config(server_name, data)
        if result['success']:
            return jsonify(result)
        else:
            return jsonify({'error': result.get('message', '?�버 ?�정 ?�데?�트 ?�패')}), 500
            
    except Exception as e:
        logger.error(f"?�버 ?�정 ?�데?�트 ?�패: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/server/logs/<server_name>', methods=['GET'])
@permission_required('view_all')
def get_server_logs(server_name):
    """?�버 로그 조회"""
    try:
        from app.services.proxmox_service import ProxmoxService
        proxmox_service = ProxmoxService()
        
        result = proxmox_service.get_server_logs(server_name)
        if result['success']:
            return jsonify(result)
        else:
            return jsonify({'error': result.get('message', '?�버 로그 조회 ?�패')}), 500
            
    except Exception as e:
        logger.error(f"?�버 로그 조회 ?�패: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/server/disk/<server_name>', methods=['POST'])
@permission_required('view_all')
def add_server_disk(server_name):
    """?�버 ?�스??추�?"""
    try:
        data = request.get_json()
        
        from app.services.proxmox_service import ProxmoxService
        proxmox_service = ProxmoxService()
        
        result = proxmox_service.add_server_disk(server_name, data)
        if result['success']:
            return jsonify(result)
        else:
            return jsonify({'error': result.get('message', '?�스??추�? ?�패')}), 500
            
    except Exception as e:
        logger.error(f"?�스??추�? ?�패: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/server/disk/<server_name>/<device>', methods=['DELETE'])
@permission_required('view_all')
def remove_server_disk(server_name, device):
    """?�버 ?�스???�거"""
    try:
        from app.services.proxmox_service import ProxmoxService
        proxmox_service = ProxmoxService()
        
        result = proxmox_service.remove_server_disk(server_name, device)
        if result['success']:
            return jsonify(result)
        else:
            return jsonify({'error': result.get('message', '?�스???�거 ?�패')}), 500
            
    except Exception as e:
        logger.error(f"?�스???�거 ?�패: {str(e)}")
        return jsonify({'error': str(e)}), 500    

@bp.route('/api/roles/assign_bulk', methods=['POST'])
@permission_required('assign_roles')
def assign_role_bulk():
    """?�중 ?�버????�� ?�당"""
    try:
        logger.info(f"?�� ?�중 ?�버 ??�� ?�당 ?�청")
        
        data = request.get_json()
        server_names = data.get('server_names', [])
        role = data.get('role')
        
        logger.info(f"?�� ?�???�버?? {server_names}")
        logger.info(f"?�� ?�당????��: {role}")
        
        if not server_names:
            return jsonify({'error': '?�버 목록??지?�해???�니??'}), 400
        
        if not role or role == '':
            return jsonify({'error': '??��(role)??지?�해???�니??'}), 400
        
        # "none" 값을 ??�� ?�제�?처리
        if role == 'none':
            logger.info(f"?�� ??�� ?�제 ?�청?�로 변?? none ??None")
            role = None
        
        # AnsibleService�??�해 ??번에 ??�� ?�당 (?�적 ?�벤?�리 + --limit)
        ansible_service = AnsibleService()
        # DB?�서 ?�???�버 ?�보 ?�집 (IP ?�수)
        db_servers = Server.query.filter(Server.name.in_(server_names)).all()
        target_servers = []
        missing = []
        for s in db_servers:
            if s.ip_address:
                target_servers.append({'ip_address': s.ip_address})
            else:
                missing.append(s.name)
        
        # ??�� ?�제??경우 별도 처리 (Ansible ?�행 ?�이 DB�??�데?�트)
        if role is None:
            logger.info(f"?�� ??�� ?�제: DB?�서�???�� ?�거")
            updated_count = 0
            for server in db_servers:
                server.role = None
                updated_count += 1
            
        from app import db
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'{updated_count}�??�버?�서 ??��???�제?�었?�니??',
            'targets': [s.name for s in db_servers],
            'missing_ip': missing
        })
        
        if not target_servers:
            return jsonify({'error': '?�택???�버?�에 ?�효??IP가 ?�습?�다.'}), 400
        
        success, message = ansible_service.run_role_for_multiple_servers(target_servers, role)
        logger.info(f"?�� ?�괄 ??�� ?�행 결과: success={success}")

        # ?�행 결과 반영: DB ?�데?�트 �??�림 ?�성
        try:
            from app import db
            from app.models.notification import Notification

            if success:
                # DB????�� 반영
                updated = 0
                for s in db_servers:
                    # ?�?�에 ?�함???�버�?                    if s.ip_address and any(t['ip_address'] == s.ip_address for t in target_servers):
                        s.role = role
                        updated += 1
                        # ?�공 ?�림 ?�성
                        n = Notification.create_notification(
                            type='ansible_role',
                            title=f"?�버 {s.name} ??�� ?�당 ?�료",
                            message=f"??�� '{role}'???�공?�으�??�용?�었?�니??",
                            # Ansible stdout(?�공 로그)??details�??�??(길면 그�?�??�?? UI?�서 모달�??�시)
                            details=message,
                            severity='success'
                        )
                        logger.info(f"?�림 ?�성: id={n.id} ?�버={s.name}")
                db.session.commit()
                logger.info(f"?�괄 ??�� DB ?�데?�트 ?�료: {updated}�??�버")
            else:
                # ?�패 ?�림(?�약)
                for s in db_servers:
                    n = Notification.create_notification(
                        type='ansible_role',
                        title=f"?�버 {s.name} ??�� ?�당 ?�패",
                        message="Ansible ?�행 �??�류가 발생?�습?�다.",
                        details=message,
                        severity='error'
                    )
                    logger.info(f"?�림 ?�성: id={n.id} ?�버={s.name} (?�패)")
        except Exception as notify_err:
            logger.warning(f"?�괄 ??�� ?�림/DB 반영 �??�류: {notify_err}")

        return jsonify({
            'success': success,
            'message': message,
            'targets': [s['ip_address'] for s in target_servers],
            'missing_ip': missing
        })
        
    except Exception as e:
        logger.error(f"?�중 ?�버 ??�� ?�당 ?�패: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# ?�락??API ?�드?�인?�들 추�?

@bp.route('/api/server_status/<server_name>', methods=['GET'])
@login_required
def get_server_status(server_name):
    """?�버 ?�태 조회"""
    try:
        from app.services.proxmox_service import ProxmoxService
        proxmox_service = ProxmoxService()
        result = proxmox_service.get_server_status(server_name)
        
        if result['success']:
            return jsonify(result['data'])
        else:
            return jsonify({'error': result['message']}), 500
    except Exception as e:
        logger.error(f"?�버 ?�태 조회 ?�패: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/roles/available', methods=['GET'])
@login_required
def get_available_roles():
    """?�용 가?�한 ??�� 목록 조회"""
    try:
        roles = {
            'web': {'name': '?�서�?, 'description': '???�비???�공'},
            'was': {'name': 'WAS', 'description': '?�플리�??�션 ?�버'},
            'db': {'name': 'DB', 'description': '?�이?�베?�스 ?�버'},
            'java': {'name': 'JAVA', 'description': '?�바 ?�버'},
            'search': {'name': '검??, 'description': '검???�버'},
            'ftp': {'name': 'FTP', 'description': '?�일 ?�버'}
        }
        
        return jsonify({
            'success': True,
            'roles': roles
        })
        
    except Exception as e:
        logger.error(f"??�� 목록 조회 ?�패: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/roles/validate/<role_name>', methods=['GET'])
@login_required
def validate_role(role_name):
    """??�� ?�효??검??""
    try:
        valid_roles = ['web', 'was', 'db', 'java', 'search', 'ftp']
        
        if role_name in valid_roles:
            return jsonify({
                'success': True,
                'valid': True,
                'message': f'??�� "{role_name}"?� ?�효?�니??
            })
        else:
            return jsonify({
                'success': True,
                'valid': False,
                'message': f'??�� "{role_name}"?� ?�효?��? ?�습?�다'
            })
            
    except Exception as e:
        logger.error(f"??�� ?�효??검???�패: {str(e)}")
        return jsonify({'error': str(e)}), 500 

#@bp.route.*datastores', methods=['GET'])
@login_required
def get_datastores():
    """?�용 가?�한 datastore 목록 조회 (DB 캐싱)"""
    try:
        from app.models.datastore import Datastore
        
        # DB?�서 datastore 목록 조회
        db_datastores = Datastore.query.filter_by(enabled=True).all()
        
        # DB??datastore가 ?�으�?Proxmox?�서 가?��????�??        if not db_datastores:
            logger.info("?�� DB??datastore ?�보가 ?�음. Proxmox?�서 가?��????�??�?..")
            
            # Proxmox?�서 datastore 목록 가?�오�?            proxmox_service = ProxmoxService()
            proxmox_datastores = proxmox_service.get_datastores()
            
            # ?�경변?�에??기본 datastore ?�정 가?�오�?(초기 ?�정??
            def load_env_file():
                """?�로?�트 루트??.env ?�일??직접 ?�어???�셔?�리�?반환"""
                env_vars = {}
                try:
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
                        logger.info(f"?�� .env ?�일 로드 ?�공: {env_file}")
                    else:
                        logger.warning(f"?�️ .env ?�일??찾을 ???�습?�다: {env_file}")
                    
                    return env_vars
                except Exception as e:
                    logger.error(f"?�️ .env ?�일 ?�기 ?�패: {e}")
                    return {}
            
            env_vars = load_env_file()
            hdd_datastore = env_vars.get('PROXMOX_HDD_DATASTORE', 'local-lvm')
            ssd_datastore = env_vars.get('PROXMOX_SSD_DATASTORE', 'local')
            
            # Proxmox datastore�?DB???�??            for datastore in proxmox_datastores:
                db_datastore = Datastore(
                    id=datastore['id'],
                    name=datastore['id'],
                    type=datastore.get('type', 'unknown'),
                    size=datastore.get('size', 0),
                    used=datastore.get('used', 0),
                    available=datastore.get('available', 0),
                    content=datastore.get('content', ''),
                    enabled=datastore.get('enabled', True),
                    is_default_hdd=datastore['id'] == hdd_datastore,
                    is_default_ssd=datastore['id'] == ssd_datastore
                )
                db.session.add(db_datastore)
        
            db.session.commit()
            logger.info(f"?�� {len(proxmox_datastores)}�?datastore�?DB???�???�료")
        
        # ?�?�된 datastore ?�시 조회
        db_datastores = Datastore.query.filter_by(enabled=True).all()
        
        # DB?�서 기본 datastore ?�정 가?�오�?        def get_default_datastores():
            """DB?�서 기본 datastore ?�정??가?�옴"""
            try:
                # DB?�서 기본 HDD datastore 조회
                default_hdd = Datastore.query.filter_by(is_default_hdd=True, enabled=True).first()
                # DB?�서 기본 SSD datastore 조회
                default_ssd = Datastore.query.filter_by(is_default_ssd=True, enabled=True).first()
                
                hdd_datastore = default_hdd.id if default_hdd else 'local-lvm'
                ssd_datastore = default_ssd.id if default_ssd else 'local'
                
                logger.info(f"?�� DB?�서 기본 datastore ?�정: HDD={hdd_datastore}, SSD={ssd_datastore}")
                return hdd_datastore, ssd_datastore
            except Exception as e:
                logger.error(f"?�️ DB?�서 기본 datastore ?�정 조회 ?�패: {e}")
                # .env ?�일?�서 fallback
                return get_default_datastores_from_env()
        
        def get_default_datastores_from_env():
            """?�경변?�에??기본 datastore ?�정??가?�옴 (fallback)"""
            try:
                current_dir = os.path.dirname(os.path.abspath(__file__))
                project_root = os.path.dirname(os.path.dirname(current_dir))
                env_file = os.path.join(project_root, '.env')
                
                hdd_datastore = 'local-lvm'
                ssd_datastore = 'local'
                
                if os.path.exists(env_file):
                    with open(env_file, 'r', encoding='utf-8') as f:
                        for line in f:
                            line = line.strip()
                            if line and not line.startswith('#') and '=' in line:
                                key, value = line.split('=', 1)
                                if key.strip() == 'PROXMOX_HDD_DATASTORE':
                                    hdd_datastore = value.strip()
                                elif key.strip() == 'PROXMOX_SSD_DATASTORE':
                                    ssd_datastore = value.strip()
                
                logger.info(f"?�� .env?�서 기본 datastore ?�정: HDD={hdd_datastore}, SSD={ssd_datastore}")
                return hdd_datastore, ssd_datastore
            except Exception as e:
                logger.error(f"?�️ .env ?�일 ?�기 ?�패: {e}")
                return 'local-lvm', 'local'
        
        hdd_datastore, ssd_datastore = get_default_datastores()
        
        # DB datastore�??�맷??        formatted_datastores = []
        for datastore in db_datastores:
            formatted_datastores.append({
                'id': datastore.id,
                'name': datastore.name,
                'type': datastore.type,
                'size': datastore.size,
                'used': datastore.used,
                'available': datastore.available,
                'is_default_hdd': datastore.id == hdd_datastore,
                'is_default_ssd': datastore.id == ssd_datastore
            })
        
        return jsonify({
            'success': True,
            'datastores': formatted_datastores,
            'default_hdd': hdd_datastore,
            'default_ssd': ssd_datastore
        })
        
    except Exception as e:
        logger.error(f"Datastore 목록 조회 ?�패: {str(e)}")
        return jsonify({'error': str(e)}), 500

#@bp.route.*datastores/refresh', methods=['POST'])
@login_required
def refresh_datastores():
    """datastore ?�보 ?�로고침 (Proxmox?�서 ?�시 가?��???DB ?�데?�트)"""
    try:
        from app.models.datastore import Datastore
        
        # 기존 datastore ?�보 ??��
        Datastore.query.delete()
        db.session.commit()
        logger.info("?�� 기존 datastore ?�보 ??�� ?�료")
        
        # Proxmox?�서 datastore 목록 가?�오�?        proxmox_service = ProxmoxService()
        proxmox_datastores = proxmox_service.get_datastores()
        
        # ?�경변?�에??기본 datastore ?�정 가?�오�?        def load_env_file():
            """?�로?�트 루트??.env ?�일??직접 ?�어???�셔?�리�?반환"""
            env_vars = {}
            try:
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
                    logger.info(f"?�� .env ?�일 로드 ?�공: {env_file}")
                else:
                    logger.warning(f"?�️ .env ?�일??찾을 ???�습?�다: {env_file}")
                
                return env_vars
            except Exception as e:
                logger.error(f"?�️ .env ?�일 ?�기 ?�패: {e}")
                return {}
        
        env_vars = load_env_file()
        hdd_datastore = env_vars.get('PROXMOX_HDD_DATASTORE', 'local-lvm')
        ssd_datastore = env_vars.get('PROXMOX_SSD_DATASTORE', 'local')
        
        # Proxmox datastore�?DB???�??        for datastore in proxmox_datastores:
            db_datastore = Datastore(
                id=datastore['id'],
                name=datastore['id'],
                type=datastore.get('type', 'unknown'),
                size=datastore.get('size', 0),
                used=datastore.get('used', 0),
                available=datastore.get('available', 0),
                content=datastore.get('content', ''),
                enabled=datastore.get('enabled', True),
                is_default_hdd=datastore['id'] == hdd_datastore,
                is_default_ssd=datastore['id'] == ssd_datastore
            )
            db.session.add(db_datastore)
        
        db.session.commit()
        logger.info(f"?�� {len(proxmox_datastores)}�?datastore�?DB???�로 ?�???�료")
        
        return jsonify({
            'success': True,
            'message': f'{len(proxmox_datastores)}�?datastore ?�보�??�로고침?�습?�다.',
            'count': len(proxmox_datastores)
        })
        
    except Exception as e:
        logger.error(f"Datastore ?�로고침 ?�패: {str(e)}")
        return jsonify({'error': str(e)}), 500

#@bp.route.*datastores/default', methods=['POST'])
@login_required
def set_default_datastores():
    """기본 datastore ?�정 변�?""
    try:
        from app.models.datastore import Datastore
        
        data = request.get_json()
        hdd_datastore_id = data.get('hdd_datastore_id')
        ssd_datastore_id = data.get('ssd_datastore_id')
        
        if not hdd_datastore_id or not ssd_datastore_id:
            return jsonify({'error': 'HDD?� SSD datastore ID가 ?�요?�니??'}), 400
        
        # 기존 기본 ?�정 ?�제
        Datastore.query.filter_by(is_default_hdd=True).update({'is_default_hdd': False})
        Datastore.query.filter_by(is_default_ssd=True).update({'is_default_ssd': False})
        
        # ?�로??기본 ?�정
        hdd_datastore = Datastore.query.filter_by(id=hdd_datastore_id).first()
        ssd_datastore = Datastore.query.filter_by(id=ssd_datastore_id).first()
        
        if not hdd_datastore:
            return jsonify({'error': f'HDD datastore�?찾을 ???�습?�다: {hdd_datastore_id}'}), 404
        if not ssd_datastore:
            return jsonify({'error': f'SSD datastore�?찾을 ???�습?�다: {ssd_datastore_id}'}), 404
        
        hdd_datastore.is_default_hdd = True
        ssd_datastore.is_default_ssd = True
        
        db.session.commit()
        
        logger.info(f"?�� 기본 datastore ?�정 변�? HDD={hdd_datastore_id}, SSD={ssd_datastore_id}")
        
        return jsonify({
            'success': True, 
            'message': '기본 datastore ?�정??변경되?�습?�다.',
            'hdd_datastore': hdd_datastore_id,
            'ssd_datastore': ssd_datastore_id
        })
        
    except Exception as e:
        logger.error(f"기본 datastore ?�정 변�??�패: {str(e)}")
        return jsonify({'error': str(e)}), 500    
