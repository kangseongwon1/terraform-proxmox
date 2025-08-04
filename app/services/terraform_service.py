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
        
        try:
            result = subprocess.run(
                command,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=300  # 5분 타임아웃
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            logger.error("Terraform 명령어 실행 타임아웃")
            return -1, "", "Terraform 명령어 실행 타임아웃"
        except Exception as e:
            logger.error(f"Terraform 명령어 실행 실패: {e}")
            return -1, "", str(e)
    
    def init(self) -> bool:
        """Terraform 초기화"""
        logger.info("Terraform 초기화 시작")
        returncode, stdout, stderr = self._run_terraform_command(["terraform", "init"])
        
        if returncode == 0:
            logger.info("Terraform 초기화 성공")
            return True
        else:
            logger.error(f"Terraform 초기화 실패: {stderr}")
            return False
    
    def plan(self) -> Tuple[bool, str]:
        """Terraform 계획"""
        logger.info("Terraform 계획 시작")
        returncode, stdout, stderr = self._run_terraform_command(["terraform", "plan"])
        
        if returncode == 0:
            logger.info("Terraform 계획 성공")
            return True, stdout
        else:
            logger.error(f"Terraform 계획 실패: {stderr}")
            return False, stderr
    
    def apply(self) -> Tuple[bool, str]:
        """Terraform 적용"""
        logger.info("Terraform 적용 시작")
        returncode, stdout, stderr = self._run_terraform_command(
            ["terraform", "apply", "-auto-approve"]
        )
        
        if returncode == 0:
            logger.info("Terraform 적용 성공")
            return True, stdout
        else:
            logger.error(f"Terraform 적용 실패: {stderr}")
            return False, stderr
    
    def destroy(self, target: str = None) -> Tuple[bool, str]:
        """Terraform 삭제"""
        logger.info("Terraform 삭제 시작")
        command = ["terraform", "destroy", "-auto-approve"]
        if target:
            command.extend(["-target", target])
        
        returncode, stdout, stderr = self._run_terraform_command(command)
        
        if returncode == 0:
            logger.info("Terraform 삭제 성공")
            return True, stdout
        else:
            logger.error(f"Terraform 삭제 실패: {stderr}")
            return False, stderr
    
    def output(self) -> Dict[str, Any]:
        """Terraform 출력값 조회"""
        logger.info("Terraform 출력값 조회")
        returncode, stdout, stderr = self._run_terraform_command(["terraform", "output", "-json"])
        
        if returncode == 0:
            try:
                return json.loads(stdout)
            except json.JSONDecodeError:
                logger.error("Terraform 출력값 파싱 실패")
                return {}
        else:
            logger.error(f"Terraform 출력값 조회 실패: {stderr}")
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
            # 초기화
            print("🔧 Terraform 초기화 시작")
            if not self.init():
                print("❌ Terraform 초기화 실패")
                return False, "Terraform 초기화 실패"
            print("✅ Terraform 초기화 완료")
            
            # 계획
            print("🔧 Terraform 계획 시작")
            plan_success, plan_output = self.plan()
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