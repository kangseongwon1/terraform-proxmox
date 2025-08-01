"""
Proxmox API 서비스
"""
import requests
import logging
from typing import Dict, List, Optional, Tuple, Any
from flask import current_app
from app.models.server import Server
from app.models.notification import Notification

logger = logging.getLogger(__name__)

class ProxmoxService:
    """Proxmox API 서비스"""
    
    def __init__(self):
        self.endpoint = current_app.config['PROXMOX_ENDPOINT']
        self.username = current_app.config['PROXMOX_USERNAME']
        self.password = current_app.config['PROXMOX_PASSWORD']
        self.node = current_app.config['PROXMOX_NODE']
        self.session = requests.Session()
        self.session.verify = False  # SSL 인증서 검증 비활성화 (개발용)
    
    def _get_auth_headers(self) -> Dict[str, str]:
        """인증 헤더 생성"""
        try:
            # Proxmox API 인증
            auth_url = f"{self.endpoint}/api2/json/access/ticket"
            auth_data = {
                'username': self.username,
                'password': self.password
            }
            
            response = self.session.post(auth_url, data=auth_data)
            response.raise_for_status()
            
            auth_result = response.json()
            if auth_result['data']:
                ticket = auth_result['data']['ticket']
                csrf_token = auth_result['data']['CSRFPreventionToken']
                
                return {
                    'Cookie': f'PVEAuthCookie={ticket}',
                    'CSRFPreventionToken': csrf_token
                }
            else:
                raise Exception("Proxmox 인증 실패")
                
        except requests.RequestException as e:
            logger.error(f"Proxmox 인증 실패: {e}")
            raise Exception(f"Proxmox 서버에 연결할 수 없습니다: {e}")
    
    def get_vm_list(self) -> List[Dict[str, Any]]:
        """VM 목록 조회"""
        try:
            headers = self._get_auth_headers()
            url = f"{self.endpoint}/api2/json/nodes/{self.node}/qemu"
            
            response = self.session.get(url, headers=headers)
            response.raise_for_status()
            
            return response.json()['data']
            
        except Exception as e:
            logger.error(f"VM 목록 조회 실패: {e}")
            raise
    
    def get_vm_info(self, vmid: int) -> Optional[Dict[str, Any]]:
        """특정 VM 정보 조회"""
        try:
            headers = self._get_auth_headers()
            url = f"{self.endpoint}/api2/json/nodes/{self.node}/qemu/{vmid}/status/current"
            
            response = self.session.get(url, headers=headers)
            response.raise_for_status()
            
            return response.json()['data']
            
        except requests.RequestException as e:
            logger.error(f"VM {vmid} 정보 조회 실패: {e}")
            return None
    
    def vm_action(self, vmid: int, action: str) -> bool:
        """VM 액션 실행 (start, stop, reset, shutdown)"""
        try:
            headers = self._get_auth_headers()
            url = f"{self.endpoint}/api2/json/nodes/{self.node}/qemu/{vmid}/status/{action}"
            
            response = self.session.post(url, headers=headers)
            response.raise_for_status()
            
            logger.info(f"VM {vmid} {action} 액션 실행 성공")
            return True
            
        except Exception as e:
            logger.error(f"VM {vmid} {action} 액션 실패: {e}")
            return False
    
    def delete_vm(self, vmid: int) -> bool:
        """VM 삭제"""
        try:
            headers = self._get_auth_headers()
            url = f"{self.endpoint}/api2/json/nodes/{self.node}/qemu/{vmid}"
            
            response = self.session.delete(url, headers=headers)
            response.raise_for_status()
            
            logger.info(f"VM {vmid} 삭제 성공")
            return True
            
        except Exception as e:
            logger.error(f"VM {vmid} 삭제 실패: {e}")
            return False
    
    def get_storage_info(self) -> List[Dict[str, Any]]:
        """스토리지 정보 조회"""
        try:
            headers = self._get_auth_headers()
            url = f"{self.endpoint}/api2/json/nodes/{self.node}/storage"
            
            response = self.session.get(url, headers=headers)
            response.raise_for_status()
            
            return response.json()['data']
            
        except Exception as e:
            logger.error(f"스토리지 정보 조회 실패: {e}")
            raise
    
    def check_vm_exists(self, name: str) -> bool:
        """VM 존재 여부 확인"""
        try:
            vm_list = self.get_vm_list()
            return any(vm['name'] == name for vm in vm_list)
        except Exception as e:
            logger.error(f"VM 존재 여부 확인 실패: {e}")
            return False
    
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