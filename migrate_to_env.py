#!/usr/bin/env python3
"""
설정 마이그레이션 스크립트
config 파일에서 .env 파일로 설정을 마이그레이션하는 도구
"""
import os
import sys
from config_loader import get_monitoring_config
from hybrid_config_loader import get_hybrid_config

def migrate_config_to_env():
    """config 파일에서 .env 파일로 설정 마이그레이션"""
    try:
        print("🔄 설정 마이그레이션 시작...")
        
        # 1. 기존 config 파일 로드
        config = get_monitoring_config()
        all_config = config.get_all_config()
        
        # 2. .env 파일 생성
        env_file = '.env'
        with open(env_file, 'w', encoding='utf-8') as f:
            f.write("# 모니터링 시스템 환경 변수\n")
            f.write("# config 파일에서 자동 마이그레이션됨\n\n")
            
            # Grafana 설정
            f.write("# Grafana 설정\n")
            grafana = all_config['grafana']
            f.write(f"GRAFANA_URL={grafana['base_url']}\n")
            f.write(f"GRAFANA_USERNAME={grafana['username']}\n")
            f.write(f"GRAFANA_PASSWORD={grafana['password']}\n")
            f.write(f"GRAFANA_ORG_ID={grafana['org_id']}\n")
            f.write(f"GRAFANA_DASHBOARD_UID={grafana['dashboard_uid']}\n")
            f.write(f"GRAFANA_ANONYMOUS_ACCESS={str(grafana['anonymous_access']).lower()}\n")
            f.write(f"GRAFANA_AUTO_REFRESH={grafana['auto_refresh']}\n\n")
            
            # Prometheus 설정
            f.write("# Prometheus 설정\n")
            prometheus = all_config['prometheus']
            f.write(f"PROMETHEUS_URL={prometheus['url']}\n")
            f.write(f"PROMETHEUS_USERNAME={prometheus['username']}\n")
            f.write(f"PROMETHEUS_PASSWORD={prometheus['password']}\n\n")
            
            # 모니터링 설정
            f.write("# 모니터링 설정\n")
            monitoring = all_config['monitoring']
            f.write(f"MONITORING_DEFAULT_TIME_RANGE={monitoring['default_time_range']}\n")
            f.write(f"MONITORING_HEALTH_CHECK_INTERVAL={monitoring['health_check_interval']}\n")
            f.write(f"MONITORING_PING_TIMEOUT={monitoring['ping_timeout']}\n")
            f.write(f"MONITORING_SSH_TIMEOUT={monitoring['ssh_timeout']}\n")
            f.write(f"NODE_EXPORTER_AUTO_INSTALL={str(monitoring['auto_install_node_exporter']).lower()}\n")
            f.write(f"NODE_EXPORTER_PORT={monitoring['node_exporter_port']}\n")
            f.write(f"NODE_EXPORTER_VERSION={monitoring['node_exporter_version']}\n\n")
            
            # 알림 설정
            f.write("# 알림 설정\n")
            alerts = all_config['alerts']
            f.write(f"ALERTS_ENABLED={str(alerts['enable_alerts']).lower()}\n")
            f.write(f"ALERTS_EMAIL={alerts['alert_email']}\n")
            f.write(f"ALERTS_CPU_WARNING_THRESHOLD={alerts['cpu_warning_threshold']}\n")
            f.write(f"ALERTS_CPU_CRITICAL_THRESHOLD={alerts['cpu_critical_threshold']}\n")
            f.write(f"ALERTS_MEMORY_WARNING_THRESHOLD={alerts['memory_warning_threshold']}\n")
            f.write(f"ALERTS_MEMORY_CRITICAL_THRESHOLD={alerts['memory_critical_threshold']}\n\n")
            
            # 보안 설정
            f.write("# 보안 설정\n")
            security = all_config['security']
            f.write(f"SECURITY_ENABLE_HTTPS={str(security['enable_https']).lower()}\n")
            f.write(f"SECURITY_ENABLE_AUTH={str(security['enable_auth']).lower()}\n")
            f.write(f"SECURITY_SESSION_TIMEOUT={security['session_timeout']}\n")
            f.write(f"SECURITY_MAX_LOGIN_ATTEMPTS={security['max_login_attempts']}\n")
        
        print(f"✅ .env 파일 생성 완료: {env_file}")
        print("📝 다음 단계:")
        print("1. .env 파일을 확인하고 필요시 수정하세요")
        print("2. .env 파일을 .gitignore에 추가하세요")
        print("3. 웹 애플리케이션을 재시작하세요")
        
        return True
        
    except Exception as e:
        print(f"❌ 마이그레이션 실패: {e}")
        return False

def migrate_env_to_config():
    """환경 변수에서 config 파일로 설정 마이그레이션"""
    try:
        print("🔄 환경 변수에서 config 파일로 마이그레이션 시작...")
        
        # 하이브리드 설정 로더 사용
        config = get_hybrid_config()
        
        # config 파일 저장
        config.save_config()
        
        print("✅ config 파일 생성 완료: monitoring_config.conf")
        print("📝 다음 단계:")
        print("1. monitoring_config.conf 파일을 확인하고 필요시 수정하세요")
        print("2. 웹 애플리케이션을 재시작하세요")
        
        return True
        
    except Exception as e:
        print(f"❌ 마이그레이션 실패: {e}")
        return False

def show_current_config():
    """현재 설정 상태 표시"""
    try:
        print("📊 현재 설정 상태:")
        
        # 하이브리드 설정 로드
        config = get_hybrid_config()
        all_config = config.get_all_config()
        
        print("\n🔧 Grafana 설정:")
        grafana = all_config['grafana']
        for key, value in grafana.items():
            if 'password' in key.lower():
                print(f"  {key}: {'*' * len(str(value))}")
            else:
                print(f"  {key}: {value}")
        
        print("\n🔧 Prometheus 설정:")
        prometheus = all_config['prometheus']
        for key, value in prometheus.items():
            if 'password' in key.lower():
                print(f"  {key}: {'*' * len(str(value))}")
            else:
                print(f"  {key}: {value}")
        
        print("\n🔧 모니터링 설정:")
        monitoring = all_config['monitoring']
        for key, value in monitoring.items():
            print(f"  {key}: {value}")
        
        print("\n🔧 알림 설정:")
        alerts = all_config['alerts']
        for key, value in alerts.items():
            print(f"  {key}: {value}")
        
        print("\n🔧 보안 설정:")
        security = all_config['security']
        for key, value in security.items():
            print(f"  {key}: {value}")
        
        return True
        
    except Exception as e:
        print(f"❌ 설정 상태 확인 실패: {e}")
        return False

def main():
    """메인 함수"""
    if len(sys.argv) < 2:
        print("사용법:")
        print("  python migrate_to_env.py config-to-env    # config 파일 → .env 파일")
        print("  python migrate_to_env.py env-to-config    # 환경 변수 → config 파일")
        print("  python migrate_to_env.py show             # 현재 설정 상태 표시")
        return
    
    command = sys.argv[1].lower()
    
    if command == 'config-to-env':
        migrate_config_to_env()
    elif command == 'env-to-config':
        migrate_env_to_config()
    elif command == 'show':
        show_current_config()
    else:
        print(f"❌ 알 수 없는 명령어: {command}")
        print("사용 가능한 명령어: config-to-env, env-to-config, show")

if __name__ == '__main__':
    main()
