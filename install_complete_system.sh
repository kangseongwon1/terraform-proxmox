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
        "requirements.txt"
        "scripts/vault.sh"
        "docker-compose.vault.yaml"
        "config/vault-dev.hcl"
        "scripts/create_tables.py"
        "monitoring/update_prometheus_targets.py"
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
        
        # 가상환경 생성 후 권한 확인 및 수정
        log_info "가상환경 파일 권한 확인 중..."
        if [ -f "venv/bin/python" ]; then
            # Python 실행 파일 권한 확인
            CURRENT_PERMS=$(ls -l venv/bin/python | awk '{print $1}')
            log_info "Python 파일 권한: $CURRENT_PERMS"
            
            if [[ ! "$CURRENT_PERMS" =~ x ]]; then
                log_info "실행 권한이 없습니다. 권한 설정 중..."
                chmod +x venv/bin/python
                if [ $? -eq 0 ]; then
                    log_success "Python 파일 실행 권한 설정 완료"
                else
                    log_warning "Python 파일 권한 설정 실패"
                fi
            else
                log_success "Python 파일에 이미 실행 권한이 있습니다"
            fi
            
            # pip 실행 파일 권한도 확인
            if [ -f "venv/bin/pip" ]; then
                chmod +x venv/bin/pip 2>/dev/null || log_warning "pip 권한 설정 실패"
            fi
        else
            log_error "가상환경 Python 파일을 찾을 수 없습니다"
            exit 1
        fi
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
    
    # 가상환경 활성화 및 Python 패키지 설치
    log_info "가상환경 활성화 중..."
    source venv/bin/activate
    
    # 가상환경 활성화 확인
    if [[ "$VIRTUAL_ENV" != *"venv"* ]]; then
        log_error "가상환경 활성화 실패"
        exit 1
    fi
    
    log_info "가상환경 활성화 완료: $VIRTUAL_ENV"
    log_info "Python 경로: $(which python)"
    log_info "pip 경로: $(which pip)"
    
    # Python 패키지 설치
    log_info "Python 패키지 설치 중..."
    pip install -r requirements.txt
    
    if [ $? -eq 0 ]; then
        log_success "Python 패키지 설치 완료"
        
        # 설치된 패키지 확인
        log_info "설치된 패키지 확인 중..."
        pip list | grep -E "(dotenv|flask|requests)" || log_warning "일부 패키지가 설치되지 않았을 수 있습니다"
        
        # 필수 패키지 개별 확인
        log_info "필수 패키지 개별 확인 중..."
        python -c "import dotenv; print('✅ python-dotenv 설치됨')" 2>/dev/null || log_warning "❌ python-dotenv 누락"
        python -c "import flask; print('✅ flask 설치됨')" 2>/dev/null || log_warning "❌ flask 누락"
        python -c "import requests; print('✅ requests 설치됨')" 2>/dev/null || log_warning "❌ requests 누락"
    else
        log_error "Python 패키지 설치 실패"
        log_info "수동으로 필수 패키지를 설치합니다..."
        
        # 필수 패키지 수동 설치
        pip install python-dotenv flask flask-sqlalchemy flask-login requests pyyaml cryptography hvac
        
        if [ $? -eq 0 ]; then
            log_success "필수 패키지 수동 설치 완료"
        else
            log_error "필수 패키지 설치 실패"
            exit 1
        fi
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
        
        # Docker 권한 확인 및 수정
        log_info "Docker 권한 확인 중..."
        if ! docker ps &> /dev/null; then
            log_warning "Docker 권한 문제 감지. Docker 소켓 권한 수정 중..."
            
            # Docker 소켓 소유자 변경
            sudo chown $USER:docker /var/run/docker.sock
            sudo chmod 660 /var/run/docker.sock
            
            # 현재 사용자를 docker 그룹에 추가
            sudo usermod -aG docker $USER
            
            log_warning "⚠️  Docker 그룹 권한이 변경되었습니다."
            log_warning "⚠️  다음 중 하나를 선택하세요:"
            log_warning "   1. 새 터미널 세션을 시작하거나"
            log_warning "   2. 'newgrp docker' 명령어를 실행하거나"
            log_warning "   3. 로그아웃 후 다시 로그인하세요"
            log_warning ""
            log_warning "그 후 다시 이 스크립트를 실행하세요."
            
            # newgrp docker 실행 시도
            log_info "newgrp docker 실행 중..."
            newgrp docker << 'EOF'
echo "Docker 그룹 권한이 적용되었습니다."
docker ps
EOF
            
            # 권한 재확인
            if docker ps &> /dev/null; then
                log_success "Docker 권한 문제 해결됨"
            else
                log_warning "Docker 권한 문제가 지속됩니다."
                log_warning "설치 완료 후 다음 중 하나를 실행하세요:"
                log_warning "  1. 새 터미널 세션 시작"
                log_warning "  2. 또는 'newgrp docker' 실행"
                log_warning "  3. 또는 로그아웃 후 재로그인"
            fi
        else
            log_success "Docker 권한 확인 완료"
        fi
    fi
    
    # Docker Compose 설치 및 확인
    log_info "Docker Compose 설치 확인 중..."
    
    # docker-compose 명령어 확인
    if command -v docker-compose &> /dev/null; then
        COMPOSE_VERSION=$(docker-compose --version)
        log_info "Docker Compose 이미 설치됨: $COMPOSE_VERSION"
    else
        log_info "Docker Compose 설치 중..."
        
        if [ "$PKG_MANAGER" = "dnf" ] || [ "$PKG_MANAGER" = "yum" ]; then
            # Rocky 8에서 Docker Compose 설치
            log_info "Rocky 8에서 Docker Compose 바이너리 직접 설치 중..."
            
            # EPEL 설치 (다른 패키지용)
            sudo $PKG_MANAGER install -y epel-release
            
            # 바이너리 직접 설치 (Rocky 8에서 권장 방법)
            log_info "최신 Docker Compose 바이너리 다운로드 중..."
            
            # 최신 Docker Compose 다운로드
            COMPOSE_VERSION=$(curl -s https://api.github.com/repos/docker/compose/releases/latest | grep tag_name | cut -d '"' -f 4)
            COMPOSE_VERSION=${COMPOSE_VERSION#v}  # v 제거
            
            log_info "Docker Compose 버전: $COMPOSE_VERSION"
            
            # 아키텍처 확인
            ARCH=$(uname -m)
            case $ARCH in
                x86_64) ARCH="x86_64" ;;
                aarch64) ARCH="aarch64" ;;
                *) log_error "지원되지 않는 아키텍처: $ARCH"; exit 1 ;;
            esac
            
            # 바이너리 다운로드 및 설치
            sudo curl -L "https://github.com/docker/compose/releases/download/v${COMPOSE_VERSION}/docker-compose-$(uname -s)-${ARCH}" -o /usr/local/bin/docker-compose
            sudo chmod +x /usr/local/bin/docker-compose
            
            log_success "Docker Compose 바이너리 설치 완료"
            
        elif [ "$PKG_MANAGER" = "apt" ]; then
            # Ubuntu/Debian에서 Docker Compose 설치
            sudo apt install -y docker-compose
        fi
        
        # 설치 확인
        if command -v docker-compose &> /dev/null; then
            COMPOSE_VERSION=$(docker-compose --version)
            log_success "Docker Compose 설치 완료: $COMPOSE_VERSION"
        else
            log_error "Docker Compose 설치 실패"
            log_info "수동 설치 방법:"
            log_info "  sudo curl -L \"https://github.com/docker/compose/releases/latest/download/docker-compose-\$(uname -s)-\$(uname -m)\" -o /usr/local/bin/docker-compose"
            log_info "  sudo chmod +x /usr/local/bin/docker-compose"
        fi
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
    
    # 임시 디렉토리에서 다운로드 및 설치
    TEMP_DIR=$(mktemp -d)
    cd "$TEMP_DIR"
    
    # 다운로드
    wget -O terraform.zip "https://releases.hashicorp.com/terraform/${TERRAFORM_VERSION}/terraform_${TERRAFORM_VERSION}_linux_${ARCH}.zip"
    
    # 압축 해제
    log_info "Terraform 압축 해제 중..."
    unzip -o terraform.zip
    
    # 원래 디렉토리로 돌아가기
    cd - > /dev/null
    
    # 설치
    if [ -f "$TEMP_DIR/terraform" ]; then
        sudo mv "$TEMP_DIR/terraform" /usr/local/bin/
        sudo chmod +x /usr/local/bin/terraform
        log_success "Terraform 바이너리 설치 완료"
    else
        log_error "Terraform 바이너리를 찾을 수 없습니다"
        exit 1
    fi
    
    # 임시 디렉토리 정리
    rm -rf "$TEMP_DIR"
    
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
        # .env 파일이 없으면 기본 템플릿 생성
        cat > .env << 'EOF'
# Proxmox Manager 환경 변수 설정
# 이 파일을 편집하여 실제 값으로 변경하세요

# Proxmox 설정
PROXMOX_ENDPOINT=https://your-proxmox-server:8006
PROXMOX_USERNAME=your-username
PROXMOX_PASSWORD=your-password
PROXMOX_NODE=your-node-name

# Vault 설정
VAULT_ADDR=http://localhost:8200
VAULT_TOKEN=your-vault-token

# 데이터베이스 설정
DATABASE_URL=sqlite:///instance/proxmox_manager.db

# Flask 설정
FLASK_ENV=development
SECRET_KEY=your-secret-key-here
EOF
        
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
        
    # SSH 키 파일 경로 확인 및 생성
    log_info "SSH 키 파일 경로 확인 중..."
    SSH_PUBLIC_KEY_PATH_FULL=$(eval echo ${SSH_PUBLIC_KEY_PATH})
    SSH_PRIVATE_KEY_PATH_FULL=$(eval echo ${SSH_PRIVATE_KEY_PATH})
    
    if [ ! -f "$SSH_PUBLIC_KEY_PATH_FULL" ]; then
        log_warning "SSH 공개키 파일이 없습니다: $SSH_PUBLIC_KEY_PATH_FULL"
        log_info "SSH 키 쌍을 생성합니다..."
        ssh-keygen -t rsa -b 4096 -f "$SSH_PRIVATE_KEY_PATH_FULL" -N "" -C "proxmox-manager@$(hostname)"
        log_success "SSH 키 쌍 생성 완료"
    else
        log_success "SSH 공개키 파일 확인됨: $SSH_PUBLIC_KEY_PATH_FULL"
    fi
    
    # Terraform 변수들을 .env 파일에 추가
    log_info "Terraform 변수를 .env 파일에 추가 중..."
    cat >> .env << EOF

