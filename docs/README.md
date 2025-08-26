# 🚀 Proxmox 서버 자동 생성 및 관리 시스템

Flask + Terraform + Ansible을 사용한 Proxmox 기반 서버 자동 생성 및 관리 시스템입니다.

## 📋 프로젝트 개요

### 🎯 목적
- **Proxmox VM 자동 생성/관리**
- **웹 기반 관리 콘솔**
- **백업 관리 시스템**
- **사용자 권한 관리**
- **모니터링 시스템**

### 🏗️ 기술 스택
- **Backend**: Flask (Python)
- **Infrastructure**: Terraform
- **Automation**: Ansible
- **Database**: SQLite
- **Frontend**: HTML/CSS/JavaScript (Bootstrap)
- **Monitoring**: Grafana + Prometheus + Node Exporter

### 📊 현재 상태
- **완성도**: 60%
- **주요 기능**: 서버 생성/삭제, 백업 관리, 사용자 관리
- **진행 중**: 방화벽 설정, Ansible 역할 기반 자동화
- **계획 중**: 모니터링 시스템, 네트워크 토폴로지

## 🚀 주요 기능

### ✅ 완성된 기능
- **서버 관리**
  - VM 생성/삭제/시작/중지/재시작
  - 서버 목록 조회 및 상태 모니터링
  - Terraform 기반 인프라 자동화

- **백업 관리**
  - VM별 백업 생성/복원/삭제
  - 실시간 백업 상태 모니터링
  - 백업 파일 관리

- **사용자 관리**
  - 로그인/로그아웃
  - 역할 기반 권한 관리 (admin, developer, operator, viewer)
  - 사용자 생성/수정/삭제

- **방화벽 관리**
  - 방화벽 그룹 생성/관리
  - VM에 방화벽 그룹 할당
  - 방화벽 규칙 관리

### 🔄 진행 중인 기능
- **Ansible 역할 기반 자동화**
  - 웹서버 (nginx), DB (MySQL), WAS (Tomcat) 자동 설치
  - 역할별 설정 자동화

- **모니터링 시스템**
  - Grafana + Prometheus + Node Exporter
  - 실시간 메트릭 수집 및 시각화

### 📋 계획 중인 기능
- **네트워크 토폴로지 시각화**
  - VM 간 연결 관계 표시
  - 실시간 네트워크 통신 감지

## 🏗️ 시스템 아키텍처

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   웹콘솔        │    │   Proxmox       │    │   Terraform     │
│   (Flask)       │◄──►│   VE            │◄──►│   (인프라 코드) │
│                 │    │                 │    │                 │
│ - 사용자 관리   │    │ - VM 관리       │    │ - VM 생성       │
│ - 백업 관리     │    │ - 스토리지 관리 │    │ - 네트워크 설정 │
│ - 모니터링      │    │ - 백업 관리     │    │ - 디스크 설정   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Ansible       │    │   Grafana       │    │   Node Exporter │
│   (자동화)      │    │   (모니터링)    │    │   (메트릭 수집) │
│                 │    │                 │    │                 │
│ - 소프트웨어 설치│    │ - 대시보드      │    │ - 시스템 메트릭 │
│ - 설정 자동화   │    │ - 알림          │    │ - 네트워크 정보 │
│ - 역할 기반 배포│    │ - 시각화        │    │ - 프로세스 정보 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 📁 프로젝트 구조

```
terraform-proxmox/
├── app/                          # Flask 애플리케이션
│   ├── __init__.py              # 앱 초기화
│   ├── main.py                  # 메인 앱
│   ├── models/                  # 데이터 모델
│   │   ├── user.py             # 사용자 모델
│   │   ├── server.py           # 서버 모델
│   │   └── notification.py     # 알림 모델
│   ├── routes/                  # 라우트
│   │   ├── auth.py             # 인증
│   │   ├── servers.py          # 서버 관리
│   │   ├── backup.py           # 백업 관리
│   │   ├── firewall.py         # 방화벽 관리
│   │   └── admin.py            # 관리자 기능
│   ├── services/                # 비즈니스 로직
│   │   ├── proxmox_service.py  # Proxmox API
│   │   ├── terraform_service.py # Terraform
│   │   ├── ansible_service.py  # Ansible
│   │   └── notification_service.py # 알림
│   ├── static/                  # 정적 파일
│   │   ├── instances.js        # 인스턴스 관리
│   │   ├── backups.js          # 백업 관리
│   │   ├── firewall.js         # 방화벽 관리
│   │   └── modern-servers.css  # 스타일
│   └── templates/               # HTML 템플릿
│       ├── index.html          # 메인 페이지
│       └── partials/           # 부분 템플릿
├── terraform/                   # Terraform 설정
│   ├── main.tf                 # 메인 설정
│   ├── variables.tf            # 변수 정의
│   ├── modules/                # 모듈
│   │   └── server/            # 서버 모듈
│   └── terraform.tfvars.json  # 변수 값
├── ansible/                     # Ansible 설정
│   ├── inventory               # 인벤토리
│   ├── role_playbook.yml      # 플레이북
│   └── roles/                 # 역할
│       ├── web/               # 웹서버 역할
│       ├── db/                # DB 역할
│       └── was/               # WAS 역할
├── docs/                       # 문서
├── requirements.txt            # Python 의존성
├── config.py                  # 설정
├── run.py                     # 실행 스크립트
└── README.md                  # 프로젝트 문서
```

## 🚀 빠른 시작

### 1. 환경 설정
```bash
# 저장소 클론
git clone <repository-url>
cd terraform-proxmox

# 가상환경 생성
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt
```

### 2. 환경 변수 설정
```bash
# .env 파일 생성
cp env_template.txt .env

# .env 파일 편집
nano .env
```

### 3. 데이터베이스 초기화
```bash
python create_tables.py
```

### 4. 애플리케이션 실행
```bash
python run.py
```

### 5. 웹 접속
- URL: http://localhost:5000
- 기본 계정: admin / admin123!

## 📚 문서

- [📋 시스템 아키텍처](ARCHITECTURE.md)
- [🔧 설치 가이드](INSTALLATION.md)
- [📖 API 참조](API_REFERENCE.md)
- [👨‍💻 개발 가이드](DEVELOPMENT.md)
- [🚀 배포 가이드](DEPLOYMENT.md)
- [📊 모니터링 가이드](MONITORING.md)
- [🔧 문제 해결](TROUBLESHOOTING.md)

## 🤝 기여하기

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다. 자세한 내용은 `LICENSE` 파일을 참조하세요.

## 📞 연락처

프로젝트 링크: [https://github.com/username/terraform-proxmox](https://github.com/username/terraform-proxmox)

---

**⭐ 이 프로젝트가 도움이 되었다면 스타를 눌러주세요!**

