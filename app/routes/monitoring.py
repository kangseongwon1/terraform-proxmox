"""
모니터링 관련 라우트
"""
from flask import Blueprint, jsonify, request, render_template
from flask_login import login_required
import requests
import json
from datetime import datetime, timedelta

bp = Blueprint('monitoring', __name__, url_prefix='/monitoring')

# 프로메테우스 설정 (개발 서버용)
PROMETHEUS_URL = "http://192.168.0.1:9090"  # 개발 서버 IP로 변경 필요

@bp.route('/content', methods=['GET'])
@login_required
def monitoring_content():
    """모니터링 페이지 컨텐츠"""
    return render_template('partials/monitoring_content.html')

@bp.route('/metrics/<server_ip>', methods=['GET'])
@login_required
def get_server_metrics(server_ip):
    """특정 서버의 메트릭 조회"""
    try:
        # 시간 범위 설정 (기본: 1시간)
        hours = request.args.get('hours', 1, type=int)
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=hours)
        
        # PromQL 쿼리들
        queries = {
            'cpu_usage': f'100 - (avg by (instance) (irate(node_cpu_seconds_total{{mode="idle",instance="{server_ip}:9100"}}[5m])) * 100)',
            'memory_usage': f'100 - (node_memory_MemAvailable_bytes{{instance="{server_ip}:9100"}} / node_memory_MemTotal_bytes{{instance="{server_ip}:9100"}} * 100)',
            'disk_usage': f'100 - (node_filesystem_avail_bytes{{instance="{server_ip}:9100",fstype!="tmpfs"}} / node_filesystem_size_bytes{{instance="{server_ip}:9100",fstype!="tmpfs"}} * 100)',
            'network_in': f'irate(node_network_receive_bytes_total{{instance="{server_ip}:9100"}}[5m])',
            'network_out': f'irate(node_network_transmit_bytes_total{{instance="{server_ip}:9100"}}[5m])'
        }
        
        metrics = {}
        
        for metric_name, query in queries.items():
            try:
                # 프로메테우스 API 호출
                response = requests.get(f"{PROMETHEUS_URL}/api/v1/query_range", params={
                    'query': query,
                    'start': start_time.isoformat() + 'Z',
                    'end': end_time.isoformat() + 'Z',
                    'step': '60s'  # 1분 간격
                })
                
                if response.status_code == 200:
                    data = response.json()
                    if data['status'] == 'success' and data['data']['result']:
                        result = data['data']['result'][0]
                        # 시계열 데이터를 간단한 형태로 변환
                        values = result['values']
                        if values:
                            # 최신 값과 평균값 계산
                            latest = float(values[-1][1])
                            avg = sum(float(v[1]) for v in values) / len(values)
                            
                            metrics[metric_name] = {
                                'latest': round(latest, 2),
                                'average': round(avg, 2),
                                'values': [(v[0], float(v[1])) for v in values[-10:]]  # 최근 10개 값
                            }
                        else:
                            metrics[metric_name] = {'error': '데이터 없음'}
                    else:
                        metrics[metric_name] = {'error': '쿼리 실패'}
                else:
                    metrics[metric_name] = {'error': f'HTTP {response.status_code}'}
                    
            except Exception as e:
                metrics[metric_name] = {'error': str(e)}
        
        return jsonify({
            'success': True,
            'server_ip': server_ip,
            'time_range': f'{hours}시간',
            'metrics': metrics
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/servers/overview', methods=['GET'])
@login_required
def get_servers_overview():
    """모든 서버의 개요 메트릭"""
    try:
        # 서버 목록 (하드코딩된 IP, 나중에 DB에서 가져오도록 수정)
        servers = ['192.168.0.10', '192.168.0.11']
        
        overview = {}
        
        for server_ip in servers:
            try:
                # 간단한 상태 확인
                response = requests.get(f"{PROMETHEUS_URL}/api/v1/query", params={
                    'query': f'up{{instance="{server_ip}:9100"}}'
                })
                
                if response.status_code == 200:
                    data = response.json()
                    if data['status'] == 'success' and data['data']['result']:
                        is_up = data['data']['result'][0]['value'][1] == '1'
                        
                        if is_up:
                            # 기본 메트릭 조회
                            cpu_query = f'100 - (avg by (instance) (irate(node_cpu_seconds_total{{mode="idle",instance="{server_ip}:9100"}}[5m])) * 100)'
                            mem_query = f'100 - (node_memory_MemAvailable_bytes{{instance="{server_ip}:9100"}} / node_memory_MemTotal_bytes{{instance="{server_ip}:9100"}} * 100)'
                            
                            cpu_response = requests.get(f"{PROMETHEUS_URL}/api/v1/query", params={'query': cpu_query})
                            mem_response = requests.get(f"{PROMETHEUS_URL}/api/v1/query", params={'query': mem_query})
                            
                            cpu_usage = 0
                            mem_usage = 0
                            
                            if cpu_response.status_code == 200:
                                cpu_data = cpu_response.json()
                                if cpu_data['status'] == 'success' and cpu_data['data']['result']:
                                    cpu_usage = round(float(cpu_data['data']['result'][0]['value'][1]), 1)
                            
                            if mem_response.status_code == 200:
                                mem_data = mem_response.json()
                                if mem_data['status'] == 'success' and mem_data['data']['result']:
                                    mem_usage = round(float(mem_data['data']['result'][0]['value'][1]), 1)
                            
                            overview[server_ip] = {
                                'status': 'online',
                                'cpu_usage': cpu_usage,
                                'memory_usage': mem_usage,
                                'last_check': datetime.now().isoformat()
                            }
                        else:
                            overview[server_ip] = {
                                'status': 'offline',
                                'error': 'node-exporter 응답 없음'
                            }
                    else:
                        overview[server_ip] = {
                            'status': 'error',
                            'error': '프로메테우스 쿼리 실패'
                        }
                else:
                    overview[server_ip] = {
                        'status': 'error',
                        'error': f'프로메테우스 API 오류: {response.status_code}'
                    }
                    
            except Exception as e:
                overview[server_ip] = {
                    'status': 'error',
                    'error': str(e)
                }
        
        return jsonify({
            'success': True,
            'servers': overview,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/health', methods=['GET'])
@login_required
def check_monitoring_health():
    """모니터링 시스템 상태 확인"""
    try:
        # 프로메테우스 상태 확인
        prometheus_status = 'unknown'
        try:
            response = requests.get(f"{PROMETHEUS_URL}/api/v1/query", params={'query': 'up'})
            if response.status_code == 200:
                prometheus_status = 'healthy'
            else:
                prometheus_status = f'unhealthy (HTTP {response.status_code})'
        except Exception as e:
            prometheus_status = f'error: {str(e)}'
        
        return jsonify({
            'success': True,
            'monitoring_system': {
                'prometheus': prometheus_status,
                'timestamp': datetime.now().isoformat()
            }
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
