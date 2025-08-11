"""
Terraform 서비스
"""
import subprocess
import json
import os
import logging
import tempfile
from typing import Tuple, Dict, List, Any, Optional
from flask import current_app
from app.models.server import Server
from app.models.notification import Notification

logger = logging.getLogger(__name__)

class TerraformService:
    """Terraform 서비스"""
    
    def __init__(self, terraform_dir: str = "terraform"):
        self.terraform_dir = terraform_dir
        self.tfvars_file = os.path.join(terraform_dir, "terraform.tfvars.json")
    
    def _run_terraform_command(self, command: List[str], cwd: str = None) -> Tuple[int, str, str]:
        """Terraform 명령어 실행"""
        if cwd is None:
            cwd = self.terraform_dir
        
        print(f"🔧 Terraform 명령어 실행: {' '.join(command)} (cwd: {cwd})")
        
        try:
            # Windows 환경에서 인코딩 문제 해결을 위해 UTF-8 명시적 지정
            result = subprocess.run(
                command,
                cwd=cwd,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',  # 디코딩 에러 시 대체 문자 사용
                timeout=300  # 5분 타임아웃
            )
            print(f"🔧 Terraform 명령어 완료: returncode={result.returncode}")
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            logger.error("Terraform 명령어 실행 타임아웃")
            print("❌ Terraform 명령어 실행 타임아웃")
            return -1, "", "Terraform 명령어 실행 타임아웃"
        except Exception as e:
            logger.error(f"Terraform 명령어 실행 실패: {e}")
            print(f"❌ Terraform 명령어 실행 실패: {e}")
            return -1, "", str(e)
    
    def init(self) -> bool:
        """Terraform 초기화"""
        logger.info("Terraform 초기화 시작")
        returncode, stdout, stderr = self._run_terraform_command(["terraform", "init"])
        
        if returncode == 0:
            logger.info("Terraform 초기화 성공")
            return True
        else:
            error_msg = stderr or stdout or "알 수 없는 Terraform 초기화 오류"
            logger.error(f"Terraform 초기화 실패: {error_msg}")
            return False
    
    def plan(self) -> Tuple[bool, str]:
        """Terraform 계획"""
        logger.info("Terraform 계획 시작")
        print("🔧 Terraform plan 명령어 실행")
        returncode, stdout, stderr = self._run_terraform_command(["terraform", "plan"])
        print(f"🔧 Terraform plan 결과: returncode={returncode}, stdout_length={len(stdout) if stdout else 0}, stderr_length={len(stderr) if stderr else 0}")
        
        if returncode == 0:
            logger.info("Terraform 계획 성공")
            result_msg = stdout or "Terraform 계획이 성공적으로 완료되었습니다."
            print(f"✅ Terraform 계획 성공: {len(result_msg)} 문자")
            return True, result_msg
        else:
            error_msg = stderr or stdout or "알 수 없는 Terraform 계획 오류"
            logger.error(f"Terraform 계획 실패: {error_msg}")
            print(f"❌ Terraform 계획 실패: {error_msg}")
            return False, error_msg
    
    def apply(self, targets: List[str] = None) -> Tuple[bool, str]:
        """Terraform 적용
        
        Args:
            targets: 특정 리소스만 대상으로 적용할 때 사용 (예: ["module.server[\"server1\"]"])
        """
        logger.info("Terraform 적용 시작")
        command = ["terraform", "apply", "-auto-approve"]
        
        if targets:
            for target in targets:
                command.extend(["-target", target])
            logger.info(f"Targeted apply 실행: {targets}")
            print(f"🔧 Targeted Terraform apply 실행: {targets}")
        
        returncode, stdout, stderr = self._run_terraform_command(command)
        
        if returncode == 0:
            logger.info("Terraform 적용 성공")
            return True, stdout or "Terraform 적용이 성공적으로 완료되었습니다."
        else:
            error_msg = stderr or stdout or "알 수 없는 Terraform 적용 오류"
            logger.error(f"Terraform 적용 실패: {error_msg}")
            return False, error_msg
    
    def destroy(self, target: str = None) -> Tuple[bool, str]:
        """Terraform 삭제 (단일 타겟)"""
        logger.info("Terraform 삭제 시작")
        command = ["terraform", "destroy", "-auto-approve"]
        if target:
            command.extend(["-target", target])
        
        returncode, stdout, stderr = self._run_terraform_command(command)
        
        if returncode == 0:
            logger.info("Terraform 삭제 성공")
            return True, stdout or "Terraform 삭제가 성공적으로 완료되었습니다."
        else:
            error_msg = stderr or stdout or "알 수 없는 Terraform 삭제 오류"
            logger.error(f"Terraform 삭제 실패: {error_msg}")
            return False, error_msg
    
    def destroy_targets(self, targets: List[str]) -> Tuple[bool, str]:
        """Terraform 대량 삭제 (여러 타겟)
        
        Args:
            targets: 삭제할 리소스 목록 (예: ["module.server[\"server1\"]", "module.server[\"server2\"]"])
        """
        if not targets:
            return False, "삭제할 타겟이 지정되지 않았습니다."
        
        logger.info(f"Terraform 대량 삭제 시작: {targets}")
        command = ["terraform", "destroy", "-auto-approve"]
        
        # 모든 타겟을 -target 옵션으로 추가
        for target in targets:
            command.extend(["-target", target])
        
        logger.info(f"Targeted destroy 실행: {targets}")
        print(f"🔥 Targeted Terraform destroy 실행: {targets}")
        
        returncode, stdout, stderr = self._run_terraform_command(command)
        
        if returncode == 0:
            logger.info(f"Terraform 대량 삭제 성공: {targets}")
            return True, stdout or f"{len(targets)}개 리소스 삭제가 성공적으로 완료되었습니다."
        else:
            error_msg = stderr or stdout or "알 수 없는 Terraform 삭제 오류"
            logger.error(f"Terraform 대량 삭제 실패: {error_msg}")
            return False, error_msg
    
    def output(self) -> Dict[str, Any]:
        """Terraform 출력값 조회"""
        logger.info("Terraform 출력값 조회")
        returncode, stdout, stderr = self._run_terraform_command(["terraform", "output", "-json"])
        
        if returncode == 0:
            try:
                return json.loads(stdout) if stdout.strip() else {}
            except json.JSONDecodeError:
                logger.error("Terraform 출력값 파싱 실패")
                return {}
        else:
            error_msg = stderr or stdout or "알 수 없는 Terraform 출력값 조회 오류"
            logger.error(f"Terraform 출력값 조회 실패: {error_msg}")
            return {}
    
    def load_tfvars(self) -> Dict[str, Any]:
        """terraform.tfvars.json 파일 로드"""
        try:
            if os.path.exists(self.tfvars_file):
                with open(self.tfvars_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                logger.warning(f"terraform.tfvars.json 파일이 존재하지 않습니다: {self.tfvars_file}")
                return {}
        except Exception as e:
            logger.error(f"terraform.tfvars.json 파일 로드 실패: {e}")
            return {}
    
    def save_tfvars(self, data: Dict[str, Any]) -> bool:
        """terraform.tfvars.json 파일 저장"""
        try:
            with open(self.tfvars_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info("terraform.tfvars.json 파일 저장 성공")
            return True
        except Exception as e:
            logger.error(f"terraform.tfvars.json 파일 저장 실패: {e}")
            return False
    
    def create_server_config(self, server_data: Dict[str, Any]) -> bool:
        """서버 설정 생성"""
        try:
            print(f"🔧 create_server_config 시작: {server_data.get('name', 'unknown')}")
            # 기존 설정 로드
            tfvars = self.load_tfvars()
            print(f"🔧 기존 tfvars 로드 완료: {len(tfvars)} 항목")
            
            # 서버 설정 추가
            if 'servers' not in tfvars:
                tfvars['servers'] = {}
            
            server_name = server_data['name']
            tfvars['servers'][server_name] = server_data
            print(f"🔧 서버 설정 추가 완료: {server_name}")
            
            # 설정 저장
            result = self.save_tfvars(tfvars)
            print(f"🔧 tfvars 저장 결과: {result}")
            return result
            
        except Exception as e:
            print(f"💥 create_server_config 실패: {e}")
            logger.error(f"서버 설정 생성 실패: {e}")
            return False
    
    def remove_server_config(self, server_name: str) -> bool:
        """서버 설정 제거"""
        try:
            # 기존 설정 로드
            tfvars = self.load_tfvars()
            
            # 서버 설정 제거
            if 'servers' in tfvars and server_name in tfvars['servers']:
                del tfvars['servers'][server_name]
                
                # 설정 저장
                return self.save_tfvars(tfvars)
            
            return True
            
        except Exception as e:
            logger.error(f"서버 설정 제거 실패: {e}")
            return False
    
    def deploy_infrastructure(self) -> Tuple[bool, str]:
        """인프라 배포"""
        try:
            print("🔧 deploy_infrastructure 시작")
            
            # tfvars 파일 존재 확인
            if not os.path.exists(self.tfvars_file):
                error_msg = f"terraform.tfvars.json 파일이 존재하지 않습니다: {self.tfvars_file}"
                print(f"❌ {error_msg}")
                return False, error_msg
            
            # tfvars 파일 내용 확인
            try:
                tfvars = self.load_tfvars()
                if not tfvars or 'servers' not in tfvars:
                    error_msg = "terraform.tfvars.json 파일에 서버 설정이 없습니다."
                    print(f"❌ {error_msg}")
                    return False, error_msg
                print(f"✅ tfvars 파일 로드 성공: {len(tfvars.get('servers', {}))}개 서버")
            except Exception as e:
                error_msg = f"tfvars 파일 로드 실패: {e}"
                print(f"❌ {error_msg}")
                return False, error_msg
            
            # 초기화
            print("🔧 Terraform 초기화 시작")
            if not self.init():
                print("❌ Terraform 초기화 실패")
                return False, "Terraform 초기화 실패"
            print("✅ Terraform 초기화 완료")
            
            # 계획
            print("🔧 Terraform 계획 시작")
            plan_success, plan_output = self.plan()
            print(f"🔧 Terraform 계획 결과: success={plan_success}, output_length={len(plan_output) if plan_output else 0}")
            if not plan_success:
                print(f"❌ Terraform 계획 실패: {plan_output}")
                return False, f"Terraform 계획 실패: {plan_output}"
            print("✅ Terraform 계획 완료")
            
            # 적용
            print("🔧 Terraform 적용 시작")
            apply_success, apply_output = self.apply()
            if not apply_success:
                print(f"❌ Terraform 적용 실패: {apply_output}")
                return False, f"Terraform 적용 실패: {apply_output}"
            print("✅ Terraform 적용 완료")
            
            print("✅ 인프라 배포 성공")
            return True, "인프라 배포 성공"
            
        except Exception as e:
            print(f"💥 deploy_infrastructure 실패: {e}")
            logger.error(f"인프라 배포 실패: {e}")
            import traceback
            traceback.print_exc()
            return False, str(e)
    
    def destroy_infrastructure(self, server_name: str = None) -> Tuple[bool, str]:
        """인프라 삭제"""
        try:
            target = None
            if server_name:
                target = f"module.server[\"{server_name}\"]"
            
            success, output = self.destroy(target)
            return success, output
            
        except Exception as e:
            logger.error(f"인프라 삭제 실패: {e}")
            return False, str(e)

    def delete_server(self, server_name: str) -> Dict[str, Any]:
        """서버 삭제 (중지 후 Terraform apply)
        
        @deprecated: 이 메서드는 더 이상 권장되지 않습니다. 
        대신 destroy_targets() 메서드를 사용하세요.
        """
        try:
            print(f"🔧 서버 삭제 시작: {server_name}")
            
            # 1. 먼저 서버 중지
            print(f"🔧 서버 중지 시작: {server_name}")
            from app.services.proxmox_service import ProxmoxService
            proxmox_service = ProxmoxService()
            stop_result = proxmox_service.stop_server(server_name)
            
            if not stop_result['success']:
                print(f"❌ 서버 중지 실패: {server_name} - {stop_result['message']}")
                return {
                    'success': False,
                    'message': f'서버 중지 실패: {stop_result["message"]}'
                }
            
            print(f"✅ 서버 중지 완료: {server_name}")
            
            # 2. 잠시 대기 (서버 중지 완료 대기)
            import time
            print(f"⏳ 서버 중지 완료 대기: {server_name}")
            time.sleep(10)
            
            # 3. tfvars.json에서 서버 설정 제거
            print(f"🔧 tfvars.json에서 서버 설정 제거: {server_name}")
            if not self.remove_server_config(server_name):
                return {
                    'success': False,
                    'message': f'서버 설정 제거 실패: {server_name}'
                }
            
            # 4. Terraform 적용 (변경사항 적용으로 서버 삭제)
            print(f"🔧 Terraform apply로 서버 삭제 시작: {server_name}")
            success, message = self.deploy_infrastructure()
            
            if success:
                print(f"✅ Terraform으로 서버 삭제 성공: {server_name}")
                return {
                    'success': True,
                    'message': f'서버 {server_name}이 중지 후 Terraform으로 삭제되었습니다.'
                }
            else:
                print(f"❌ Terraform으로 서버 삭제 실패: {server_name} - {message}")
                return {
                    'success': False,
                    'message': f'Terraform 서버 삭제 실패: {message}'
                }
                
        except Exception as e:
            error_msg = f'서버 삭제 중 오류: {str(e)}'
            print(f"💥 서버 삭제 예외: {error_msg}")
            return {
                'success': False,
                'message': error_msg
            } 