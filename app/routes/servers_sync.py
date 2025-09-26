"""
서버 동기 작업 관련 엔드포인트
"""
import logging
from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash
from flask_login import login_required
from app.routes.auth import permission_required
from app.models import Server, Notification
from app import db
from app.routes.server_utils import (
    create_notification, get_server_by_name, validate_server_config, 
    format_server_response, handle_server_error, get_cached_server_status,
    set_cached_server_status, merge_db_server_info
)
from app.utils.redis_utils import redis_utils

logger = logging.getLogger(__name__)

# 동기 작업용 별도 Blueprint 생성
sync_bp = Blueprint('servers_sync', __name__)


@sync_bp.route('/api/servers', methods=['GET'])
@login_required
def get_servers():
    """서버 목록 조회"""
    try:
        servers = Server.query.all()
        server_list = []
        
        for server in servers:
            server_data = {
                'id': server.id,
                'name': server.name,
                'cpu': server.cpu,
                'memory': server.memory,
                'disk': server.disk,
                'os_type': server.os_type,
                'role': server.role,
                'firewall_group': server.firewall_group,
                'created_at': server.created_at.isoformat() if server.created_at else None
            }
            server_list.append(server_data)
        
        return jsonify({
            'success': True,
            'servers': server_list
        })
        
    except Exception as e:
        return jsonify(handle_server_error(e, "서버 목록 조회")), 500


@sync_bp.route('/api/servers', methods=['POST'])
@permission_required('create_server')
def create_server():
    """서버 생성 (동기)"""
    try:
        data = request.get_json()
        
        # 서버 설정 검증
        is_valid, error_msg, config = validate_server_config(data)
        if not is_valid:
            return jsonify({'error': error_msg}), 400
        
        # 새 서버 생성
        server = Server(
            name=config['name'],
            cpu=config['cpu'],
            memory=config['memory'],
            disk=config['disk'],
            os_type=config.get('os_type', 'ubuntu'),
            role=config.get('role', ''),
            firewall_group=config.get('firewall_group', '')
        )
        
        db.session.add(server)
        db.session.commit()
        
        # 성공 알림 생성
        create_notification(
            notification_type='server_created',
            title='서버 생성 완료',
            message=f'서버 {server.name}이(가) 성공적으로 생성되었습니다.',
            severity='success'
        )
        
        logger.info(f"✅ 서버 생성 완료: {server.name}")
        
        return jsonify({
            'success': True,
            'message': f'서버 {server.name}이(가) 생성되었습니다.',
            'server': {
                'id': server.id,
                'name': server.name,
                'cpu': server.cpu,
                'memory': server.memory,
                'disk': server.disk,
                'os_type': server.os_type,
                'role': server.role,
                'firewall_group': server.firewall_group
            }
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify(handle_server_error(e, "서버 생성")), 500


@sync_bp.route('/api/servers/<server_name>/start', methods=['POST'])
@permission_required('manage_server')
def start_server(server_name):
    """서버 시작"""
    try:
        from app.services.proxmox_service import ProxmoxService
        
        server = get_server_by_name(server_name)
        if not server:
            return jsonify({'error': '서버를 찾을 수 없습니다.'}), 404
        
        proxmox_service = ProxmoxService()
        result = proxmox_service.start_vm(server_name)
        
        if result['success']:
            create_notification(
                notification_type='server_action',
                title='서버 시작',
                message=f'서버 {server_name}이(가) 시작되었습니다.',
                severity='success'
            )
            return jsonify({'success': True, 'message': f'서버 {server_name}이(가) 시작되었습니다.'})
        else:
            return jsonify({'error': result.get('message', '서버 시작 실패')}), 500
            
    except Exception as e:
        return jsonify(handle_server_error(e, "서버 시작")), 500


@sync_bp.route('/api/servers/<server_name>/stop', methods=['POST'])
@permission_required('manage_server')
def stop_server(server_name):
    """서버 중지"""
    try:
        from app.services.proxmox_service import ProxmoxService
        
        server = get_server_by_name(server_name)
        if not server:
            return jsonify({'error': '서버를 찾을 수 없습니다.'}), 404
        
        proxmox_service = ProxmoxService()
        result = proxmox_service.stop_vm(server_name)
        
        if result['success']:
            create_notification(
                notification_type='server_action',
                title='서버 중지',
                message=f'서버 {server_name}이(가) 중지되었습니다.',
                severity='info'
            )
            return jsonify({'success': True, 'message': f'서버 {server_name}이(가) 중지되었습니다.'})
        else:
            return jsonify({'error': result.get('message', '서버 중지 실패')}), 500
            
    except Exception as e:
        return jsonify(handle_server_error(e, "서버 중지")), 500


@sync_bp.route('/api/servers/<server_name>/reboot', methods=['POST'])
@permission_required('manage_server')
def reboot_server(server_name):
    """서버 재부팅"""
    try:
        from app.services.proxmox_service import ProxmoxService
        
        server = get_server_by_name(server_name)
        if not server:
            return jsonify({'error': '서버를 찾을 수 없습니다.'}), 404
        
        proxmox_service = ProxmoxService()
        result = proxmox_service.reboot_vm(server_name)
        
        if result['success']:
            create_notification(
                notification_type='server_action',
                title='서버 재부팅',
                message=f'서버 {server_name}이(가) 재부팅되었습니다.',
                severity='info'
            )
            return jsonify({'success': True, 'message': f'서버 {server_name}이(가) 재부팅되었습니다.'})
        else:
            return jsonify({'error': result.get('message', '서버 재부팅 실패')}), 500
            
    except Exception as e:
        return jsonify(handle_server_error(e, "서버 재부팅")), 500


@sync_bp.route('/api/servers/<server_name>/delete', methods=['POST'])
@permission_required('manage_server')
def delete_server(server_name):
    """서버 삭제"""
    try:
        from app.services.proxmox_service import ProxmoxService
        
        server = get_server_by_name(server_name)
        if not server:
            return jsonify({'error': '서버를 찾을 수 없습니다.'}), 404
        
        proxmox_service = ProxmoxService()
        result = proxmox_service.delete_vm(server_name)
        
        if result['success']:
            # DB에서 서버 삭제
            db.session.delete(server)
            db.session.commit()
            
            create_notification(
                notification_type='server_deleted',
                title='서버 삭제',
                message=f'서버 {server_name}이(가) 삭제되었습니다.',
                severity='warning'
            )
            
            return jsonify({'success': True, 'message': f'서버 {server_name}이(가) 삭제되었습니다.'})
        else:
            return jsonify({'error': result.get('message', '서버 삭제 실패')}), 500
            
    except Exception as e:
        db.session.rollback()
        return jsonify(handle_server_error(e, "서버 삭제")), 500

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