# 시스템 아키텍처

## 📋 개요

Terraform Proxmox Manager는 마이크로서비스 아키텍처를 기반으로 한 통합 가상화 관리 시스템입니다. 각 구성 요소는 독립적으로 동작하며, REST API를 통해 상호 통신합니다.

## 🏗️ 전체 아키텍처

```mermaid
graph TB
    subgraph "Frontend Layer"
        UI[Web UI<br/>HTML/CSS/JS]
    end
    
    subgraph "Application Layer"
        API[Flask API<br/>Python 3.8+]
        AUTH[Authentication<br/>Flask-Login]
        NOTIF[Notification<br/>System]
    end
    
    subgraph "Data Layer"
        DB[(SQLite Database<br/>Metadata Storage)]
        VAULT[HashiCorp Vault<br/>Secrets Management)]
    end
    
    subgraph "Infrastructure Layer"
        TF[Terraform<br/>Infrastructure as Code]
        ANS[Ansible<br/>Configuration Management]
    end
    
    subgraph "Monitoring Layer"
        PROM[Prometheus<br/>Metrics Collection]
        GRAF[Grafana<br/>Visualization]
        NODE[Node Exporter<br/>System Metrics]
    end
    
    subgraph "Virtualization Layer"
        PVE[Proxmox VE<br/>Hypervisor]
        VM[Virtual Machines<br/>Rocky Linux 8+]
    end
    
    UI --> API
    API --> AUTH
    API --> NOTIF
    API --> DB
    API --> VAULT
    API --> TF
    API --> ANS
    TF --> PVE
    ANS --> VM
    VM --> NODE
    NODE --> PROM
    PROM --> GRAF
    GRAF --> UI
```

## 🔧 핵심 구성 요소

### 1. 웹 애플리케이션 (Flask)

**위치**: `app/` 디렉토리
**역할**: REST API 서버 및 웹 UI 제공

```python
# 주요 모듈 구조
app/
├── __init__.py          # Flask 앱 초기화
├── routes/              # API 엔드포인트
│   ├── servers.py       # 서버 관리 API
│   ├── monitoring.py    # 모니터링 API
│   ├── backup.py        # 백업 관리 API
│   └── notification.py  # 알림 API
├── services/            # 비즈니스 로직
│   ├── terraform_service.py    # Terraform 연동
│   ├── ansible_service.py      # Ansible 연동
│   ├── prometheus_service.py   # Prometheus 연동
│   └── proxmox_service.py      # Proxmox API 연동
└── models/              # 데이터 모델
    └── server.py        # 서버 모델
```

**주요 기능**:
- RESTful API 제공
- 실시간 알림 시스템
- 사용자 인증 및 권한 관리
- 비동기 작업 처리

### 2. 데이터베이스 (SQLite)

**위치**: `instance/proxmox_manager.db`
**역할**: 메타데이터 저장 및 관리

```sql
-- 주요 테이블 구조
servers (
    id INTEGER PRIMARY KEY,
    name VARCHAR(100),
    ip_address VARCHAR(15),
    role VARCHAR(50),
    status VARCHAR(20),
    created_at TIMESTAMP,
    updated_at TIMESTAMP
)

notifications (
    id INTEGER PRIMARY KEY,
    message TEXT,
    type VARCHAR(50),
    created_at TIMESTAMP
)

backups (
    id INTEGER PRIMARY KEY,
    server_id INTEGER,
    backup_id VARCHAR(100),
    status VARCHAR(20),
    created_at TIMESTAMP
)
```

### 3. 비밀 정보 관리 (Vault)

**위치**: Docker 컨테이너 (`vault-dev`)
**역할**: 민감한 정보 암호화 저장

```yaml
# 저장되는 정보
secret/ssh:
  private_key: "-----BEGIN OPENSSH PRIVATE KEY-----"
  public_key: "ssh-rsa AAAAB3NzaC1yc2E..."

secret/proxmox:
  api_token: "proxmox_api_token"
  api_secret: "proxmox_api_secret"

secret/ansible:
  mysql_root_password: "root1234"
  mysql_user_password: "app1234"
```

### 4. 인프라 관리 (Terraform)

**위치**: `terraform/` 디렉토리
**역할**: Proxmox VM 생성 및 관리

```hcl
# 주요 리소스
resource "proxmox_virtual_environment_vm" "this" {
  name      = var.name
  node_name = var.proxmox_node
  
  cpu {
    cores = var.cpu
  }
  
  memory {
    dedicated = var.memory
  }
  
  disk {
    interface    = "scsi0"
    size         = var.disk_size
    datastore_id = var.datastore_id
  }
  
  network_device {
    bridge = var.bridge
  }
  
  initialization {
    user_account {
      username = var.vm_username
      password = var.vm_password
      keys     = var.ssh_keys
    }
  }
}
```

### 5. 설정 관리 (Ansible)

