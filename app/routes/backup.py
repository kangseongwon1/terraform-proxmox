"""
백업 관리 관련 라우트
"""
from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required
from functools import wraps
import threading
import time
import uuid
from datetime import datetime
from app.routes.auth import permission_required

bp = Blueprint('backup', __name__)

# 백업 상태 관리 시스템 (간소화)
backup_status = {}  # 백업 중인 서버들의 상태 추적

def start_backup_monitoring(server_name, backup_config):
    """백업 모니터링 시작"""
    backup_id = str(uuid.uuid4())
    backup_status[server_name] = {
        'backup_id': backup_id,
        'status': 'running',
        'started_at': time.time(),
        'config': backup_config,
        'message': f'서버 {server_name} 백업이 진행 중입니다.',
        'last_check': time.time()
    }
    print(f"🔧 백업 모니터링 시작: {server_name} (ID: {backup_id})")
    print(f"🔧 backup_status에 추가됨: {backup_status}")
    return backup_id

def update_backup_status(server_name, status, message=None):
    """백업 상태 업데이트"""
    print(f"🔧 백업 상태 업데이트 시도: {server_name} - {status} - {message}")
    print(f"🔧 현재 backup_status: {backup_status}")
    
    if server_name in backup_status:
        backup_status[server_name]['status'] = status
        if message:
            backup_status[server_name]['message'] = message
        backup_status[server_name]['last_update'] = time.time()
        print(f"✅ 백업 상태 업데이트 성공: {server_name} - {status} - {message}")
        print(f"✅ 업데이트 후 backup_status: {backup_status}")
    else:
        print(f"❌ 백업 상태를 찾을 수 없음: {server_name}")
        print(f"❌ 현재 backup_status 키들: {list(backup_status.keys())}")

def is_server_backing_up(server_name):
    """서버가 백업 중인지 확인"""
    return server_name in backup_status and backup_status[server_name]['status'] == 'running'

def get_backup_status(server_name):
    """서버의 백업 상태 조회"""
    return backup_status.get(server_name, None)

def start_file_monitoring(server_name):
    """파일 기반 백업 완료 감지 시작"""
    def monitor_backup_files():
        from app.main import app
        with app.app_context():
            try:
                from app.services.proxmox_service import ProxmoxService
                proxmox_service = ProxmoxService()
                
                start_time = backup_status[server_name]['started_at']
                print(f"🔍 백업 파일 감지 시작: {server_name} (시작: {datetime.fromtimestamp(start_time).strftime('%H:%M:%S')})")
                print(f"🔍 현재 시간: {datetime.now().strftime('%H:%M:%S')}")
                print(f"🔍 백업 시작 시간: {start_time}")
                
                check_count = 0
                
                # 30초마다 파일 체크
                while is_server_backing_up(server_name):
                    check_count += 1
                    current_time = time.time()
                    elapsed_time = current_time - start_time
                    
                    print(f"🔍 파일 감지 체크 #{check_count}: {server_name} (경과: {elapsed_time:.1f}초)")
                    
                    try:
                        # 백업 타임아웃 체크 (30분)
                        if elapsed_time > 1800:  # 30분
                            print(f"⏰ 백업 타임아웃: {server_name} (30분 초과)")
                            update_backup_status(server_name, 'failed', f'서버 {server_name} 백업이 타임아웃되었습니다. (30분 초과)')
                            break
                        
                        # 백업 파일 목록 확인
                        print(f"🔍 백업 파일 목록 조회 시작: {server_name}")
                        backup_files = proxmox_service.get_server_backups(server_name)
                        print(f"🔍 백업 파일 목록 응답: {backup_files}")
                        
                        if backup_files.get('success') and backup_files.get('data'):
                            backup_data = backup_files['data']
                            all_backups = backup_data.get('backups', [])
                            print(f"🔍 전체 백업 파일 수: {len(all_backups)}")
                            
                            # 백업 시작 시간 이후의 백업 파일들 찾기
                            recent_backups = [
                                b for b in all_backups 
                                if b.get('ctime', 0) > start_time
                            ]
                            
                            print(f"🔍 백업 시작 후 생성된 파일 수: {len(recent_backups)}")
                            
                            if recent_backups:
                                # 최근 백업 파일의 정보 확인
                                latest_backup = max(recent_backups, key=lambda x: x.get('ctime', 0))
                                backup_age = current_time - latest_backup.get('ctime', 0)
                                
                                print(f"📁 백업 파일 발견: {latest_backup.get('name', 'unknown')}")
                                print(f"📁 백업 파일 정보: {latest_backup}")
                                print(f"📁 백업 파일 나이: {backup_age:.1f}초")
                                print(f"📁 백업 파일 크기: {latest_backup.get('size_gb', 0)}GB")
                                
                                # 백업 파일이 최근에 생성되었고 (5분 이내), 파일 크기가 0이 아니면 완료로 간주
                                if backup_age < 300 and latest_backup.get('size_gb', 0) > 0:
                                    print(f"✅ 백업 완료 조건 충족: {server_name}")
                                    update_backup_status(server_name, 'completed', f'서버 {server_name} 백업이 완료되었습니다.')
                                    print(f"✅ 백업 완료 감지: {server_name} (파일: {latest_backup.get('name', 'unknown')})")
                                    
                                    # 완료 후 5분 후 상태 정리
                                    def cleanup_backup_status():
                                        time.sleep(300)  # 5분 후 정리
                                        if server_name in backup_status and backup_status[server_name]['status'] == 'completed':
                                            del backup_status[server_name]
                                            print(f"🧹 완료된 백업 상태 정리: {server_name}")
                                    cleanup_thread = threading.Thread(target=cleanup_backup_status)
                                    cleanup_thread.daemon = True
                                    cleanup_thread.start()
                                    break
                                else:
                                    print(f"⏳ 백업 파일 발견했지만 완료 조건 불충족: {server_name}")
                                    print(f"⏳ 나이 조건: {backup_age:.1f}초 < 300초 = {backup_age < 300}")
                                    print(f"⏳ 크기 조건: {latest_backup.get('size_gb', 0)}GB > 0 = {latest_backup.get('size_gb', 0) > 0}")
                            else:
                                print(f"⏳ 백업 시작 후 생성된 백업 파일 없음: {server_name}")
                                print(f"⏳ 전체 백업 파일들: {[b.get('name', 'unknown') for b in all_backups]}")
                        else:
                            print(f"⚠️ 백업 파일 목록 조회 실패: {server_name}")
                            print(f"⚠️ 응답: {backup_files}")
                            
                    except Exception as e:
                        print(f"⚠️ 백업 파일 확인 중 오류: {str(e)}")
                        import traceback
                        print(f"⚠️ 오류 상세: {traceback.format_exc()}")
                    
                    print(f"⏳ 30초 대기 시작: {server_name}")
                    time.sleep(30)
                    print(f"⏳ 30초 대기 완료: {server_name}")
                    
            except Exception as e:
                print(f"💥 백업 파일 감지 실패: {str(e)}")
                import traceback
                print(f"💥 오류 상세: {traceback.format_exc()}")
                update_backup_status(server_name, 'failed', f'백업 파일 감지 중 오류 발생: {str(e)}')
    
    print(f"🔧 파일 감지 스레드 시작: {server_name}")
    # 백그라운드 스레드로 파일 감지 시작
    monitor_thread = threading.Thread(target=monitor_backup_files)
    monitor_thread.daemon = True
    monitor_thread.start()
    print(f"🔧 파일 감지 스레드 시작 완료: {server_name}")



