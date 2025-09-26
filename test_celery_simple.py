#!/usr/bin/env python3
"""
간단한 Celery 테스트 (Docker 없이)
"""
import sys
import os

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_celery_import():
    """Celery 모듈 import 테스트"""
    try:
        from app.celery_app import celery_app
        print("✅ Celery 앱 import 성공")
        return True
    except Exception as e:
        print(f"❌ Celery 앱 import 실패: {e}")
        return False

def test_celery_config():
    """Celery 설정 테스트"""
    try:
        from app.celery_app import celery_app
        print(f"📊 Celery 설정:")
        print(f"  - 브로커: {celery_app.conf.broker_url}")
        print(f"  - 백엔드: {celery_app.conf.result_backend}")
        print(f"  - 결과 무시: {celery_app.conf.task_ignore_result}")
        return True
    except Exception as e:
        print(f"❌ Celery 설정 확인 실패: {e}")
        return False

def test_task_registration():
    """태스크 등록 테스트"""
    try:
        from app.celery_app import celery_app
        tasks = list(celery_app.tasks.keys())
        print(f"📋 등록된 태스크: {len(tasks)}개")
        for task in tasks:
            if not task.startswith('celery.'):
                print(f"  - {task}")
        return True
    except Exception as e:
        print(f"❌ 태스크 등록 확인 실패: {e}")
        return False

def main():
    """메인 테스트 함수"""
    print("🔍 간단한 Celery 테스트 시작")
    print("=" * 50)
    
    tests = [
        ("Celery 앱 Import", test_celery_import),
        ("Celery 설정 확인", test_celery_config),
        ("태스크 등록 확인", test_task_registration),
    ]
    
    passed = 0
    for name, test_func in tests:
        print(f"\n🧪 {name} 테스트...")
        if test_func():
            passed += 1
            print(f"✅ {name} 성공")
        else:
            print(f"❌ {name} 실패")
    
    print("\n" + "=" * 50)
    print(f"📊 테스트 결과: {passed}/{len(tests)} 통과")
    
    if passed == len(tests):
        print("🎉 모든 테스트 통과!")
        return 0
    else:
        print("❌ 일부 테스트 실패")
        return 1

if __name__ == "__main__":
    exit(main())