**위치**: `ansible/` 디렉토리
**역할**: VM 생성 후 소프트웨어 설치 및 설정

```yaml
# 역할별 설정
roles/
├── node_exporter/       # 모니터링 에이전트
├── web/                 # Nginx 웹서버
├── was/                 # Tomcat 애플리케이션 서버
└── db/                  # MySQL 데이터베이스
```

### 6. 모니터링 시스템

**위치**: `monitoring/` 디렉토리 (Docker)
**역할**: 시스템 메트릭 수집 및 시각화

```yaml
# Docker Compose 구성
services:
  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    volumes:
      - grafana_data:/var/lib/grafana
      - ./grafana/provisioning:/etc/grafana/provisioning
    environment:
      - GF_AUTH_ANONYMOUS_ENABLED=true
      - GF_SECURITY_ALLOW_EMBEDDING=true
```

## 🔄 데이터 플로우

### 1. 서버 생성 프로세스

```mermaid
sequenceDiagram
    participant U as User
    participant W as Web UI
    participant A as Flask API
    participant T as Terraform
    participant P as Proxmox
    participant AN as Ansible
    participant PR as Prometheus
    
    U->>W: 서버 생성 요청
    W->>A: POST /api/servers/create
    A->>T: terraform apply
    T->>P: VM 생성 요청
    P-->>T: VM 생성 완료
    T-->>A: 생성 결과 반환
    A->>AN: ansible-playbook 실행
    AN->>P: Node Exporter 설치
    A->>PR: Prometheus 설정 업데이트
    A-->>W: 생성 완료 응답
    W-->>U: 성공 알림
```

### 2. 모니터링 데이터 플로우

```mermaid
sequenceDiagram
    participant VM as Virtual Machine
    participant NE as Node Exporter
    participant PR as Prometheus
    participant GR as Grafana
    participant W as Web UI
    
    VM->>NE: 시스템 메트릭
    NE->>PR: HTTP /metrics
    PR->>PR: 메트릭 저장
    W->>GR: 대시보드 요청
    GR->>PR: 쿼리 요청
    PR-->>GR: 메트릭 데이터
    GR-->>W: 시각화된 데이터
```

## 🔐 보안 아키텍처

### 1. 인증 및 권한 관리

```python
# Flask-Login 기반 인증
@login_manager.user_loader
def load_user(user_id):
    return User.get(user_id)

# API 엔드포인트 보호
@login_required
@admin_required
def create_server():
    pass
```

### 2. 비밀 정보 보호

- **Vault 암호화**: 모든 민감한 정보는 Vault에 암호화 저장
- **환경 변수**: 설정 정보는 `.env` 파일로 관리
- **SSH 키 관리**: Vault를 통한 SSH 키 안전한 저장 및 배포

### 3. 네트워크 보안

- **방화벽 규칙**: 서버별 자동 방화벽 설정
- **SSH 보안**: 키 기반 인증, 비밀번호 인증 비활성화
- **API 보안**: JWT 토큰 기반 인증

## 📊 확장성 고려사항

### 1. 수평 확장

- **로드 밸런서**: Nginx를 통한 API 서버 로드 밸런싱
- **데이터베이스**: PostgreSQL로 마이그레이션 가능
- **캐싱**: Redis 추가로 성능 향상

### 2. 수직 확장

- **리소스 모니터링**: Prometheus를 통한 리소스 사용량 추적
- **자동 스케일링**: CPU/메모리 사용량 기반 자동 확장
- **백업 전략**: 자동화된 백업 및 복구 시스템

## 🔧 개발 환경

### 1. 로컬 개발 설정

```bash
# 가상환경 설정
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 또는
venv\Scripts\activate     # Windows

# 의존성 설치
pip install -r requirements.txt

# 개발 서버 실행
python run.py
```

### 2. 테스트 환경

```bash
# 통합 테스트 실행
python tests/integration_test_suite.py

# 기능 테스트 실행
python tests/functional_test_suite.py

# 전체 테스트 실행
python tests/run_tests.py
```

## 📈 성능 최적화

### 1. 데이터베이스 최적화

- **인덱스**: 자주 조회되는 컬럼에 인덱스 설정
- **연결 풀링**: SQLAlchemy 연결 풀 설정
- **쿼리 최적화**: N+1 문제 해결

### 2. API 성능

- **캐싱**: Redis를 통한 응답 캐싱
- **비동기 처리**: Celery를 통한 백그라운드 작업
- **압축**: gzip 압축으로 응답 크기 감소

### 3. 모니터링 최적화

- **메트릭 수집**: 효율적인 메트릭 수집 주기 설정
- **데이터 보존**: Prometheus 데이터 보존 정책 설정
- **알림 최적화**: 중복 알림 방지 및 알림 그룹핑

---

이 아키텍처는 확장 가능하고 유지보수가 용이한 구조로 설계되었으며, 각 구성 요소는 독립적으로 개발, 배포, 확장할 수 있습니다.
