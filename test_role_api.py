#!/usr/bin/env python3
"""
역할 할당 API 직접 테스트
"""

import requests
import json

def test_role_assignment_api():
    """역할 할당 API 직접 테스트"""
    print("🧪 역할 할당 API 직접 테스트")
    
    # Flask 앱이 실행 중인지 확인
    try:
        # 1. 세션 체크
        print("\n1️⃣ 세션 체크")
        response = requests.get('http://localhost:5000/api/session/check')
        print(f"   상태 코드: {response.status_code}")
        print(f"   응답: {response.json()}")
        
        if response.status_code != 200:
            print("   ❌ 세션이 유효하지 않습니다. 로그인이 필요합니다.")
            return
        
        # 2. 역할 할당 API 호출
        print("\n2️⃣ 역할 할당 API 호출")
        response = requests.post(
            'http://localhost:5000/api/assign_role/test',
            json={'role': 'was'},
            headers={'Content-Type': 'application/json'}
        )
        
        print(f"   상태 코드: {response.status_code}")
        print(f"   응답: {response.json()}")
        
        if response.status_code == 200:
            print("   ✅ API 호출 성공")
        else:
            print("   ❌ API 호출 실패")
            
    except requests.exceptions.ConnectionError:
        print("   ❌ Flask 앱이 실행되지 않았습니다. 'python run.py'로 앱을 시작하세요.")
    except Exception as e:
        print(f"   ❌ 오류 발생: {e}")

if __name__ == "__main__":
    test_role_assignment_api()
