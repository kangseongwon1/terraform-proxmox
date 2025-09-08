#!/bin/bash

# 수동 Vault 테스트 스크립트
# 단계별로 Vault 초기화 및 설정을 진행합니다.

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
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }

echo "🔧 수동 Vault 테스트 시작..."
echo ""

# 1. Vault 상태 확인
log_info "1. Vault 상태 확인 중..."
docker exec vault-dev vault status
echo ""

# 2. Vault 초기화
log_info "2. Vault 초기화 중..."
if docker exec vault-dev vault status | grep -q "Initialized.*false"; then
    log_info "Vault 초기화 실행 중..."
    docker exec vault-dev vault operator init -key-shares=1 -key-threshold=1 > vault_init.txt
    
    if [ $? -eq 0 ]; then
        log_success "Vault 초기화 완료"
        echo ""
        log_info "초기화 정보:"
        cat vault_init.txt
        echo ""
    else
        log_error "Vault 초기화 실패"
        exit 1
    fi
else
    log_info "Vault가 이미 초기화되어 있습니다."
fi

# 3. Unseal 키 추출
log_info "3. Unseal 키 추출 중..."
UNSEAL_KEY=$(grep 'Unseal Key 1:' vault_init.txt | awk '{print $NF}')
ROOT_TOKEN=$(grep 'Root Token:' vault_init.txt | awk '{print $NF}')

log_info "Unseal 키: $UNSEAL_KEY"
log_info "Root 토큰: $ROOT_TOKEN"
echo ""

# 4. Vault 언실
log_info "4. Vault 언실 중..."
docker exec vault-dev vault operator unseal $UNSEAL_KEY

if [ $? -eq 0 ]; then
    log_success "Vault 언실 완료"
else
    log_error "Vault 언실 실패"
    exit 1
fi
echo ""

# 5. Vault 인증
log_info "5. Vault 인증 중..."
docker exec vault-dev vault login $ROOT_TOKEN

if [ $? -eq 0 ]; then
    log_success "Vault 인증 완료"
else
    log_error "Vault 인증 실패"
    exit 1
fi
echo ""

# 6. Vault 상태 재확인
log_info "6. Vault 상태 재확인 중..."
docker exec vault-dev vault status
echo ""

# 7. KV v2 엔진 활성화
log_info "7. KV v2 엔진 활성화 중..."
docker exec vault-dev vault secrets enable -path=secret kv-v2

if [ $? -eq 0 ]; then
    log_success "KV v2 엔진 활성화 완료"
else
    log_error "KV v2 엔진 활성화 실패"
    exit 1
fi
echo ""

# 8. 테스트 시크릿 저장
log_info "8. 테스트 시크릿 저장 중..."
docker exec vault-dev vault kv put secret/test key1=value1 key2=value2

if [ $? -eq 0 ]; then
    log_success "테스트 시크릿 저장 완료"
else
    log_error "테스트 시크릿 저장 실패"
    exit 1
fi
echo ""

# 9. 테스트 시크릿 조회
log_info "9. 테스트 시크릿 조회 중..."
docker exec vault-dev vault kv get secret/test
echo ""

log_success "✅ 수동 Vault 테스트 완료!"
echo ""
log_info "🌐 Vault 웹 UI: http://127.0.0.1:8200"
log_info "🔑 토큰: $ROOT_TOKEN"
echo ""
log_info "📁 중요 파일:"
log_info "  - vault_init.txt: 초기화 정보 (안전하게 보관하세요)"
echo ""
log_info "🔧 관리 명령어:"
log_info "  - 상태 확인: docker exec vault-dev vault status"
log_info "  - 시크릿 조회: docker exec vault-dev vault kv get secret/test"
log_info "  - 서비스 중지: docker-compose -f docker-compose.vault.yml down"
