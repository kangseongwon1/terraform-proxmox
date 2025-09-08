#!/bin/bash

# Vault Docker Compose 설정 스크립트 (Rocky 8 호환)
# Docker Compose를 사용하여 HashiCorp Vault를 실행하고 설정합니다.
# 모든 민감한 정보는 .env 파일에서 가져옵니다.

set -e  # 오류 발생 시 스크립트 중단

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 로그 함수
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# .env 파일 확인
check_env_file() {
    if [ ! -f ".env" ]; then
        log_error ".env 파일이 없습니다!"
        log_info "env_template.txt를 .env로 복사한 후 설정하세요:"
        log_info "cp env_template.txt .env"
        log_info "nano .env"
        exit 1
    fi
    
    log_success ".env 파일 확인 완료"
}

# .env 파일 로드
load_env() {
    log_info ".env 파일 로드 중..."
    
    # .env 파일에서 변수 로드 (주석과 빈 줄 제외)
    export $(grep -v '^#' .env | grep -v '^$' | xargs)
    
    # 필수 변수 확인
    required_vars=(
        "PROXMOX_USERNAME"
        "PROXMOX_PASSWORD"
        "VM_USERNAME"
        "VM_PASSWORD"
    )
    
    for var in "${required_vars[@]}"; do
        if [ -z "${!var}" ]; then
            log_error "필수 환경변수 $var가 설정되지 않았습니다!"
            exit 1
        fi
    done
    
    log_success "환경변수 로드 완료"
}

# Docker 및 Docker Compose 설치 확인
check_docker() {
    if ! command -v docker &> /dev/null; then
        log_error "Docker가 설치되지 않았습니다!"
        log_info "Rocky 8에서 Docker 설치 방법:"
        log_info "sudo dnf install -y docker"
        log_info "sudo systemctl enable docker"
        log_info "sudo systemctl start docker"
        log_info "sudo usermod -aG docker \$USER"
        log_info "로그아웃 후 다시 로그인하세요."
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose가 설치되지 않았습니다!"
        log_info "Docker Compose 설치 방법:"
        log_info "sudo dnf install -y docker-compose"
        exit 1
    fi
    
    # Docker 서비스 상태 확인
    if ! sudo systemctl is-active --quiet docker; then
        log_warning "Docker 서비스가 실행되지 않았습니다. 시작 중..."
        sudo systemctl start docker
    fi
    
    log_success "Docker 및 Docker Compose 확인 완료"
}

# Vault 설정 파일 확인
check_vault_config() {
    if [ ! -f "vault-dev.hcl" ]; then
        log_error "vault-dev.hcl 파일이 없습니다!"
        log_info "vault-dev.hcl 파일을 생성하세요."
        exit 1
    fi
    
    log_success "Vault 설정 파일 확인 완료"
}

# 기존 Vault 컨테이너 정리
cleanup_vault() {
    log_info "기존 Vault 컨테이너 정리 중..."
    
    # Docker Compose로 실행 중인 Vault 중지
    if [ -f "docker-compose.vault.yml" ]; then
        docker-compose -f docker-compose.vault.yml down 2>/dev/null || true
        log_info "기존 Vault Docker Compose 서비스 중지 완료"
    fi
    
    # 기존 Vault 컨테이너 중지 및 제거
    if docker ps -a --format 'table {{.Names}}' | grep -q "vault-dev"; then
        docker stop vault-dev 2>/dev/null || true
        docker rm vault-dev 2>/dev/null || true
        log_info "기존 Vault 컨테이너 제거 완료"
    fi
    
    # 기존 Vault 볼륨 제거
    if docker volume ls --format 'table {{.Name}}' | grep -q "vault-data"; then
        docker volume rm vault-data 2>/dev/null || true
        log_info "기존 Vault 볼륨 제거 완료"
    fi
}

# Vault Docker Compose 실행
start_vault() {
    log_info "Vault Docker Compose 시작 중..."
    
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
        if docker exec vault-dev vault status >/dev/null 2>&1; then
            log_success "Vault Docker Compose 시작 완료"
            return 0
        fi
        
        log_info "Vault 시작 대기 중... ($attempt/$max_attempts)"
        sleep 2
        ((attempt++))
    done
    
    log_error "Vault 시작 실패"
    exit 1
}

