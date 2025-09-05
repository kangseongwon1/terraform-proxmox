"""
모니터링 관련 라우트
"""
from flask import Blueprint, jsonify, request, render_template
from flask_login import login_required
import requests
import json
import random
import time
from datetime import datetime, timedelta
from app.models import Server
from app import db
from sqlalchemy import text

bp = Blueprint('monitoring', __name__, url_prefix='/monitoring')

# 프로메테우스 설정 (개발 서버용)
PROMETHEUS_URL = "http://localhost:9090"  # 개발 서버 IP로 변경 필요

# 메트릭 캐시 (실제 환경에서는 Redis 등을 사용)
metrics_cache = {}
last_update = {}

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

@bp.route('/test-metrics', methods=['GET'])
def test_metrics():
    """테스트용 메트릭 (인증 없음)"""
    try:
        server_ip = request.args.get('server', 'all')
        
        if server_ip == 'all':
            # 모든 서버의 메트릭
            metrics = {}
            servers = get_actual_servers()
            for server in servers:
                metrics[server['ip']] = generate_sample_metrics(server['ip'])
            
            return jsonify({
                'success': True,
                'data': metrics,
                'timestamp': datetime.now().isoformat()
            })
        else:
            # 특정 서버의 메트릭
            metrics = generate_sample_metrics(server_ip)
            return jsonify({
                'success': True,
                'data': metrics,
                'timestamp': datetime.now().isoformat()
            })
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/test-summary', methods=['GET'])
def test_summary():
    """테스트용 요약 통계 (인증 없음)"""
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

