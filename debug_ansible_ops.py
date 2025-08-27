#!/usr/bin/env python3
"""
역할 할당 API 직접 테스트
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.services.ansible_service import AnsibleService
import requests
import json

def test_role_assignment_api():
    """역할 할당 API 직접 테스트"""
    print("🧪 역할 할당 API 직접 테스트")
    
    # Flask 애플리케이션 컨텍스트 설정
    app = create_app()
    
    with app.app_context():
        # 1. Ansible 서비스 직접 테스트
        print("\n1️⃣ Ansible 서비스 직접 테스트")
        ansible_service = AnsibleService()
        
        # test 서버에 web 역할 할당
        success, message = ansible_service.assign_role_to_server("test", "web")
        print(f"   결과: {success} - {message}")
        
        # 2. HTTP API 직접 테스트
        print("\n2️⃣ HTTP API 직접 테스트")
        
        # Flask 앱을 테스트 모드로 실행
        with app.test_client() as client:
            # 역할 할당 API 호출
            response = client.post(
                '/api/assign_role/test',
                json={'role': 'web'},
                content_type='application/json'
            )
            
            print(f"   상태 코드: {response.status_code}")
            print(f"   응답: {response.get_json()}")
        
        # 3. 실제 HTTP 요청 테스트 (Flask 앱이 실행 중일 때)
        print("\n3️⃣ 실제 HTTP 요청 테스트")
        try:
            response = requests.post(
                'http://localhost:5000/api/assign_role/test',
                json={'role': 'web'},
                headers={'Content-Type': 'application/json'}
            )
            print(f"   상태 코드: {response.status_code}")
            print(f"   응답: {response.json()}")
        except requests.exceptions.ConnectionError:
            print("   Flask 앱이 실행되지 않았습니다. 'python run.py'로 앱을 시작하세요.")

if __name__ == "__main__":
    test_role_assignment_api()
