"""
Proxmox API 서비스
"""
import requests
import logging
import sqlite3
import json
import os
from typing import Dict, List, Optional, Tuple, Any
from flask import current_app
from app.models.server import Server
from app.models.notification import Notification
from app import db

logger = logging.getLogger(__name__)

# terraform.tfvars.json 파일 경로
TFVARS_PATH = 'terraform/terraform.tfvars.json'

class ProxmoxService:
    """Proxmox API 서비스"""
    
    def __init__(self):
        self.endpoint = current_app.config['PROXMOX_ENDPOINT']
        self.username = current_app.config['PROXMOX_USERNAME']
        self.password = current_app.config['PROXMOX_PASSWORD']
        self.node = current_app.config['PROXMOX_NODE']
        self.session = requests.Session()
        self.session.verify = False  # SSL 인증서 검증 비활성화 (개발용)
    
    def _get_db_connection(self):
        """데이터베이스 연결"""
        conn = sqlite3.connect('proxmox.db')
        conn.row_factory = sqlite3.Row
        return conn
    
    def get_proxmox_auth(self) -> Tuple[Optional[Dict[str, str]], Optional[str]]:
        """Proxmox API 인증 정보 반환 (공통 함수)"""
        try:
            print(f"🔐 Proxmox 인증 시도: {self.endpoint}")
            auth_url = f"{self.endpoint}/api2/json/access/ticket"
            auth_data = {'username': self.username, 'password': self.password}
            
            auth_response = self.session.post(auth_url, data=auth_data, timeout=3)
            print(f"📡 인증 응답 상태: {auth_response.status_code}")
            
            if auth_response.status_code != 200:
                return None, 'Proxmox 인증 실패'
            
            auth_result = auth_response.json()
            print(f"🔑 인증 결과: {auth_result}")
            
            if 'data' not in auth_result:
                return None, '인증 토큰을 가져올 수 없습니다'
            
            ticket = auth_result['data']['ticket']
            csrf_token = auth_result['data']['CSRFPreventionToken']
            
            headers = {
                'Cookie': f'PVEAuthCookie={ticket}',
                'CSRFPreventionToken': csrf_token
            }
            
            print(f"✅ 인증 성공: {headers}")
            return headers, None
        except Exception as e:
            print(f"❌ Proxmox 인증 실패: {e}")
            return None, f'인증 중 예외 발생: {str(e)}'
    
    def get_proxmox_vms(self, headers: Dict[str, str]) -> Tuple[Optional[List[Dict[str, Any]]], Optional[str]]:
        """Proxmox에서 모든 VM 목록 조회 (공통 함수)"""
        try:
            print(f"🔍 VM 목록 조회 시작")
            
            # 모든 노드에서 VM 검색
            nodes_url = f"{self.endpoint}/api2/json/nodes"
            nodes_response = self.session.get(nodes_url, headers=headers, timeout=3)
            
            if nodes_response.status_code != 200:
                return None, '노드 정보를 가져올 수 없습니다'
            
            nodes = nodes_response.json().get('data', [])
            all_vms = []
            
            for node in nodes:
                node_name = node['node']
                vms_url = f"{self.endpoint}/api2/json/nodes/{node_name}/qemu"
                vms_response = self.session.get(vms_url, headers=headers, timeout=3)
                
                if vms_response.status_code == 200:
                    vms = vms_response.json().get('data', [])
                    for vm in vms:
                        vm['node'] = node_name
                    all_vms.extend(vms)
            
            print(f"📋 총 VM 수: {len(all_vms)}")
            return all_vms, None
        except Exception as e:
            print(f"❌ VM 목록 조회 실패: {e}")
            return None, f'VM 목록 조회 중 예외 발생: {str(e)}'
    
    def read_servers_from_tfvars(self):
        """terraform.tfvars.json에서 서버 정보 읽기"""
        try:
            with open(TFVARS_PATH, 'r', encoding='utf-8') as f:
                obj = json.load(f)
                return obj.get('servers', {})
        except FileNotFoundError:
            print(f"⚠️ terraform.tfvars.json 파일이 존재하지 않습니다: {TFVARS_PATH}")
            return {}
        except json.JSONDecodeError as e:
            print(f"❌ terraform.tfvars.json 파일 파싱 오류: {e}")
            return {}
        except Exception as e:
            print(f"❌ terraform.tfvars.json 파일 읽기 오류: {e}")
            return {}
    
    def get_all_vms(self) -> Dict[str, Any]:
        """모든 VM 정보 조회 (API 호환)"""
        try:
            print(f"🔍 get_all_vms 시작")
            
            # Proxmox 인증
            headers, error = self.get_proxmox_auth()
            if error:
                print(f"❌ 인증 실패: {error}")
                return {
                    'success': False,
                    'message': error,
                    'data': {
                        'vms': [],
                        'total': 0,
                        'running': 0,
                        'stopped': 0
                    }
                }
            
            # Proxmox 노드 정보 조회 (전체 리소스 확인)
            node_url = f"{self.endpoint}/api2/json/nodes/{self.node}/status"
            node_response = self.session.get(node_url, headers=headers, verify=False, timeout=3)
            
            if node_response.status_code != 200:
                print(f"❌ 노드 정보 조회 실패: {node_response.status_code}")
                return {
                    'success': False,
                    'message': '노드 정보를 가져올 수 없습니다',
                    'data': {
                        'vms': [],
                        'total': 0,
                        'running': 0,
                        'stopped': 0
                    }
                }
            
            node_data = node_response.json()['data']
            print(f"📊 노드 데이터: {node_data}")
            
            node_cpu_count = node_data.get('cpuinfo', {}).get('cpus', 0)
            node_memory_total = node_data.get('memory', {}).get('total', 0)
            node_memory_used = node_data.get('memory', {}).get('used', 0)
            
            # Proxmox에서 VM 목록 조회
            vms, error = self.get_proxmox_vms(headers)
            if error:
                print(f"❌ VM 목록 조회 실패: {error}")
                return {
                    'success': False,
                    'message': error,
                    'data': {
                        'vms': [],
                        'total': 0,
                        'running': 0,
                        'stopped': 0
                    }
                }
            
            # terraform.tfvars.json에 있는 서버만 필터링
            servers = self.read_servers_from_tfvars()
            print(f"📋 tfvars 서버 수: {len(servers)}")
            
            all_servers = {}
            vm_total_cpu = 0
            vm_total_memory = 0
            vm_used_cpu = 0
            vm_used_memory = 0
            running_count = 0
            stopped_count = 0
            
            for vm in vms:
                if vm['name'] in servers:
                    server_data = servers[vm['name']]
                    print(f"🔍 VM 처리: {vm['name']}")
                    
                    # IP 정보 추출 (network_devices 또는 ip_addresses)
                    ip_list = []
                    if 'network_devices' in server_data and server_data['network_devices']:
                        ip_list = [nd.get('ip_address') for nd in server_data['network_devices'] if nd.get('ip_address')]
                    elif 'ip_addresses' in server_data and server_data['ip_addresses']:
                        ip_list = server_data['ip_addresses']
                    
                    # CPU 정보 추출 (tfvars에서 가져오거나 기본값 사용)
                    vm_cpu = server_data.get('cpu', 1)
                    
                    # DB에서 방화벽 그룹 정보 가져오기
                    firewall_group = None
                    try:
                        with self._get_db_connection() as conn:
                            cursor = conn.cursor()
                            cursor.execute('SELECT firewall_group FROM servers WHERE name = ?', (vm['name'],))
                            db_server = cursor.fetchone()
                            if db_server:
                                firewall_group = db_server['firewall_group']
                    except Exception as e:
                        print(f"⚠️ DB 조회 실패: {e}")
                    
                    status_info = {
                        'name': vm['name'],
                        'status': vm['status'],
                        'vmid': vm['vmid'],
                        'node': vm['node'],
                        'cpu': vm.get('cpu', 0),
                        'memory': vm.get('mem', 0),
                        'maxmem': vm.get('maxmem', 0),
                        'uptime': vm.get('uptime', 0),
                        'disk': vm.get('disk', 0),
                        'maxdisk': vm.get('maxdisk', 0),
                        'role': server_data.get('role', 'unknown'),
                        'firewall_group': firewall_group,
                        'ip_addresses': ip_list,
                        'vm_cpu': vm_cpu  # tfvars에서 가져온 CPU 코어 수
                    }
                    all_servers[vm['name']] = status_info
                    
                    # VM 통계 계산
                    if vm['status'] == 'running':
                        running_count += 1
                        vm_total_memory += vm.get('maxmem', 0)
                        vm_used_memory += vm.get('mem', 0)  # 현재 사용 중인 메모리
                        vm_total_cpu += vm_cpu
                        vm_used_cpu += vm_cpu  # 실행 중인 서버는 CPU를 모두 사용 중
                    else:
                        stopped_count += 1
                        vm_total_memory += vm.get('maxmem', 0)
                        vm_total_cpu += vm_cpu
                        # 중지된 서버는 CPU/메모리 사용량 0
            
            # 노드 기준 통계 정보 추가
            stats = {
                'total_servers': len(all_servers),
                'running_servers': running_count,
                'stopped_servers': stopped_count,
                # 노드 전체 리소스
                'node_total_cpu': node_cpu_count,
                'node_total_memory_gb': round(node_memory_total / (1024 * 1024 * 1024), 1),
                'node_used_memory_gb': round(node_memory_used / (1024 * 1024 * 1024), 1),
                # VM 할당된 리소스
                'vm_total_cpu': vm_total_cpu,
                'vm_total_memory_gb': round(vm_total_memory / (1024 * 1024 * 1024), 1),
                'vm_used_cpu': vm_used_cpu,
                'vm_used_memory_gb': round(vm_used_memory / (1024 * 1024 * 1024), 1),
                # 사용률 계산
                'cpu_usage_percent': round((vm_used_cpu / node_cpu_count * 100) if node_cpu_count > 0 else 0, 1),
                'memory_usage_percent': round((vm_used_memory / node_memory_total * 100) if node_memory_total > 0 else 0, 1),
                'cpu_allocation_percent': round((vm_total_cpu / node_cpu_count * 100) if node_cpu_count > 0 else 0, 1),
                'memory_allocation_percent': round((vm_total_memory / node_memory_total * 100) if node_memory_total > 0 else 0, 1)
            }
            
            result = {
                'success': True,
                'data': {
                    'servers': all_servers,
                    'stats': stats
                }
            }
            print(f"✅ get_all_vms 완료: {result}")
            return result
                
        except Exception as e:
            print(f"❌ get_all_vms 실패: {e}")
            return {
                'success': False,
                'message': str(e),
                'data': {
                    'vms': [],
                    'total': 0,
                    'running': 0,
                    'stopped': 0
                }
            }

    def get_storage_info(self) -> Dict[str, Any]:
        """스토리지 정보 조회 (API 호환)"""
        try:
            print(f"🔍 get_storage_info 시작")
            headers, error = self.get_proxmox_auth()
            if error:
                print(f"❌ 인증 실패: {error}")
                return {
                    'success': False,
                    'message': error,
                    'data': []
                }
            
            url = f"{self.endpoint}/api2/json/nodes/{self.node}/storage"
            
            print(f"🌐 스토리지 API URL: {url}")
            response = self.session.get(url, headers=headers, timeout=3)
            print(f"📡 스토리지 API 응답 상태: {response.status_code}")
            
            response.raise_for_status()
            
            storage_data = response.json()
            print(f"📋 스토리지 데이터: {storage_data}")
            
            storage_list = storage_data['data']
            print(f"📋 스토리지 수: {len(storage_list)}")
            
            processed_storage = []
            for storage in storage_list:
                storage_info = {
                    'storage': storage.get('storage'),
                    'type': storage.get('type', 'unknown'),
                    'content': storage.get('content', []),
                    'shared': storage.get('shared', False),
                    'active': storage.get('active', False),
                    'avail': storage.get('avail', 0),
                    'total': storage.get('total', 0),
                    'used': storage.get('used', 0)
                }
                processed_storage.append(storage_info)
            
            result = {
                'success': True,
                'data': processed_storage
            }
            print(f"✅ get_storage_info 완료: {result}")
            return result
                
        except Exception as e:
            print(f"❌ get_storage_info 실패: {e}")
            return {
                'success': False,
                'message': str(e),
                'data': []
            }

    def start_vm(self, server_name: str) -> Dict[str, Any]:
        """VM 시작 (API 호환)"""
        try:
            # 서버명으로 VM ID 찾기
            vm_list = self.get_vm_list()
            target_vm = None
            
            for vm in vm_list:
                if vm.get('name') == server_name:
                    target_vm = vm
                    break
            
            if not target_vm:
                return {
                    'success': False,
                    'message': f'서버 {server_name}을(를) 찾을 수 없습니다.'
                }
            
            vmid = target_vm['vmid']
            if self.vm_action(vmid, 'start'):
                return {
                    'success': True,
                    'message': f'서버 {server_name}이(가) 시작되었습니다.'
                }
            else:
                return {
                    'success': False,
                    'message': f'서버 {server_name} 시작에 실패했습니다.'
                }
                
        except Exception as e:
            logger.error(f"VM 시작 실패: {e}")
            return {
                'success': False,
                'message': str(e)
            }

    def stop_vm(self, server_name: str) -> Dict[str, Any]:
        """VM 중지 (API 호환)"""
        try:
            # 서버명으로 VM ID 찾기
            vm_list = self.get_vm_list()
            target_vm = None
            
            for vm in vm_list:
                if vm.get('name') == server_name:
                    target_vm = vm
                    break
            
            if not target_vm:
                return {
                    'success': False,
                    'message': f'서버 {server_name}을(를) 찾을 수 없습니다.'
                }
            
            vmid = target_vm['vmid']
            if self.vm_action(vmid, 'stop'):
                return {
                    'success': True,
                    'message': f'서버 {server_name}이(가) 중지되었습니다.'
                }
            else:
                return {
                    'success': False,
                    'message': f'서버 {server_name} 중지에 실패했습니다.'
                }
                
        except Exception as e:
            logger.error(f"VM 중지 실패: {e}")
            return {
                'success': False,
                'message': str(e)
            }

    def reboot_vm(self, server_name: str) -> Dict[str, Any]:
        """VM 재부팅 (API 호환)"""
        try:
            print(f"🔧 VM 재부팅 시작: {server_name}")
            # 서버명으로 VM ID 찾기
            vm_list = self.get_vm_list()
            target_vm = None
            
            for vm in vm_list:
                if vm.get('name') == server_name:
                    target_vm = vm
                    break
            
            if not target_vm:
                print(f"❌ VM을 찾을 수 없음: {server_name}")
                return {
                    'success': False,
                    'message': f'서버 {server_name}을(를) 찾을 수 없습니다.'
                }
            
            vmid = target_vm['vmid']
            print(f"🔧 VM 액션 호출: {vmid} - reset")
            if self.vm_action(vmid, 'reset'):
                print(f"✅ VM 재부팅 성공: {server_name}")
                return {
                    'success': True,
                    'message': f'서버 {server_name}이(가) 재부팅되었습니다.'
                }
            else:
                print(f"❌ VM 재부팅 실패: {server_name}")
                return {
                    'success': False,
                    'message': f'서버 {server_name} 재부팅에 실패했습니다.'
                }
                
        except Exception as e:
            print(f"❌ VM 재부팅 실패: {e}")
            return {
                'success': False,
                'message': str(e)
            }
    
    def check_vm_exists(self, name: str) -> bool:
        """VM 존재 여부 확인"""
        try:
            headers, error = self.get_proxmox_auth()
            if error:
                return False
            
            vms, error = self.get_proxmox_vms(headers)
            if error:
                return False
            
            return any(vm['name'] == name for vm in vms)
        except Exception as e:
            print(f"❌ VM 존재 확인 실패: {e}")
            return False

    def get_vm_info(self, name: str) -> Optional[Dict[str, Any]]:
        """특정 VM의 상세 정보 조회"""
        try:
            print(f"🔍 VM 정보 조회: {name}")
            headers, error = self.get_proxmox_auth()
            if error:
                print(f"❌ 인증 실패: {error}")
                return None
            
            vms, error = self.get_proxmox_vms(headers)
            if error:
                print(f"❌ VM 목록 조회 실패: {error}")
                return None
            
            # 특정 VM 찾기
            for vm in vms:
                if vm['name'] == name:
                    print(f"✅ VM 정보 찾음: {name} - {vm.get('status', 'unknown')}")
                    return vm
            
            print(f"❌ VM을 찾을 수 없음: {name}")
            return None
        except Exception as e:
            print(f"❌ VM 정보 조회 실패: {e}")
            return None

    def get_vm_list(self) -> List[Dict[str, Any]]:
        """VM 목록 조회 (API 호환)"""
        try:
            print("🔍 VM 목록 조회 (API 호환)")
            headers, error = self.get_proxmox_auth()
            if error:
                print(f"❌ 인증 실패: {error}")
                return []
            
            vms, error = self.get_proxmox_vms(headers)
            if error:
                print(f"❌ VM 목록 조회 실패: {error}")
                return []
            
            # 각 VM의 상세 정보 가져오기
            detailed_vms = []
            for vm in vms:
                try:
                    node = vm.get('node', self.node)
                    vmid = vm.get('vmid')
                    
                    # VM 상세 정보 조회
                    vm_detail_url = f"{self.endpoint}/api2/json/nodes/{node}/qemu/{vmid}/status/current"
                    detail_response = self.session.get(vm_detail_url, headers=headers, timeout=3)
                    
                    if detail_response.status_code == 200:
                        detail_data = detail_response.json().get('data', {})
                        
                        # 상세 정보와 기본 정보 병합
                        vm.update({
                            'cpu': detail_data.get('cpu', 0),
                            'memory': detail_data.get('memory', 0),
                            'maxmem': detail_data.get('maxmem', 0),
                            'cpus': detail_data.get('cpus', 0),
                            'network_devices': detail_data.get('netin', []),  # 네트워크 정보
                            'ip_addresses': self._extract_ip_addresses(detail_data)
                        })
                    
                    detailed_vms.append(vm)
                except Exception as e:
                    print(f"⚠️ VM 상세 정보 조회 실패 ({vm.get('name', 'unknown')}): {e}")
                    detailed_vms.append(vm)  # 기본 정보라도 포함
            
            print(f"✅ VM 목록 조회 완료: {len(detailed_vms)}개")
            return detailed_vms
        except Exception as e:
            print(f"❌ VM 목록 조회 실패: {e}")
            return []

    def _extract_ip_addresses(self, vm_data: Dict[str, Any]) -> List[str]:
        """VM 데이터에서 IP 주소 추출"""
        ip_addresses = []
        try:
            # 네트워크 인터페이스에서 IP 주소 추출
            for key, value in vm_data.items():
                if key.startswith('net') and isinstance(value, str):
                    # net0, net1 등의 네트워크 인터페이스에서 IP 추출
                    if 'ip=' in value:
                        ip_parts = value.split('ip=')
                        if len(ip_parts) > 1:
                            ip_part = ip_parts[1].split(',')[0]
                            if ip_part and ip_part != 'dhcp':
                                ip_addresses.append(ip_part)
        except Exception as e:
            print(f"⚠️ IP 주소 추출 실패: {e}")
        
        return ip_addresses

    def vm_action(self, vmid: int, action: str) -> bool:
        """VM 액션 수행 (시작/중지/재부팅)"""
        try:
            print(f"🔧 VM 액션 수행: {vmid} - {action}")
            headers, error = self.get_proxmox_auth()
            if error:
                print(f"❌ 인증 실패: {error}")
                return False
            
            # VM 정보 조회로 노드 확인
            vms, error = self.get_proxmox_vms(headers)
            if error:
                print(f"❌ VM 목록 조회 실패: {error}")
                return False
            
            target_vm = None
            for vm in vms:
                if vm.get('vmid') == vmid:
                    target_vm = vm
                    break
            
            if not target_vm:
                print(f"❌ VM을 찾을 수 없음: {vmid}")
                return False
            
            node = target_vm.get('node', self.node)
            
            # 액션 URL 구성
            action_url = f"{self.endpoint}/api2/json/nodes/{node}/qemu/{vmid}/status/{action}"
            
            # 액션 수행
            response = self.session.post(action_url, headers=headers, timeout=30)
            
            if response.status_code == 200:
                print(f"✅ VM 액션 성공: {vmid} - {action}")
                return True
            else:
                print(f"❌ VM 액션 실패: {vmid} - {action} - {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ VM 액션 실패: {e}")
            return False

    def start_server(self, server_name: str) -> Dict[str, Any]:
        """서버 시작 (API 호환)"""
        try:
            print(f"🔧 서버 시작: {server_name}")
            return self.start_vm(server_name)
        except Exception as e:
            print(f"❌ 서버 시작 실패: {e}")
            return {
                'success': False,
                'message': str(e)
            }

    def stop_server(self, server_name: str) -> Dict[str, Any]:
        """서버 중지 (API 호환)"""
        try:
            print(f"🔧 서버 중지: {server_name}")
            return self.stop_vm(server_name)
        except Exception as e:
            print(f"❌ 서버 중지 실패: {e}")
            return {
                'success': False,
                'message': str(e)
            }

    def reboot_server(self, server_name: str) -> Dict[str, Any]:
        """서버 재부팅 (API 호환)"""
        try:
            print(f"🔧 서버 재부팅: {server_name}")
            return self.reboot_vm(server_name)
        except Exception as e:
            print(f"❌ 서버 재부팅 실패: {e}")
            return {
                'success': False,
                'message': str(e)
            }

    def wait_for_vm_status(self, vmid: int, target_status: str, timeout: int = 300) -> bool:
        """VM 상태 대기"""
        import time
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            vm_info = self.get_vm_info(vmid)
            if vm_info and vm_info.get('status') == target_status:
                return True
            time.sleep(5)
        
        return False
    
    def get_firewall_groups(self) -> List[Dict[str, Any]]:
        """방화벽 그룹 목록 조회"""
        try:
            print("🔍 방화벽 그룹 목록 조회")
            headers, error = self.get_proxmox_auth()
            if error:
                print(f"❌ 인증 실패: {error}")
                return []
            
            # Proxmox에서 방화벽 그룹 정보 가져오기
            firewall_url = f"{self.endpoint}/api2/json/nodes/{self.node}/firewall/groups"
            response = self.session.get(firewall_url, headers=headers, timeout=3)
            
            if response.status_code == 200:
                firewall_data = response.json().get('data', {})
                groups = []
                
                for group_name, group_info in firewall_data.items():
                    groups.append({
                        'name': group_name,
                        'description': group_info.get('comment', ''),
                        'rules': group_info.get('rules', [])
                    })
                
                print(f"✅ 방화벽 그룹 조회 완료: {len(groups)}개")
                return groups
            else:
                print(f"❌ 방화벽 그룹 조회 실패: {response.status_code}")
                return []
                
        except Exception as e:
            print(f"❌ 방화벽 그룹 조회 실패: {e}")
            return []

    def sync_vm_data(self):
        """VM 데이터 동기화"""
        try:
            vm_list = self.get_vm_list()
            
            for vm_data in vm_list:
                server = Server.get_by_name(vm_data['name'])
                if server:
                    # 기존 서버 정보 업데이트
                    server.vmid = vm_data['vmid']
                    server.status = vm_data['status']
                    server.update_vm_info(vm_data['vmid'])
                else:
                    # 새 서버 정보 추가
                    server = Server(
                        name=vm_data['name'],
                        vmid=vm_data['vmid'],
                        status=vm_data['status']
                    )
                    db.session.add(server)
            
            db.session.commit()
            logger.info("VM 데이터 동기화 완료")
            
        except Exception as e:
            logger.error(f"VM 데이터 동기화 실패: {e}")
            db.session.rollback()
            raise 