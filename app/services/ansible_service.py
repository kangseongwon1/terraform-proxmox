"""
Ansible 서비스
"""
import subprocess
import yaml
import os
import logging
from typing import Dict, List, Any, Optional, Tuple
from flask import current_app
from app.models.server import Server
from app.models.notification import Notification

logger = logging.getLogger(__name__)

class AnsibleService:
    """Ansible 서비스"""
    
    def __init__(self, ansible_dir: str = "ansible"):
        self.ansible_dir = ansible_dir
        self.inventory_file = os.path.join(ansible_dir, "inventory")
        self.playbook_file = os.path.join(ansible_dir, "role_playbook.yml")
    
    def _run_ansible_command(self, command: List[str], cwd: str = None) -> Tuple[int, str, str]:
        """Ansible 명령어 실행"""
        if cwd is None:
            cwd = self.ansible_dir
        
        try:
            result = subprocess.run(
                command,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=600  # 10분 타임아웃
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            logger.error("Ansible 명령어 실행 타임아웃")
            return -1, "", "Ansible 명령어 실행 타임아웃"
        except Exception as e:
            logger.error(f"Ansible 명령어 실행 실패: {e}")
            return -1, "", str(e)
    
    def create_inventory(self, servers: List[Dict[str, Any]]) -> bool:
        """Ansible 인벤토리 파일 생성"""
        try:
            inventory_content = []
            
            for server in servers:
                if server.get('ip_address'):
                    inventory_content.append(f"{server['ip_address']}")
            
            # 인벤토리 파일 저장
            with open(self.inventory_file, 'w', encoding='utf-8') as f:
                f.write('\n'.join(inventory_content))
            
            logger.info("Ansible 인벤토리 파일 생성 성공")
            return True
            
        except Exception as e:
            logger.error(f"Ansible 인벤토리 파일 생성 실패: {e}")
            return False
    
    def run_playbook(self, role: str, extra_vars: Dict[str, Any] = None) -> Tuple[bool, str]:
        """Ansible 플레이북 실행"""
        try:
            # 플레이북 파일 생성
            playbook_content = {
                'hosts': 'all',
                'become': True,
                'roles': [role]
            }
            
            if extra_vars:
                playbook_content['vars'] = extra_vars
            
            with open(self.playbook_file, 'w', encoding='utf-8') as f:
                yaml.dump([playbook_content], f, default_flow_style=False, allow_unicode=True)
            
            # Ansible 플레이북 실행
            command = [
                'ansible-playbook',
                '-i', self.inventory_file,
                self.playbook_file,
                '--ssh-common-args="-o StrictHostKeyChecking=no"'
            ]
            
            returncode, stdout, stderr = self._run_ansible_command(command)
            
            if returncode == 0:
                logger.info(f"Ansible 플레이북 실행 성공 (role: {role})")
                return True, stdout
            else:
                logger.error(f"Ansible 플레이북 실행 실패 (role: {role}): {stderr}")
                return False, stderr
                
        except Exception as e:
            logger.error(f"Ansible 플레이북 실행 실패: {e}")
            return False, str(e)
    
    def run_role_for_server(self, server_name: str, role: str, extra_vars: Dict[str, Any] = None) -> Tuple[bool, str]:
        """특정 서버에 대해 역할 실행"""
        try:
            # 서버 정보 조회
            server = Server.get_by_name(server_name)
            if not server or not server.ip_address:
                return False, f"서버 {server_name}의 IP 주소를 찾을 수 없습니다"
            
            # 인벤토리 생성
            servers_data = [{'ip_address': server.ip_address}]
            if not self.create_inventory(servers_data):
                return False, "인벤토리 파일 생성 실패"
            
            # 플레이북 실행
            return self.run_playbook(role, extra_vars)
            
        except Exception as e:
            logger.error(f"서버 {server_name}에 대한 역할 {role} 실행 실패: {e}")
            return False, str(e)
    
    def run_role_for_multiple_servers(self, servers: List[Dict[str, Any]], role: str, 
                                    extra_vars: Dict[str, Any] = None) -> Tuple[bool, str]:
        """여러 서버에 대해 역할 실행"""
        try:
            # IP 주소가 있는 서버만 필터링
            valid_servers = [s for s in servers if s.get('ip_address')]
            
            if not valid_servers:
                return False, "유효한 IP 주소를 가진 서버가 없습니다"
            
            # 인벤토리 생성
            if not self.create_inventory(valid_servers):
                return False, "인벤토리 파일 생성 실패"
            
            # 플레이북 실행
            return self.run_playbook(role, extra_vars)
            
        except Exception as e:
            logger.error(f"여러 서버에 대한 역할 {role} 실행 실패: {e}")
            return False, str(e)
    
    def ping_servers(self, servers: List[Dict[str, Any]]) -> Dict[str, bool]:
        """서버 연결 테스트"""
        try:
            # 인벤토리 생성
            if not self.create_inventory(servers):
                return {}
            
            # ping 명령어 실행
            command = [
                'ansible', 'all', '-i', self.inventory_file,
                '-m', 'ping',
                '--ssh-common-args="-o StrictHostKeyChecking=no"'
            ]
            
            returncode, stdout, stderr = self._run_ansible_command(command)
            
            # 결과 파싱
            results = {}
            for server in servers:
                ip = server.get('ip_address')
                if ip:
                    # stdout에서 해당 IP의 ping 결과 확인
                    if ip in stdout and 'SUCCESS' in stdout:
                        results[ip] = True
                    else:
                        results[ip] = False
            
            return results
            
        except Exception as e:
            logger.error(f"서버 ping 테스트 실패: {e}")
            return {}
    
    def get_available_roles(self) -> List[str]:
        """사용 가능한 역할 목록 조회"""
        try:
            roles_dir = os.path.join(self.ansible_dir, "roles")
            if os.path.exists(roles_dir):
                return [d for d in os.listdir(roles_dir) 
                       if os.path.isdir(os.path.join(roles_dir, d))]
            return []
        except Exception as e:
            logger.error(f"사용 가능한 역할 목록 조회 실패: {e}")
            return []
    
    def validate_role(self, role: str) -> bool:
        """역할 유효성 검사"""
        try:
            role_dir = os.path.join(self.ansible_dir, "roles", role)
            tasks_file = os.path.join(role_dir, "tasks", "main.yml")
            return os.path.exists(tasks_file)
        except Exception as e:
            logger.error(f"역할 {role} 유효성 검사 실패: {e}")
            return False 