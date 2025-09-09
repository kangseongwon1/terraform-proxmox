#!/bin/bash

# 프로메테우스 설치 스크립트
echo "🔧 프로메테우스 설치 시작..."

# 프로메테우스 다운로드 (Linux x64)
PROMETHEUS_VERSION="2.47.2"
PROMETHEUS_URL="https://github.com/prometheus/prometheus/releases/download/v${PROMETHEUS_VERSION}/prometheus-${PROMETHEUS_VERSION}.linux-amd64.tar.gz"

echo "📥 프로메테우스 ${PROMETHEUS_VERSION} 다운로드 중..."
wget -O prometheus.tar.gz ${PROMETHEUS_URL}

# 압축 해제
echo "📦 압축 해제 중..."
tar -xzf prometheus.tar.gz
mv prometheus-${PROMETHEUS_VERSION}.linux-amd64 prometheus

# 표준 배치 경로 준비 (/opt, /etc, /var/lib)
echo "🔧 디렉토리 준비 중..."
sudo useradd --no-create-home --shell /bin/false prometheus 2>/dev/null || true
sudo mkdir -p /opt/prometheus
sudo mkdir -p /etc/prometheus
sudo mkdir -p /var/lib/prometheus

# 바이너리 및 콘솔 파일 배치 (/opt/prometheus)
echo "📦 바이너리 배치 중..."
sudo cp -f prometheus/prometheus /opt/prometheus/
sudo cp -f prometheus/promtool /opt/prometheus/
sudo cp -rf prometheus/consoles /opt/prometheus/
sudo cp -rf prometheus/console_libraries /opt/prometheus/
sudo chown -R prometheus:prometheus /opt/prometheus
sudo chmod 0755 /opt/prometheus/prometheus /opt/prometheus/promtool

# 프로메테우스 설정 파일 생성 (/etc/prometheus/prometheus.yml)
echo "⚙️ 프로메테우스 설정 파일 생성 중..."
sudo tee /etc/prometheus/prometheus.yml > /dev/null << 'EOF'
global:
  scrape_interval: 15s
  evaluation_interval: 15s

rule_files: []

scrape_configs:
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

  - job_name: 'node-exporter'
    scrape_interval: 10s
    static_configs:
      - targets: ['192.168.0.10:9100', '192.168.0.11:9100']
EOF

# 소유권 설정
sudo chown -R prometheus:prometheus /etc/prometheus
sudo chown -R prometheus:prometheus /var/lib/prometheus

# systemd 유닛 생성 (표준 경로 사용)
echo "🔧 시스템 서비스 등록 중..."
sudo tee /etc/systemd/system/prometheus.service > /dev/null << 'EOF'
[Unit]
Description=Prometheus
Wants=network-online.target
After=network-online.target

[Service]
User=prometheus
Group=prometheus
Type=simple
ExecStart=/opt/prometheus/prometheus \
    --config.file=/etc/prometheus/prometheus.yml \
    --storage.tsdb.path=/var/lib/prometheus \
    --web.console.templates=/opt/prometheus/consoles \
    --web.console.libraries=/opt/prometheus/console_libraries \
    --web.listen-address=0.0.0.0:9090
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# 서비스 시작
echo "🚀 프로메테우스 서비스 시작 중..."
sudo systemctl daemon-reload
sudo systemctl enable prometheus
sudo systemctl start prometheus

# 상태 확인
echo "✅ 설치 완료! 상태 확인 중..."
sudo systemctl status prometheus --no-pager

echo "🌐 프로메테우스는 http://localhost:9090 에서 접근 가능합니다."
echo "📊 설정된 타겟:"
echo "  - 프로메테우스 자체: localhost:9090"
echo "  - 노드 익스포터: 192.168.0.10:9100, 192.168.0.11:9100"

