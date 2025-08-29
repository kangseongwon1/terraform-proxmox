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
from datetime import datetime
from app.routes.auth import permission_required

bp = Blueprint('servers', __name__)


# 전역 작업 상태 dict
tasks = {}

def create_task(status, type, message):
    task_id = str(uuid.uuid4())
    tasks[task_id] = {
        'status': status, 
        'type': type, 
        'message': message,
        'created_at': time.time(),
        'timeout': 18000  # 5시간 타임아웃
    }
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

def check_task_timeout():
    """Task 타임아웃 체크"""
    current_time = time.time()
    for task_id, task_info in list(tasks.items()):
        if task_info['status'] == 'running':
            elapsed_time = current_time - task_info['created_at']
            if elapsed_time > task_info['timeout']:
                timeout_hours = task_info['timeout'] / 3600
                print(f"⏰ Task 타임아웃: {task_id} (경과시간: {elapsed_time:.1f}초, 설정된 타임아웃: {timeout_hours:.1f}시간)")
                update_task(task_id, 'failed', f'작업 타임아웃 ({timeout_hours:.1f}시간 초과)')

@bp.route('/api/tasks/status')
def get_task_status():
    task_id = request.args.get('task_id')
    print(f"🔍 Task 상태 조회: {task_id}")
    print(f"📋 현재 Tasks: {list(tasks.keys())}")
    
    # 타임아웃 체크
    check_task_timeout()
    
    if not task_id:
        return jsonify({'error': 'task_id가 필요합니다.'}), 400
    
    if task_id not in tasks:
        print(f"❌ Task를 찾을 수 없음 (404): {task_id}")
        # 404 에러 시 task를 자동으로 종료 상태로 변경
        tasks[task_id] = {
            'status': 'failed', 
            'type': 'unknown', 
            'message': 'Task를 찾을 수 없어 자동 종료됨',
            'created_at': time.time(),
            'timeout': 18000
        }
        print(f"🔧 Task 자동 종료 처리: {task_id}")
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
        print(f"💥 서버 목록 조회 실패: {str(e)}")
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
        print(f"💥 서버 디버깅 정보 조회 실패: {str(e)}")
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
        ip_address = data.get('ip_address',[])
        disks = data.get('disks', [])
        network_devices = data.get('network_devices', [])
        template_vm_id = data.get('template_vm_id', 8000)
        vm_username = data.get('vm_username', 'rocky')
        vm_password = data.get('vm_password', 'rocky123')
        
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
                    print(f"🔧 서버 생성 작업 시작: {server_name}")
                    
                    # Terraform 서비스 초기화
                    terraform_service = TerraformService()
                    
                    # OS 타입 동적 분류
                    os_type = classify_os_type(template_vm_id or 'rocky-9-template')
                    
                    # 기본 사용자명/비밀번호 설정 (사용자가 입력하지 않은 경우)
                    if not vm_username:
                        vm_username = get_default_username(os_type)
                    if not vm_password:
                        vm_password = get_default_password(os_type)
                    
                    # 서버 설정 생성
                    server_data = {
                        'name': server_name,
                        'cpu': cpu,
                        'memory': memory,
                        'role': role,
                        'ip_address': ip_address,
                        'os_type': os_type,  # 동적으로 분류된 OS 타입
                        'disks': disks,
                        'network_devices': network_devices,
                        'template_vm_id': template_vm_id,
                        'vm_username': vm_username,
                        'vm_password': vm_password
                    }
                    print(f"🔧 서버 설정 생성 시작: {json.dumps(server_data, indent=2)}")
                    
                    try:
                        config_success = terraform_service.create_server_config(server_data)
                        print(f"🔧 서버 설정 생성 결과: {config_success}")
                        
                        if not config_success:
                            error_msg = '서버 설정 생성 실패'
                            print(f"❌ {error_msg}")
                            update_task(task_id, 'failed', error_msg)
                            return
                    except Exception as config_error:
                        error_msg = f'서버 설정 생성 중 예외 발생: {str(config_error)}'
                        print(f"❌ {error_msg}")
                        import traceback
                        traceback.print_exc()
                        update_task(task_id, 'failed', error_msg)
                        return
                    
                    # 인프라 배포
                    print(f"🔧 인프라 배포 시작: {server_name}")
                    try:
                        deploy_success, deploy_message = terraform_service.deploy_infrastructure()
                        print(f"🔧 인프라 배포 결과: success={deploy_success}, message={deploy_message}")
                        
                        if not deploy_success:
                            print(f"❌ 인프라 배포 실패: {deploy_message}")
                            update_task(task_id, 'failed', f'인프라 배포 실패: {deploy_message}')
                            return
                    except Exception as deploy_error:
                        error_msg = f"인프라 배포 중 예외 발생: {str(deploy_error)}"
                        print(f"❌ {error_msg}")
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
                    
                    # DB에 서버 정보 저장
                    new_server = Server(
                        name=server_name,
                        ip_address=ip_address,  # IP 주소 추가
                        role=role,  # 역할 정보 추가
                        status='stopped',  # 초기 상태는 중지됨
                        cpu=cpu,
                        memory=memory,
                        os_type=os_type  # OS 타입 추가
                    )
                    db.session.add(new_server)
                    db.session.commit()
                    
                    # Ansible을 통한 역할별 소프트웨어 설치
                    if role and role != 'none':
                        print(f"🔧 Ansible 역할 할당 시작: {server_name} - {role}")
                        try:
                            ansible_service = AnsibleService()
                            ansible_success, ansible_message = ansible_service.assign_role_to_server(server_name, role)
                            
                            if ansible_success:
                                print(f"✅ Ansible 역할 할당 성공: {server_name} - {role}")
                                update_task(task_id, 'completed', f'서버 {server_name} 생성 및 {role} 역할 할당 완료')
                            else:
                                print(f"⚠️ Ansible 역할 할당 실패: {server_name} - {role}, 메시지: {ansible_message}")
                                update_task(task_id, 'completed', f'서버 {server_name} 생성 완료 (Ansible 실패: {ansible_message})')
                        except Exception as ansible_error:
                            print(f"⚠️ Ansible 실행 중 오류: {str(ansible_error)}")
                            update_task(task_id, 'completed', f'서버 {server_name} 생성 완료 (Ansible 오류: {str(ansible_error)})')
                    else:
                        update_task(task_id, 'completed', f'서버 {server_name} 생성 완료')
                    
                    print(f"✅ 서버 생성 완료: {server_name}")
                    
            except Exception as e:
                print(f"💥 서버 생성 작업 실패: {str(e)}")
                update_task(task_id, 'failed', f'서버 생성 중 오류: {str(e)}')
                
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
                    print(f"💥 정리 작업 실패: {str(cleanup_error)}")
        
        # 백그라운드에서 서버 생성 작업 실행
        thread = threading.Thread(target=create_server_task)
        thread.start()
        
        return jsonify({
            'success': True,
            'task_id': task_id,
            'message': f'서버 {server_name} 생성이 시작되었습니다.'
        })
        
    except Exception as e:
        print(f"💥 서버 생성 실패: {str(e)}")
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
                    print(f"🔧 다중 서버 생성 작업 시작: {len(servers_data)}개 서버")
                    
                    # Terraform 서비스 초기화
                    terraform_service = TerraformService()
                    
                    # 기존 tfvars 로드
                    try:
                        tfvars = terraform_service.load_tfvars()
                        print(f"🔧 기존 tfvars 로드 완료: {len(tfvars.get('servers', {}))}개 서버")
                    except Exception as e:
                        print(f"❌ 기존 tfvars 로드 실패: {e}")
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
                            'role': server_data.get('role', ''),
                            'cpu': server_data.get('cpu', 2),
                            'memory': server_data.get('memory', 2048),
                            'disks': server_data.get('disks', []),
                            'network_devices': server_data.get('network_devices', []),
                            'template_vm_id': server_data.get('template_vm_id', 8000),
                            'vm_username': server_data.get('vm_username', tfvars.get('vm_username', 'rocky')),
                            'vm_password': server_data.get('vm_password', tfvars.get('vm_password', 'rocky123'))
                        }
                        
                        # 디스크 설정에 기본값 추가
                        for disk in server_config['disks']:
                            if 'disk_type' not in disk:
                                disk['disk_type'] = 'hdd'
                            if 'file_format' not in disk:
                                disk['file_format'] = 'auto'
                        
                        tfvars['servers'][server_name] = server_config
                        print(f"🔧 서버 설정 추가: {server_name}")
                    
                    # tfvars 파일 저장
                    try:
                        save_success = terraform_service.save_tfvars(tfvars)
                        if not save_success:
                            error_msg = 'tfvars 파일 저장 실패'
                            print(f"❌ {error_msg}")
                            update_task(task_id, 'failed', error_msg)
                            return
                        print(f"✅ tfvars 파일 저장 완료: {len(tfvars['servers'])}개 서버")
                    except Exception as save_error:
                        error_msg = f'tfvars 파일 저장 중 예외 발생: {str(save_error)}'
                        print(f"❌ {error_msg}")
                        import traceback
                        traceback.print_exc()
                        update_task(task_id, 'failed', error_msg)
                        return
                    
                    # 새로 생성될 서버들에 대한 targeted apply 실행
                    print(f"🔧 Targeted Terraform apply 시작: {len(servers_data)}개 서버")
                    try:
                        # 새로 생성될 서버들만 대상으로 targeted apply 실행
                        new_server_targets = []
                        for server_data in servers_data:
                            server_name = server_data.get('name')
                            if server_name:
                                # Terraform 모듈 리소스 타겟 형식: module.server["서버이름"]
                                target = f'module.server["{server_name}"]'
                                new_server_targets.append(target)
                        
                        print(f"🔧 Targeted apply 대상: {new_server_targets}")
                        apply_success, apply_message = terraform_service.apply(targets=new_server_targets)
                        print(f"🔧 Terraform apply 결과: success={apply_success}, message_length={len(apply_message) if apply_message else 0}")
                        
                        if not apply_success:
                            print(f"❌ Terraform apply 실패: {apply_message}")
                            update_task(task_id, 'failed', f'Terraform apply 실패: {apply_message}')
                            return
                    except Exception as apply_error:
                        error_msg = f"Terraform apply 중 예외 발생: {str(apply_error)}"
                        print(f"❌ {error_msg}")
                        import traceback
                        traceback.print_exc()
                        update_task(task_id, 'failed', error_msg)
                        return
                    
                    # Proxmox에서 실제 VM 생성 확인
                    proxmox_service = ProxmoxService()
                    created_servers = []
                    failed_servers = []
                    
                    for server_data in servers_data:
                        server_name = server_data.get('name')
                        if not server_name:
                            continue
                        
                        vm_exists = proxmox_service.check_vm_exists(server_name)
                        if vm_exists:
                            created_servers.append(server_name)
                            
                            # DB에 서버 정보 저장
                            new_server = Server(
                                name=server_name,
                                cpu=server_data.get('cpu', 2),
                                memory=server_data.get('memory', 2048),
                                role=server_data.get('role', ''),
                                status='running',
                                created_at=datetime.utcnow()
                            )
                            
                            try:
                                db.session.add(new_server)
                                db.session.commit()
                                print(f"✅ 서버 DB 저장 완료: {server_name}")
                            except Exception as db_error:
                                print(f"⚠️ 서버 DB 저장 실패: {server_name} - {db_error}")
                                db.session.rollback()
                        else:
                            failed_servers.append(server_name)
                            print(f"❌ VM 생성 확인 실패: {server_name}")
                    
                    # 결과 메시지 생성
                    if created_servers and not failed_servers:
                        success_msg = f'모든 서버 생성 완료: {", ".join(created_servers)}'
                        update_task(task_id, 'completed', success_msg)
                        print(f"✅ {success_msg}")
                    elif created_servers and failed_servers:
                        partial_msg = f'일부 서버 생성 완료. 성공: {", ".join(created_servers)}, 실패: {", ".join(failed_servers)}'
                        update_task(task_id, 'completed', partial_msg)
                        print(f"⚠️ {partial_msg}")
                    else:
                        error_msg = f'모든 서버 생성 실패: {", ".join(failed_servers)}'
                        update_task(task_id, 'failed', error_msg)
                        print(f"❌ {error_msg}")
                    
            except Exception as e:
                error_msg = f'다중 서버 생성 작업 중 예외 발생: {str(e)}'
                print(f"❌ {error_msg}")
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
        print(f"💥 다중 서버 생성 API 오류: {str(e)}")
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
        
        print(f"🔧 대량 서버 작업: {action} - {len(server_names)}개 서버")
        
        # Task 생성
        task_id = create_task('running', 'bulk_server_action', f'{len(server_names)}개 서버 {action} 작업 중...')
        
        def bulk_action_task():
            try:
                from app import create_app
                app = create_app()
                with app.app_context():
                    print(f"🔧 대량 서버 작업 시작: {action} - {server_names}")
                    
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
                        print(f"✅ {success_msg}")
                    elif success_servers and failed_servers:
                        partial_msg = f'일부 서버 {action_name} 완료. 성공: {", ".join(success_servers)}, 실패: {len(failed_servers)}개'
                        update_task(task_id, 'completed', partial_msg)
                        print(f"⚠️ {partial_msg}")
                        print(f"⚠️ 실패 상세: {failed_servers}")
                    else:
                        error_msg = f'모든 서버 {action_name} 실패: {len(failed_servers)}개'
                        update_task(task_id, 'failed', error_msg)
                        print(f"❌ {error_msg}")
                        print(f"❌ 실패 상세: {failed_servers}")
                        
            except Exception as e:
                error_msg = f'대량 서버 작업 중 예외 발생: {str(e)}'
                print(f"❌ {error_msg}")
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
        print(f"💥 대량 서버 작업 API 오류: {str(e)}")
        return jsonify({'error': str(e)}), 500

