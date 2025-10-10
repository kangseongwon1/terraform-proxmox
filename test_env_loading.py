#!/usr/bin/env python3
"""
환경변수 로딩 테스트 스크립트
"""
import os
import sys

def test_env_loading():
    print("🔧 환경변수 로딩 테스트 시작")
    print("=" * 50)
    
    # 1. .env 파일 존재 확인
    env_file = '.env'
    print(f"1. .env 파일 존재 확인: {os.path.exists(env_file)}")
    
    if os.path.exists(env_file):
        print(f"   .env 파일 경로: {os.path.abspath(env_file)}")
        
        # .env 파일 내용 확인
        print(f"2. .env 파일 내용 확인:")
        try:
            with open(env_file, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    if 'DATASTORE' in line.upper() or 'HDD' in line.upper():
                        print(f"   라인 {line_num}: {line.strip()}")
        except Exception as e:
            print(f"   ❌ .env 파일 읽기 실패: {e}")
    
    # 2. dotenv 로드 전 환경변수 확인
    print(f"\n3. dotenv 로드 전 환경변수:")
    print(f"   PROXMOX_HDD_DATASTORE: {os.environ.get('PROXMOX_HDD_DATASTORE', '없음')}")
    print(f"   HDD_DATASTORE: {os.environ.get('HDD_DATASTORE', '없음')}")
    
    # 3. dotenv 강제 로드
    print(f"\n4. dotenv 강제 로드:")
    try:
        from dotenv import load_dotenv
        load_dotenv()
        print(f"   ✅ dotenv 로드 성공")
    except Exception as e:
        print(f"   ❌ dotenv 로드 실패: {e}")
        return False
    
    # 4. dotenv 로드 후 환경변수 확인
    print(f"\n5. dotenv 로드 후 환경변수:")
    print(f"   PROXMOX_HDD_DATASTORE: {os.environ.get('PROXMOX_HDD_DATASTORE', '없음')}")
    print(f"   HDD_DATASTORE: {os.environ.get('HDD_DATASTORE', '없음')}")
    
    # 5. 최종 datastore 값 결정
    hdd_datastore = os.environ.get('PROXMOX_HDD_DATASTORE') or os.environ.get('HDD_DATASTORE')
    print(f"\n6. 최종 HDD datastore: {hdd_datastore}")
    
    # 6. terraform.tfvars.json 파일 확인
    tfvars_file = 'terraform/terraform.tfvars.json'
    print(f"\n7. terraform.tfvars.json 파일 확인:")
    print(f"   파일 존재: {os.path.exists(tfvars_file)}")
    
    if os.path.exists(tfvars_file):
        try:
            import json
            with open(tfvars_file, 'r', encoding='utf-8') as f:
                tfvars = json.load(f)
            print(f"   현재 proxmox_hdd_datastore: {tfvars.get('proxmox_hdd_datastore', '없음')}")
        except Exception as e:
            print(f"   ❌ tfvars 파일 읽기 실패: {e}")
    
    print("=" * 50)
    print("🔧 테스트 완료")
    
    return True

if __name__ == "__main__":
    test_env_loading()
