"""
서버 관리 메인 라우터 - 분리된 모듈들을 통합
"""
from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from app.routes.auth import permission_required
from app.models import Server, User, UserPermission, Notification
from app.services import ProxmoxService, TerraformService, AnsibleService, NotificationService
from app.utils.redis_utils import redis_utils
from app.routes.server_utils import get_cached_server_status, set_cached_server_status, merge_db_server_info, create_task, update_task
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


# 동기 서버 생성은 제거 - 비동기 방식 사용


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
    """사용 가능한 datastore 목록 조회 (DB 캐싱)"""
    try:
        from app.models.datastore import Datastore
        
        # DB에서 datastore 목록 조회
        db_datastores = Datastore.query.filter_by(enabled=True).all()
        
        # DB에 datastore가 없으면 Proxmox에서 가져와서 저장
        if not db_datastores:
            logger.info("🔧 DB에 datastore 정보가 없음. Proxmox에서 가져와서 저장 중...")
            
            # Proxmox에서 datastore 목록 가져오기
            proxmox_service = ProxmoxService()
            proxmox_datastores = proxmox_service.get_datastores()
            
            # 환경변수에서 기본 datastore 설정 가져오기 (초기 설정용)
            def load_env_file():
                """프로젝트 루트의 .env 파일을 직접 읽어서 딕셔너리로 반환"""
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
                        logger.info(f"🔧 .env 파일 로드 성공: {env_file}")
                    else:
                        logger.warning(f"⚠️ .env 파일을 찾을 수 없습니다: {env_file}")
                    
                    return env_vars
                except Exception as e:
                    logger.error(f"⚠️ .env 파일 읽기 실패: {e}")
                    return {}
            
            env_vars = load_env_file()
            hdd_datastore = env_vars.get('PROXMOX_HDD_DATASTORE', 'local-lvm')
            ssd_datastore = env_vars.get('PROXMOX_SSD_DATASTORE', 'local')
            
            # Proxmox datastore를 DB에 저장
            for datastore in proxmox_datastores:
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
            logger.info(f"🔧 {len(proxmox_datastores)}개 datastore를 DB에 저장 완료")
        
        # 저장된 datastore 다시 조회
        db_datastores = Datastore.query.filter_by(enabled=True).all()
        
        # DB에서 기본 datastore 설정 가져오기
        def get_default_datastores():
            """DB에서 기본 datastore 설정을 가져옴"""
            try:
                # DB에서 기본 HDD datastore 조회
                default_hdd = Datastore.query.filter_by(is_default_hdd=True, enabled=True).first()
                # DB에서 기본 SSD datastore 조회
                default_ssd = Datastore.query.filter_by(is_default_ssd=True, enabled=True).first()
                
                hdd_datastore = default_hdd.id if default_hdd else 'local-lvm'
                ssd_datastore = default_ssd.id if default_ssd else 'local'
                
                logger.info(f"🔧 DB에서 기본 datastore 설정: HDD={hdd_datastore}, SSD={ssd_datastore}")
                return hdd_datastore, ssd_datastore
            except Exception as e:
                logger.error(f"⚠️ DB에서 기본 datastore 설정 조회 실패: {e}")
                # .env 파일에서 fallback
                return get_default_datastores_from_env()
        
        def get_default_datastores_from_env():
            """환경변수에서 기본 datastore 설정을 가져옴 (fallback)"""
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
                
                logger.info(f"🔧 .env에서 기본 datastore 설정: HDD={hdd_datastore}, SSD={ssd_datastore}")
                return hdd_datastore, ssd_datastore
            except Exception as e:
                logger.error(f"⚠️ .env 파일 읽기 실패: {e}")
                return 'local-lvm', 'local'
        
        hdd_datastore, ssd_datastore = get_default_datastores()
        
        # DB datastore를 포맷팅
        formatted_datastores = []
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
        logger.error(f"Datastore 목록 조회 실패: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/datastores/refresh', methods=['POST'])
@login_required
def refresh_datastores():
    """datastore 정보 새로고침 (Proxmox에서 다시 가져와서 DB 업데이트)"""
    try:
        from app.models.datastore import Datastore
        
        # 기존 datastore 정보 삭제
        Datastore.query.delete()
        db.session.commit()
        logger.info("🔧 기존 datastore 정보 삭제 완료")
        
        # Proxmox에서 datastore 목록 가져오기
        proxmox_service = ProxmoxService()
        proxmox_datastores = proxmox_service.get_datastores()
        
        # 환경변수에서 기본 datastore 설정 가져오기
        def load_env_file():
            """프로젝트 루트의 .env 파일을 직접 읽어서 딕셔너리로 반환"""
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
                    logger.info(f"🔧 .env 파일 로드 성공: {env_file}")
                else:
                    logger.warning(f"⚠️ .env 파일을 찾을 수 없습니다: {env_file}")
                
                return env_vars
            except Exception as e:
                logger.error(f"⚠️ .env 파일 읽기 실패: {e}")
                return {}
        
        env_vars = load_env_file()
        hdd_datastore = env_vars.get('PROXMOX_HDD_DATASTORE', 'local-lvm')
        ssd_datastore = env_vars.get('PROXMOX_SSD_DATASTORE', 'local')
        
        # Proxmox datastore를 DB에 저장
        for datastore in proxmox_datastores:
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
        logger.info(f"🔧 {len(proxmox_datastores)}개 datastore를 DB에 새로 저장 완료")
        
        return jsonify({
            'success': True,
            'message': f'{len(proxmox_datastores)}개 datastore 정보를 새로고침했습니다.',
            'count': len(proxmox_datastores)
        })
        
    except Exception as e:
        logger.error(f"Datastore 새로고침 실패: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/datastores/default', methods=['POST'])
@login_required
def set_default_datastores():
    """기본 datastore 설정 변경"""
    try:
        from app.models.datastore import Datastore
        
        data = request.get_json()
        hdd_datastore_id = data.get('hdd_datastore_id')
        ssd_datastore_id = data.get('ssd_datastore_id')
        
        if not hdd_datastore_id or not ssd_datastore_id:
            return jsonify({'error': 'HDD와 SSD datastore ID가 필요합니다.'}), 400
        
        # 기존 기본 설정 해제
        Datastore.query.filter_by(is_default_hdd=True).update({'is_default_hdd': False})
        Datastore.query.filter_by(is_default_ssd=True).update({'is_default_ssd': False})
        
        # 새로운 기본 설정
        hdd_datastore = Datastore.query.filter_by(id=hdd_datastore_id).first()
        ssd_datastore = Datastore.query.filter_by(id=ssd_datastore_id).first()
        
        if not hdd_datastore:
            return jsonify({'error': f'HDD datastore를 찾을 수 없습니다: {hdd_datastore_id}'}), 404
        if not ssd_datastore:
            return jsonify({'error': f'SSD datastore를 찾을 수 없습니다: {ssd_datastore_id}'}), 404
        
        hdd_datastore.is_default_hdd = True
        ssd_datastore.is_default_ssd = True
        
        db.session.commit()
        
        logger.info(f"🔧 기본 datastore 설정 변경: HDD={hdd_datastore_id}, SSD={ssd_datastore_id}")
        
        return jsonify({
            'success': True, 
            'message': '기본 datastore 설정이 변경되었습니다.',
            'hdd_datastore': hdd_datastore_id,
            'ssd_datastore': ssd_datastore_id
        })
        
    except Exception as e:
        logger.error(f"기본 datastore 설정 변경 실패: {str(e)}")
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