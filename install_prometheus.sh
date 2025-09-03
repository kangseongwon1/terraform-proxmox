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

# 프로메테우스 설정 파일 생성
echo "⚙️ 프로메테HEUS 설정 파일 생성 중..."
cat > prometheus/prometheus.yml << 'EOF'
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
    scrape_interval: 10s
EOF

# 프로메테우스 서비스 파일 생성
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
ExecStart=/home/dmc_dev/prometheus/prometheus \
    --config.file=/home/dmc_dev/prometheus/prometheus.yml \
    --storage.tsdb.path=/home/dmc_dev/prometheus/data \
    --web.console.templates=/home/dmc_dev/prometheus/consoles \
    --web.console.libraries=/home/dmc_dev/prometheus/console_libraries \
    --web.listen-address=0.0.0.0:9090

[Install]
WantedBy=multi-user.target
EOF

# prometheus 사용자 생성
echo "👤 prometheus 사용자 생성 중..."
sudo useradd --no-create-home --shell /bin/false prometheus

# 디렉토리 권한 설정
echo "🔐 디렉토리 권한 설정 중..."
sudo mkdir -p /home/dmc_dev/prometheus/data
sudo chown -R prometheus:prometheus /home/dmc_dev/prometheus

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

