#!/bin/bash
# Vault에서 SSH 키를 가져와서 스니펫을 업데이트하는 스크립트

echo "🔑 Vault에서 SSH 키를 가져와서 스니펫 업데이트"
echo "============================================="

# Vault에서 SSH 키 가져오기
echo "📋 Vault에서 SSH 키 조회 중..."
SSH_KEY_FROM_VAULT=$(docker exec vault-dev vault kv get -field=public_key secret/ssh 2>/dev/null)

if [ $? -eq 0 ] && [ -n "$SSH_KEY_FROM_VAULT" ]; then
    echo "✅ Vault에서 SSH 키 조회 성공"
    echo "SSH 키 (처음 50자): $(echo "$SSH_KEY_FROM_VAULT" | head -c 50)..."
else
    echo "❌ Vault에서 SSH 키 조회 실패"
    exit 1
fi

# 스니펫 파일 생성
echo ""
echo "📝 스니펫 파일 생성 중..."
cat > ci-userdata-dev-with-ssh.yaml << EOF
manage_etc_hosts: true

users:
  - name: dev
    gecos: "Dev User"
    groups: [wheel]
    sudo: ["ALL=(ALL) NOPASSWD:ALL"]
    shell: /bin/bash
    lock_passwd: false
  - name: rocky
    gecos: "Rocky User"
    groups: [wheel]
    sudo: ["ALL=(ALL) NOPASSWD:ALL"]
    shell: /bin/bash
    lock_passwd: false

ssh_pwauth: true

chpasswd:
  expire: false
  list: |
    dev:dev1234!
    rocky:rocky1234

# SSH 키 설정 (Vault에서 가져온 키)
ssh_authorized_keys:
  - $SSH_KEY_FROM_VAULT

# 시스템 타임존을 KST로 고정
timezone: Asia/Seoul

# NTP 동기화 (chrony 사용 권장)
ntp:
  enabled: true
  ntp_client: chrony
  servers:
    - time.kriss.re.kr
    - time.bora.net
    - 0.kr.pool.ntp.org
    - 1.kr.pool.ntp.org

# SELinux/Firewalld 비활성화 및 시간/서비스 보정
runcmd:
  # SELinux 비활성화 (영구/즉시)
  - [ bash, -lc, "sed -ri 's/^SELINUX=.*/SELINUX=disabled/' /etc/selinux/config || true" ]
  - [ bash, -lc, "setenforce 0 || true" ]

  # firewalld 중지/비활성화 (이미지에 있을 경우)
  - [ bash, -lc, "systemctl disable --now firewalld || true" ]

  # chrony 보강 설정(있으면 유지, 없으면 설치)
  - [ bash, -lc, "rpm -q chrony >/dev/null 2>&1 || (dnf -y install chrony || yum -y install chrony)" ]
  - [ bash, -lc, "systemctl enable --now chronyd" ]

  # 타임존 재확인
  - [ bash, -lc, "timedatectl set-timezone Asia/Seoul" ]

final_message: "Cloud-init: dev/rocky 계정/SSH PW/SELinux off/firewalld off/KST/NTP 설정 완료"
EOF

echo "✅ 스니펫 파일 생성 완료: ci-userdata-dev-with-ssh.yaml"
echo ""
echo "📋 다음 명령어로 Proxmox에 스니펫을 업데이트하세요:"
echo "   scp ci-userdata-dev-with-ssh.yaml root@192.168.0.100:/var/lib/vz/snippets/ci-userdata-dev.yaml"
echo ""
echo "   또는 Proxmox 웹 UI에서 스니펫을 업데이트하세요."
echo ""
echo "🔄 그 후 다음 명령어로 VM 템플릿을 업데이트하세요:"
echo "   qm set 8000 --cicustom 'user=local:snippets/ci-userdata-dev.yaml'"
