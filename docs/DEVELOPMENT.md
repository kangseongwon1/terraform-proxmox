# 👨‍💻 개발 가이드

## 📋 개요

이 문서는 Proxmox 서버 자동 생성 및 관리 시스템의 개발 환경 설정과 개발 가이드라인을 설명합니다.

## 🛠️ 개발 환경 설정

### 1. 필수 소프트웨어

#### Python 환경
```bash
# Python 3.8+ 설치 확인
python3 --version

# 가상환경 도구
pip install virtualenv
```

#### 개발 도구
```bash
# 코드 포맷팅
pip install black isort

# 린팅
pip install flake8 pylint

# 테스트
pip install pytest pytest-flask

# 타입 체크
pip install mypy
```

#### 인프라 도구
```bash
# Terraform 설치
# https://www.terraform.io/downloads.html

# Ansible 설치
pip install ansible

# Proxmox VE 접근 권한
# - API 토큰 또는 사용자 계정
# - 네트워크 접근 권한
```

### 2. 프로젝트 설정

#### 저장소 클론
```bash
git clone <repository-url>
cd terraform-proxmox
```

#### 가상환경 생성
```bash
# 가상환경 생성
python3 -m venv venv

# 가상환경 활성화
source venv/bin/activate  # Linux/Mac
# 또는
venv\Scripts\activate     # Windows
```

#### 의존성 설치
```bash
# 기본 의존성
pip install -r requirements.txt

# 개발 의존성
pip install -r requirements-dev.txt
```

#### 환경 변수 설정
```bash
# 환경 변수 파일 복사
cp env_template.txt .env

# .env 파일 편집
nano .env
```

#### 데이터베이스 초기화
```bash
python create_tables.py
```

## 🏗️ 프로젝트 구조 이해

### 디렉토리 구조
```
terraform-proxmox/
├── app/                    # Flask 애플리케이션
│   ├── __init__.py        # 앱 팩토리
│   ├── models/            # 데이터 모델
│   ├── routes/            # 라우트 (Blueprint)
│   ├── services/          # 비즈니스 로직
│   ├── static/            # 정적 파일
│   └── templates/         # HTML 템플릿
├── terraform/             # Terraform 설정
├── ansible/               # Ansible 설정
├── docs/                  # 문서
├── tests/                 # 테스트
└── scripts/               # 유틸리티 스크립트
```

### 핵심 컴포넌트

#### 1. Flask 애플리케이션 (`app/`)
- **Blueprint 기반 모듈화**: 각 기능별로 독립적인 라우트
- **서비스 레이어**: 비즈니스 로직과 데이터 접근 분리
- **모델-뷰-컨트롤러 (MVC)**: 명확한 책임 분리

#### 2. Terraform (`terraform/`)
- **모듈화**: 재사용 가능한 인프라 모듈
- **변수 관리**: 환경별 설정 분리
- **상태 관리**: 인프라 상태 추적

#### 3. Ansible (`ansible/`)
- **역할 기반**: 기능별 역할 분리
- **템플릿**: 동적 설정 파일 생성
- **인벤토리**: 서버 목록 관리

## 🔧 개발 워크플로우

### 1. 기능 개발 프로세스

#### 새 기능 개발
```bash
# 1. 브랜치 생성
git checkout -b feature/new-feature

# 2. 개발 작업
# - 코드 작성
# - 테스트 작성
# - 문서 업데이트

# 3. 커밋
git add .
git commit -m "feat: 새로운 기능 추가"

# 4. 푸시 및 PR 생성
git push origin feature/new-feature
```

#### 버그 수정
```bash
# 1. 브랜치 생성
git checkout -b fix/bug-description

# 2. 수정 작업
# - 버그 수정
# - 테스트 추가
# - 문서 업데이트

# 3. 커밋
git commit -m "fix: 버그 수정 설명"
```

### 2. 코드 품질 관리

#### 코드 포맷팅
```bash
# Black으로 코드 포맷팅
black app/ tests/

# isort로 import 정렬
isort app/ tests/
```

#### 린팅
```bash
# flake8으로 코드 검사
flake8 app/ tests/

# pylint로 코드 분석
pylint app/
```

#### 타입 체크
```bash
# mypy로 타입 체크
mypy app/
```

### 3. 테스트

#### 테스트 실행
```bash
# 전체 테스트 실행
pytest

# 특정 테스트 실행
pytest tests/test_servers.py

# 커버리지와 함께 실행
pytest --cov=app tests/
```

