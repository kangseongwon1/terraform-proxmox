#!/bin/bash

# Grafana 익명 접근 설정 스크립트

echo "🔧 Grafana 익명 접근 설정 시작..."

# Grafana 설정 파일 찾기
GRAFANA_CONFIG=""
if [ -f "/etc/grafana/grafana.ini" ]; then
    GRAFANA_CONFIG="/etc/grafana/grafana.ini"
elif [ -f "/usr/local/etc/grafana/grafana.ini" ]; then
    GRAFANA_CONFIG="/usr/local/etc/grafana/grafana.ini"
elif [ -f "/opt/grafana/conf/grafana.ini" ]; then
    GRAFANA_CONFIG="/opt/grafana/conf/grafana.ini"
else
    echo "❌ Grafana 설정 파일을 찾을 수 없습니다."
    echo "Grafana가 설치되어 있는지 확인하세요."
    exit 1
fi

echo "📁 Grafana 설정 파일: $GRAFANA_CONFIG"

# 백업 생성
cp "$GRAFANA_CONFIG" "${GRAFANA_CONFIG}.backup.$(date +%Y%m%d_%H%M%S)"
echo "✅ 설정 파일 백업 완료"

# 익명 접근 설정
echo "🔧 익명 접근 설정 중..."

# [auth.anonymous] 섹션 설정
if grep -q "\[auth.anonymous\]" "$GRAFANA_CONFIG"; then
    echo "📝 기존 [auth.anonymous] 섹션 수정 중..."
    sed -i '/\[auth.anonymous\]/,/^\[/ {
        s/^enabled = .*/enabled = true/
        s/^org_name = .*/org_name = Main Org./
        s/^org_role = .*/org_role = Viewer/
        s/^hide_version = .*/hide_version = false/
    }' "$GRAFANA_CONFIG"
else
    echo "📝 새로운 [auth.anonymous] 섹션 추가 중..."
    cat >> "$GRAFANA_CONFIG" << 'EOF'

[auth.anonymous]
enabled = true
org_name = Main Org.
org_role = Viewer
hide_version = false
EOF
fi

# [security] 섹션 설정
if grep -q "\[security\]" "$GRAFANA_CONFIG"; then
    echo "📝 기존 [security] 섹션 수정 중..."
    sed -i '/\[security\]/,/^\[/ {
        s/^allow_embedding = .*/allow_embedding = true/
        s/^cookie_secure = .*/cookie_secure = false/
        s/^cookie_samesite = .*/cookie_samesite = lax/
    }' "$GRAFANA_CONFIG"
else
    echo "📝 새로운 [security] 섹션 추가 중..."
    cat >> "$GRAFANA_CONFIG" << 'EOF'

[security]
allow_embedding = true
cookie_secure = false
cookie_samesite = lax
EOF
fi

echo "✅ Grafana 설정 완료"
echo "🔄 Grafana 서비스 재시작 중..."

# Grafana 서비스 재시작
if systemctl is-active --quiet grafana-server; then
    sudo systemctl restart grafana-server
    echo "✅ Grafana 서비스 재시작 완료"
elif systemctl is-active --quiet grafana; then
    sudo systemctl restart grafana
    echo "✅ Grafana 서비스 재시작 완료"
else
    echo "⚠️  Grafana 서비스를 찾을 수 없습니다. 수동으로 재시작하세요."
fi

echo ""
echo "🎉 Grafana 익명 접근 설정 완료!"
echo ""
echo "📋 설정된 내용:"
echo "   - 익명 사용자 접근 허용"
echo "   - iframe 임베딩 허용"
echo "   - 기본 조직: Main Org."
echo "   - 기본 역할: Viewer"
echo ""
echo "🌐 테스트 URL:"
echo "   http://localhost:3000/d/system_monitoring?kiosk=tv"
echo ""
echo "⚠️  보안 주의사항:"
echo "   - 이 설정은 개발/테스트 환경용입니다"
echo "   - 프로덕션 환경에서는 적절한 인증을 설정하세요"
