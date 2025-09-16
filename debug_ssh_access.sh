#!/bin/bash
# SSH 접근 문제 진단 스크립트

echo "🔍 SSH 접근 문제 진단 스크립트"
echo "================================="

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 로그 함수
log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

# 1. Vault에서 SSH 키 확인
echo ""
log_info "1. Vault에서 SSH 키 확인"
echo "------------------------"

if command -v vault >/dev/null 2>&1; then
    log_info "Vault CLI 사용 가능"
    
    # Vault 상태 확인
    if vault status >/dev/null 2>&1; then
        log_success "Vault 연결 성공"
        
        # SSH 키 조회
        log_info "SSH 키 조회 중..."
        SSH_KEY_FROM_VAULT=$(vault kv get -field=public_key secret/ssh 2>/dev/null)
        if [ $? -eq 0 ] && [ -n "$SSH_KEY_FROM_VAULT" ]; then
            log_success "Vault에서 SSH 키 조회 성공"
            echo "SSH 키 (처음 50자): $(echo "$SSH_KEY_FROM_VAULT" | head -c 50)..."
            echo "SSH 키 길이: $(echo "$SSH_KEY_FROM_VAULT" | wc -c) 문자"
        else
            log_error "Vault에서 SSH 키 조회 실패"
        fi
    else
        log_error "Vault 연결 실패"
    fi
else
    log_warning "Vault CLI가 설치되지 않음"
fi

# 2. 로컬 SSH 키 확인
echo ""
log_info "2. 로컬 SSH 키 확인"
echo "-------------------"

LOCAL_SSH_KEY=""
for ssh_path in "$HOME/.ssh/id_rsa.pub" "$HOME/.ssh/id_ed25519.pub" "/root/.ssh/id_rsa.pub" "/root/.ssh/id_ed25519.pub"; do
    if [ -f "$ssh_path" ]; then
        LOCAL_SSH_KEY="$ssh_path"
        log_success "로컬 SSH 키 발견: $LOCAL_SSH_KEY"
        echo "로컬 SSH 키 (처음 50자): $(head -c 50 "$LOCAL_SSH_KEY")..."
        break
    fi
done

if [ -z "$LOCAL_SSH_KEY" ]; then
    log_error "로컬 SSH 키를 찾을 수 없음"
fi

# 3. Vault와 로컬 SSH 키 비교
echo ""
log_info "3. Vault와 로컬 SSH 키 비교"
echo "---------------------------"

if [ -n "$SSH_KEY_FROM_VAULT" ] && [ -n "$LOCAL_SSH_KEY" ]; then
    LOCAL_SSH_CONTENT=$(cat "$LOCAL_SSH_KEY")
    if [ "$SSH_KEY_FROM_VAULT" = "$LOCAL_SSH_CONTENT" ]; then
        log_success "Vault와 로컬 SSH 키가 일치함"
    else
        log_error "Vault와 로컬 SSH 키가 일치하지 않음"
        echo "Vault 키: $(echo "$SSH_KEY_FROM_VAULT" | head -c 50)..."
        echo "로컬 키: $(echo "$LOCAL_SSH_CONTENT" | head -c 50)..."
    fi
else
    log_warning "SSH 키 비교를 위한 데이터가 부족함"
fi

# 4. Terraform 상태 확인
echo ""
log_info "4. Terraform 상태 확인"
echo "----------------------"

if [ -d "terraform" ]; then
    cd terraform || exit 1
    
    # Terraform 초기화 확인
    if [ -d ".terraform" ]; then
        log_success "Terraform 초기화됨"
    else
        log_warning "Terraform이 초기화되지 않음"
    fi
    
    # Terraform 상태 확인
    log_info "Terraform 상태 조회 중..."
    TERRAFORM_OUTPUT=$(terraform show -json 2>/dev/null)
    if [ $? -eq 0 ]; then
        log_success "Terraform 상태 조회 성공"
        
        # 생성된 서버 정보 추출
        SERVERS=$(echo "$TERRAFORM_OUTPUT" | jq -r '.values.root_module.child_modules[]?.resources[]? | select(.type == "proxmox_virtual_environment_vm") | .values.name' 2>/dev/null)
        if [ -n "$SERVERS" ]; then
            log_success "생성된 서버들:"
            echo "$SERVERS"
        else
            log_warning "생성된 서버가 없음"
        fi
    else
        log_error "Terraform 상태 조회 실패"
    fi
    
    cd ..
else
    log_error "terraform 디렉토리를 찾을 수 없음"
fi

# 5. 서버별 SSH 접근 테스트
echo ""
log_info "5. 서버별 SSH 접근 테스트"
echo "------------------------"

