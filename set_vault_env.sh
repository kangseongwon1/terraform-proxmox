#!/bin/bash

# Vault 환경변수 설정 스크립트
# Terraform에서 Vault 토큰을 자동으로 설정합니다.

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

echo "🔧 Vault 환경변수 설정 시작..."
echo ""

# 1. vault_init.txt 파일 확인
if [ ! -f "vault_init.txt" ]; then
    log_error "vault_init.txt 파일이 없습니다!"
    log_info "Vault를 먼저 초기화하세요: ./quick_vault_test.sh"
    exit 1
fi

# 2. Root 토큰 추출
ROOT_TOKEN=$(grep 'Root Token:' vault_init.txt | awk '{print $NF}')

if [ -z "$ROOT_TOKEN" ]; then
    log_error "Root 토큰을 찾을 수 없습니다!"
    exit 1
fi

log_info "Root 토큰: $ROOT_TOKEN"

# 3. 환경변수 설정
export VAULT_ADDR="http://127.0.0.1:8200"
export VAULT_TOKEN="$ROOT_TOKEN"

log_success "환경변수 설정 완료"
echo ""

# 4. 환경변수 확인
log_info "설정된 환경변수:"
echo "  VAULT_ADDR: $VAULT_ADDR"
echo "  VAULT_TOKEN: $VAULT_TOKEN"
echo ""

# 5. Vault 연결 테스트
log_info "Vault 연결 테스트 중..."
if docker exec vault-dev vault status | grep -q "Sealed.*false"; then
    log_success "Vault 연결 성공"
else
    log_error "Vault 연결 실패"
    exit 1
fi

# 6. Terraform 디렉토리로 이동
log_info "Terraform 디렉토리로 이동 중..."
cd terraform

# 7. terraform.tfvars.json 업데이트
log_info "terraform.tfvars.json 업데이트 중..."
if [ -f "terraform.tfvars.json" ]; then
    # 기존 파일 백업
    cp terraform.tfvars.json terraform.tfvars.json.backup
    
    # 토큰 업데이트
    sed -i "s/\"vault_token\": \".*\"/\"vault_token\": \"$ROOT_TOKEN\"/" terraform.tfvars.json
    
    log_success "terraform.tfvars.json 업데이트 완료"
else
    log_error "terraform.tfvars.json 파일이 없습니다!"
    exit 1
fi

# 8. Terraform 초기화
log_info "Terraform 초기화 중..."
terraform init

if [ $? -eq 0 ]; then
    log_success "Terraform 초기화 완료"
else
    log_error "Terraform 초기화 실패"
    exit 1
fi

# 9. Terraform 계획 실행
log_info "Terraform 계획 실행 중..."
terraform plan

if [ $? -eq 0 ]; then
    log_success "Terraform 계획 실행 완료"
else
    log_error "Terraform 계획 실행 실패"
    exit 1
fi

# 10. 원래 디렉토리로 복귀
cd ..

log_success "✅ Vault 환경변수 설정 및 Terraform 테스트 완료!"
echo ""
log_info "🔧 사용된 환경변수:"
echo "  VAULT_ADDR: $VAULT_ADDR"
echo "  VAULT_TOKEN: $VAULT_TOKEN"
echo ""
log_info "📁 업데이트된 파일:"
echo "  - terraform/terraform.tfvars.json"
echo "  - terraform/terraform.tfvars.json.backup (백업)"
echo ""
log_info "🌐 Vault 웹 UI: http://127.0.0.1:8200"
log_info "🔑 토큰: $ROOT_TOKEN"
