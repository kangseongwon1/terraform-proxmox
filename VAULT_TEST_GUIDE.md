# 🧪 Vault Docker Compose 테스트 가이드

## 📋 개요

이 가이드는 **Vault Docker Compose 기능**을 테스트하는 방법을 설명합니다. Rocky 8 환경에서 Vault가 Docker Compose로 정상 실행되는지 확인합니다.

## 🚀 테스트 준비

### 1. **환경 확인**
```bash
# Rocky 8 환경에서 실행
cat /etc/os-release

# Docker 설치 확인
docker --version

# Docker Compose 설치 확인
docker-compose --version

# Docker 서비스 상태 확인
sudo systemctl status docker
```

### 2. **테스트 파일 준비**
```bash
# 테스트용 .env 파일 복사
cp test.env .env

# 실행 권한 설정
chmod +x quick_vault_test.sh
chmod +x test_vault.sh
chmod +x vault_setup.sh
```

## 🧪 테스트 실행

### **방법 1: 빠른 테스트 (권장)**
```bash
# 간단한 Vault Docker Compose 테스트
./quick_vault_test.sh
```

**테스트 내용:**
- ✅ Docker 및 Docker Compose 설치 확인
- ✅ Docker 서비스 상태 확인
- ✅ Vault 설정 파일 확인
- ✅ Vault Docker Compose 실행
- ✅ Vault 초기화 및 언실
- ✅ KV v2 엔진 활성화
- ✅ 테스트 시크릿 저장/조회

### **방법 2: 실제 Vault 설정 테스트**
```bash
# 실제 Vault 설정 스크립트 테스트
./vault_setup.sh
```

**테스트 내용:**
- ✅ .env 파일 로드
- ✅ Vault Docker Compose 실행
- ✅ Vault 초기화 및 언실
- ✅ 실제 자격증명 저장
- ✅ Vault 상태 확인

### **방법 3: 수동 Docker Compose 테스트**
```bash
# Docker Compose로 Vault 실행
docker-compose -f docker-compose.vault.yml up -d

# Vault 상태 확인
docker exec vault-dev vault status

# Vault 초기화 (최초 1회)
docker exec vault-dev vault operator init -key-shares=1 -key-threshold=1

# Unseal 키로 언실
docker exec vault-dev vault operator unseal <UNSEAL_KEY>

# Root 토큰으로 로그인
docker exec vault-dev vault auth <ROOT_TOKEN>
```

## 🔍 테스트 결과 확인

### **1. Vault 컨테이너 상태**
```bash
# Vault 컨테이너 실행 상태 확인
docker ps | grep vault-dev

# Vault 컨테이너 로그 확인
docker logs vault-dev

# Vault 상태 확인
docker exec vault-dev vault status
```

### **2. Vault 웹 UI 접속**
```bash
# 웹 브라우저에서 접속
http://127.0.0.1:8200

# 토큰: vault_init.txt 파일에서 확인
cat vault_init.txt | grep "Root Token"
```

### **3. Vault API 테스트**
```bash
# Vault API 상태 확인
curl http://127.0.0.1:8200/v1/sys/health

# Vault API 인증 테스트
curl -H "X-Vault-Token: <ROOT_TOKEN>" http://127.0.0.1:8200/v1/sys/health
```

### **4. 저장된 시크릿 확인**
```bash
# 환경변수 설정
export VAULT_ADDR="http://127.0.0.1:8200"
export VAULT_TOKEN="<ROOT_TOKEN>"

# 저장된 시크릿 조회
docker exec vault-dev vault kv get secret/proxmox
docker exec vault-dev vault kv get secret/vm
docker exec vault-dev vault kv get secret/ssh
```

## 🐛 문제 해결

### **1. Docker 관련 문제**
```bash
# Docker 서비스 시작
sudo systemctl start docker

# Docker 그룹에 사용자 추가
sudo usermod -aG docker $USER

# 로그아웃 후 다시 로그인
```

### **2. Docker Compose 관련 문제**
```bash
# Docker Compose 설치
sudo dnf install -y docker-compose

# 또는 최신 버전 설치
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

### **3. Vault 컨테이너 문제**
```bash
# Vault 컨테이너 로그 확인
docker logs vault-dev

# Vault 컨테이너 재시작
docker-compose -f docker-compose.vault.yml restart

