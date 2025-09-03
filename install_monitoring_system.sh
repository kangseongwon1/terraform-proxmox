#!/bin/bash

# 🚀 통합 모니터링 시스템 설치 스크립트
# Prometheus + Grafana + Node Exporter (Ansible)

set -e

echo "🔧 통합 모니터링 시스템 설치 시작..."
echo "📋 설치 대상: Prometheus + Grafana + Node Exporter"
echo "🌐 대상 서버: 개발 서버 (192.168.0.x 대역과 통신 가능)"
echo ""

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

# 시스템 체크
check_system() {
    log_info "시스템 환경 체크 중..."
    
    # OS 확인
    if [[ -f /etc/redhat-release ]]; then
        OS="redhat"
        log_info "RedHat/CentOS/Rocky Linux 감지됨"
    elif [[ -f /etc/debian_version ]]; then
        OS="debian"
        log_info "Debian/Ubuntu 감지됨"
    else
        log_error "지원하지 않는 OS입니다."
        exit 1
    fi
    
    # Python 확인
    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 --version)
        log_success "Python3 설치됨: $PYTHON_VERSION"
    else
        log_error "Python3가 설치되지 않았습니다."
        exit 1
    fi
    
    # Ansible 확인
    if command -v ansible &> /dev/null; then
        ANSIBLE_VERSION=$(ansible --version | head -n1)
        log_success "Ansible 설치됨: $ANSIBLE_VERSION"
    else
        log_warning "Ansible이 설치되지 않았습니다. 설치를 진행합니다..."
        install_ansible
    fi
}

# Ansible 설치
install_ansible() {
    log_info "Ansible 설치 중..."
    
    if [[ "$OS" == "redhat" ]]; then
        sudo yum install -y epel-release
        sudo yum install -y ansible
    elif [[ "$OS" == "debian" ]]; then
        sudo apt update
        sudo apt install -y software-properties-common
        sudo apt-add-repository --yes --update ppa:ansible/ansible
        sudo apt install -y ansible
    fi
    
    if command -v ansible &> /dev/null; then
        log_success "Ansible 설치 완료"
    else
        log_error "Ansible 설치 실패"
        exit 1
    fi
}

# Prometheus 설치
install_prometheus() {
    log_info "Prometheus 설치 중..."
    
    # 사용자 생성
    sudo useradd --system --no-create-home --shell /bin/false prometheus
    
    # 디렉토리 생성
    sudo mkdir -p /etc/prometheus
    sudo mkdir -p /var/lib/prometheus
    
    # Prometheus 다운로드
    PROMETHEUS_VERSION="2.47.2"
    cd /tmp
    wget -q "https://github.com/prometheus/prometheus/releases/download/v${PROMETHEUS_VERSION}/prometheus-${PROMETHEUS_VERSION}.linux-amd64.tar.gz"
    tar -xzf "prometheus-${PROMETHEUS_VERSION}.linux-amd64.tar.gz"
    
    # 바이너리 복사
    sudo cp prometheus-${PROMETHEUS_VERSION}.linux-amd64/prometheus /usr/local/bin/
    sudo cp prometheus-${PROMETHEUS_VERSION}.linux-amd64/promtool /usr/local/bin/
    
    # 설정 파일 복사
    sudo cp prometheus-${PROMETHEUS_VERSION}.linux-amd64/prometheus.yml /etc/prometheus/
    
    # 권한 설정
    sudo chown prometheus:prometheus /usr/local/bin/prometheus
    sudo chown prometheus:prometheus /usr/local/bin/promtool
    sudo chown -R prometheus:prometheus /etc/prometheus
    sudo chown -R prometheus:prometheus /var/lib/prometheus
    
    # systemd 서비스 생성
    sudo tee /etc/systemd/system/prometheus.service > /dev/null <<EOF
[Unit]
Description=Prometheus
Wants=network-online.target
After=network-online.target

[Service]
User=prometheus
Group=prometheus
Type=simple
ExecStart=/usr/local/bin/prometheus \\
    --config.file=/etc/prometheus/prometheus.yml \\
    --storage.tsdb.path=/var/lib/prometheus \\
    --web.console.templates=/etc/prometheus/consoles \\
    --web.console.libraries=/etc/prometheus/console_libraries \\
    --web.listen-address=0.0.0.0:9090 \\
    --web.enable-lifecycle

[Install]
WantedBy=multi-user.target
EOF
    
    # 서비스 시작
    sudo systemctl daemon-reload
    sudo systemctl enable prometheus
    sudo systemctl start prometheus
    
    # 상태 확인
    sleep 5
    if sudo systemctl is-active --quiet prometheus; then
        log_success "Prometheus 설치 및 시작 완료"
    else
        log_error "Prometheus 시작 실패"
        exit 1
    fi
    
    # 정리
    cd /tmp
    rm -rf prometheus-${PROMETHEUS_VERSION}.linux-amd64*
}

