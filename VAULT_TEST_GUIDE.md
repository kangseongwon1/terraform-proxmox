# 🧪 Vault Docker 테스트 가이드

## 📋 개요

이 가이드는 **Vault Docker 기능**을 테스트하는 방법을 설명합니다. Rocky 8 환경에서 Vault가 Docker로 정상 실행되는지 확인합니다.

## 🚀 테스트 준비

### 1. **환경 확인**
```bash
# Rocky 8 환경에서 실행
cat /etc/os-release

# Docker 설치 확인
docker --version

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
# 간단한 Vault Docker 테스트
./quick_vault_test.sh
```

**테스트 내용:**
- ✅ Docker 설치 확인
- ✅ Docker 서비스 상태 확인
- ✅ Vault 컨테이너 실행
- ✅ Vault 상태 확인
- ✅ KV v2 엔진 활성화
- ✅ 테스트 시크릿 저장/조회

### **방법 2: 상세 테스트**
```bash
# 전체 Vault Docker 테스트
./test_vault.sh
```

**테스트 내용:**
- ✅ 환경 확인 테스트
- ✅ Vault 컨테이너 테스트
- ✅ Vault 설정 테스트
- ✅ 실제 시크릿 저장 테스트
- ✅ Vault 웹 UI 테스트
- ✅ 정리 테스트

### **방법 3: 실제 Vault 설정 테스트**
```bash
# 실제 Vault 설정 스크립트 테스트
./vault_setup.sh
```

**테스트 내용:**
- ✅ .env 파일 로드
- ✅ Vault Docker 컨테이너 실행
- ✅ 실제 자격증명 저장
- ✅ Vault 상태 확인

## 🔍 테스트 결과 확인

### **1. Vault 컨테이너 상태**
```bash
# Vault 컨테이너 실행 상태 확인
docker ps | grep vault

# Vault 컨테이너 로그 확인
docker logs vault

# Vault 상태 확인
docker exec vault vault status
```

### **2. Vault 웹 UI 접속**
```bash
# 웹 브라우저에서 접속
http://127.0.0.1:8200

# 토큰: root
```

### **3. Vault API 테스트**
```bash
# Vault API 상태 확인
curl http://127.0.0.1:8200/v1/sys/health

# Vault API 인증 테스트
curl -H "X-Vault-Token: root" http://127.0.0.1:8200/v1/sys/health
```

### **4. 저장된 시크릿 확인**
```bash
# 환경변수 설정
export VAULT_ADDR="http://127.0.0.1:8200"
export VAULT_TOKEN="root"

# 저장된 시크릿 조회
docker exec vault vault kv get secret/proxmox
docker exec vault vault kv get secret/vm
docker exec vault vault kv get secret/ssh
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

### **2. Vault 컨테이너 문제**
```bash
# Vault 컨테이너 로그 확인
docker logs vault

# Vault 컨테이너 재시작
docker restart vault

# Vault 컨테이너 완전 재시작
docker stop vault && docker rm vault
./quick_vault_test.sh
```

### **3. 포트 충돌 문제**
```bash
# 8200 포트 사용 확인
sudo netstat -tlnp | grep 8200

# 포트 사용 프로세스 종료
sudo kill -9 $(sudo lsof -t -i:8200)
```

### **4. 권한 문제**
```bash
# Docker 권한 확인
groups $USER

# Docker 그룹에 사용자 추가
sudo usermod -aG docker $USER

# Docker 서비스 재시작
sudo systemctl restart docker
```

## 📊 테스트 결과 해석

### **✅ 성공적인 테스트 결과**
```
[SUCCESS] Docker 설치됨: Docker version 20.10.21
[SUCCESS] Docker 서비스 실행 중
[SUCCESS] Vault 컨테이너 실행 중
[SUCCESS] Vault 정상 실행 중
[SUCCESS] Vault Docker 테스트 완료!
```

### **❌ 실패한 테스트 결과**
```
[ERROR] Docker가 설치되지 않았습니다!
[ERROR] Docker 서비스가 실행되지 않았습니다!
[ERROR] Vault 실행 실패
```

## 🔄 테스트 후 정리

### **1. Vault 컨테이너 정리**
```bash
# Vault 컨테이너 중지 및 제거
docker stop vault
docker rm vault

# Vault 볼륨 제거
docker volume rm vault-data
```

### **2. 테스트 파일 정리**
```bash
# 테스트용 .env 파일 제거
rm test.env

# 테스트 스크립트 제거 (선택사항)
rm quick_vault_test.sh
rm test_vault.sh
```

## 📋 테스트 체크리스트

### ✅ **기본 테스트**
- [ ] Docker 설치 확인
- [ ] Docker 서비스 실행 확인
- [ ] Vault 컨테이너 실행 확인
- [ ] Vault 상태 확인
- [ ] KV v2 엔진 활성화 확인
- [ ] 테스트 시크릿 저장/조회 확인

### ✅ **고급 테스트**
- [ ] 실제 자격증명 저장 확인
- [ ] Vault 웹 UI 접속 확인
- [ ] Vault API 테스트 확인
- [ ] SSH 키 저장 확인 (있는 경우)

### ✅ **정리 테스트**
- [ ] Vault 컨테이너 중지 확인
- [ ] Vault 컨테이너 제거 확인
- [ ] Vault 볼륨 제거 확인

## 🎯 다음 단계

테스트가 성공적으로 완료되면:

1. **실제 환경변수 설정**: `test.env`를 참고하여 실제 `.env` 파일 생성
2. **Vault 설정**: `./vault_setup.sh` 실행하여 실제 자격증명 저장
3. **Terraform 연동**: Vault와 Terraform 연동 테스트
4. **전체 시스템 테스트**: `./install_all.sh` 실행

---

**Vault Docker 테스트를 통해 안전하고 효율적인 시크릿 관리 시스템을 검증하세요!** 🧪🔒
