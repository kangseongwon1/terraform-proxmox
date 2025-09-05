"""
하이브리드 설정 로더
.env 파일과 config 파일을 모두 지원하는 설정 관리 시스템
"""
import os
import configparser
from typing import Dict, Any, Optional
from flask import current_app

class HybridConfigLoader:
    """하이브리드 설정 로더 - .env와 config 파일 모두 지원"""
    
    def __init__(self, config_file: str = 'monitoring_config.conf'):
        self.config_file = config_file
        self.config = configparser.ConfigParser()
        self.load_config()
    
    def load_config(self) -> None:
        """설정 로드 (.env 우선, config 파일 fallback)"""
        try:
            # 1. .env 파일에서 환경 변수 로드
            self._load_from_env()
            
            # 2. config 파일이 있으면 추가 로드 (환경 변수가 없는 경우만)
            if os.path.exists(self.config_file):
                self.config.read(self.config_file, encoding='utf-8')
                print(f"✅ 설정 파일 로드 완료: {self.config_file}")
            else:
                print(f"⚠️ 설정 파일이 없습니다: {self.config_file}")
                self._create_default_config()
                
        except Exception as e:
            print(f"❌ 설정 로드 오류: {e}")
            self._create_default_config()
    
    def _load_from_env(self) -> None:
        """환경 변수에서 설정 로드"""
        try:
            # Flask 앱 컨텍스트에서 환경 변수 가져오기
            if current_app:
                env_vars = dict(current_app.config)
            else:
                env_vars = dict(os.environ)
            
            # 환경 변수를 config 구조로 변환
            self._env_to_config(env_vars)
            print("✅ 환경 변수에서 설정 로드 완료")
            
        except Exception as e:
            print(f"⚠️ 환경 변수 로드 실패: {e}")
    
    def _env_to_config(self, env_vars: Dict[str, str]) -> None:
        """환경 변수를 config 구조로 변환"""
        # 섹션별 매핑
        section_mappings = {
            'GRAFANA': ['GRAFANA_URL', 'GRAFANA_USERNAME', 'GRAFANA_PASSWORD', 'GRAFANA_ORG_ID', 
                       'GRAFANA_DASHBOARD_UID', 'GRAFANA_ANONYMOUS_ACCESS', 'GRAFANA_AUTO_REFRESH'],
            'PROMETHEUS': ['PROMETHEUS_URL', 'PROMETHEUS_USERNAME', 'PROMETHEUS_PASSWORD'],
            'MONITORING': ['MONITORING_DEFAULT_TIME_RANGE', 'MONITORING_HEALTH_CHECK_INTERVAL', 
                          'MONITORING_PING_TIMEOUT', 'MONITORING_SSH_TIMEOUT', 'NODE_EXPORTER_AUTO_INSTALL',
                          'NODE_EXPORTER_PORT', 'NODE_EXPORTER_VERSION'],
            'ALERTS': ['ALERTS_ENABLED', 'ALERTS_EMAIL', 'ALERTS_CPU_WARNING_THRESHOLD', 
                      'ALERTS_CPU_CRITICAL_THRESHOLD', 'ALERTS_MEMORY_WARNING_THRESHOLD', 
                      'ALERTS_MEMORY_CRITICAL_THRESHOLD'],
            'SECURITY': ['SECURITY_ENABLE_HTTPS', 'SECURITY_ENABLE_AUTH', 'SECURITY_SESSION_TIMEOUT', 
                        'SECURITY_MAX_LOGIN_ATTEMPTS']
        }
        
        for section, env_keys in section_mappings.items():
            if section not in self.config:
                self.config[section] = {}
            
            for env_key in env_keys:
                if env_key in env_vars:
                    # 환경 변수명을 config 키로 변환 (GRAFANA_URL -> grafana_url)
                    config_key = env_key.lower().replace(section.lower() + '_', '')
                    self.config[section][config_key] = env_vars[env_key]
    
    def _create_default_config(self) -> None:
        """기본 설정 생성"""
        self.config['GRAFANA'] = {
            'grafana_url': 'http://localhost:3000',
            'grafana_username': 'admin',
            'grafana_password': 'admin',
            'org_id': '1',
            'dashboard_uid': 'system_monitoring',
            'anonymous_access': 'false',
            'auto_refresh': '5s'
        }
        
        self.config['PROMETHEUS'] = {
            'prometheus_url': 'http://localhost:9090',
            'prometheus_username': '',
            'prometheus_password': ''
        }
        
        self.config['MONITORING'] = {
            'default_time_range': '1h',
            'health_check_interval': '30s',
            'ping_timeout': '5s',
            'ssh_timeout': '10s',
            'auto_install_node_exporter': 'true',
            'node_exporter_port': '9100',
            'node_exporter_version': '1.6.1'
        }
        
        self.config['ALERTS'] = {
            'enable_alerts': 'true',
            'alert_email': 'admin@example.com',
            'cpu_warning_threshold': '80',
            'cpu_critical_threshold': '95',
            'memory_warning_threshold': '85',
            'memory_critical_threshold': '95'
        }
        
        self.config['SECURITY'] = {
            'enable_https': 'false',
            'enable_auth': 'true',
            'session_timeout': '3600',
            'max_login_attempts': '5'
        }
    
    def get_grafana_config(self) -> Dict[str, Any]:
        """Grafana 설정 반환"""
        return {
            'base_url': self.config.get('GRAFANA', 'grafana_url', fallback='http://localhost:3000'),
            'username': self.config.get('GRAFANA', 'grafana_username', fallback='admin'),
            'password': self.config.get('GRAFANA', 'grafana_password', fallback='admin'),
            'org_id': self.config.get('GRAFANA', 'org_id', fallback='1'),
            'dashboard_uid': self.config.get('GRAFANA', 'dashboard_uid', fallback='system_monitoring'),
            'anonymous_access': self.config.getboolean('GRAFANA', 'anonymous_access', fallback=False),
            'auto_refresh': self.config.get('GRAFANA', 'auto_refresh', fallback='5s')
        }
    
    def get_prometheus_config(self) -> Dict[str, Any]:
        """Prometheus 설정 반환"""
        return {
            'url': self.config.get('PROMETHEUS', 'prometheus_url', fallback='http://localhost:9090'),
            'username': self.config.get('PROMETHEUS', 'prometheus_username', fallback=''),
            'password': self.config.get('PROMETHEUS', 'prometheus_password', fallback='')
        }
    
    def get_monitoring_config(self) -> Dict[str, Any]:
        """모니터링 설정 반환"""
        return {
            'default_time_range': self.config.get('MONITORING', 'default_time_range', fallback='1h'),
            'health_check_interval': self.config.get('MONITORING', 'health_check_interval', fallback='30s'),
            'ping_timeout': self.config.get('MONITORING', 'ping_timeout', fallback='5s'),
            'ssh_timeout': self.config.get('MONITORING', 'ssh_timeout', fallback='10s'),
            'auto_install_node_exporter': self.config.getboolean('MONITORING', 'auto_install_node_exporter', fallback=True),
            'node_exporter_port': self.config.getint('MONITORING', 'node_exporter_port', fallback=9100),
            'node_exporter_version': self.config.get('MONITORING', 'node_exporter_version', fallback='1.6.1')
        }
    
    def get_alerts_config(self) -> Dict[str, Any]:
        """알림 설정 반환"""
        return {
            'enable_alerts': self.config.getboolean('ALERTS', 'enable_alerts', fallback=True),
            'alert_email': self.config.get('ALERTS', 'alert_email', fallback='admin@example.com'),
            'cpu_warning_threshold': self.config.getfloat('ALERTS', 'cpu_warning_threshold', fallback=80.0),
            'cpu_critical_threshold': self.config.getfloat('ALERTS', 'cpu_critical_threshold', fallback=95.0),
            'memory_warning_threshold': self.config.getfloat('ALERTS', 'memory_warning_threshold', fallback=85.0),
            'memory_critical_threshold': self.config.getfloat('ALERTS', 'memory_critical_threshold', fallback=95.0)
        }
    
    def get_security_config(self) -> Dict[str, Any]:
        """보안 설정 반환"""
        return {
            'enable_https': self.config.getboolean('SECURITY', 'enable_https', fallback=False),
            'enable_auth': self.config.getboolean('SECURITY', 'enable_auth', fallback=True),
            'session_timeout': self.config.getint('SECURITY', 'session_timeout', fallback=3600),
            'max_login_attempts': self.config.getint('SECURITY', 'max_login_attempts', fallback=5)
        }
    
    def get_all_config(self) -> Dict[str, Any]:
        """모든 설정 반환"""
        return {
            'grafana': self.get_grafana_config(),
            'prometheus': self.get_prometheus_config(),
            'monitoring': self.get_monitoring_config(),
            'alerts': self.get_alerts_config(),
            'security': self.get_security_config()
        }
    
    def save_config(self) -> None:
        """설정 파일 저장"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                self.config.write(f)
            print(f"✅ 설정 파일 저장 완료: {self.config_file}")
        except Exception as e:
            print(f"❌ 설정 파일 저장 오류: {e}")
    
    def export_to_env(self, env_file: str = '.env') -> None:
        """현재 설정을 .env 파일로 내보내기"""
        try:
            with open(env_file, 'w', encoding='utf-8') as f:
                f.write("# 모니터링 시스템 환경 변수\n")
                f.write("# 자동 생성됨\n\n")
                
                # 섹션별로 환경 변수 생성
                for section_name, section in self.config.items():
                    f.write(f"# {section_name} 설정\n")
                    for key, value in section.items():
                        env_key = f"{section_name.upper()}_{key.upper()}"
                        f.write(f"{env_key}={value}\n")
                    f.write("\n")
            
            print(f"✅ 환경 변수 파일 생성 완료: {env_file}")
        except Exception as e:
            print(f"❌ 환경 변수 파일 생성 오류: {e}")

# 전역 설정 인스턴스
hybrid_config = HybridConfigLoader()

def get_hybrid_config() -> HybridConfigLoader:
    """하이브리드 설정 인스턴스 반환"""
    return hybrid_config
