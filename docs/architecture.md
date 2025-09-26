# Proxmox Manager 아키텍처 문서

## 📋 개요

Proxmox Manager는 Flask 기반의 웹 애플리케이션으로, Proxmox 가상화 환경을 관리하는 시스템입니다.

## 🏗️ 전체 아키텍처

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   웹 브라우저    │    │   Flask 앱      │    │   Celery 워커   │
│                 │    │   (호스트)      │    │   (Docker)      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │ 1. 서버 생성 요청      │                       │
         ├──────────────────────►│                       │
         │                       │ 2. Celery 태스크 큐에  │
         │                       │    작업 추가           │
         │                       ├──────────────────────►│
         │                       │                       │
         │                       │                       │ 3. Terraform 실행
         │                       │                       │    (호스트 바이너리)
         │                       │                       │
         │                       │ 4. 작업 완료 알림     │
         │                       │◄──────────────────────┤
         │ 5. 결과 반환          │                       │
         │◄─────────────────────┤                       │
```

## 🔧 핵심 컴포넌트

### 1. Flask 웹 애플리케이션 (호스트)
- **위치**: 호스트에서 직접 실행
- **역할**: 웹 인터페이스 제공, API 엔드포인트 처리
- **실행**: `python run.py`

### 2. Celery 워커 (Docker 컨테이너)
- **위치**: Docker 컨테이너 내부
- **역할**: 비동기 작업 처리
- **실행**: `celery -A app.celery_app worker`

### 3. Redis (Docker 컨테이너)
- **위치**: Docker 컨테이너 내부
- **역할**: Celery 브로커 및 백엔드, 캐싱
- **포트**: 6379

### 4. Terraform (호스트)
- **위치**: 호스트에 설치
- **역할**: 인프라스트럭처 프로비저닝
- **실행**: Celery 워커에서 호스트 바이너리 호출

## 🔄 작업 흐름

### 동기 작업 (기존)
```
웹 요청 → Flask 앱 → ProxmoxService → Proxmox API
```

### 비동기 작업 (새로운)
```
웹 요청 → Flask 앱 → Celery 태스크 큐 → Celery 워커 → 호스트 Terraform → 결과 반환
```

## 🐳 Docker 구성

### Celery 워커 컨테이너
```yaml
celery-worker:
  build:
    context: ..
    dockerfile: docker/Dockerfile.celery
  volumes:
    - ../:/app                    # 애플리케이션 코드
    - /etc/localtime:/etc/localtime:ro  # 시간 동기화
    - /etc/timezone:/etc/timezone:ro
  environment:
    - REDIS_HOST=redis
    - REDIS_PORT=6379
    - REDIS_PASSWORD=${REDIS_PASSWORD}
```

### Redis 컨테이너
```yaml
redis:
  image: redis:7-alpine
  ports:
    - "6379:6379"
  command: redis-server --requirepass ${REDIS_PASSWORD}
```

## 🔧 Terraform 통합

### 호스트 Terraform 사용
- **이유**: Celery 워커가 Docker 컨테이너에서 실행되지만, Terraform은 호스트에서 실행
- **방법**: Docker 볼륨 마운트를 통해 호스트의 terraform 바이너리 접근
- **장점**: 기존 설치된 terraform 활용, 호환성 보장

### Terraform 실행 경로
```python
# app/tasks/server_tasks.py
host_terraform_dir = "/app/terraform"  # Docker 마운트된 경로
terraform_service = TerraformService(host_terraform_dir)
```

## 📁 디렉토리 구조

```
terraform-proxmox/
├── app/                    # Flask 애플리케이션
│   ├── routes/            # API 엔드포인트
│   │   ├── servers.py     # 동기 서버 작업
│   │   ├── servers_async.py  # 비동기 서버 작업
│   │   └── servers_sync.py   # 동기 서버 작업
│   ├── tasks/             # Celery 태스크
│   │   └── server_tasks.py   # 비동기 서버 생성
│   ├── services/          # 비즈니스 로직
│   │   ├── proxmox_service.py
│   │   └── terraform_service.py
│   └── celery_app.py      # Celery 설정
├── redis/                 # Redis & Celery Docker 설정
│   └── docker-compose.yml
├── docker/               # Docker 파일들
│   └── Dockerfile.celery
└── terraform/            # Terraform 설정 파일들
```

## 🔄 비동기 작업 처리

### 1. 서버 생성
```python
# 웹 요청
POST /api/servers/async
{
  "name": "test-server",
  "cpu": 2,
  "memory": 4,
  "disk": 20
}

