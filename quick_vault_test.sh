#!/bin/bash

# 간단한 Vault Docker Compose 테스트 스크립트
# 빠른 테스트를 위한 최소한의 기능만 테스트합니다.

set -e

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

echo "🧪 Vault Docker Compose 빠른 테스트 시작..."
echo ""

# 1. Docker 및 Docker Compose 확인
log_info "1. Docker 및 Docker Compose 확인 중..."
if command -v docker &> /dev/null; then
    log_success "Docker 설치됨: $(docker --version)"
else
    log_error "Docker가 설치되지 않았습니다!"
    exit 1
fi

if command -v docker-compose &> /dev/null; then
    log_success "Docker Compose 설치됨: $(docker-compose --version)"
else
    log_error "Docker Compose가 설치되지 않았습니다!"
    exit 1
fi

# 2. Docker 서비스 확인
log_info "2. Docker 서비스 확인 중..."
if sudo systemctl is-active --quiet docker; then
    log_success "Docker 서비스 실행 중"
else
    log_error "Docker 서비스가 실행되지 않았습니다!"
    exit 1
fi

# 3. Vault 설정 파일 확인
log_info "3. Vault 설정 파일 확인 중..."
if [ -f "vault-dev.hcl" ]; then
    log_success "vault-dev.hcl 파일 존재"
else
    log_error "vault-dev.hcl 파일이 없습니다!"
    exit 1
fi

if [ -f "docker-compose.vault.yml" ]; then
    log_success "docker-compose.vault.yml 파일 존재"
else
    log_error "docker-compose.vault.yml 파일이 없습니다!"
    exit 1
fi

# 4. 기존 Vault 컨테이너 정리
log_info "4. 기존 Vault 컨테이너 정리 중..."
docker-compose -f docker-compose.vault.yml down 2>/dev/null || true
docker stop vault-dev 2>/dev/null || true
docker rm vault-dev 2>/dev/null || true

# 5. Vault 데이터 디렉토리 생성
log_info "5. Vault 데이터 디렉토리 생성 중..."
mkdir -p vault-data

# 6. Vault Docker Compose 실행
log_info "6. Vault Docker Compose 실행 중..."
docker-compose -f docker-compose.vault.yml up -d

# 7. Vault 초기화 대기
log_info "7. Vault 초기화 대기 중..."
sleep 15

# 8. Vault 상태 확인
log_info "8. Vault 상태 확인 중..."
if docker exec vault-dev vault status | grep -q "Version"; then
    log_success "Vault 컨테이너 정상 실행 중"
else
    log_error "Vault 컨테이너 실행 실패"
    exit 1
fi

# 9. Vault 초기화 (최초 1회)
log_info "9. Vault 초기화 중..."
if docker exec vault-dev vault status | grep -q "Initialized.*false"; then
    log_info "Vault 초기화 실행 중..."
    docker exec vault-dev vault operator init -key-shares=1 -key-threshold=1 > vault_init.txt
    
    if [ $? -ne 0 ]; then
        log_error "Vault 초기화 실패"
        exit 1
    fi
    
    # Unseal 키 추출
    UNSEAL_KEY=$(grep 'Unseal Key 1:' vault_init.txt | awk '{print $NF}')
    ROOT_TOKEN=$(grep 'Root Token:' vault_init.txt | awk '{print $NF}')
    
    log_info "Unseal 키: $UNSEAL_KEY"
    log_info "Root 토큰: $ROOT_TOKEN"
    
    # Vault 언실
    log_info "Vault 언실 중..."
    docker exec vault-dev vault operator unseal $UNSEAL_KEY
    
    if [ $? -ne 0 ]; then
        log_error "Vault 언실 실패"
        exit 1
    fi
    
    # Root 토큰으로 로그인
    log_info "Vault 인증 중..."
    docker exec vault-dev vault login $ROOT_TOKEN
    
    if [ $? -ne 0 ]; then
        log_error "Vault 인증 실패"
        exit 1
    fi
    
    log_success "Vault 초기화 및 언실 완료"
else
    log_info "Vault가 이미 초기화되어 있습니다."
    # 기존 토큰 사용
    if [ -f "vault_init.txt" ]; then
        ROOT_TOKEN=$(grep 'Root Token:' vault_init.txt | awk '{print $NF}')
        log_info "기존 Root 토큰 사용: $ROOT_TOKEN"
    else
        log_error "vault_init.txt 파일이 없습니다. Vault를 재초기화하세요."
        exit 1
    fi
fi

# 10. Vault 설정
log_info "10. Vault 설정 중..."
export VAULT_ADDR="http://127.0.0.1:8200"
export VAULT_TOKEN="$ROOT_TOKEN"

# KV v2 엔진 활성화
docker exec vault-dev vault secrets enable -path=secret kv-v2

# 테스트 시크릿 저장
docker exec vault-dev vault kv put secret/test key1=value1 key2=value2

# 테스트 시크릿 조회
log_info "11. 테스트 시크릿 조회 중..."
docker exec vault-dev vault kv get secret/test

log_success "✅ Vault Docker Compose 테스트 완료!"
echo ""
log_info "🌐 Vault 웹 UI: http://127.0.0.1:8200"
log_info "🔑 토큰: $ROOT_TOKEN"
echo ""
log_info "🔧 관리 명령어:"
log_info "  - 상태 확인: docker exec vault-dev vault status"
log_info "  - 서비스 중지: docker-compose -f docker-compose.vault.yml down"
log_info "  - 서비스 시작: docker-compose -f docker-compose.vault.yml up -d"
log_info "  - 서비스 재시작: docker-compose -f docker-compose.vault.yml restart"
echo ""
log_info "📁 중요 파일:"
log_info "  - vault_init.txt: 초기화 정보 (안전하게 보관하세요)"
log_info "  - vault-dev.hcl: Vault 설정 파일"
log_info "  - docker-compose.vault.yml: Docker Compose 설정"