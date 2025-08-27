#!/usr/bin/env python3
"""
Dynamic Inventory Script for Proxmox Manager
Ansible에서 --list 또는 --host <hostname> 인자로 호출됨
"""

import json
import sys
import os
import sqlite3
from typing import Dict, List, Any

class DynamicInventory:
    def __init__(self):
        self.db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'instance', 'proxmox_manager.db')
    
    def get_servers_from_db(self) -> List[Dict[str, Any]]:
        """DB에서 서버 정보 조회"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT name, ip_address, role, status, cpu, memory 
                FROM servers 
                WHERE ip_address IS NOT NULL AND ip_address != ''
            """)
            
            servers = []
            for row in cursor.fetchall():
                name, ip_address, role, status, cpu, memory = row
                servers.append({
                    'name': name,
                    'ip_address': ip_address,
                    'role': role,
                    'status': status,
                    'cpu': cpu,
                    'memory': memory
                })
            
            conn.close()
            return servers
            
        except Exception as e:
            print(f"DB 조회 오류: {e}", file=sys.stderr)
            return []
    
    def generate_inventory(self, target_server_ip: str = None) -> Dict[str, Any]:
        """전체 inventory 생성 (--list)"""
        servers = self.get_servers_from_db()
        
        # 특정 서버만 필터링
        if target_server_ip:
            servers = [s for s in servers if s['ip_address'] == target_server_ip]
            print(f"🔧 특정 서버만 대상으로 함: {target_server_ip}", file=sys.stderr)
        
        # 기본 그룹 설정
        inventory = {
            'all': {
                'children': ['ungrouped']
            },
            'ungrouped': {
                'hosts': []
            },
            '_meta': {
                'hostvars': {}
            }
        }
        
        # 역할별 그룹 매핑
        role_groups = {
            'web': 'webservers',
            'db': 'dbservers',
            'was': 'was_servers',
            'java': 'java_servers',
            'search': 'search_servers',
            'ftp': 'ftp_servers',
            'monitoring': 'monitoring_servers'
        }
        
        # 서버별로 그룹에 추가
        for server in servers:
            hostname = server['ip_address']
            role = server.get('role', 'none')
            
            # ungrouped에 추가
            inventory['ungrouped']['hosts'].append(hostname)
            
            # 역할별 그룹에 추가
            if role in role_groups:
                group_name = role_groups[role]
                
                if group_name not in inventory:
                    inventory[group_name] = {'hosts': []}
                    inventory['all']['children'].append(group_name)
                
                inventory[group_name]['hosts'].append(hostname)
            
            # 호스트 변수 설정
            inventory['_meta']['hostvars'][hostname] = {
                'ansible_host': hostname,
                'server_name': server['name'],
                'server_role': role,
                'server_status': server['status'],
                'ansible_user': 'rocky',
                'ansible_ssh_private_key_file': '~/.ssh/id_rsa',
                'ansible_host_key_checking': False,
                'ansible_python_interpreter': '/usr/bin/python3'
            }
        
        return inventory
    
    def get_host_vars(self, hostname: str) -> Dict[str, Any]:
        """특정 호스트의 변수 조회 (--host)"""
        servers = self.get_servers_from_db()
        
        for server in servers:
            if server['ip_address'] == hostname:
                return {
                    'ansible_host': hostname,
                    'server_name': server['name'],
                    'server_role': server.get('role', 'none'),
                    'server_status': server['status'],
                    'ansible_user': 'rocky',
                    'ansible_ssh_private_key_file': '~/.ssh/id_rsa',
                    'ansible_host_key_checking': False,
                    'ansible_python_interpreter': '/usr/bin/python3'
                }
        
        return {}

def main():
    inventory = DynamicInventory()
    
    if len(sys.argv) == 2 and sys.argv[1] == '--list':
        # 전체 inventory 반환
        result = inventory.generate_inventory()
        print(json.dumps(result, indent=2))
    
    elif len(sys.argv) == 3 and sys.argv[1] == '--list':
        # 특정 서버만 대상으로 하는 inventory 반환
        target_server_ip = sys.argv[2]
        result = inventory.generate_inventory(target_server_ip)
        print(json.dumps(result, indent=2))
    
    elif len(sys.argv) == 3 and sys.argv[1] == '--host':
        # 특정 호스트 변수 반환
        hostname = sys.argv[2]
        result = inventory.get_host_vars(hostname)
        print(json.dumps(result, indent=2))
    
    else:
        print("Usage: python dynamic_inventory.py --list")
        print("       python dynamic_inventory.py --list <target_server_ip>")
        print("       python dynamic_inventory.py --host <hostname>")
        sys.exit(1)

if __name__ == '__main__':
    main()
