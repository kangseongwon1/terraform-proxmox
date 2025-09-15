# 🐧 Rocky 8 설치 가이드

## 📋 개요

이 가이드는 **Rocky 8 (RedHat 계열)** 환경에서 Proxmox 서버 자동 생성 시스템을 설치하는 방법을 설명합니다. **Docker 기반 Vault**와 **dnf 패키지 매니저**를 사용합니다.

## 🔧 Rocky 8 환경 준비

### 1. **시스템 업데이트**
```bash
# Rocky 8 시스템 업데이트
sudo dnf update -y

# EPEL 저장소 활성화
sudo dnf install -y epel-release

# 개발 도구 설치
sudo dnf groupinstall -y "Development Tools"
```

### 2. **Docker 설치**
```bash
# Docker 설치
sudo dnf install -y docker

# Docker 서비스 시작 및 활성화
sudo systemctl enable docker
sudo systemctl start docker

# 사용자를 docker 그룹에 추가
sudo usermod -aG docker $USER

# 로그아웃 후 다시 로그인 (그룹 변경사항 적용)
```

### 3. **Docker Compose 설치**
```bash
# Docker Compose 설치
sudo dnf install -y docker-compose

# 또는 최신 버전 설치
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

## 🚀 설치 과정

### **1단계: 환경변수 설정**
```bash
# 환경변수 템플릿 복사
cp env_template.txt .env

# .env 파일 편집
nano .env
```

**필수 환경변수 설정:**
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
VAULT_TOKEN=root
```

### **2단계: 기본 설치**
```bash
# 실행 권한 설정
chmod +x setup.sh

# 기본 설치 실행
./setup.sh
```

**설치되는 구성 요소:**
- Python 3 + pip (dnf로 설치)
- Flask 애플리케이션
- Terraform (HashiCorp 저장소에서 설치)
- Ansible (dnf로 설치)
- Python 가상환경
- SSH 키 생성
- 데이터베이스 초기화

### **3단계: Vault Docker 설정**
```bash
# 실행 권한 설정
chmod +x vault_setup.sh

# Vault Docker 설정 실행
./vault_setup.sh
```

**Vault Docker 특징:**
- **컨테이너 기반**: Docker로 Vault 실행
- **볼륨 마운트**: 데이터 영속성 보장
- **자동 설정**: .env 변수를 Vault에 자동 저장
- **간소화된 시크릿**: proxmox_password, vm_password, ssh_key만 저장

### **4단계: 전체 설치 (모니터링 포함)**
```bash
# 실행 권한 설정
chmod +x install_all.sh

# 전체 설치 실행
./install_all.sh
```

**추가로 설치되는 구성 요소:**
- Grafana (RPM 패키지로 설치)
- Prometheus (바이너리로 설치)
- Node Exporter (바이너리로 설치)
- Node.js (NodeSource 저장소에서 설치)

## 🔒 Vault Docker 관리

### **1. Vault 컨테이너 상태 확인**
```bash
# Vault 컨테이너 상태 확인
docker ps | grep vault

# Vault 로그 확인
docker logs vault

# Vault 상태 확인
docker exec vault vault status
```

### **2. Vault 시크릿 관리**
```bash
# 시크릿 조회
docker exec vault vault kv get secret/proxmox
docker exec vault vault kv get secret/vm
docker exec vault vault kv get secret/ssh

# 시크릿 업데이트
docker exec vault vault kv put secret/proxmox username="new_user" password="new_pass"
```

### **3. Vault 컨테이너 관리**
```bash
# Vault 컨테이너 중지
docker stop vault

# Vault 컨테이너 시작
docker start vault

# Vault 컨테이너 재시작
docker restart vault

# Vault 컨테이너 제거
docker stop vault && docker rm vault
```

