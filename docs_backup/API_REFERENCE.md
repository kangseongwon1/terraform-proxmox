# 📖 API 참조

## 📋 개요

이 문서는 Proxmox 서버 자동 생성 및 관리 시스템의 API 엔드포인트를 설명합니다.

## 🔐 인증

모든 API 요청은 인증이 필요합니다. Flask-Login을 사용한 세션 기반 인증을 사용합니다.

### 로그인
```http
POST /auth/login
Content-Type: application/x-www-form-urlencoded

username=admin&password=admin123!
```

### 응답
```json
{
  "success": true,
  "message": "로그인 성공"
}
```

## 👥 사용자 관리 API

### 사용자 목록 조회
```http
GET /api/admin/users
```

**응답:**
```json
{
  "success": true,
  "users": [
    {
      "id": 1,
      "username": "admin",
      "email": "admin@example.com",
      "role": "admin",
      "is_active": true,
      "created_at": "2024-01-01T00:00:00Z"
    }
  ]
}
```

### 사용자 생성
```http
POST /api/admin/users
Content-Type: application/json

{
  "username": "newuser",
  "email": "newuser@example.com",
  "password": "password123",
  "role": "developer"
}
```

### 사용자 권한 설정
```http
POST /api/admin/iam/{username}/permissions
Content-Type: application/json

{
  "permissions": ["create_server", "view_all", "backup_management"]
}
```

## 🖥️ 서버 관리 API

### 서버 목록 조회
```http
GET /api/servers
```

**응답:**
```json
{
  "success": true,
  "servers": {
    "web-server-01": {
      "name": "web-server-01",
      "vmid": 101,
      "status": "running",
      "cpu": 2,
      "memory": 4096,
      "ip_addresses": ["192.168.1.100"],
      "role": "web",
      "created_at": "2024-01-01T00:00:00Z"
    }
  }
}
```

### 서버 생성
```http
POST /api/servers
Content-Type: application/json

{
  "name": "web-server-02",
  "cpu": 2,
  "memory": 4096,
  "role": "web",
  "ip_address": "192.168.1.101",
  "disks": [
    {
      "size": 50,
      "interface": "scsi0",
      "datastore_id": "local-lvm"
    }
  ],
  "network_devices": [
    {
      "bridge": "vmbr0",
      "ip_address": "192.168.1.101",
      "subnet": "24",
      "gateway": "192.168.1.1"
    }
  ]
}
```

### 서버 제어
```http
POST /api/servers/{server_name}/start
POST /api/servers/{server_name}/stop
POST /api/servers/{server_name}/reboot
DELETE /api/servers/{server_name}
```

### 서버 삭제
```http
DELETE /api/servers/{server_name}
```

## 💾 백업 관리 API

### 백업 목록 조회
```http
GET /api/backups/nodes
```

**응답:**
```json
{
  "success": true,
  "data": {
    "backups": [
      {
        "vm_name": "web-server-01",
        "vm_id": 101,
        "backups": [
          {
            "filename": "vzdump-qemu-101-2024_01_01-12_00_00.vma.zst",
            "size_gb": 2.5,
            "ctime": 1704096000,
            "storage": "local"
          }
        ],
        "total_size_gb": 2.5
      }
    ],
    "total_count": 1,
    "total_size_gb": 2.5
  }
}
```

### 백업 생성
```http
POST /api/server/backup/{server_name}
Content-Type: application/json

{
  "backup_config": {
    "storage": "local",
    "compress": "zstd",
    "mode": "snapshot"
  }
}
```

### 백업 복원
```http
POST /api/server/restore/{server_name}
Content-Type: application/json

{
  "filename": "vzdump-qemu-101-2024_01_01-12_00_00.vma.zst",
  "storage": "local"
}
```

### 백업 삭제
```http
DELETE /api/server/backup/{server_name}
Content-Type: application/json

{
  "filename": "vzdump-qemu-101-2024_01_01-12_00_00.vma.zst",
  "storage": "local"
}
```

### 백업 상태 조회
```http
GET /api/server/backup/status/{server_name}
```

**응답:**
```json
{
  "success": true,
  "status": "running",
  "progress": 45,
  "message": "백업 진행 중..."
}
```

## 🔥 방화벽 관리 API

### 방화벽 그룹 목록 조회
```http
GET /api/firewall/groups
```

**응답:**
```json
{
  "success": true,
  "groups": [
    {
      "name": "web-servers",
      "description": "웹서버용 방화벽 그룹",
      "instance_count": 3,
      "rules": []
    }
  ]
}
```

### 방화벽 그룹 생성
```http
POST /api/firewall/groups
Content-Type: application/json

{
  "name": "new-group",
  "description": "새로운 방화벽 그룹"
}
```

### 방화벽 그룹 상세 조회
```http
GET /api/firewall/groups/{group_name}
```

### 방화벽 규칙 추가
```http
POST /api/firewall/groups/{group_name}/rules
Content-Type: application/json

{
  "action": "ACCEPT",
  "protocol": "tcp",
  "port": "80",
  "source": "0.0.0.0/0",
  "description": "HTTP 접근 허용"
}
```

### VM에 방화벽 그룹 할당
```http
POST /api/apply_security_group/{server_name}
Content-Type: application/json

{
  "security_group": "web-servers"
}
```

## 📊 모니터링 API

### 시스템 개요 메트릭
```http
GET /api/metrics/grafana/overview
```