def process_bulk_delete_terraform(server_names):
    """Terraform 기반 대량 서버 삭제"""
    success_servers = []
    failed_servers = []
    
    try:
        print(f"🗑️ Terraform 기반 대량 삭제 시작: {server_names}")
        
        # 1. 서버 존재 확인 및 유효성 검사
        valid_servers = []
        for server_name in server_names:
            server = Server.query.filter_by(name=server_name).first()
            if not server:
                failed_servers.append(f"{server_name}: 서버를 찾을 수 없음")
                continue
            valid_servers.append(server_name)
        
        if not valid_servers:
            print("❌ 유효한 서버가 없습니다.")
            return success_servers, failed_servers
        
        # 2. Terraform 설정에서 삭제할 서버들 제거
        terraform_service = TerraformService()
        tfvars = terraform_service.load_tfvars()
        
        deleted_from_tfvars = []
        for server_name in valid_servers:
            if 'servers' in tfvars and server_name in tfvars['servers']:
                del tfvars['servers'][server_name]
                deleted_from_tfvars.append(server_name)
                print(f"🗑️ tfvars.json에서 {server_name} 제거")
        
        if not deleted_from_tfvars:
            print("❌ tfvars.json에서 삭제할 서버를 찾을 수 없습니다.")
            for server_name in valid_servers:
                failed_servers.append(f"{server_name}: tfvars.json에서 찾을 수 없음")
            return success_servers, failed_servers
        
        # 3. tfvars.json 저장
        terraform_service.save_tfvars(tfvars)
        print(f"💾 tfvars.json 업데이트 완료: {len(deleted_from_tfvars)}개 서버 제거")
        
        # 4. Terraform destroy with targeted resources
        destroy_targets = []
        for server_name in deleted_from_tfvars:
            target = f'module.server["{server_name}"]'
            destroy_targets.append(target)
        
        print(f"🔥 Terraform destroy 실행 - 대상: {destroy_targets}")
        destroy_success, destroy_message = terraform_service.destroy_targets(destroy_targets)
        
        if destroy_success:
            print(f"✅ Terraform destroy 성공: {deleted_from_tfvars}")
            
            # 5. DB에서 서버 제거
            for server_name in deleted_from_tfvars:
                server = Server.query.filter_by(name=server_name).first()
                if server:
                    db.session.delete(server)
                    print(f"🗑️ DB에서 {server_name} 제거")
            
            db.session.commit()
            success_servers.extend(deleted_from_tfvars)
            
        else:
            print(f"❌ Terraform destroy 실패: {destroy_message}")
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
            print("🔄 tfvars.json 복원 완료")
        
    except Exception as e:
        error_msg = f"대량 삭제 중 예외 발생: {str(e)}"
        print(f"❌ {error_msg}")
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
                print(f"🔧 서버 작업 처리: {server_name} - {action}")
                
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
                    print(f"✅ {server_name} {action} 성공")
                else:
                    error_msg = result.get('message', '알 수 없는 오류')
                    failed_servers.append(f"{server_name}: {error_msg}")
                    print(f"❌ {server_name} {action} 실패: {error_msg}")
                    
            except Exception as server_error:
                error_msg = f"{server_name}: {str(server_error)}"
                failed_servers.append(error_msg)
                print(f"❌ {server_name} 처리 중 오류: {server_error}")
    
    except Exception as e:
        error_msg = f"대량 Proxmox 작업 중 예외 발생: {str(e)}"
        print(f"❌ {error_msg}")
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
        print(f"💥 서버 시작 실패: {str(e)}")
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
        print(f"💥 서버 중지 실패: {str(e)}")
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
        print(f"💥 서버 재부팅 실패: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/servers/<server_name>/delete', methods=['POST'])
@permission_required('delete_server')
def delete_server(server_name):
    """서버 삭제"""
    try:
        server = Server.query.filter_by(name=server_name).first()
        if not server:
            return jsonify({'error': '서버를 찾을 수 없습니다.'}), 404
        
        # Task 생성
        task_id = create_task('running', 'delete_server', f'서버 {server_name} 삭제 중...')
        
        def delete_server_task():
            try:
                from app import create_app
                app = create_app()
                with app.app_context():
                    print(f"🔧 개별 서버 삭제 작업 시작: {server_name}")
                    
                    # 새로운 Terraform 기반 삭제 방식 사용
                    success_servers, failed_servers = process_bulk_delete_terraform([server_name])
                    
                    if success_servers and server_name in success_servers:
                        update_task(task_id, 'completed', f'서버 {server_name} 삭제 완료')
                        print(f"✅ 서버 삭제 완료: {server_name}")
                    else:
                        # 실패 원인 메시지 추출
                        failure_reason = "알 수 없는 오류"
                        for failed in failed_servers:
                            if server_name in failed:
                                failure_reason = failed.split(": ", 1)[1] if ": " in failed else failed
                                break
                        
                        update_task(task_id, 'failed', f'서버 삭제 실패: {failure_reason}')
                        print(f"💥 서버 삭제 실패: {failure_reason}")
                        
            except Exception as e:
                print(f"💥 서버 삭제 작업 실패: {str(e)}")
                update_task(task_id, 'failed', f'서버 삭제 중 오류: {str(e)}')
        
        # 백그라운드에서 서버 삭제 작업 실행
        thread = threading.Thread(target=delete_server_task)
        thread.start()
        
        return jsonify({
            'success': True,
            'task_id': task_id,
            'message': f'서버 {server_name} 삭제가 시작되었습니다.'
        })
        
    except Exception as e:
        print(f"💥 서버 삭제 실패: {str(e)}")
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
        print(f"💥 서버 상태 조회 실패: {str(e)}")
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
        print(f"💥 스토리지 정보 조회 실패: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/sync_servers', methods=['POST'])
@login_required
def sync_servers():
    """기존 서버를 DB에 동기화"""
    try:
        print("🔧 서버 동기화 시작")
        from app.services.proxmox_service import ProxmoxService
        proxmox_service = ProxmoxService()
        
        # Proxmox에서 서버 목록 가져오기
        vm_list = proxmox_service.get_vm_list()
        print(f"🔧 Proxmox에서 가져온 서버: {[vm['name'] for vm in vm_list]}")
        
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
                print(f"✅ 서버 동기화: {vm['name']}")
            else:
                # 기존 서버 정보 업데이트
                existing_server.vmid = vm['vmid']
                existing_server.status = vm['status']
                existing_server.ip_address = vm.get('ip_addresses', [None])[0] if vm.get('ip_addresses') else None
                print(f"🔄 서버 정보 업데이트: {vm['name']}")
        
        db.session.commit()
        print(f"✅ 서버 동기화 완료: {synced_count}개 서버 추가됨")
        
        return jsonify({
            'success': True, 
            'message': f'{synced_count}개 서버가 DB에 동기화되었습니다.'
        })
        
    except Exception as e:
        print(f"💥 서버 동기화 실패: {str(e)}")
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
                    print(f"🔧 서버 생성 작업 시작: {server_name}")
                    
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
                    
                    # DB에 서버 정보 저장
                    new_server = Server(
                        name=server_name,
                        ip_address=ip_address,  # IP 주소 추가
                        role=role,  # 역할 정보 추가
                        status='stopped',  # 초기 상태는 중지됨
                        cpu=cpu,
                        memory=memory,
                        os_type=os_type  # OS 타입 추가
                    )
                    db.session.add(new_server)
                    db.session.commit()
                    
                    # Ansible을 통한 역할별 소프트웨어 설치
                    if role and role != 'none':
                        print(f"🔧 Ansible 역할 할당 시작: {server_name} - {role}")
                        try:
                            ansible_service = AnsibleService()
                            ansible_success, ansible_message = ansible_service.assign_role_to_server(server_name, role)
                            
                            if ansible_success:
                                print(f"✅ Ansible 역할 할당 성공: {server_name} - {role}")
                            else:
                                print(f"⚠️ Ansible 역할 할당 실패: {server_name} - {role}, 메시지: {ansible_message}")
                        except Exception as ansible_error:
                            print(f"⚠️ Ansible 실행 중 오류: {str(ansible_error)}")
                    
                    update_task(task_id, 'completed', f'서버 {server_name} 생성 완료')
                    print(f"✅ 서버 생성 완료: {server_name}")
                    
            except Exception as e:
                print(f"💥 서버 생성 작업 실패: {str(e)}")
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
        print(f"🔧 역할 할당 요청: {server_name}")
        
        data = request.get_json()
        role = data.get('role')
        print(f"🔧 할당할 역할: {role}")
        
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
        print(f"💥 역할 할당 실패: {str(e)}")
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
        print(f"💥 역할 제거 실패: {str(e)}")
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
        print(f"💥 서버 설정 조회 실패: {str(e)}")
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
        print(f"💥 서버 설정 업데이트 실패: {str(e)}")
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
        print(f"💥 서버 로그 조회 실패: {str(e)}")
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
        print(f"💥 디스크 추가 실패: {str(e)}")
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
        print(f"💥 디스크 제거 실패: {str(e)}")
        return jsonify({'error': str(e)}), 500    

@bp.route('/api/roles/assign_bulk', methods=['POST'])
@permission_required('assign_roles')
def assign_role_bulk():
    """다중 서버에 역할 할당"""
    try:
        print(f"🔧 다중 서버 역할 할당 요청")
        
        data = request.get_json()
        server_names = data.get('server_names', [])
        role = data.get('role')
        
        print(f"🔧 대상 서버들: {server_names}")
        print(f"🔧 할당할 역할: {role}")
        
        if not server_names:
            return jsonify({'error': '서버 목록을 지정해야 합니다.'}), 400
        
        if not role:
            return jsonify({'error': '역할(role)을 지정해야 합니다.'}), 400
        
        # AnsibleService를 통해 각 서버에 역할 할당
        ansible_service = AnsibleService()
        results = []
        
        for server_name in server_names:
            try:
                success, message = ansible_service.assign_role_to_server(server_name, role)
                results.append({
                    'server_name': server_name,
                    'success': success,
                    'message': message
                })
                print(f"🔧 {server_name}: {'성공' if success else '실패'} - {message}")
            except Exception as e:
                results.append({
                    'server_name': server_name,
                    'success': False,
                    'message': str(e)
                })
                print(f"❌ {server_name}: 오류 - {e}")
        
        # 결과 요약
        success_count = sum(1 for r in results if r['success'])
        total_count = len(results)
        
        return jsonify({
            'success': True,
            'message': f'{success_count}/{total_count}개 서버에 역할 할당 완료',
            'results': results,
            'summary': {
                'total': total_count,
                'success': success_count,
                'failed': total_count - success_count
            }
        })
        
    except Exception as e:
        print(f"💥 다중 서버 역할 할당 실패: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500 