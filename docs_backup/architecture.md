# 🏗️ 시스템 아키텍처

## 📋 개요

이 문서는 Proxmox 서버 자동 생성 및 관리 시스템의 전체 아키텍처를 설명합니다.

## 🎯 아키텍처 원칙

### 1. **모듈화 설계**
- 각 컴포넌트는 독립적으로 개발/배포 가능
- 명확한 인터페이스 정의
- 느슨한 결합 (Loose Coupling)

### 2. **확장성**
- 수평적 확장 지원
- 새로운 기능 추가 용이
- 멀티 노드 지원 준비

### 3. **보안**
- 역할 기반 접근 제어 (RBAC)
- API 인증 및 권한 검증
- 환경 변수를 통한 민감 정보 관리

## 🏗️ 전체 시스템 아키텍처

```
┌─────────────────────────────────────────────────────────────────┐
│                        웹 콘솔 (Flask)                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│  │   인증      │  │   서버 관리 │  │   백업 관리 │            │
│  │   (Auth)    │  │   (Server)  │  │   (Backup)  │            │
│  └─────────────┘  └─────────────┘  └─────────────┘            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│  │   방화벽    │  │   사용자    │  │   모니터링  │            │
│  │   (Firewall)│  │   (Admin)   │  │   (Metrics) │            │
│  └─────────────┘  └─────────────┘  └─────────────┘            │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      비즈니스 로직 레이어                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│  │ Proxmox     │  │ Terraform   │  │ Ansible     │            │
│  │ Service     │  │ Service     │  │ Service     │            │
│  └─────────────┘  └─────────────┘  └─────────────┘            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│  │ Notification│  │ Monitoring  │  │ Backup      │            │
│  │ Service     │  │ Service     │  │ Service     │            │
│  └─────────────┘  └─────────────┘  └─────────────┘            │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                        데이터 레이어                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│  │   SQLite    │  │   Proxmox   │  │   Terraform │            │
│  │   Database  │  │   API       │  │   State     │            │
│  └─────────────┘  └─────────────┘  └─────────────┘            │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      인프라 레이어                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│  │   Proxmox   │  │   Terraform │  │   Ansible   │            │
│  │   VE        │  │   (IaC)     │  │   (Config)  │            │
│  └─────────────┘  └─────────────┘  └─────────────┘            │
└─────────────────────────────────────────────────────────────────┘
```

## 🔧 컴포넌트별 상세 아키텍처

### 1. **웹 콘솔 (Flask)**

#### 구조
```
app/
├── __init__.py              # 애플리케이션 팩토리
├── main.py                  # 메인 애플리케이션
├── models/                  # 데이터 모델
│   ├── user.py             # 사용자 모델
│   ├── server.py           # 서버 모델
│   └── notification.py     # 알림 모델
├── routes/                  # 라우트 (Blueprint)
│   ├── auth.py             # 인증 라우트
│   ├── servers.py          # 서버 관리 라우트
│   ├── backup.py           # 백업 관리 라우트
│   ├── firewall.py         # 방화벽 관리 라우트
│   └── admin.py            # 관리자 라우트
├── services/                # 비즈니스 로직
│   ├── proxmox_service.py  # Proxmox API 서비스
│   ├── terraform_service.py # Terraform 서비스
│   ├── ansible_service.py  # Ansible 서비스
│   └── notification_service.py # 알림 서비스
├── static/                  # 정적 파일
└── templates/               # HTML 템플릿
```

#### 특징
- **Blueprint 기반 모듈화**: 각 기능별로 독립적인 라우트
- **서비스 레이어**: 비즈니스 로직과 데이터 접근 분리
- **템플릿 상속**: Jinja2 템플릿 엔진 사용
- **정적 파일 관리**: CSS, JS 파일 분리

### 2. **데이터 모델**

#### 사용자 모델 (User)
```python
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default='developer')
    permissions = db.relationship('UserPermission', backref='user')
```

#### 서버 모델 (Server)
```python
class Server(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    vmid = db.Column(db.Integer)
    cpu = db.Column(db.Integer)
    memory = db.Column(db.Integer)
    status = db.Column(db.String(20))
    firewall_group = db.Column(db.String(100))
```

#### 권한 시스템
```python
class UserPermission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    permission = db.Column(db.String(50), nullable=False)
```

### 3. **서비스 레이어**

#### ProxmoxService
```python
class ProxmoxService:
    def __init__(self):
        self.endpoint = config['PROXMOX_ENDPOINT']
        self.username = config['PROXMOX_USERNAME']
        self.password = config['PROXMOX_PASSWORD']
    
    def get_all_vms(self) -> Dict
    def create_vm(self, vm_config: Dict) -> bool
    def delete_vm(self, vmid: int) -> bool
    def get_vm_status(self, vmid: int) -> str
```

#### TerraformService
```python
class TerraformService:
    def __init__(self, terraform_dir: str = "terraform"):
        self.terraform_dir = terraform_dir
    
    def create_server_config(self, server_data: Dict) -> bool
    def deploy_infrastructure(self) -> Tuple[bool, str]
    def destroy_infrastructure(self) -> Tuple[bool, str]
```

#### AnsibleService
```python
class AnsibleService:
    def __init__(self, ansible_dir: str = "ansible"):
        self.ansible_dir = ansible_dir
    
    def run_role_for_server(self, server_name: str, role: str) -> Tuple[bool, str]
    def create_inventory(self, servers: List[Dict]) -> bool
```

### 4. **인프라 자동화**