### **4. Docker Compose 사용**
```bash
# Docker Compose로 Vault 실행
docker-compose -f docker-compose.vault.yml up -d

# Docker Compose로 Vault 중지
docker-compose -f docker-compose.vault.yml down

# Docker Compose로 Vault 재시작
docker-compose -f docker-compose.vault.yml restart
```

## 🐛 Rocky 8 특화 문제 해결

### 1. **SELinux 관련 문제**
```bash
# SELinux 상태 확인
sestatus

# SELinux 비활성화 (필요시)
sudo setenforce 0

# 영구적으로 비활성화
sudo sed -i 's/SELINUX=enforcing/SELINUX=disabled/' /etc/selinux/config
```

### 2. **Firewall 설정**
```bash
# Firewall 상태 확인
sudo firewall-cmd --state

# 필요한 포트 열기
sudo firewall-cmd --permanent --add-port=5000/tcp  # Flask
sudo firewall-cmd --permanent --add-port=8200/tcp  # Vault
sudo firewall-cmd --permanent --add-port=3000/tcp  # Grafana
sudo firewall-cmd --permanent --add-port=9090/tcp  # Prometheus
sudo firewall-cmd --permanent --add-port=9100/tcp  # Node Exporter

# Firewall 재시작
sudo firewall-cmd --reload
```

### 3. **Docker 권한 문제**
```bash
# Docker 그룹 확인
groups $USER

# Docker 그룹에 사용자 추가
sudo usermod -aG docker $USER

# Docker 서비스 재시작
sudo systemctl restart docker
```

### 4. **패키지 설치 문제**
```bash
# 저장소 캐시 정리
sudo dnf clean all

# 저장소 메타데이터 새로고침
sudo dnf makecache

# 패키지 의존성 해결
sudo dnf install -y --resolve
```

## 📋 Rocky 8 설치 체크리스트

### ✅ **시스템 준비**
- [ ] Rocky 8 시스템 업데이트 완료
- [ ] EPEL 저장소 활성화
- [ ] Docker 설치 및 서비스 시작
- [ ] Docker Compose 설치
- [ ] 사용자를 docker 그룹에 추가

### ✅ **기본 설치**
- [ ] .env 파일 설정 완료
- [ ] Python 3 설치 확인 (dnf)
- [ ] Flask 애플리케이션 실행 확인
- [ ] Terraform 설치 확인 (HashiCorp 저장소)
- [ ] Ansible 설치 확인 (dnf)
- [ ] SSH 키 생성 및 등록

### ✅ **Vault Docker**
- [ ] Vault Docker 컨테이너 실행 확인
- [ ] Vault 시크릿 저장 확인
- [ ] Vault 웹 UI 접속 확인
- [ ] Terraform Vault 연동 확인

### ✅ **전체 설치**
- [ ] Grafana 설치 및 접속 확인
- [ ] Prometheus 설치 및 접속 확인
- [ ] Node Exporter 설치 확인
- [ ] Node.js 설치 확인

## 🔄 업데이트

### 1. **시스템 업데이트**
```bash
# Rocky 8 패키지 업데이트
sudo dnf update -y

# Python 패키지 업데이트
source venv/bin/activate
pip install --upgrade -r requirements.txt
```

### 2. **Docker 이미지 업데이트**
```bash
# Vault 이미지 업데이트
docker pull vault:latest

# 기존 컨테이너 재시작
docker stop vault && docker rm vault
./vault_setup.sh
```

## 📞 지원

Rocky 8 설치 관련 문의사항이 있으시면 다음을 참조하세요:

- **설치 로그**: `install.log` 파일 확인
- **Docker 로그**: `docker logs vault` 명령어 사용
- **시스템 로그**: `journalctl -u docker` 명령어 사용
- **문제 해결**: `docs/TROUBLESHOOTING.md` 참조

---

**Rocky 8 환경에서 Docker 기반 Vault를 사용한 안전하고 효율적인 Proxmox 관리 시스템을 구축하세요!** 🐧🐳🔒