**응답:**
```json
{
  "success": true,
  "overview": [
    {
      "vm_name": "web-server-01",
      "role": "web",
      "status": "running",
      "cpu_percent": 25.5,
      "memory_percent": 45.2
    }
  ]
}
```

### VM 메트릭 조회
```http
GET /api/metrics/grafana/vm/{vm_name}?metric=cpu&time_range=1h
```

**응답:**
```json
{
  "success": true,
  "data": {
    "results": [
      {
        "frames": [
          {
            "data": {
              "values": [
                ["2024-01-01T12:00:00Z", "2024-01-01T12:01:00Z"],
                [25.5, 26.1]
              ]
            }
          }
        ]
      }
    ]
  }
}
```

## 🔔 알림 API

### 알림 목록 조회
```http
GET /api/notifications
```

**응답:**
```json
{
  "success": true,
  "notifications": [
    {
      "id": 1,
      "title": "서버 생성 완료",
      "message": "web-server-01이 성공적으로 생성되었습니다.",
      "level": "info",
      "category": "server",
      "created_at": "2024-01-01T12:00:00Z",
      "read": false
    }
  ]
}
```

### 알림 읽음 처리
```http
POST /api/notifications/{notification_id}/read
```

### 모든 알림 읽음 처리
```http
POST /api/notifications/clear-all
```

## 🛠️ 작업 관리 API

### 작업 목록 조회
```http
GET /api/tasks
```

**응답:**
```json
{
  "success": true,
  "tasks": [
    {
      "id": "task_123",
      "type": "create_server",
      "status": "running",
      "message": "서버 생성 중...",
      "progress": 45,
      "created_at": "2024-01-01T12:00:00Z",
      "updated_at": "2024-01-01T12:01:00Z"
    }
  ]
}
```

### 작업 상태 조회
```http
GET /api/tasks/{task_id}
```

## 📝 에러 응답 형식

모든 API는 에러 발생 시 다음과 같은 형식으로 응답합니다:

```json
{
  "success": false,
  "error": "에러 메시지",
  "code": "ERROR_CODE"
}
```

### 일반적인 에러 코드

| 코드 | 설명 |
|------|------|
| `AUTHENTICATION_REQUIRED` | 인증이 필요합니다 |
| `PERMISSION_DENIED` | 권한이 없습니다 |
| `RESOURCE_NOT_FOUND` | 리소스를 찾을 수 없습니다 |
| `VALIDATION_ERROR` | 입력 데이터 검증 실패 |
| `INTERNAL_ERROR` | 내부 서버 오류 |

## 🔒 권한 요구사항

### 서버 관리
- `create_server`: 서버 생성
- `delete_server`: 서버 삭제
- `start_server`: 서버 시작
- `stop_server`: 서버 중지
- `reboot_server`: 서버 재시작

### 백업 관리
- `backup_management`: 백업 생성/복원/삭제

### 방화벽 관리
- `manage_firewall_groups`: 방화벽 그룹 관리
- `assign_firewall_groups`: 방화벽 그룹 할당

### 사용자 관리
- `manage_users`: 사용자 관리
- `manage_roles`: 역할 관리

### 시스템 관리
- `view_all`: 모든 정보 조회
- `view_logs`: 로그 조회

## 📊 요청/응답 예제

### 서버 생성 전체 예제

**요청:**
```http
POST /api/servers
Content-Type: application/json
Cookie: session=your_session_cookie

{
  "name": "web-server-03",
  "cpu": 4,
  "memory": 8192,
  "role": "web",
  "ip_address": "192.168.1.103",
  "disks": [
    {
      "size": 100,
      "interface": "scsi0",
      "datastore_id": "local-lvm",
      "disk_type": "ssd"
    }
  ],
  "network_devices": [
    {
      "bridge": "vmbr0",
      "ip_address": "192.168.1.103",
      "subnet": "24",
      "gateway": "192.168.1.1"
    }
  ],
  "template_vm_id": 9000,
  "vm_username": "rocky",
  "vm_password": "password123"
}
```

**응답:**
```json
{
  "success": true,
  "message": "서버 생성이 시작되었습니다.",
  "task_id": "task_456",
  "server": {
    "name": "web-server-03",
    "status": "creating",
    "estimated_time": "5-10분"
  }
}
```

### 백업 생성 전체 예제

**요청:**
```http
POST /api/server/backup/web-server-01
Content-Type: application/json
Cookie: session=your_session_cookie

{
  "backup_config": {
    "storage": "local",
    "compress": "zstd",
    "mode": "snapshot",
    "remove": false,
    "notes": "정기 백업"
  }
}
```

**응답:**
```json
{
  "success": true,
  "message": "백업이 시작되었습니다.",
  "backup_id": "backup_789",
  "estimated_time": "10-15분"
}
```

## 🔄 웹소켓 API (실시간 업데이트)

### 백업 상태 실시간 업데이트
```javascript
// 백업 상태 구독
const eventSource = new EventSource('/api/server/backup/status/web-server-01/stream');

eventSource.onmessage = function(event) {
  const data = JSON.parse(event.data);
  console.log('백업 상태:', data);
  
  if (data.status === 'completed') {
    eventSource.close();
  }
};
```

### 서버 상태 실시간 업데이트
```javascript
// 서버 상태 구독
const eventSource = new EventSource('/api/servers/status/stream');

eventSource.onmessage = function(event) {
  const data = JSON.parse(event.data);
  console.log('서버 상태 업데이트:', data);
};
```

---

이 문서는 API의 기본적인 사용법을 설명합니다. 더 자세한 정보는 각 엔드포인트의 구현 코드를 참조하세요.

