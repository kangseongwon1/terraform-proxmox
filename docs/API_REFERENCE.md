# API 레퍼런스

## 📋 개요

Terraform Proxmox Manager는 RESTful API를 제공하여 서버 관리, 모니터링, 백업 등의 기능을 프로그래밍 방식으로 제어할 수 있습니다.

## 🔐 인증

### 기본 인증
현재 버전에서는 Flask-Login을 사용한 세션 기반 인증을 지원합니다.

```bash
# 로그인
curl -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "password"}'

# 로그아웃
curl -X POST http://localhost:5000/api/auth/logout
```

### API 키 인증 (향후 지원 예정)
```bash
curl -H "Authorization: Bearer YOUR_API_KEY" \
  http://localhost:5000/api/servers
```

## 📊 서버 관리 API

### 1. 서버 목록 조회

**GET** `/api/servers`

서버 목록을 조회합니다.

```bash
curl http://localhost:5000/api/servers
```

**응답 예시**:
```json
{
  "servers": [
    {
      "id": 1,
      "name": "web-server-01",
      "ip_address": "192.168.0.21",
      "role": "web",
      "status": "running",
      "cpu": 2,
      "memory": 4096,
      "disk_size": 50,
      "created_at": "2024-01-15T10:30:00Z",
      "updated_at": "2024-01-15T10:30:00Z"
    }
  ],
  "total": 1
}
```

### 2. 서버 생성

**POST** `/api/servers/create`

새로운 서버를 생성합니다.

```bash
curl -X POST http://localhost:5000/api/servers/create \
  -H "Content-Type: application/json" \
  -d '{
    "name": "web-server-02",
    "role": "web",
    "cpu": 2,
    "memory": 4096,
    "disk_size": 50,
    "network_config": {
      "ip_address": "192.168.0.22",
      "subnet": "24",
      "gateway": "192.168.0.1"
    }
  }'
```

**요청 파라미터**:
- `name` (string, 필수): 서버 이름
- `role` (string, 필수): 서버 역할 (web, was, db)
- `cpu` (integer, 필수): CPU 코어 수
- `memory` (integer, 필수): 메모리 크기 (MB)
- `disk_size` (integer, 필수): 디스크 크기 (GB)
- `network_config` (object, 필수): 네트워크 설정

**응답 예시**:
```json
{
  "success": true,
  "message": "서버 생성이 시작되었습니다",
  "task_id": "task_12345"
}
```

### 3. 대량 서버 생성

**POST** `/api/servers/bulk-create`

여러 서버를 한 번에 생성합니다.

```bash
curl -X POST http://localhost:5000/api/servers/bulk-create \
  -H "Content-Type: application/json" \
  -d '{
    "servers": [
      {
        "name": "web-server-01",
        "role": "web",
        "cpu": 2,
        "memory": 4096,
        "disk_size": 50
      },
      {
        "name": "was-server-01",
        "role": "was",
        "cpu": 4,
        "memory": 8192,
        "disk_size": 100
      }
    ],
    "network_config": {
      "ip_range": "192.168.0.21-192.168.0.30",
      "subnet": "24",
      "gateway": "192.168.0.1"
    }
  }'
```

### 4. 서버 삭제

**DELETE** `/api/servers/{server_id}`

특정 서버를 삭제합니다.

```bash
curl -X DELETE http://localhost:5000/api/servers/1
```

**응답 예시**:
```json
{
  "success": true,
  "message": "서버가 성공적으로 삭제되었습니다"
}
```

### 5. 대량 서버 삭제

**POST** `/api/servers/bulk-delete`

여러 서버를 한 번에 삭제합니다.

```bash
curl -X POST http://localhost:5000/api/servers/bulk-delete \
  -H "Content-Type: application/json" \
  -d '{
    "server_ids": [1, 2, 3]
  }'
```

### 6. 서버 상태 업데이트

**PUT** `/api/servers/{server_id}/status`

서버 상태를 업데이트합니다.

