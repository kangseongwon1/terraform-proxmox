"""
서버 비동기 작업 관련 엔드포인트
"""
import logging
from flask import Blueprint, request, jsonify
from flask_login import login_required
from app.routes.auth import permission_required
from app.routes.server_utils import validate_server_config, format_server_response, handle_server_error

logger = logging.getLogger(__name__)

# 비동기 작업용 별도 Blueprint 생성
async_bp = Blueprint('servers_async', __name__)


@async_bp.route('/api/servers/async', methods=['POST'])
@permission_required('create_server')
def create_server_async_endpoint():
    """비동기 서버 생성"""
    try:
        # 지연 임포트로 순환 참조 방지
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
            return jsonify({'error': '서버 이름이 필요합니다.'}), 400
        
        # 서버 설정 검증
        is_valid, error_msg, config = validate_server_config(data)
        if not is_valid:
            return jsonify({'error': error_msg}), 400
        
        # 서버 설정 구성
        server_config = {
            'name': server_name,
            'cpu': cpu,
            'memory': memory,
            'disk': disk,
            'os_type': os_type,
            'role': role,
            'firewall_group': firewall_group,
            # 추가 필드들
            'disks': data.get('disks', []),
            'network_devices': data.get('network_devices', []),
            'template_vm_id': data.get('template_vm_id', 8000),
            'vm_username': data.get('vm_username', 'rocky'),
            'vm_password': data.get('vm_password', 'rocky123')
        }
        
        # Celery 작업 실행
        task = create_server_async.delay(server_config)
        
        logger.info(f"🚀 비동기 서버 생성 작업 시작: {server_name} (Task ID: {task.id})")
        
        return jsonify({
            'success': True,
            'task_id': task.id,
            'message': f'서버 {server_name} 생성 작업이 시작되었습니다.',
            'status': 'queued'
        })
        
    except Exception as e:
        return jsonify(handle_server_error(e, "비동기 서버 생성")), 500


@async_bp.route('/api/servers/bulk_action/async', methods=['POST'])
@permission_required('manage_server')
def bulk_server_action_async_endpoint():
    """비동기 대량 서버 작업"""
    try:
        # 지연 임포트로 순환 참조 방지
        from app.tasks.server_tasks import bulk_server_action_async
        
        data = request.get_json()
        action = data.get('action')
        server_names = data.get('server_names', [])
        
        if not action or not server_names:
            return jsonify({'error': '작업 유형과 서버 목록이 필요합니다.'}), 400
        
        # Celery 작업 실행
        task = bulk_server_action_async.delay(action, server_names)
        
        logger.info(f"🚀 비동기 대량 서버 작업 시작: {action} - {len(server_names)}개 서버 (Task ID: {task.id})")
        
        return jsonify({
            'success': True,
            'task_id': task.id,
            'message': f'{len(server_names)}개 서버에 대한 {action} 작업이 시작되었습니다.',
            'status': 'queued'
        })
        
    except Exception as e:
        return jsonify(handle_server_error(e, "비동기 대량 서버 작업")), 500


@async_bp.route('/api/tasks/<task_id>/status', methods=['GET'])
@login_required
def get_task_status(task_id):
    """작업 상태 조회"""
    try:
        from app.celery_app import celery_app
        
        task = celery_app.AsyncResult(task_id)
        
        if task.state == 'PENDING':
            response = {
                'status': 'pending',
                'message': '작업 대기 중...',
                'progress': 0
            }
        elif task.state == 'PROGRESS':
            response = {
                'status': 'running',
                'message': task.info.get('message', '작업 진행 중...'),
                'progress': task.info.get('progress', 0)
            }
        elif task.state == 'SUCCESS':
            response = {
                'status': 'completed',
                'message': '작업 완료',
                'progress': 100,
                'result': task.result
            }
        else:  # FAILURE
            response = {
                'status': 'failed',
                'message': '작업 실패',
                'progress': 0,
                'error': str(task.info)
            }
        
        response['task_id'] = task_id
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"작업 상태 조회 실패: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': '작업 상태 조회 실패',
            'error': str(e)
        }), 500