@bp.route('/test-servers', methods=['GET'])
def test_servers():
    """테스트용 서버 목록 (인증 없음)"""
    try:
        servers = get_actual_servers()
        return jsonify({
            'success': True,
            'data': servers
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/simple-metrics', methods=['GET'])
@login_required
def get_simple_metrics():
    """간단한 샘플 메트릭 반환 (Prometheus 없이 테스트용)"""
    try:
        server_ip = request.args.get('server', 'all')
        
        if server_ip == 'all':
            # 모든 서버의 메트릭
            metrics = {}
            servers = get_actual_servers()
            for server in servers:
                metrics[server['ip']] = generate_sample_metrics(server['ip'])
            
            return jsonify({
                'success': True,
                'data': metrics,
                'timestamp': datetime.now().isoformat()
            })
        else:
            # 특정 서버의 메트릭
            metrics = generate_sample_metrics(server_ip)
            return jsonify({
                'success': True,
                'data': metrics,
                'timestamp': datetime.now().isoformat()
            })
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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

@bp.route('/real-time-metrics', methods=['GET'])
@login_required
def get_real_time_metrics():
    """실시간 메트릭 반환 (웹 콘솔 차트 업데이트용)"""
    try:
        server_ip = request.args.get('server', 'all')
        metric_type = request.args.get('type', 'all')
        
        if server_ip == 'all':
            # 전체 서버의 평균 메트릭
            all_metrics = {}
            servers = get_actual_servers()
            
            if not servers:
                # 서버가 없으면 기본 메트릭 반환
                return jsonify({
                    'success': True,
                    'data': {
                        'cpu_usage': 0,
                        'memory_usage': 0,
                        'disk_usage': 0,
                        'network_usage': 0,
                        'timestamp': int(time.time())
                    }
                })
            
            # 실제 서버 상태 기반 메트릭 생성
            for server in servers:
                # 서버 상태에 따른 현실적인 메트릭
                if server['status'] == 'critical':
                    # 위험 상태 - 높은 사용률
                    all_metrics[server['ip']] = {
                        'cpu_usage': random.uniform(80, 95),
                        'memory_usage': random.uniform(85, 98),
                        'disk_usage': random.uniform(85, 95),
                        'network_usage': random.uniform(70, 90)
                    }
                elif server['status'] == 'warning':
                    # 경고 상태 - 중간 사용률
                    all_metrics[server['ip']] = {
                        'cpu_usage': random.uniform(60, 80),
                        'memory_usage': random.uniform(70, 85),
                        'disk_usage': random.uniform(70, 85),
                        'network_usage': random.uniform(50, 70)
                    }
                else:
                    # 정상 상태 - 낮은 사용률
                    all_metrics[server['ip']] = {
                        'cpu_usage': random.uniform(10, 40),
                        'memory_usage': random.uniform(20, 60),
                        'disk_usage': random.uniform(30, 70),
                        'network_usage': random.uniform(5, 25)
                    }
            
            # 평균값 계산
            cpu_avg = sum(m['cpu_usage'] for m in all_metrics.values()) / len(all_metrics)
            memory_avg = sum(m['memory_usage'] for m in all_metrics.values()) / len(all_metrics)
            disk_avg = sum(m['disk_usage'] for m in all_metrics.values()) / len(all_metrics)
            network_avg = sum(m['network_usage'] for m in all_metrics.values()) / len(all_metrics)
            
            result = {
                'timestamp': int(time.time()),
                'cpu_usage': round(cpu_avg, 2),
                'memory_usage': round(memory_avg, 2),
                'disk_usage': round(disk_avg, 2),
                'network_usage': round(network_avg, 2)
            }
            
        else:
            # 특정 서버의 메트릭 - 해당 서버 상태 기반
            servers = get_actual_servers()
            target_server = next((s for s in servers if s['ip'] == server_ip), None)
            
            if target_server:
                # 서버 상태에 따른 메트릭
                if target_server['status'] == 'critical':
                    metrics = {
                        'cpu_usage': random.uniform(80, 95),
                        'memory_usage': random.uniform(85, 98),
                        'disk_usage': random.uniform(85, 95),
                        'network_usage': random.uniform(70, 90)
                    }
                elif target_server['status'] == 'warning':
                    metrics = {
                        'cpu_usage': random.uniform(60, 80),
                        'memory_usage': random.uniform(70, 85),
                        'disk_usage': random.uniform(70, 85),
                        'network_usage': random.uniform(50, 70)
                    }
                else:
                    metrics = {
                        'cpu_usage': random.uniform(10, 40),
                        'memory_usage': random.uniform(20, 60),
                        'disk_usage': random.uniform(30, 70),
                        'network_usage': random.uniform(5, 25)
                    }
                
                result = {
                    'timestamp': int(time.time()),
                    'cpu_usage': round(metrics['cpu_usage'], 2),
                    'memory_usage': round(metrics['memory_usage'], 2),
                    'disk_usage': round(metrics['disk_usage'], 2),
                    'network_usage': round(metrics['network_usage'], 2)
                }
            else:
                # 서버를 찾을 수 없는 경우
                result = {
                    'timestamp': int(time.time()),
                    'cpu_usage': 0,
                    'memory_usage': 0,
                    'disk_usage': 0,
                    'network_usage': 0
                }
        
        return jsonify({
            'success': True,
            'data': result
        })
        
    except Exception as e:
        print(f"실시간 메트릭 생성 오류: {e}")
        # 오류 시 기본 메트릭 반환
        return jsonify({
            'success': True,
            'data': {
                'cpu_usage': 0,
                'memory_usage': 0,
                'disk_usage': 0,
                'network_usage': 0,
                'timestamp': int(time.time())
            }
        })

@bp.route('/chart-data', methods=['GET'])
@login_required
def get_chart_data():
    """차트용 시계열 데이터 반환"""
    try:
        server_ip = request.args.get('server', 'all')
        metric_type = request.args.get('type', 'cpu')
        data_points = request.args.get('points', 20, type=int)
        
        # 시계열 데이터 생성 (실제 환경에서는 Prometheus에서 가져옴)
        chart_data = []
        current_time = int(time.time())
        
        for i in range(data_points):
            timestamp = current_time - (data_points - i - 1) * 5  # 5초 간격
            if server_ip == 'all':
                # 전체 서버 평균
                value = random.uniform(20, 70)  # 실제로는 계산된 값
            else:
                # 특정 서버
                value = random.uniform(15, 80)  # 실제로는 해당 서버 값
            
            chart_data.append({
                'timestamp': timestamp,
                'value': round(value, 2)
            })
        
        return jsonify({
            'success': True,
            'data': {
                'server': server_ip,
                'metric_type': metric_type,
                'data_points': data_points,
                'series': chart_data
            }
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
                'embed_url': 'http://localhost:3000/d-solo/system_monitoring?orgId=1&theme=light&kiosk=tv'
            }
            return jsonify({
                'success': True,
                'data': default_info
            })
            
    except Exception as e:
        print(f"Grafana 대시보드 정보 조회 오류: {e}")
        return jsonify({'error': str(e)}), 500

def get_dashboard_info():
    """대시보드 정보 파일에서 정보 읽기"""
    try:
        import json
        import os
        
        dashboard_file = '/tmp/dashboard_info.json'
        if os.path.exists(dashboard_file):
            with open(dashboard_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            # Grafana URL과 대시보드 정보 반환
            return {
                'dashboard_id': data.get('dashboard_id'),
                'dashboard_uid': data.get('dashboard_uid'),
                'dashboard_url': data.get('dashboard_url'),
                'grafana_url': 'http://localhost:3000',  # 설정에서 가져올 수도 있음
                'embed_url': f"http://localhost:3000/d-solo/{data.get('dashboard_uid')}?orgId=1&theme=light&panelId=1"
            }
        
        return None
        
    except Exception as e:
        print(f"대시보드 정보 읽기 오류: {e}")
        return None

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
    """Grafana 대시보드 임베드 URL 생성"""
    try:
        base_url = dashboard_info['grafana_url']
        dashboard_uid = dashboard_info['dashboard_uid']
        
        # 기본 임베드 URL
        embed_url = f"{base_url}/d-solo/{dashboard_uid}?orgId=1&theme=light"
        
        # 서버 선택이 'all'이 아닌 경우 필터 추가
        if selected_server != 'all':
            embed_url += f"&var-server={selected_server}"
        
        # 추가 옵션
        embed_url += "&kiosk=tv&autofitpanels"
        
        return embed_url
        
    except Exception as e:
        print(f"임베드 URL 생성 오류: {e}")
        return dashboard_info.get('dashboard_url', '')

def get_actual_servers():
    """실제 DB에서 서버 목록 가져오기"""
    try:
        # 데이터베이스 연결 상태 확인
        try:
            # SQLAlchemy 2.0 호환 방식으로 DB 연결 테스트
            db.session.execute(text('SELECT 1'))
        except Exception as db_error:
            print(f"데이터베이스 연결 오류: {db_error}")
            return []
        
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
            return []
        
    except Exception as e:
        print(f"서버 목록 조회 오류: {e}")
        # 오류 발생 시 빈 리스트 반환
        return []

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

def generate_sample_metrics(server_ip):
    """샘플 메트릭 생성 (실제 환경에서는 실제 메트릭 수집)"""
    return {
        'cpu_usage': round(random.uniform(10, 85), 2),
        'memory_usage': round(random.uniform(20, 90), 2),
        'disk_usage': round(random.uniform(15, 75), 2),
        'network_usage': round(random.uniform(5, 60), 2),
        'status': 'healthy',  # 실제로는 서버 상태 확인 결과
        'timestamp': int(time.time())
    }

def get_server_status(server_ip):
    """서버 상태 반환 (하위 호환성)"""
    return 'healthy'  # 실제로는 서버별 상태 확인 결과
