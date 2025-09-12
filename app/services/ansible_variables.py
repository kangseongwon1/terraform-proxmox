"""
Ansible 변수 관리 서비스
"""
import os
import yaml
from typing import Dict, Any, Optional
from flask import current_app

class AnsibleVariableManager:
    """Ansible 변수 관리 클래스"""
    
    def __init__(self, ansible_dir: str = "ansible"):
        # 프로젝트 루트 디렉토리 찾기
        current_file = os.path.abspath(__file__)
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_file)))
        
        self.ansible_dir = os.path.join(project_root, ansible_dir)
        self.group_vars_dir = os.path.join(self.ansible_dir, "group_vars")
        self.host_vars_dir = os.path.join(self.ansible_dir, "host_vars")
        
        # 변수 캐시
        self._variable_cache = {}
        self._cache_loaded = False
    
    def load_all_variables(self) -> Dict[str, Any]:
        """모든 변수 파일을 로드하여 통합된 변수 딕셔너리 반환"""
        if self._cache_loaded:
            return self._variable_cache
        
        variables = {}
        
        # 1. group_vars/all.yml 로드 (기본 변수)
        all_vars_file = os.path.join(self.group_vars_dir, "all.yml")
        if os.path.exists(all_vars_file):
            with open(all_vars_file, 'r', encoding='utf-8') as f:
                all_vars = yaml.safe_load(f) or {}
                variables.update(all_vars)
                print(f"✅ group_vars/all.yml 로드: {len(all_vars)}개 변수")
        
        # 2. 환경별 변수는 제거 (단순화)
        # 필요시 group_vars/all.yml에서 직접 관리
        
        # 3. 역할별 변수 로드 (web, db, was 등)
        role_vars_files = ['web.yml', 'db.yml', 'was.yml', 'search.yml', 'ftp.yml', 'java.yml']
        for role_file in role_vars_files:
            role_vars_path = os.path.join(self.group_vars_dir, role_file)
            if os.path.exists(role_vars_path):
                with open(role_vars_path, 'r', encoding='utf-8') as f:
                    role_vars = yaml.safe_load(f) or {}
                    # 역할별 변수는 접두사를 붙여서 구분
                    role_name = role_file.replace('.yml', '')
                    for key, value in role_vars.items():
                        variables[f"{role_name}_{key}"] = value
                print(f"✅ group_vars/{role_file} 로드: {len(role_vars)}개 변수")
        
        # 4. 환경 변수에서 보안 변수 로드
        security_vars = self._load_security_variables()
        variables.update(security_vars)
        
        # 5. Flask 앱 설정에서 변수 로드
        app_vars = self._load_app_config_variables()
        variables.update(app_vars)
        
        self._variable_cache = variables
        self._cache_loaded = True
        
        print(f"✅ 총 {len(variables)}개 변수 로드 완료")
        return variables
    
    def _load_security_variables(self) -> Dict[str, Any]:
        """환경 변수에서 보안 변수 로드"""
        security_vars = {}
        
        # MySQL 관련 보안 변수
        mysql_root_password = os.environ.get('ANSIBLE_MYSQL_ROOT_PASSWORD')
        if mysql_root_password:
            security_vars['mysql_root_password'] = mysql_root_password
            security_vars['ansible_mysql_root_password'] = mysql_root_password
        
        mysql_user_password = os.environ.get('ANSIBLE_MYSQL_USER_PASSWORD')
        if mysql_user_password:
            security_vars['mysql_user_password'] = mysql_user_password
            security_vars['ansible_mysql_user_password'] = mysql_user_password
        
        mysql_replication_password = os.environ.get('ANSIBLE_MYSQL_REPLICATION_PASSWORD')
        if mysql_replication_password:
            security_vars['mysql_slave_password'] = mysql_replication_password
            security_vars['ansible_mysql_replication_password'] = mysql_replication_password
        
        # FTP 관련 보안 변수
        ftp_password = os.environ.get('ANSIBLE_FTP_PASSWORD')
        if ftp_password:
            security_vars['ftp_password'] = ftp_password
            security_vars['ansible_ftp_password'] = ftp_password
        
        # Tomcat Manager 관련 보안 변수
        tomcat_manager_password = os.environ.get('ANSIBLE_TOMCAT_MANAGER_PASSWORD')
        if tomcat_manager_password:
            security_vars['tomcat_manager_password'] = tomcat_manager_password
            security_vars['ansible_tomcat_manager_password'] = tomcat_manager_password
        
        return security_vars
    
    def _load_app_config_variables(self) -> Dict[str, Any]:
        """Flask 앱 설정에서 변수 로드"""
        app_vars = {}
        
        try:
            if current_app:
                # SSH 설정
                ssh_user = current_app.config.get('SSH_USER')
                if ssh_user:
                    app_vars['ansible_user'] = ssh_user
                
                ssh_private_key = current_app.config.get('SSH_PRIVATE_KEY_PATH')
                if ssh_private_key:
                    app_vars['ansible_ssh_private_key_file'] = ssh_private_key
                
                # Proxmox 설정
                proxmox_endpoint = current_app.config.get('PROXMOX_ENDPOINT')
                if proxmox_endpoint:
                    app_vars['proxmox_endpoint'] = proxmox_endpoint
                
                # 기타 설정들
                for key, value in current_app.config.items():
                    if key.startswith('ANSIBLE_'):
                        app_vars[key.lower()] = value
        except Exception as e:
            print(f"⚠️ Flask 앱 설정 로드 중 오류: {e}")
        
        return app_vars
    
    def get_role_variables(self, role: str) -> Dict[str, Any]:
        """특정 역할에 대한 변수 반환"""
        all_vars = self.load_all_variables()
        role_vars = {}
        
        # 역할별 변수 추출 (접두사 기반)
        role_prefix = f"{role}_"
        for key, value in all_vars.items():
            if key.startswith(role_prefix):
                # 접두사 제거하여 원래 변수명으로 변환
                original_key = key[len(role_prefix):]
                role_vars[original_key] = value
            elif not any(key.startswith(f"{other_role}_") for other_role in ['web', 'db', 'was', 'search', 'ftp', 'java']):
                # 다른 역할 접두사가 없는 공통 변수들
                role_vars[key] = value
        
        return role_vars
    
    def get_environment_variables(self) -> Dict[str, Any]:
        """현재 환경에 대한 변수 반환"""
        all_vars = self.load_all_variables()
        env_vars = {}
        
        # 환경별 변수 추출
        environment = os.environ.get('ANSIBLE_ENVIRONMENT', 'production')
        for key, value in all_vars.items():
            # 환경별 변수는 접두사 없이 직접 사용
            if not any(key.startswith(f"{role}_") for role in ['web', 'db', 'was', 'search', 'ftp', 'java']):
                env_vars[key] = value
        
        return env_vars
    
    def get_variable(self, key: str, default: Any = None) -> Any:
        """특정 변수 값 반환"""
        all_vars = self.load_all_variables()
        return all_vars.get(key, default)
    
    def set_variable(self, key: str, value: Any) -> None:
        """변수 캐시에 변수 설정 (임시)"""
        self._variable_cache[key] = value
    
    def clear_cache(self) -> None:
        """변수 캐시 초기화"""
        self._variable_cache = {}
        self._cache_loaded = False
        print("🔄 Ansible 변수 캐시 초기화")
    
    def get_ansible_extra_vars(self, role: str, additional_vars: Dict[str, Any] = None) -> Dict[str, Any]:
        """Ansible 실행을 위한 extra_vars 딕셔너리 생성"""
        # 기본 변수 로드
        extra_vars = self.get_role_variables(role)
        
        # 추가 변수 병합
        if additional_vars:
            extra_vars.update(additional_vars)
        
        # 역할 정보 추가
        extra_vars['role'] = role
        
        # 환경 정보는 제거 (단순화)
        
        return extra_vars
