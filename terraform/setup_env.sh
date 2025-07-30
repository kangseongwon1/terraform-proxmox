#!/bin/bash

# Terraform 환경 변수 설정 스크립트

# Vault 토큰 파일에서 환경 변수 설정
if [ -f "../.env.tokens" ]; then
    source ../.env.tokens
    echo "환경 변수가 설정되었습니다."
    echo "TERRAFORM_TOKEN: ${TERRAFORM_TOKEN:0:10}..."
    echo "FLASK_TOKEN: ${FLASK_TOKEN:0:10}..."
else
    echo "토큰 파일을 찾을 수 없습니다: ../.env.tokens"
    exit 1
fi

# Terraform 실행
echo "Terraform을 실행합니다..."
terraform "$@" 
