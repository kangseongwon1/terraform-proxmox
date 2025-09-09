#!/bin/bash

# Node.js/npm 호환성 문제 해결 스크립트
echo "🔧 Node.js/npm 호환성 문제 해결 중..."

# 현재 Node.js 버전 확인
if command -v node &> /dev/null; then
    NODE_VERSION=$(node --version)
    echo "📋 현재 Node.js 버전: $NODE_VERSION"
    
    NODE_MAJOR_VERSION=$(echo $NODE_VERSION | cut -d'.' -f1 | sed 's/v//')
    echo "📋 Node.js 메이저 버전: $NODE_MAJOR_VERSION"
else
    echo "❌ Node.js가 설치되지 않았습니다"
    exit 1
fi

# 현재 npm 버전 확인
if command -v npm &> /dev/null; then
    NPM_VERSION=$(npm --version)
    echo "📋 현재 npm 버전: $NPM_VERSION"
else
    echo "❌ npm이 설치되지 않았습니다"
    exit 1
fi

# 호환성 문제 해결
if [ "$NODE_MAJOR_VERSION" -lt 20 ]; then
    echo "⚠️ Node.js 18 감지, 호환되는 npm 버전으로 다운그레이드 중..."
    
    # npm 10.x로 다운그레이드 (Node.js 18과 호환)
    sudo npm install -g npm@10
    
    if [ $? -eq 0 ]; then
        NEW_NPM_VERSION=$(npm --version)
        echo "✅ npm 다운그레이드 완료: $NEW_NPM_VERSION"
    else
        echo "❌ npm 다운그레이드 실패"
        exit 1
    fi
else
    echo "✅ Node.js 20+ 감지, npm 최신 버전으로 업그레이드 중..."
    
    # npm 최신 버전으로 업그레이드
    sudo npm install -g npm@latest
    
    if [ $? -eq 0 ]; then
        NEW_NPM_VERSION=$(npm --version)
        echo "✅ npm 업그레이드 완료: $NEW_NPM_VERSION"
    else
        echo "❌ npm 업그레이드 실패"
        exit 1
    fi
fi

# 최종 버전 확인
echo ""
echo "🎉 Node.js/npm 호환성 문제 해결 완료!"
echo "📋 최종 버전:"
echo "   Node.js: $(node --version)"
echo "   npm: $(npm --version)"

# 호환성 테스트
echo ""
echo "🧪 호환성 테스트 중..."
npm --version > /dev/null 2>&1

if [ $? -eq 0 ]; then
    echo "✅ npm 명령어 정상 작동"
else
    echo "❌ npm 명령어 오류"
    exit 1
fi

echo ""
echo "📋 다음 단계:"
echo "1. 설치 스크립트 재실행: ./install_complete_system.sh"
echo "2. 또는 Node.js 20+로 업그레이드 고려"
