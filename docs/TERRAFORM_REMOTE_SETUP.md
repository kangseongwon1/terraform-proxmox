# Terraform 원격 서버 설정 가이드

## 📋 개요

Terraform을 별도 서버에서 실행하도록 설정하는 방법을 설명합니다.

## 🔧 설정 방법

### 1. 환경 변수 설정

#### 로컬 실행 (기본값)
```bash
# .env 파일에 설정하지 않으면 로컬 실행
# 별도 설정 불필요
```

#### 원격 서버 실행
```bash
# .env 파일에 추가
TERRAFORM_REMOTE_ENABLED=true
TERRAFORM_REMOTE_HOST=terraform-server.example.com
TERRAFORM_REMOTE_PORT=22
TERRAFORM_REMOTE_USERNAME=terraform
TERRAFORM_REMOTE_PASSWORD=your_password
TERRAFORM_REMOTE_KEY_FILE=/path/to/private/key
TERRAFORM_REMOTE_DIR=/opt/terraform
```

### 2. 원격 서버 준비

#### A. Terraform 서버 설정
```bash
# 원격 서버에 terraform 설치
wget https://releases.hashicorp.com/terraform/1.5.7/terraform_1.5.7_linux_amd64.zip
unzip terraform_1.5.7_linux_amd64.zip
sudo mv terraform /usr/local/bin/
sudo chmod +x /usr/local/bin/terraform

# terraform 디렉토리 생성
sudo mkdir -p /opt/terraform
sudo chown terraform:terraform /opt/terraform
```

#### B. SSH 키 설정 (선택사항)
```bash
# SSH 키 생성
ssh-keygen -t rsa -b 4096 -f ~/.ssh/terraform_key

# 공개키를 원격 서버에 복사
ssh-copy-id -i ~/.ssh/terraform_key.pub terraform@terraform-server.example.com
```

### 3. 코드에서 사용

#### A. 기본 사용 (로컬)
```python
# app/tasks/server_tasks.py
terraform_service = TerraformService()  # 로컬 실행
```

#### B. 원격 서버 사용
```python
# app/tasks/server_tasks.py
import os

# 환경 변수에서 원격 서버 설정 읽기
remote_config = None
if os.getenv('TERRAFORM_REMOTE_ENABLED', 'false').lower() == 'true':
    remote_config = {
        'host': os.getenv('TERRAFORM_REMOTE_HOST'),
        'port': int(os.getenv('TERRAFORM_REMOTE_PORT', 22)),
        'username': os.getenv('TERRAFORM_REMOTE_USERNAME'),
        'password': os.getenv('TERRAFORM_REMOTE_PASSWORD'),
        'key_file': os.getenv('TERRAFORM_REMOTE_KEY_FILE'),
        'terraform_dir': os.getenv('TERRAFORM_REMOTE_DIR', '/opt/terraform')
    }

terraform_service = TerraformService(remote_server=remote_config)
```

## 🔄 마이그레이션 전략

### 1단계: 로컬에서 테스트
```bash
# 기본 설정으로 로컬 실행
python run.py
```

### 2단계: 원격 서버 설정
```bash
# .env 파일에 원격 서버 설정 추가
TERRAFORM_REMOTE_ENABLED=true
TERRAFORM_REMOTE_HOST=terraform-server.example.com
# ... 기타 설정
```

### 3단계: 점진적 전환
```python
# 코드에서 환경 변수 확인 후 자동 전환
if os.getenv('TERRAFORM_REMOTE_ENABLED', 'false').lower() == 'true':
    # 원격 서버 사용
    terraform_service = TerraformService(remote_server=remote_config)
else:
    # 로컬 사용
    terraform_service = TerraformService()
```

## 🛠️ 문제 해결

### 1. SSH 연결 실패
```bash
# SSH 연결 테스트
ssh -i /path/to/private/key terraform@terraform-server.example.com

# SSH 설정 확인
ssh -v -i /path/to/private/key terraform@terraform-server.example.com
```

### 2. 원격 서버에서 terraform 명령어를 찾을 수 없는 경우
```bash
# 원격 서버에 terraform 설치 확인
ssh terraform@terraform-server.example.com "which terraform"

# PATH 설정 확인
ssh terraform@terraform-server.example.com "echo $PATH"
```

### 3. 권한 문제
```bash
# 원격 서버에서 terraform 디렉토리 권한 확인
ssh terraform@terraform-server.example.com "ls -la /opt/terraform"

# 권한 수정
ssh terraform@terraform-server.example.com "sudo chown -R terraform:terraform /opt/terraform"
```

## 📊 모니터링

### 1. 원격 서버 상태 확인
```bash
# SSH 연결 상태 확인
ssh terraform@terraform-server.example.com "uptime"

# Terraform 버전 확인
ssh terraform@terraform-server.example.com "terraform --version"
```

### 2. 로그 확인
```bash
# Celery 워커 로그에서 원격 실행 확인
docker logs proxmox-celery-worker | grep "원격 Terraform"
```

## 🔒 보안 고려사항

### 1. SSH 키 관리
- SSH 키 파일 권한: `600`
- SSH 키 파일 위치: 안전한 디렉토리
- 정기적인 키 로테이션

### 2. 네트워크 보안
- 방화벽 설정으로 SSH 포트 제한
- VPN 또는 사설 네트워크 사용 권장
- SSH 키 기반 인증 사용

### 3. 원격 서버 보안
- 정기적인 보안 업데이트
- 불필요한 서비스 비활성화
- 로그 모니터링

## 📝 설정 예시

### .env 파일 예시
```bash
# 기본 설정
PROXMOX_ENDPOINT=https://proxmox.example.com:8006
PROXMOX_USERNAME=user@pam
PROXMOX_PASSWORD=password
PROXMOX_NODE=proxmox-node

# Redis & Celery
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=your_password
REDIS_ENABLED=true

# Terraform 원격 서버 설정 (선택사항)
TERRAFORM_REMOTE_ENABLED=false
# TERRAFORM_REMOTE_HOST=terraform-server.example.com
# TERRAFORM_REMOTE_PORT=22
# TERRAFORM_REMOTE_USERNAME=terraform
# TERRAFORM_REMOTE_PASSWORD=your_password
# TERRAFORM_REMOTE_KEY_FILE=/path/to/private/key
# TERRAFORM_REMOTE_DIR=/opt/terraform
```

---

**최종 업데이트**: 2025-09-26
**버전**: 1.0.0
