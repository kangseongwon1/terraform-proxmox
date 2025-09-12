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
    
    def get_manual_setup_instructions(self) -> str:
        """수동 설정 안내 메시지 생성"""
        return f"""
🔧 Prometheus 수동 설정 안내:

1. sudo 권한 설정:
   sudo visudo
   # 다음 줄 추가: username ALL=(ALL) NOPASSWD: /bin/mv, /bin/chown

2. 또는 수동으로 설정 파일 복사:
   sudo cp /tmp/prometheus_config_*.yml /etc/prometheus/prometheus.yml
   sudo chown prometheus:prometheus /etc/prometheus/prometheus.yml
   sudo systemctl restart prometheus

3. Prometheus 서비스 상태 확인:
   sudo systemctl status prometheus
   curl http://localhost:9090/targets
"""

    def _check_file_permissions(self) -> Dict[str, Any]:
        """Prometheus 설정 파일 권한 확인"""
        try:
            if not os.path.exists(self.prometheus_config_path):
                return {
                    'exists': False,
                    'readable': False,
                    'writable': False,
                    'owner': None,
                    'permissions': None
                }
            
            # 파일 정보 수집
            stat_info = os.stat(self.prometheus_config_path)
            
            # 권한 확인
            readable = os.access(self.prometheus_config_path, os.R_OK)
            writable = os.access(self.prometheus_config_path, os.W_OK)
            
            # 소유자 정보 (가능한 경우)
            owner = None
            try:
                import pwd
                owner = pwd.getpwuid(stat_info.st_uid).pw_name
            except (ImportError, KeyError):
                owner = f"UID:{stat_info.st_uid}"
            
            return {
                'exists': True,
                'readable': readable,
                'writable': writable,
                'owner': owner,
                'permissions': oct(stat_info.st_mode),
                'uid': stat_info.st_uid,
                'gid': stat_info.st_gid
            }
            
        except Exception as e:
            print(f"❌ 파일 권한 확인 실패: {e}")
            return {
                'exists': False,
                'readable': False,
                'writable': False,
                'owner': None,
                'permissions': None,
                'error': str(e)
            }

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
                # 파일 권한 확인
                file_perms = self._check_file_permissions()
                print(f"🔧 파일 권한 확인: {file_perms}")
                
                # 방법 1: 직접 파일 수정 시도
                try:
                    print("🔧 직접 파일 수정 시도...")
                    with open(self.prometheus_config_path, 'w') as f:
                        yaml.dump(config, f, default_flow_style=False, sort_keys=False)
                    print("✅ 직접 파일 수정 성공")
                    return True
                except PermissionError as perm_error:
                    print(f"⚠️ 직접 파일 수정 실패 (권한 부족): {perm_error}")
                    print(f"📋 파일 소유자: {file_perms.get('owner', 'unknown')}")
                    print(f"📋 파일 권한: {file_perms.get('permissions', 'unknown')}")
                    print(f"📋 쓰기 권한: {file_perms.get('writable', False)}")
                    
                    # 방법 2: 임시 파일 생성 후 sudo로 이동
                    temp_config_path = f"/tmp/prometheus_config_{os.getpid()}.yml"
                    
                    # 임시 파일에 설정 쓰기
                    with open(temp_config_path, 'w') as f:
                        yaml.dump(config, f, default_flow_style=False, sort_keys=False)
                    
                    # sudo 권한 확인
                    if not self._check_sudo_permissions():
                        print("🔧 sudo 권한이 없으므로 수동 설정 안내를 제공합니다")
                        
                        # 수동 설정 안내
                        print("🔧 수동 설정 안내:")
                        print(f"1. 임시 파일을 수동으로 복사하세요:")
                        print(f"   sudo cp {temp_config_path} {self.prometheus_config_path}")
                        print(f"2. 파일 소유자를 변경하세요:")
                        print(f"   sudo chown prometheus:prometheus {self.prometheus_config_path}")
                        print(f"3. Prometheus 서비스를 재시작하세요:")
                        print(f"   sudo systemctl restart prometheus")
                        print(f"4. 임시 파일을 정리하세요:")
                        print(f"   rm {temp_config_path}")
                        
                        # 임시 파일 경로를 반환하여 사용자가 수동으로 처리할 수 있도록 함
                        raise Exception(f"sudo 권한이 필요합니다. 수동 설정을 위해 임시 파일이 생성되었습니다: {temp_config_path}")
                    
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
                        
                        print("✅ sudo를 통한 파일 이동 성공")
                        return True
                        
                    except subprocess.CalledProcessError as e:
                        # sudo 실패 시 임시 파일 정리
                        if os.path.exists(temp_config_path):
                            os.remove(temp_config_path)
                        raise Exception(f"sudo 권한이 필요합니다: {e.stderr}")
                    
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
            
            # 방법 1: systemctl reload 시도 (권한 확인)
            try:
                print("🔧 systemctl reload 시도...")
                result = subprocess.run(
                    ['systemctl', 'reload', 'prometheus'],
                    capture_output=True,
                    text=True
                )
                
                if result.returncode == 0:
                    print("✅ systemctl reload 성공")
                    return True
                else:
                    print(f"⚠️ systemctl reload 실패: {result.stderr}")
            except Exception as reload_error:
                print(f"⚠️ systemctl reload 오류: {reload_error}")
            
            # 방법 2: sudo systemctl reload 시도
            try:
                print("🔧 sudo systemctl reload 시도...")
                result = subprocess.run(
                    ['sudo', 'systemctl', 'reload', 'prometheus'],
                    capture_output=True,
                    text=True
                )
                
                if result.returncode == 0:
                    print("✅ sudo systemctl reload 성공")
                    return True
                else:
                    print(f"⚠️ sudo systemctl reload 실패: {result.stderr}")
            except Exception as sudo_error:
                print(f"⚠️ sudo systemctl reload 오류: {sudo_error}")
            
            # 방법 3: sudo systemctl restart 시도
            try:
                print("🔧 sudo systemctl restart 시도...")
                result = subprocess.run(
                    ['sudo', 'systemctl', 'restart', 'prometheus'],
                    capture_output=True,
                    text=True
                )
                
                if result.returncode == 0:
                    print("✅ sudo systemctl restart 성공")
                    return True
                else:
                    print(f"❌ sudo systemctl restart 실패: {result.stderr}")
            except Exception as restart_error:
                print(f"❌ sudo systemctl restart 오류: {restart_error}")
            
            # 방법 4: 수동 재시작 안내
            print("🔧 수동 재시작 안내:")
            print("   sudo systemctl restart prometheus")
            print("   또는")
            print("   sudo systemctl reload prometheus")
            
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
