#!/usr/bin/env python3
"""
Proxmox API 직접 호출 테스트 스크립트 (수정된 버전)
"""

import requests
import json
import urllib3

# SSL 경고 비활성화
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Proxmox 설정
PROXMOX_ENDPOINT = "https://prox.dmcmedia.co.kr:8006"
PROXMOX_USERNAME = "root@pam"
PROXMOX_PASSWORD = "YzaxdJOA2j9Itv8S"
GROUP_NAME = "test"

def test_proxmox_api():
    """Proxmox API 테스트"""
    
    # 1. 인증 토큰 발급
    print("🔐 1. 인증 토큰 발급 중...")
    auth_url = f"{PROXMOX_ENDPOINT}/api2/json/access/ticket"
    auth_data = {
        'username': PROXMOX_USERNAME,
        'password': PROXMOX_PASSWORD
    }
    
    try:
        auth_response = requests.post(auth_url, data=auth_data, verify=False, timeout=10)
        print(f"📡 인증 응답 상태: {auth_response.status_code}")
        
        if auth_response.status_code != 200:
            print(f"❌ 인증 실패: {auth_response.text}")
            return
        
        auth_result = auth_response.json()
        print(f"🔑 인증 성공!")
        
        ticket = auth_result['data']['ticket']
        csrf_token = auth_result['data']['CSRFPreventionToken']
        
        headers = {
            'Cookie': f'PVEAuthCookie={ticket}',
            'CSRFPreventionToken': csrf_token
        }
        
    except Exception as e:
        print(f"❌ 인증 실패: {e}")
        return
    
    # 2. Security Group 목록 조회
    print("\n🔍 2. Security Group 목록 조회 중...")
    groups_url = f"{PROXMOX_ENDPOINT}/api2/json/cluster/firewall/groups"
    
    try:
        groups_response = requests.get(groups_url, headers=headers, verify=False, timeout=10)
        print(f"📡 Groups 응답 상태: {groups_response.status_code}")
        
        if groups_response.status_code == 200:
            groups_result = groups_response.json()
            print(f"📋 Security Groups: {json.dumps(groups_result, indent=2)}")
        else:
            print(f"❌ Groups 조회 실패: {groups_response.text}")
            
    except Exception as e:
        print(f"❌ Groups 조회 실패: {e}")
    
    # 3. 특정 Security Group 상세 정보 조회 (Rules 포함)
    print(f"\n🔍 3. Security Group '{GROUP_NAME}' 상세 정보 조회 중...")
    group_url = f"{PROXMOX_ENDPOINT}/api2/json/cluster/firewall/groups/{GROUP_NAME}"
    
    try:
        group_response = requests.get(group_url, headers=headers, verify=False, timeout=10)
        print(f"📡 Group 상세 응답 상태: {group_response.status_code}")
        
        if group_response.status_code == 200:
            group_result = group_response.json()
            print(f"📋 Group 상세 정보 (Rules 포함): {json.dumps(group_result, indent=2)}")
            
            # Rules 개수 확인
            rules = group_result.get('data', [])
            print(f"📊 Rules 개수: {len(rules)}")
            
            # 각 Rule 상세 정보
            for i, rule in enumerate(rules):
                print(f"\n📋 Rule {i+1}:")
                print(f"  - Action: {rule.get('action')}")
                print(f"  - Protocol: {rule.get('proto')}")
                print(f"  - Port: {rule.get('dport')}")
                print(f"  - Source: {rule.get('source')}")
                print(f"  - Destination: {rule.get('dest')}")
                print(f"  - Type: {rule.get('type')}")
                print(f"  - Enabled: {rule.get('enable')}")
        else:
            print(f"❌ Group 상세 조회 실패: {group_response.text}")
            
    except Exception as e:
        print(f"❌ Group 상세 조회 실패: {e}")

if __name__ == "__main__":
    test_proxmox_api() 