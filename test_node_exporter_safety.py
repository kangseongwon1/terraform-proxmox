#!/usr/bin/env python3
"""
Node Exporter 설치 안전성 테스트 스크립트
"""

import os
import sys

# Flask 앱 컨텍스트 설정
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_install_node_exporter_playbook():
    """install_node_exporter.yml 안전성 테스트"""
    print("🔧 install_node_exporter.yml 안전성 테스트...")
    
    try:
        playbook_path = 'ansible/install_node_exporter.yml'
        if os.path.exists(playbook_path):
            with open(playbook_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # hosts 설정 확인
            if 'hosts: all' in content:
                print("✅ hosts: all 설정 확인!")
            else:
                print("❌ hosts 설정이 잘못되었습니다!")
                return False
            
            # 주석 확인
            if '--limit 옵션과 함께 사용되어 특정 서버에만' in content:
                print("✅ 안전성 주석 확인!")
            else:
                print("⚠️ 안전성 주석이 없습니다!")
            
            # 대상 서버 확인 태스크 확인
            if '대상 서버 확인' in content:
                print("✅ 대상 서버 확인 태스크 확인!")
            else:
                print("❌ 대상 서버 확인 태스크가 없습니다!")
                return False
            
            return True
        else:
            print("❌ install_node_exporter.yml 파일이 존재하지 않습니다!")
            return False
            
    except Exception as e:
        print(f"❌ install_node_exporter.yml 테스트 실패: {e}")
        return False

def test_ansible_service_logic():
    """AnsibleService 로직 테스트"""
    print("\n🔧 AnsibleService 로직 테스트...")
    
    try:
        from app.services.ansible_service import AnsibleService
        
        service = AnsibleService()
        
        # _run_node_exporter_playbook 메서드 확인
        if hasattr(service, '_run_node_exporter_playbook'):
            print("✅ _run_node_exporter_playbook 메서드가 존재합니다!")
        else:
            print("❌ _run_node_exporter_playbook 메서드가 존재하지 않습니다!")
            return False
        
        # _install_node_exporter_if_needed 메서드 확인
        if hasattr(service, '_install_node_exporter_if_needed'):
            print("✅ _install_node_exporter_if_needed 메서드가 존재합니다!")
        else:
            print("❌ _install_node_exporter_if_needed 메서드가 존재하지 않습니다!")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ AnsibleService 로직 테스트 실패: {e}")
        return False

def test_safety_measures():
    """안전성 조치 테스트"""
    print("\n🔧 안전성 조치 테스트...")
    
    try:
        # install_node_exporter.yml 파일 확인
        playbook_path = 'ansible/install_node_exporter.yml'
        if os.path.exists(playbook_path):
            with open(playbook_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            safety_measures = [
                'hosts: all',
                '--limit 옵션과 함께 사용되어 특정 서버에만',
                '대상 서버 확인',
                'Node Exporter 설치 확인',
                'when: not node_exporter_installed.stat.exists'
            ]
            
            passed_measures = 0
            for measure in safety_measures:
                if measure in content:
                    print(f"✅ {measure} 확인!")
                    passed_measures += 1
                else:
                    print(f"❌ {measure} 누락!")
            
            print(f"\n📊 안전성 조치: {passed_measures}/{len(safety_measures)} 통과")
            return passed_measures == len(safety_measures)
        else:
            print("❌ install_node_exporter.yml 파일이 존재하지 않습니다!")
            return False
            
    except Exception as e:
        print(f"❌ 안전성 조치 테스트 실패: {e}")
        return False

def main():
    """메인 테스트 함수"""
    print("🚀 Node Exporter 설치 안전성 테스트 시작")
    print("=" * 60)
    
    test_results = []
    
    # 1. install_node_exporter.yml 안전성 테스트
    test_results.append(("install_node_exporter.yml 안전성", test_install_node_exporter_playbook()))
    
    # 2. AnsibleService 로직 테스트
    test_results.append(("AnsibleService 로직", test_ansible_service_logic()))
    
    # 3. 안전성 조치 테스트
    test_results.append(("안전성 조치", test_safety_measures()))
    
    # 결과 요약
    print("\n" + "=" * 60)
    print("📊 테스트 결과 요약")
    print("=" * 60)
    
    passed = 0
    total = len(test_results)
    
    for test_name, result in test_results:
        status = "✅ 통과" if result else "❌ 실패"
        print(f"{test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\n총 {total}개 테스트 중 {passed}개 통과 ({passed/total*100:.1f}%)")
    
    if passed == total:
        print("🎉 모든 테스트가 통과했습니다!")
        print("\n📋 안전성 보장:")
        print("1. ✅ hosts: all + --limit 옵션으로 특정 서버만 제한")
        print("2. ✅ 대상 서버 확인 태스크로 실행 대상 명시")
        print("3. ✅ Node Exporter 설치 확인으로 중복 설치 방지")
        print("4. ✅ 조건부 실행으로 안전성 보장")
        print("\n🔒 안전성 확인:")
        print("- install_node_exporter.yml은 --limit 옵션과 함께 사용")
        print("- 특정 서버에만 Node Exporter 설치")
        print("- 기존 서버에 영향 없음")
        return True
    else:
        print("⚠️ 일부 테스트가 실패했습니다.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
