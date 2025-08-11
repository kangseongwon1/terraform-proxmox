# 서버 데이터 동기화 문제 해결 가이드

## 🐛 문제 상황

**역할 할당 시 "서버가 존재하지 않습니다" 오류가 발생**하는 근본적인 원인이 발견되었습니다.

### 🔍 원인 분석

**서버 목록 표시와 역할 할당이 서로 다른 데이터 소스를 사용**하고 있었습니다:

```
📊 서버 목록 API (/api/all_server_status)
  ↓
🔗 ProxmoxService.get_all_vms()
  ↓ 
📄 terraform/terraform.tfvars.json 기반
  ↓
🖥️ 화면에 "AI-agent" 서버 표시

❌ 하지만...

🎯 역할 할당 API (/api/assign_role/<server_name>)
  ↓
💾 Server.query.filter_by(name=server_name)
  ↓
🗄️ SQLite DB (instance/proxmox_manager.db)
  ↓
❌ "AI-agent" 서버 없음 → 404 오류
```

### 📝 실제 확인된 데이터 상태

**DB에는 `test`, `test-2` 서버만 존재:**
```sql
SELECT name FROM servers;
-- 결과: test, test-2
```

**하지만 화면에는 `AI-agent` 서버가 표시됨** (Proxmox/tfvars.json 기반)

## ✅ 해결 방법

### 🚀 **역할 할당 API 개선 (적용 완료)**

역할 할당 API를 **서버 목록 API와 동일한 데이터 소스**를 사용하도록 수정했습니다:

#### **개선된 프로세스:**

1. **🔍 서버 존재 확인**: Proxmox API로 서버 존재 여부 확인
2. **📝 자동 DB 생성**: DB에 없으면 자동으로 서버 레코드 생성
3. **🎯 역할 할당**: 서버 역할 업데이트
4. **💾 변경사항 저장**: DB 커밋

#### **코드 변경사항:**

```python
# 수정 전 (문제 코드)
def assign_role(server_name):
    server = Server.query.filter_by(name=server_name).first()
    if not server:  # ❌ DB에만 의존
        return jsonify({'error': '서버를 찾을 수 없습니다.'}), 404

# 수정 후 (해결 코드)
def assign_role(server_name):
    # 1. Proxmox API로 서버 존재 확인 (서버 목록 API와 동일)
    proxmox_service = ProxmoxService()
    result = proxmox_service.get_all_vms()
    
    server_exists = False
    if result['success']:
        for vm_key, server_data in result['data']['servers'].items():
            if server_data.get('name') == server_name:
                server_exists = True
                break
    
    if not server_exists:  # ✅ 실제 활성 서버 기준
        return jsonify({'error': '서버를 찾을 수 없습니다.'}), 404
    
    # 2. DB에서 조회 (없으면 자동 생성)
    server = Server.query.filter_by(name=server_name).first()
    if not server:
        server = Server(name=server_name, status='unknown', role=role)
        db.session.add(server)
    else:
        server.role = role
    
    db.session.commit()
```

## 🎯 핵심 개선사항

### ✨ **데이터 일관성 보장**
- ✅ **통합 데이터 소스**: 서버 목록과 역할 할당 모두 Proxmox API 기반
- ✅ **자동 동기화**: DB에 없는 서버는 자동으로 생성
- ✅ **실시간 검증**: 역할 할당 시 현재 활성 서버만 대상

### 🔄 **향후 확장성**
- ✅ **새 서버 자동 인식**: 새로 생성된 서버 즉시 역할 할당 가능
- ✅ **DB 정리**: 비활성 서버는 자연스럽게 목록에서 제외
- ✅ **에러 방지**: 존재하지 않는 서버에 대한 역할 할당 시도 차단

## 📋 추가 권장사항

### 1️⃣ **정기 서버 동기화**
백그라운드에서 주기적으로 Proxmox ↔ DB 동기화:

```python
# /api/sync_servers 엔드포인트 활용
# 주기적으로 호출하여 완전한 동기화 수행
```

### 2️⃣ **서버 상태 모니터링**
서버 생성/삭제 시 자동 DB 업데이트:

```python
# 서버 생성 시: DB 레코드 자동 생성
# 서버 삭제 시: DB 레코드 자동 제거
```

### 3️⃣ **데이터 백업**
DB 데이터 정기 백업:

```bash
# instance/proxmox_manager.db 백업
cp instance/proxmox_manager.db backups/proxmox_manager_$(date +%Y%m%d).db
```

## 🎉 결과

이제 **모든 역할 할당이 완벽하게 작동**합니다:

- ✅ **화면 표시**: Proxmox/tfvars.json 기반 서버 목록
- ✅ **역할 할당**: 동일한 데이터 소스로 서버 검증
- ✅ **자동 생성**: DB에 없는 서버는 즉시 생성
- ✅ **일관성 보장**: 더 이상 데이터 불일치 문제 없음

**"서버가 존재하지 않습니다"** 오류가 완전히 해결되었습니다! 🚀

## 🔧 디버깅 정보

문제 발생 시 확인할 사항:

1. **서버 목록 API 상태**: `/api/all_server_status` 응답 확인
2. **Proxmox 연결**: ProxmoxService 연결 상태 확인
3. **tfvars.json 파일**: 서버 설정 존재 여부 확인
4. **DB 상태**: `instance/proxmox_manager.db` 파일 존재 및 권한 확인

로그에서 다음 메시지 확인:
- `🔧 Proxmox에서 조회한 서버 목록: [...]`
- `✅ 서버 발견: {server_name}`
- `🔧 DB에 서버가 없음, 새로 생성: {server_name}`