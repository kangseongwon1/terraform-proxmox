# 🚀 통합 모니터링 시스템 설치 가이드

## 📋 개요

이 문서는 Proxmox 환경에서 Prometheus + Grafana + Node Exporter를 사용한 통합 모니터링 시스템 구축 방법을 설명합니다.

## 🎯 시스템 구성

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   개발 서버     │    │   VM 서버들     │    │   웹 콘솔      │
│                 │    │                 │    │                 │
│ ┌─────────────┐ │    │ ┌─────────────┐ │    │ ┌─────────────┐ │
│ │ Prometheus  │◄────┤ │Node Exporter│ │    │ │ Flask App  │ │
│ │   :9090     │ │    │ │   :9100     │ │    │ │             │ │
│ └─────────────┘ │    │ └─────────────┘ │    │ └─────────────┘ │
│                 │    │                 │    │                 │
│ ┌─────────────┐ │    │                 │    │                 │
│ │   Grafana   │ │    │                 │    │                 │
│ │   :3000     │ │    │                 │    │                 │
│ └─────────────┘ │    │                 │    │                 │
│                 │    │                 │    │                 │
│ ┌─────────────┐ │    │                 │    │                 │
│ │Node Exporter│ │    │                 │    │                 │
│ │   :9100     │ │    │                 │    │                 │
│ └─────────────┘ │    │                 │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 🛠️ 설치 단계

### **1단계: 개발 서버에 모니터링 시스템 설치**

```bash
# 스크립트 실행 권한 부여
chmod +x install_monitoring_system.sh

# 통합 설치 실행
sudo ./install_monitoring_system.sh
```

**설치되는 서비스:**
- Prometheus (포트 9090)
- Grafana (포트 3000)
- Node Exporter (포트 9100)
- Ansible 설정

### **2단계: 설치 후 자동 설정**

```bash
# 후처리 설정 스크립트 실행 권한 부여
chmod +x setup_monitoring_post_install.sh

# 자동 설정 실행
sudo ./setup_monitoring_post_install.sh
```

**자동 설정 내용:**
- Prometheus 데이터 소스 추가
- 기본 모니터링 대시보드 생성
- 알림 규칙 템플릿 생성

### **3단계: 다른 서버들에 Node Exporter 설치**

```bash
# SSH 키 설정 (필요시)
ssh-keygen -t rsa -b 4096
ssh-copy-id root@192.168.0.10
ssh-copy-id root@192.168.0.11
# ... 기타 서버들

# Ansible로 일괄 설치
ansible-playbook -i /etc/ansible/hosts ansible/install_node_exporter.yml
```

## 🔧 설정 파일

### **Prometheus 설정** (`/etc/prometheus/prometheus.yml`)

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

  - job_name: 'node-exporter'
    static_configs:
      - targets: ['192.168.0.10:9100']
      - targets: ['192.168.0.11:9100']
      # ... 기타 서버들
    scrape_interval: 10s
    metrics_path: /metrics
```

### **Grafana 설정** (`/etc/grafana/grafana.ini`)

```ini
[server]
http_addr = 0.0.0.0
http_port = 3000

[security]
admin_user = admin
admin_password = admin123

[database]
type = sqlite3
path = /var/lib/grafana/grafana.db
```

## 📊 접속 정보

### **기본 접속 정보**
- **Grafana**: http://서버IP:3000
- **Prometheus**: http://서버IP:9090
- **Node Exporter**: http://서버IP:9100

### **기본 계정**
- **사용자**: admin
- **비밀번호**: admin123

## 🎨 기본 대시보드

설치 후 자동으로 생성되는 대시보드:

1. **CPU 사용률**: 모든 서버의 CPU 사용률 그래프
2. **메모리 사용률**: 모든 서버의 메모리 사용률 그래프
3. **디스크 사용률**: 모든 서버의 디스크 사용률 그래프
4. **네트워크 트래픽**: 모든 서버의 네트워크 송수신 그래프

## 🚨 알림 설정

### **기본 알림 규칙**
- **CPU 사용률**: 80% 이상 시 경고
- **메모리 사용률**: 85% 이상 시 경고

### **알림 채널 설정**
Grafana 웹 UI에서 다음 경로로 설정:
- Alerting > Notification channels > Add channel

## 🔍 문제 해결

### **서비스 상태 확인**
```bash
# 모든 서비스 상태 확인
sudo systemctl status prometheus grafana-server node_exporter

# 특정 서비스 로그 확인
sudo journalctl -u prometheus -f
sudo journalctl -u grafana-server -f
sudo journalctl -u node_exporter -f
```

### **포트 확인**
```bash
# 사용 중인 포트 확인
sudo netstat -tlnp | grep -E ':(9090|3000|9100)'

# 또는 ss 명령어 사용
sudo ss -tlnp | grep -E ':(9090|3000|9100)'
```

### **방화벽 설정**
```bash
# RedHat/CentOS/Rocky
sudo firewall-cmd --permanent --add-port=9090/tcp
sudo firewall-cmd --permanent --add-port=3000/tcp
sudo firewall-cmd --permanent --add-port=9100/tcp
sudo firewall-cmd --reload

# Ubuntu/Debian
sudo ufw allow 9090/tcp
sudo ufw allow 3000/tcp
sudo ufw allow 9100/tcp
```

## 📈 확장 및 커스터마이징

### **추가 메트릭 수집**
- **MySQL Exporter**: 데이터베이스 메트릭
- **Nginx Exporter**: 웹 서버 메트릭
- **Custom Exporter**: 애플리케이션별 메트릭

### **대시보드 커스터마이징**
- Grafana 웹 UI에서 대시보드 편집
- 추가 패널 및 그래프 생성
- 알림 규칙 추가

### **백업 및 복구**
```bash
# Prometheus 데이터 백업
sudo tar -czf prometheus_backup_$(date +%Y%m%d).tar.gz /var/lib/prometheus

# Grafana 설정 백업
sudo tar -czf grafana_backup_$(date +%Y%m%d).tar.gz /etc/grafana /var/lib/grafana
```

## 🚀 운영 환경 적용

### **프로덕션 고려사항**
1. **보안**: 기본 비밀번호 변경
2. **백업**: 정기적인 데이터 백업
3. **모니터링**: 모니터링 시스템 자체 모니터링
4. **확장성**: 데이터베이스 전환 (PostgreSQL/MySQL)
5. **고가용성**: 클러스터 구성

### **성능 최적화**
- Prometheus 스토리지 설정 조정
- Grafana 캐싱 설정
- 메트릭 수집 간격 조정

## 📚 참고 자료

- [Prometheus 공식 문서](https://prometheus.io/docs/)
- [Grafana 공식 문서](https://grafana.com/docs/)
- [Node Exporter GitHub](https://github.com/prometheus/node_exporter)
- [Ansible 공식 문서](https://docs.ansible.com/)

## 🤝 지원 및 문의

문제가 발생하거나 추가 도움이 필요한 경우:
1. 로그 파일 확인
2. 서비스 상태 점검
3. 네트워크 연결 확인
4. 방화벽 설정 확인