# Grafana 설치
install_grafana() {
    log_info "Grafana 설치 중..."
    
    if [[ "$OS" == "redhat" ]]; then
        # Grafana 저장소 추가
        sudo tee /etc/yum.repos.d/grafana.repo > /dev/null <<EOF
[grafana]
name=grafana
baseurl=https://packages.grafana.com/oss/rpm
repo_gpgcheck=1
enabled=1
gpgcheck=0
gpgkey=https://packages.grafana.com/gpg.key
sslverify=1
sslcacert=/etc/pki/tls/certs/ca-bundle.crt
EOF
        
        sudo yum install -y grafana
        
    elif [[ "$OS" == "debian" ]]; then
        # Grafana 저장소 추가
        wget -q -O - https://packages.grafana.com/gpg.key | sudo apt-key add -
        echo "deb https://packages.grafana.com/oss/deb stable main" | sudo tee /etc/apt/sources.list.d/grafana.list
        sudo apt update
        sudo apt install -y grafana
    fi
    
    # Grafana 설정
    sudo tee /etc/grafana/grafana.ini > /dev/null <<EOF
[server]
http_addr = 0.0.0.0
http_port = 3000
domain = localhost
root_url = %(protocol)s://%(domain)s:%(http_port)s/
serve_from_sub_path = false

[security]
admin_user = admin
admin_password = admin123
allow_embedding = true

[database]
type = sqlite3
path = /var/lib/grafana/grafana.db

[users]
allow_sign_up = false
allow_org_create = false

[auth.anonymous]
enabled = false
EOF
    
    # 서비스 시작
    sudo systemctl daemon-reload
    sudo systemctl enable grafana-server
    sudo systemctl start grafana-server
    
    # 상태 확인
    sleep 5
    if sudo systemctl is-active --quiet grafana-server; then
        log_success "Grafana 설치 및 시작 완료"
    else
        log_error "Grafana 시작 실패"
        exit 1
    fi
}

# Prometheus 설정 업데이트
configure_prometheus() {
    log_info "Prometheus 설정 업데이트 중..."
    
    # 동적 타겟 설정 (나중에 Ansible로 업데이트)
    sudo tee /etc/prometheus/prometheus.yml > /dev/null <<EOF
global:
  scrape_interval: 15s
  evaluation_interval: 15s

rule_files:
  # - "first_rules.yml"
  # - "second_rules.yml"

scrape_configs:
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

  - job_name: 'node-exporter'
    static_configs:
      - targets: ['192.168.0.10:9100']
      - targets: ['192.168.0.11:9100']
      - targets: ['192.168.0.12:9100']
      - targets: ['192.168.0.13:9100']
      - targets: ['192.168.0.14:9100']
      - targets: ['192.168.0.15:9100']
      - targets: ['192.168.0.16:9100']
      - targets: ['192.168.0.17:9100']
    scrape_interval: 10s
    metrics_path: /metrics
EOF
    
    # Prometheus 재시작
    sudo systemctl restart prometheus
    log_success "Prometheus 설정 업데이트 완료"
}

