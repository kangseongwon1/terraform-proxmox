#!/bin/bash

# ========================================
# Proxmox Manager 완전 통합 설치 스크립트
# ========================================
# 이 스크립트는 다음을 모두 자동으로 설치하고 설정합니다:
# - Python, pip, Node.js
# - Docker, Docker Compose
# - Terraform, Ansible
# - Vault (Docker)
# - Grafana, Prometheus, Node Exporter
# - Flask 애플리케이션
# - 모든 환경변수 설정
# - 데이터베이스 초기화
# - 보안 설정

set -e  # 오류 발생 시 스크립트 중단

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 로그 함수들
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

log_step() {
    echo -e "${PURPLE}[STEP]${NC} $1"
}

# ========================================
# 0. 사전 검증
# ========================================

pre_validation() {
    log_step "0. 사전 검증 중..."
    
    # 필수 파일 확인
    REQUIRED_FILES=(
        "env_template.txt"
        "requirements.txt"
        "vault.sh"
        "docker-compose.vault.yml"
        "vault-dev.hcl"
        "create_tables.py"
        "update_prometheus_targets.py"
    )
    
    MISSING_FILES=()
    
    for file in "${REQUIRED_FILES[@]}"; do
        if [ ! -f "$file" ]; then
            MISSING_FILES+=("$file")
        fi
    done
    
    if [ ${#MISSING_FILES[@]} -gt 0 ]; then
        log_error "❌ 필수 파일이 누락되었습니다:"
        for file in "${MISSING_FILES[@]}"; do
            log_error "   - $file"
        done
        log_error ""
        log_error "모든 필수 파일이 있는지 확인하고 다시 실행하세요."
        exit 1
    fi
    
    # .env 파일이 이미 존재하는 경우 검증
    if [ -f ".env" ]; then
        log_info "기존 .env 파일 발견. 내용을 검증합니다..."
        source .env
        
        # 필수 변수 확인
        if [ -z "$PROXMOX_ENDPOINT" ] || [ -z "$PROXMOX_USERNAME" ] || [ -z "$PROXMOX_PASSWORD" ] || \
           [ "$PROXMOX_ENDPOINT" = "your_proxmox_endpoint" ] || \
           [ "$PROXMOX_USERNAME" = "your_proxmox_username" ] || \
           [ "$PROXMOX_PASSWORD" = "your_proxmox_password" ]; then
            log_warning "⚠️  .env 파일에 기본값이 있습니다. 대화형으로 설정하시겠습니까? (y/n)"
            read -r response
            if [[ "$response" =~ ^[Yy]$ ]]; then
                log_info "기존 .env 파일을 백업합니다..."
                cp .env .env.backup.$(date +%Y%m%d_%H%M%S)
                rm .env
            else
                log_error "❌ .env 파일의 필수 정보를 수정한 후 다시 실행하세요."
                exit 1
            fi
        else
            log_success "기존 .env 파일이 올바르게 설정되어 있습니다."
        fi
    fi
    
    log_success "사전 검증 완료"
}

# ========================================
# 1. 시스템 정보 확인 및 준비
# ========================================

check_system() {
    log_step "1. 시스템 정보 확인 중..."
    
    # OS 확인
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS=$NAME
        VERSION=$VERSION_ID
        log_info "OS: $OS $VERSION"
    else
        log_error "OS 정보를 확인할 수 없습니다"
        exit 1
    fi
    
    # 패키지 매니저 확인
    if command -v dnf &> /dev/null; then
        PKG_MANAGER="dnf"
    elif command -v yum &> /dev/null; then
        PKG_MANAGER="yum"
    elif command -v apt &> /dev/null; then
        PKG_MANAGER="apt"
    else
        log_error "지원되지 않는 패키지 매니저입니다"
        exit 1
    fi
    
    log_info "패키지 매니저: $PKG_MANAGER"
    
    # sudo 권한 확인
    if ! sudo -n true 2>/dev/null; then
        log_warning "sudo 권한이 필요합니다. 설치 중에 비밀번호를 입력해주세요."
    fi
    
    log_success "시스템 정보 확인 완료"
}

# ========================================
# 2. 필수 패키지 설치
# ========================================

install_essential_packages() {
    log_step "2. 필수 패키지 설치 중..."
    
    # 공통 필수 패키지
    ESSENTIAL_PACKAGES="curl wget git unzip tar gcc gcc-c++ make"
    
    if [ "$PKG_MANAGER" = "dnf" ] || [ "$PKG_MANAGER" = "yum" ]; then
        # RedHat 계열 (Rocky, CentOS, RHEL)
        log_info "RedHat 계열 패키지 설치 중..."
        sudo $PKG_MANAGER update -y
        sudo $PKG_MANAGER groupinstall -y "Development Tools"
        sudo $PKG_MANAGER install -y $ESSENTIAL_PACKAGES python3 python3-pip python3-devel openssl-devel libffi-devel
    elif [ "$PKG_MANAGER" = "apt" ]; then
        # Debian 계열 (Ubuntu, Debian)
        log_info "Debian 계열 패키지 설치 중..."
        sudo apt update
        sudo apt install -y build-essential $ESSENTIAL_PACKAGES python3 python3-pip python3-dev libssl-dev libffi-dev
    fi
    
    log_success "필수 패키지 설치 완료"
}

# ========================================
# 3. Python 환경 설정
# ========================================

setup_python() {
    log_step "3. Python 3.12 설치 및 환경 설정 중..."
    
    # 현재 Python 버전 확인
    CURRENT_PYTHON=$(python3 --version 2>&1 | awk '{print $2}')
    log_info "현재 Python 버전: $CURRENT_PYTHON"
    
    # Python 3.12 설치 확인
    if command -v python3.12 &> /dev/null; then
        PYTHON312_VERSION=$(python3.12 --version 2>&1 | awk '{print $2}')
        log_info "Python 3.12 이미 설치됨: $PYTHON312_VERSION"
    else
        log_info "Python 3.12 설치 중..."
        
        if [ "$PKG_MANAGER" = "dnf" ] || [ "$PKG_MANAGER" = "yum" ]; then
    # RedHat 계열에서 Python 3.12 설치 (소스 빌드 방식)
    log_info "RedHat 계열에서 Python 3.12 소스 빌드 설치 중..."
    
    # 사용자 계정으로 설치 시도
    log_info "사용자 계정으로 Python 3.12 설치 시도 중..."
    install_python312_from_source
    
    # 설치 실패 시 sudo 권한으로 재시도
    if [ $? -ne 0 ]; then
        log_warning "사용자 계정 설치 실패, sudo 권한으로 재시도..."
        install_python312_from_source_sudo
    fi
            
        elif [ "$PKG_MANAGER" = "apt" ]; then
            # Debian 계열에서 Python 3.12 설치
            log_info "Debian 계열에서 Python 3.12 설치 중..."
            
            # deadsnakes PPA 추가 (Ubuntu)
            sudo apt update
            sudo apt install -y software-properties-common
            sudo add-apt-repository -y ppa:deadsnakes/ppa
            sudo apt update
            sudo apt install -y python3.12 python3.12-pip python3.12-venv python3.12-dev
            
            if [ $? -eq 0 ]; then
                log_success "Python 3.12 설치 완료"
            else
                log_warning "패키지 매니저로 Python 3.12 설치 실패, 소스에서 빌드 시도..."
                install_python312_from_source
            fi
        fi
    fi
    
    # Python 3.12 확인
    if command -v python3.12 &> /dev/null; then
        PYTHON312_VERSION=$(python3.12 --version 2>&1 | awk '{print $2}')
        log_success "Python 3.12 사용 가능: $PYTHON312_VERSION"
    else
        log_error "Python 3.12 설치 실패"
        exit 1
    fi
    
    # 가상환경 생성 (Python 3.12 사용)
    # 재설치 시에도 문제없이 작동하도록 기존 가상환경 정리
    if [ -d "venv" ]; then
        log_info "기존 가상환경 정리 중..."
        rm -rf venv
    fi
    
    log_info "Python 3.12로 가상환경 생성 중..."
    
    # Python 경로 확인 (python 명령어 우선, 없으면 python3.12)
    if command -v python &> /dev/null; then
        PYTHON_PATH=$(which python)
        PYTHON_VERSION=$(python --version 2>&1)
        log_info "Python 경로: $PYTHON_PATH"
        log_info "Python 버전: $PYTHON_VERSION"
        
        # Python 3.12인지 확인
        if [[ "$PYTHON_VERSION" == *"3.12"* ]]; then
            python -m venv venv
        else
            log_warning "python 명령어가 Python 3.12가 아닙니다: $PYTHON_VERSION"
            if command -v python3.12 &> /dev/null; then
                PYTHON_PATH=$(which python3.12)
                log_info "Python 3.12 경로로 재시도: $PYTHON_PATH"
                python3.12 -m venv venv
            else
                log_error "Python 3.12를 찾을 수 없습니다"
                exit 1
            fi
        fi
    elif command -v python3.12 &> /dev/null; then
        PYTHON_PATH=$(which python3.12)
        log_info "Python 3.12 경로: $PYTHON_PATH"
        python3.12 -m venv venv
    else
        log_error "Python을 찾을 수 없습니다"
        exit 1
    fi
    
    if [ $? -eq 0 ]; then
        log_success "가상환경 생성 완료"
    else
        log_error "가상환경 생성 실패"
        exit 1
    fi
    
    # 가상환경 활성화
    log_info "가상환경 활성화 중..."
    source venv/bin/activate
    
    # 가상환경에서 Python 버전 확인
    if command -v python &> /dev/null; then
        VENV_PYTHON_VERSION=$(python --version 2>&1)
        log_info "가상환경 Python 버전: $VENV_PYTHON_VERSION"
        
        if [[ "$VENV_PYTHON_VERSION" == *"3.12"* ]]; then
            log_success "가상환경이 Python 3.12를 사용합니다"
        else
            log_warning "가상환경이 Python 3.12가 아닙니다: $VENV_PYTHON_VERSION"
        fi
    else
        log_error "가상환경에서 python 명령어를 찾을 수 없습니다"
        exit 1
    fi
    
    # pip 업그레이드
    log_info "pip 업그레이드 중..."
    
    # 가상환경에서 Python 명령어 확인
    if command -v python &> /dev/null; then
        python -m pip install --upgrade pip
    elif command -v python3 &> /dev/null; then
        python3 -m pip install --upgrade pip
    elif command -v python3.12 &> /dev/null; then
        python3.12 -m pip install --upgrade pip
    else
        log_error "Python 명령어를 찾을 수 없습니다"
        exit 1
    fi
    
    if [ $? -eq 0 ]; then
        log_success "pip 업그레이드 완료"
    else
        log_warning "pip 업그레이드 실패 (계속 진행)"
    fi
    
    # Python 패키지 설치
    log_info "Python 패키지 설치 중..."
    pip install -r requirements.txt
    
    if [ $? -eq 0 ]; then
        log_success "Python 패키지 설치 완료"
    else
        log_error "Python 패키지 설치 실패"
        exit 1
    fi
    
    log_success "Python 3.12 환경 설정 완료"
}

install_python312_from_source() {
    log_info "소스에서 Python 3.12 빌드 중..."
    
    # 빌드 도구 설치
    if [ "$PKG_MANAGER" = "dnf" ] || [ "$PKG_MANAGER" = "yum" ]; then
        log_info "빌드 도구 설치 중..."
        sudo $PKG_MANAGER groupinstall -y "Development Tools"
        sudo $PKG_MANAGER install -y openssl-devel bzip2-devel libffi-devel zlib-devel readline-devel sqlite-devel wget gcc gcc-c++ make
    elif [ "$PKG_MANAGER" = "apt" ]; then
        sudo apt install -y build-essential libssl-dev libbz2-dev libffi-dev zlib1g-dev libreadline-dev libsqlite3-dev wget
    fi
    
    # 사용자 홈 디렉토리에 Python 설치
    PYTHON_INSTALL_DIR="$HOME/python3.12"
    PYTHON_BUILD_DIR="$HOME/python-build"
    
    log_info "Python 3.12.7 다운로드 중..."
    mkdir -p "$PYTHON_BUILD_DIR"
    cd "$PYTHON_BUILD_DIR"
    
    if [ ! -f "Python-3.12.7.tgz" ]; then
        wget https://www.python.org/ftp/python/3.12.7/Python-3.12.7.tgz
        
        if [ $? -eq 0 ]; then
            log_success "Python 3.12.7 다운로드 완료"
        else
            log_error "Python 3.12.7 다운로드 실패"
            exit 1
        fi
    else
        log_info "Python 3.12.7 이미 다운로드됨"
    fi
    
    log_info "압축 해제 중..."
    tar xzf Python-3.12.7.tgz
    cd Python-3.12.7
    
    log_info "컨피규어 실행 중..."
    ./configure --enable-optimizations --prefix="$PYTHON_INSTALL_DIR"
    
    if [ $? -eq 0 ]; then
        log_success "컨피규어 완료"
    else
        log_error "컨피규어 실패"
        exit 1
    fi
    
    log_info "컴파일 중... (시간이 걸릴 수 있습니다)"
    make -j $(nproc)
    
    if [ $? -eq 0 ]; then
        log_success "컴파일 완료"
    else
        log_error "컴파일 실패"
        exit 1
    fi
    
    log_info "설치 중..."
    make install
    
    if [ $? -eq 0 ]; then
        log_success "Python 3.12 소스 빌드 및 설치 완료"
    else
        log_error "Python 3.12 설치 실패"
        exit 1
    fi
    
    # PATH에 Python 3.12 추가
    log_info "PATH 설정 중..."
    echo "export PATH=\"$PYTHON_INSTALL_DIR/bin:\$PATH\"" >> ~/.bashrc
    export PATH="$PYTHON_INSTALL_DIR/bin:$PATH"
    
    # python 심볼릭 링크 생성 (python3.12 -> python)
    log_info "python 심볼릭 링크 생성 중..."
    ln -sf "$PYTHON_INSTALL_DIR/bin/python3.12" "$PYTHON_INSTALL_DIR/bin/python"
    ln -sf "$PYTHON_INSTALL_DIR/bin/python3.12" "$PYTHON_INSTALL_DIR/bin/python3"
    
    # 정리 (권한 문제 해결)
    log_info "빌드 파일 정리 중..."
    cd "$HOME"
    rm -rf "$PYTHON_BUILD_DIR"
    
    log_info "Python 3.12 설치 확인 중..."
    if command -v python3.12 &> /dev/null; then
        PYTHON312_VERSION=$(python3.12 --version 2>&1 | awk '{print $2}')
        log_success "Python 3.12 설치 확인: $PYTHON312_VERSION"
        log_info "Python 3.12 경로: $(which python3.12)"
        
        # python 명령어 확인
        if command -v python &> /dev/null; then
            log_success "python 명령어 사용 가능: $(which python)"
        else
            log_warning "python 명령어를 찾을 수 없습니다"
        fi
    else
        log_error "Python 3.12 설치 확인 실패"
        exit 1
    fi
}

install_python312_from_source_sudo() {
    log_info "sudo 권한으로 Python 3.12 소스 빌드 중..."
    
    # 빌드 도구 설치
    if [ "$PKG_MANAGER" = "dnf" ] || [ "$PKG_MANAGER" = "yum" ]; then
        log_info "빌드 도구 설치 중..."
        sudo $PKG_MANAGER groupinstall -y "Development Tools"
        sudo $PKG_MANAGER install -y openssl-devel bzip2-devel libffi-devel zlib-devel readline-devel sqlite-devel wget gcc gcc-c++ make
    elif [ "$PKG_MANAGER" = "apt" ]; then
        sudo apt install -y build-essential libssl-dev libbz2-dev libffi-dev zlib1g-dev libreadline-dev libsqlite3-dev wget
    fi
    
    # /tmp 대신 사용자 홈 디렉토리 사용
    PYTHON_BUILD_DIR="$HOME/python-build"
    PYTHON_INSTALL_DIR="/usr/local"
    
    log_info "Python 3.12.7 다운로드 중..."
    mkdir -p "$PYTHON_BUILD_DIR"
    cd "$PYTHON_BUILD_DIR"
    
    if [ ! -f "Python-3.12.7.tgz" ]; then
        wget https://www.python.org/ftp/python/3.12.7/Python-3.12.7.tgz
        
        if [ $? -eq 0 ]; then
            log_success "Python 3.12.7 다운로드 완료"
        else
            log_error "Python 3.12.7 다운로드 실패"
            exit 1
        fi
    else
        log_info "Python 3.12.7 이미 다운로드됨"
    fi
    
    log_info "압축 해제 중..."
    tar xzf Python-3.12.7.tgz
    cd Python-3.12.7
    
    log_info "컨피규어 실행 중..."
    ./configure --enable-optimizations --prefix="$PYTHON_INSTALL_DIR"
    
    if [ $? -eq 0 ]; then
        log_success "컨피규어 완료"
    else
        log_error "컨피규어 실패"
        exit 1
    fi
    
    log_info "컴파일 중... (시간이 걸릴 수 있습니다)"
    make -j $(nproc)
    
    if [ $? -eq 0 ]; then
        log_success "컴파일 완료"
    else
        log_error "컴파일 실패"
        exit 1
    fi
    
    log_info "설치 중..."
    sudo make altinstall
    
    if [ $? -eq 0 ]; then
        log_success "Python 3.12 소스 빌드 및 설치 완료"
    else
        log_error "Python 3.12 설치 실패"
        exit 1
    fi
    
    # python 심볼릭 링크 생성 (python3.12 -> python)
    log_info "python 심볼릭 링크 생성 중..."
    sudo ln -sf "$PYTHON_INSTALL_DIR/bin/python3.12" "$PYTHON_INSTALL_DIR/bin/python"
    sudo ln -sf "$PYTHON_INSTALL_DIR/bin/python3.12" "$PYTHON_INSTALL_DIR/bin/python3"
    
    # 정리 (권한 문제 해결)
    log_info "빌드 파일 정리 중..."
    cd "$HOME"
    sudo rm -rf "$PYTHON_BUILD_DIR"
    
    log_info "Python 3.12 설치 확인 중..."
    if command -v python3.12 &> /dev/null; then
        PYTHON312_VERSION=$(python3.12 --version 2>&1 | awk '{print $2}')
        log_success "Python 3.12 설치 확인: $PYTHON312_VERSION"
        log_info "Python 3.12 경로: $(which python3.12)"
        
        # python 명령어 확인
        if command -v python &> /dev/null; then
            log_success "python 명령어 사용 가능: $(which python)"
        else
            log_warning "python 명령어를 찾을 수 없습니다"
        fi
    else
        log_error "Python 3.12 설치 확인 실패"
        exit 1
    fi
}

# ========================================
# 4. Node.js 설치
# ========================================

install_nodejs() {
    log_step "4. Node.js 설치 중..."
    
    # Node.js 설치 확인 및 재설치 지원
    if command -v node &> /dev/null; then
        NODE_VERSION=$(node --version)
        NODE_MAJOR_VERSION=$(echo $NODE_VERSION | cut -d'.' -f1 | sed 's/v//')
        
        # Node.js 18 이하인 경우 재설치 (20+ 권장)
        if [ "$NODE_MAJOR_VERSION" -lt 20 ]; then
            log_info "Node.js $NODE_VERSION 감지, 20 LTS로 업그레이드 중..."
        else
            log_info "Node.js 이미 설치됨: $NODE_VERSION"
        fi
    else
        log_info "Node.js 설치 중..."
        
        if [ "$PKG_MANAGER" = "dnf" ] || [ "$PKG_MANAGER" = "yum" ]; then
            # NodeSource 저장소 추가 (Node.js 20 LTS)
            curl -fsSL https://rpm.nodesource.com/setup_20.x | sudo bash -
            sudo $PKG_MANAGER install -y nodejs
        elif [ "$PKG_MANAGER" = "apt" ]; then
            # NodeSource 저장소 추가 (Node.js 20 LTS)
            curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
            sudo apt install -y nodejs
        fi
    fi
    
    # Node.js 18 이하인 경우 재설치
    if [ "$NODE_MAJOR_VERSION" -lt 20 ]; then
        log_info "Node.js 20 LTS로 재설치 중..."
        
        if [ "$PKG_MANAGER" = "dnf" ] || [ "$PKG_MANAGER" = "yum" ]; then
            # 기존 Node.js 제거
            sudo $PKG_MANAGER remove -y nodejs npm
            # NodeSource 저장소 추가 (Node.js 20 LTS)
            curl -fsSL https://rpm.nodesource.com/setup_20.x | sudo bash -
            sudo $PKG_MANAGER install -y nodejs
        elif [ "$PKG_MANAGER" = "apt" ]; then
            # 기존 Node.js 제거
            sudo apt remove -y nodejs npm
            # NodeSource 저장소 추가 (Node.js 20 LTS)
            curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
            sudo apt install -y nodejs
        fi
        
        NODE_VERSION=$(node --version)
        log_info "Node.js 설치 완료: $NODE_VERSION"
    fi
    
    # npm 버전 확인 및 업그레이드
    NPM_VERSION=$(npm --version)
    log_info "현재 npm 버전: $NPM_VERSION"
    
    # Node.js 버전에 따른 npm 업그레이드
    NODE_MAJOR_VERSION=$(echo $NODE_VERSION | cut -d'.' -f1 | sed 's/v//')
    
    if [ "$NODE_MAJOR_VERSION" -ge 20 ]; then
        log_info "Node.js 20+ 감지, npm 최신 버전으로 업그레이드 중..."
        sudo npm install -g npm@latest
    else
        log_info "Node.js 18 감지, 호환되는 npm 버전으로 업그레이드 중..."
        sudo npm install -g npm@10
    fi
    
    # 업그레이드 후 npm 버전 확인
    NEW_NPM_VERSION=$(npm --version)
    log_info "업그레이드된 npm 버전: $NEW_NPM_VERSION"
    
    log_success "Node.js 설치 완료"
}

# ========================================
# 5. Docker 설치
# ========================================

install_docker() {
    log_step "5. Docker 설치 중..."
    
    # Docker 설치 확인
    if command -v docker &> /dev/null; then
        DOCKER_VERSION=$(docker --version)
        log_info "Docker 이미 설치됨: $DOCKER_VERSION"
    else
        log_info "Docker 설치 중..."
        
        if [ "$PKG_MANAGER" = "dnf" ] || [ "$PKG_MANAGER" = "yum" ]; then
            # Docker 저장소 추가
            sudo $PKG_MANAGER config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
            sudo $PKG_MANAGER install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
        elif [ "$PKG_MANAGER" = "apt" ]; then
            # Docker 저장소 추가
            sudo apt update
            sudo apt install -y ca-certificates curl gnupg lsb-release
            sudo mkdir -p /etc/apt/keyrings
            curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
            echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
            sudo apt update
            sudo apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
        fi
        
        # Docker 서비스 시작 및 활성화
        sudo systemctl start docker
        sudo systemctl enable docker
        
        # 현재 사용자를 docker 그룹에 추가
        sudo usermod -aG docker $USER
        
        DOCKER_VERSION=$(docker --version)
        log_info "Docker 설치 완료: $DOCKER_VERSION"
    fi
    
    # Docker Compose 확인
    if command -v docker-compose &> /dev/null; then
        COMPOSE_VERSION=$(docker-compose --version)
        log_info "Docker Compose: $COMPOSE_VERSION"
    else
        log_warning "Docker Compose가 설치되지 않았습니다"
    fi
    
    log_success "Docker 설치 완료"
}

# ========================================
# 6. Terraform 설치
# ========================================

install_terraform() {
    log_step "6. Terraform 설치 중..."
    
    # Terraform 설치 확인 및 재설치 지원
    if command -v terraform &> /dev/null; then
        TERRAFORM_VERSION=$(terraform --version | head -n1)
        log_info "Terraform 이미 설치됨: $TERRAFORM_VERSION"
        log_info "Terraform 재설치를 위해 기존 설치 제거 중..."
        
        # 기존 Terraform 제거
        sudo rm -f /usr/local/bin/terraform
    fi
    
    log_info "Terraform 설치 중..."
    
    # 최신 버전 다운로드
    TERRAFORM_VERSION=$(curl -s https://api.github.com/repos/hashicorp/terraform/releases/latest | grep tag_name | cut -d '"' -f 4)
    TERRAFORM_VERSION=${TERRAFORM_VERSION#v}  # v 제거
    
    # 아키텍처 확인
    ARCH=$(uname -m)
    case $ARCH in
        x86_64) ARCH="amd64" ;;
        aarch64) ARCH="arm64" ;;
        *) log_error "지원되지 않는 아키텍처: $ARCH"; exit 1 ;;
    esac
    
    # 다운로드 및 설치
    wget -O terraform.zip "https://releases.hashicorp.com/terraform/${TERRAFORM_VERSION}/terraform_${TERRAFORM_VERSION}_linux_${ARCH}.zip"
    
    # 기존 terraform 디렉토리/파일 정리 (재설치 지원)
    if [ -d "terraform" ]; then
        log_info "기존 terraform 디렉토리 정리 중..."
        rm -rf terraform
    fi
    
    if [ -f "terraform" ]; then
        log_info "기존 terraform 파일 정리 중..."
        rm -f terraform
    fi
    
    # 압축 해제
    log_info "Terraform 압축 해제 중..."
    unzip -o terraform.zip
    
    # 설치
    if [ -f "terraform" ]; then
        sudo mv terraform /usr/local/bin/
        sudo chmod +x /usr/local/bin/terraform
        log_success "Terraform 바이너리 설치 완료"
    else
        log_error "Terraform 바이너리를 찾을 수 없습니다"
        exit 1
    fi
    
    # 정리
    rm -f terraform.zip
    
    TERRAFORM_VERSION=$(terraform --version | head -n1)
    log_info "Terraform 설치 완료: $TERRAFORM_VERSION"
    
    log_success "Terraform 설치 완료"
}

# ========================================
# 7. Ansible 설치
# ========================================

install_ansible() {
    log_step "7. Ansible 설치 중..."
    
    # Ansible 설치 확인
    if command -v ansible &> /dev/null; then
        ANSIBLE_VERSION=$(ansible --version | head -n1)
        log_info "Ansible 이미 설치됨: $ANSIBLE_VERSION"
    else
        log_info "Ansible 설치 중..."
        
        if [ "$PKG_MANAGER" = "dnf" ] || [ "$PKG_MANAGER" = "yum" ]; then
            # EPEL 저장소 추가
            sudo $PKG_MANAGER install -y epel-release
            sudo $PKG_MANAGER install -y ansible
        elif [ "$PKG_MANAGER" = "apt" ]; then
            sudo apt update
            sudo apt install -y ansible
        fi
        
        ANSIBLE_VERSION=$(ansible --version | head -n1)
        log_info "Ansible 설치 완료: $ANSIBLE_VERSION"
    fi
    
    log_success "Ansible 설치 완료"
}

# ========================================
# 8. 환경변수 파일 설정 및 검증
# ========================================

setup_environment() {
    log_step "8. 환경변수 파일 설정 및 검증 중..."
    
    # .env 파일 확인
    if [ ! -f ".env" ]; then
        log_info ".env 파일 생성 중..."
        cp env_template.txt .env
        
        log_warning "⚠️  .env 파일을 생성했습니다. 필수 정보를 입력해주세요:"
        echo ""
        
        # 필수 정보 입력
        read -p "Proxmox 서버 주소를 입력하세요 (예: https://prox.dmcmedia.co.kr:8006): " PROXMOX_ENDPOINT
        read -p "Proxmox 사용자명을 입력하세요 (예: root@pam): " PROXMOX_USERNAME
        read -s -p "Proxmox 비밀번호를 입력하세요: " PROXMOX_PASSWORD
        echo
        
        # 입력값 검증
        if [ -z "$PROXMOX_ENDPOINT" ] || [ -z "$PROXMOX_USERNAME" ] || [ -z "$PROXMOX_PASSWORD" ]; then
            log_error "❌ 필수 정보가 누락되었습니다. 설치를 중단합니다."
            log_error "   - PROXMOX_ENDPOINT: $([ -z "$PROXMOX_ENDPOINT" ] && echo "누락" || echo "입력됨")"
            log_error "   - PROXMOX_USERNAME: $([ -z "$PROXMOX_USERNAME" ] && echo "누락" || echo "입력됨")"
            log_error "   - PROXMOX_PASSWORD: $([ -z "$PROXMOX_PASSWORD" ] && echo "누락" || echo "입력됨")"
            exit 1
        fi
        
        # .env 파일 업데이트
        sed -i "s|PROXMOX_ENDPOINT=.*|PROXMOX_ENDPOINT=$PROXMOX_ENDPOINT|" .env
        sed -i "s|PROXMOX_USERNAME=.*|PROXMOX_USERNAME=$PROXMOX_USERNAME|" .env
        sed -i "s|PROXMOX_PASSWORD=.*|PROXMOX_PASSWORD=$PROXMOX_PASSWORD|" .env
        
        log_success ".env 파일 설정 완료"
    else
        log_info ".env 파일이 이미 존재합니다"
    fi
    
    # .env 파일 로드
    source .env
    
    # 필수 환경변수 검증
    log_info "필수 환경변수 검증 중..."
    
    REQUIRED_VARS=(
        "PROXMOX_ENDPOINT"
        "PROXMOX_USERNAME" 
        "PROXMOX_PASSWORD"
    )
    
    MISSING_VARS=()
    
    for var in "${REQUIRED_VARS[@]}"; do
        if [ -z "${!var}" ] || [ "${!var}" = "your_proxmox_endpoint" ] || [ "${!var}" = "your_proxmox_username" ] || [ "${!var}" = "your_proxmox_password" ]; then
            MISSING_VARS+=("$var")
        fi
    done
    
    if [ ${#MISSING_VARS[@]} -gt 0 ]; then
        log_error "❌ 필수 환경변수가 설정되지 않았습니다:"
        for var in "${MISSING_VARS[@]}"; do
            log_error "   - $var: ${!var:-'설정되지 않음'}"
        done
        log_error ""
        log_error "다음 중 하나를 선택하세요:"
        log_error "1. .env 파일을 수정하여 필수 정보를 설정한 후 다시 실행"
        log_error "2. 이 스크립트를 다시 실행하여 대화형으로 설정"
        log_error ""
        log_error "설치를 중단합니다."
        exit 1
    fi
    
    log_success "모든 필수 환경변수가 설정되었습니다"
    log_success "환경변수 설정 완료"
}

# ========================================
# 9. Vault 설정
# ========================================

setup_vault() {
    log_step "9. Vault 설정 중..."
    
    # Vault 관련 환경변수 검증
    log_info "Vault 설정을 위한 환경변수 검증 중..."
    
    VAULT_REQUIRED_VARS=(
        "PROXMOX_PASSWORD"
    )
    
    VAULT_MISSING_VARS=()
    
    for var in "${VAULT_REQUIRED_VARS[@]}"; do
        if [ -z "${!var}" ] || [ "${!var}" = "your_proxmox_password" ]; then
            VAULT_MISSING_VARS+=("$var")
        fi
    done
    
    if [ ${#VAULT_MISSING_VARS[@]} -gt 0 ]; then
        log_error "❌ Vault 설정을 위한 필수 환경변수가 누락되었습니다:"
        for var in "${VAULT_MISSING_VARS[@]}"; do
            log_error "   - $var: ${!var:-'설정되지 않음'}"
        done
        log_error ""
        log_error "Vault는 Proxmox 비밀번호를 안전하게 저장하기 위해 필요합니다."
        log_error "설치를 중단합니다."
        exit 1
    fi
    
    # Vault 스크립트 실행
    if [ -f "vault.sh" ]; then
        log_info "Vault 설정 스크립트 실행 중..."
        chmod +x vault.sh
        ./vault.sh
        
        if [ $? -eq 0 ]; then
            log_success "Vault 설정 완료"
        else
            log_error "Vault 설정 실패"
            exit 1
        fi
    else
        log_error "vault.sh 파일을 찾을 수 없습니다"
        exit 1
    fi
}

# ========================================
# 10. 모니터링 시스템 설치
# ========================================

install_monitoring() {
    log_step "10. 모니터링 시스템 설치 중..."
    
    # Prometheus 설치
    if [ -f "install_prometheus.sh" ]; then
        log_info "Prometheus 설치 중..."
        chmod +x install_prometheus.sh
        ./install_prometheus.sh
        
        if [ $? -eq 0 ]; then
            log_success "Prometheus 설치 완료"
        else
            log_warning "Prometheus 설치 실패 (계속 진행)"
        fi
    fi
    
    # Grafana 설정
    if [ -f "setup_grafana_anonymous.sh" ]; then
        log_info "Grafana 설정 중..."
        chmod +x setup_grafana_anonymous.sh
        ./setup_grafana_anonymous.sh
        
        if [ $? -eq 0 ]; then
            log_success "Grafana 설정 완료"
        else
            log_warning "Grafana 설정 실패 (계속 진행)"
        fi
    fi
    
    # Prometheus 타겟 업데이트 스크립트 권한 설정
    if [ -f "update_prometheus_targets.py" ]; then
        log_info "Prometheus 타겟 업데이트 스크립트 설정 중..."
        chmod +x update_prometheus_targets.py
        
        # PyYAML 설치 확인 (스크립트 실행에 필요)
        source venv/bin/activate
        pip install PyYAML requests
        
        log_success "Prometheus 타겟 업데이트 스크립트 설정 완료"
    fi
    
    log_success "모니터링 시스템 설치 완료"
}

# ========================================
# 11. 데이터베이스 초기화
# ========================================

setup_database() {
    log_step "11. 데이터베이스 초기화 중..."
    
    # instance 디렉토리 생성
    if [ ! -d "instance" ]; then
        log_info "instance 디렉토리 생성 중..."
        mkdir -p instance
    fi
    
    # 기존 데이터베이스 백업 (재설치 지원)
    if [ -f "instance/proxmox_manager.db" ]; then
        log_info "기존 데이터베이스 백업 중..."
        cp instance/proxmox_manager.db instance/proxmox_manager.db.backup.$(date +%Y%m%d_%H%M%S)
        log_success "데이터베이스 백업 완료"
    fi
    
    # 가상환경 활성화
    source venv/bin/activate
    
    # 데이터베이스 테이블 생성
    if [ -f "create_tables.py" ]; then
        log_info "데이터베이스 테이블 생성 중..."
        python3 create_tables.py
        
        if [ $? -eq 0 ]; then
            log_success "데이터베이스 테이블 생성 완료"
            
            # 데이터베이스 파일 확인
            if [ -f "instance/proxmox_manager.db" ]; then
                log_success "데이터베이스 파일 생성 확인: instance/proxmox_manager.db"
            else
                log_warning "데이터베이스 파일이 생성되지 않았습니다"
            fi
        else
            log_warning "데이터베이스 테이블 생성 실패 (계속 진행)"
        fi
    else
        log_error "create_tables.py 파일을 찾을 수 없습니다"
        exit 1
    fi
    
    log_success "데이터베이스 초기화 완료"
}

# ========================================
# 12. 보안 설정
# ========================================

setup_security() {
    log_step "12. 보안 설정 중..."
    
    # 방화벽 설정 (RedHat 계열)
    if [ "$PKG_MANAGER" = "dnf" ] || [ "$PKG_MANAGER" = "yum" ]; then
        if command -v firewall-cmd &> /dev/null; then
            log_info "방화벽 포트 설정 중..."
            sudo firewall-cmd --permanent --add-port=5000/tcp  # Flask
            sudo firewall-cmd --permanent --add-port=3000/tcp  # Grafana
            sudo firewall-cmd --permanent --add-port=9090/tcp  # Prometheus
            sudo firewall-cmd --permanent --add-port=8200/tcp  # Vault
            sudo firewall-cmd --reload
            log_success "방화벽 설정 완료"
        fi
    fi
    
    # SSH 키 생성 (없는 경우)
    if [ ! -f ~/.ssh/id_rsa ]; then
        log_info "SSH 키 생성 중..."
        ssh-keygen -t rsa -b 4096 -f ~/.ssh/id_rsa -N ""
        log_success "SSH 키 생성 완료"
    fi
    
    log_success "보안 설정 완료"
}

# ========================================
# 13. 서비스 시작
# ========================================

start_services() {
    log_step "13. 서비스 시작 중..."
    
    # Vault 서비스 시작
    if [ -f "docker-compose.vault.yml" ]; then
        log_info "Vault 서비스 시작 중..."
        docker-compose -f docker-compose.vault.yml up -d
        
        if [ $? -eq 0 ]; then
            log_success "Vault 서비스 시작 완료"
        else
            log_warning "Vault 서비스 시작 실패"
        fi
    fi
    
    # Flask 애플리케이션 시작 (백그라운드)
    log_info "Flask 애플리케이션 시작 중..."
    nohup python3 run.py > app.log 2>&1 &
    FLASK_PID=$!
    echo $FLASK_PID > flask.pid
    
    # 서비스 시작 확인
    sleep 5
    if ps -p $FLASK_PID > /dev/null; then
        log_success "Flask 애플리케이션 시작 완료 (PID: $FLASK_PID)"
    else
        log_warning "Flask 애플리케이션 시작 실패"
    fi
    
    log_success "서비스 시작 완료"
}

# ========================================
# 14. 설치 완료 및 정보 출력
# ========================================

show_completion_info() {
    log_step "14. 설치 완료!"
    
    echo -e "${GREEN}"
    echo "=========================================="
    echo "🎉 Proxmox Manager 설치 완료!"
    echo "=========================================="
    echo -e "${NC}"
    
    echo -e "${CYAN}📋 설치된 구성요소:${NC}"
    echo "  ✅ Python 환경 및 Flask 애플리케이션"
    echo "  ✅ Docker 및 Docker Compose"
    echo "  ✅ Terraform"
    echo "  ✅ Ansible"
    echo "  ✅ HashiCorp Vault"
    echo "  ✅ Prometheus (모니터링)"
    echo "  ✅ Grafana (대시보드)"
    echo "  ✅ Node Exporter"
    echo "  ✅ 데이터베이스"
    echo "  ✅ 보안 설정"
    
    echo ""
    echo -e "${CYAN}🌐 접속 정보:${NC}"
    echo "  📱 웹 관리 콘솔: http://$(hostname -I | awk '{print $1}'):5000"
    echo "  📊 Grafana 대시보드: http://$(hostname -I | awk '{print $1}'):3000"
    echo "  📈 Prometheus: http://$(hostname -I | awk '{print $1}'):9090"
    echo "  🔐 Vault: http://$(hostname -I | awk '{print $1}'):8200"
    
    echo ""
    echo -e "${CYAN}🔧 관리 명령어:${NC}"
    echo "  서비스 상태 확인: ps aux | grep -E '(python|docker)'"
    echo "  Flask 로그 확인: tail -f app.log"
    echo "  Vault 상태 확인: docker exec vault-dev vault status"
    echo "  서비스 중지: kill \$(cat flask.pid) && docker-compose -f docker-compose.vault.yml down"
    
    echo ""
    echo -e "${CYAN}📁 중요 파일:${NC}"
    echo "  환경설정: .env"
    echo "  데이터베이스: instance/proxmox_manager.db"
    echo "  Vault 초기화: vault_init.txt"
    echo "  Flask 로그: app.log"
    echo "  서비스 PID: flask.pid"
    
    echo ""
    echo -e "${YELLOW}⚠️  다음 단계:${NC}"
    echo "  1. 웹 브라우저에서 관리 콘솔에 접속"
    echo "  2. .env 파일에서 추가 설정 확인"
    echo "  3. Proxmox 서버 연결 테스트"
    echo "  4. 첫 번째 VM 생성 테스트"
    
    echo ""
    echo -e "${GREEN}🚀 설치가 완료되었습니다!${NC}"
}

# ========================================
# 메인 실행 함수
# ========================================

main() {
    echo -e "${PURPLE}"
    echo "=========================================="
    echo "🚀 Proxmox Manager 완전 통합 설치 시작"
    echo "=========================================="
    echo "ℹ️  이 스크립트는 재설치에 안전합니다."
    echo "ℹ️  기존 설치가 있어도 자동으로 정리하고 재설치합니다."
    echo "=========================================="
    echo -e "${NC}"
    
    # 설치 단계 실행
    pre_validation
    check_system
    install_essential_packages
    setup_python
    install_nodejs
    install_docker
    install_terraform
    install_ansible
    setup_environment
    setup_vault
    install_monitoring
    setup_database
    setup_security
    start_services
    show_completion_info
    
    echo -e "${GREEN}✅ 모든 설치가 완료되었습니다!${NC}"
}

# 스크립트 실행
main "$@"
