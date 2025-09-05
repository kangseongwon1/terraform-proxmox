import os
from datetime import timedelta

class VaultConfig:
    """Vault 설정"""
    VAULT_ADDR = os.environ.get('VAULT_ADDR', 'http://127.0.0.1:8200')
    VAULT_TOKEN = os.environ.get('VAULT_TOKEN')
    
    @classmethod
    def get_secret(cls, secret_path, key):
        """Vault에서 시크릿 가져오기"""
        try:
            import hvac
            client = hvac.Client(url=cls.VAULT_ADDR, token=cls.VAULT_TOKEN)
            if client.is_authenticated():
                response = client.secrets.kv.v2.read_secret_version(path=secret_path)
                return response['data']['data'].get(key)
            else:
                raise ValueError("Vault 인증 실패")
        except ImportError:
            # hvac 패키지가 없으면 환경 변수에서 가져오기
            return os.environ.get(f'TF_VAR_{key.upper()}')
        except Exception as e:
            print(f"Vault에서 시크릿 가져오기 실패: {e}")
            # 폴백: 환경 변수에서 가져오기
            return os.environ.get(f'TF_VAR_{key.upper()}')


class Config:
    """기본 설정"""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    DEBUG = os.environ.get('DEBUG', 'True').lower() == 'true'
    
    # SQLAlchemy 설정
    basedir = os.path.abspath(os.path.dirname(__file__))
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', f'sqlite:///{os.path.join(basedir, "instance", "proxmox_manager.db")}')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Proxmox 설정 (환경 변수 필수)
    PROXMOX_ENDPOINT = os.environ.get('PROXMOX_ENDPOINT', 'https://localhost:8006')
    PROXMOX_USERNAME = os.environ.get('PROXMOX_USERNAME', 'root@pam')
    PROXMOX_PASSWORD = os.environ.get('PROXMOX_PASSWORD', 'password')
    PROXMOX_NODE = os.environ.get('PROXMOX_NODE', 'pve')
    PROXMOX_DATASTORE = os.environ.get('PROXMOX_DATASTORE', 'local-lvm')
    
    # 세션 보안 설정
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'False').lower() == 'true'
    SESSION_COOKIE_HTTPONLY = os.environ.get('SESSION_COOKIE_HTTPONLY', 'True').lower() == 'true'
    SESSION_COOKIE_SAMESITE = os.environ.get('SESSION_COOKIE_SAMESITE', 'Strict')
    PERMANENT_SESSION_LIFETIME = timedelta(
        seconds=int(os.environ.get('PERMANENT_SESSION_LIFETIME', 28800))  # 8시간으로 연장
    )
    
    # 로깅 설정
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_FILE = os.environ.get('LOG_FILE', 'app.log')
    
    # SSH 설정
    SSH_PRIVATE_KEY_PATH = os.environ.get('SSH_PRIVATE_KEY_PATH', '~/.ssh/id_rsa')
    SSH_PUBLIC_KEY_PATH = os.environ.get('SSH_PUBLIC_KEY_PATH', '~/.ssh/id_rsa.pub')
    SSH_USER = os.environ.get('SSH_USER', 'rocky')
    
    # 모니터링 설정 (환경 변수)
    GRAFANA_URL = os.environ.get('GRAFANA_URL', 'http://localhost:3000')
    GRAFANA_USERNAME = os.environ.get('GRAFANA_USERNAME', 'admin')
    GRAFANA_PASSWORD = os.environ.get('GRAFANA_PASSWORD', 'admin')
    GRAFANA_ORG_ID = os.environ.get('GRAFANA_ORG_ID', '1')
    GRAFANA_DASHBOARD_UID = os.environ.get('GRAFANA_DASHBOARD_UID', 'system_monitoring')
    GRAFANA_ANONYMOUS_ACCESS = os.environ.get('GRAFANA_ANONYMOUS_ACCESS', 'false').lower() == 'true'
    GRAFANA_AUTO_REFRESH = os.environ.get('GRAFANA_AUTO_REFRESH', '5s')
    
    PROMETHEUS_URL = os.environ.get('PROMETHEUS_URL', 'http://localhost:9090')
    PROMETHEUS_USERNAME = os.environ.get('PROMETHEUS_USERNAME', '')
    PROMETHEUS_PASSWORD = os.environ.get('PROMETHEUS_PASSWORD', '')
    
    NODE_EXPORTER_AUTO_INSTALL = os.environ.get('NODE_EXPORTER_AUTO_INSTALL', 'true').lower() == 'true'
    NODE_EXPORTER_PORT = int(os.environ.get('NODE_EXPORTER_PORT', '9100'))
    NODE_EXPORTER_VERSION = os.environ.get('NODE_EXPORTER_VERSION', '1.6.1')
    
    MONITORING_DEFAULT_TIME_RANGE = os.environ.get('MONITORING_DEFAULT_TIME_RANGE', '1h')
    MONITORING_HEALTH_CHECK_INTERVAL = os.environ.get('MONITORING_HEALTH_CHECK_INTERVAL', '30s')
    MONITORING_PING_TIMEOUT = os.environ.get('MONITORING_PING_TIMEOUT', '5s')
    MONITORING_SSH_TIMEOUT = os.environ.get('MONITORING_SSH_TIMEOUT', '10s')
    
    ALERTS_ENABLED = os.environ.get('ALERTS_ENABLED', 'true').lower() == 'true'
    ALERTS_EMAIL = os.environ.get('ALERTS_EMAIL', 'admin@example.com')
    ALERTS_CPU_WARNING_THRESHOLD = float(os.environ.get('ALERTS_CPU_WARNING_THRESHOLD', '80'))
    ALERTS_CPU_CRITICAL_THRESHOLD = float(os.environ.get('ALERTS_CPU_CRITICAL_THRESHOLD', '95'))
    ALERTS_MEMORY_WARNING_THRESHOLD = float(os.environ.get('ALERTS_MEMORY_WARNING_THRESHOLD', '85'))
    ALERTS_MEMORY_CRITICAL_THRESHOLD = float(os.environ.get('ALERTS_MEMORY_CRITICAL_THRESHOLD', '95'))
    
    SECURITY_ENABLE_HTTPS = os.environ.get('SECURITY_ENABLE_HTTPS', 'false').lower() == 'true'
    SECURITY_ENABLE_AUTH = os.environ.get('SECURITY_ENABLE_AUTH', 'true').lower() == 'true'
    SECURITY_SESSION_TIMEOUT = int(os.environ.get('SECURITY_SESSION_TIMEOUT', '3600'))
    SECURITY_MAX_LOGIN_ATTEMPTS = int(os.environ.get('SECURITY_MAX_LOGIN_ATTEMPTS', '5'))

class DevelopmentConfig(Config):
    """개발 환경 설정"""
    DEBUG = True
    SESSION_COOKIE_SECURE = False

class ProductionConfig(Config):
    """운영 환경 설정"""
    DEBUG = False
    SESSION_COOKIE_SECURE = True

# 환경별 설정 매핑
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
} 