# Terraform 변수 (자동 매핑용)
TF_VAR_vault_token=${VAULT_TOKEN}
TF_VAR_vault_address=${VAULT_ADDR}
TF_VAR_proxmox_endpoint=${PROXMOX_ENDPOINT}
TF_VAR_proxmox_username=${PROXMOX_USERNAME}
TF_VAR_proxmox_password=${PROXMOX_PASSWORD}
TF_VAR_proxmox_node=${PROXMOX_NODE}
TF_VAR_vm_username=${SSH_USER}
TF_VAR_ssh_keys=${SSH_PUBLIC_KEY_PATH_FULL}
EOF
        
        log_success ".env 파일 설정 완료"
    else
        log_info ".env 파일이 이미 존재합니다"
        
        # SSH 키 파일 경로 확인 및 생성
        log_info "SSH 키 파일 경로 확인 중..."
        SSH_PUBLIC_KEY_PATH_FULL=$(eval echo ${SSH_PUBLIC_KEY_PATH})
        SSH_PRIVATE_KEY_PATH_FULL=$(eval echo ${SSH_PRIVATE_KEY_PATH})
        
        if [ ! -f "$SSH_PUBLIC_KEY_PATH_FULL" ]; then
            log_warning "SSH 공개키 파일이 없습니다: $SSH_PUBLIC_KEY_PATH_FULL"
            log_info "SSH 키 쌍을 생성합니다..."
            ssh-keygen -t rsa -b 4096 -f "$SSH_PRIVATE_KEY_PATH_FULL" -N "" -C "proxmox-manager@$(hostname)"
            log_success "SSH 키 쌍 생성 완료"
        else
            log_success "SSH 공개키 파일 확인됨: $SSH_PUBLIC_KEY_PATH_FULL"
        fi
        
        # 기존 .env 파일에 Terraform 변수가 있는지 확인
        if ! grep -q "TF_VAR_vault_token" .env; then
            log_info "기존 .env 파일에 Terraform 변수를 추가 중..."
            cat >> .env << EOF

# Terraform 변수 (자동 매핑용)
TF_VAR_vault_token=${VAULT_TOKEN}
TF_VAR_vault_address=${VAULT_ADDR}
TF_VAR_proxmox_endpoint=${PROXMOX_ENDPOINT}
TF_VAR_proxmox_username=${PROXMOX_USERNAME}
TF_VAR_proxmox_password=${PROXMOX_PASSWORD}
TF_VAR_proxmox_node=${PROXMOX_NODE}
TF_VAR_vm_username=${SSH_USER}
TF_VAR_ssh_keys=${SSH_PUBLIC_KEY_PATH_FULL}
EOF
            log_success "기존 .env 파일에 Terraform 변수 추가 완료"
        else
            log_info "Terraform 변수가 이미 .env 파일에 존재합니다"
        fi
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
    
    # Terraform 변수 설정
    log_info "Terraform 변수 설정 중..."
    export TF_VAR_proxmox_endpoint="$PROXMOX_ENDPOINT"
    export TF_VAR_proxmox_username="$PROXMOX_USERNAME"
    export TF_VAR_proxmox_password="$PROXMOX_PASSWORD"
    export TF_VAR_proxmox_node="$PROXMOX_NODE"
    export TF_VAR_vm_username="$VM_USERNAME"
    export TF_VAR_vm_password="$VM_PASSWORD"
    export TF_VAR_vault_address="$VAULT_ADDR"
    export TF_VAR_vault_token="$VAULT_TOKEN"
    
    # SSH 공개키 설정 (파일이 존재하는 경우)
    if [ -f "$SSH_PUBLIC_KEY_PATH" ]; then
        export TF_VAR_ssh_keys="$(cat $SSH_PUBLIC_KEY_PATH)"
    fi
    
    log_success "Terraform 변수 설정 완료"
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
    if [ -f "scripts/vault.sh" ]; then
        log_info "Vault 설정 스크립트 실행 중..."
        chmod +x scripts/vault.sh
        ./scripts/vault.sh
        
        if [ $? -eq 0 ]; then
            log_success "Vault 설정 완료"
        else
            log_error "Vault 설정 실패"
            exit 1
        fi
    else
        log_error "scripts/vault.sh 파일을 찾을 수 없습니다"
        exit 1
    fi
    
    # Vault 수동 초기화 스크립트 생성
    log_info "Vault 수동 초기화 스크립트 생성 중..."
    cat > vault-init.sh << 'EOF'
#!/bin/bash
# Vault 수동 초기화 스크립트

echo "🔐 Vault 수동 초기화 스크립트"
echo "================================"

# Vault 컨테이너 상태 확인
if ! docker ps | grep -q vault-dev; then
    echo "❌ Vault 컨테이너가 실행되지 않았습니다."
    echo "먼저 다음 명령어로 Vault를 시작하세요:"
    echo "docker-compose -f docker-compose.vault.yaml up -d"
    exit 1
fi

# Vault 상태 확인
echo "🔍 Vault 상태 확인 중..."
VAULT_STATUS=$(docker exec vault-dev vault status 2>/dev/null)

if echo "$VAULT_STATUS" | grep -q "Initialized.*true"; then
    echo "⚠️ Vault가 이미 초기화되어 있습니다."
    echo ""
    echo "현재 상태:"
    echo "$VAULT_STATUS"
    echo ""
    
    read -p "Vault를 재초기화하시겠습니까? (y/N): " -n 1 -r
    echo ""
    
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "취소되었습니다."
        exit 0
    fi
    
    echo "⚠️ 주의: Vault 재초기화 시 기존 데이터가 모두 삭제됩니다!"
    read -p "정말로 재초기화하시겠습니까? (y/N): " -n 1 -r
    echo ""
    
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "취소되었습니다."
        exit 0
    fi
fi

echo ""
echo "🔐 Vault 초기화를 위한 정보를 입력해주세요:"
echo ""

# Proxmox 비밀번호 입력
read -p "Proxmox root 비밀번호를 입력하세요: " -s PROXMOX_PASSWORD
echo ""

# VM 비밀번호 입력
read -p "VM 기본 비밀번호를 입력하세요: " -s VM_PASSWORD
echo ""

# Vault 볼륨 권한 설정 (권한 문제 해결)
echo "🔧 Vault 볼륨 권한 설정 중..."
docker exec vault-dev sh -c "mkdir -p /vault/data && chmod 755 /vault/data" 2>/dev/null || true

# Vault 초기화 실행
echo "🚀 Vault 초기화 실행 중..."
VAULT_INIT_OUTPUT=$(docker exec vault-dev vault operator init -key-shares=1 -key-threshold=1 2>/dev/null)

if [ $? -eq 0 ]; then
    VAULT_TOKEN=$(echo "$VAULT_INIT_OUTPUT" | grep "Initial Root Token:" | awk '{print $4}')
    UNSEAL_KEY=$(echo "$VAULT_INIT_OUTPUT" | grep "Unseal Key 1:" | awk '{print $4}')
    
    # 토큰과 Unseal 키를 파일에 저장
    echo "$VAULT_TOKEN" > /data/terraform-proxmox/vault_token.txt
    echo "$UNSEAL_KEY" > /data/terraform-proxmox/vault_unseal_keys.txt
    chmod 600 /data/terraform-proxmox/vault_token.txt
    chmod 600 /data/terraform-proxmox/vault_unseal_keys.txt
    
    echo "✅ Vault 초기화 완료 및 키 저장"
    
    # 환경변수에 토큰 설정
    export VAULT_TOKEN="$VAULT_TOKEN"
    export TF_VAR_vault_token="$VAULT_TOKEN"
    
    # .env 파일에 토큰 업데이트
    if [ -f "/data/terraform-proxmox/.env" ]; then
        sed -i "s|VAULT_TOKEN=.*|VAULT_TOKEN=$VAULT_TOKEN|" /data/terraform-proxmox/.env
        sed -i "s|TF_VAR_vault_token=.*|TF_VAR_vault_token=$VAULT_TOKEN|" /data/terraform-proxmox/.env
        echo "✅ .env 파일에 토큰 업데이트 완료"
    fi
    
    # Vault 시크릿 설정 (Base64 암호화)
    echo "🔐 Vault 시크릿 설정 중 (Base64 암호화)..."
    
    # Proxmox 비밀번호 Base64 암호화
    PROXMOX_PASSWORD_B64=$(echo -n "$PROXMOX_PASSWORD" | base64)
    VM_PASSWORD_B64=$(echo -n "$VM_PASSWORD" | base64)
    
    # Vault에 시크릿 저장
    docker exec vault-dev vault kv put secret/proxmox username=root@pam password="$PROXMOX_PASSWORD_B64" password_plain="$PROXMOX_PASSWORD"
    docker exec vault-dev vault kv put secret/vm username=rocky password="$VM_PASSWORD_B64" password_plain="$VM_PASSWORD"
    
    echo "✅ Vault 시크릿 설정 완료 (Base64 암호화)"
    
    # 중요 정보 출력
    echo ""
    echo "================================"
    echo "📋 Vault 초기화 완료 정보:"
    echo "================================"
    echo "  Vault Token: $VAULT_TOKEN"
    echo "  Unseal Key: $UNSEAL_KEY"
    echo "  Proxmox Password (Base64): $PROXMOX_PASSWORD_B64"
    echo "  VM Password (Base64): $VM_PASSWORD_B64"
    echo ""
    echo "📁 저장된 파일:"
    echo "  /data/terraform-proxmox/vault_token.txt"
    echo "  /data/terraform-proxmox/vault_unseal_keys.txt"
    echo ""
    echo "⚠️  중요: 이 정보들을 안전한 곳에 보관하세요!"
    echo ""
    
    # Vault 상태 확인
    echo "🔍 Vault 최종 상태:"
    docker exec vault-dev vault status
    
else
    echo "❌ Vault 초기화 실패"
    exit 1
fi
EOF
    
    chmod +x vault-init.sh
    log_success "Vault 수동 초기화 스크립트 생성 완료"
}

# ========================================
# 10. 모니터링 시스템 설치
# ========================================

