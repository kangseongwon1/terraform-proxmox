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
            
            # 설정 파일에 쓰기 (권한 문제 해결)
            if self._write_config_file(config):
                print(f"✅ Prometheus 설정 파일 업데이트 완료: {self.prometheus_config_path}")
            else:
                raise Exception("설정 파일 쓰기 실패")
            
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
                
                # 설정 파일에 쓰기 (권한 문제 해결)
                if not self._write_config_file(config):
                    raise Exception("설정 파일 쓰기 실패")
                
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
                        
                        # 설정 파일에 쓰기 (권한 문제 해결)
                        if not self._write_config_file(config):
                            raise Exception("설정 파일 쓰기 실패")
                        
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
    
    def _check_sudo_permissions(self) -> bool:
        """sudo 권한 확인"""
        try:
            # sudo 명령어 존재 확인
            result = subprocess.run(['which', 'sudo'], capture_output=True, text=True)
            if result.returncode != 0:
                print("❌ sudo 명령어가 설치되지 않았습니다")
                return False
            
            # sudo 권한 테스트
            test_result = subprocess.run(['sudo', '-n', 'true'], capture_output=True, text=True)
            if test_result.returncode == 0:
                print("✅ sudo 권한이 설정되어 있습니다")
                return True
            else:
                print("⚠️ sudo 권한이 설정되어 있지 않습니다")
                return False
                
        except Exception as e:
            print(f"❌ sudo 권한 확인 실패: {e}")
            return False

    def _write_config_file(self, config: Dict[str, Any]) -> bool:
        """Prometheus 설정 파일에 쓰기 (권한 문제 해결)"""
        try:
            if os.name == 'nt':  # Windows
                # Windows에서는 직접 쓰기
                with open(self.prometheus_config_path, 'w') as f:
                    yaml.dump(config, f, default_flow_style=False, sort_keys=False)
                return True
            else:  # Linux/Unix
                # Linux에서는 임시 파일 생성 후 sudo로 이동
                temp_config_path = f"/tmp/prometheus_config_{os.getpid()}.yml"
                
                # 임시 파일에 설정 쓰기
                with open(temp_config_path, 'w') as f:
                    yaml.dump(config, f, default_flow_style=False, sort_keys=False)
                
                # sudo 권한 확인
                if not self._check_sudo_permissions():
                    print("🔧 sudo 권한이 없으므로 대안 방법을 시도합니다")
                    
                    try:
                        # 직접 파일 복사 시도
                        import shutil
                        shutil.copy2(temp_config_path, self.prometheus_config_path)
                        os.remove(temp_config_path)
                        print("✅ 대안 방법으로 파일 복사 성공")
                        return True
                    except Exception as copy_error:
                        print(f"❌ 대안 방법도 실패: {copy_error}")
                        raise Exception(f"sudo 권한이 필요하며 대안 방법도 실패했습니다: {copy_error}")
                
                # sudo로 임시 파일을 실제 위치로 이동
                try:
                    # sudo 명령어 실행
                    mv_result = subprocess.run([
                        'sudo', 'mv', temp_config_path, self.prometheus_config_path
                    ], capture_output=True, text=True, check=True)
                    
                    # 파일 소유자를 prometheus로 변경
                    chown_result = subprocess.run([
                        'sudo', 'chown', 'prometheus:prometheus', self.prometheus_config_path
                    ], capture_output=True, text=True, check=True)
                    
                    return True
                    
                except subprocess.CalledProcessError as e:
                    # sudo 실패 시 임시 파일 정리
                    if os.path.exists(temp_config_path):
                        os.remove(temp_config_path)
                    
                    # sudo 권한 문제인 경우 대안 방법 시도
                    print(f"⚠️ sudo 권한 문제 감지: {e.stderr}")
                    print("🔧 대안 방법 시도: 직접 파일 복사")
                    
                    try:
                        # 직접 파일 복사 시도
                        import shutil
                        shutil.copy2(temp_config_path, self.prometheus_config_path)
                        os.remove(temp_config_path)
                        print("✅ 대안 방법으로 파일 복사 성공")
                        return True
                    except Exception as copy_error:
                        print(f"❌ 대안 방법도 실패: {copy_error}")
                        raise Exception(f"sudo 권한이 필요하며 대안 방법도 실패했습니다: {e.stderr}")
                    
        except Exception as e:
            print(f"❌ 설정 파일 쓰기 실패: {e}")
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
