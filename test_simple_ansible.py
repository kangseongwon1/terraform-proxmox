#!/usr/bin/env python3
"""
간단한 Ansible 연결 테스트
"""

import os
import subprocess
import json

def test_ansible_connection():
    """Ansible 연결 테스트"""
    
    # 환경 변수 설정
    os.environ['TARGET_SERVER_IP'] = '192.168.0.10'
    
    print("🔧 Ansible 연결 테스트 시작")
    
    # 1. Dynamic Inventory 테스트
    print("\n1. Dynamic Inventory 테스트:")
    try:
        result = subprocess.run([
            'python3', 'ansible/dynamic_inventory.py', '--list'
        ], capture_output=True, text=True, timeout=30)
        
        print(f"Return Code: {result.returncode}")
        if result.returncode == 0:
            print("✅ Dynamic Inventory 정상")
            inventory = json.loads(result.stdout)
            print(f"호스트 목록: {list(inventory.get('_meta', {}).get('hostvars', {}).keys())}")
        else:
            print(f"❌ Dynamic Inventory 실패: {result.stderr}")
    except Exception as e:
        print(f"❌ Dynamic Inventory 오류: {e}")
    
    # 2. Ansible ping 테스트
    print("\n2. Ansible ping 테스트:")
    try:
        result = subprocess.run([
            'ansible', '192.168.0.10', '-i', 'ansible/dynamic_inventory.py', '-m', 'ping'
        ], capture_output=True, text=True, timeout=60)
        
        print(f"Return Code: {result.returncode}")
        print(f"stdout: {result.stdout}")
        print(f"stderr: {result.stderr}")
    except Exception as e:
        print(f"❌ Ansible ping 오류: {e}")
    
    # 3. 간단한 플레이북 테스트
    print("\n3. 간단한 플레이북 테스트:")
    try:
        result = subprocess.run([
            'ansible-playbook',
            '-i', 'ansible/dynamic_inventory.py',
            'ansible/minimal_test_playbook.yml',
            '--extra-vars', json.dumps({'target_server': '192.168.0.10', 'role': 'web'}),
            '--ssh-common-args=-o StrictHostKeyChecking=no'
        ], capture_output=True, text=True, timeout=300)
        
        print(f"Return Code: {result.returncode}")
        print(f"stdout 길이: {len(result.stdout)}")
        print(f"stderr 길이: {len(result.stderr)}")
        
        if result.stdout:
            print(f"stdout (처음 500자): {result.stdout[:500]}")
        if result.stderr:
            print(f"stderr (처음 500자): {result.stderr[:500]}")
            
    except Exception as e:
        print(f"❌ 플레이북 테스트 오류: {e}")

if __name__ == '__main__':
    test_ansible_connection()
