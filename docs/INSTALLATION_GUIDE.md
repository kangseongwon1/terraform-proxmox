# 🚀 설치 가이드 (보안 강화 버전)

## 📋 개요

이 가이드는 Proxmox 서버 자동 생성 시스템의 보안 강화된 설치 방법을 설명합니다. **모든 민감한 정보는 .env 파일에서 관리**되며, 설치 스크립트에는 절대 하드코딩되지 않습니다.

## 🔒 보안 강화 특징

- ✅ **민감정보 분리**: 모든 비밀번호, 토큰은 .env 파일에서 관리
- ✅ **Vault 연동**: HashiCorp Vault를 통한 중앙화된 시크릿 관리
- ✅ **환경변수 기반**: 설치 스크립트가 .env 변수를 참조
- ✅ **자동화된 설정**: 한 번의 스크립트 실행으로 모든 구성 요소 설치

## 📦 설치 옵션

### 1. **기본 설치** (Flask + Terraform + Ansible)
```bash
./setup.sh
```

### 2. **전체 설치** (모니터링 시스템 포함)
```bash
./install_all.sh
```

### 3. **Vault만 설정**
```bash
./vault_setup.sh
```

## 🛠️ 설치 전 준비

### 1. **환경변수 파일 설정**
```bash
# 환경변수 템플릿 복사
cp env_template.txt .env

# .env 파일 편집
nano .env
```

### 2. **필수 환경변수 설정**
```bash
# Proxmox 설정 (필수)
PROXMOX_ENDPOINT=https://your-proxmox-server:8006
PROXMOX_USERNAME=root@pam
PROXMOX_PASSWORD=your-proxmox-password
PROXMOX_NODE=your-node-name

# VM 설정 (필수)
VM_USERNAME=rocky
VM_PASSWORD=your-vm-password

# Vault 설정 (선택사항)
USE_VAULT=true
VAULT_ADDR=http://127.0.0.1:8200
VAULT_TOKEN=your-vault-token

# 모니터링 설정 (선택사항)
GRAFANA_URL=http://localhost:3000
GRAFANA_USERNAME=admin
GRAFANA_PASSWORD=your-grafana-password
PROMETHEUS_URL=http://localhost:9090

# Ansible 설정 (통합 관리)
ANSIBLE_MYSQL_ROOT_PASSWORD=your_secure_mysql_root_password
ANSIBLE_MYSQL_USER_PASSWORD=your_secure_mysql_user_password
ANSIBLE_FTP_PASSWORD=your_secure_ftp_password
ANSIBLE_TOMCAT_MANAGER_PASSWORD=your_secure_tomcat_manager_password
NODE_EXPORTER_AUTO_INSTALL=true
rol```

## 🚀 설치 과정

### **1단계: 기본 설치**
```bash
# 실행 권한 설정 (Linux/Unix)
chmod +x setup.sh

# 기본 설치 실행
./setup.sh
```

**설치되는 구성 요소:**
- Python 3 + pip
- Flask 애플리케이션
- Terraform
- Ansible
- Python 가상환경
- SSH 키 생성
- 데이터베이스 초기화

### **2단계: 전체 설치 (모니터링 포함)**
```bash
# 실행 권한 설정 (Linux/Unix)
chmod +x install_all.sh

# 전체 설치 실행
./install_all.sh
```

**추가로 설치되는 구성 요소:**
- HashiCorp Vault
- Grafana
- Prometheus
- Node Exporter
- Docker
- Node.js

### **3단계: Vault 설정 (선택사항)**
```bash
# 실행 권한 설정 (Linux/Unix)
chmod +x vault_setup.sh

# Vault 설정 실행
./vault_setup.sh
```

**Vault에 저장되는 시크릿:**
- `secret/proxmox` - Proxmox 자격증명
- `secret/vm` - VM 자격증명
- `secret/mysql` - MySQL 자격증명
- `secret/ftp` - FTP 자격증명
- `secret/grafana` - Grafana 자격증명
- `secret/prometheus` - Prometheus 자격증명

## 🔧 설치 후 설정

### 1. **SSH 키 등록**
```bash
# 공개키 확인
cat ~/.ssh/id_rsa.pub

# Proxmox 웹 UI에서 등록
# Datacenter → SSH Keys → Add
```

### 2. **Flask 애플리케이션 시작**
```bash
# 가상환경 활성화
source venv/bin/activate

# Flask 애플리케이션 시작
python run.py
```

### 3. **웹 접속**
- **Flask 애플리케이션**: http://localhost:5000
- **Grafana**: http://localhost:3000
- **Prometheus**: http://localhost:9090
- **Vault**: http://localhost:8200

## 🔒 보안 설정

