"""
Ansible 서비스
"""
import subprocess
import yaml
import os
import logging
import tempfile
import json
import threading
import time
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from flask import current_app
from app.models.server import Server
from app.models.notification import Notification
from app import db

# ansible-runner import
try:
    import ansible_runner
    ANSIBLE_RUNNER_AVAILABLE = True
except ImportError:
    ANSIBLE_RUNNER_AVAILABLE = False
    print("⚠️ ansible-runner가 설치되지 않았습니다. subprocess를 사용합니다.")

logger = logging.getLogger(__name__)

class AnsibleService:
    """Ansible 서비스"""
    
    def __init__(self, ansible_dir: str = "ansible"):
        # 프로젝트 루트 디렉토리 찾기 (리팩토링에 강건한 방식)
        current_file = os.path.abspath(__file__)
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_file)))
        
        # Ansible 디렉토리 설정
        self.ansible_dir = os.path.join(project_root, ansible_dir)
        self.dynamic_inventory_script = os.path.join(self.ansible_dir, "dynamic_inventory.py")
        self.playbook_file = os.path.join(self.ansible_dir, "role_playbook.yml")
        self.single_server_playbook = os.path.join(self.ansible_dir, "single_server_playbook.yml")
        
        print(f"🔧 프로젝트 루트: {project_root}")
        print(f"🔧 Ansible 디렉토리: {self.ansible_dir}")
        print(f"🔧 Dynamic Inventory 스크립트: {self.dynamic_inventory_script}")
        print(f"🔧 Playbook 파일: {self.playbook_file}")
        print(f"🔧 Single Server Playbook 파일: {self.single_server_playbook}")
        
        # 파일 존재 확인
        if not os.path.exists(self.playbook_file):
            print(f"⚠️ 플레이북 파일이 존재하지 않습니다: {self.playbook_file}")
        else:
            print(f"✅ 플레이북 파일 확인됨: {self.playbook_file}")
        
        if not os.path.exists(self.single_server_playbook):
            print(f"⚠️ Single Server 플레이북 파일이 존재하지 않습니다: {self.single_server_playbook}")
        else:
            print(f"✅ Single Server 플레이북 파일 확인됨: {self.single_server_playbook}")
        
        if not os.path.exists(self.dynamic_inventory_script):
            print(f"⚠️ Dynamic Inventory 스크립트가 존재하지 않습니다: {self.dynamic_inventory_script}")
        else:
            print(f"✅ Dynamic Inventory 스크립트 확인됨: {self.dynamic_inventory_script}")
    

    
    def _run_ansible_command(self, command: List[str], cwd: str = None, env: Dict[str, str] = None) -> Tuple[int, str, str]:
        """Ansible 명령어 실행"""
        if cwd is None:
            cwd = self.ansible_dir
        
        print(f"🔧 작업 디렉토리: {cwd}")
        print(f"🔧 현재 작업 디렉토리: {os.getcwd()}")
        
        try:
            # 환경 변수 설정
            if env is None:
                env = os.environ.copy()
            else:
                base_env = os.environ.copy()
                base_env.update(env)
                env = base_env
            
            # SSH 설정 환경 변수 추가
            ssh_user = current_app.config.get('SSH_USER', 'rocky')
            ssh_private_key = current_app.config.get('SSH_PRIVATE_KEY_PATH', '~/.ssh/id_rsa')
            
            env['ANSIBLE_USER'] = ssh_user
            env['ANSIBLE_SSH_PRIVATE_KEY_FILE'] = ssh_private_key
            env['ANSIBLE_HOST_KEY_CHECKING'] = 'False'  # 호스트 키 검증 비활성화
            
            print(f"🔧 Ansible 명령어 실행: {' '.join(command)}")
            print(f"🔧 SSH 사용자: {ssh_user}")
            print(f"🔧 SSH 키: {ssh_private_key}")
            
            # Windows 환경에서 Ansible 명령어 경로 확인 및 수정
            if os.name == 'nt':  # Windows 환경
                # Windows에서 Ansible 실행 방법들 시도
                possible_commands = [
                    command,  # 원래 명령어
                    ['python', '-m', 'ansible'] + command[1:],  # Python 모듈로 실행
                    ['ansible.cmd'] + command[1:],  # .cmd 확장자
                    ['ansible.exe'] + command[1:],  # .exe 확장자
                ]
                
                for cmd in possible_commands:
                    try:
                        print(f"🔧 Windows에서 Ansible 명령어 시도: {' '.join(cmd)}")
                        result = subprocess.run(
                            cmd,
                            cwd=cwd,
                            env=env,
                            capture_output=True,
                            text=True,
                            encoding='utf-8',
                            errors='replace',
                            timeout=600
                        )
                        
                        print(f"🔧 Ansible 명령어 완료: returncode={result.returncode}")
                        if result.stderr:
                            print(f"🔧 Ansible stderr: {result.stderr}")
                        
                        return result.returncode, result.stdout, result.stderr
                        
                    except FileNotFoundError:
                        print(f"🔧 명령어 실패, 다음 시도: {' '.join(cmd)}")
                        continue
                    except Exception as e:
                        print(f"🔧 명령어 실행 중 오류: {e}")
                        continue
                
                # 모든 시도 실패
                error_msg = "Windows 환경에서 Ansible 명령어를 찾을 수 없습니다. Ansible이 설치되어 있고 PATH에 추가되었는지 확인하세요."
                logger.error(error_msg)
                return -1, "", error_msg
            else:
                # Linux/Mac 환경
                result = subprocess.run(
                    command,
                    cwd=cwd,
                    env=env,
                    capture_output=True,
                    text=True,
                    encoding='utf-8',
                    errors='replace',
                    timeout=600
                )
                
                print(f"🔧 Ansible 명령어 완료: returncode={result.returncode}")
                if result.stderr:
                    print(f"🔧 Ansible stderr: {result.stderr}")
                
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
            
            # SSH 설정 가져오기
            ssh_user = current_app.config.get('SSH_USER', 'rocky')
            ssh_private_key = current_app.config.get('SSH_PRIVATE_KEY_PATH', '~/.ssh/id_rsa')
            
            for server in servers:
                if server.get('ip_address'):
                    # SSH 사용자명과 키 설정을 포함한 인벤토리 항목
                    inventory_item = f"{server['ip_address']} ansible_user={ssh_user} ansible_ssh_private_key_file={ssh_private_key}"
                    inventory_content.append(inventory_item)
            
            # 인벤토리 파일 저장
            with open(self.inventory_file, 'w', encoding='utf-8') as f:
                f.write('\n'.join(inventory_content))
            
            logger.info(f"Ansible 인벤토리 파일 생성 성공: {len(inventory_content)}개 서버")
            return True
            
        except Exception as e:
            logger.error(f"Ansible 인벤토리 파일 생성 실패: {e}")
            return False
    
    def run_playbook(self, role: str, extra_vars: Dict[str, Any] = None, target_server: str = None) -> Tuple[bool, str]:
        """Ansible 플레이북 실행 (ansible-runner 사용)"""
        try:
            print(f"🔧 Ansible 플레이북 실행 시작: {role}")
            if target_server:
                print(f"🔧 대상 서버: {target_server}")
            
            if ANSIBLE_RUNNER_AVAILABLE:
                return self._run_playbook_with_runner(role, extra_vars, target_server)
            else:
                return self._run_playbook_with_subprocess(role, extra_vars, target_server)
                
        except Exception as e:
            logger.error(f"Ansible 플레이북 실행 실패: {e}")
            return False, str(e)
    
    def _run_playbook_with_runner(self, role: str, extra_vars: Dict[str, Any] = None) -> Tuple[bool, str]:
        """ansible-runner를 사용한 플레이북 실행"""
        try:
            print(f"🔧 ansible-runner를 사용한 플레이북 실행: {role}")
            
            # 임시 디렉토리 생성
            with tempfile.TemporaryDirectory() as temp_dir:
                # 플레이북 파일 생성
                playbook_path = os.path.join(temp_dir, 'playbook.yml')
                playbook_content = [{
                    'hosts': 'all',
                    'become': True,
                    'roles': [role]
                }]
                
                if extra_vars:
                    playbook_content[0]['vars'] = extra_vars
                
                with open(playbook_path, 'w', encoding='utf-8') as f:
                    yaml.dump(playbook_content, f, default_flow_style=False, allow_unicode=True)
                
                # inventory 파일 복사
                inventory_path = os.path.join(temp_dir, 'inventory')
                with open(self.inventory_file, 'r', encoding='utf-8') as src:
                    with open(inventory_path, 'w', encoding='utf-8') as dst:
                        dst.write(src.read())
                
                # ansible-runner 실행
                print(f"🔧 ansible-runner 실행: {playbook_path}")
                result = ansible_runner.run(
                    private_data_dir=temp_dir,
                    playbook='playbook.yml',
                    inventory=inventory_path,
                    quiet=False,
                    json_mode=False
                )
                
                print(f"🔧 ansible-runner 결과: returncode={result.rc}")
                print(f"🔧 ansible-runner 상태: {result.status}")
                
                if result.rc == 0:
                    success_msg = f"Ansible 플레이북 실행 성공 (role: {role})"
                    print(f"✅ {success_msg}")
                    return True, success_msg
                else:
                    error_msg = f"Ansible 플레이북 실행 실패 (role: {role}, returncode: {result.rc})"
                    print(f"❌ {error_msg}")
                    return False, error_msg
                    
        except Exception as e:
            error_msg = f"ansible-runner 실행 중 오류: {str(e)}"
            print(f"❌ {error_msg}")
            return False, error_msg
    
    def _run_playbook_with_subprocess(self, role: str, extra_vars: Dict[str, Any] = None, target_server: str = None) -> Tuple[bool, str]:
        """subprocess를 사용한 플레이북 실행 (기존 방식)"""
        try:
            print(f"🔧 subprocess를 사용한 플레이북 실행: {role}")
            
            # 대상 서버가 지정된 경우 개별 서버 플레이북 사용
            if target_server:
                print(f"🔧 개별 서버 플레이북 사용: {target_server}")
                
                # 개별 서버 플레이북에 extra_vars 추가
                extra_vars = extra_vars or {}
                extra_vars.update({
                    'target_server': target_server,
                    'role': role
                })
                
                # Ansible 플레이북 실행 (개별 서버 플레이북 사용)
                command = [
                    'ansible-playbook',
                    '-i', f'python {self.dynamic_inventory_script} {target_server}',
                    self.single_server_playbook,
                    '--extra-vars', json.dumps(extra_vars),
                    '--ssh-common-args="-o StrictHostKeyChecking=no"'
                ]
            else:
                # 기존 방식 (전체 서버 대상)
                print(f"🔧 전체 서버 플레이북 사용")
                
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
                
                # Ansible 플레이북 실행 (Dynamic Inventory 사용)
                command = [
                    'ansible-playbook',
                    '-i', f'python {self.dynamic_inventory_script} --list',
                    self.playbook_file,
                    '--ssh-common-args="-o StrictHostKeyChecking=no"'
                ]
            
            print(f"🔧 Ansible 명령어: {' '.join(command)}")
            print(f"🔧 플레이북 파일 존재 확인: {os.path.exists(self.playbook_file)}")
            print(f"🔧 Dynamic Inventory 스크립트 존재 확인: {os.path.exists(self.dynamic_inventory_script)}")
            
            returncode, stdout, stderr = self._run_ansible_command(command)
            
            if returncode == 0:
                logger.info(f"Ansible 플레이북 실행 성공 (role: {role})")
                return True, stdout or f"Ansible 플레이북 실행 성공 (role: {role})"
            else:
                error_msg = stderr or stdout or f"알 수 없는 Ansible 플레이북 실행 오류 (role: {role})"
                logger.error(f"Ansible 플레이북 실행 실패 (role: {role}): {error_msg}")
                return False, error_msg
                
        except Exception as e:
            logger.error(f"subprocess Ansible 플레이북 실행 실패: {e}")
            return False, str(e)
    
    def assign_role_to_server(self, server_name: str, role: str, extra_vars: Dict[str, Any] = None) -> Tuple[bool, str]:
        """서버에 역할 할당 (DB 기반)"""
        try:
            print(f"🔧 서버 역할 할당 시작: {server_name} - {role}")
            print(f"🔧 호출 스택: {__name__}.assign_role_to_server")
            print(f"🔧 매개변수: server_name={server_name}, role={role}, extra_vars={extra_vars}")
            
            # 1. DB에서 서버 정보 조회
            server = Server.get_by_name(server_name)
            if not server:
                return False, f"서버 {server_name}을 DB에서 찾을 수 없습니다"
            
            # 2. 현재 역할 확인 (로그용)
            current_role = server.role
            print(f"🔧 현재 역할: {current_role}")
            print(f"🔧 요청된 역할: {role}")
            
            # 3. 역할 변경 감지 및 제거 처리
            # 빈 문자열이나 None인 경우 역할 제거로 처리 (먼저 체크)
            if role is None or role.strip() == "" or role.lower() in ["none", "역할 없음", "no role"]:
                # 역할 제거 요청
                print(f"🔧 역할 제거 요청: {current_role} → 없음")
                
                # 1. DB에서 역할 제거
                server.role = None
                db.session.commit()
                print(f"✅ DB에서 역할 제거 완료: {server_name}")
                
                # 2. tfvars에서 역할 제거
                try:
                    from app.services.terraform_service import TerraformService
                    terraform_service = TerraformService()
                    
                    # tfvars 로드
                    tfvars = terraform_service.load_tfvars()
                    if 'servers' in tfvars and server_name in tfvars['servers']:
                        # 역할 제거 (빈 문자열로 설정)
                        tfvars['servers'][server_name]['role'] = ""
                        terraform_service.save_tfvars(tfvars)
                        print(f"✅ tfvars에서 역할 제거 완료: {server_name}")
                    else:
                        print(f"⚠️ tfvars에서 서버를 찾을 수 없음: {server_name}")
                except Exception as e:
                    print(f"⚠️ tfvars 업데이트 실패: {e}")
                
                print(f"✅ 역할 제거 시 Ansible 실행 생략 (불필요)")
                return True, f"서버 {server_name}에서 역할이 제거되었습니다"
            
            elif current_role == role:
                print(f"🔧 역할 변경 없음: {current_role} → {role}")
                # 역할이 같아도 Ansible 실행 (강제 적용)
                print(f"🔧 강제 Ansible 실행 진행")
            
            # 4. 서버 IP 주소 확인
            if not server.ip_address:
                return False, f"서버 {server_name}의 IP 주소가 설정되지 않았습니다"
            
            # 5. 서버 데이터 준비 (로그용)
            server_data = {
                'name': server.name,
                'role': role,
                'ip_address': server.ip_address
            }
            print(f"🔧 서버 데이터: {server_data}")
            print(f"🔧 Dynamic Inventory 스크립트 사용: {self.dynamic_inventory_script}")
            
            # 7. 역할별 추가 변수 설정
            role_vars = extra_vars or {}
            
            # 역할별 기본 설정
            if role == 'web':
                role_vars.update({
                    'nginx_user': 'www-data',
                    'nginx_port': 80
                })
            elif role == 'db':
                role_vars.update({
                    'mysql_root_password': 'dmc1234!',
                    'mysql_port': 3306
                })
            elif role == 'was':
                role_vars.update({
                    'java_version': '11',
                    'tomcat_port': 8080
                })
            elif role == 'java':
                role_vars.update({
                    'java_version': '11',
                    'spring_profile': 'production'
                })
            elif role == 'search':
                role_vars.update({
                    'elasticsearch_port': 9200,
                    'kibana_port': 5601
                })
            elif role == 'ftp':
                role_vars.update({
                    'ftp_port': 21,
                    'ftp_user': 'ftpuser'
                })
            
            print(f"🔧 역할 변수 설정: {role_vars}")
            
            # 8. 비동기 Ansible 실행
            print(f"🔧 비동기 Ansible 실행 시작: {server_name} - {role}")
            
            # 비동기로 Ansible 실행
            message = self._run_ansible_async(server_name, role, role_vars)
            
            # 즉시 성공 응답 (실제 처리는 백그라운드에서)
            return True, message
            
        except Exception as e:
            logger.error(f"서버 {server_name}에 대한 역할 {role} 할당 실패: {e}")
            return False, str(e)
    
    def run_role_for_server(self, server_name: str, role: str, extra_vars: Dict[str, Any] = None) -> Tuple[bool, str]:
        """특정 서버에 대해 역할 실행 (기존 호환성 유지)"""
        try:
            print(f"🔧 Ansible 역할 실행 시작: {server_name} - {role}")
            
            # 서버 정보 조회 (DB 또는 Proxmox에서)
            server_data = None
            
            # 1. DB에서 서버 정보 조회
            server = Server.get_by_name(server_name)
            if server:
                server_data = {
                    'name': server.name,
                    'role': server.role or role,
                    'networks': [{'ip': server.ip_address}] if server.ip_address else []
                }
                print(f"🔧 DB에서 서버 정보 조회: {server_data}")
            else:
                # 2. Proxmox에서 서버 정보 조회
                from app.services.proxmox_service import ProxmoxService
                proxmox_service = ProxmoxService()
                result = proxmox_service.get_all_vms()
                
                if result['success']:
                    servers = result['data']['servers']
                    for vm_key, s_data in servers.items():
                        if s_data.get('name') == server_name:
                            ip_addresses = s_data.get('ip_addresses', [])
                            if ip_addresses:
                                server_data = {
                                    'name': server_name,
                                    'role': role,
                                    'networks': [{'ip': ip_addresses[0]}]
                                }
                                print(f"🔧 Proxmox에서 서버 정보 조회: {server_data}")
                                break
            
            if not server_data:
                return False, f"서버 {server_name}의 정보를 찾을 수 없습니다"
            
            # 동적 inventory 생성
            if not self._generate_dynamic_inventory([server_data]):
                return False, "동적 inventory 파일 생성 실패"
            
            # 역할별 추가 변수 설정
            role_vars = extra_vars or {}
            
            # 역할별 기본 설정
            if role == 'web':
                role_vars.update({
                    'nginx_user': 'www-data',
                    'nginx_port': 80
                })
            elif role == 'db':
                role_vars.update({
                    'mysql_root_password': 'dmc1234!',
                    'mysql_port': 3306
                })
            elif role == 'was':
                role_vars.update({
                    'java_version': '11',
                    'tomcat_port': 8080
                })
            elif role == 'java':
                role_vars.update({
                    'java_version': '11',
                    'spring_profile': 'production'
                })
            elif role == 'search':
                role_vars.update({
                    'elasticsearch_port': 9200,
                    'kibana_port': 5601
                })
            elif role == 'ftp':
                role_vars.update({
                    'ftp_port': 21,
                    'ftp_user': 'ftpuser'
                })
            
            print(f"🔧 역할 변수 설정: {role_vars}")
            
            # 플레이북 실행
            return self.run_playbook(role, role_vars)
            
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
    
    def check_ansible_installation(self) -> Tuple[bool, str]:
        """Ansible 설치 상태 확인"""
        try:
            # ansible-runner가 있으면 사용 가능
            if ANSIBLE_RUNNER_AVAILABLE:
                return True, "ansible-runner를 사용하여 Ansible 실행 가능"
            
            if os.name == 'nt':  # Windows 환경
                # Windows에서 Ansible 설치 확인
                possible_commands = [
                    ['ansible', '--version'],
                    ['ansible.cmd', '--version'],
                    ['ansible.exe', '--version'],
                    ['python', '-m', 'ansible', '--version']
                ]
                
                for cmd in possible_commands:
                    try:
                        result = subprocess.run(
                            cmd,
                            capture_output=True,
                            text=True,
                            timeout=10
                        )
                        if result.returncode == 0:
                            return True, f"Ansible 설치됨: {' '.join(cmd)}"
                    except (FileNotFoundError, subprocess.TimeoutExpired):
                        continue
                
                return False, "Windows에서 Ansible이 설치되지 않았습니다. 'pip install ansible' 또는 WSL을 사용하세요."
            else:
                # Linux/Mac 환경
                result = subprocess.run(
                    ['ansible', '--version'],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode == 0:
                    return True, "Ansible 설치됨"
                else:
                    return False, "Linux/Mac에서 Ansible이 설치되지 않았습니다. 'sudo apt install ansible' 또는 'brew install ansible'을 사용하세요."
                    
        except Exception as e:
            return False, f"Ansible 설치 확인 중 오류: {str(e)}"

    def _update_tfvars_role(self, server_name: str, role: str) -> bool:
        """terraform.tfvars.json에서 서버 역할 업데이트"""
        try:
            from app.services.terraform_service import TerraformService
            terraform_service = TerraformService()
            
            # tfvars 로드
            tfvars = terraform_service.load_tfvars()
            if 'servers' in tfvars and server_name in tfvars['servers']:
                # 역할 업데이트
                tfvars['servers'][server_name]['role'] = role
                terraform_service.save_tfvars(tfvars)
                print(f"✅ tfvars에서 역할 업데이트 완료: {server_name} - {role}")
                return True
            else:
                print(f"⚠️ tfvars에서 서버를 찾을 수 없음: {server_name}")
                return False
        except Exception as e:
            print(f"⚠️ tfvars 업데이트 실패: {e}")
            return False

    def _run_ansible_async(self, server_name: str, role: str, extra_vars: Dict[str, Any] = None) -> str:
        """Ansible을 비동기로 실행하고 알림 생성"""
        def run_ansible():
            try:
                # Flask 앱 컨텍스트 생성
                from app import create_app
                app = create_app()
                with app.app_context():
                    print(f"🔧 비동기 Ansible 실행 시작: {server_name} - {role}")
                    
                    # 서버 정보 조회
                    server = Server.query.filter_by(name=server_name).first()
                    if not server or not server.ip_address:
                        self._create_notification(
                            f"서버 {server_name} 역할 할당 실패",
                            f"서버 정보를 찾을 수 없거나 IP 주소가 설정되지 않았습니다.",
                            "error"
                        )
                        return
                
                    # 환경 변수 설정
                    env = os.environ.copy()
                    env['TARGET_SERVER_IP'] = server.ip_address
                    
                    # 역할 변수 설정
                    role_vars = extra_vars or {}
                    role_vars['target_server'] = server.ip_address
                    role_vars['role'] = role
                    
                    # Ansible 명령어 구성
                    command = [
                        'ansible-playbook',
                        '-i', self.dynamic_inventory_script,
                        self.single_server_playbook,
                        '--extra-vars', json.dumps(role_vars),
                        '--ssh-common-args="-o StrictHostKeyChecking=no"'
                    ]
                    
                    # Ansible 실행
                    returncode, stdout, stderr = self._run_ansible_command(command, env=env)
                    
                    if returncode == 0:
                        # 성공 시 DB 업데이트
                        server.role = role
                        db.session.commit()
                        self._update_tfvars_role(server_name, role)
                        
                        # 성공 로그 구성
                        success_log = f"""✅ Ansible 실행 성공
서버: {server_name}
역할: {role}
명령어: {' '.join(command)}

출력:
{stdout}"""
                        
                        self._create_notification(
                            f"서버 {server_name} 역할 할당 완료",
                            f"역할 '{role}'이 성공적으로 적용되었습니다.",
                            "success",
                            success_log
                        )
                        print(f"✅ 비동기 Ansible 실행 성공: {server_name} - {role}")
                    else:
                        # 실패 시 알림 (상세 로그 포함)
                        error_log = f"""❌ Ansible 실행 실패
서버: {server_name}
역할: {role}
명령어: {' '.join(command)}
Return Code: {returncode}

표준 출력:
{stdout}

오류 출력:
{stderr}"""
                        
                        self._create_notification(
                            f"서버 {server_name} 역할 할당 실패",
                            f"Ansible 실행 중 오류가 발생했습니다. (Return Code: {returncode})",
                            "error",
                            error_log
                        )
                        print(f"❌ 비동기 Ansible 실행 실패: {server_name} - {role}")
                        
            except Exception as e:
                # Flask 컨텍스트가 없을 때도 알림 생성 시도
                try:
                    from app import create_app
                    app = create_app()
                    with app.app_context():
                        error_msg = f"비동기 Ansible 실행 중 예외 발생: {str(e)}"
                        self._create_notification(
                            f"서버 {server_name} 역할 할당 실패",
                            error_msg,
                            "error"
                        )
                except:
                    print(f"❌ 알림 생성 실패: {e}")
                print(f"❌ 비동기 Ansible 실행 중 예외 발생: {str(e)}")
                
                # 예외 발생 시에도 로그 포함하여 알림 생성
                try:
                    from app import create_app
                    app = create_app()
                    with app.app_context():
                        error_log = f"""❌ Ansible 실행 중 예외 발생
서버: {server_name}
역할: {role}
예외: {str(e)}
타입: {type(e).__name__}"""
                        
                        self._create_notification(
                            f"서버 {server_name} 역할 할당 실패",
                            f"Ansible 실행 중 예외가 발생했습니다: {type(e).__name__}",
                            "error",
                            error_log
                        )
                except:
                    pass
        
        # 백그라운드 스레드에서 실행
        thread = threading.Thread(target=run_ansible)
        thread.daemon = True
        thread.start()
        
        return f"Ansible 실행이 백그라운드에서 시작되었습니다. 완료 시 알림을 확인하세요."

    def _create_notification(self, title: str, message: str, severity: str = "info", details: str = None):
        """알림 생성"""
        try:
            notification = Notification(
                type="ansible_role",
                title=title,
                message=message,
                severity=severity,
                details=details,
                created_at=datetime.now()
            )
            db.session.add(notification)
            db.session.commit()
            print(f"✅ 알림 생성: {title}")
        except Exception as e:
            print(f"⚠️ 알림 생성 실패: {e}") 