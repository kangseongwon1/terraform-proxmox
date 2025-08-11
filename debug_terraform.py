#!/usr/bin/env python3
"""
Terraform 서비스 디버깅 스크립트
"""

import os
import sys
import json

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.terraform_service import TerraformService

def debug_terraform():
    """Terraform 서비스 디버깅"""
    print("🔧 Terraform 서비스 디버깅 시작")
    
    # Terraform 서비스 초기화
    terraform_service = TerraformService()
    
    # tfvars 파일 확인
    print(f"🔧 tfvars 파일 경로: {terraform_service.tfvars_file}")
    if os.path.exists(terraform_service.tfvars_file):
        print("✅ tfvars 파일 존재")
        try:
            with open(terraform_service.tfvars_file, 'r', encoding='utf-8') as f:
                content = f.read()
                print(f"📄 tfvars 파일 크기: {len(content)} 문자")
                print(f"📄 tfvars 파일 내용 미리보기: {content[:200]}...")
        except Exception as e:
            print(f"❌ tfvars 파일 읽기 실패: {e}")
    else:
        print("❌ tfvars 파일 없음")
    
    # Terraform 디렉토리 확인
    print(f"🔧 Terraform 디렉토리: {terraform_service.terraform_dir}")
    if os.path.exists(terraform_service.terraform_dir):
        print("✅ Terraform 디렉토리 존재")
        files = os.listdir(terraform_service.terraform_dir)
        print(f"📁 Terraform 디렉토리 파일들: {files}")
    else:
        print("❌ Terraform 디렉토리 없음")
    
    # Terraform 초기화 테스트
    print("\n🔧 Terraform 초기화 테스트")
    init_success = terraform_service.init()
    print(f"🔧 초기화 결과: {init_success}")
    
    # Terraform 계획 테스트
    print("\n🔧 Terraform 계획 테스트")
    plan_success, plan_output = terraform_service.plan()
    print(f"🔧 계획 결과: success={plan_success}")
    print(f"🔧 계획 출력 길이: {len(plan_output) if plan_output else 0}")
    if plan_output:
        print(f"🔧 계획 출력 미리보기: {plan_output[:300]}...")
    
    print("\n✅ 디버깅 완료")

if __name__ == "__main__":
    debug_terraform() 