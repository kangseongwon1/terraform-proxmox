# 대량 작업 API 사용 가이드

## 📋 API 개요

새로운 대량 작업 API를 통해 여러 서버에 대한 작업을 효율적으로 처리할 수 있습니다.

## 🔥 주요 개선사항

### ✨ Terraform 기반 삭제
- **일괄 삭제**: Terraform의 `targeted destroy` 사용
- **일관성 보장**: tfvars.json → Terraform destroy → DB 순서로 처리
- **다른 서버 보호**: targeted apply/destroy로 무관한 서버 영향 방지
- **복원 기능**: 실패 시 자동으로 tfvars.json 복원

## 🔗 API 엔드포인트

### POST `/api/servers/bulk_action`

여러 서버에 대해 동일한 작업을 일괄 처리합니다.

#### 요청 형식
```json
{
  "server_names": ["server1", "server2", "server3"],
  "action": "start"
}
```

#### 지원하는 액션
- `start` - 서버 시작
- `stop` - 서버 중지
- `reboot` - 서버 재시작
- `delete` - 서버 삭제 (Proxmox + DB + Terraform)

#### 응답 형식
```json
{
  "success": true,
  "message": "3개 서버 start 작업이 시작되었습니다.",
  "task_id": "task_12345"
}
```

## 🔄 기존 API vs 대량 작업 API

### 기존 방식 (개별 API 호출)
```javascript
// 각 서버마다 별도 API 호출
servers.forEach(serverName => {
  fetch(`/api/servers/${serverName}/start`, { method: 'POST' });
});
```

**단점:**
- 네트워크 요청이 서버 수만큼 발생
- 순차 처리로 인한 시간 지연
- 에러 핸들링이 복잡

### 새로운 방식 (대량 작업 API)
```javascript
// 한 번의 API 호출로 모든 서버 처리
fetch('/api/servers/bulk_action', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    server_names: ['server1', 'server2', 'server3'],
    action: 'start'
  })
});
```

**장점:**
- 단일 네트워크 요청
- 병렬 처리로 빠른 실행
- 통합된 에러 핸들링
- 진행 상황 추적 (task_id)

## 💡 사용 예시

### JavaScript에서 사용
```javascript
function executeBulkAction(serverNames, action) {
  $.ajax({
    url: '/api/servers/bulk_action',
    method: 'POST',
    contentType: 'application/json',
    data: JSON.stringify({
      server_names: serverNames,
      action: action
    }),
    success: function(res) {
      if (res.success && res.task_id) {
        // 작업 상태 폴링 시작
        pollTaskStatus(res.task_id, 'bulk_server_action', `${serverNames.length}개 서버 ${action}`);
      }
    },
    error: function(xhr) {
      console.error('대량 작업 실패:', xhr.responseJSON?.error);
    }
  });
}

// 사용법
executeBulkAction(['web-01', 'web-02', 'web-03'], 'start');
```

### Python에서 사용
```python
import requests

def bulk_server_action(server_names, action):
    response = requests.post('/api/servers/bulk_action', json={
        'server_names': server_names,
        'action': action
    })
    
    if response.status_code == 200:
        result = response.json()
        return result['task_id']
    else:
        raise Exception(f"대량 작업 실패: {response.json()['error']}")

# 사용법
task_id = bulk_server_action(['app-01', 'app-02'], 'reboot')
```

## 🎯 작업 추적

대량 작업은 백그라운드에서 실행되며, `task_id`를 통해 진행 상황을 추적할 수 있습니다.

### 작업 상태 확인
```javascript
function checkTaskStatus(task_id) {
  $.get('/api/tasks/status', { task_id }, function(res) {
    console.log(`작업 상태: ${res.status} - ${res.message}`);
    
    if (res.status === 'completed') {
      console.log('작업 완료!');
      loadActiveServers(); // 서버 목록 새로고침
    } else if (res.status === 'failed') {
      console.error('작업 실패:', res.message);
    }
  });
}
```

## ⚡ 성능 비교

### 10개 서버 시작 작업 기준

| 방식 | 네트워크 요청 | 예상 시간 | 에러 처리 |
|------|---------------|------------|----------|
| 기존 (개별) | 10회 | 10-30초 | 복잡 |
| 새로운 (대량) | 1회 | 3-10초 | 단순 |

## 🔒 권한 및 보안

- `manage_server` 권한 필요
- 서버 존재 여부 확인
- 각 서버별 개별 권한 검증
- 실패한 서버는 건너뛰고 계속 진행

## 🚀 추천 사용법

### 언제 대량 작업 API를 사용할까?

**사용 권장:**
- 3개 이상의 서버에 동일한 작업
- 정기적인 서버 관리 작업
- 스크립트나 자동화에서 사용

**개별 API 사용 권장:**
- 1-2개 서버만 처리
- 서버별로 다른 설정이 필요한 경우
- 세밀한 제어가 필요한 경우

## 🛡️ 삭제 작업의 안전성

### Terraform 기반 삭제 프로세스
1. **유효성 검사**: 삭제할 서버 존재 확인
2. **tfvars.json 수정**: 삭제할 서버 설정 제거
3. **Targeted Destroy**: `terraform destroy -target` 실행
4. **DB 정리**: 성공 시에만 DB에서 서버 제거
5. **실패 시 복원**: destroy 실패 시 tfvars.json 자동 복원

### 다른 서버 보호
```bash
# 예시: 2개 서버만 삭제
terraform destroy -auto-approve \
  -target 'module.server["web-01"]' \
  -target 'module.server["web-02"]'
```

### 장점
- ✅ **인프라 일관성**: Terraform 상태와 실제 인프라 동기화
- ✅ **롤백 지원**: 실패 시 자동 설정 복원
- ✅ **격리 보장**: 다른 서버에 절대 영향 없음
- ✅ **추적 가능**: 모든 변경사항 Terraform으로 관리

이제 대량 서버 관리가 훨씬 효율적이고 안전해졌습니다! 🎉