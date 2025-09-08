#!/bin/bash

# 간단한 Vault Docker 테스트 스크립트
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

echo "🧪 Vault Docker 빠른 테스트 시작..."
echo ""

# 1. Docker 확인
log_info "1. Docker 확인 중..."
if command -v docker &> /dev/null; then
    log_success "Docker 설치됨: $(docker --version)"
else
    log_error "Docker가 설치되지 않았습니다!"
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

# 3. 기존 Vault 컨테이너 정리
log_info "3. 기존 Vault 컨테이너 정리 중..."
docker stop vault 2>/dev/null || true
docker rm vault 2>/dev/null || true
docker volume rm vault-data 2>/dev/null || true

# 4. Vault 컨테이너 실행
log_info "4. Vault 컨테이너 실행 중..."
docker volume create vault-data
docker run -d \
    --name vault \
    --cap-add=IPC_LOCK \
    -p 8200:8200 \
    -v vault-data:/vault/data \
    -e VAULT_DEV_ROOT_TOKEN_ID=root \
    -e VAULT_DEV_LISTEN_ADDRESS=0.0.0.0:8200 \
    vault:latest

# 5. Vault 초기화 대기
log_info "5. Vault 초기화 대기 중..."
sleep 10

# 6. Vault 상태 확인
log_info "6. Vault 상태 확인 중..."
if docker exec vault vault status; then
    log_success "Vault 정상 실행 중"
else
    log_error "Vault 실행 실패"
    exit 1
fi

# 7. Vault 설정
log_info "7. Vault 설정 중..."
export VAULT_ADDR="http://127.0.0.1:8200"
export VAULT_TOKEN="root"

# KV v2 엔진 활성화
docker exec vault vault secrets enable -path=secret kv-v2

# 테스트 시크릿 저장
docker exec vault vault kv put secret/test key1=value1 key2=value2

# 테스트 시크릿 조회
log_info "8. 테스트 시크릿 조회 중..."
docker exec vault vault kv get secret/test

log_success "✅ Vault Docker 테스트 완료!"
echo ""
log_info "🌐 Vault 웹 UI: http://127.0.0.1:8200"
log_info "🔑 토큰: root"
echo ""
log_info "🛑 Vault 중지: docker stop vault"
log_info "🔄 Vault 재시작: docker start vault"
log_info "🗑️  Vault 제거: docker stop vault && docker rm vault"
