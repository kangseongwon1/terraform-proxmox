#!/bin/bash

# 통합 Vault 스크립트
# Vault 설치부터 환경변수 설정, 시크릿 저장까지 모든 것을 처리합니다.

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

echo "🚀 통합 Vault 스크립트 시작..."
echo ""

# 1. Docker 및 Docker Compose 확인
check_docker() {
    log_info "1. Docker 및 Docker Compose 확인 중..."
    
    if ! command -v docker &> /dev/null; then
        log_error "Docker가 설치되지 않았습니다!"
        log_info "Docker 설치 방법:"
        log_info "sudo dnf install -y docker"
        log_info "sudo systemctl enable docker"
        log_info "sudo systemctl start docker"
        log_info "sudo usermod -aG docker \$USER"
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose가 설치되지 않았습니다!"
        log_info "Docker Compose 설치 방법:"
        log_info "sudo dnf install -y docker-compose"
        exit 1
    fi
    
    if ! sudo systemctl is-active --quiet docker; then
        log_warning "Docker 서비스가 실행되지 않았습니다. 시작 중..."
        sudo systemctl start docker
    fi
    
    log_success "Docker 및 Docker Compose 확인 완료"
}

# 2. .env 파일 확인
check_env() {
    log_info "2. .env 파일 확인 중..."
    
    if [ ! -f ".env" ]; then
        log_error ".env 파일이 없습니다!"
        log_info "test.env를 .env로 복사하세요:"
        log_info "cp test.env .env"
        exit 1
    fi
    
    source .env
    log_success ".env 파일 로드 완료"
}

# 3. 기존 Vault 컨테이너 정리
cleanup_vault() {
    log_info "3. 기존 Vault 컨테이너 정리 중..."
    
    # Docker Compose로 실행 중인 Vault 중지
    if [ -f "docker-compose.vault.yml" ]; then
        docker-compose -f docker-compose.vault.yml down 2>/dev/null || true
    fi
    
    # 기존 Vault 컨테이너 중지 및 제거
    docker stop vault-dev 2>/dev/null || true
    docker rm vault-dev 2>/dev/null || true
    
    # 기존 Vault 볼륨 제거
    docker volume rm vault-data 2>/dev/null || true
    
    log_success "기존 Vault 컨테이너 정리 완료"
}

# 4. Vault Docker Compose 실행
start_vault() {
    log_info "4. Vault Docker Compose 실행 중..."
    
    # Vault 데이터 디렉토리 생성
    mkdir -p vault-data
    
    # Docker Compose로 Vault 실행
    docker-compose -f docker-compose.vault.yml up -d
    
    # Vault 초기화 대기
    log_info "Vault 초기화 대기 중..."
    sleep 15
    
    # Vault 상태 확인
    local max_attempts=30
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if docker exec vault-dev vault status | grep -q "Version"; then
            log_success "Vault 컨테이너 시작 완료"
            return 0
        fi
        
        log_info "Vault 시작 대기 중... ($attempt/$max_attempts)"
        sleep 2
        ((attempt++))
    done
    
    log_error "Vault 시작 실패"
    exit 1
}

# 5. Vault 초기화 및 언실
init_vault() {
    log_info "5. Vault 초기화 및 언실 중..."
    
    # Vault 초기화 (최초 1회)
    if docker exec vault-dev vault status | grep -q "Initialized.*false"; then
        log_info "Vault 초기화 실행 중..."
        docker exec vault-dev vault operator init -key-shares=1 -key-threshold=1 > vault_init.txt
        
        if [ $? -ne 0 ]; then
            log_error "Vault 초기화 실패"
            exit 1
        fi
        
        log_success "Vault 초기화 완료"
    else
        log_info "Vault가 이미 초기화되어 있습니다."
    fi
    
    # Unseal 키 추출
    UNSEAL_KEY=$(grep 'Unseal Key 1:' vault_init.txt | awk '{print $NF}')
    ROOT_TOKEN=$(grep 'Root Token:' vault_init.txt | awk '{print $NF}')
    
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
}

# 6. Vault 설정
configure_vault() {
    log_info "6. Vault 설정 중..."
    
    # KV v2 엔진 활성화
    log_info "KV v2 엔진 활성화 중..."
    docker exec vault-dev vault secrets enable -path=secret kv-v2
    
    # SSH 키 읽기
    local ssh_public_key=""
    if [ -f ~/.ssh/id_rsa.pub ]; then
        ssh_public_key=$(cat ~/.ssh/id_rsa.pub)
        log_info "SSH 공개키 읽기 완료"
    else
        log_warning "SSH 공개키가 없습니다. SSH 키를 먼저 생성하세요."
        log_info "ssh-keygen -t rsa -b 4096 -f ~/.ssh/id_rsa -N \"\" -C \"proxmox-manager\""
    fi
    
    # Proxmox 자격증명 저장
    log_info "Proxmox 자격증명 저장 중..."
    docker exec vault-dev vault kv put secret/proxmox \
        username="${PROXMOX_USERNAME}" \
        password="${PROXMOX_PASSWORD}"
    
    # VM 자격증명 저장
    log_info "VM 자격증명 저장 중..."
    docker exec vault-dev vault kv put secret/vm \
        username="${VM_USERNAME}" \
        password="${VM_PASSWORD}"
    
    # SSH 키 저장
    if [ -n "$ssh_public_key" ]; then
        log_info "SSH 키 저장 중..."
        docker exec vault-dev vault kv put secret/ssh \
            public_key="$ssh_public_key"
    fi
    
    log_success "Vault 설정 완료"
}