#### 테스트 작성 가이드
```python
# tests/test_servers.py
import pytest
from app import create_app, db
from app.models.server import Server

@pytest.fixture
def app():
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

def test_create_server(client):
    """서버 생성 테스트"""
    response = client.post('/api/servers', json={
        'name': 'test-server',
        'cpu': 2,
        'memory': 4096
    })
    assert response.status_code == 200
    assert response.json['success'] == True
```

## 📝 코딩 스타일 가이드

### 1. Python 스타일

#### 명명 규칙
```python
# 클래스: PascalCase
class ServerManager:
    pass

# 함수/변수: snake_case
def create_server():
    server_name = "web-server-01"

# 상수: UPPER_SNAKE_CASE
MAX_RETRY_COUNT = 3
DEFAULT_TIMEOUT = 30
```

#### 함수 작성
```python
def create_server(server_config: Dict[str, Any]) -> Tuple[bool, str]:
    """
    서버를 생성합니다.
    
    Args:
        server_config: 서버 설정 정보
        
    Returns:
        Tuple[bool, str]: (성공 여부, 메시지)
    """
    try:
        # 구현 로직
        return True, "서버 생성 성공"
    except Exception as e:
        return False, f"서버 생성 실패: {str(e)}"
```

#### 에러 처리
```python
def safe_api_call(func):
    """API 호출을 안전하게 처리하는 데코레이터"""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except requests.RequestException as e:
            logger.error(f"API 호출 실패: {e}")
            return None
        except Exception as e:
            logger.error(f"예상치 못한 오류: {e}")
            return None
    return wrapper
```

### 2. Flask 스타일

#### 라우트 작성
```python
@bp.route('/api/servers', methods=['POST'])
@login_required
@permission_required('create_server')
def create_server():
    """서버 생성 API"""
    try:
        data = request.get_json()
        
        # 입력 검증
        if not data.get('name'):
            return jsonify({'error': '서버 이름이 필요합니다.'}), 400
        
        # 비즈니스 로직
        success, message = server_service.create_server(data)
        
        if success:
            return jsonify({'success': True, 'message': message})
        else:
            return jsonify({'error': message}), 500
            
    except Exception as e:
        logger.error(f"서버 생성 실패: {e}")
        return jsonify({'error': '내부 서버 오류'}), 500
```

#### 서비스 레이어
```python
class ServerService:
    """서버 관리 서비스"""
    
    def __init__(self):
        self.proxmox_service = ProxmoxService()
        self.terraform_service = TerraformService()
    
    def create_server(self, server_data: Dict) -> Tuple[bool, str]:
        """서버 생성"""
        try:
            # 1. Terraform 설정 생성
            config_success = self.terraform_service.create_server_config(server_data)
            if not config_success:
                return False, "Terraform 설정 생성 실패"
            
            # 2. 인프라 배포
            deploy_success, deploy_message = self.terraform_service.deploy_infrastructure()
            if not deploy_success:
                return False, f"인프라 배포 실패: {deploy_message}"
            
            # 3. 데이터베이스 저장
            self._save_server_to_db(server_data)
            
            return True, "서버 생성 완료"
            
        except Exception as e:
            logger.error(f"서버 생성 중 오류: {e}")
            return False, str(e)
```

### 3. 프론트엔드 스타일

#### JavaScript 작성
```javascript
// 모듈 패턴 사용
const ServerManager = (function() {
    'use strict';
    
    // private 변수
    let serverList = [];
    
    // private 함수
    function validateServerData(data) {
        if (!data.name) {
            throw new Error('서버 이름이 필요합니다.');
        }
        return true;
    }
    
    // public API
    return {
        createServer: function(serverData) {
            try {
                validateServerData(serverData);
                
                return $.ajax({
                    url: '/api/servers',
                    method: 'POST',
                    contentType: 'application/json',
                    data: JSON.stringify(serverData)
                });
            } catch (error) {
                console.error('서버 생성 실패:', error);
                return Promise.reject(error);
            }
        },
        
        getServers: function() {
            return $.get('/api/servers');
        }
    };
})();
```

#### CSS 작성
```css
/* BEM 방법론 사용 */
.server-list {
    padding: 20px;
}

.server-list__item {
    border: 1px solid #ddd;
    margin-bottom: 10px;
    padding: 15px;
}

.server-list__item--active {
    border-color: #007bff;
    background-color: #f8f9fa;
}

.server-list__name {
    font-weight: bold;
    color: #333;
}

.server-list__status {
    float: right;
    padding: 2px 8px;
    border-radius: 3px;
}

.server-list__status--running {
    background-color: #28a745;
    color: white;
}
```