### 1. **Vault 사용 시**
```bash
# Vault 환경변수 설정
export VAULT_ADDR='http://127.0.0.1:8200'
export VAULT_TOKEN='your-vault-token'

# Terraform에서 Vault 사용
cd terraform
terraform init
terraform plan
terraform apply
```

### 2. **환경변수 보안**
```bash
# .env 파일 권한 설정
chmod 600 .env

# .env 파일을 버전 관리에서 제외
echo ".env" >> .gitignore
```

### 3. **프로덕션 환경 설정**
```bash
# HTTPS 설정
SESSION_COOKIE_SECURE=true

# Vault 프로덕션 설정
VAULT_ADDR=https://your-vault-server:8200
VAULT_TOKEN=your-production-token

# 로그 레벨 조정
LOG_LEVEL=WARNING
```

## 🐛 문제 해결

### 1. **.env 파일 오류**
```bash
# .env 파일 확인
cat .env

# 필수 변수 확인
grep -E "PROXMOX_|VM_" .env
```

### 2. **Vault 연결 오류**
```bash
# Vault 상태 확인
vault status

# Vault 토큰 확인
vault auth -method=token token=your-token
```

### 3. **Terraform 오류**
```bash
# Terraform 초기화
cd terraform
terraform init

# Terraform 상태 확인
terraform state list
```

### 4. **Ansible 오류**
```bash
# Ansible 연결 테스트
ansible all -i ansible/inventory -m ping

# SSH 키 확인
ssh-keygen -l -f ~/.ssh/id_rsa.pub
```

### 5. **Prometheus 권한 오류**
```bash
# 오류 예시
❌ Prometheus 설정 업데이트 실패: [Errno 13] Permission denied: '/etc/prometheus/prometheus.yml'
❌ 설정 파일 쓰기 실패: sudo 권한이 필요합니다: sudo: effective uid is not 0
```

**해결 방법:**

1. **Prometheus 설정 파일 권한 확인:**
```bash
# Prometheus 설정 파일 권한 확인
ls -la /etc/prometheus/prometheus.yml

# prometheus 사용자 확인
id prometheus
```

2. **sudo 권한 설정:**
```bash
# sudo 권한 확인
sudo -l

# 비밀번호 없이 sudo 사용 가능하도록 설정
sudo visudo
# 다음 줄 추가: username ALL=(ALL) NOPASSWD: /bin/mv, /bin/chown

# 또는 더 제한적인 권한 설정
username ALL=(ALL) NOPASSWD: /bin/mv /etc/prometheus/prometheus.yml, /bin/chown prometheus:prometheus /etc/prometheus/prometheus.yml
```

3. **Prometheus 서비스 재시작:**
```bash
sudo systemctl restart prometheus
```

4. **자동 해결:**
시스템이 자동으로 다음 방법으로 권한 문제를 해결합니다:
- sudo 권한 확인
- sudo 실패 시 직접 파일 복사 시도
- 임시 파일 생성 후 안전한 이동

## 📋 설치 체크리스트

### ✅ **기본 설치**
- [ ] .env 파일 설정 완료
- [ ] Python 3 설치 확인
- [ ] Flask 애플리케이션 실행 확인
- [ ] Terraform 초기화 완료
- [ ] Ansible 설치 확인
- [ ] SSH 키 생성 및 등록

### ✅ **전체 설치**
- [ ] Vault 설치 및 설정
- [ ] Grafana 설치 및 접속 확인
- [ ] Prometheus 설치 및 접속 확인
- [ ] Prometheus 권한 설정 (sudo 권한)
- [ ] Node Exporter 설치 확인
- [ ] Docker 설치 확인

### ✅ **보안 설정**
- [ ] .env 파일 권한 설정 (600)
- [ ] Vault 시크릿 저장 확인
- [ ] Terraform Vault 연동 확인
- [ ] 민감한 정보 로그 출력 차단

## 🔄 업데이트

### 1. **시스템 업데이트**
```bash
# 패키지 업데이트
sudo apt update && sudo apt upgrade -y

# Python 패키지 업데이트
source venv/bin/activate
pip install --upgrade -r requirements.txt
```

### 2. **구성 요소 업데이트**
```bash
# Terraform 업데이트
terraform init -upgrade

# Ansible 업데이트
sudo apt update && sudo apt upgrade ansible
```

## 📞 지원

설치 관련 문의사항이 있으시면 다음을 참조하세요:

- **설치 로그**: `install.log` 파일 확인
- **환경변수**: `env_template.txt` 참조
- **보안 가이드**: `SECURITY_GUIDE.md` 참조
- **문제 해결**: `docs/TROUBLESHOOTING.md` 참조

---

**보안이 강화된 설치를 통해 안전하고 효율적인 Proxmox 관리 시스템을 구축하세요!** 🔒🚀