```bash
curl -X PUT http://localhost:5000/api/servers/1/status \
  -H "Content-Type: application/json" \
  -d '{
    "status": "stopped"
  }'
```

## 📈 모니터링 API

### 1. 모니터링 상태 조회

**GET** `/api/monitoring/status`

모니터링 시스템의 상태를 조회합니다.

```bash
curl http://localhost:5000/api/monitoring/status
```

**응답 예시**:
```json
{
  "prometheus": {
    "status": "running",
    "url": "http://localhost:9090",
    "targets": 5,
    "healthy_targets": 4
  },
  "grafana": {
    "status": "running",
    "url": "http://localhost:3000",
    "dashboards": 3
  },
  "node_exporters": {
    "total": 5,
    "active": 4,
    "inactive": 1
  }
}
```

### 2. 서버 메트릭 조회

**GET** `/api/monitoring/metrics/{server_id}`

특정 서버의 메트릭을 조회합니다.

```bash
curl http://localhost:5000/api/monitoring/metrics/1
```

**응답 예시**:
```json
{
  "server_id": 1,
  "server_name": "web-server-01",
  "metrics": {
    "cpu_usage": 45.2,
    "memory_usage": 67.8,
    "disk_usage": 23.4,
    "network_in": 1024,
    "network_out": 2048,
    "timestamp": "2024-01-15T10:30:00Z"
  }
}
```

### 3. Prometheus 설정 업데이트

**POST** `/api/monitoring/prometheus/update`

Prometheus 설정을 업데이트합니다.

```bash
curl -X POST http://localhost:5000/api/monitoring/prometheus/update
```

## 💾 백업 관리 API

### 1. 백업 목록 조회

**GET** `/api/backups`

백업 목록을 조회합니다.

```bash
curl http://localhost:5000/api/backups
```

**응답 예시**:
```json
{
  "backups": [
    {
      "id": 1,
      "server_id": 1,
      "server_name": "web-server-01",
      "backup_id": "backup_12345",
      "status": "completed",
      "size": "2.5GB",
      "created_at": "2024-01-15T02:00:00Z"
    }
  ],
  "total": 1
}
```

### 2. 백업 생성

**POST** `/api/backups/create`

서버의 백업을 생성합니다.

```bash
curl -X POST http://localhost:5000/api/backups/create \
  -H "Content-Type: application/json" \
  -d '{
    "server_id": 1,
    "backup_type": "full"
  }'
```

### 3. 백업 복원

**POST** `/api/backups/{backup_id}/restore`

백업을 복원합니다.

```bash
curl -X POST http://localhost:5000/api/backups/backup_12345/restore \
  -H "Content-Type: application/json" \
  -d '{
    "target_server_id": 2,
    "overwrite": true
  }'
```

### 4. 백업 삭제

**DELETE** `/api/backups/{backup_id}`

백업을 삭제합니다.

```bash
curl -X DELETE http://localhost:5000/api/backups/backup_12345
```

## 🔔 알림 API

### 1. 알림 목록 조회

**GET** `/api/notifications`

알림 목록을 조회합니다.

```bash
curl http://localhost:5000/api/notifications
```

**응답 예시**:
```json
{
  "notifications": [
    {
      "id": 1,
      "message": "서버 web-server-01이 성공적으로 생성되었습니다",
      "type": "success",
      "created_at": "2024-01-15T10:30:00Z"
    }
  ],
  "total": 1
}
```

### 2. 최신 알림 조회

**GET** `/api/notifications/latest`

최신 알림을 조회합니다.

```bash
curl http://localhost:5000/api/notifications/latest
```

### 3. 알림 삭제

**DELETE** `/api/notifications/{notification_id}`

특정 알림을 삭제합니다.

```bash
curl -X DELETE http://localhost:5000/api/notifications/1
```

## 🔧 시스템 관리 API

### 1. 시스템 상태 조회

**GET** `/api/system/status`

시스템 전체 상태를 조회합니다.

