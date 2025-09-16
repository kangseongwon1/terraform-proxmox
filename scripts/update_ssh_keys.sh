#!/bin/bash
# SSH 공개키를 terraform.tfvars.json에 업데이트하는 스크립트

echo "🔑 SSH 공개키 업데이트 스크립트"
echo "================================"

# 현재 사용자 확인
CURRENT_USER=$(whoami)
echo "현재 사용자: $CURRENT_USER"

# SSH 공개키 파일 확인
SSH_PUBLIC_KEY_FILE="$HOME/.ssh/id_rsa.pub"

if [ ! -f "$SSH_PUBLIC_KEY_FILE" ]; then
    echo "❌ SSH 공개키 파일을 찾을 수 없습니다: $SSH_PUBLIC_KEY_FILE"
    echo "💡 SSH 키를 생성하려면:"
    echo "   ssh-keygen -t rsa -b 4096 -C \"$CURRENT_USER@$(hostname)\""
    exit 1
fi

# SSH 공개키 읽기
SSH_PUBLIC_KEY=$(cat "$SSH_PUBLIC_KEY_FILE")
echo "✅ SSH 공개키 발견:"
echo "$SSH_PUBLIC_KEY"
echo ""

# terraform.tfvars.json 파일 경로
TFVARS_FILE="terraform/terraform.tfvars.json"

if [ ! -f "$TFVARS_FILE" ]; then
    echo "❌ terraform.tfvars.json 파일을 찾을 수 없습니다: $TFVARS_FILE"
    exit 1
fi

echo "🔧 terraform.tfvars.json 업데이트 중..."

# jq가 설치되어 있는지 확인
if ! command -v jq &> /dev/null; then
    echo "❌ jq가 설치되지 않았습니다. 설치 중..."
    if command -v apt &> /dev/null; then
        sudo apt update && sudo apt install -y jq
    elif command -v yum &> /dev/null; then
        sudo yum install -y jq
    elif command -v dnf &> /dev/null; then
        sudo dnf install -y jq
    else
        echo "❌ 패키지 매니저를 찾을 수 없습니다. jq를 수동으로 설치하세요."
        exit 1
    fi
fi

# 백업 생성
BACKUP_FILE="${TFVARS_FILE}.backup.$(date +%Y%m%d_%H%M%S)"
cp "$TFVARS_FILE" "$BACKUP_FILE"
echo "📋 백업 파일 생성: $BACKUP_FILE"

# 임시 파일 생성
TEMP_FILE=$(mktemp)

# jq를 사용하여 ssh_keys 업데이트
jq --arg key "$SSH_PUBLIC_KEY" '.ssh_keys = [$key]' "$TFVARS_FILE" > "$TEMP_FILE"

# 업데이트된 내용 확인
echo "🔍 업데이트된 ssh_keys:"
jq -r '.ssh_keys[0]' "$TEMP_FILE"
echo ""

# 원본 파일을 임시 파일로 교체
mv "$TEMP_FILE" "$TFVARS_FILE"

echo "✅ terraform.tfvars.json 업데이트 완료"
echo ""
echo "🎯 다음 단계:"
echo "1. cd terraform"
echo "2. terraform plan"
echo "3. terraform apply"
echo "4. ssh rocky@<server_ip>로 연결 테스트"
echo ""
echo "📋 백업 파일: $BACKUP_FILE"
