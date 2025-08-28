#!/usr/bin/env python3
"""
Ansible 명령어 테스트 스크립트
"""

import os
import subprocess
import json

def test_ansible_command():
    """Ansible 명령어 테스트"""
    
    # 환경 변수 설정
    os.environ['TARGET_SERVER_IP'] = '192.168.0.10'
    
    # Ansible 명령어 구성
    command = [
        'ansible-playbook',
        '-i', 'ansible/dynamic_inventory.py',
        'ansible/single_server_playbook.yml',
        '--extra-vars', json.dumps({
            'nginx_user': 'www-data',
            'nginx_port': 80,
            'target_server': '192.168.0.10',
            'role': 'web'
        }),
        '--ssh-common-args="-o StrictHostKeyChecking=no"'
    ]
    
    print("🔧 Ansible 명령어 테스트 시작")
    print(f"🔧 명령어: {' '.join(command)}")
    print(f"🔧 작업 디렉토리: {os.getcwd()}")
    print(f"🔧 환경 변수 TARGET_SERVER_IP: {os.environ.get('TARGET_SERVER_IP')}")
    
    try:
        # Ansible 실행
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=300
        )
        
        print(f"🔧 Return Code: {result.returncode}")
        print(f"🔧 stdout 길이: {len(result.stdout)}")
        print(f"🔧 stderr 길이: {len(result.stderr)}")
        
        if result.stdout:
            print(f"🔧 stdout (처음 1000자):")
            print(result.stdout[:1000])
            if len(result.stdout) > 1000:
                print("... (더 많은 출력이 있습니다)")
        
        if result.stderr:
            print(f"🔧 stderr (처음 1000자):")
            print(result.stderr[:1000])
            if len(result.stderr) > 1000:
                print("... (더 많은 출력이 있습니다)")
        
        if result.returncode == 0:
            print("✅ Ansible 명령어 실행 성공")
        else:
            print(f"❌ Ansible 명령어 실행 실패 (returncode: {result.returncode})")
            
    except subprocess.TimeoutExpired:
        print("❌ Ansible 명령어 실행 타임아웃")
    except FileNotFoundError:
        print("❌ Ansible 명령어를 찾을 수 없습니다")
    except Exception as e:
        print(f"❌ Ansible 명령어 실행 중 오류: {e}")

if __name__ == '__main__':
    test_ansible_command()
