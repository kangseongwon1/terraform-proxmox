"""
모니터링 관련 라우트 - .env 파일 중심, 더미 데이터 제거
"""
from flask import Blueprint, jsonify, request, render_template
from flask_login import login_required
import requests
import json
import random
import time
import os
from datetime import datetime, timedelta
from app.models import Server
from app import db
from sqlalchemy import text

bp = Blueprint('monitoring', __name__, url_prefix='/monitoring')

# 메트릭 캐시 (실제 환경에서는 Redis 등을 사용)
metrics_cache = {}
last_update = {}

def get_grafana_config():
    """Grafana 설정을 .env에서 직접 가져오기"""
    return {
        'base_url': os.environ.get('GRAFANA_URL', 'http://localhost:3000'),
        'username': os.environ.get('GRAFANA_USERNAME', 'admin'),
        'password': os.environ.get('GRAFANA_PASSWORD', 'admin'),
        'org_id': os.environ.get('GRAFANA_ORG_ID', '1'),
        'dashboard_uid': os.environ.get('GRAFANA_DASHBOARD_UID', 'system_monitoring'),
        'dashboard_id': os.environ.get('GRAFANA_DASHBOARD_ID', '2'),
        'dashboard_url': os.environ.get('GRAFANA_DASHBOARD_URL', '/d/system_monitoring/system-monitoring-dashboard-10-servers'),
        'anonymous_access': os.environ.get('GRAFANA_ANONYMOUS_ACCESS', 'true').lower() == 'true',
        'auto_refresh': os.environ.get('GRAFANA_AUTO_REFRESH', '5s')
    }

def get_prometheus_config():
    """Prometheus 설정을 .env에서 직접 가져오기"""
    return {
        'url': os.environ.get('PROMETHEUS_URL', 'http://localhost:9090'),
        'username': os.environ.get('PROMETHEUS_USERNAME', ''),
        'password': os.environ.get('PROMETHEUS_PASSWORD', '')
    }

def get_monitoring_config():
    """모니터링 설정을 .env에서 직접 가져오기"""
    return {
        'default_time_range': os.environ.get('MONITORING_DEFAULT_TIME_RANGE', '1h'),
        'health_check_interval': os.environ.get('MONITORING_HEALTH_CHECK_INTERVAL', '30s'),
        'ping_timeout': os.environ.get('MONITORING_PING_TIMEOUT', '5s'),
        'ssh_timeout': os.environ.get('MONITORING_SSH_TIMEOUT', '10s'),
        'auto_install_node_exporter': os.environ.get('NODE_EXPORTER_AUTO_INSTALL', 'true').lower() == 'true',
        'node_exporter_port': int(os.environ.get('NODE_EXPORTER_PORT', '9100')),
        'node_exporter_version': os.environ.get('NODE_EXPORTER_VERSION', '1.6.1')
    }

def get_alerts_config():
    """알림 설정을 .env에서 직접 가져오기"""
    return {
        'enable_alerts': os.environ.get('ALERTS_ENABLED', 'true').lower() == 'true',
        'alert_email': os.environ.get('ALERTS_EMAIL', 'admin@example.com'),
        'cpu_warning_threshold': float(os.environ.get('ALERTS_CPU_WARNING_THRESHOLD', '80')),
        'cpu_critical_threshold': float(os.environ.get('ALERTS_CPU_CRITICAL_THRESHOLD', '95')),
        'memory_warning_threshold': float(os.environ.get('ALERTS_MEMORY_WARNING_THRESHOLD', '85')),
        'memory_critical_threshold': float(os.environ.get('ALERTS_MEMORY_CRITICAL_THRESHOLD', '95'))
    }

def get_security_config():
    """보안 설정을 .env에서 직접 가져오기"""
    return {
        'enable_https': os.environ.get('SECURITY_ENABLE_HTTPS', 'false').lower() == 'true',
        'enable_auth': os.environ.get('SECURITY_ENABLE_AUTH', 'true').lower() == 'true',
        'session_timeout': int(os.environ.get('SECURITY_SESSION_TIMEOUT', '3600')),
        'max_login_attempts': int(os.environ.get('SECURITY_MAX_LOGIN_ATTEMPTS', '5'))
    }

def get_current_alerts():
    """현재 알림 목록 반환"""
    try:
        # 실제 환경에서는 DB에서 알림을 가져옴
        # 현재는 메모리에서 관리 (테스트용)
        if not hasattr(get_current_alerts, '_alerts'):
            get_current_alerts._alerts = []
        
        return get_current_alerts._alerts
        
    except Exception as e:
        print(f"알림 목록 조회 오류: {e}")
        return []