# Vault 초기화 및 언실
init_vault() {
    log_info "Vault 초기화 및 언실 중..."
    
    # Vault 초기화 (최초 1회)
    if ! docker exec vault-dev vault status | grep -q "Initialized"; then
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
    
    log_success "Vault 언실 완료"
    
    # 환경변수 설정
    export VAULT_ADDR="${VAULT_ADDR:-http://127.0.0.1:8200}"
    export VAULT_TOKEN="$ROOT_TOKEN"
    
    # Root 토큰으로 로그인
    docker exec vault-dev vault auth $ROOT_TOKEN
    
    log_success "Vault 인증 완료"
}

# Vault 설정
configure_vault() {
    log_info "Vault 설정 중..."
    
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

# Vault 상태 확인
verify_vault() {
    log_info "Vault 상태 확인 중..."
    
    # Vault 상태 확인
    if docker exec vault-dev vault status >/dev/null 2>&1; then
        log_success "Vault 서비스 정상 동작"
    else
        log_error "Vault 서비스 오류"
        exit 1
    fi
    
    # 저장된 시크릿 확인
    log_info "저장된 시크릿 확인 중..."
    
    if docker exec vault-dev vault kv get secret/proxmox >/dev/null 2>&1; then
        log_success "Proxmox 자격증명 저장 확인"
    else
        log_error "Proxmox 자격증명 저장 실패"
    fi
    
    if docker exec vault-dev vault kv get secret/vm >/dev/null 2>&1; then
        log_success "VM 자격증명 저장 확인"
    else
        log_error "VM 자격증명 저장 실패"
    fi
    
    if docker exec vault-dev vault kv get secret/ssh >/dev/null 2>&1; then
        log_success "SSH 키 저장 확인"
    else
        log_warning "SSH 키 저장 실패 (SSH 키가 없을 수 있음)"
    fi
}

# 설치 완료 메시지
show_completion_message() {
    log_success "=========================================="
    log_success "Vault Docker Compose 설정 완료!"
    log_success "=========================================="
    
    echo ""
    log_info "🔑 Vault 정보:"
    echo "  - 주소: ${VAULT_ADDR:-http://127.0.0.1:8200}"
    echo "  - 토큰: $ROOT_TOKEN"
    echo "  - 컨테이너: vault-dev"
    echo ""
    
    log_info "📋 저장된 시크릿:"
    echo "  - secret/proxmox (Proxmox 자격증명)"
    echo "  - secret/vm (VM 자격증명)"
    echo "  - secret/ssh (SSH 공개키)"
    echo ""
    
    log_info "🔧 Vault 관리 명령어:"
    echo "  - 상태 확인: docker exec vault-dev vault status"
    echo "  - 시크릿 조회: docker exec vault-dev vault kv get secret/proxmox"
    echo "  - 서비스 중지: docker-compose -f docker-compose.vault.yml down"
    echo "  - 서비스 시작: docker-compose -f docker-compose.vault.yml up -d"
    echo "  - 서비스 재시작: docker-compose -f docker-compose.vault.yml restart"
    echo ""
    
    log_info "🌐 웹 UI 접속:"
    echo "  - Vault UI: ${VAULT_ADDR:-http://127.0.0.1:8200}"
    echo "  - 토큰: $ROOT_TOKEN"
    echo ""
    
    log_info "📁 중요 파일:"
    echo "  - vault_init.txt: 초기화 정보 (안전하게 보관하세요)"
    echo "  - vault-dev.hcl: Vault 설정 파일"
    echo "  - docker-compose.vault.yml: Docker Compose 설정"
    echo ""
    
    log_warning "⚠️  주의: vault_init.txt 파일을 안전하게 보관하세요!"
    echo ""
    log_info "🔄 Terraform에서 Vault 사용:"
    echo "  export VAULT_ADDR='${VAULT_ADDR:-http://127.0.0.1:8200}'"
    echo "  export VAULT_TOKEN='$ROOT_TOKEN'"
    echo "  cd terraform && terraform init && terraform plan"
}

# 메인 실행 함수
main() {
    log_info "Vault Docker Compose 설정 시작..."
    
    # 필수 확인
    check_env_file
    load_env
    check_docker
    check_vault_config
    
    # Vault 설정
    cleanup_vault
    start_vault
    init_vault
    configure_vault
    verify_vault
    
    # 완료 메시지
    show_completion_message
}

# 스크립트 실행
main "$@"