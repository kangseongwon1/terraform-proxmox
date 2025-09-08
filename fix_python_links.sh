#!/bin/bash

# Python 심볼릭 링크 생성 스크립트
echo "🔧 Python 심볼릭 링크 생성 중..."

# Python 3.12 경로 찾기
PYTHON312_PATH=$(which python3.12 2>/dev/null)

if [ -z "$PYTHON312_PATH" ]; then
    echo "❌ python3.12를 찾을 수 없습니다"
    exit 1
fi

echo "✅ Python 3.12 경로: $PYTHON312_PATH"

# 설치 디렉토리 확인
PYTHON_DIR=$(dirname "$PYTHON312_PATH")
echo "📁 Python 설치 디렉토리: $PYTHON_DIR"

# 심볼릭 링크 생성
echo "🔗 python 심볼릭 링크 생성 중..."
ln -sf "$PYTHON312_PATH" "$PYTHON_DIR/python"
ln -sf "$PYTHON312_PATH" "$PYTHON_DIR/python3"

# 링크 확인
if [ -L "$PYTHON_DIR/python" ]; then
    echo "✅ python 링크 생성 완료: $PYTHON_DIR/python"
else
    echo "❌ python 링크 생성 실패"
fi

if [ -L "$PYTHON_DIR/python3" ]; then
    echo "✅ python3 링크 생성 완료: $PYTHON_DIR/python3"
else
    echo "❌ python3 링크 생성 실패"
fi

# 테스트
echo "🧪 Python 명령어 테스트 중..."
if command -v python &> /dev/null; then
    PYTHON_VERSION=$(python --version 2>&1)
    echo "✅ python 명령어 사용 가능: $PYTHON_VERSION"
    echo "📍 python 경로: $(which python)"
else
    echo "❌ python 명령어를 찾을 수 없습니다"
fi

if command -v python3 &> /dev/null; then
    PYTHON3_VERSION=$(python3 --version 2>&1)
    echo "✅ python3 명령어 사용 가능: $PYTHON3_VERSION"
    echo "📍 python3 경로: $(which python3)"
else
    echo "❌ python3 명령어를 찾을 수 없습니다"
fi

echo "🎉 Python 심볼릭 링크 설정 완료!"
