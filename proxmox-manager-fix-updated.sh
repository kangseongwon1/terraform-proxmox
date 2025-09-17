#!/bin/bash
# Proxmox Manager 자동 복구 스크립트 (수정된 버전)
# 사용법: sudo systemctl start proxmox-manager (자동으로 이 스크립트가 실행됨)

# Proxmox Manager 프로젝트 디렉토리로 이동
cd /data/terraform-proxmox || {
    echo "❌ Proxmox Manager 디렉토리를 찾을 수 없습니다: /data/terraform-proxmox"
    exit 1
}

echo "🔧 Proxmox Manager 자동 복구 시작..."
echo "📁 작업 디렉토리: $(pwd)"

# Vault Unseal 및 토큰 복원
echo "🔐 Vault Unseal 및 토큰 복원 중..."

# Vault 상태 확인
if docker ps | grep -q vault-dev; then
    VAULT_SEALED=$(docker exec vault-dev vault status 2>/dev/null | grep "Sealed" | awk '{print $2}')
    
    if [ "$VAULT_SEALED" = "true" ]; then
        echo "⚠️ Vault가 sealed 상태입니다. Unseal을 진행합니다..."
        
        # Unseal 키 파일 확인
        if [ -f "vault_unseal_keys.txt" ]; then
            echo "📋 저장된 Unseal 키를 사용합니다..."
            UNSEAL_KEY=$(cat vault_unseal_keys.txt)
            
            # Vault Unseal 실행
            if docker exec vault-dev vault operator unseal "$UNSEAL_KEY" 2>/dev/null; then
                echo "✅ Vault Unseal 성공"
            else
                echo "❌ Vault Unseal 실패"
            fi
        elif [ -f "vault_init.txt" ]; then
            echo "📋 vault_init.txt에서 Unseal 키를 추출합니다..."
            UNSEAL_KEY=$(grep "Unseal Key 1:" vault_init.txt | awk '{print $4}')
            
            if [ -n "$UNSEAL_KEY" ]; then
                # Unseal 키를 별도 파일에 저장
                echo "$UNSEAL_KEY" > vault_unseal_keys.txt
                chmod 600 vault_unseal_keys.txt
                echo "✅ Unseal 키를 vault_unseal_keys.txt에 저장했습니다."
                
                # Vault Unseal 실행
                if docker exec vault-dev vault operator unseal "$UNSEAL_KEY" 2>/dev/null; then
                    echo "✅ Vault Unseal 성공"
                else
                    echo "❌ Vault Unseal 실패"
                fi
            else
                echo "❌ vault_init.txt에서 Unseal 키를 찾을 수 없습니다."
            fi
        else
            echo "❌ Unseal 키 파일이 없습니다:"
            echo "  - vault_unseal_keys.txt"
            echo "  - vault_init.txt"
        fi
    else
        echo "✅ Vault가 이미 unsealed 상태입니다."
    fi
    
    # 토큰 복원
    if [ -f "vault_token.txt" ]; then
        VAULT_TOKEN=$(cat vault_token.txt)
        export VAULT_TOKEN="$VAULT_TOKEN"
        export TF_VAR_vault_token="$VAULT_TOKEN"
        
        # .env 파일에 토큰 업데이트
        if [ -f ".env" ]; then
            sed -i "s|VAULT_TOKEN=.*|VAULT_TOKEN=$VAULT_TOKEN|" .env
            sed -i "s|TF_VAR_vault_token=.*|TF_VAR_vault_token=$VAULT_TOKEN|" .env
        fi
        
        echo "✅ Vault 토큰 복원 완료"
    elif [ -f "vault_init.txt" ]; then
        echo "📋 vault_init.txt에서 Vault 토큰을 추출합니다..."
        VAULT_TOKEN=$(grep "Initial Root Token:" vault_init.txt | awk '{print $4}')
        
        if [ -n "$VAULT_TOKEN" ]; then
            # 토큰을 별도 파일에 저장
            echo "$VAULT_TOKEN" > vault_token.txt
            chmod 600 vault_token.txt
            echo "✅ Vault 토큰을 vault_token.txt에 저장했습니다."
            
            export VAULT_TOKEN="$VAULT_TOKEN"
            export TF_VAR_vault_token="$VAULT_TOKEN"
            
            # .env 파일에 토큰 업데이트
            if [ -f ".env" ]; then
                sed -i "s|VAULT_TOKEN=.*|VAULT_TOKEN=$VAULT_TOKEN|" .env
                sed -i "s|TF_VAR_vault_token=.*|TF_VAR_vault_token=$VAULT_TOKEN|" .env
            fi
            
            echo "✅ Vault 토큰 복원 완료"
        else
            echo "❌ vault_init.txt에서 Vault 토큰을 찾을 수 없습니다."
        fi
    else
        echo "⚠️ 저장된 Vault 토큰이 없습니다:"
        echo "  - vault_token.txt"
        echo "  - vault_init.txt"
    fi
else
    echo "⚠️ Vault 컨테이너가 실행되지 않았습니다."
fi

