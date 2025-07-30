#!/bin/bash

# ========================================
# Proxmox 서버 자동 생성 시스템 설치 스크립트
# ========================================

set -e  # 오류 발생 시 스크립트 중단

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 로그 함수
log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

# 시스템 확인
check_system() {
    log_info "시스템 요구사항을 확인합니다..."
    
    # OS 확인
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        log_success "Linux 시스템 감지됨"
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        log_success "macOS 시스템 감지됨"
    else
        log_warning "지원되지 않는 OS: $OSTYPE"
    fi
    
    # Python 버전 확인
    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
        log_success "Python $PYTHON_VERSION 발견됨"
    else
        log_error "Python 3이 설치되지 않았습니다. 먼저 Python 3를 설치해주세요."
        exit 1
    fi
    
    # Git 확인
    if command -v git &> /dev/null; then
        log_success "Git 발견됨"
    else
        log_error "Git이 설치되지 않았습니다. 먼저 Git을 설치해주세요."
        exit 1
    fi
}

# 필요한 디렉토리 생성
create_directories() {
    log_info "필요한 디렉토리를 생성합니다..."
    
    mkdir -p projects
    mkdir -p logs
    mkdir -p static
    mkdir -p templates/partials
    
    log_success "디렉토리 생성 완료"
}

# Python 가상환경 설정
setup_python_env() {
    log_info "Python 가상환경을 설정합니다..."
    
    # 가상환경 생성
    if [ ! -d "venv" ]; then
        python3 -m venv venv
        log_success "가상환경 생성 완료"
    else
        log_warning "가상환경이 이미 존재합니다"
    fi
    
    # 가상환경 활성화
    source venv/bin/activate
    
    # pip 업그레이드
    pip install --upgrade pip
    
    # Python 의존성 설치
    if [ -f "requirements.txt" ]; then
        log_info "Python 패키지를 설치합니다..."
        pip install -r requirements.txt
        log_success "Python 패키지 설치 완료"
    else
        log_warning "requirements.txt 파일이 없습니다"
    fi
}

# Terraform 설치
install_terraform() {
    log_info "Terraform 설치를 확인합니다..."
    
    if command -v terraform &> /dev/null; then
        TERRAFORM_VERSION=$(terraform --version | head -n1 | cut -d' ' -f2)
        log_success "Terraform $TERRAFORM_VERSION 발견됨"
    else
        log_warning "Terraform이 설치되지 않았습니다"
        log_info "Terraform을 설치하려면 다음 명령을 실행하세요:"
        echo "curl -fsSL https://apt.releases.hashicorp.com/gpg | sudo apt-key add -"
        echo "sudo apt-add-repository \"deb [arch=amd64] https://apt.releases.hashicorp.com \$(lsb_release -cs) main\""
        echo "sudo apt update && sudo apt install terraform"
    fi
}

# Ansible 설치
install_ansible() {
    log_info "Ansible 설치를 확인합니다..."
    
    if command -v ansible &> /dev/null; then
        ANSIBLE_VERSION=$(ansible --version | head -n1 | cut -d' ' -f2)
        log_success "Ansible $ANSIBLE_VERSION 발견됨"
    else
        log_warning "Ansible이 설치되지 않았습니다"
        log_info "Ansible을 설치하려면 다음 명령을 실행하세요:"
        echo "sudo apt install ansible"
    fi
}

# 환경 설정 파일 생성
setup_env_file() {
    log_info "환경 설정 파일을 확인합니다..."
    
    if [ ! -f ".env" ]; then
        if [ -f "env_template.txt" ]; then
            cp env_template.txt .env
            log_success ".env 파일이 생성되었습니다"
            log_warning "⚠️  .env 파일을 수정하여 Proxmox 설정을 입력해주세요!"
        else
            log_error "env_template.txt 파일이 없습니다"
        fi
    else
        log_success ".env 파일이 이미 존재합니다"
    fi
}

# SSH 키 설정
setup_ssh_keys() {
    log_info "SSH 키를 확인합니다..."
    
    if [ ! -f ~/.ssh/id_rsa ]; then
        log_info "SSH 키를 생성합니다..."
        ssh-keygen -t rsa -b 4096 -f ~/.ssh/id_rsa -N "" -C "proxmox-manager"
        log_success "SSH 키 생성 완료"
    else
        log_success "SSH 키가 이미 존재합니다"
    fi
    
    # SSH 키 권한 설정
    chmod 600 ~/.ssh/id_rsa
    chmod 644 ~/.ssh/id_rsa.pub
    
    log_info "SSH 공개키:"
    cat ~/.ssh/id_rsa.pub
    echo ""
    log_warning "⚠️  이 공개키를 Proxmox에 등록해주세요!"
}

# Terraform 초기화
init_terraform() {
    log_info "Terraform을 초기화합니다..."
    
    if [ -d "terraform" ]; then
        cd terraform
        if [ -f "main.tf" ]; then
            terraform init -input=false
            log_success "Terraform 초기화 완료"
        else
            log_warning "terraform/main.tf 파일이 없습니다"
        fi
        cd ..
    else
        log_warning "terraform 디렉토리가 없습니다"
    fi
}

# 권한 설정
set_permissions() {
    log_info "파일 권한을 설정합니다..."
    
    chmod +x setup.sh
    chmod 600 .env 2>/dev/null || true
    
    log_success "권한 설정 완료"
}

# 설치 완료 메시지
show_completion_message() {
    echo ""
    echo "🎉 설치가 완료되었습니다!"
    echo ""
    echo "📋 다음 단계를 따라주세요:"
    echo ""
    echo "1️⃣  환경 설정:"
    echo "   nano .env"
    echo "   # Proxmox 서버 정보를 입력하세요"
    echo ""
    echo "2️⃣  SSH 키 등록:"
    echo "   # 위에 표시된 SSH 공개키를 Proxmox에 등록하세요"
    echo "   # Proxmox 웹 UI → Datacenter → SSH Keys"
    echo ""
    echo "3️⃣  애플리케이션 실행:"
    echo "   source venv/bin/activate"
    echo "   python app.py"
    echo ""
    echo "4️⃣  웹 브라우저에서 접속:"
    echo "   http://localhost:5000"
    echo "   # 기본 로그인: admin / admin123!"
    echo ""
    echo "📚 자세한 내용은 README.md 파일을 참조하세요."
    echo ""
}

# 메인 실행
main() {
    echo "🚀 Proxmox 서버 자동 생성 시스템 설치를 시작합니다..."
    echo ""
    
    check_system
    create_directories
    setup_python_env
    install_terraform
    install_ansible
    setup_env_file
    setup_ssh_keys
    init_terraform
    set_permissions
    show_completion_message
}

# 스크립트 실행
main "$@"