## 🔍 디버깅 가이드

### 1. 로깅 설정

#### 로그 레벨 설정
```python
import logging

# 로그 설정
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)
```

#### 로그 사용
```python
def create_server(server_data):
    logger.info(f"서버 생성 시작: {server_data['name']}")
    
    try:
        # 구현 로직
        logger.debug("Terraform 설정 생성 중...")
        result = terraform_service.create_config(server_data)
        
        if result:
            logger.info(f"서버 생성 성공: {server_data['name']}")
        else:
            logger.error(f"서버 생성 실패: {server_data['name']}")
            
    except Exception as e:
        logger.exception(f"서버 생성 중 예외 발생: {e}")
        raise
```

### 2. 디버깅 도구

#### Flask Debug 모드
```python
# run.py
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
```

#### 브라우저 개발자 도구
```javascript
// 콘솔 로깅
console.log('디버그 정보:', data);
console.error('에러 정보:', error);

// 브레이크포인트
debugger;
```

#### API 테스트
```bash
# curl을 사용한 API 테스트
curl -X POST http://localhost:5000/api/servers \
  -H "Content-Type: application/json" \
  -d '{"name": "test-server", "cpu": 2, "memory": 4096}'
```

## 🚀 배포 준비

### 1. 프로덕션 설정

#### 환경 변수
```bash
# .env.production
FLASK_ENV=production
DEBUG=False
SECRET_KEY=your-production-secret-key
PROXMOX_ENDPOINT=https://your-proxmox-server:8006
PROXMOX_USERNAME=root@pam
PROXMOX_PASSWORD=your-secure-password
```

#### 설정 파일
```python
# config.py
class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Strict'
    
    # 로깅 설정
    LOG_LEVEL = 'INFO'
    LOG_FILE = '/var/log/proxmox-manager/app.log'
```

### 2. 성능 최적화

#### 데이터베이스 최적화
```python
# 데이터베이스 연결 풀 설정
SQLALCHEMY_ENGINE_OPTIONS = {
    'pool_size': 10,
    'pool_recycle': 3600,
    'pool_pre_ping': True
}
```

#### 캐싱 설정
```python
# Redis 캐싱 (선택사항)
from flask_caching import Cache

cache = Cache(config={
    'CACHE_TYPE': 'redis',
    'CACHE_REDIS_URL': 'redis://localhost:6379/0'
})
```

## 📚 학습 리소스

### 1. 필수 지식
- **Flask**: [Flask 공식 문서](https://flask.palletsprojects.com/)
- **Terraform**: [Terraform 공식 문서](https://www.terraform.io/docs)
- **Ansible**: [Ansible 공식 문서](https://docs.ansible.com/)
- **Proxmox API**: [Proxmox API 문서](https://pve.proxmox.com/pve-docs/api-viewer/)

### 2. 추가 학습
- **Python**: [Python 공식 튜토리얼](https://docs.python.org/3/tutorial/)
- **SQLAlchemy**: [SQLAlchemy 문서](https://docs.sqlalchemy.org/)
- **JavaScript**: [MDN JavaScript 가이드](https://developer.mozilla.org/en-US/docs/Web/JavaScript)
- **CSS**: [MDN CSS 가이드](https://developer.mozilla.org/en-US/docs/Web/CSS)

### 3. 개발 도구
- **VS Code**: 추천 IDE
- **Postman**: API 테스트 도구
- **Docker**: 컨테이너화
- **Git**: 버전 관리

## 🤝 기여 가이드

### 1. 이슈 리포트
- 명확한 제목과 설명
- 재현 가능한 단계
- 예상 동작과 실제 동작
- 환경 정보 (OS, Python 버전 등)

### 2. 풀 리퀘스트
- 명확한 설명
- 테스트 코드 포함
- 문서 업데이트
- 코드 리뷰 요청

### 3. 커밋 메시지
```
feat: 새로운 기능 추가
fix: 버그 수정
docs: 문서 업데이트
style: 코드 스타일 변경
refactor: 코드 리팩토링
test: 테스트 추가
chore: 빌드 프로세스 변경
```

---

이 문서는 개발 환경 설정과 개발 가이드라인을 제공합니다. 추가 질문이 있으면 팀에 문의하세요.