# 가상환경 패키지 문제 해결
# 현재 디렉토리에서 실행되므로 상대 경로 사용
if ! ./venv/bin/python -c "import dotenv, flask, requests" 2>/dev/null; then
    echo "⚠️  가상환경 패키지 문제 감지. 자동 수정 중..."
    
    # 가상환경 shebang 수정 (잘못된 경로 참조 문제 해결)
    echo "🔧 가상환경 shebang 수정 중..."
    VENV_PYTHON_PATH=$(which python3)
    if [ -n "$VENV_PYTHON_PATH" ]; then
        # venv/bin/python의 shebang을 현재 시스템의 python3로 수정
        sed -i "1s|.*|#!$VENV_PYTHON_PATH|" ./venv/bin/python
        sed -i "1s|.*|#!$VENV_PYTHON_PATH|" ./venv/bin/pip
        echo "✅ 가상환경 shebang 수정 완료: $VENV_PYTHON_PATH"
    fi
    
    # 가상환경 활성화 및 패키지 재설치
    source ./venv/bin/activate
    pip install --upgrade python-dotenv flask flask-sqlalchemy flask-login requests paramiko
    deactivate
    
    echo "✅ 가상환경 패키지 수정 완료"
fi

# 데이터베이스 디렉토리 및 권한 설정
echo "🗄️ 데이터베이스 디렉토리 설정 중..."
mkdir -p instance
chmod 755 instance
chown $USER:$USER instance 2>/dev/null || true

# 데이터베이스 파일 권한 설정 (존재하는 경우)
if [ -f "instance/proxmox_manager.db" ]; then
    chmod 664 instance/proxmox_manager.db
    chown $USER:$USER instance/proxmox_manager.db 2>/dev/null || true
    echo "✅ 데이터베이스 파일 권한 설정 완료"
else
    echo "ℹ️ 데이터베이스 파일이 아직 생성되지 않았습니다 (정상)"
fi

# config.py import 문제 해결
echo "🔍 config.py import 테스트 중..."
if ! ./venv/bin/python -c "import sys; sys.path.insert(0, '.'); from config.config import TerraformConfig" 2>/dev/null; then
    echo "⚠️  config.py import 문제 감지. 자동 수정 중..."
    
    # config 디렉토리 생성 및 __init__.py 파일 생성
    echo "📝 config 디렉토리 및 __init__.py 파일 생성 중..."
    mkdir -p config
    echo '"""Config 패키지 초기화 파일"""' > config/__init__.py
    
    # config.py 파일 자동 생성
    echo "📝 config.py 파일 자동 생성 중..."
    cat > config/config.py << 'PYEOF'
"""
Flask 애플리케이션 설정
"""
import os
from pathlib import Path

# 프로젝트 루트 디렉토리 설정
project_root = Path(__file__).parent.parent.absolute()
instance_dir = project_root / 'instance'

# instance 디렉토리 생성
os.makedirs(instance_dir, exist_ok=True)

class Config:
    """기본 설정"""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    SQLALCHEMY_DATABASE_URI = f'sqlite:///{instance_dir}/proxmox_manager.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Proxmox 설정
    PROXMOX_ENDPOINT = os.environ.get('PROXMOX_ENDPOINT') or 'https://localhost:8006'
    PROXMOX_USERNAME = os.environ.get('PROXMOX_USERNAME') or 'root@pam'
    PROXMOX_PASSWORD = os.environ.get('PROXMOX_PASSWORD') or 'password'
    PROXMOX_NODE = os.environ.get('PROXMOX_NODE') or 'pve'
    
    # Vault 설정
    VAULT_ADDR = os.environ.get('VAULT_ADDR') or 'http://127.0.0.1:8200'
    VAULT_TOKEN = os.environ.get('VAULT_TOKEN') or ''
    
    # 모니터링 설정
    NODE_EXPORTER_AUTO_INSTALL = os.environ.get('NODE_EXPORTER_AUTO_INSTALL', 'true').lower() == 'true'
    PROMETHEUS_PORT = int(os.environ.get('PROMETHEUS_PORT', 9090))
    GRAFANA_PORT = int(os.environ.get('GRAFANA_PORT', 3000))
    
    # 백업 설정
    BACKUP_ENABLED = os.environ.get('BACKUP_ENABLED', 'true').lower() == 'true'
    BACKUP_RETENTION_DAYS = int(os.environ.get('BACKUP_RETENTION_DAYS', 7))
    BACKUP_SCHEDULE = os.environ.get('BACKUP_SCHEDULE', '0 2 * * *')
    
    # 로그 설정
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_RETENTION_DAYS = int(os.environ.get('LOG_RETENTION_DAYS', 30))

class TerraformConfig(Config):
    """Terraform 관련 설정"""
    pass

# 설정 객체 생성
config = Config()
PYEOF
    
    echo "✅ config.py 파일 생성 완료"
else
    echo "✅ config.py import 정상"
fi

# 데이터베이스 초기화 확인
echo "🗄️ 데이터베이스 초기화 확인 중..."
if [ ! -f "instance/proxmox_manager.db" ]; then
    echo "📝 데이터베이스 초기화 중..."
    ./venv/bin/python -c "
import sys
sys.path.insert(0, '.')
from app import create_app, db
app = create_app()
with app.app_context():
    db.create_all()
    print('✅ 데이터베이스 초기화 완료')
" 2>/dev/null || echo "⚠️ 데이터베이스 초기화 실패 (서비스 시작 시 자동 생성됨)"
else
    echo "✅ 데이터베이스 파일이 이미 존재합니다"
fi

# systemd 서비스 재시작 (sudo 사용)
echo "🔄 systemd 서비스 재시작 중..."
sudo systemctl daemon-reload
sudo systemctl restart proxmox-manager

# 서비스 상태 확인
sleep 3
if sudo systemctl is-active --quiet proxmox-manager; then
    echo "✅ Proxmox Manager 서비스가 정상적으로 실행 중입니다"
    echo "🌐 웹 인터페이스: http://$(hostname -I | awk '{print $1}'):5000"
else
    echo "❌ 서비스 시작 실패. 로그를 확인하세요:"
    echo "   sudo journalctl -u proxmox-manager -n 20"
fi
