#!/bin/bash

# 서버 자동 생성 시스템 설치 스크립트

echo "🚀 서버 자동 생성 시스템 설치를 시작합니다..."

# 필요한 디렉토리 생성
mkdir -p projects terraform ansible templates

# 가상환경 생성 및 활성화
echo "📦 Python 가상환경을 생성합니다..."
python3.8 -m venv venv
source venv/bin/activate

# Python 의존성 설치
echo "📦 Python 패키지를 설치합니다..."
pip install -r requirements.txt

# Terraform 설치 (Ubuntu/Debian)
echo "🔧 Terraform을 설치합니다..."
if ! command -v terraform &> /dev/null; then
    curl -fsSL https://apt.releases.hashicorp.com/gpg | sudo apt-key add -
    sudo apt-add-repository "deb [arch=amd64] https://apt.releases.hashicorp.com $(lsb_release -cs) main"
    sudo apt-get update && sudo apt-get install terraform
else
    echo "✅ Terraform이 이미 설치되어 있습니다."
fi

# Ansible 설치
echo "🔧 Ansible을 설치합니다..."
if ! command -v ansible &> /dev/null; then
    pip install ansible
else
    echo "✅ Ansible이 이미 설치되어 있습니다."
fi

# 설정 파일 생성
if [ ! -f .env ]; then
    echo "📝 .env 파일을 생성합니다..."
    cp .env.example .env
    echo "⚠️  .env 파일을 수정하여 Proxmox 설정을 입력해주세요."
fi

# SSH 키 생성 (없는 경우)
if [ ! -f ~/.ssh/id_rsa ]; then
    echo "🔑 SSH 키를 생성합니다..."
    ssh-keygen -t rsa -b 4096 -f ~/.ssh/id_rsa -N ""
fi

# 권한 설정
chmod +x setup.sh
chmod 600 ~/.ssh/id_rsa
chmod 644 ~/.ssh/id_rsa.pub

echo "✅ 설치가 완료되었습니다!"
echo ""
echo "다음 단계:"
echo "1. .env 파일을 수정하여 Proxmox 설정을 입력하세요"
echo "2. python app.py 명령으로 서버를 시작하세요"
echo "3. 브라우저에서 http://localhost:5000 에 접속하세요"
echo ""
echo "Docker를 사용하려면:"
echo "1. docker-compose up -d 명령을 실행하세요"
echo "2. 브라우저에서 http://localhost 에 접속하세요"
