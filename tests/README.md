# 🧪 Proxmox Manager 테스트 가이드

이 디렉토리는 Proxmox Manager 프로젝트의 모든 테스트를 포함합니다.

## 📋 테스트 구조

```
tests/
├── integration_test_suite.py    # 통합 테스트 스위트
├── functional_test_suite.py     # 기능별 테스트 스위트
├── run_tests.py                 # 테스트 실행기
├── unit/                        # 단위 테스트
│   ├── test_*.py               # 개별 단위 테스트 파일들
└── README.md                   # 이 파일
```

## 🚀 테스트 실행 방법

### 1. 전체 테스트 실행

#### Linux/Mac
```bash
# 시스템 테스트 스크립트 실행
./test_system.sh

# 또는 직접 실행
python tests/run_tests.py --all
```

#### Windows
```powershell
# PowerShell 스크립트 실행
.\test_system.ps1

# 또는 직접 실행
python tests/run_tests.py --all
```

### 2. 개별 테스트 실행

```bash
# 통합 테스트만 실행
python tests/run_tests.py --integration

# 기능별 테스트만 실행
python tests/run_tests.py --functional

# 단위 테스트만 실행
python tests/run_tests.py --unit

# 보고서만 생성
python tests/run_tests.py --report-only
```

### 3. 개별 테스트 스크립트 실행

```bash
# 통합 테스트 스위트 직접 실행
python tests/integration_test_suite.py

# 기능별 테스트 스위트 직접 실행
python tests/functional_test_suite.py
```

## 📊 테스트 종류

### 🔧 통합 테스트 (Integration Tests)

**목적**: 시스템의 모든 구성 요소가 함께 올바르게 작동하는지 확인

**테스트 항목**:
- ✅ 환경 설정 (필수 파일, Python 패키지)
- ✅ 데이터베이스 연결 및 테이블 구조
- ✅ Flask 애플리케이션 실행 상태
- ✅ 사용자 인증 시스템
- ✅ API 엔드포인트 응답
- ✅ Terraform 통합
- ✅ Ansible 통합
- ✅ 모니터링 시스템 (Prometheus + Grafana)
- ✅ Vault 통합
- ✅ 백업 시스템
- ✅ 권한 시스템

**성공 기준**: 80% 이상 통과

### ⚙️ 기능별 테스트 (Functional Tests)

**목적**: 각 기능별로 상세한 동작 확인

**테스트 항목**:
- 🖥️ 서버 관리 기능
- 💾 백업 관리 기능
- 👥 사용자 관리 기능
- 📊 모니터링 시스템 기능
- 🔥 방화벽 관리 기능
- 🔔 알림 시스템 기능
- 🗄️ 데이터베이스 작업
- 🏗️ Terraform 작업
- ⚙️ Ansible 작업
- 📊 모니터링 작업

**성공 기준**: 70% 이상 통과

### 🧪 단위 테스트 (Unit Tests)

**목적**: 개별 함수나 클래스의 동작 확인

**위치**: `tests/unit/` 디렉토리

**파일 명명 규칙**: `test_*.py`

## 📄 테스트 보고서

테스트 실행 후 다음 위치에 보고서가 생성됩니다:

```
logs/
├── integration_test.log              # 통합 테스트 로그
├── integration_test_report.json      # 통합 테스트 보고서
├── functional_test.log               # 기능별 테스트 로그
├── functional_test_report.json       # 기능별 테스트 보고서
└── overall_test_report.json          # 전체 테스트 보고서
```

### 보고서 구조

```json
{
  "timestamp": "2024-01-01T00:00:00",
  "summary": {
    "total_tests": 20,
    "passed_tests": 18,
    "failed_tests": 2,
    "success_rate": 90.0,
    "overall_success": true
  },
  "test_results": [
    {
      "test_name": "environment_setup",
      "success": true,
      "message": "환경 설정 확인 완료",
      "details": {},
      "timestamp": "2024-01-01T00:00:00"
    }
  ]
}
```

## 🔧 테스트 환경 요구사항

### 필수 조건
- Python 3.8+
- Flask 애플리케이션이 실행 가능한 상태
- 필요한 Python 패키지들이 설치된 상태
- 프로젝트 루트 디렉토리에서 실행

### 권장 조건
- Flask 애플리케이션이 실행 중인 상태 (자동 시작 가능)
- Proxmox 서버에 접근 가능한 상태
- Vault 서비스가 실행 중인 상태

## 🐛 문제 해결

### 일반적인 문제들

#### 1. Flask 애플리케이션이 실행되지 않음
```bash
# Flask 앱을 수동으로 시작
python run.py

# 또는 백그라운드에서 시작
nohup python run.py > logs/flask_app.log 2>&1 &
```

#### 2. 데이터베이스 파일이 없음
```bash
# 데이터베이스 초기화
python database.py
```

#### 3. 가상환경이 활성화되지 않음
```bash
# 가상환경 활성화
source venv/bin/activate  # Linux/Mac
# 또는
venv\Scripts\activate     # Windows
```

#### 4. 필수 패키지가 설치되지 않음
```bash
# 패키지 설치
pip install -r requirements.txt
```

### 로그 확인

테스트 실행 중 문제가 발생하면 다음 로그 파일들을 확인하세요:

- `logs/integration_test.log`: 통합 테스트 로그
- `logs/functional_test.log`: 기능별 테스트 로그
- `logs/flask_app.log`: Flask 애플리케이션 로그 (자동 시작 시)

## 📈 테스트 확장

### 새로운 테스트 추가

1. **통합 테스트 추가**:
   `tests/integration_test_suite.py`의 `IntegrationTestSuite` 클래스에 새 메서드 추가

2. **기능별 테스트 추가**:
   `tests/functional_test_suite.py`의 `FunctionalTestSuite` 클래스에 새 메서드 추가

3. **단위 테스트 추가**:
   `tests/unit/` 디렉토리에 `test_*.py` 파일 생성

### 테스트 메서드 구조

```python
def test_new_feature(self) -> bool:
    """새 기능 테스트"""
    logger.info("새 기능 테스트 시작...")
    
    try:
        # 테스트 로직
        result = some_function()
        
        if result:
            self.log_test_result("new_feature", True, "새 기능 테스트 성공")
            return True
        else:
            self.log_test_result("new_feature", False, "새 기능 테스트 실패")
            return False
            
    except Exception as e:
        self.log_test_result("new_feature", False, f"테스트 실행 중 오류: {e}")
        return False
```

## 🎯 테스트 모범 사례

1. **독립성**: 각 테스트는 다른 테스트에 의존하지 않아야 함
2. **재현성**: 동일한 조건에서 항상 동일한 결과를 보여야 함
3. **명확성**: 테스트 이름과 메시지가 명확해야 함
4. **완전성**: 모든 주요 기능을 테스트해야 함
5. **유지보수성**: 코드 변경 시 테스트도 함께 업데이트해야 함

## 📞 지원

테스트 관련 문제가 있으면 다음을 확인하세요:

1. 이 README 파일의 문제 해결 섹션
2. 프로젝트의 메인 README.md
3. `docs/` 디렉토리의 관련 문서들
4. 테스트 로그 파일들
