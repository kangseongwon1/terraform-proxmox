#!/usr/bin/env python3
"""
Celery 연결 및 작업 테스트 스크립트
"""
import requests
import json
import time
import sys
import os

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def log(msg):
    print(msg, flush=True)

def test_celery_connection():
    """Celery 연결 및 작업 테스트"""
    base_url = "http://localhost:5000"
    
    print("🔍 Celery 연결 테스트 시작...")
    print("=" * 50)
    
    try:
        # 1. 로그인
        print("\n1. 로그인 테스트...")
        session = requests.Session()
        
        login_data = {
            'username': 'admin',
            'password': 'admin123!'
        }
        
        login_response = session.post(f"{base_url}/login", data=login_data, allow_redirects=False)
        print(f"📊 로그인 응답: {login_response.status_code}")
        
        if login_response.status_code not in [200, 302]:
            print("❌ 로그인 실패")
            return False
        
        print("✅ 로그인 성공")
        
        # 2. 간단한 서버 생성 테스트
        print("\n2. 비동기 서버 생성 테스트...")
        server_data = {
            'name': 'test-celery-connection',
            'cpu': 1,
            'memory': 2,
            'disk': 10,
            'os_type': 'ubuntu'
        }
        
        async_response = session.post(f"{base_url}/api/servers/async", json=server_data)
        print(f"📊 비동기 응답: {async_response.status_code}")
        
        if async_response.status_code == 200:
            result = async_response.json()
            print(f"✅ 비동기 작업 시작: {result}")
            
            if 'task_id' in result:
                task_id = result['task_id']
                print(f"📋 작업 ID: {task_id}")
                
                # 3. 작업 상태 폴링 (짧은 시간)
                print("\n3. 작업 상태 폴링 (30초 제한)...")
                for i in range(15):  # 최대 15번 폴링 (30초)
                    try:
                        status_response = session.get(f"{base_url}/api/tasks/{task_id}/status")
                        
                        if status_response.status_code == 200:
                            status_data = status_response.json()
                            status = status_data.get('status', 'unknown')
                            message = status_data.get('message', '')
                            progress = status_data.get('progress', 0)
                            
                            print(f"📊 상태 {i+1}: {status} ({progress}%) - {message}")
                            
                            if status in ['SUCCESS', 'FAILURE']:
                                print(f"✅ 작업 완료: {status}")
                                if status == 'SUCCESS':
                                    print("🎉 Celery 연결 테스트 성공!")
                                    return True
                                else:
                                    print(f"❌ 작업 실패: {status_data}")
                                    return False
                                break
                        else:
                            print(f"❌ 상태 조회 실패: {status_response.status_code}")
                            print(f"📊 응답: {status_response.text}")
                            
                    except Exception as e:
                        print(f"❌ 폴링 중 오류: {e}")
                    
                    time.sleep(2)  # 2초 대기
                
                print("⏰ 작업 타임아웃 (30초)")
                return False
            else:
                print("❌ task_id가 없습니다")
                return False
        else:
            print(f"❌ 비동기 작업 시작 실패: {async_response.text}")
            return False
            
    except Exception as e:
        print(f"❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_redis_celery_status():
    """Redis와 Celery 상태 확인"""
    print("\n4. Redis & Celery 상태 확인...")
    
    try:
        # Redis 연결 테스트
        from app.utils.redis_utils import redis_utils
        
        if redis_utils.is_available():
            print("✅ Redis 연결 성공")
        else:
            print("❌ Redis 연결 실패")
            return False
        
        # Celery 앱 테스트
        from app.celery_app import celery_app
        
        # Celery 인스펙션
        inspect = celery_app.control.inspect()
        stats = inspect.stats()
        
        if stats:
            print(f"✅ Celery 워커 연결 성공: {len(stats)}개 워커")
            for worker_name, worker_stats in stats.items():
                print(f"  - {worker_name}: {worker_stats.get('total', 0)}개 작업 처리")
        else:
            print("❌ Celery 워커 연결 실패")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ 상태 확인 실패: {e}")
        return False

def main():
    """메인 테스트 함수"""
    print("🚀 Celery 연결 테스트 시작")
    print("=" * 50)
    
    # Redis & Celery 상태 확인
    status_ok = test_redis_celery_status()
    
    # Celery 연결 테스트
    connection_ok = test_celery_connection()
    
    print("\n" + "=" * 50)
    print("📊 테스트 결과:")
    print(f"  Redis & Celery 상태: {'✅ 성공' if status_ok else '❌ 실패'}")
    print(f"  Celery 연결: {'✅ 성공' if connection_ok else '❌ 실패'}")
    
    if status_ok and connection_ok:
        print("\n🎉 모든 테스트 통과!")
        return 0
    else:
        print("\n❌ 일부 테스트 실패")
        return 1

if __name__ == "__main__":
    exit(main())