# 개별 서버 백업 관련 API 엔드포인트
@bp.route('/api/server/backup/<server_name>', methods=['POST'])
@permission_required('backup_management')
def create_server_backup(server_name):
    """개별 서버 백업 생성"""
    try:
        data = request.get_json()
        
        # 이미 백업 중인지 확인
        if is_server_backing_up(server_name):
            return jsonify({
                'error': f'서버 {server_name}은(는) 이미 백업 중입니다.'
            }), 400
        
        # 백업 모니터링 시작
        backup_id = start_backup_monitoring(server_name, data)
        
        # 백그라운드에서 백업 작업 실행
        def run_backup_task():
            from app.main import app
            with app.app_context():
                try:
                    from app.services.proxmox_service import ProxmoxService
                    proxmox_service = ProxmoxService()
                    
                    print(f"🚀 백업 작업 시작: {server_name}")
                    print(f"🚀 백업 설정: {data}")
                    
                    result = proxmox_service.create_server_backup(server_name, data)
                    print(f"🚀 Proxmox 백업 API 응답: {result}")
                    
                    if result['success']:
                        print(f"✅ 백업 작업 요청 성공: {server_name}")
                        print(f"✅ 파일 감지 시작 호출: {server_name}")
                        # 백업 작업이 성공적으로 시작됨 - 파일 감지 시작
                        start_file_monitoring(server_name)
                        print(f"✅ 파일 감지 시작 완료: {server_name}")
                    else:
                        print(f"❌ 백업 작업 요청 실패: {server_name} - {result.get('message', '알 수 없는 오류')}")
                        update_backup_status(server_name, 'failed', f'백업 생성 실패: {result.get("message", "알 수 없는 오류")}')
                        
                except Exception as e:
                    print(f"💥 백업 작업 실패: {str(e)}")
                    import traceback
                    print(f"💥 오류 상세: {traceback.format_exc()}")
                    update_backup_status(server_name, 'failed', f'백업 작업 중 오류 발생: {str(e)}')
        
        # 백그라운드 스레드로 백업 작업 실행
        backup_thread = threading.Thread(target=run_backup_task)
        backup_thread.daemon = True
        backup_thread.start()
        
        response_data = {
            'success': True,
            'message': f'서버 {server_name} 백업이 시작되었습니다.',
            'backup_id': backup_id,
            'data': {
                'backup_id': backup_id,
                'server_name': server_name,
                'status': 'running'
            }
        }
        print(f"🔧 백업 생성 응답: {response_data}")
        return jsonify(response_data)
            
    except Exception as e:
        print(f"💥 백업 생성 실패: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/server/backups/<server_name>', methods=['GET'])
@permission_required('backup_management')
def get_server_backups(server_name):
    """개별 서버 백업 목록 조회"""
    try:
        from app.services.proxmox_service import ProxmoxService
        proxmox_service = ProxmoxService()
        
        result = proxmox_service.get_server_backups(server_name)
        if result['success']:
            return jsonify(result)
        else:
            return jsonify({'error': result.get('message', '백업 목록 조회 실패')}), 500
            
    except Exception as e:
        print(f"💥 백업 목록 조회 실패: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/server/backup/status/<server_name>', methods=['GET'])
@permission_required('backup_management')
def get_server_backup_status(server_name):
    """서버 백업 상태 조회"""
    try:
        status = get_backup_status(server_name)
        print(f"🔍 백업 상태 조회: {server_name} - {status}")
        print(f"🔍 현재 backup_status 딕셔너리: {backup_status}")
        
        if status:
            print(f"✅ 백업 상태 반환: {server_name} - {status['status']}")
            return jsonify({
                'success': True,
                'backup_status': status
            })
        else:
            print(f"❌ 백업 상태 없음: {server_name}")
            return jsonify({
                'success': True,
                'backup_status': None
            })
    except Exception as e:
        print(f"💥 백업 상태 조회 실패: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/server/backup/status', methods=['GET'])
@permission_required('backup_management')
def get_all_backup_status():
    """모든 서버의 백업 상태 조회"""
    try:
        print(f"🔍 전체 백업 상태 조회 - 현재 backup_status: {backup_status}")
        return jsonify({
            'success': True,
            'backup_status': backup_status
        })
    except Exception as e:
        print(f"💥 전체 백업 상태 조회 실패: {str(e)}")
        return jsonify({'error': str(e)}), 500

# 백업 관리 관련 API 엔드포인트 (전체 백업 관리)
@bp.route('/api/backups/nodes', methods=['GET'])
@permission_required('backup_management')
def get_all_node_backups():
    """모든 노드의 백업 목록 조회"""
    try:
        from app.services.proxmox_service import ProxmoxService
        proxmox_service = ProxmoxService()
        
        result = proxmox_service.get_node_backups()
        if result['success']:
            return jsonify(result)
        else:
            return jsonify({'error': result.get('error', '백업 목록 조회 실패')}), 500
            
    except Exception as e:
        print(f"💥 백업 목록 조회 실패: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/backups/nodes/<node_name>', methods=['GET'])
@permission_required('backup_management')
def get_node_backups(node_name):
    """특정 노드의 백업 목록 조회"""
    try:
        from app.services.proxmox_service import ProxmoxService
        proxmox_service = ProxmoxService()
        
        result = proxmox_service.get_node_backups(node_name)
        if result['success']:
            return jsonify(result)
        else:
            return jsonify({'error': result.get('error', '백업 목록 조회 실패')}), 500
            
    except Exception as e:
        print(f"💥 백업 목록 조회 실패: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/backups/restore', methods=['POST'])
@permission_required('backup_management')
def restore_backup():
    """백업 복원"""
    try:
        data = request.get_json()
        node = data.get('node')
        vm_id = data.get('vm_id')
        filename = data.get('filename')
        
        if not all([node, vm_id, filename]):
            return jsonify({'error': 'node, vm_id, filename이 모두 필요합니다.'}), 400
        
        from app.services.proxmox_service import ProxmoxService
        proxmox_service = ProxmoxService()
        
        result = proxmox_service.restore_backup(node, vm_id, filename)
        if result['success']:
            return jsonify(result)
        else:
            return jsonify({'error': result.get('message', '백업 복원 실패')}), 500
            
    except Exception as e:
        print(f"💥 백업 복원 실패: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/backups/delete', methods=['POST'])
@permission_required('backup_management')
def delete_backup():
    """백업 삭제"""
    try:
        data = request.get_json()
        node = data.get('node')
        filename = data.get('filename')
        
        if not all([node, filename]):
            return jsonify({'error': 'node, filename이 모두 필요합니다.'}), 400
        
        from app.services.proxmox_service import ProxmoxService
        proxmox_service = ProxmoxService()
        
        result = proxmox_service.delete_backup(node, filename)
        if result['success']:
            return jsonify(result)
        else:
            return jsonify({'error': result.get('message', '백업 삭제 실패')}), 500
            
    except Exception as e:
        print(f"💥 백업 삭제 실패: {str(e)}")
        return jsonify({'error': str(e)}), 500 