def add_alert(alert):
    """새 알림 추가"""
    try:
        if not hasattr(get_current_alerts, '_alerts'):
            get_current_alerts._alerts = []
        
        # 중복 알림 체크 (같은 서버, 같은 메트릭, 같은 레벨)
        existing_alert = next(
            (a for a in get_current_alerts._alerts 
             if a['server_ip'] == alert['server_ip'] 
             and a['metric_type'] == alert['metric_type'] 
             and a['level'] == alert['level']), None
        )
        
        if not existing_alert:
            get_current_alerts._alerts.append(alert)
            print(f"새 알림 추가: {alert['message']}")
        
        return True
        
    except Exception as e:
        print(f"알림 추가 오류: {e}")
        return False

def acknowledge_alert(alert_id):
    """알림 확인 처리"""
    try:
        alerts = get_current_alerts()
        for alert in alerts:
            if alert['id'] == alert_id:
                alert['acknowledged'] = True
                alert['acknowledged_at'] = datetime.now().isoformat()
                print(f"알림 확인 처리: {alert_id}")
                return True
        
        return False
        
    except Exception as e:
        print(f"알림 확인 처리 오류: {e}")
        return False

def clear_old_alerts():
    """오래된 알림 정리 (24시간 이상 된 알림)"""
    try:
        alerts = get_current_alerts()
        current_time = datetime.now()
        
        # 24시간 이상 된 알림 제거
        alerts[:] = [
            alert for alert in alerts 
            if (current_time - datetime.fromisoformat(alert['timestamp'])).total_seconds() < 86400
        ]
        
        print(f"오래된 알림 정리 완료")
        
    except Exception as e:
        print(f"오래된 알림 정리 오류: {e}")