```bash
curl http://localhost:5000/api/system/status
```

**응답 예시**:
```json
{
  "system": {
    "status": "healthy",
    "uptime": "7 days, 12 hours",
    "version": "1.0.0",
    "last_updated": "2024-01-15T10:30:00Z"
  },
  "services": {
    "flask": "running",
    "prometheus": "running",
    "grafana": "running",
    "vault": "running"
  },
  "resources": {
    "cpu_usage": 25.4,
    "memory_usage": 45.6,
    "disk_usage": 67.8
  }
}
```

### 2. 로그 조회

**GET** `/api/system/logs`

시스템 로그를 조회합니다.

```bash
curl http://localhost:5000/api/system/logs?level=error&limit=100
```

**쿼리 파라미터**:
- `level` (string, 선택): 로그 레벨 (debug, info, warning, error)
- `limit` (integer, 선택): 조회할 로그 수 (기본값: 50)
- `offset` (integer, 선택): 오프셋 (기본값: 0)

### 3. 설정 조회

**GET** `/api/system/config`

시스템 설정을 조회합니다.

```bash
curl http://localhost:5000/api/system/config
```

## 🔐 Vault 관리 API

### 1. Vault 상태 조회

**GET** `/api/vault/status`

Vault 상태를 조회합니다.

```bash
curl http://localhost:5000/api/vault/status
```

### 2. 비밀 정보 조회

**GET** `/api/vault/secrets/{path}`

Vault에서 비밀 정보를 조회합니다.

```bash
curl http://localhost:5000/api/vault/secrets/secret/ssh
```

### 3. 비밀 정보 저장

**POST** `/api/vault/secrets/{path}`

Vault에 비밀 정보를 저장합니다.

```bash
curl -X POST http://localhost:5000/api/vault/secrets/secret/ssh \
  -H "Content-Type: application/json" \
  -d '{
    "private_key": "-----BEGIN OPENSSH PRIVATE KEY-----",
    "public_key": "ssh-rsa AAAAB3NzaC1yc2E..."
  }'
```

## 📊 응답 코드

| 코드 | 설명 |
|------|------|
| 200 | 성공 |
| 201 | 생성 성공 |
| 400 | 잘못된 요청 |
| 401 | 인증 실패 |
| 403 | 권한 없음 |
| 404 | 리소스 없음 |
| 500 | 서버 오류 |

## 🔄 비동기 작업

### 작업 상태 조회

**GET** `/api/tasks/{task_id}`

비동기 작업의 상태를 조회합니다.

```bash
curl http://localhost:5000/api/tasks/task_12345
```

**응답 예시**:
```json
{
  "task_id": "task_12345",
  "status": "running",
  "progress": 75,
  "message": "서버 생성 중...",
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:35:00Z"
}
```

## 📝 에러 응답

에러 발생 시 다음과 같은 형식으로 응답합니다:

```json
{
  "error": {
    "code": "INVALID_REQUEST",
    "message": "요청 파라미터가 올바르지 않습니다",
    "details": {
      "field": "name",
      "reason": "서버 이름은 필수입니다"
    }
  }
}
```

## 🔧 API 테스트

### Postman 컬렉션

API 테스트를 위한 Postman 컬렉션을 제공합니다:

```bash
# Postman 컬렉션 다운로드
curl -O https://raw.githubusercontent.com/your-org/terraform-proxmox/main/docs/postman_collection.json
```

### cURL 예제

```bash
# 서버 생성 예제
curl -X POST http://localhost:5000/api/servers/create \
  -H "Content-Type: application/json" \
  -d '{
    "name": "test-server",
    "role": "web",
    "cpu": 2,
    "memory": 4096,
    "disk_size": 50
  }' | jq '.'

# 응답 포맷팅 (jq 사용)
curl http://localhost:5000/api/servers | jq '.servers[] | {name, status, ip_address}'
```

---

더 자세한 API 사용법은 [운영 가이드](OPERATION_GUIDE.md)를 참조하세요.