# 7. 환경변수 설정
set_environment() {
    log_info "7. 환경변수 설정 중..."
    
    # Vault 환경변수 설정
    export VAULT_ADDR="http://127.0.0.1:8200"
    export VAULT_TOKEN="$ROOT_TOKEN"
    
    # Terraform 환경변수 설정 (TF_VAR_ 접두사 사용)
    export TF_VAR_vault_token="$ROOT_TOKEN"
    export TF_VAR_vault_address="http://127.0.0.1:8200"
    
    # terraform.tfvars.json 업데이트
    if [ -f "terraform/terraform.tfvars.json" ]; then
        log_info "terraform.tfvars.json 업데이트 중..."
        cd terraform
        
        # 기존 파일 백업
        cp terraform.tfvars.json terraform.tfvars.json.backup 2>/dev/null || true
        
        # 토큰 업데이트
        sed -i "s/\"vault_token\": \".*\"/\"vault_token\": \"$ROOT_TOKEN\"/" terraform.tfvars.json
        
        cd ..
        log_success "terraform.tfvars.json 업데이트 완료"
    fi
    
    log_success "환경변수 설정 완료"
    log_info "설정된 환경변수:"
    echo "  VAULT_ADDR: $VAULT_ADDR"
    echo "  VAULT_TOKEN: $VAULT_TOKEN"
    echo "  TF_VAR_vault_token: $TF_VAR_vault_token"
    echo "  TF_VAR_vault_address: $TF_VAR_vault_address"
}

# 8. Terraform 테스트
test_terraform() {
    log_info "8. Terraform 테스트 중..."
    
    cd terraform
    
    # Terraform 초기화
    log_info "Terraform 초기화 중..."
    terraform init
    
    if [ $? -eq 0 ]; then
        log_success "Terraform 초기화 완료"
    else
        log_error "Terraform 초기화 실패"
        exit 1
    fi
    
    # Terraform 계획 실행
    log_info "Terraform 계획 실행 중..."
    terraform plan
    
    if [ $? -eq 0 ]; then
        log_success "Terraform 계획 실행 완료"
    else
        log_error "Terraform 계획 실행 실패"
        exit 1
    fi
    
    cd ..
    log_success "Terraform 테스트 완료"
}

# 9. 완료 메시지
show_completion() {
    log_success "=========================================="
    log_success "통합 Vault 스크립트 완료!"
    log_success "=========================================="
    
    echo ""
    log_info "🔑 Vault 정보:"
    echo "  - 주소: $VAULT_ADDR"
    echo "  - 토큰: $ROOT_TOKEN"
    echo "  - 컨테이너: vault-dev"
    echo ""
    
    log_info "📋 저장된 시크릿:"
    echo "  - secret/proxmox (Proxmox 자격증명)"
    echo "  - secret/vm (VM 자격증명)"
    if [ -f ~/.ssh/id_rsa.pub ]; then
        echo "  - secret/ssh (SSH 공개키)"
    fi
    echo ""
    
    log_info "🔧 관리 명령어:"
    echo "  - 상태 확인: docker exec vault-dev vault status"
    echo "  - 시크릿 조회: docker exec vault-dev vault kv get secret/proxmox"
    echo "  - 서비스 중지: docker-compose -f docker-compose.vault.yml down"
    echo "  - 서비스 시작: docker-compose -f docker-compose.vault.yml up -d"
    echo ""
    
    log_info "🌐 웹 UI 접속:"
    echo "  - Vault UI: $VAULT_ADDR"
    echo "  - 토큰: $ROOT_TOKEN"
    echo ""
    
    log_info "📁 중요 파일:"
    echo "  - vault_init.txt: 초기화 정보 (안전하게 보관하세요)"
    echo "  - vault-dev.hcl: Vault 설정 파일"
    echo "  - docker-compose.vault.yml: Docker Compose 설정"
    echo ""
    
    log_info "🔄 Terraform 사용:"
    echo "  export VAULT_ADDR='$VAULT_ADDR'"
    echo "  export VAULT_TOKEN='$ROOT_TOKEN'"
    echo "  export TF_VAR_vault_token='$ROOT_TOKEN'"
    echo "  export TF_VAR_vault_address='$VAULT_ADDR'"
    echo "  cd terraform && terraform plan"
    echo ""
    
    log_warning "⚠️  주의: vault_init.txt 파일을 안전하게 보관하세요!"
}

# 메인 실행 함수
main() {
    log_info "통합 Vault 스크립트 시작..."
    
    # 각 단계 실행
    check_docker
    check_env
    cleanup_vault
    start_vault
    init_vault
    configure_vault
    set_environment
    test_terraform
    
    # 완료 메시지
    show_completion
}

# 스크립트 실행
main "$@"