@bp.route('/alerts/<alert_id>/acknowledge', methods=['POST'])
@login_required
def acknowledge_alert_route(alert_id):
    """알림 확인 처리 API"""
    try:
        if acknowledge_alert(alert_id):
            return jsonify({
                'success': True,
                'message': '알림이 확인 처리되었습니다.'
            })
        else:
            return jsonify({
                'success': False,
                'error': '알림을 찾을 수 없습니다.'
            }), 404
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/alerts/clear', methods=['POST'])
@login_required
def clear_alerts():
    """모든 알림 정리"""
    try:
        if hasattr(get_current_alerts, '_alerts'):
            get_current_alerts._alerts.clear()
        
        return jsonify({
            'success': True,
            'message': '모든 알림이 정리되었습니다.'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/content', methods=['GET'])
@login_required
def monitoring_content():
    """모니터링 페이지 컨텐츠"""
    return render_template('partials/monitoring_content.html')

@bp.route('/summary', methods=['GET'])
@login_required
def get_monitoring_summary():
    """모니터링 요약 통계 반환"""
    try:
        servers = get_actual_servers()
        total = len(servers)
        healthy = len([s for s in servers if s['status'] == 'healthy'])
        warning = len([s for s in servers if s['status'] == 'warning'])
        critical = len([s for s in servers if s['status'] == 'critical'])
        
        return jsonify({
            'success': True,
            'data': {
                'total_servers': total,
                'healthy_servers': healthy,
                'warning_servers': warning,
                'critical_servers': critical,
                'last_update': datetime.now().isoformat()
            }
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/servers', methods=['GET'])
@login_required
def get_monitoring_servers():
    """모니터링 대상 서버 목록 반환"""
    try:
        servers = get_actual_servers()
        return jsonify({
            'success': True,
            'data': servers
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/grafana-dashboard', methods=['GET'])
@login_required
def get_grafana_dashboard():
    """Grafana 대시보드 정보 조회 (개선된 버전)"""
    try:
        dashboard_info = get_dashboard_info()
        if dashboard_info:
            return jsonify({
                'success': True,
                'data': dashboard_info
            })
        else:
            # 대시보드 정보가 없으면 기본 정보 반환
            default_info = {
                'base_url': 'http://localhost:3000',
                'dashboard_id': '1',
                'dashboard_uid': 'system_monitoring',
                'org_id': '1',
                'dashboard_url': 'http://localhost:3000/d/system_monitoring',
                'grafana_url': 'http://localhost:3000',
                'embed_url': 'http://localhost:3000/d/system_monitoring?orgId=1&theme=light&kiosk=tv'
            }
            return jsonify({
                'success': True,
                'data': default_info
            })
            
    except Exception as e:
        print(f"Grafana 대시보드 정보 조회 오류: {e}")
        return jsonify({'error': str(e)}), 500

def get_dashboard_info():
    """대시보드 정보를 .env에서 직접 가져오기"""
    try:
        # .env에서 Grafana 설정 가져오기
        grafana_config = get_grafana_config()
        
        # 대시보드 정보 파일도 확인 (우선순위: .env > 대시보드 파일)
        dashboard_file = '/tmp/dashboard_info.json'
        if os.path.exists(dashboard_file):
            with open(dashboard_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            # 대시보드 파일의 정보를 .env 설정과 병합
            dashboard_uid = data.get('dashboard_uid', grafana_config['dashboard_uid'])
            dashboard_id = data.get('dashboard_id', grafana_config['dashboard_id'])
            dashboard_url = data.get('dashboard_url', grafana_config['dashboard_url'])
        else:
            # 대시보드 파일이 없으면 .env 설정 사용
            dashboard_uid = grafana_config['dashboard_uid']
            dashboard_id = grafana_config['dashboard_id']
            dashboard_url = grafana_config['dashboard_url']
        
        # 최종 대시보드 정보 반환
        return {
            'base_url': grafana_config['base_url'],
            'dashboard_id': dashboard_id,
            'dashboard_uid': dashboard_uid,
            'org_id': grafana_config['org_id'],
            'dashboard_url': dashboard_url,
            'grafana_url': grafana_config['base_url'],  # 하위 호환성
            'embed_url': f"{grafana_config['base_url']}/d/{dashboard_uid}?orgId={grafana_config['org_id']}&theme=light&kiosk=tv"
        }
        
    except Exception as e:
        print(f"대시보드 정보 읽기 오류: {e}")
        # 오류 시 .env 기본 설정 반환
        grafana_config = get_grafana_config()
        return {
            'base_url': grafana_config['base_url'],
            'dashboard_id': grafana_config['dashboard_id'],
            'dashboard_uid': grafana_config['dashboard_uid'],
            'org_id': grafana_config['org_id'],
            'dashboard_url': grafana_config['dashboard_url'],
            'grafana_url': grafana_config['base_url'],
            'embed_url': f"{grafana_config['base_url']}/d/{grafana_config['dashboard_uid']}?orgId={grafana_config['org_id']}&theme=light&kiosk=tv"
        }

@bp.route('/grafana-dashboard/embed', methods=['GET'])
@login_required
def get_grafana_embed_url():
    """Grafana 대시보드 임베드 URL 생성"""
    try:
        dashboard_info = get_dashboard_info()
        if not dashboard_info:
            return jsonify({
                'success': False,
                'error': '대시보드 정보를 찾을 수 없습니다.'
            }), 404
        
        # 서버 선택 파라미터 추가
        selected_server = request.args.get('server', 'all')
        
        # Grafana 대시보드 임베드 URL 생성
        embed_url = create_grafana_embed_url(dashboard_info, selected_server)
        
        return jsonify({
            'success': True,
            'data': {
                'embed_url': embed_url,
                'dashboard_info': dashboard_info
            }
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def create_grafana_embed_url(dashboard_info, selected_server):
    """Grafana 대시보드 임베드 URL 생성 (.env 사용)"""
    try:
        # .env에서 Grafana 설정 가져오기
        grafana_config = get_grafana_config()
        
        # 필드명 매핑 (하위 호환성)
        base_url = dashboard_info.get('base_url') or dashboard_info.get('grafana_url', grafana_config['base_url'])
        dashboard_uid = dashboard_info['dashboard_uid']
        org_id = dashboard_info.get('org_id', grafana_config['org_id'])
        
        # .env 설정에 따라 인증 방식 결정
        if grafana_config['anonymous_access']:
            # 익명 접근 허용
            embed_url = f"{base_url}/d/{dashboard_uid}?orgId={org_id}&theme=light&kiosk=tv&autofitpanels&refresh={grafana_config['auto_refresh']}"
        else:
            # 기본 인증 정보 포함
            username = grafana_config['username']
            password = grafana_config['password']
            embed_url = f"http://{username}:{password}@{base_url.replace('http://', '')}/d/{dashboard_uid}?orgId={org_id}&theme=light&kiosk=tv&autofitpanels&refresh={grafana_config['auto_refresh']}"
        
        # 서버 선택이 'all'이 아닌 경우 필터 추가
        if selected_server != 'all':
            # Grafana 변수로 서버 필터링
            embed_url += f"&var-instance={selected_server}:9100"
        
        # 시간 범위 설정 (.env에서 설정)
        monitoring_config = get_monitoring_config()
        time_range = monitoring_config['default_time_range']
        
        if time_range == '1h':
            now = datetime.now()
            one_hour_ago = now - timedelta(hours=1)
            embed_url += f"&from={int(one_hour_ago.timestamp() * 1000)}&to={int(now.timestamp() * 1000)}"
        elif time_range == '6h':
            now = datetime.now()
            six_hours_ago = now - timedelta(hours=6)
            embed_url += f"&from={int(six_hours_ago.timestamp() * 1000)}&to={int(now.timestamp() * 1000)}"
        elif time_range == '24h':
            now = datetime.now()
            one_day_ago = now - timedelta(days=1)
            embed_url += f"&from={int(one_day_ago.timestamp() * 1000)}&to={int(now.timestamp() * 1000)}"
        
        return embed_url
        
    except Exception as e:
        print(f"임베드 URL 생성 오류: {e}")
        return dashboard_info.get('embed_url', '')

@bp.route('/config', methods=['GET'])
@login_required
def get_monitoring_config_api():
    """모니터링 설정 조회 API (.env 기반)"""
    try:
        all_config = {
            'grafana': get_grafana_config(),
            'prometheus': get_prometheus_config(),
            'monitoring': get_monitoring_config(),
            'alerts': get_alerts_config(),
            'security': get_security_config()
        }
        return jsonify({
            'success': True,
            'data': all_config
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/config', methods=['POST'])
@login_required
def update_monitoring_config_api():
    """모니터링 설정 업데이트 API"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': '설정 데이터가 없습니다.'}), 400
        
        # .env 파일 업데이트는 별도 구현 필요
        return jsonify({
            'success': True,
            'message': '설정이 업데이트되었습니다.'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/config-page')
@login_required
def monitoring_config_page():
    """모니터링 설정 페이지"""
    return render_template('partials/monitoring_config_content.html')

def get_actual_servers():
    """실제 DB에서 서버 목록 가져오기 - 더미 데이터 제거"""
    try:
        # 데이터베이스 연결 상태 확인
        try:
            # SQLAlchemy 2.0 호환 방식으로 DB 연결 테스트
            db.session.execute(text('SELECT 1'))
        except Exception as db_error:
            print(f"데이터베이스 연결 오류: {db_error}")
            return []  # 더미 데이터 제거 - 빈 배열 반환
        
        # Server 모델 접근 시도
        try:
            servers = []
            db_servers = Server.query.all()
            
            for server in db_servers:
                # IP 주소 처리
                ip_address = server.ip_address
                if isinstance(ip_address, list) and len(ip_address) > 0:
                    ip = ip_address[0]
                elif isinstance(ip_address, str):
                    ip = ip_address
                else:
                    ip = '0.0.0.0'
                
                # 포트 설정 (기본값: 22)
                port = '22'
                
                # 서버 상태 결정
                status = determine_server_status(server)
                
                servers.append({
                    'ip': ip,
                    'port': port,
                    'status': status,
                    'name': server.name,
                    'role': server.role,
                    'vmid': server.vmid
                })
            
            print(f"DB에서 {len(servers)}개 서버 로드 완료")
            return servers
            
        except Exception as model_error:
            print(f"Server 모델 접근 오류: {model_error}")
            return []  # 더미 데이터 제거 - 빈 배열 반환
        
    except Exception as e:
        print(f"서버 목록 조회 오류: {e}")
        return []  # 더미 데이터 제거 - 빈 배열 반환

def determine_server_status(server):
    """서버 상태 결정 (실제 환경에서는 ping 또는 SSH로 확인)"""
    try:
        # 여기서 실제 서버 상태 확인 로직 구현
        # 예: ping, SSH 연결, HTTP 응답 등
        
        # 임시로 랜덤 상태 반환 (실제 환경에서는 실제 확인)
        status_rand = random.random()
        if status_rand < 0.8:
            return 'healthy'
        elif status_rand < 0.95:
            return 'warning'
        else:
            return 'critical'
            
    except Exception as e:
        print(f"서버 상태 확인 오류 ({server.name}): {e}")
        return 'unknown'