# Vault 컨테이너 완전 재시작
docker-compose -f docker-compose.vault.yml down
docker-compose -f docker-compose.vault.yml up -d
```

### **4. Vault 초기화 문제**
```bash
# Vault 초기화 상태 확인
docker exec vault-dev vault status

# Vault 재초기화 (주의: 기존 데이터 삭제됨)
docker-compose -f docker-compose.vault.yml down
rm -rf vault-data
docker-compose -f docker-compose.vault.yml up -d
```

### **5. 포트 충돌 문제**
```bash
# 8200 포트 사용 확인
sudo netstat -tlnp | grep 8200

# 포트 사용 프로세스 종료
sudo kill -9 $(sudo lsof -t -i:8200)
```

## 📊 테스트 결과 해석

### **✅ 성공적인 테스트 결과**
```
[SUCCESS] Docker 설치됨: Docker version 20.10.21
[SUCCESS] Docker Compose 설치됨: docker-compose version 1.29.2
[SUCCESS] Docker 서비스 실행 중
[SUCCESS] vault-dev.hcl 파일 존재
[SUCCESS] docker-compose.vault.yml 파일 존재
[SUCCESS] Vault 정상 실행 중
[SUCCESS] Vault 초기화 및 언실 완료
[SUCCESS] Vault Docker Compose 테스트 완료!
```

### **❌ 실패한 테스트 결과**
```
[ERROR] Docker가 설치되지 않았습니다!
[ERROR] Docker Compose가 설치되지 않았습니다!
[ERROR] Docker 서비스가 실행되지 않았습니다!
[ERROR] vault-dev.hcl 파일이 없습니다!
[ERROR] Vault 실행 실패
```

## 🔄 테스트 후 정리

### **1. Vault 컨테이너 정리**
```bash
# Vault Docker Compose 서비스 중지
docker-compose -f docker-compose.vault.yml down

# Vault 데이터 디렉토리 제거 (선택사항)
rm -rf vault-data
```

### **2. 테스트 파일 정리**
```bash
# 테스트용 .env 파일 제거
rm test.env

# Vault 초기화 파일 제거 (선택사항)
rm vault_init.txt

# 테스트 스크립트 제거 (선택사항)
rm quick_vault_test.sh
rm test_vault.sh
```

## 📋 테스트 체크리스트

### ✅ **기본 테스트**
- [ ] Docker 설치 확인
- [ ] Docker Compose 설치 확인
- [ ] Docker 서비스 실행 확인
- [ ] Vault 설정 파일 확인
- [ ] Vault Docker Compose 실행 확인
- [ ] Vault 초기화 및 언실 확인
- [ ] KV v2 엔진 활성화 확인
- [ ] 테스트 시크릿 저장/조회 확인

### ✅ **고급 테스트**
- [ ] 실제 자격증명 저장 확인
- [ ] Vault 웹 UI 접속 확인
- [ ] Vault API 테스트 확인
- [ ] SSH 키 저장 확인 (있는 경우)

### ✅ **정리 테스트**
- [ ] Vault Docker Compose 서비스 중지 확인
- [ ] Vault 데이터 디렉토리 정리 확인

## 🎯 다음 단계

테스트가 성공적으로 완료되면:

1. **실제 환경변수 설정**: `test.env`를 참고하여 실제 `.env` 파일 생성
2. **Vault 설정**: `./vault_setup.sh` 실행하여 실제 자격증명 저장
3. **Terraform 연동**: Vault와 Terraform 연동 테스트
4. **전체 시스템 테스트**: `./install_all.sh` 실행

## 🔧 Docker Compose 관리 명령어

### **서비스 관리**
```bash
# 서비스 시작
docker-compose -f docker-compose.vault.yml up -d

# 서비스 중지
docker-compose -f docker-compose.vault.yml down

# 서비스 재시작
docker-compose -f docker-compose.vault.yml restart

# 서비스 상태 확인
docker-compose -f docker-compose.vault.yml ps
```

### **로그 확인**
```bash
# 서비스 로그 확인
docker-compose -f docker-compose.vault.yml logs

# 실시간 로그 확인
docker-compose -f docker-compose.vault.yml logs -f
```

---

**Vault Docker Compose 테스트를 통해 안전하고 효율적인 시크릿 관리 시스템을 검증하세요!** 🧪🔒🐳