#### Terraform 구조
```
terraform/
├── main.tf                 # 메인 설정
├── variables.tf            # 변수 정의
├── outputs.tf              # 출력 정의
├── providers.tf            # 프로바이더 설정
├── modules/                # 모듈
│   └── server/            # 서버 모듈
│       ├── main.tf        # 서버 생성
│       └── variables.tf   # 서버 변수
└── terraform.tfvars.json  # 변수 값
```

#### Ansible 구조
```
ansible/
├── inventory               # 인벤토리 파일
├── role_playbook.yml      # 메인 플레이북
├── roles/                 # 역할
│   ├── web/              # 웹서버 역할
│   ├── db/               # 데이터베이스 역할
│   ├── was/              # WAS 역할
│   └── java/             # Java 역할
└── templates/             # 템플릿
```

## 🔄 데이터 흐름

### 1. **서버 생성 흐름**
```
1. 웹 콘솔에서 서버 생성 요청
   ↓
2. TerraformService.create_server_config()
   ↓
3. terraform.tfvars.json 업데이트
   ↓
4. TerraformService.deploy_infrastructure()
   ↓
5. Proxmox에서 VM 생성
   ↓
6. AnsibleService.run_role_for_server()
   ↓
7. 소프트웨어 설치 및 설정
   ↓
8. 데이터베이스에 서버 정보 저장
```

### 2. **백업 생성 흐름**
```
1. 웹 콘솔에서 백업 생성 요청
   ↓
2. ProxmoxService.create_backup()
   ↓
3. 백그라운드에서 백업 진행
   ↓
4. 파일 모니터링으로 완료 감지
   ↓
5. 백업 상태 업데이트
   ↓
6. 알림 생성
```

### 3. **모니터링 데이터 흐름**
```
1. Node Exporter가 메트릭 수집
   ↓
2. Prometheus가 메트릭 저장
   ↓
3. Grafana가 메트릭 시각화
   ↓
4. 웹 콘솔에서 Grafana API 호출
   ↓
5. 메트릭 데이터 표시
```

## 🔐 보안 아키텍처

### 1. **인증 시스템**
- **Flask-Login**: 세션 기반 인증
- **비밀번호 해싱**: Werkzeug의 generate_password_hash 사용
- **세션 관리**: 보안 쿠키 설정

### 2. **권한 시스템**
- **역할 기반 접근 제어 (RBAC)**
- **세분화된 권한**: 각 기능별 권한 정의
- **데코레이터**: @permission_required 데코레이터

### 3. **API 보안**
- **인증 토큰**: Proxmox API 토큰 관리
- **HTTPS**: 모든 통신 암호화
- **입력 검증**: 모든 사용자 입력 검증

## 📊 성능 아키텍처

### 1. **데이터베이스 최적화**
- **인덱싱**: 자주 조회되는 컬럼에 인덱스
- **쿼리 최적화**: N+1 문제 방지
- **연결 풀링**: 데이터베이스 연결 재사용

### 2. **캐싱 전략**
- **로컬 스토리지**: 브라우저 캐싱
- **메모리 캐싱**: 자주 사용되는 데이터 캐싱
- **API 캐싱**: Proxmox API 응답 캐싱

### 3. **비동기 처리**
- **백그라운드 작업**: 긴 작업은 별도 스레드에서 처리
- **폴링**: 실시간 상태 업데이트
- **이벤트 기반**: 상태 변화 시 알림

## 🔄 확장성 고려사항

### 1. **수평적 확장**
- **로드 밸런서**: 여러 웹 콘솔 인스턴스
- **데이터베이스 분리**: 읽기/쓰기 분리
- **세션 공유**: Redis를 통한 세션 공유

### 2. **멀티 노드 지원**
- **Proxmox 클러스터**: 여러 Proxmox 노드 관리
- **노드 선택**: VM 배치 노드 선택 로직
- **상태 동기화**: 노드 간 상태 동기화

### 3. **마이크로서비스 전환**
- **API 게이트웨이**: 통합 API 엔드포인트
- **서비스 분리**: 각 기능별 독립 서비스
- **메시지 큐**: 서비스 간 통신

## 🚀 배포 아키텍처

### 1. **개발 환경**
```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   개발자    │    │   Flask     │    │   Proxmox   │
│   PC        │◄──►│   Dev       │◄──►│   Dev       │
└─────────────┘    └─────────────┘    └─────────────┘
```

### 2. **운영 환경**
```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   사용자    │    │   Nginx     │    │   Proxmox   │
│   브라우저  │◄──►│   + Flask   │◄──►│   Prod      │
└─────────────┘    └─────────────┘    └─────────────┘
```

### 3. **컨테이너 배포**
```yaml
# docker-compose.yml
version: '3.8'
services:
  web:
    build: .
    ports:
      - "5000:5000"
    environment:
      - FLASK_ENV=production
    volumes:
      - ./data:/app/data
```

## 📈 모니터링 아키텍처

### 1. **메트릭 수집**
- **Node Exporter**: 시스템 메트릭 수집
- **Prometheus**: 시계열 데이터 저장
- **Grafana**: 메트릭 시각화

### 2. **로그 관리**
- **구조화된 로깅**: JSON 형식 로그
- **로그 레벨**: DEBUG, INFO, WARNING, ERROR
- **로그 로테이션**: 파일 크기/시간 기반 로테이션

### 3. **알림 시스템**
- **임계값 기반**: CPU, 메모리, 디스크 사용률
- **상태 기반**: 서비스 다운, 백업 실패
- **채널**: 웹 콘솔, 이메일, Slack

---

이 문서는 시스템의 전체적인 아키텍처를 설명합니다. 각 컴포넌트의 상세한 구현은 해당 문서를 참조하세요. 