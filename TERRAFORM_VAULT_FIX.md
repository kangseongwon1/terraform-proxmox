# 🔧 Terraform Vault 토큰 문제 해결 가이드

## 📋 문제 상황
```
terraform plan
var.vault_token
  Vault token for authentication

  Enter a value:
```

## 🚀 해결 방법

### **방법 1: 자동 설정 스크립트 사용 (권장)**
```bash
# 실행 권한 설정
chmod +x set_vault_env.sh

# 자동 설정 및 테스트
./set_vault_env.sh
```

### **방법 2: 수동 환경변수 설정**
```bash
# 1. Root 토큰 추출
ROOT_TOKEN=$(grep 'Root Token:' vault_init.txt | awk '{print $NF}')

# 2. 환경변수 설정
export VAULT_ADDR="http://127.0.0.1:8200"
export VAULT_TOKEN="$ROOT_TOKEN"

# 3. Terraform 디렉토리로 이동
cd terraform

# 4. terraform.tfvars.json 업데이트
sed -i "s/\"vault_token\": \".*\"/\"vault_token\": \"$ROOT_TOKEN\"/" terraform.tfvars.json

# 5. Terraform 계획 실행
terraform plan
```

### **방법 3: terraform.tfvars.json 직접 수정**
```bash
# 1. Root 토큰 확인
cat vault_init.txt | grep "Root Token"

# 2. terraform/terraform.tfvars.json 파일 편집
nano terraform/terraform.tfvars.json

# 3. vault_token 값을 실제 토큰으로 변경
# "vault_token": "hvs.ECxycbZdCCskJeaGAW77rbfL"

# 4. Terraform 계획 실행
cd terraform
terraform plan
```

### **방법 4: 환경변수로 직접 전달**
```bash
# 1. Root 토큰 추출
ROOT_TOKEN=$(grep 'Root Token:' vault_init.txt | awk '{print $NF}')

# 2. 환경변수 설정
export VAULT_ADDR="http://127.0.0.1:8200"
export VAULT_TOKEN="$ROOT_TOKEN"

# 3. Terraform 계획 실행
cd terraform
terraform plan
```

## 🔍 문제 원인

1. **Terraform이 Vault에 접근할 때 토큰이 필요**
2. **terraform.tfvars.json에 토큰이 설정되지 않음**
3. **환경변수로 토큰이 전달되지 않음**

## ✅ 해결 확인

### **성공적인 결과:**
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

### **실패한 결과:**
```
Error: failed to read secret from Vault: error reading secret from Vault: 
Error making API request.

URL: GET http://127.0.0.1:8200/v1/secret/proxmox
Code: 403. Errors:

* permission denied
```

## 🐛 문제 해결

### **1. 토큰 권한 문제**
```bash
# Vault 토큰 확인
docker exec vault-dev vault token lookup

# Vault 정책 확인
docker exec vault-dev vault policy list
```

### **2. Vault 연결 문제**
```bash
# Vault 상태 확인
docker exec vault-dev vault status

# Vault 연결 테스트
curl -H "X-Vault-Token: $ROOT_TOKEN" http://127.0.0.1:8200/v1/sys/health
```

### **3. 시크릿 경로 문제**
```bash
# 시크릿 목록 확인
docker exec vault-dev vault kv list secret/

# 시크릿 조회 테스트
docker exec vault-dev vault kv get secret/proxmox
```

## 📋 체크리스트

### ✅ **해결 전 확인사항**
- [ ] Vault가 실행 중인가?
- [ ] vault_init.txt 파일이 있는가?
- [ ] Root 토큰이 유효한가?
- [ ] 시크릿이 저장되어 있는가?

### ✅ **해결 후 확인사항**
- [ ] terraform.tfvars.json에 토큰이 설정되었는가?
- [ ] 환경변수가 올바르게 설정되었는가?
- [ ] Terraform이 Vault에 연결되는가?
- [ ] 시크릿을 성공적으로 읽는가?

## 🎯 다음 단계

Terraform Vault 연동이 성공하면:

1. **실제 서버 생성**: `terraform apply`
2. **Ansible 연동**: 서버 생성 후 Ansible로 설정
3. **모니터링 설정**: Grafana, Prometheus 연동
4. **전체 시스템 테스트**: 모든 구성 요소 통합 테스트

---

**Terraform Vault 연동 문제를 해결하고 안전한 인프라 관리를 시작하세요!** 🔧🔒
