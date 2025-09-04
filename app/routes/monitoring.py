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

bp = Blueprint('monitoring', __name__, url_prefix='/monitoring')

# 프로메테우스 설정 (개발 서버용)
PROMETHEUS_URL = "http://localhost:9090"  # 개발 서버 IP로 변경 필요

# 메트릭 캐시 (실제 환경에서는 Redis 등을 사용)
metrics_cache = {}
last_update = {}

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
            for server in servers:
                all_metrics[server['ip']] = generate_sample_metrics(server['ip'])
            
            # 평균값 계산
            if metric_type == 'all' or metric_type == 'cpu':
                cpu_avg = sum(m['cpu_usage'] for m in all_metrics.values()) / len(all_metrics)
            if metric_type == 'all' or metric_type == 'memory':
                memory_avg = sum(m['memory_usage'] for m in all_metrics.values()) / len(all_metrics)
            if metric_type == 'all' or metric_type == 'disk':
                disk_avg = sum(m['disk_usage'] for m in all_metrics.values()) / len(all_metrics)
            if metric_type == 'all' or metric_type == 'network':
                network_avg = sum(m['network_usage'] for m in all_metrics.values()) / len(all_metrics)
            
            result = {
                'timestamp': int(time.time()),
                'server': 'all',
                'metrics': {
                    'cpu_usage': round(cpu_avg, 2) if metric_type in ['all', 'cpu'] else None,
                    'memory_usage': round(memory_avg, 2) if metric_type in ['all', 'memory'] else None,
                    'disk_usage': round(disk_avg, 2) if metric_type in ['all', 'disk'] else None,
                    'network_usage': round(network_avg, 2) if metric_type in ['all', 'network'] else None
                }
            }
        else:
            # 특정 서버의 메트릭
            result = generate_sample_metrics(server_ip)
            result['server'] = server_ip
        
        return jsonify({
            'success': True,
            'data': result
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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

def get_actual_servers():
    """실제 DB에서 서버 목록 가져오기"""
    try:
        # DB에서 서버 목록 조회
        db_servers = Server.query.all()
        
        servers = []
        for server in db_servers:
            # 서버 상태 결정 (실제 환경에서는 ping 또는 SSH로 확인)
            status = determine_server_status(server)
            
            # IP 주소 처리 (리스트 형태일 수 있음)
            ip_address = '0.0.0.0'
            if server.ip_address:
                if isinstance(server.ip_address, list) and len(server.ip_address) > 0:
                    ip_address = server.ip_address[0]
                elif isinstance(server.ip_address, str):
                    ip_address = server.ip_address
            
            servers.append({
                'ip': ip_address,
                'port': '22',  # 기본 SSH 포트 (실제로는 서버별로 다를 수 있음)
                'status': status,
                'name': server.name,
                'role': server.role,
                'vmid': server.vmid
            })
        
        # DB에 서버가 없으면 샘플 데이터 사용
        if not servers:
            servers = [
                {'ip': '192.168.0.10', 'port': '22', 'status': 'healthy', 'name': 'dev-server-1', 'role': 'web', 'vmid': None},
                {'ip': '192.168.0.111', 'port': '20222', 'status': 'healthy', 'name': 'prod-server-1', 'role': 'web', 'vmid': None},
                {'ip': '192.168.0.112', 'port': '20222', 'status': 'warning', 'name': 'prod-server-2', 'role': 'db', 'vmid': None},
                {'ip': '192.168.0.113', 'port': '20222', 'status': 'healthy', 'name': 'prod-server-3', 'role': 'web', 'vmid': None},
                {'ip': '192.168.0.114', 'port': '20222', 'status': 'healthy', 'name': 'prod-server-4', 'role': 'web', 'vmid': None},
                {'ip': '192.168.0.115', 'port': '20222', 'status': 'healthy', 'name': 'prod-server-5', 'role': 'web', 'vmid': None},
                {'ip': '192.168.0.116', 'port': '20222', 'status': 'healthy', 'name': 'prod-server-6', 'role': 'web', 'vmid': None},
                {'ip': '192.168.0.117', 'port': '20222', 'status': 'critical', 'name': 'prod-server-7', 'role': 'db', 'vmid': None},
                {'ip': '192.168.0.118', 'port': '20222', 'status': 'healthy', 'name': 'prod-server-8', 'role': 'web', 'vmid': None},
                {'ip': '192.168.0.119', 'port': '20222', 'status': 'healthy', 'name': 'prod-server-9', 'role': 'web', 'vmid': None}
            ]
        
        return servers
        
    except Exception as e:
        print(f"서버 목록 조회 오류: {e}")
        # 오류 시 샘플 데이터 반환
        return [
            {'ip': '192.168.0.10', 'port': '22', 'status': 'healthy', 'name': 'dev-server-1', 'role': 'web', 'vmid': None},
            {'ip': '192.168.0.111', 'port': '20222', 'status': 'healthy', 'name': 'prod-server-1', 'role': 'web', 'vmid': None},
            {'ip': '192.168.0.112', 'port': '20222', 'status': 'warning', 'name': 'prod-server-2', 'role': 'db', 'vmid': None},
            {'ip': '192.168.0.113', 'port': '20222', 'status': 'healthy', 'name': 'prod-server-3', 'role': 'web', 'vmid': None},
            {'ip': '192.168.0.114', 'port': '20222', 'status': 'healthy', 'name': 'prod-server-4', 'role': 'web', 'vmid': None},
            {'ip': '192.168.0.115', 'port': '20222', 'status': 'healthy', 'name': 'prod-server-5', 'role': 'web', 'vmid': None},
            {'ip': '192.168.0.116', 'port': '20222', 'status': 'healthy', 'name': 'prod-server-6', 'role': 'web', 'vmid': None},
            {'ip': '192.168.0.117', 'port': '20222', 'status': 'critical', 'name': 'prod-server-7', 'role': 'db', 'vmid': None},
            {'ip': '192.168.0.118', 'port': '20222', 'status': 'healthy', 'name': 'prod-server-8', 'role': 'web', 'vmid': None},
            {'ip': '192.168.0.119', 'port': '20222', 'status': 'healthy', 'name': 'prod-server-9', 'role': 'web', 'vmid': None}
        ]

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