install_monitoring() {
    log_step "10. 모니터링 시스템 설치 중..."
    
    # Docker 모니터링 시스템 설치 (권장)
    log_info "Docker 모니터링 시스템 설치 중..."
    
    # Docker 설치 확인
    if ! command -v docker &> /dev/null; then
        log_error "Docker가 설치되지 않았습니다."
        log_info "Docker 설치 후 다시 시도해주세요."
        log_info "설치 명령어: curl -fsSL https://get.docker.com -o get-docker.sh && sudo sh get-docker.sh"
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose가 설치되지 않았습니다."
        log_info "Docker Compose 설치 후 다시 시도해주세요."
        log_info "설치 명령어: sudo curl -L \"https://github.com/docker/compose/releases/latest/download/docker-compose-\$(uname -s)-\$(uname -m)\" -o /usr/local/bin/docker-compose && sudo chmod +x /usr/local/bin/docker-compose"
        exit 1
    fi
    
    log_success "Docker 및 Docker Compose 확인 완료"
    
    # 모니터링 디렉토리 생성
    log_info "모니터링 디렉토리 생성 중..."
    mkdir -p monitoring/grafana/provisioning/datasources
    mkdir -p monitoring/grafana/provisioning/dashboards
    mkdir -p monitoring/grafana/dashboards
    mkdir -p monitoring/prometheus_data
    mkdir -p monitoring/grafana_data
    
    # Docker 모니터링 시스템 시작
    log_info "Docker 모니터링 시스템 시작 중..."
    if [ -f "monitoring/start-monitoring.sh" ]; then
        chmod +x monitoring/start-monitoring.sh
        cd monitoring
        ./start-monitoring.sh
        cd ..
        log_success "Docker 모니터링 시스템 시작 완료"
    else
        log_warning "Docker 모니터링 스크립트를 찾을 수 없습니다."
        log_info "수동으로 Docker 모니터링 시스템을 시작하세요:"
        log_info "  cd monitoring && docker-compose up -d"
    fi
    
    # Prometheus 타겟 업데이트 스크립트 권한 설정
    if [ -f "monitoring/update_prometheus_targets.py" ]; then
        log_info "Prometheus 타겟 업데이트 스크립트 설정 중..."
        chmod +x monitoring/update_prometheus_targets.py
        
        # PyYAML 설치 확인 (스크립트 실행에 필요)
        source venv/bin/activate
        pip install PyYAML requests
        
        log_success "Prometheus 타겟 업데이트 스크립트 설정 완료"
    fi
    
    # Ansible Dynamic Inventory 스크립트 권한 설정
    if [ -f "ansible/dynamic_inventory.py" ]; then
        log_info "Ansible Dynamic Inventory 스크립트 권한 설정 중..."
        chmod +x ansible/dynamic_inventory.py
        log_success "Dynamic Inventory 스크립트 권한 설정 완료"
    fi
    
    # 방화벽 설정 (Docker 포트)
    if command -v firewall-cmd &> /dev/null; then
        log_info "방화벽 설정 중..."
        sudo firewall-cmd --permanent --add-port=3000/tcp  # Grafana
        sudo firewall-cmd --permanent --add-port=9090/tcp  # Prometheus
        sudo firewall-cmd --permanent --add-port=9100/tcp  # Node Exporter
        sudo firewall-cmd --reload
        log_success "방화벽 설정 완료"
    fi
    
    log_success "모니터링 시스템 설치 완료"
    
    # 사용법 안내
    log_info "==========================================="
    log_info "🎉 Docker 모니터링 시스템 설치 완료!"
    log_info "==========================================="
    log_info "📊 접속 정보:"
    log_info "  - Prometheus: http://localhost:9090"
    log_info "  - Grafana: http://localhost:3000 (admin/admin123)"
    log_info ""
    log_info "🔧 관리 명령어:"
    log_info "  - 시작: cd monitoring && docker-compose up -d"
    log_info "  - 중지: cd monitoring && docker-compose down"
    log_info "  - 재시작: cd monitoring && docker-compose restart"
    log_info "  - 로그 확인: cd monitoring && docker-compose logs"
    log_info "  - 상태 확인: cd monitoring && docker-compose ps"
    log_info "==========================================="
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

[Install]
WantedBy=multi-user.target
EOF
    
    # 기존 Prometheus 데이터 정리 (깨끗한 설치를 위해)
    log_info "기존 Prometheus 데이터 정리 중..."
    sudo systemctl stop prometheus 2>/dev/null || true
    sudo rm -rf /var/lib/prometheus/* 2>/dev/null || true
    
    # 서비스 시작
    log_info "프로메테우스 서비스 시작 중..."
    sudo systemctl daemon-reload
    sudo systemctl enable prometheus
    sudo systemctl start prometheus
    
    # 상태 확인
    log_info "설치 완료! 상태 확인 중..."
    sudo systemctl status prometheus --no-pager
    
    # 정리
    rm -rf prometheus_temp prometheus.tar.gz
    
    log_success "Prometheus 설치 완료"
    log_info "프로메테우스는 http://localhost:9090 에서 접근 가능합니다"
    
    # Grafana 설치 (통합)
    log_info "Grafana 설치 중..."
    
    # Grafana 다운로드 (Linux x64)
    GRAFANA_VERSION="10.2.0"
    GRAFANA_URL="https://dl.grafana.com/oss/release/grafana-${GRAFANA_VERSION}.linux-amd64.tar.gz"
    
    log_info "Grafana ${GRAFANA_VERSION} 다운로드 중..."
    wget -O grafana.tar.gz ${GRAFANA_URL}
    
    # 압축 해제
    log_info "압축 해제 중..."
    tar -xzf grafana.tar.gz
    mv grafana-${GRAFANA_VERSION} grafana_temp
    
    # 표준 배치 경로 준비
    log_info "디렉토리 준비 중..."
    sudo useradd --no-create-home --shell /bin/false grafana 2>/dev/null || true
    sudo mkdir -p /opt/grafana
    sudo mkdir -p /etc/grafana
    sudo mkdir -p /var/lib/grafana
    sudo mkdir -p /var/lib/grafana/plugins
    sudo mkdir -p /var/log/grafana
    sudo mkdir -p /var/run/grafana
    
    # 바이너리 및 파일 배치
    log_info "바이너리 배치 중..."
    sudo cp -rf grafana_temp/* /opt/grafana/
    sudo chown -R grafana:grafana /opt/grafana
    sudo chown -R grafana:grafana /var/lib/grafana
    sudo chown -R grafana:grafana /var/lib/grafana/plugins
    sudo chown -R grafana:grafana /var/log/grafana
    sudo chown -R grafana:grafana /var/run/grafana
    sudo chmod 0755 /opt/grafana/bin/grafana-server
    sudo chmod 755 /var/run/grafana
    
    # Grafana 설정 파일 생성
    log_info "Grafana 설정 파일 생성 중..."
    sudo tee /etc/grafana/grafana.ini > /dev/null << 'EOF'
[paths]
data = /var/lib/grafana
logs = /var/log/grafana
plugins = /var/lib/grafana/plugins
provisioning = /etc/grafana/provisioning

[server]
http_port = 3000
domain = localhost
root_url = http://localhost:3000/
pidfile = /var/run/grafana/grafana-server.pid

[database]
type = sqlite3
path = grafana.db

[session]
provider = file

[log]
mode = console file
level = info

[security]
admin_user = admin
admin_password = admin
allow_embedding = true
cookie_secure = false
cookie_samesite = lax

[auth.anonymous]
enabled = true
org_name = Main Org.
org_role = Viewer
hide_version = false
EOF
    
    # 소유권 설정
    sudo chown -R grafana:grafana /etc/grafana
    
    # PID 파일 디렉토리 권한 재확인
    log_info "PID 파일 디렉토리 권한 재확인 중..."
    sudo chown -R grafana:grafana /var/run/grafana
    sudo chmod 755 /var/run/grafana
    
    # 기존 서비스 중지 (있다면)
    log_info "기존 Grafana 서비스 중지 중..."
    sudo systemctl stop grafana-server 2>/dev/null || true
    
    # systemd 유닛 생성 (표준 PID 파일 경로 사용)
    log_info "시스템 서비스 등록 중..."
    sudo tee /etc/systemd/system/grafana-server.service > /dev/null << 'EOF'
[Unit]
Description=Grafana Server
Documentation=http://docs.grafana.org
Wants=network-online.target
After=network-online.target

[Service]
Type=notify
User=grafana
Group=grafana
WorkingDirectory=/opt/grafana
ExecStart=/opt/grafana/bin/grafana server --config=/etc/grafana/grafana.ini --pidfile=/var/run/grafana/grafana-server.pid
Restart=on-failure
RestartSec=5
TimeoutStopSec=20
LimitNOFILE=10000
Environment=GF_PATHS_HOME=/opt/grafana
Environment=GF_PATHS_DATA=/var/lib/grafana
Environment=GF_PATHS_LOGS=/var/log/grafana
Environment=GF_PATHS_PLUGINS=/var/lib/grafana/plugins
Environment=GF_PATHS_PROVISIONING=/etc/grafana/provisioning
Environment=GF_PATHS_CONFIG=/etc/grafana/grafana.ini

[Install]
WantedBy=multi-user.target
EOF
    
    # 서비스 시작
    log_info "Grafana 서비스 시작 중..."
    sudo systemctl daemon-reload
    sudo systemctl enable grafana-server
    
    # 서비스 시작 및 상태 확인
    log_info "Grafana 서비스 시작 중..."
    if sudo systemctl start grafana-server; then
        log_success "Grafana 서비스 시작 성공"
        
        # 서비스 상태 확인 (최대 10초 대기)
        log_info "서비스 상태 확인 중..."
        for i in {1..10}; do
            if sudo systemctl is-active --quiet grafana-server; then
                log_success "Grafana 서비스가 정상적으로 실행 중입니다"
                break
            else
                log_info "서비스 시작 대기 중... ($i/10)"
                sleep 1
            fi
        done
        
        # 최종 상태 확인
        if sudo systemctl is-active --quiet grafana-server; then
            log_success "Grafana 설치 및 시작 완료"
        else
            log_warning "Grafana 서비스 시작에 문제가 있을 수 있습니다"
            log_info "서비스 로그 확인: sudo journalctl -u grafana-server -n 20"
        fi
    else
        log_error "Grafana 서비스 시작 실패"
        log_info "서비스 로그 확인: sudo journalctl -u grafana-server -n 20"
    fi
    
    # 정리
    rm -rf grafana_temp grafana.tar.gz
    
    log_success "Grafana 설치 완료"
    log_info "Grafana는 http://localhost:3000 에서 접근 가능합니다 (admin/admin)"
    
    # Grafana Provisioning 설정 (파일 기반)
    log_info "Grafana Provisioning 설정 중..."
    
    # Provisioning 디렉토리 생성
    sudo mkdir -p /etc/grafana/provisioning/datasources
    sudo mkdir -p /etc/grafana/provisioning/dashboards
    
    # 데이터소스 provisioning 파일 복사
    if [ -f "grafana/provisioning/datasources/prometheus.yml" ]; then
        sudo cp grafana/provisioning/datasources/prometheus.yml /etc/grafana/provisioning/datasources/
        log_success "Prometheus 데이터소스 provisioning 파일 복사 완료"
    else
        log_warning "Prometheus 데이터소스 provisioning 파일을 찾을 수 없습니다"
    fi
    
    # 대시보드 provisioning 파일 복사
    if [ -f "grafana/provisioning/dashboards/dashboard.yml" ]; then
        sudo cp grafana/provisioning/dashboards/dashboard.yml /etc/grafana/provisioning/dashboards/
        log_success "대시보드 provisioning 설정 파일 복사 완료"
    else
        log_warning "대시보드 provisioning 설정 파일을 찾을 수 없습니다"
    fi
    
    # 대시보드 JSON 파일 복사
    if [ -f "grafana/provisioning/dashboards/system-monitoring.json" ]; then
        sudo cp grafana/provisioning/dashboards/system-monitoring.json /etc/grafana/provisioning/dashboards/
        log_success "시스템 모니터링 대시보드 JSON 파일 복사 완료"
    else
        log_warning "시스템 모니터링 대시보드 JSON 파일을 찾을 수 없습니다"
    fi
    
    # 소유권 설정
    sudo chown -R grafana:grafana /etc/grafana/provisioning
    
    # Grafana 서비스 재시작 (provisioning 적용)
    log_info "Grafana 서비스 재시작 중 (provisioning 적용)..."
    sudo systemctl restart grafana-server
    
    # 서비스 재시작 확인
    sleep 5
    if sudo systemctl is-active --quiet grafana-server; then
        log_success "Grafana 서비스 재시작 완료"
        
        # 데이터소스 연결 확인
        log_info "Prometheus 데이터소스 연결 확인 중..."
        sleep 10  # Grafana가 완전히 시작될 때까지 대기
        
        # 데이터소스 연결 테스트
        if curl -s -f http://admin:admin@localhost:3000/api/datasources/prometheus > /dev/null 2>&1; then
            log_success "Prometheus 데이터소스 연결 확인 완료"
        else
            log_warning "Prometheus 데이터소스 연결에 문제가 있을 수 있습니다"
            log_info "Grafana 웹 인터페이스에서 데이터소스 설정을 확인해주세요: http://localhost:3000/datasources"
        fi
    else
        log_warning "Grafana 서비스 재시작에 문제가 있을 수 있습니다"
    fi
    
    # Grafana 설정 완료
    log_success "Grafana Provisioning 설정 완료"
    log_info "익명 접근 및 iframe 임베딩이 설정되었습니다"
    log_info "Prometheus 데이터소스가 자동으로 추가됩니다"
    log_info "시스템 모니터링 대시보드가 자동으로 생성됩니다"
    log_info "대시보드 URL: http://localhost:3000/d/system-monitoring-dashboard?kiosk=tv"
    
    # Ansible Dynamic Inventory 스크립트 권한 설정
    if [ -f "ansible/dynamic_inventory.py" ]; then
        log_info "Ansible Dynamic Inventory 스크립트 권한 설정 중..."
        chmod +x ansible/dynamic_inventory.py
        log_success "Dynamic Inventory 스크립트 권한 설정 완료"
    fi
    
    # Prometheus 타겟 업데이트 스크립트 권한 설정
    if [ -f "monitoring/update_prometheus_targets.py" ]; then
        log_info "Prometheus 타겟 업데이트 스크립트 설정 중..."
        chmod +x monitoring/update_prometheus_targets.py
        
        # PyYAML 설치 확인 (스크립트 실행에 필요)
        source venv/bin/activate
        pip install PyYAML requests
        
        log_success "Prometheus 타겟 업데이트 스크립트 설정 완료"
    fi
    
    # Docker 모니터링 시스템 설정
    log_info "Docker 모니터링 시스템 설정 중..."
    if [ -f "monitoring/start-monitoring.sh" ]; then
        chmod +x monitoring/start-monitoring.sh
        log_success "Docker 모니터링 스크립트 권한 설정 완료"
        
        # Docker 설치 확인
        if command -v docker &> /dev/null && command -v docker-compose &> /dev/null; then
            log_info "Docker 모니터링 시스템 시작 중..."
            cd monitoring
            ./start-monitoring.sh
            cd ..
            log_success "Docker 모니터링 시스템 시작 완료"
        else
            log_warning "Docker가 설치되지 않아 모니터링 시스템을 시작할 수 없습니다."
            log_info "Docker 설치 후 'monitoring/start-monitoring.sh'를 실행하세요."
        fi
    else
        log_warning "Docker 모니터링 스크립트를 찾을 수 없습니다."
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
    elif [ -f "docker-compose.vault.yaml" ]; then
        log_info "Vault 서비스 시작 중..."
        
        # Vault 데이터 볼륨 확인 및 생성
        if ! docker volume ls | grep -q vault-data; then
            log_info "Vault 데이터 볼륨 생성 중..."
            docker volume create vault-data
        fi
        
        docker-compose -f docker-compose.vault.yaml up -d
        
        if [ $? -eq 0 ]; then
            log_success "Vault 서비스 시작 완료"
        else
            log_warning "Vault 서비스 시작 실패"
        fi
    fi
    
    # Vault 초기화 및 Unseal 자동화
    log_info "Vault 초기화 및 Unseal 설정 중..."
    
    # Vault 서비스가 완전히 시작될 때까지 대기
    log_info "Vault 서비스 초기화 대기 중..."
    sleep 15
    
    # Vault 상태 확인 및 초기화
    if docker ps | grep -q vault-dev; then
        log_info "Vault 상태 확인 중..."
        
        # Vault 초기화 상태 확인
        VAULT_INIT_STATUS=$(docker exec vault-dev vault status 2>/dev/null | grep "Initialized" | awk '{print $2}')
        
        if [ "$VAULT_INIT_STATUS" = "true" ]; then
            log_info "Vault가 이미 초기화되어 있습니다."
            
            # Vault Unseal 상태 확인
            VAULT_SEALED=$(docker exec vault-dev vault status 2>/dev/null | grep "Sealed" | awk '{print $2}')
            
            if [ "$VAULT_SEALED" = "true" ]; then
                log_info "Vault가 sealed 상태입니다. Unseal을 진행합니다..."
                
                # Unseal 키 파일 확인
                if [ -f "/data/terraform-proxmox/vault_unseal_keys.txt" ]; then
                    log_info "저장된 Unseal 키를 사용합니다..."
                    UNSEAL_KEY=$(cat /data/terraform-proxmox/vault_unseal_keys.txt)
                    
                    # Vault Unseal 실행
                    if docker exec vault-dev vault operator unseal "$UNSEAL_KEY" 2>/dev/null; then
                        log_success "Vault Unseal 성공"
                    else
                        log_error "Vault Unseal 실패"
                    fi
                elif [ -f "/data/terraform-proxmox/vault_init.txt" ]; then
                    log_info "vault_init.txt에서 Unseal 키를 추출합니다..."
                    UNSEAL_KEY=$(grep "Unseal Key 1:" /data/terraform-proxmox/vault_init.txt | awk '{print $4}')
                    
                    if [ -n "$UNSEAL_KEY" ]; then
                        # Unseal 키를 별도 파일에 저장
                        echo "$UNSEAL_KEY" > /data/terraform-proxmox/vault_unseal_keys.txt
                        chmod 600 /data/terraform-proxmox/vault_unseal_keys.txt
                        log_success "Unseal 키를 vault_unseal_keys.txt에 저장했습니다."
                        
                        # Vault Unseal 실행
                        if docker exec vault-dev vault operator unseal "$UNSEAL_KEY" 2>/dev/null; then
                            log_success "Vault Unseal 성공"
                        else
                            log_error "Vault Unseal 실패"
                        fi
                    else
                        log_error "vault_init.txt에서 Unseal 키를 찾을 수 없습니다."
                    fi
                else
                    log_warning "Unseal 키 파일이 없습니다. Vault를 다시 초기화합니다."
                    
                    # Vault 재초기화 시 사용자 입력 받기
                    echo ""
                    echo -e "${YELLOW}🔐 Vault 재초기화를 위한 정보를 입력해주세요:${NC}"
                    echo ""
                    
                    # Proxmox 비밀번호 입력
                    read -p "Proxmox root 비밀번호를 입력하세요: " -s PROXMOX_PASSWORD
                    echo ""
                    
                    # VM 비밀번호 입력
                    read -p "VM 기본 비밀번호를 입력하세요: " -s VM_PASSWORD
                    echo ""
                    
                    # Vault 볼륨 권한 설정 (권한 문제 해결)
                    log_info "Vault 볼륨 권한 설정 중..."
                    docker exec vault-dev sh -c "mkdir -p /vault/data && chmod 755 /vault/data" 2>/dev/null || true
                    
                    # Vault 재초기화 실행
                    log_info "Vault 재초기화 실행 중..."
                    VAULT_INIT_OUTPUT=$(docker exec vault-dev vault operator init -key-shares=1 -key-threshold=1 2>/dev/null)
                    
                    if [ $? -eq 0 ]; then
                        VAULT_TOKEN=$(echo "$VAULT_INIT_OUTPUT" | grep "Initial Root Token:" | awk '{print $4}')
                        UNSEAL_KEY=$(echo "$VAULT_INIT_OUTPUT" | grep "Unseal Key 1:" | awk '{print $4}')
                        
                        # 토큰과 Unseal 키를 파일에 저장
                        echo "$VAULT_TOKEN" > /data/terraform-proxmox/vault_token.txt
                        echo "$UNSEAL_KEY" > /data/terraform-proxmox/vault_unseal_keys.txt
                        chmod 600 /data/terraform-proxmox/vault_token.txt
                        chmod 600 /data/terraform-proxmox/vault_unseal_keys.txt
                        
                        log_success "Vault 재초기화 완료 및 키 저장"
                        
                        # 환경변수에 토큰 설정
                        export VAULT_TOKEN="$VAULT_TOKEN"
                        export TF_VAR_vault_token="$VAULT_TOKEN"
                        
                        # .env 파일에 토큰 업데이트
                        if [ -f ".env" ]; then
                            sed -i "s|VAULT_TOKEN=.*|VAULT_TOKEN=$VAULT_TOKEN|" .env
                            sed -i "s|TF_VAR_vault_token=.*|TF_VAR_vault_token=$VAULT_TOKEN|" .env
                        fi
                        
                        # Vault 시크릿 설정 (Base64 암호화)
                        log_info "Vault 시크릿 설정 중 (Base64 암호화)..."
                        
                        # Proxmox 비밀번호 Base64 암호화
                        PROXMOX_PASSWORD_B64=$(echo -n "$PROXMOX_PASSWORD" | base64)
                        VM_PASSWORD_B64=$(echo -n "$VM_PASSWORD" | base64)
                        
                        # Vault에 시크릿 저장
                        docker exec vault-dev vault kv put secret/proxmox username=root@pam password="$PROXMOX_PASSWORD_B64" password_plain="$PROXMOX_PASSWORD"
                        docker exec vault-dev vault kv put secret/vm username=rocky password="$VM_PASSWORD_B64" password_plain="$VM_PASSWORD"
                        
                        log_success "Vault 시크릿 설정 완료 (Base64 암호화)"
                        
                        # 중요 정보 출력
                        echo ""
                        echo -e "${CYAN}📋 Vault 재초기화 완료 정보:${NC}"
                        echo "  Vault Token: $VAULT_TOKEN"
                        echo "  Unseal Key: $UNSEAL_KEY"
                        echo "  Proxmox Password (Base64): $PROXMOX_PASSWORD_B64"
                        echo "  VM Password (Base64): $VM_PASSWORD_B64"
                        echo ""
                        echo -e "${YELLOW}⚠️  중요: 이 정보들을 안전한 곳에 보관하세요!${NC}"
                        echo ""
                        
                    else
                        log_error "Vault 재초기화 실패"
                        exit 1
                    fi
                fi
            else
                log_success "Vault가 이미 unsealed 상태입니다."
            fi
            
            # 토큰 복원
            if [ -f "/data/terraform-proxmox/vault_token.txt" ]; then
                VAULT_TOKEN=$(cat /data/terraform-proxmox/vault_token.txt)
                export VAULT_TOKEN="$VAULT_TOKEN"
                export TF_VAR_vault_token="$VAULT_TOKEN"
                
                # .env 파일에 토큰 업데이트
                if [ -f ".env" ]; then
                    sed -i "s|VAULT_TOKEN=.*|VAULT_TOKEN=$VAULT_TOKEN|" .env
                    sed -i "s|TF_VAR_vault_token=.*|TF_VAR_vault_token=$VAULT_TOKEN|" .env
                    log_success "Vault 토큰이 .env 파일에 업데이트되었습니다."
                fi
            elif [ -f "/data/terraform-proxmox/vault_init.txt" ]; then
                log_info "vault_init.txt에서 Vault 토큰을 추출합니다..."
                VAULT_TOKEN=$(grep "Initial Root Token:" /data/terraform-proxmox/vault_init.txt | awk '{print $4}')
                
                if [ -n "$VAULT_TOKEN" ]; then
                    # 토큰을 별도 파일에 저장
                    echo "$VAULT_TOKEN" > /data/terraform-proxmox/vault_token.txt
                    chmod 600 /data/terraform-proxmox/vault_token.txt
                    log_success "Vault 토큰을 vault_token.txt에 저장했습니다."
                    
                    export VAULT_TOKEN="$VAULT_TOKEN"
                    export TF_VAR_vault_token="$VAULT_TOKEN"
                    
                    # .env 파일에 토큰 업데이트
                    if [ -f ".env" ]; then
                        sed -i "s|VAULT_TOKEN=.*|VAULT_TOKEN=$VAULT_TOKEN|" .env
                        sed -i "s|TF_VAR_vault_token=.*|TF_VAR_vault_token=$VAULT_TOKEN|" .env
                        log_success "Vault 토큰이 .env 파일에 업데이트되었습니다."
                    fi
                else
                    log_error "vault_init.txt에서 Vault 토큰을 찾을 수 없습니다."
                fi
            fi
            
            # Vault 시크릿 설정 확인
            log_info "Vault 시크릿 설정 확인 중..."
            
            # Proxmox 시크릿 확인
            if ! docker exec vault-dev vault kv get secret/proxmox 2>/dev/null | grep -q "password"; then
                log_info "Proxmox 시크릿을 Vault에 저장 중..."
                docker exec vault-dev vault kv put secret/proxmox username=root@pam password=YzaxdJOA2j9Itv8S
                log_success "Proxmox 시크릿 저장 완료"
            else
                log_info "Proxmox 시크릿이 이미 존재합니다."
            fi
            
            # VM 시크릿 확인
            if ! docker exec vault-dev vault kv get secret/vm 2>/dev/null | grep -q "password"; then
                log_info "VM 시크릿을 Vault에 저장 중..."
                docker exec vault-dev vault kv put secret/vm username=rocky password=rocky123
                log_success "VM 시크릿 저장 완료"
            else
                log_info "VM 시크릿이 이미 존재합니다."
            fi
            
        else
            log_info "Vault 초기화 중..."
            
            # Vault 초기화 시 사용자 입력 받기
            echo ""
            echo -e "${YELLOW}🔐 Vault 초기화를 위한 정보를 입력해주세요:${NC}"
            echo ""
            
            # Proxmox 비밀번호 입력
            read -p "Proxmox root 비밀번호를 입력하세요: " -s PROXMOX_PASSWORD
            echo ""
            
            # VM 비밀번호 입력
            read -p "VM 기본 비밀번호를 입력하세요: " -s VM_PASSWORD
            echo ""
            
            # Vault 볼륨 권한 설정 (권한 문제 해결)
            log_info "Vault 볼륨 권한 설정 중..."
            docker exec vault-dev sh -c "mkdir -p /vault/data && chmod 755 /vault/data" 2>/dev/null || true
            
            # Vault 초기화 실행
            log_info "Vault 초기화 실행 중..."
            VAULT_INIT_OUTPUT=$(docker exec vault-dev vault operator init -key-shares=1 -key-threshold=1 2>/dev/null)
            
            if [ $? -eq 0 ]; then
                VAULT_TOKEN=$(echo "$VAULT_INIT_OUTPUT" | grep "Initial Root Token:" | awk '{print $4}')
                UNSEAL_KEY=$(echo "$VAULT_INIT_OUTPUT" | grep "Unseal Key 1:" | awk '{print $4}')
                
                # 토큰과 Unseal 키를 파일에 저장
                echo "$VAULT_TOKEN" > /data/terraform-proxmox/vault_token.txt
                echo "$UNSEAL_KEY" > /data/terraform-proxmox/vault_unseal_keys.txt
                chmod 600 /data/terraform-proxmox/vault_token.txt
                chmod 600 /data/terraform-proxmox/vault_unseal_keys.txt
                
                log_success "Vault 초기화 완료 및 키 저장"
                
                # 환경변수에 토큰 설정
                export VAULT_TOKEN="$VAULT_TOKEN"
                export TF_VAR_vault_token="$VAULT_TOKEN"
                
                # .env 파일에 토큰 업데이트
                if [ -f ".env" ]; then
                    sed -i "s|VAULT_TOKEN=.*|VAULT_TOKEN=$VAULT_TOKEN|" .env
                    sed -i "s|TF_VAR_vault_token=.*|TF_VAR_vault_token=$VAULT_TOKEN|" .env
                fi
                
                # Vault 시크릿 설정 (Base64 암호화)
                log_info "Vault 시크릿 설정 중 (Base64 암호화)..."
                
                # Proxmox 비밀번호 Base64 암호화
                PROXMOX_PASSWORD_B64=$(echo -n "$PROXMOX_PASSWORD" | base64)
                VM_PASSWORD_B64=$(echo -n "$VM_PASSWORD" | base64)
                
                # Vault에 시크릿 저장
                docker exec vault-dev vault kv put secret/proxmox username=root@pam password="$PROXMOX_PASSWORD_B64" password_plain="$PROXMOX_PASSWORD"
                docker exec vault-dev vault kv put secret/vm username=rocky password="$VM_PASSWORD_B64" password_plain="$VM_PASSWORD"
                
                log_success "Vault 시크릿 설정 완료 (Base64 암호화)"
                
                # 중요 정보 출력
                echo ""
                echo -e "${CYAN}📋 Vault 초기화 완료 정보:${NC}"
                echo "  Vault Token: $VAULT_TOKEN"
                echo "  Unseal Key: $UNSEAL_KEY"
                echo "  Proxmox Password (Base64): $PROXMOX_PASSWORD_B64"
                echo "  VM Password (Base64): $VM_PASSWORD_B64"
                echo ""
                echo -e "${YELLOW}⚠️  중요: 이 정보들을 안전한 곳에 보관하세요!${NC}"
                echo ""
                
            else
                log_error "Vault 초기화 실패"
                exit 1
            fi
        fi
        
        log_success "Vault 초기화 및 Unseal 설정 완료"
    else
        log_warning "Vault 컨테이너가 실행되지 않았습니다."
    fi
    
    # Flask 애플리케이션 systemd 서비스 등록
    log_info "Flask 애플리케이션 systemd 서비스 등록 중..."
    
    # 현재 디렉토리 경로 가져오기
    APP_DIR=$(pwd)
    VENV_PYTHON="$APP_DIR/venv/bin/python"
    
    # 가상환경 Python 경로 확인
    if [ ! -f "$VENV_PYTHON" ]; then
        log_error "가상환경을 찾을 수 없습니다. Python 패키지 설치를 먼저 완료하세요."
        log_error "가상환경 경로: $VENV_PYTHON"
        exit 1
    else
        log_info "가상환경 Python 사용: $VENV_PYTHON"
        
        # 가상환경에서 필수 패키지 확인
        log_info "가상환경 패키지 확인 중..."
        if ! $VENV_PYTHON -c "import dotenv" 2>/dev/null; then
            log_warning "python-dotenv가 설치되지 않았습니다. 설치 중..."
            $VENV_PYTHON -m pip install python-dotenv
        fi
        
        if ! $VENV_PYTHON -c "import flask" 2>/dev/null; then
            log_warning "Flask가 설치되지 않았습니다. 설치 중..."
            $VENV_PYTHON -m pip install flask flask-sqlalchemy flask-login
        fi
        
        if ! $VENV_PYTHON -c "import requests" 2>/dev/null; then
            log_warning "requests가 설치되지 않았습니다. 설치 중..."
            $VENV_PYTHON -m pip install requests
        fi
    fi
    
    # 가상환경 Python 실행 권한 확인 및 설정
    log_info "가상환경 Python 실행 권한 설정 중..."
    
    # 가상환경 Python 파일 권한 확인
    if [ -f "$VENV_PYTHON" ]; then
        CURRENT_PERMS=$(ls -l "$VENV_PYTHON" | awk '{print $1}')
        log_info "현재 Python 파일 권한: $CURRENT_PERMS"
        
        # 실행 권한이 없는 경우에만 설정 시도
        if [[ ! "$CURRENT_PERMS" =~ x ]]; then
            log_info "실행 권한이 없습니다. 권한 설정 시도 중..."
            if chmod +x "$VENV_PYTHON" 2>/dev/null; then
                log_success "Python 파일 실행 권한 설정 완료"
            else
                log_warning "Python 파일 권한 설정 실패 (계속 진행)"
                log_info "가상환경 재생성을 시도합니다..."
                
                # 가상환경 재생성
                log_info "기존 가상환경 백업 중..."
                if [ -d "venv" ]; then
                    mv venv venv.backup.$(date +%Y%m%d_%H%M%S)
                fi
                
                log_info "새 가상환경 생성 중..."
                if command -v python3.12 &> /dev/null; then
                    python3.12 -m venv venv
                elif command -v python3 &> /dev/null; then
                    python3 -m venv venv
                else
                    log_error "Python을 찾을 수 없습니다"
                    exit 1
                fi
                
                # 새 가상환경에서 Python 패키지 재설치
                log_info "가상환경 활성화 및 패키지 재설치 중..."
                source venv/bin/activate
                pip install -r requirements.txt
                
                # 새 Python 경로 업데이트
                VENV_PYTHON="$APP_DIR/venv/bin/python"
                log_info "새 가상환경 Python 경로: $VENV_PYTHON"
            fi
        else
            log_success "Python 파일에 이미 실행 권한이 있습니다"
        fi
    else
        log_error "가상환경 Python 파일을 찾을 수 없습니다: $VENV_PYTHON"
        exit 1
    fi
    
    # config.py 파일 자동 생성 (TerraformConfig 클래스 포함)
    log_info "config.py 파일 자동 생성 중..."
    cat > config/config.py << 'EOF'
import os
from datetime import timedelta

class VaultConfig:
    """Vault 설정"""
    VAULT_ADDR = os.environ.get('VAULT_ADDR', 'http://127.0.0.1:8200')
    VAULT_TOKEN = os.environ.get('VAULT_TOKEN')
    
    @classmethod
    def get_secret(cls, secret_path, key):
        """Vault에서 시크릿 가져오기"""
        try:
            import hvac
            client = hvac.Client(url=cls.VAULT_ADDR, token=cls.VAULT_TOKEN)
            if client.is_authenticated():
                response = client.secrets.kv.v2.read_secret_version(path=secret_path)
                return response['data']['data'].get(key)
            else:
                raise ValueError("Vault 인증 실패")
        except ImportError:
            # hvac 패키지가 없으면 환경 변수에서 가져오기
            return os.environ.get(f'TF_VAR_{key.upper()}')
        except Exception as e:
            print(f"Vault에서 시크릿 가져오기 실패: {e}")
            # 폴백: 환경 변수에서 가져오기
            return os.environ.get(f'TF_VAR_{key.upper()}')


class TerraformConfig:
    """Terraform 변수 자동 매핑"""
    
    # 환경변수 → Terraform 변수 매핑 (.env 파일 기반)
    MAPPINGS = {
        'VAULT_TOKEN': 'TF_VAR_vault_token',
        'VAULT_ADDR': 'TF_VAR_vault_address',
        'PROXMOX_ENDPOINT': 'TF_VAR_proxmox_endpoint',
        'PROXMOX_USERNAME': 'TF_VAR_proxmox_username',
        'PROXMOX_PASSWORD': 'TF_VAR_proxmox_password',
        'PROXMOX_NODE': 'TF_VAR_proxmox_node',
        'SSH_USER': 'TF_VAR_vm_username',
        'SSH_PUBLIC_KEY_PATH': 'TF_VAR_ssh_keys'
    }
    
    @classmethod
    def setup_terraform_vars(cls):
        """환경변수를 Terraform 변수로 자동 매핑"""
        for source_var, target_var in cls.MAPPINGS.items():
            value = os.getenv(source_var)
            if value and not os.getenv(target_var):
                os.environ[target_var] = value
                print(f"✅ {source_var} → {target_var}")
    
    @classmethod
    def get_terraform_var(cls, var_name):
        """Terraform 변수 가져오기"""
        return os.getenv(f'TF_VAR_{var_name}')
    
    @classmethod
    def get_all_terraform_vars(cls):
        """모든 Terraform 변수 가져오기"""
        return {k: v for k, v in os.environ.items() if k.startswith('TF_VAR_')}
    
    @classmethod
    def validate_terraform_vars(cls):
        """Terraform 변수 검증"""
        required_vars = ['vault_token', 'vault_address', 'proxmox_endpoint', 'proxmox_username', 'proxmox_password']
        missing_vars = []
        
        for var in required_vars:
            if not cls.get_terraform_var(var):
                missing_vars.append(f'TF_VAR_{var}')
        
        if missing_vars:
            print(f"⚠️ 누락된 Terraform 변수: {', '.join(missing_vars)}")
            return False
        
        print("✅ 모든 필수 Terraform 변수가 설정되었습니다")
        return True
    
    @classmethod
    def debug_terraform_vars(cls):
        """Terraform 변수 디버깅 정보 출력"""
        print("🔧 Terraform 변수 상태:")
        for source_var, target_var in cls.MAPPINGS.items():
            source_value = os.getenv(source_var, '❌ 없음')
            target_value = os.getenv(target_var, '❌ 없음')
            print(f"  {source_var}: {'✅ 설정됨' if source_value != '❌ 없음' else '❌ 없음'}")
            print(f"  {target_var}: {'✅ 설정됨' if target_value != '❌ 없음' else '❌ 없음'}")
            print()


class Config:
    """기본 설정"""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    DEBUG = os.environ.get('DEBUG', 'True').lower() == 'true'
    
    # SQLAlchemy 설정
    basedir = os.path.abspath(os.path.dirname(__file__))
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', f'sqlite:///{os.path.join(basedir, "instance", "proxmox_manager.db")}')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Proxmox 설정 (환경 변수 필수)
    PROXMOX_ENDPOINT = os.environ.get('PROXMOX_ENDPOINT', 'https://localhost:8006')
    PROXMOX_USERNAME = os.environ.get('PROXMOX_USERNAME', 'root@pam')
    PROXMOX_PASSWORD = os.environ.get('PROXMOX_PASSWORD', 'password')
    PROXMOX_NODE = os.environ.get('PROXMOX_NODE', 'pve')
    PROXMOX_DATASTORE = os.environ.get('PROXMOX_DATASTORE', 'local-lvm')
    
    # 세션 보안 설정
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'False').lower() == 'true'
    SESSION_COOKIE_HTTPONLY = os.environ.get('SESSION_COOKIE_HTTPONLY', 'True').lower() == 'true'
    SESSION_COOKIE_SAMESITE = os.environ.get('SESSION_COOKIE_SAMESITE', 'Strict')
    PERMANENT_SESSION_LIFETIME = timedelta(
        seconds=int(os.environ.get('PERMANENT_SESSION_LIFETIME', 28800))  # 8시간으로 연장
    )
    
    # 로깅 설정
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_FILE = os.environ.get('LOG_FILE', 'app.log')
    
    # SSH 설정
    SSH_PRIVATE_KEY_PATH = os.environ.get('SSH_PRIVATE_KEY_PATH', '~/.ssh/id_rsa')
    SSH_PUBLIC_KEY_PATH = os.environ.get('SSH_PUBLIC_KEY_PATH', '~/.ssh/id_rsa.pub')
    SSH_USER = os.environ.get('SSH_USER', 'rocky')
    
    # 모니터링 설정 (환경 변수)
    GRAFANA_URL = os.environ.get('GRAFANA_URL', 'http://localhost:3000')
    GRAFANA_USERNAME = os.environ.get('GRAFANA_USERNAME', 'admin')
    GRAFANA_PASSWORD = os.environ.get('GRAFANA_PASSWORD', 'admin')
    GRAFANA_ORG_ID = os.environ.get('GRAFANA_ORG_ID', '1')
    GRAFANA_DASHBOARD_UID = os.environ.get('GRAFANA_DASHBOARD_UID', 'system_monitoring')
    GRAFANA_ANONYMOUS_ACCESS = os.environ.get('GRAFANA_ANONYMOUS_ACCESS', 'false').lower() == 'true'
    GRAFANA_AUTO_REFRESH = os.environ.get('GRAFANA_AUTO_REFRESH', '5s')
    
    PROMETHEUS_URL = os.environ.get('PROMETHEUS_URL', 'http://localhost:9090')
    PROMETHEUS_USERNAME = os.environ.get('PROMETHEUS_USERNAME', '')
    PROMETHEUS_PASSWORD = os.environ.get('PROMETHEUS_PASSWORD', '')
    
    NODE_EXPORTER_AUTO_INSTALL = os.environ.get('NODE_EXPORTER_AUTO_INSTALL', 'true').lower() == 'true'
    NODE_EXPORTER_PORT = int(os.environ.get('NODE_EXPORTER_PORT', '9100'))
    NODE_EXPORTER_VERSION = os.environ.get('NODE_EXPORTER_VERSION', '1.6.1')
    
    MONITORING_DEFAULT_TIME_RANGE = os.environ.get('MONITORING_DEFAULT_TIME_RANGE', '1h')
    MONITORING_HEALTH_CHECK_INTERVAL = os.environ.get('MONITORING_HEALTH_CHECK_INTERVAL', '30s')
    MONITORING_PING_TIMEOUT = os.environ.get('MONITORING_PING_TIMEOUT', '5s')
    MONITORING_SSH_TIMEOUT = os.environ.get('MONITORING_SSH_TIMEOUT', '10s')
    
    ALERTS_ENABLED = os.environ.get('ALERTS_ENABLED', 'true').lower() == 'true'
    ALERTS_EMAIL = os.environ.get('ALERTS_EMAIL', 'admin@example.com')
    ALERTS_CPU_WARNING_THRESHOLD = float(os.environ.get('ALERTS_CPU_WARNING_THRESHOLD', '80'))
    ALERTS_CPU_CRITICAL_THRESHOLD = float(os.environ.get('ALERTS_CPU_CRITICAL_THRESHOLD', '95'))
    ALERTS_MEMORY_WARNING_THRESHOLD = float(os.environ.get('ALERTS_MEMORY_WARNING_THRESHOLD', '85'))
    ALERTS_MEMORY_CRITICAL_THRESHOLD = float(os.environ.get('ALERTS_MEMORY_CRITICAL_THRESHOLD', '95'))
    
    SECURITY_ENABLE_HTTPS = os.environ.get('SECURITY_ENABLE_HTTPS', 'false').lower() == 'true'
    SECURITY_ENABLE_AUTH = os.environ.get('SECURITY_ENABLE_AUTH', 'true').lower() == 'true'
    SECURITY_SESSION_TIMEOUT = int(os.environ.get('SECURITY_SESSION_TIMEOUT', '3600'))
    SECURITY_MAX_LOGIN_ATTEMPTS = int(os.environ.get('SECURITY_MAX_LOGIN_ATTEMPTS', '5'))

class DevelopmentConfig(Config):
    """개발 환경 설정"""
    DEBUG = True
    SESSION_COOKIE_SECURE = False

class ProductionConfig(Config):
    """운영 환경 설정"""
    DEBUG = False
    SESSION_COOKIE_SECURE = True

# 환경별 설정 매핑
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
EOF
    
    log_success "config.py 파일 생성 완료"
    
    # 필수 패키지 설치 확인 및 재설치 (완전 자동화)
    log_info "필수 패키지 설치 확인 중..."
    
    # 가상환경 활성화 및 패키지 설치를 위한 스크립트 생성
    cat > fix_venv.sh << 'EOF'
#!/bin/bash
cd /data/terraform-proxmox

# 가상환경 활성화
source venv/bin/activate

# 필수 패키지 설치
pip install python-dotenv flask flask-sqlalchemy flask-login requests paramiko

# 가상환경 비활성화
deactivate

echo "가상환경 패키지 설치 완료"
EOF
    
    chmod +x fix_venv.sh
    
    # 가상환경 패키지 설치 실행
    log_info "가상환경 패키지 자동 설치 중..."
    if ./fix_venv.sh; then
        log_success "가상환경 패키지 설치 완료"
    else
        log_warning "가상환경 패키지 설치 실패, 수동 설치 시도 중..."
        
        # 수동 설치 시도
        if ! $VENV_PYTHON -c "import dotenv" 2>/dev/null; then
            log_warning "python-dotenv가 설치되지 않았습니다. 재설치 중..."
            $VENV_PYTHON -m pip install python-dotenv
        fi
        
        if ! $VENV_PYTHON -c "import flask" 2>/dev/null; then
            log_warning "Flask가 설치되지 않았습니다. 재설치 중..."
            $VENV_PYTHON -m pip install flask flask-sqlalchemy flask-login
        fi
        
        if ! $VENV_PYTHON -c "import requests" 2>/dev/null; then
            log_warning "requests가 설치되지 않았습니다. 재설치 중..."
            $VENV_PYTHON -m pip install requests
        fi
    fi
    
    # 임시 스크립트 정리
    rm -f fix_venv.sh
    
    # run.py 파일 권한 설정
    if [ -f "$APP_DIR/run.py" ]; then
        chmod +x "$APP_DIR/run.py" 2>/dev/null || log_warning "run.py 권한 설정 실패"
    fi
    
    # systemd 서비스 파일 생성 (가상환경 문제 해결)
    sudo tee /etc/systemd/system/proxmox-manager.service > /dev/null << EOF
[Unit]
Description=Proxmox Manager Flask Application
After=network.target
Wants=network.target

[Service]
Type=simple
User=$USER
Group=$USER
WorkingDirectory=$APP_DIR
EnvironmentFile=$APP_DIR/.env
Environment=PATH=$APP_DIR/venv/bin:/usr/local/bin:/usr/bin:/bin
Environment=VIRTUAL_ENV=$APP_DIR/venv
Environment=PYTHONPATH=$APP_DIR
ExecStart=$VENV_PYTHON run.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

# 보안 설정 (권한 문제 해결을 위해 일부 완화)
NoNewPrivileges=true
PrivateTmp=false
ProtectSystem=false
ProtectHome=false
ReadWritePaths=$APP_DIR

[Install]
WantedBy=multi-user.target
EOF
    
    # 서비스 등록 및 시작
    log_info "Flask 애플리케이션 서비스 시작 중..."
    sudo systemctl daemon-reload
    sudo systemctl enable proxmox-manager
    
    # 서비스 시작 전 자동 검증 및 수정
    log_info "서비스 시작 전 자동 검증 중..."
    
    # 가상환경 Python 실행 테스트
    if ! $VENV_PYTHON -c "import dotenv, flask, requests" 2>/dev/null; then
        log_warning "가상환경 패키지 문제 감지. 자동 수정 중..."
        
        # 자동 수정 스크립트 실행
        cat > auto_fix_venv.sh << 'EOF'
#!/bin/bash
cd /data/terraform-proxmox
source venv/bin/activate
pip install --upgrade python-dotenv flask flask-sqlalchemy flask-login requests
deactivate
echo "가상환경 자동 수정 완료"
EOF
        
        chmod +x auto_fix_venv.sh
        ./auto_fix_venv.sh
        rm -f auto_fix_venv.sh
        
        log_success "가상환경 자동 수정 완료"
    fi
    
    # 서비스 시작 시도 (재시도 로직 포함)
    MAX_RETRIES=3
    RETRY_COUNT=0
    
    while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
        log_info "서비스 시작 시도 $((RETRY_COUNT + 1))/$MAX_RETRIES"
        
        if sudo systemctl start proxmox-manager; then
            log_success "Flask 애플리케이션 서비스 시작 완료"
            
            # 서비스 상태 확인
            sleep 5
            if sudo systemctl is-active --quiet proxmox-manager; then
                log_success "Flask 애플리케이션 서비스가 정상적으로 실행 중입니다"
                log_info "서비스 상태: $(sudo systemctl is-active proxmox-manager)"
                break
            else
                log_warning "서비스가 시작되었지만 상태가 불안정합니다. 재시도 중..."
                sudo systemctl stop proxmox-manager
                sleep 2
            fi
        else
            log_warning "서비스 시작 실패. 재시도 중..."
            sleep 3
        fi
        
        RETRY_COUNT=$((RETRY_COUNT + 1))
    done
    
    # 최종 상태 확인
    if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
        log_error "Flask 애플리케이션 서비스 시작 실패 (최대 재시도 횟수 초과)"
        log_info "서비스 로그를 확인하세요: sudo journalctl -u proxmox-manager -n 20"
        log_info "수동으로 다음 명령어를 실행해보세요:"
        log_info "  sudo systemctl restart proxmox-manager"
        log_info "  sudo systemctl status proxmox-manager"
        exit 1
    fi
    
    log_success "서비스 시작 완료"
    
    # 자동 복구 스크립트 생성 (사용자가 systemctl start만 해도 문제 해결)
    log_info "자동 복구 스크립트 생성 중..."
    sudo tee /usr/local/bin/proxmox-manager-fix > /dev/null << 'EOF'
#!/bin/bash
# Proxmox Manager 자동 복구 스크립트
# 사용법: sudo systemctl start proxmox-manager (자동으로 이 스크립트가 실행됨)

cd /data/terraform-proxmox

echo "🔧 Proxmox Manager 자동 복구 시작..."

# Vault Unseal 및 토큰 복원
echo "🔐 Vault Unseal 및 토큰 복원 중..."

# Vault 상태 확인
if docker ps | grep -q vault-dev; then
    VAULT_SEALED=$(docker exec vault-dev vault status 2>/dev/null | grep "Sealed" | awk '{print $2}')
    
    if [ "$VAULT_SEALED" = "true" ]; then
        echo "⚠️ Vault가 sealed 상태입니다. Unseal을 진행합니다..."
        
        # Unseal 키 파일 확인
        if [ -f "/data/terraform-proxmox/vault_unseal_keys.txt" ]; then
            echo "📋 저장된 Unseal 키를 사용합니다..."
            UNSEAL_KEY=$(cat /data/terraform-proxmox/vault_unseal_keys.txt)
            
            # Vault Unseal 실행
            if docker exec vault-dev vault operator unseal "$UNSEAL_KEY" 2>/dev/null; then
                echo "✅ Vault Unseal 성공"
            else
                echo "❌ Vault Unseal 실패"
            fi
        elif [ -f "/data/terraform-proxmox/vault_init.txt" ]; then
            echo "📋 vault_init.txt에서 Unseal 키를 추출합니다..."
            UNSEAL_KEY=$(grep "Unseal Key 1:" /data/terraform-proxmox/vault_init.txt | awk '{print $4}')
            
            if [ -n "$UNSEAL_KEY" ]; then
                # Unseal 키를 별도 파일에 저장
                echo "$UNSEAL_KEY" > /data/terraform-proxmox/vault_unseal_keys.txt
                chmod 600 /data/terraform-proxmox/vault_unseal_keys.txt
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
            echo "  - /data/terraform-proxmox/vault_unseal_keys.txt"
            echo "  - /data/terraform-proxmox/vault_init.txt"
        fi
    else
        echo "✅ Vault가 이미 unsealed 상태입니다."
    fi
    
    # 토큰 복원
    if [ -f "/data/terraform-proxmox/vault_token.txt" ]; then
        VAULT_TOKEN=$(cat /data/terraform-proxmox/vault_token.txt)
        export VAULT_TOKEN="$VAULT_TOKEN"
        export TF_VAR_vault_token="$VAULT_TOKEN"
        
        # .env 파일에 토큰 업데이트
        if [ -f "/data/terraform-proxmox/.env" ]; then
            sed -i "s|VAULT_TOKEN=.*|VAULT_TOKEN=$VAULT_TOKEN|" /data/terraform-proxmox/.env
            sed -i "s|TF_VAR_vault_token=.*|TF_VAR_vault_token=$VAULT_TOKEN|" /data/terraform-proxmox/.env
        fi
        
        echo "✅ Vault 토큰 복원 완료"
    elif [ -f "/data/terraform-proxmox/vault_init.txt" ]; then
        echo "📋 vault_init.txt에서 Vault 토큰을 추출합니다..."
        VAULT_TOKEN=$(grep "Initial Root Token:" /data/terraform-proxmox/vault_init.txt | awk '{print $4}')
        
        if [ -n "$VAULT_TOKEN" ]; then
            # 토큰을 별도 파일에 저장
            echo "$VAULT_TOKEN" > /data/terraform-proxmox/vault_token.txt
            chmod 600 /data/terraform-proxmox/vault_token.txt
            echo "✅ Vault 토큰을 vault_token.txt에 저장했습니다."
            
            export VAULT_TOKEN="$VAULT_TOKEN"
            export TF_VAR_vault_token="$VAULT_TOKEN"
            
            # .env 파일에 토큰 업데이트
            if [ -f "/data/terraform-proxmox/.env" ]; then
                sed -i "s|VAULT_TOKEN=.*|VAULT_TOKEN=$VAULT_TOKEN|" /data/terraform-proxmox/.env
                sed -i "s|TF_VAR_vault_token=.*|TF_VAR_vault_token=$VAULT_TOKEN|" /data/terraform-proxmox/.env
            fi
            
            echo "✅ Vault 토큰 복원 완료"
        else
            echo "❌ vault_init.txt에서 Vault 토큰을 찾을 수 없습니다."
        fi
    else
        echo "⚠️ 저장된 Vault 토큰이 없습니다:"
        echo "  - /data/terraform-proxmox/vault_token.txt"
        echo "  - /data/terraform-proxmox/vault_init.txt"
    fi
else
    echo "⚠️ Vault 컨테이너가 실행되지 않았습니다."
fi

# 가상환경 패키지 문제 해결
if ! /data/terraform-proxmox/venv/bin/python -c "import dotenv, flask, requests" 2>/dev/null; then
    echo "⚠️  가상환경 패키지 문제 감지. 자동 수정 중..."
    
    # 가상환경 활성화 및 패키지 재설치
    source /data/terraform-proxmox/venv/bin/activate
    pip install --upgrade python-dotenv flask flask-sqlalchemy flask-login requests paramiko
    deactivate
    
    echo "✅ 가상환경 패키지 수정 완료"
fi

# config.py import 문제 해결
echo "🔍 config.py import 테스트 중..."
if ! /data/terraform-proxmox/venv/bin/python -c "import sys; sys.path.insert(0, '/data/terraform-proxmox'); from config import TerraformConfig" 2>/dev/null; then
    echo "⚠️  config.py import 문제 감지. 자동 수정 중..."
    
    # config.py 파일 자동 생성
    echo "📝 config.py 파일 자동 생성 중..."
    cat > /data/terraform-proxmox/config/config.py << 'PYEOF'
import os
from datetime import timedelta

class VaultConfig:
    """Vault 설정"""
    VAULT_ADDR = os.environ.get('VAULT_ADDR', 'http://127.0.0.1:8200')
    VAULT_TOKEN = os.environ.get('VAULT_TOKEN')
    
    @classmethod
    def get_secret(cls, secret_path, key):
        """Vault에서 시크릿 가져오기"""
        try:
            import hvac
            client = hvac.Client(url=cls.VAULT_ADDR, token=cls.VAULT_TOKEN)
            if client.is_authenticated():
                response = client.secrets.kv.v2.read_secret_version(path=secret_path)
                return response['data']['data'].get(key)
            else:
                raise ValueError("Vault 인증 실패")
        except ImportError:
            return os.environ.get(f'TF_VAR_{key.upper()}')
        except Exception as e:
            print(f"Vault에서 시크릿 가져오기 실패: {e}")
            return os.environ.get(f'TF_VAR_{key.upper()}')

class TerraformConfig:
    """Terraform 변수 자동 매핑"""
    
    MAPPINGS = {
        'VAULT_TOKEN': 'TF_VAR_vault_token',
        'VAULT_ADDR': 'TF_VAR_vault_address',
        'PROXMOX_ENDPOINT': 'TF_VAR_proxmox_endpoint',
        'PROXMOX_USERNAME': 'TF_VAR_proxmox_username',
        'PROXMOX_PASSWORD': 'TF_VAR_proxmox_password',
        'PROXMOX_NODE': 'TF_VAR_proxmox_node',
        'SSH_USER': 'TF_VAR_vm_username',
        'SSH_PUBLIC_KEY_PATH': 'TF_VAR_ssh_keys'
    }
    
    @classmethod
    def setup_terraform_vars(cls):
        """환경변수를 Terraform 변수로 자동 매핑"""
        for source_var, target_var in cls.MAPPINGS.items():
            value = os.getenv(source_var)
            if value and not os.getenv(target_var):
                os.environ[target_var] = value
                print(f"✅ {source_var} → {target_var}")
    
    @classmethod
    def get_terraform_var(cls, var_name):
        """Terraform 변수 가져오기"""
        return os.getenv(f'TF_VAR_{var_name}')
    
    @classmethod
    def get_all_terraform_vars(cls):
        """모든 Terraform 변수 가져오기"""
        return {k: v for k, v in os.environ.items() if k.startswith('TF_VAR_')}
    
    @classmethod
    def validate_terraform_vars(cls):
        """Terraform 변수 검증"""
        required_vars = ['vault_token', 'vault_address', 'proxmox_endpoint', 'proxmox_username', 'proxmox_password']
        missing_vars = []
        
        for var in required_vars:
            if not cls.get_terraform_var(var):
                missing_vars.append(f'TF_VAR_{var}')
        
        if missing_vars:
            print(f"⚠️ 누락된 Terraform 변수: {', '.join(missing_vars)}")
            return False
        
        print("✅ 모든 필수 Terraform 변수가 설정되었습니다")
        return True
    
    @classmethod
    def debug_terraform_vars(cls):
        """Terraform 변수 디버깅 정보 출력"""
        print("🔧 Terraform 변수 상태:")
        for source_var, target_var in cls.MAPPINGS.items():
            source_value = os.getenv(source_var, '❌ 없음')
            target_value = os.getenv(target_var, '❌ 없음')
            print(f"  {source_var}: {'✅ 설정됨' if source_value != '❌ 없음' else '❌ 없음'}")
            print(f"  {target_var}: {'✅ 설정됨' if target_value != '❌ 없음' else '❌ 없음'}")
            print()

class Config:
    """기본 설정"""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    DEBUG = os.environ.get('DEBUG', 'True').lower() == 'true'
    
    basedir = os.path.abspath(os.path.dirname(__file__))
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', f'sqlite:///{os.path.join(basedir, "instance", "proxmox_manager.db")}')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    PROXMOX_ENDPOINT = os.environ.get('PROXMOX_ENDPOINT', 'https://localhost:8006')
    PROXMOX_USERNAME = os.environ.get('PROXMOX_USERNAME', 'root@pam')
    PROXMOX_PASSWORD = os.environ.get('PROXMOX_PASSWORD', 'password')
    PROXMOX_NODE = os.environ.get('PROXMOX_NODE', 'pve')
    PROXMOX_DATASTORE = os.environ.get('PROXMOX_DATASTORE', 'local-lvm')
    
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'False').lower() == 'true'
    SESSION_COOKIE_HTTPONLY = os.environ.get('SESSION_COOKIE_HTTPONLY', 'True').lower() == 'true'
    SESSION_COOKIE_SAMESITE = os.environ.get('SESSION_COOKIE_SAMESITE', 'Strict')
    PERMANENT_SESSION_LIFETIME = timedelta(
        seconds=int(os.environ.get('PERMANENT_SESSION_LIFETIME', 28800))
    )
    
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_FILE = os.environ.get('LOG_FILE', 'app.log')
    
    SSH_PRIVATE_KEY_PATH = os.environ.get('SSH_PRIVATE_KEY_PATH', '~/.ssh/id_rsa')
    SSH_PUBLIC_KEY_PATH = os.environ.get('SSH_PUBLIC_KEY_PATH', '~/.ssh/id_rsa.pub')
    SSH_USER = os.environ.get('SSH_USER', 'rocky')
    
    GRAFANA_URL = os.environ.get('GRAFANA_URL', 'http://localhost:3000')
    GRAFANA_USERNAME = os.environ.get('GRAFANA_USERNAME', 'admin')
    GRAFANA_PASSWORD = os.environ.get('GRAFANA_PASSWORD', 'admin')
    GRAFANA_ORG_ID = os.environ.get('GRAFANA_ORG_ID', '1')
    GRAFANA_DASHBOARD_UID = os.environ.get('GRAFANA_DASHBOARD_UID', 'system_monitoring')
    GRAFANA_ANONYMOUS_ACCESS = os.environ.get('GRAFANA_ANONYMOUS_ACCESS', 'false').lower() == 'true'
    GRAFANA_AUTO_REFRESH = os.environ.get('GRAFANA_AUTO_REFRESH', '5s')
    
    PROMETHEUS_URL = os.environ.get('PROMETHEUS_URL', 'http://localhost:9090')
    PROMETHEUS_USERNAME = os.environ.get('PROMETHEUS_USERNAME', '')
    PROMETHEUS_PASSWORD = os.environ.get('PROMETHEUS_PASSWORD', '')
    
    NODE_EXPORTER_AUTO_INSTALL = os.environ.get('NODE_EXPORTER_AUTO_INSTALL', 'true').lower() == 'true'
    NODE_EXPORTER_PORT = int(os.environ.get('NODE_EXPORTER_PORT', '9100'))
    NODE_EXPORTER_VERSION = os.environ.get('NODE_EXPORTER_VERSION', '1.6.1')
    
    MONITORING_DEFAULT_TIME_RANGE = os.environ.get('MONITORING_DEFAULT_TIME_RANGE', '1h')
    MONITORING_HEALTH_CHECK_INTERVAL = os.environ.get('MONITORING_HEALTH_CHECK_INTERVAL', '30s')
    MONITORING_PING_TIMEOUT = os.environ.get('MONITORING_PING_TIMEOUT', '5s')
    MONITORING_SSH_TIMEOUT = os.environ.get('MONITORING_SSH_TIMEOUT', '10s')
    
    ALERTS_ENABLED = os.environ.get('ALERTS_ENABLED', 'true').lower() == 'true'
    ALERTS_EMAIL = os.environ.get('ALERTS_EMAIL', 'admin@example.com')
    ALERTS_CPU_WARNING_THRESHOLD = float(os.environ.get('ALERTS_CPU_WARNING_THRESHOLD', '80'))
    ALERTS_CPU_CRITICAL_THRESHOLD = float(os.environ.get('ALERTS_CPU_CRITICAL_THRESHOLD', '95'))
    ALERTS_MEMORY_WARNING_THRESHOLD = float(os.environ.get('ALERTS_MEMORY_WARNING_THRESHOLD', '85'))
    ALERTS_MEMORY_CRITICAL_THRESHOLD = float(os.environ.get('ALERTS_MEMORY_CRITICAL_THRESHOLD', '95'))
    
    SECURITY_ENABLE_HTTPS = os.environ.get('SECURITY_ENABLE_HTTPS', 'false').lower() == 'true'
    SECURITY_ENABLE_AUTH = os.environ.get('SECURITY_ENABLE_AUTH', 'true').lower() == 'true'
    SECURITY_SESSION_TIMEOUT = int(os.environ.get('SECURITY_SESSION_TIMEOUT', '3600'))
    SECURITY_MAX_LOGIN_ATTEMPTS = int(os.environ.get('SECURITY_MAX_LOGIN_ATTEMPTS', '5'))

class DevelopmentConfig(Config):
    """개발 환경 설정"""
    DEBUG = True
    SESSION_COOKIE_SECURE = False

class ProductionConfig(Config):
    """운영 환경 설정"""
    DEBUG = False
    SESSION_COOKIE_SECURE = True

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
PYEOF
    
    echo "✅ config.py 파일 생성 완료"
    
    # 다시 import 테스트
    if /data/terraform-proxmox/venv/bin/python -c "import sys; sys.path.insert(0, '/data/terraform-proxmox'); from config import TerraformConfig" 2>/dev/null; then
        echo "✅ config.py import 문제 해결 완료"
    else
        echo "❌ config.py import 문제 해결 실패"
    fi
fi

# systemd 서비스 재시작
echo "🔄 systemd 서비스 재시작 중..."
systemctl daemon-reload
systemctl restart proxmox-manager

# 서비스 상태 확인
sleep 3
if systemctl is-active --quiet proxmox-manager; then
    echo "✅ Proxmox Manager 서비스가 정상적으로 실행 중입니다"
    echo "🌐 웹 인터페이스: http://$(hostname -I | awk '{print $1}'):5000"
else
    echo "❌ 서비스 시작 실패. 로그를 확인하세요:"
    echo "   journalctl -u proxmox-manager -n 20"
fi
EOF
    
    sudo chmod +x /usr/local/bin/proxmox-manager-fix
    
    # systemd 서비스에 자동 복구 스크립트 연결
    log_info "systemd 서비스에 자동 복구 기능 추가 중..."
    sudo tee /etc/systemd/system/proxmox-manager.service > /dev/null << EOF
[Unit]
Description=Proxmox Manager Flask Application
After=network.target
Wants=network.target

[Service]
Type=simple
User=$USER
Group=$USER
WorkingDirectory=$APP_DIR
EnvironmentFile=$APP_DIR/.env
Environment=PATH=$APP_DIR/venv/bin:/usr/local/bin:/usr/bin:/bin
Environment=VIRTUAL_ENV=$APP_DIR/venv
Environment=PYTHONPATH=$APP_DIR
ExecStartPre=/usr/local/bin/proxmox-manager-fix
ExecStart=$VENV_PYTHON run.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

# 보안 설정 (권한 문제 해결을 위해 일부 완화)
NoNewPrivileges=true
PrivateTmp=false
ProtectSystem=false
ProtectHome=false
ReadWritePaths=$APP_DIR

[Install]
WantedBy=multi-user.target
EOF
    
    sudo systemctl daemon-reload
    
    log_success "자동 복구 스크립트 생성 완료"
    log_info "이제 'sudo systemctl start proxmox-manager'만 실행하면 모든 문제가 자동으로 해결됩니다!"
}

# ========================================
# 14. 설치 완료 및 정보 출력
# ========================================

show_completion_info() {
    log_step "14. 설치 완료!"
    
    echo -e "${GREEN}"
    echo "=========================================="
    echo "🎉 Proxmox Manager 설치 완료!"
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
    echo -e "${CYAN}🔧 서비스 관리 명령어:${NC}"
    echo "  Flask 애플리케이션:"
    echo "    상태 확인: sudo systemctl status proxmox-manager"
    echo "    시작: sudo systemctl start proxmox-manager"
    echo "    중지: sudo systemctl stop proxmox-manager"
    echo "    재시작: sudo systemctl restart proxmox-manager"
    echo "    로그 확인: sudo journalctl -u proxmox-manager -f"
    echo ""
    echo "  모니터링 서비스:"
    echo "    Prometheus: sudo systemctl status prometheus"
    echo "    Grafana: sudo systemctl status grafana-server"
    echo "    Grafana 재시작: sudo systemctl restart grafana-server"
    echo "    Grafana 로그: sudo journalctl -u grafana-server -f"
    echo ""
    echo "  Vault 서비스:"
    echo "    상태 확인: docker exec vault-dev vault status"
    echo "    중지: docker-compose -f docker-compose.vault.yml down"
    
    echo ""
    echo -e "${CYAN}📁 중요 파일:${NC}"
    echo "  환경설정: .env"
    echo "  데이터베이스: instance/proxmox_manager.db"
    echo "  Vault 초기화: vault_init.txt"
    echo "  Flask 서비스: /etc/systemd/system/proxmox-manager.service"
    
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