# Node Exporter 설치 (로컬 테스트용)
install_local_node_exporter() {
    log_info "로컬 Node Exporter 설치 중..."
    
    # 사용자 생성
    sudo useradd --system --no-create-home --shell /bin/false node_exporter
    
    # 디렉토리 생성
    sudo mkdir -p /opt/node_exporter
    
    # Node Exporter 다운로드
    NODE_EXPORTER_VERSION="1.6.1"
    cd /tmp
    wget -q "https://github.com/prometheus/node_exporter/releases/download/v${NODE_EXPORTER_VERSION}/node_exporter-${NODE_EXPORTER_VERSION}.linux-amd64.tar.gz"
    tar -xzf "node_exporter-${NODE_EXPORTER_VERSION}.linux-amd64.tar.gz"
    
    # 바이너리 복사
    sudo cp node_exporter-${NODE_EXPORTER_VERSION}.linux-amd64/node_exporter /usr/local/bin/
    
    # 권한 설정
    sudo chown node_exporter:node_exporter /usr/local/bin/node_exporter
    
    # systemd 서비스 생성
    sudo tee /etc/systemd/system/node_exporter.service > /dev/null <<EOF
[Unit]
Description=Node Exporter
After=network.target

[Service]
User=node_exporter
Group=node_exporter
Type=simple
ExecStart=/usr/local/bin/node_exporter --web.listen-address=0.0.0.0:9100

[Install]
WantedBy=multi-user.target
EOF
    
    # 서비스 시작
    sudo systemctl daemon-reload
    sudo systemctl enable node_exporter
    sudo systemctl start node_exporter
    
    # 상태 확인
    sleep 3
    if sudo systemctl is-active --quiet node_exporter; then
        log_success "로컬 Node Exporter 설치 및 시작 완료"
    else
        log_error "로컬 Node Exporter 시작 실패"
        exit 1
    fi
    
    # 정리
    cd /tmp
    rm -rf node_exporter-${NODE_EXPORTER_VERSION}.linux-amd64*
}

# Ansible 인벤토리 및 설정
setup_ansible() {
    log_info "Ansible 설정 중..."
    
    # 인벤토리 파일 생성
    sudo tee /etc/ansible/hosts > /dev/null <<EOF
[monitoring_targets]
192.168.0.10
192.168.0.11
192.168.0.12
192.168.0.13
192.168.0.14
192.168.0.15
192.168.0.16
192.168.0.17

[monitoring_targets:vars]
ansible_user=root
ansible_ssh_private_key_file=/root/.ssh/id_rsa
ansible_python_interpreter=/usr/bin/python3
EOF
    
    # SSH 키 설정 확인
    if [[ ! -f /root/.ssh/id_rsa ]]; then
        log_warning "SSH 키가 설정되지 않았습니다. 수동으로 설정해주세요."
        log_info "SSH 키 설정 방법:"
        log_info "1. ssh-keygen -t rsa -b 4096"
        log_info "2. ssh-copy-id root@192.168.0.x (각 서버별로)"
    fi
    
    log_success "Ansible 설정 완료"
}

# 설치 완료 후 정보 출력
show_completion_info() {
    echo ""
    echo "🎉 모니터링 시스템 설치 완료!"
    echo "=" * 60
    echo ""
    echo "📊 서비스 정보:"
    echo "  - Prometheus: http://$(hostname -I | awk '{print $1}'):9090"
    echo "  - Grafana: http://$(hostname -I | awk '{print $1}'):3000"
    echo "  - Node Exporter (로컬): http://$(hostname -I | awk '{print $1}'):9100"
    echo ""
    echo "🔑 Grafana 기본 계정:"
    echo "  - 사용자: admin"
    echo "  - 비밀번호: admin123"
    echo ""
    echo "📋 다음 단계:"
    echo "  1. Grafana에 로그인하여 Prometheus 데이터 소스 추가"
    echo "  2. 대시보드 생성"
    echo "  3. Ansible로 다른 서버들에 Node Exporter 설치"
    echo ""
    echo "🚀 Node Exporter 일괄 설치 명령:"
    echo "  ansible-playbook -i /etc/ansible/hosts ansible/install_node_exporter.yml"
    echo ""
    echo "💡 서비스 상태 확인:"
    echo "  sudo systemctl status prometheus"
    echo "  sudo systemctl status grafana-server"
    echo "  sudo systemctl status node_exporter"
    echo ""
}

# 메인 실행
main() {
    echo "🚀 통합 모니터링 시스템 설치 시작..."
    echo "⏰ 시작 시간: $(date)"
    echo ""
    
    check_system
    install_prometheus
    install_grafana
    configure_prometheus
    install_local_node_exporter
    setup_ansible
    
    show_completion_info
    
    echo "✅ 설치 완료! $(date)"
}

# 스크립트 실행
main "$@"

