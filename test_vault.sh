#!/bin/bash

# Vault Docker 테스트 스크립트
# Rocky 8 환경에서 Vault Docker 기능을 테스트합니다.

set -e  # 오류 발생 시 스크립트 중단

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 로그 함수
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 테스트 결과 카운터
TESTS_PASSED=0
TESTS_FAILED=0

# 테스트 함수
run_test() {
    local test_name="$1"
    local test_command="$2"
    
    log_info "테스트 실행: $test_name"
    
    if eval "$test_command"; then
        log_success "✅ $test_name 통과"
        ((TESTS_PASSED++))
    else
        log_error "❌ $test_name 실패"
        ((TESTS_FAILED++))
    fi
    echo ""
}

# 테스트 결과 요약
show_test_summary() {
    echo ""
    log_info "=========================================="
    log_info "테스트 결과 요약"
    log_info "=========================================="
    echo "✅ 통과: $TESTS_PASSED"
    echo "❌ 실패: $TESTS_FAILED"
    echo "📊 총 테스트: $((TESTS_PASSED + TESTS_FAILED))"
    
    if [ $TESTS_FAILED -eq 0 ]; then
        log_success "🎉 모든 테스트 통과!"
    else
        log_error "⚠️  일부 테스트 실패"
    fi
    echo ""
}

# 1. 환경 확인 테스트
test_environment() {
    log_info "🔍 환경 확인 테스트 시작..."
    
    # Docker 설치 확인
    run_test "Docker 설치 확인" "command -v docker"
    
    # Docker 서비스 상태 확인
    run_test "Docker 서비스 실행 확인" "sudo systemctl is-active --quiet docker"
    
    # .env 파일 확인
    run_test ".env 파일 존재 확인" "[ -f .env ]"
    
    # 필수 환경변수 확인
    if [ -f .env ]; then
        source .env
        run_test "PROXMOX_USERNAME 설정 확인" "[ -n \"$PROXMOX_USERNAME\" ]"
        run_test "PROXMOX_PASSWORD 설정 확인" "[ -n \"$PROXMOX_PASSWORD\" ]"
        run_test "VM_USERNAME 설정 확인" "[ -n \"$VM_USERNAME\" ]"
        run_test "VM_PASSWORD 설정 확인" "[ -n \"$VM_PASSWORD\" ]"
    fi
}

# 2. Vault 컨테이너 테스트
test_vault_container() {
    log_info "🐳 Vault 컨테이너 테스트 시작..."
    
    # 기존 Vault 컨테이너 정리
    log_info "기존 Vault 컨테이너 정리 중..."
    docker stop vault 2>/dev/null || true
    docker rm vault 2>/dev/null || true
    docker volume rm vault-data 2>/dev/null || true
    
    # Vault 볼륨 생성
    run_test "Vault 볼륨 생성" "docker volume create vault-data"
    
    # Vault 컨테이너 실행
    run_test "Vault 컨테이너 실행" "docker run -d --name vault --cap-add=IPC_LOCK -p 8200:8200 -v vault-data:/vault/data -e VAULT_DEV_ROOT_TOKEN_ID=root -e VAULT_DEV_LISTEN_ADDRESS=0.0.0.0:8200 vault:latest"
    
    # Vault 초기화 대기
    log_info "Vault 초기화 대기 중..."
    sleep 10
    
    # Vault 상태 확인
    run_test "Vault 컨테이너 실행 상태 확인" "docker ps | grep -q vault"
    
    # Vault 서비스 상태 확인
    run_test "Vault 서비스 상태 확인" "docker exec vault vault status"
}

# 3. Vault 설정 테스트
test_vault_configuration() {
    log_info "⚙️  Vault 설정 테스트 시작..."
    
    # 환경변수 설정
    export VAULT_ADDR="http://127.0.0.1:8200"
    export VAULT_TOKEN="root"
    
    # KV v2 엔진 활성화
    run_test "KV v2 엔진 활성화" "docker exec vault vault secrets enable -path=secret kv-v2"
    
    # 테스트 시크릿 저장
    run_test "테스트 시크릿 저장" "docker exec vault vault kv put secret/test key1=value1 key2=value2"
    
    # 테스트 시크릿 조회
    run_test "테스트 시크릿 조회" "docker exec vault vault kv get secret/test"
    
    # 테스트 시크릿 삭제
    run_test "테스트 시크릿 삭제" "docker exec vault vault kv delete secret/test"
}

# 4. 실제 시크릿 저장 테스트
test_real_secrets() {
    log_info "🔐 실제 시크릿 저장 테스트 시작..."
    
    if [ -f .env ]; then
        source .env
        
        # Proxmox 자격증명 저장
        run_test "Proxmox 자격증명 저장" "docker exec vault vault kv put secret/proxmox username=\"$PROXMOX_USERNAME\" password=\"$PROXMOX_PASSWORD\""
        
        # VM 자격증명 저장
        run_test "VM 자격증명 저장" "docker exec vault vault kv put secret/vm username=\"$VM_USERNAME\" password=\"$VM_PASSWORD\""
        
        # SSH 키 저장 (있는 경우)
        if [ -f ~/.ssh/id_rsa.pub ]; then
            SSH_PUBLIC_KEY=$(cat ~/.ssh/id_rsa.pub)
            run_test "SSH 키 저장" "docker exec vault vault kv put secret/ssh public_key=\"$SSH_PUBLIC_KEY\""
        else
            log_warning "SSH 공개키가 없습니다. SSH 키 테스트 건너뜀"
        fi
        
        # 저장된 시크릿 조회 테스트
        run_test "Proxmox 자격증명 조회" "docker exec vault vault kv get secret/proxmox"
        run_test "VM 자격증명 조회" "docker exec vault vault kv get secret/vm"
        
        if [ -f ~/.ssh/id_rsa.pub ]; then
            run_test "SSH 키 조회" "docker exec vault vault kv get secret/ssh"
        fi
    else
        log_warning ".env 파일이 없습니다. 실제 시크릿 테스트 건너뜀"
    fi
}

# 5. Vault 웹 UI 테스트
test_vault_web_ui() {
    log_info "🌐 Vault 웹 UI 테스트 시작..."
    
    # Vault 웹 UI 접속 테스트
    run_test "Vault 웹 UI 접속 테스트" "curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8200/v1/sys/health | grep -q '200'"
    
    # Vault API 테스트
    run_test "Vault API 테스트" "curl -s -H 'X-Vault-Token: root' http://127.0.0.1:8200/v1/sys/health | grep -q 'initialized'"
}

# 6. 정리 테스트
test_cleanup() {
    log_info "🧹 정리 테스트 시작..."
    
    # Vault 컨테이너 중지
    run_test "Vault 컨테이너 중지" "docker stop vault"
    
    # Vault 컨테이너 제거
    run_test "Vault 컨테이너 제거" "docker rm vault"
    
    # Vault 볼륨 제거
    run_test "Vault 볼륨 제거" "docker volume rm vault-data"
}

# 메인 테스트 실행
main() {
    log_info "🚀 Vault Docker 테스트 시작..."
    echo ""
    
    # 테스트 실행
    test_environment
    test_vault_container
    test_vault_configuration
    test_real_secrets
    test_vault_web_ui
    test_cleanup
    
    # 테스트 결과 요약
    show_test_summary
    
    log_info "테스트 완료!"
}

# 스크립트 실행
main "$@"
