"""
서버 관리 메인 라우터 - 분리된 모듈들을 통합
"""
from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from app.routes.auth import permission_required
from app.models import Server, User, UserPermission
from app.services import ProxmoxService, TerraformService, AnsibleService, NotificationService
from app.utils.redis_utils import redis_utils
from app.routes.server_utils import get_cached_server_status, set_cached_server_status, merge_db_server_info
from app import db
import json
import os
import subprocess
import threading
import time
import uuid
import logging
from datetime import datetime

# 로거 설정
logger = logging.getLogger(__name__)

bp = Blueprint('servers', __name__)

# 전역 작업 상태 dict
tasks = {}


def _remove_from_known_hosts(ip_address: str) -> bool:
    """SSH known_hosts 파일에서 특정 IP 제거"""
    try:
        home_dir = os.path.expanduser('~')
        known_hosts_path = os.path.join(home_dir, '.ssh', 'known_hosts')
        
        if not os.path.exists(known_hosts_path):
            logger.info(f"known_hosts 파일이 존재하지 않음: {known_hosts_path}")
            return True
        
        try:
            result = subprocess.run([
                'ssh-keygen', '-R', ip_address
            ], capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                logger.info(f"ssh-keygen으로 {ip_address} 제거 성공")
                return True
            else:
                logger.warning(f"ssh-keygen으로 {ip_address} 제거 실패: {result.stderr}")
                return False
        except subprocess.TimeoutExpired:
            logger.error(f"ssh-keygen 타임아웃: {ip_address}")
            return False
        except Exception as e:
            logger.error(f"ssh-keygen 실행 중 오류: {e}")
            return False
            
    except Exception as e:
        logger.error(f"known_hosts 파일 처리 중 오류: {e}")
        return False


# ========================================
# 공통 API 엔드포인트
# ========================================

@bp.route('/api/tasks/status')
@login_required
def get_tasks_status():
    """작업 상태 조회"""
    try:
        return jsonify({
            'success': True,
            'tasks': tasks
        })
    except Exception as e:
        logger.error(f"작업 상태 조회 실패: {str(e)}")
        return jsonify({'error': str(e)}), 500


@bp.route('/api/tasks/config')
@login_required
def get_tasks_config():
    """작업 설정 조회"""
    try:
        return jsonify({
            'success': True,
            'config': {
                'max_concurrent_tasks': 5,
                'task_timeout': 300
            }
        })
    except Exception as e:
        logger.error(f"작업 설정 조회 실패: {str(e)}")
        return jsonify({'error': str(e)}), 500


@bp.route('/api/servers/brief', methods=['GET'])
@login_required
def get_servers_brief():
    """서버 간단 정보 조회"""
    try:
        servers = Server.query.all()
        server_list = []
        
        for server in servers:
            server_data = {
                'id': server.id,
                'name': server.name,
                'role': server.role,
                'firewall_group': server.firewall_group,
                'os_type': server.os_type
            }
            server_list.append(server_data)
        
        return jsonify({
            'success': True,
            'servers': server_list
        })
        
    except Exception as e:
        logger.error(f"서버 간단 정보 조회 실패: {str(e)}")
        return jsonify({'error': str(e)}), 500


@bp.route('/api/all_server_status', methods=['GET'])
@login_required
def get_all_server_status():
    """모든 서버 상태 조회 (Redis 캐싱 적용)"""
    try:
        # Redis 캐시 확인
        cached_data = get_cached_server_status()
        if cached_data:
            return jsonify(cached_data)
        
        logger.info("🌐 서버 상태 데이터 조회 (캐시 미스)")
        from app.services.proxmox_service import ProxmoxService
        proxmox_service = ProxmoxService()
        
        # get_all_vms 함수 사용 (통계 정보 포함)
        result = proxmox_service.get_all_vms()
        
        if result['success']:
            # 기존 구조와 호환성을 위해 데이터 변환
            servers = result['data']['servers']
            stats = result['data']['stats']
            
            # Proxmox 데이터에 DB 정보 병합
            servers = merge_db_server_info(servers)
            
            # 통계 정보를 포함하여 반환
            response_data = {
                'success': True,
                'servers': servers,
                'stats': stats
            }
            
            # Redis에 캐시 저장 (2분)
            set_cached_server_status(response_data, expire=120)
            
            return jsonify(response_data)
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


# ========================================
# 웹 페이지 라우트
# ========================================

@bp.route('/')
@login_required
def index():
    """서버 목록 페이지"""
    return render_template('servers/index.html')


# @bp.route('/create', methods=['GET', 'POST'])
# @login_required
# def create():
#     """서버 생성 페이지"""
#     if request.method == 'POST':
#         # 폼 데이터 처리
#         data = request.form.to_dict()
        
#         # 서버 생성 로직 (기존 코드 유지)
#         try:
#             # ... 기존 서버 생성 로직 ...
#             pass
#         except Exception as e:
#             flash(f'서버 생성 중 오류가 발생했습니다: {str(e)}', 'error')
#             return redirect(url_for('servers.create'))
    
#     return render_template('servers/create.html')


@bp.route('/<int:server_id>')
@login_required
def server_detail(server_id):
    """서버 상세 페이지"""
    server = Server.query.get_or_404(server_id)
    return render_template('servers/detail.html', server=server)


@bp.route('/status')
@login_required
def status():
    """서버 상태 페이지"""
    return render_template('servers/status.html')


# ========================================
# 기타 유틸리티 엔드포인트
# ========================================

@bp.route('/api/datastores', methods=['GET'])
@login_required
def get_datastores():
    """데이터스토어 목록 조회"""
    try:
        from app.services.proxmox_service import ProxmoxService
        
        proxmox_service = ProxmoxService()
        result = proxmox_service.get_storage_info()
        
        if result['success']:
            return jsonify({
                'success': True,
                'datastores': result['data']
            })
        else:
            return jsonify({
                'success': False,
                'error': result.get('message', '데이터스토어 조회 실패')
            }), 500
            
    except Exception as e:
        logger.error(f"데이터스토어 조회 실패: {str(e)}")
        return jsonify({'error': str(e)}), 500


@bp.route('/api/datastores/refresh', methods=['POST'])
@permission_required('manage_server')
def refresh_datastores():
    """데이터스토어 목록 새로고침"""
    try:
        from app.services.proxmox_service import ProxmoxService
        
        proxmox_service = ProxmoxService()
        result = proxmox_service.get_storage_info()
        
        if result['success']:
            return jsonify({
                'success': True,
                'message': '데이터스토어 목록이 새로고침되었습니다.',
                'datastores': result['data']
            })
        else:
            return jsonify({
                'success': False,
                'error': result.get('message', '데이터스토어 새로고침 실패')
            }), 500
            
    except Exception as e:
        logger.error(f"데이터스토어 새로고침 실패: {str(e)}")
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