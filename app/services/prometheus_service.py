"""
Prometheus 서비스
"""
import yaml
import os
import subprocess
import logging
from typing import List, Dict, Any
from app.models.server import Server
from app import db

logger = logging.getLogger(__name__)

class PrometheusService:
    """Prometheus 서비스"""
    
    def __init__(self):
        # Windows 환경에서는 로컬 경로 사용, Linux에서는 시스템 경로 사용
        if os.name == 'nt':  # Windows
            self.prometheus_config_path = "prometheus.yml"
        else:  # Linux/Unix
            self.prometheus_config_path = "/etc/prometheus/prometheus.yml"
        self.node_exporter_port = 9100
        
    def update_prometheus_config(self, server_ips: List[str] = None) -> bool:
        """Prometheus 설정 파일 업데이트"""
        try:
            # 서버 IP 목록이 제공되지 않으면 DB에서 가져오기
            if server_ips is None:
                servers = Server.query.filter(Server.ip_address.isnot(None)).all()
                server_ips = []
                for server in servers:
                    if server.ip_address:
                        # IP 주소에서 첫 번째 IP 추출
                        first_ip = server.ip_address.split(',')[0].strip()
                        if first_ip and first_ip not in server_ips:
                            server_ips.append(first_ip)
            
            print(f"🔧 Prometheus 설정 업데이트: {len(server_ips)}개 서버")
            
            # Prometheus 설정 생성
            config = {
                'global': {
                    'scrape_interval': '15s',
                    'evaluation_interval': '15s'
                },
                'rule_files': [],
                'scrape_configs': [
                    {
                        'job_name': 'prometheus',
                        'static_configs': [
                            {'targets': ['localhost:9090']}
                        ]
                    }
                ]
            }
            
            # Node Exporter 타겟 추가
            if server_ips:
                node_exporter_targets = [f"{ip}:{self.node_exporter_port}" for ip in server_ips]
                config['scrape_configs'].append({
                    'job_name': 'node-exporter',
                    'scrape_interval': '10s',
                    'static_configs': [
                        {'targets': node_exporter_targets}
                    ],
                    'metrics_path': '/metrics'
                })
                
                print(f"🔧 Node Exporter 타겟 추가: {node_exporter_targets}")
            
            # 설정 파일에 쓰기
            with open(self.prometheus_config_path, 'w') as f:
                yaml.dump(config, f, default_flow_style=False, sort_keys=False)
            
            print(f"✅ Prometheus 설정 파일 업데이트 완료: {self.prometheus_config_path}")
            
            # Prometheus 서비스 재시작
            return self._restart_prometheus()
            
        except Exception as e:
            print(f"❌ Prometheus 설정 업데이트 실패: {e}")
            logger.error(f"Prometheus 설정 업데이트 실패: {e}")
            return False
    
    def add_server_to_prometheus(self, server_ip: str) -> bool:
        """새 서버를 Prometheus 설정에 추가"""
        try:
            print(f"🔧 Prometheus에 서버 추가: {server_ip}")
            
            # 현재 설정 파일 읽기
            if os.path.exists(self.prometheus_config_path):
                with open(self.prometheus_config_path, 'r') as f:
                    config = yaml.safe_load(f)
            else:
                # 기본 설정 생성
                config = {
                    'global': {
                        'scrape_interval': '15s',
                        'evaluation_interval': '15s'
                    },
                    'rule_files': [],
                    'scrape_configs': [
                        {
                            'job_name': 'prometheus',
                            'static_configs': [
                                {'targets': ['localhost:9090']}
                            ]
                        }
                    ]
                }
            
            # Node Exporter job 찾기 또는 생성
            node_exporter_job = None
            for job in config['scrape_configs']:
                if job['job_name'] == 'node-exporter':
                    node_exporter_job = job
                    break
            
            if not node_exporter_job:
                # Node Exporter job 생성
                node_exporter_job = {
                    'job_name': 'node-exporter',
                    'scrape_interval': '10s',
                    'static_configs': [
                        {'targets': []}
                    ],
                    'metrics_path': '/metrics'
                }
                config['scrape_configs'].append(node_exporter_job)
            
            # 새 타겟 추가
            new_target = f"{server_ip}:{self.node_exporter_port}"
            targets = node_exporter_job['static_configs'][0]['targets']
            
            if new_target not in targets:
                targets.append(new_target)
                print(f"🔧 Node Exporter 타겟 추가: {new_target}")
                
                # 설정 파일에 쓰기
                with open(self.prometheus_config_path, 'w') as f:
                    yaml.dump(config, f, default_flow_style=False, sort_keys=False)
                
                print(f"✅ Prometheus 설정에 서버 추가 완료: {server_ip}")
                
                # Prometheus 서비스 재시작
                return self._restart_prometheus()
            else:
                print(f"ℹ️ 서버가 이미 Prometheus 설정에 존재: {server_ip}")
                return True
                
        except Exception as e:
            print(f"❌ Prometheus에 서버 추가 실패: {e}")
            logger.error(f"Prometheus에 서버 추가 실패: {e}")
            return False
    
    def remove_server_from_prometheus(self, server_ip: str) -> bool:
        """서버를 Prometheus 설정에서 제거"""
        try:
            print(f"🔧 Prometheus에서 서버 제거: {server_ip}")
            
            # 현재 설정 파일 읽기
            if not os.path.exists(self.prometheus_config_path):
                print(f"⚠️ Prometheus 설정 파일이 없습니다: {self.prometheus_config_path}")
                return True
            
            with open(self.prometheus_config_path, 'r') as f:
                config = yaml.safe_load(f)
            
            # Node Exporter job에서 타겟 제거
            target_to_remove = f"{server_ip}:{self.node_exporter_port}"
            
            for job in config['scrape_configs']:
                if job['job_name'] == 'node-exporter':
                    targets = job['static_configs'][0]['targets']
                    if target_to_remove in targets:
                        targets.remove(target_to_remove)
                        print(f"🔧 Node Exporter 타겟 제거: {target_to_remove}")
                        
                        # 설정 파일에 쓰기
                        with open(self.prometheus_config_path, 'w') as f:
                            yaml.dump(config, f, default_flow_style=False, sort_keys=False)
                        
                        print(f"✅ Prometheus 설정에서 서버 제거 완료: {server_ip}")
                        
                        # Prometheus 서비스 재시작
                        return self._restart_prometheus()
                    break
            
            print(f"ℹ️ 서버가 Prometheus 설정에 존재하지 않음: {server_ip}")
            return True
                
        except Exception as e:
            print(f"❌ Prometheus에서 서버 제거 실패: {e}")
            logger.error(f"Prometheus에서 서버 제거 실패: {e}")
            return False
    
    def _restart_prometheus(self) -> bool:
        """Prometheus 서비스 재시작"""
        try:
            print("🔧 Prometheus 서비스 재시작 중...")
            
            # Windows 환경에서는 서비스 재시작 스킵
            if os.name == 'nt':
                print("ℹ️ Windows 환경에서는 Prometheus 서비스 재시작을 스킵합니다.")
                return True
            
            # Prometheus 설정 파일 검증
            result = subprocess.run(
                ['promtool', 'check', 'config', self.prometheus_config_path],
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                print(f"❌ Prometheus 설정 파일 검증 실패: {result.stderr}")
                return False
            
            # Prometheus 서비스 재시작
            result = subprocess.run(
                ['sudo', 'systemctl', 'reload', 'prometheus'],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                print("✅ Prometheus 서비스 재시작 완료")
                return True
            else:
                print(f"⚠️ Prometheus 서비스 재시작 실패, 강제 재시작 시도: {result.stderr}")
                
                # 강제 재시작 시도
                result = subprocess.run(
                    ['sudo', 'systemctl', 'restart', 'prometheus'],
                    capture_output=True,
                    text=True
                )
                
                if result.returncode == 0:
                    print("✅ Prometheus 서비스 강제 재시작 완료")
                    return True
                else:
                    print(f"❌ Prometheus 서비스 재시작 실패: {result.stderr}")
                    return False
                    
        except Exception as e:
            print(f"❌ Prometheus 서비스 재시작 중 오류: {e}")
            logger.error(f"Prometheus 서비스 재시작 중 오류: {e}")
            return False
    
    def get_prometheus_targets(self) -> List[str]:
        """현재 Prometheus 타겟 목록 조회"""
        try:
            if not os.path.exists(self.prometheus_config_path):
                return []
            
            with open(self.prometheus_config_path, 'r') as f:
                config = yaml.safe_load(f)
            
            targets = []
            for job in config.get('scrape_configs', []):
                if job['job_name'] == 'node-exporter':
                    for static_config in job.get('static_configs', []):
                        targets.extend(static_config.get('targets', []))
                    break
            
            return targets
            
        except Exception as e:
            print(f"❌ Prometheus 타겟 조회 실패: {e}")
            logger.error(f"Prometheus 타겟 조회 실패: {e}")
            return []
