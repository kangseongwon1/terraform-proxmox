# 역할 할당 문제 해결 가이드

## 🐛 문제 상황

역할 할당 시 "서버가 존재하지 않습니다" 오류가 발생하는 문제가 있었습니다.

### 증상
- 서버 목록에서 역할 드롭다운을 선택하고 '역할 적용' 버튼 클릭
- API 요청 실패: `404 - 서버를 찾을 수 없습니다`
- 실제로는 서버가 DB에 존재함

## 🔍 원인 분석

### 문제 발생 지점
JavaScript에서 서버 이름을 잘못 전달하는 문제였습니다.

```javascript
// 문제 코드 (수정 전)
for (const [name, s] of Object.entries(servers)) {
  const serverRow = `
    <tr data-server="${name}">  // ❌ 잘못된 값
      <td><strong>${s.name}</strong></td>  // ✅ 올바른 서버 이름
    </tr>
  `;
}
```

### 데이터 구조 차이
서버 목록 API(`/api/all_server_status`)는 다음과 같은 구조로 데이터를 반환:

```json
{
  "servers": {
    "vm-101": {           // ← 이것이 name (vmid 기반)
      "name": "web-01",   // ← 이것이 실제 서버 이름
      "status": "running",
      "role": "web"
    }
  }
}
```

- `name` (키): Proxmox VMID 기반 식별자 (예: "vm-101")
- `s.name` (값): 실제 서버 이름 (예: "web-01")

## ✅ 해결 방법

### 1. 테이블 뷰 수정
```javascript
// 수정 전
<tr data-server="${name}">  // vm-101

// 수정 후  
<tr data-server="${s.name}">  // web-01
```

### 2. 카드 뷰 수정
```javascript
// 수정 전
<div class="server-card" data-server="${name}">  // vm-101

// 수정 후
<div class="server-card" data-server="${s.name}">  // web-01
```

### 3. 체크박스 값 수정
```javascript
// 수정 전
<input type="checkbox" value="${name}">  // vm-101

// 수정 후
<input type="checkbox" value="${s.name}">  // web-01
```

### 4. 서버 설정 버튼 수정
```javascript
// 수정 전
onclick="openServerConfig('${name}')"  // vm-101

// 수정 후
onclick="openServerConfig('${s.name}')"  // web-01
```

## 🔧 수정된 파일

### `app/static/instances.js`
- `renderTableView()` 함수의 `data-server` 속성 수정
- `renderCardView()` 함수의 `data-server` 속성 수정
- 체크박스 `value` 속성 수정
- 서버 설정 버튼의 `onclick` 함수 인자 수정

## 🎯 결과

이제 역할 할당이 정상적으로 작동합니다:

1. ✅ **올바른 서버 이름 전달**: `data-server` 속성에 실제 서버 이름 저장
2. ✅ **API 요청 성공**: `/api/assign_role/{server_name}` 호출 시 올바른 이름 전달
3. ✅ **DB 조회 성공**: `Server.query.filter_by(name=server_name)` 정상 작동
4. ✅ **역할 할당 완료**: 서버 역할이 성공적으로 업데이트

## 🚨 주의사항

### 데이터 일관성
서버 목록 API가 반환하는 데이터 구조에서:
- **키 (`name`)**: 내부 식별자 (Proxmox VMID 기반)
- **값 (`s.name`)**: 사용자가 보는 실제 서버 이름

### 다른 기능에 미치는 영향
- ✅ **대량 작업**: 체크박스 값 수정으로 올바른 서버 이름 전달
- ✅ **서버 액션**: `data-server` 속성을 통한 올바른 서버 식별
- ✅ **검색 필터링**: 실제 서버 이름으로 검색 가능

## 🔍 디버깅 팁

역할 할당 문제 발생 시 확인 사항:

1. **브라우저 개발자 도구**: 네트워크 탭에서 API 요청 URL 확인
2. **서버 로그**: `app/routes/servers.py`의 디버깅 로그 확인
3. **데이터 구조**: `console.log`로 서버 객체 구조 확인

```javascript
// 디버깅용 로그
console.log('서버 키:', name);        // vm-101
console.log('서버 객체:', s);         // { name: "web-01", ... }
console.log('실제 이름:', s.name);    // web-01
```

이제 역할 할당이 완벽하게 작동합니다! 🎉