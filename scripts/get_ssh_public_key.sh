#!/bin/bash
# SSH 공개키를 가져와서 terraform.tfvars.json에 추가하는 스크립트

echo "🔑 SSH 공개키 확인 중..."

# SSH 공개키 파일 확인
if [ -f ~/.ssh/id_rsa.pub ]; then
    SSH_PUBLIC_KEY=$(cat ~/.ssh/id_rsa.pub)
    echo "✅ SSH 공개키 발견:"
    echo "$SSH_PUBLIC_KEY"
    echo ""
    
    # terraform.tfvars.json 파일 경로
    TFVARS_FILE="terraform/terraform.tfvars.json"
    
    if [ -f "$TFVARS_FILE" ]; then
        echo "🔧 terraform.tfvars.json 업데이트 중..."
        
        # 임시 파일 생성
        TEMP_FILE=$(mktemp)
        
        # jq를 사용하여 ssh_keys 업데이트
        jq --arg key "$SSH_PUBLIC_KEY" '.ssh_keys = [$key]' "$TFVARS_FILE" > "$TEMP_FILE"
        
        # 원본 파일 백업
        cp "$TFVARS_FILE" "${TFVARS_FILE}.backup.$(date +%Y%m%d_%H%M%S)"
        
        # 임시 파일을 원본으로 이동
        mv "$TEMP_FILE" "$TFVARS_FILE"
        
        echo "✅ terraform.tfvars.json 업데이트 완료"
        echo "📋 백업 파일: ${TFVARS_FILE}.backup.$(date +%Y%m%d_%H%M%S)"
    else
        echo "❌ terraform.tfvars.json 파일을 찾을 수 없습니다: $TFVARS_FILE"
        exit 1
    fi
else
    echo "❌ SSH 공개키 파일을 찾을 수 없습니다: ~/.ssh/id_rsa.pub"
    echo "💡 SSH 키를 생성하려면: ssh-keygen -t rsa -b 4096 -C \"your_email@example.com\""
    exit 1
fi

echo ""
echo "🎯 다음 단계:"
echo "1. terraform plan으로 변경사항 확인"
echo "2. terraform apply로 서버 재생성"
echo "3. ssh rocky@<server_ip>로 연결 테스트"
