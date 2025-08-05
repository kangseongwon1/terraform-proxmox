"""
서버 관리 관련 라우트
"""
from flask import Blueprint, request, jsonify, render_template, current_app
from flask_login import login_required, current_user
from functools import wraps
from app.models import Server, User, UserPermission
from app.services import ProxmoxService, TerraformService, AnsibleService, NotificationService
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
        'timeout': 60  # 60초 타임아웃
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
                print(f"⏰ Task 타임아웃: {task_id} (경과시간: {elapsed_time:.1f}초)")
                update_task(task_id, 'failed', f'작업 타임아웃 (60초 초과)')

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
            'timeout': 60
        }
        print(f"🔧 Task 자동 종료 처리: {task_id}")
        return jsonify(tasks[task_id])
    
    return jsonify(tasks[task_id])

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
        cpu_cores = data.get('cpu_cores', 2)
        memory_gb = data.get('memory_gb', 4)
        
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
                    
                    # 서버 설정 생성
                    server_data = {
                        'name': server_name,
                        'cpu_cores': cpu_cores,
                        'memory_gb': memory_gb
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
                        cpu_cores=cpu_cores,
                        memory_gb=memory_gb,
                        status='stopped'  # 초기 상태는 중지됨
                    )
                    db.session.add(new_server)
                    db.session.commit()
                    
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
                    print(f"🔧 서버 삭제 작업 시작: {server_name}")
                    
                    # 1. 서버 중지
                    from app.services.proxmox_service import ProxmoxService
                    proxmox_service = ProxmoxService()
                    proxmox_service.stop_server(server_name)
                    
                    # 2. 10초 대기
                    time.sleep(10)
                    
                    # 3. Terraform으로 삭제
                    terraform_service = TerraformService()
                    success, message = terraform_service.delete_server(server_name)
                    
                    if success:
                        # 4. DB에서 서버 삭제
                        server_to_delete = Server.query.filter_by(name=server_name).first()
                        if server_to_delete:
                            db.session.delete(server_to_delete)
                            db.session.commit()
                        
                        update_task(task_id, 'completed', f'서버 {server_name} 삭제 완료')
                        print(f"✅ 서버 삭제 완료: {server_name}")
                    else:
                        update_task(task_id, 'failed', f'서버 삭제 실패: {message}')
                        print(f"💥 서버 삭제 실패: {message}")
                        
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
        cpu_cores = data.get('cpu_cores', 2)
        memory_gb = data.get('memory_gb', 4)
        
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
                        'cpu_cores': cpu_cores,
                        'memory_gb': memory_gb
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
                        cpu_cores=cpu_cores,
                        memory_gb=memory_gb,
                        status='stopped'  # 초기 상태는 중지됨
                    )
                    db.session.add(new_server)
                    db.session.commit()
                    
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


@bp.route('/api/assign_role/<server_name>', methods=['POST'])
@permission_required('assign_roles')
def assign_role(server_name):
    """서버에 역할 할당"""
    try:
        print(f"🔧 역할 할당 요청: {server_name}")
        print(f"🔧 Content-Type: {request.content_type}")
        print(f"🔧 요청 헤더: {dict(request.headers)}")
        
        # 데이터베이스 세션 상태 확인
        from app import db
        print(f"🔧 DB 세션 상태: {db.session.is_active}")
        print(f"🔧 DB 세션 ID: {id(db.session)}")
        
        data = request.get_json()
        print(f"🔧 요청 데이터: {data}")
        
        role = data.get('role')
        print(f"🔧 할당할 역할: {role}")
        
        # 모든 서버 목록 확인
        all_servers = Server.query.all()
        print(f"🔧 DB에 있는 모든 서버: {[s.name for s in all_servers]}")
        
        # 직접 쿼리로 확인
        result = db.session.execute(db.text("SELECT name FROM servers WHERE name = :name"), {"name": server_name})
        db_servers = result.fetchall()
        print(f"🔧 직접 SQL 쿼리 결과: {db_servers}")
        
        server = Server.query.filter_by(name=server_name).first()
        print(f"🔧 ORM 쿼리 결과: {server}")
        
        if not server:
            print(f"❌ 서버를 찾을 수 없음: {server_name}")
            return jsonify({'error': '서버를 찾을 수 없습니다.'}), 404
        
        print(f"🔧 서버 정보: {server.name} - 현재 역할: {server.role}")
        print(f"🔧 서버 ID: {server.id}")
        
        server.role = role
        db.session.commit()
        
        print(f"✅ 역할 할당 완료: {server_name} - {role}")
        return jsonify({'success': True, 'message': f'서버 {server_name}에 역할 {role}이 할당되었습니다.'})
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