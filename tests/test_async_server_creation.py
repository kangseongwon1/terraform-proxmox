#!/usr/bin/env python3
"""
비동기 서버 생성 테스트 스크립트
"""
import requests
import time
import json
import sys
from typing import Dict, Any

class AsyncServerTest:
    def __init__(self, base_url: str = "http://127.0.0.1:5000"):
        self.base_url = base_url
        self.session = requests.Session()
        self.task_id = None
        
    def login(self, username: str = "admin", password: str = "admin123!") -> bool:
        """로그인"""
        print("🔐 로그인 중...")
        try:
            response = self.session.post(
                f"{self.base_url}/login",
                json={"username": username, "password": password},
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    print(f"✅ 로그인 성공: {result['user']['username']}")
                    return True
                else:
                    print(f"❌ 로그인 실패: {result.get('error', '알 수 없는 오류')}")
                    return False
            else:
                print(f"❌ 로그인 실패: HTTP {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ 로그인 오류: {e}")
            return False
    
    def create_server_async(self, server_config: Dict[str, Any]) -> bool:
        """비동기 서버 생성 요청"""
        print(f"🚀 서버 생성 요청: {server_config['name']}")
        try:
            response = self.session.post(
                f"{self.base_url}/api/servers/async",
                json=server_config,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    self.task_id = result.get('task_id')
                    print(f"✅ 서버 생성 작업 시작: {result['message']}")
                    print(f"📋 Task ID: {self.task_id}")
                    return True
                else:
                    print(f"❌ 서버 생성 실패: {result.get('error', '알 수 없는 오류')}")
                    return False
            else:
                print(f"❌ 서버 생성 실패: HTTP {response.status_code}")
                print(f"📊 응답: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ 서버 생성 오류: {e}")
            return False
    
    def check_task_status(self, task_id: str = None) -> Dict[str, Any]:
        """작업 상태 확인"""
        if task_id is None:
            task_id = self.task_id
            
        if not task_id:
            return {"error": "Task ID가 없습니다"}
            
        try:
            response = self.session.get(f"{self.base_url}/api/tasks/{task_id}/status")
            
            if response.status_code == 200:
                return response.json()
            else:
                return {"error": f"HTTP {response.status_code}", "response": response.text}
                
        except Exception as e:
            return {"error": str(e)}
    
    def monitor_task(self, max_wait: int = 300, poll_interval: int = 5) -> bool:
        """작업 완료까지 모니터링"""
        if not self.task_id:
            print("❌ Task ID가 없습니다")
            return False
            
        print(f"👀 작업 모니터링 시작 (최대 {max_wait}초 대기)")
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            status = self.check_task_status()
            
            if "error" in status:
                print(f"❌ 상태 확인 실패: {status['error']}")
                return False
                
            task_status = status.get('status', 'unknown')
            progress = status.get('progress', 0)
            message = status.get('message', '')
            
            print(f"📊 상태: {task_status} ({progress}%) - {message}")
            
            if task_status in ['completed', 'SUCCESS']:
                result = status.get('result', {})
                if result.get('success'):
                    print("🎉 서버 생성 성공!")
                    print(f"📋 결과: {result.get('message', '')}")
                    return True
                else:
                    print("❌ 서버 생성 실패!")
                    print(f"📋 오류: {result.get('error', '알 수 없는 오류')}")
                    return False
                    
            elif task_status in ['failed', 'FAILURE']:
                print("❌ 작업 실패!")
                print(f"📋 오류: {status.get('error', '알 수 없는 오류')}")
                return False
                
            time.sleep(poll_interval)
            
        print(f"⏰ 타임아웃 ({max_wait}초)")
        return False
    
    def run_full_test(self, server_name: str = "test-celery", cpu: int = 2, memory: int = 4, disk: int = 20) -> bool:
        """전체 테스트 실행"""
        print("🧪 비동기 서버 생성 테스트 시작")
        print("=" * 50)
        
        # 1. 로그인
        if not self.login():
            return False
            
        # 2. 서버 생성 요청
        server_config = {
            "name": server_name,
            "cpu": cpu,
            "memory": memory,
            "disk": disk,
            "os_type": "ubuntu",
            "role": "test",
            "firewall_group": "default"
        }
        
        if not self.create_server_async(server_config):
            return False
            
        # 3. 작업 모니터링
        if not self.monitor_task():
            return False
            
        print("=" * 50)
        print("🎉 전체 테스트 완료!")
        return True

def main():
    """메인 함수"""
    import argparse
    
    parser = argparse.ArgumentParser(description='비동기 서버 생성 테스트')
    parser.add_argument('--url', default='http://127.0.0.1:5000', help='서버 URL')
    parser.add_argument('--name', default='test-celery', help='서버 이름')
    parser.add_argument('--cpu', type=int, default=2, help='CPU 코어 수')
    parser.add_argument('--memory', type=int, default=4, help='메모리 (GB)')
    parser.add_argument('--disk', type=int, default=20, help='디스크 (GB)')
    parser.add_argument('--username', default='admin', help='로그인 사용자명')
    parser.add_argument('--password', default='admin123!', help='로그인 비밀번호')
    
    args = parser.parse_args()
    
    # 테스트 실행
    tester = AsyncServerTest(args.url)
    
    try:
        success = tester.run_full_test(
            server_name=args.name,
            cpu=args.cpu,
            memory=args.memory,
            disk=args.disk
        )
        
        if success:
            print("✅ 테스트 성공!")
            sys.exit(0)
        else:
            print("❌ 테스트 실패!")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n⏹️ 테스트 중단됨")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 테스트 오류: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
