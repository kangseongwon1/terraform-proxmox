# 🚀 Vault 통합 가이드

## 📋 개요

**`vault.sh`** 스크립트 하나로 모든 Vault 관련 작업을 처리합니다:
- ✅ Docker 및 Docker Compose 확인
- ✅ .env 파일 로드
- ✅ 기존 Vault 컨테이너 정리
- ✅ Vault Docker Compose 실행
- ✅ Vault 초기화 및 언실
- ✅ Vault 설정 (KV v2, 시크릿 저장)
- ✅ 환경변수 설정
- ✅ Terraform 테스트

## 🚀 사용 방법

### **1단계: 환경 준비**
```bash
# .env 파일 준비
cp test.env .env
nano .env  # 실제 값으로 수정
```

### **2단계: 통합 스크립트 실행**
```bash
# 실행 권한 설정
chmod +x vault.sh

# 통합 스크립트 실행
./vault.sh
```

## 🔍 실행 결과

### **성공적인 실행:**
```
[SUCCESS] Docker 및 Docker Compose 확인 완료
[SUCCESS] .env 파일 로드 완료
[SUCCESS] 기존 Vault 컨테이너 정리 완료
[SUCCESS] Vault 컨테이너 시작 완료
[SUCCESS] Vault 초기화 및 언실 완료
[SUCCESS] Vault 설정 완료
[SUCCESS] 환경변수 설정 완료
[SUCCESS] Terraform 테스트 완료
[SUCCESS] 통합 Vault 스크립트 완료!
```

### **Terraform 성공 결과:**
```
Terraform will perform the following actions:

  # data.vault_generic_secret.proxmox will be read during apply
  <= data "vault_generic_secret" "proxmox" {
      + data = (sensitive value)
      + data_json = (sensitive value)
      + id       = "secret/proxmox"
      + path     = "secret/proxmox"
    }

  # data.vault_generic_secret.vm will be read during apply
  <= data "vault_generic_secret" "vm" {
      + data = (sensitive value)
      + data_json = (sensitive value)
      + id       = "secret/vm"
      + path     = "secret/vm"
    }

Plan: 0 to add, 0 to change, 0 to destroy.
```

## 🔧 관리 명령어

### **Vault 관리:**
```bash
# Vault 상태 확인
docker exec vault-dev vault status

# 시크릿 조회
docker exec vault-dev vault kv get secret/proxmox
docker exec vault-dev vault kv get secret/vm

# 시크릿 목록
docker exec vault-dev vault kv list secret/
```

### **Docker Compose 관리:**
```bash
# 서비스 중지
docker-compose -f docker-compose.vault.yml down

# 서비스 시작
docker-compose -f docker-compose.vault.yml up -d

# 서비스 재시작
docker-compose -f docker-compose.vault.yml restart
```

### **Terraform 사용:**
```bash
# 환경변수 설정
export VAULT_ADDR="http://127.0.0.1:8200"
export VAULT_TOKEN="$(grep 'Root Token:' vault_init.txt | awk '{print $NF}')"

# Terraform 실행
cd terraform
terraform plan
terraform apply
```

## 🌐 웹 UI 접속

- **주소**: http://127.0.0.1:8200
- **토큰**: `vault_init.txt` 파일에서 확인

## 📁 중요 파일

- **`vault.sh`**: 통합 Vault 스크립트
- **`vault_init.txt`**: 초기화 정보 (안전하게 보관)
- **`vault-dev.hcl`**: Vault 설정 파일
- **`docker-compose.vault.yml`**: Docker Compose 설정
- **`terraform/terraform.tfvars.json`**: Terraform 변수 파일

## 🐛 문제 해결

### **Docker 관련 문제:**
```bash
# Docker 서비스 시작
sudo systemctl start docker

# Docker 그룹에 사용자 추가
sudo usermod -aG docker $USER
```

### **Vault 관련 문제:**
```bash
# Vault 컨테이너 로그 확인
docker logs vault-dev

# Vault 컨테이너 재시작
docker-compose -f docker-compose.vault.yml restart
```

### **Terraform 관련 문제:**
```bash
# 환경변수 확인
echo $VAULT_ADDR
echo $VAULT_TOKEN

# Terraform 초기화
cd terraform
terraform init
```

## 🎯 다음 단계

Vault 설정이 완료되면:

1. **실제 서버 생성**: `terraform apply`
2. **Ansible 연동**: 서버 생성 후 Ansible로 설정
3. **모니터링 설정**: Grafana, Prometheus 연동
4. **전체 시스템 테스트**: 모든 구성 요소 통합 테스트

---

**하나의 스크립트로 모든 Vault 작업을 완료하세요!** 🚀🔒
