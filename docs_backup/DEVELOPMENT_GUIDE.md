# 개발 가이드 (Development Guide)

## 아키텍처 개선 완료 ✅

### **새로운 구조**

```
app/routes/
├── main.py      # 순수 렌더링만 (HTML 페이지)
├── api.py       # 모든 API 엔드포인트 (/api/ 접두사)
└── auth.py      # 인증 관련 (로그인/로그아웃)
```

### **핵심 원칙**

- ✅ **API는 모두 `api.py`에** (`/api/` 접두사)
- ✅ **렌더링은 모두 `main.py`에**
- ✅ **호환성 엔드포인트로 기존 기능 유지**
- ✅ **중복 제거 및 단일 책임 원칙**

### **1. 새로운 API 개발 시 표준 패턴**

```python
# app/routes/api.py에 추가
@bp.route('/api/example', methods=['GET'])
@login_required  # 또는 @permission_required('specific_permission')
def get_example():
    """예시 API"""
    try:
        # 비즈니스 로직
        return jsonify({'data': 'example'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/api/example', methods=['POST'])
@permission_required('create_example')
def create_example():
    """예시 생성 API"""
    try:
        data = request.get_json()
        # 생성 로직
        return jsonify({'success': True, 'message': '생성 완료'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
```

### **2. 호환성 엔드포인트 추가 (필요시)**

```python
# app/routes/main.py에 추가 (기존 프론트엔드 호환용)
@bp.route('/example', methods=['GET'])
@login_required
def get_example_compat():
    """예시 API (호환성)"""
    try:
        from app.routes.api import get_example
        return get_example()
    except Exception as e:
        print(f"💥 /example 호환성 엔드포인트 오류: {str(e)}")
        return jsonify({'error': str(e)}), 500
```

### **3. JavaScript 파일 표준 구조**

```javascript
// example.js
$(function() {
  // 중복 실행 방지 플래그
  if (window.exampleInitialized) {
    console.log('[example.js] 이미 초기화됨, 중복 실행 방지');
    return;
  }
  window.exampleInitialized = true;
  
  console.log('[example.js] example.js loaded');
  
  // 전역 함수로 정의 (loadSPA에서 재실행 가능)
  window.loadExampleData = function() {
    console.log('[example.js] loadExampleData 호출');
    // API 호출 (/api/ 접두사 사용)
    $.get('/api/example', function(data) {
      // 데이터 처리
    });
  };
  
  // 초기 로드 실행
  loadExampleData();
});
```

### **4. loadSPA 함수에 추가할 재실행 로직**

```javascript
// app/templates/index.html의 loadSPA 함수에 추가
} else if (scriptName === 'example.js' && typeof window.exampleInitialized !== 'undefined') {
  console.log(`[loadSPA] example.js 재초기화 실행`);
  if (typeof loadExampleData === 'function') {
    setTimeout(function() {
      console.log('[loadSPA] loadExampleData 재실행');
      loadExampleData();
    }, 100);
  }
}
```

### **5. 체크리스트**

새로운 기능 개발 시 다음 항목들을 확인하세요:

- [ ] **API 엔드포인트**: `api.py`에 `/api/` 접두사로 추가
- [ ] **호환성 엔드포인트**: 기존 프론트엔드 호환을 위해 `main.py`에 추가
- [ ] **JavaScript 파일**: 중복 실행 방지 로직 추가
- [ ] **전역 함수**: `window.loadExampleData` 형태로 정의
- [ ] **loadSPA 재실행**: `index.html`에 재실행 로직 추가
- [ ] **권한 체크**: `@login_required` 또는 `@permission_required` 추가
- [ ] **예외 처리**: 모든 API에 try-catch 블록 추가
- [ ] **로깅**: 디버깅을 위한 print 문 추가

### **6. 권한 관련 주의사항**

- **일반 사용자 접근**: `@login_required` 사용
- **관리자 전용**: `@permission_required('manage_users')` 사용
- **현재 사용자 정보**: `/api/current-user` 엔드포인트 사용
- **전체 사용자 목록**: `/api/users` 엔드포인트 사용 (관리자만)

### **7. 네비게이션 링크 추가 시**

```javascript
// app/templates/index.html에 추가
} else if (href === '#example') {
  loadSPA('/example/content', '/static/example.js');
}
```

### **8. 장점**

**개발자 관점:**
- ✅ **단일 파일**: API 문제 → `api.py`만 확인
- ✅ **명확한 역할**: 렌더링 vs API 명확히 구분
- ✅ **중복 제거**: 같은 로직이 한 곳에만 존재
- ✅ **확장성**: 새로운 API는 `api.py`에만 추가

**유지보수 관점:**
- ✅ **문제 추적**: 404 에러 → `api.py` 확인
- ✅ **코드 검색**: 특정 기능 → 한 파일에서만 검색
- ✅ **테스트**: API 테스트는 `api.py`만 대상

### **9. 향후 개선 방향**

**단계적 마이그레이션:**
1. **현재**: 호환성 엔드포인트로 기존 기능 유지
2. **향후**: 프론트엔드에서 `/api/` 접두사 사용으로 전환
3. **최종**: 호환성 엔드포인트 제거

이 표준을 따르면 네비게이션 클릭 시 동적 콘텐츠가 정상적으로 로드되고, 유지보수성이 크게 향상됩니다. 