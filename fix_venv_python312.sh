#!/bin/bash

# 가상환경 Python 3.12 문제 해결 스크립트
echo "🔧 가상환경 Python 3.12 문제 해결 중..."

# 현재 디렉토리 확인
if [ ! -f "requirements.txt" ]; then
    echo "❌ requirements.txt 파일을 찾을 수 없습니다. 프로젝트 루트 디렉토리에서 실행하세요."
    exit 1
fi

# Python 3.12 확인
if ! command -v python3.12 &> /dev/null; then
    echo "❌ python3.12를 찾을 수 없습니다"
    exit 1
fi

PYTHON312_PATH=$(which python3.12)
echo "✅ Python 3.12 경로: $PYTHON312_PATH"

# 기존 가상환경 백업 및 삭제
if [ -d "venv" ]; then
    echo "📦 기존 가상환경 백업 중..."
    mv venv venv_backup_$(date +%Y%m%d_%H%M%S)
    echo "✅ 기존 가상환경 백업 완료"
fi

# Python 3.12로 새 가상환경 생성
echo "🆕 Python 3.12로 새 가상환경 생성 중..."
python3.12 -m venv venv

if [ $? -eq 0 ]; then
    echo "✅ 가상환경 생성 완료"
else
    echo "❌ 가상환경 생성 실패"
    exit 1
fi

# 가상환경 활성화
echo "🔌 가상환경 활성화 중..."
source venv/bin/activate

# 가상환경에서 Python 버전 확인
if command -v python &> /dev/null; then
    VENV_PYTHON_VERSION=$(python --version 2>&1)
    echo "✅ 가상환경 Python 버전: $VENV_PYTHON_VERSION"
    
    if [[ "$VENV_PYTHON_VERSION" == *"3.12"* ]]; then
        echo "🎉 가상환경이 Python 3.12를 사용합니다!"
    else
        echo "⚠️ 가상환경이 Python 3.12가 아닙니다: $VENV_PYTHON_VERSION"
    fi
else
    echo "❌ 가상환경에서 python 명령어를 찾을 수 없습니다"
    exit 1
fi

# pip 업그레이드
echo "⬆️ pip 업그레이드 중..."
python -m pip install --upgrade pip

if [ $? -eq 0 ]; then
    echo "✅ pip 업그레이드 완료"
else
    echo "❌ pip 업그레이드 실패"
    exit 1
fi

# pip 버전 확인
PIP_VERSION=$(pip --version 2>&1)
echo "✅ pip 버전: $PIP_VERSION"

# requirements.txt 설치
echo "📦 Python 패키지 설치 중..."
pip install -r requirements.txt

if [ $? -eq 0 ]; then
    echo "✅ Python 패키지 설치 완료"
else
    echo "❌ Python 패키지 설치 실패"
    exit 1
fi

echo "🎉 가상환경 Python 3.12 문제 해결 완료!"
echo ""
echo "📋 다음 단계:"
echo "1. 가상환경 활성화: source venv/bin/activate"
echo "2. Python 버전 확인: python --version"
echo "3. pip 버전 확인: pip --version"
echo "4. 설치 스크립트 재실행: ./install_complete_system.sh"