# Celery 태스크
@celery_app.task(bind=True)
def create_server_async(self, server_config):
    # 1. Terraform 파일 생성
    # 2. Terraform 실행 (호스트 바이너리)
    # 3. 서버 정보 DB 저장
    # 4. 결과 반환
```

### 2. 대량 서버 작업
```python
# 웹 요청
POST /api/servers/bulk_action/async
{
  "server_names": ["server1", "server2"],
  "action": "start"
}

# Celery 태스크
@celery_app.task(bind=True)
def bulk_server_action_async(self, server_names, action):
    # 1. 각 서버에 대해 작업 실행
    # 2. 성공/실패 결과 수집
    # 3. 결과 반환
```

## 🚀 배포 및 실행

### 1. 호스트에서 Flask 앱 실행
```bash
python run.py
```

### 2. Docker로 Redis & Celery 실행
```bash
cd redis
docker-compose up -d
```

### 3. 서비스 확인
- **웹 인터페이스**: http://localhost:5000
- **Celery Flower**: http://localhost:5555
- **Redis**: localhost:6379

## 🔧 환경 변수

### 필수 환경 변수
```bash
# Proxmox 연결
PROXMOX_ENDPOINT=https://proxmox.example.com:8006
PROXMOX_USERNAME=user@pam
PROXMOX_PASSWORD=password
PROXMOX_NODE=proxmox-node

# Redis & Celery
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=your_password
REDIS_ENABLED=true
```

## 📊 모니터링

### Celery Flower
- **URL**: http://localhost:5555
- **기능**: Celery 워커 상태, 태스크 모니터링

### Redis 모니터링
```bash
# Redis CLI 접속
redis-cli -a your_password

# 키 확인
KEYS *

# Celery 큐 확인
LLEN celery
```

## 🛠️ 문제 해결

### 1. Terraform 명령어를 찾을 수 없는 경우
```bash
# 호스트에 terraform 설치 확인
which terraform

# Docker 컨테이너에서 호스트 terraform 접근 확인
docker exec proxmox-celery-worker which terraform
```

### 2. Celery 워커가 작업을 처리하지 않는 경우
```bash
# Celery 워커 상태 확인
docker logs proxmox-celery-worker

# Redis 연결 확인
docker exec proxmox-redis redis-cli -a your_password PING
```

### 3. 작업이 PENDING 상태에서 멈춘 경우
```bash
# Celery 워커 재시작
cd redis
docker-compose restart celery-worker
```

## 📝 개발 가이드

### 새로운 비동기 작업 추가
1. `app/tasks/` 디렉토리에 태스크 함수 정의
2. `app/routes/servers_async.py`에 API 엔드포인트 추가
3. 프론트엔드에서 비동기 작업 호출

### 동기 작업 유지
- 기존 `app/routes/servers.py`의 동기 작업들은 그대로 유지
- 새로운 비동기 작업은 `app/routes/servers_async.py`에 추가

## 🔄 마이그레이션 전략

### 단계적 마이그레이션
1. **1단계**: 기존 동기 작업 유지
2. **2단계**: 새로운 비동기 작업 추가
3. **3단계**: 점진적으로 동기 작업을 비동기로 전환

### 호환성 보장
- 기존 API 엔드포인트 유지
- 새로운 비동기 API 추가
- 프론트엔드에서 점진적 전환

---

**최종 업데이트**: 2025-09-26
**버전**: 1.0.0