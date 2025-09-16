#!/bin/bash
# SSH 공개키를 프로젝트 디렉토리에 복사하고 terraform.tfvars.json에 설정하는 스크립트

echo "🔑 SSH 공개키 설정 스크립트"
echo "=============================="

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

# 방법 1: 프로젝트 디렉토리에 SSH 키 파일 복사
echo "📋 방법 1: 프로젝트 디렉토리에 SSH 키 파일 복사"
PROJECT_SSH_KEY="ssh_keys/id_rsa.pub"
mkdir -p ssh_keys
cp "$SSH_PUBLIC_KEY_FILE" "$PROJECT_SSH_KEY"
echo "✅ SSH 공개키를 $PROJECT_SSH_KEY에 복사했습니다"

# terraform.tfvars.json 파일 경로
TFVARS_FILE="terraform/terraform.tfvars.json"

if [ ! -f "$TFVARS_FILE" ]; then
    echo "❌ terraform.tfvars.json 파일을 찾을 수 없습니다: $TFVARS_FILE"
    exit 1
fi

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

# 방법 1: 프로젝트 상대 경로 사용
echo "🔧 방법 1: 프로젝트 상대 경로로 terraform.tfvars.json 업데이트 중..."
jq --arg key "../$PROJECT_SSH_KEY" '.ssh_keys = [$key]' "$TFVARS_FILE" > "$TEMP_FILE"

# 업데이트된 내용 확인
echo "🔍 업데이트된 ssh_keys (방법 1):"
jq -r '.ssh_keys[0]' "$TEMP_FILE"
echo ""

# 원본 파일을 임시 파일로 교체
mv "$TEMP_FILE" "$TFVARS_FILE"

echo "✅ terraform.tfvars.json 업데이트 완료 (방법 1)"
echo ""
echo "📋 방법 2: 홈 디렉토리 경로 사용"
echo "   terraform.tfvars.json에서 ssh_keys를 [\"~/.ssh/id_rsa.pub\"]로 설정"
echo ""
echo "🎯 다음 단계:"
echo "1. cd terraform"
echo "2. terraform plan"
echo "3. terraform apply"
echo "4. ssh rocky@<server_ip>로 연결 테스트"
echo ""
echo "📋 백업 파일: $BACKUP_FILE"
echo "📋 SSH 키 파일: $PROJECT_SSH_KEY"