# 서버 IP 목록 (실제 환경에 맞게 수정 필요)
SERVER_IPS=("192.168.0.21" "192.168.0.22" "192.168.0.23")

for server_ip in "${SERVER_IPS[@]}"; do
    echo ""
    log_info "서버 $server_ip 테스트 중..."
    
    # 서버 연결성 확인
    if ping -c 1 -W 3 "$server_ip" >/dev/null 2>&1; then
        log_success "서버 $server_ip 연결 가능"
        
        # SSH 포트 확인
        if nc -z -w 3 "$server_ip" 22 >/dev/null 2>&1; then
            log_success "SSH 포트 22 열림"
            
            # SSH 키 인증 테스트
            log_info "SSH 키 인증 테스트 중..."
            SSH_KEY_TEST=$(ssh -o ConnectTimeout=10 -o BatchMode=yes -o StrictHostKeyChecking=no rocky@"$server_ip" "echo 'SSH 키 인증 성공'" 2>&1)
            if [ $? -eq 0 ]; then
                log_success "SSH 키 인증 성공: $SSH_KEY_TEST"
            else
                log_error "SSH 키 인증 실패: $SSH_KEY_TEST"
            fi
            
            # 비밀번호 인증 테스트
            log_info "비밀번호 인증 테스트 중..."
            SSH_PASS_TEST=$(sshpass -p 'rocky123' ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=no rocky@"$server_ip" "echo '비밀번호 인증 성공'" 2>&1)
            if [ $? -eq 0 ]; then
                log_success "비밀번호 인증 성공: $SSH_PASS_TEST"
            else
                log_error "비밀번호 인증 실패: $SSH_PASS_TEST"
            fi
            
        else
            log_error "SSH 포트 22 닫힘"
        fi
    else
        log_warning "서버 $server_ip 연결 불가"
    fi
done

# 6. Cloud-init 로그 확인 (가능한 경우)
echo ""
log_info "6. Cloud-init 상태 확인"
echo "----------------------"

for server_ip in "${SERVER_IPS[@]}"; do
    if ping -c 1 -W 3 "$server_ip" >/dev/null 2>&1; then
        log_info "서버 $server_ip Cloud-init 로그 확인 중..."
        
        # Cloud-init 로그 조회
        CLOUD_INIT_LOG=$(sshpass -p 'rocky123' ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=no rocky@"$server_ip" "sudo cat /var/log/cloud-init.log 2>/dev/null | tail -20" 2>&1)
        if [ $? -eq 0 ] && [ -n "$CLOUD_INIT_LOG" ]; then
            log_success "Cloud-init 로그 조회 성공"
            echo "최근 Cloud-init 로그:"
            echo "$CLOUD_INIT_LOG"
        else
            log_warning "Cloud-init 로그 조회 실패: $CLOUD_INIT_LOG"
        fi
        
        # 사용자 계정 확인
        log_info "사용자 계정 확인 중..."
        USER_CHECK=$(sshpass -p 'rocky123' ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=no rocky@"$server_ip" "id rocky && ls -la /home/rocky/.ssh/" 2>&1)
        if [ $? -eq 0 ]; then
            log_success "사용자 계정 확인 성공"
            echo "$USER_CHECK"
        else
            log_error "사용자 계정 확인 실패: $USER_CHECK"
        fi
    fi
done

# 7. Proxmox VM 설정 확인
echo ""
log_info "7. Proxmox VM 설정 확인"
echo "----------------------"

# .env 파일에서 Proxmox 설정 로드
if [ -f ".env" ]; then
    source .env
    log_info "Proxmox 설정 로드됨"
    
    # Proxmox API 연결 테스트
    if command -v pvesh >/dev/null 2>&1; then
        log_info "Proxmox CLI 사용 가능"
        # VM 목록 조회
        VM_LIST=$(pvesh get /nodes/localhost/qemu 2>/dev/null)
        if [ $? -eq 0 ]; then
            log_success "Proxmox VM 목록 조회 성공"
            echo "$VM_LIST" | head -10
        else
            log_error "Proxmox VM 목록 조회 실패"
        fi
    else
        log_warning "Proxmox CLI (pvesh)가 설치되지 않음"
    fi
else
    log_warning ".env 파일을 찾을 수 없음"
fi

echo ""
log_info "진단 완료"
echo "=========="
echo "위 결과를 확인하여 SSH 접근 문제의 원인을 파악하세요."
echo ""
echo "일반적인 문제 해결 방법:"
echo "1. SSH 키가 Vault에 올바르게 저장되었는지 확인"
echo "2. Cloud-init가 SSH 키를 올바르게 적용했는지 확인"
echo "3. VM의 SSH 서비스가 정상적으로 실행 중인지 확인"
echo "4. 방화벽 설정이 SSH 포트를 차단하지 않는지 확인"
