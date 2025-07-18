# 🚀 Proxmox 서버 자동 생성 시스템

Flask + Terraform + Ansible을 사용한 Proxmox 기반 서버 자동 생성 및 관리 시스템입니다.

## 📁 프로젝트 구조

---
### [전체 코드 구조 및 역할 요약]

- **Python(Flask)**: `app.py`(웹 UI 및 API 서버), `templates/`(웹 인터페이스 템플릿)
- **Terraform**: `terraform/`(Proxmox VM 자동화 인프라 코드), `modules/server/`(서버 VM 생성 모듈)
- **Ansible**: `ansible/`(서버 소프트웨어 자동 설치 및 설정), `roles/`(nginx, db, java 등 역할별 자동화), `templates/`(설정 템플릿)
- **기타**: `setup.sh`(환경 자동 세팅), `requirements.txt`(Python 의존성), `venv/`(가상환경)

#### 전체 동작 흐름
1. 환경설정(.env)
2. Flask 웹에서 서버 생성 요청
3. Terraform으로 VM 생성
4. Ansible로 소프트웨어 자동 설치/설정
5. 웹 UI/REST API로 상태 및 제어
---

```
terraform-proxmox/
├── app.py                    # Flask 메인 애플리케이션
├── requirements.txt          # Python 의존성
├── .env                     # 환경 설정 파일
├── setup.sh                 # 설치 스크립트
├── README.md                # 프로젝트 문서
├── templates/               # Flask HTML 템플릿
│   └── index.html           # 메인 웹 인터페이스
├── ansible/                 # Ansible 설정
│   ├── inventory            # Ansible 인벤토리
│   ├── playbook.yml         # Ansible 플레이북
│   └── templates/           # Ansible 템플릿
│       ├── nginx.conf.j2    # Nginx 설정 템플릿
│       └── nginx-rocky.conf.j2
├── terraform/               # Terraform 설정
│   ├── main.tf              # 메인 Terraform 설정
│   ├── variables.tf         # 변수 정의
│   ├── outputs.tf           # 출력 정의
│   ├── providers.tf         # 프로바이더 설정
│   ├── terraform.tfvars.json # 변수 값 (JSON 형식)
│   └── modules/             # Terraform 모듈
│       └── server/          # 서버 모듈
│           ├── main.tf      # 서버 리소스 정의
│           └── variables.tf # 서버 모듈 변수
└── venv/                    # Python 가상환경
```

## 🛠️ 시스템 요구사항

### 필수 소프트웨어
- Python 3.8+
- Terraform 1.0+
- Ansible 2.9+
- Docker & Docker Compose (선택사항)

### 환경 요구사항
- Proxmox VE 6.0+
- Ubuntu/Debian 기반 템플릿 VM
- SSH 접근이 가능한 네트워크 환경

## 🚀 빠른 시작

### 1. 설치

```bash
# 리포지토리 클론
git clone <repository-url>
cd terraform-proxmox

# 자동 설치 스크립트 실행
chmod +x setup.sh
./setup.sh
```

### 2. 환경 설정

`.env` 파일을 수정하여 Proxmox 설정을 입력합니다:

```env
PROXMOX_ENDPOINT=https://your-proxmox-server:8006
PROXMOX_USERNAME=root@pam
PROXMOX_PASSWORD=your-password
PROXMOX_NODE=pve
PROXMOX_DATASTORE=local-lvm
PROXMOX_TEMPLATE_ID=9000
```

### 3. 실행

#### 직접 실행
```bash
# 가상환경 활성화
source venv/bin/activate  # Linux/Mac
# 또는
venv\Scripts\activate     # Windows

# Flask 애플리케이션 실행
python app.py
```

#### Docker 실행
```bash
# Docker Compose로 실행
docker-compose up -d

# 로그 확인
docker-compose logs -f
```

### 4. 웹 인터페이스 접속

- 직접 실행: http://localhost:5000
- Docker 실행: http://localhost

## 🎯 주요 기능

### 서버 관리 기능
- **서버 생성**: 웹 UI를 통한 간편한 서버 생성
- **서버 목록**: 생성된 서버들의 실시간 상태 확인
- **서버 제어**: 시작, 중지, 리부팅, 삭제 기능
- **동적 설정**: 디스크와 네트워크 디바이스 동적 추가/삭제

### 지원 OS
- Ubuntu 20.04/22.04
- Debian 11/12
- Rocky Linux 8/9
- CentOS 7/8

### 서버 역할 지원
- **Web Server**: Nginx 기반 웹 서버
- **Database Server**: MySQL/PostgreSQL 데이터베이스
- **Application Server**: Python/Node.js 애플리케이션
- **Cache Server**: Redis 캐시 서버
- **Load Balancer**: Nginx 로드 밸런서

### 자동화 기능
- 동적 Terraform 설정 생성 (JSON 형식)
- 역할 기반 Ansible 플레이북 자동 적용
- 멀티 서버 동시 생성 및 관리
- 네트워크 및 스토리지 동적 설정
- 실시간 배포 상태 모니터링

## 🔧 고급 설정

### Terraform 커스터마이징

`terraform/` 디렉토리의 파일들을 수정하여 고급 설정을 추가할 수 있습니다:

```hcl
# terraform/variables.tf에서 변수 추가
variable "custom_network" {
  description = "Custom network configuration"
  type = object({
    bridge = string
    vlan   = optional(number)
  })
  default = null
}

# terraform/modules/server/main.tf에서 동적 블록 추가
dynamic "network_device" {
  for_each = var.networks
  content {
    bridge = network_device.value.bridge
    vlan   = network_device.value.vlan
  }
}
```

### Ansible 플레이북 확장

`ansible/playbook.yml` 파일을 수정하여 커스텀 설정을 추가할 수 있습니다:

```yaml
- name: Install custom packages
  apt:
    name:
      - htop
      - vim
      - git
    state: present

- name: Configure firewall
  ufw:
    rule: allow
    port: '80'
    proto: tcp
```

## 📊 모니터링 및 관리

### 웹 UI 기능
- **실시간 서버 상태**: CPU, 메모리, IP 정보 표시
- **자동 새로고침**: 서버 상태 자동 업데이트
- **진행률 표시**: 서버 생성/삭제 진행 상황
- **확인 대화상자**: 중요 작업 전 확인 요청

### API 엔드포인트
```bash
# 서버 생성
POST /api/servers
{
  "name": "web-server-1",
  "os": "ubuntu-22.04",
  "roles": ["web"],
  "cpu": 2,
  "memory": 4096,
  "disks": [...],
  "networks": [...]
}

# 서버 목록 조회
GET /api/servers

# 서버 제어
POST /api/servers/{server_id}/start
POST /api/servers/{server_id}/stop
POST /api/servers/{server_id}/reboot
DELETE /api/servers/{server_id}
```

## 🔐 보안 고려사항

### 네트워크 보안
- Proxmox API 접근을 위한 방화벽 설정
- VM 간 네트워크 분리 (VLAN 활용)
- SSH 키 기반 인증 설정

### 접근 제어
- Flask 애플리케이션에 인증 시스템 추가 (향후 구현 예정)
- Terraform 상태 파일 암호화
- Ansible Vault를 사용한 민감 정보 관리

## 🐛 문제 해결

### 일반적인 오류

#### Proxmox 연결 오류
```
Error: failed to connect to Proxmox API
```
**해결방법**: `.env` 파일의 Proxmox 설정 확인

#### Terraform 초기화 오류
```
Error: Failed to install provider
```
**해결방법**: 인터넷 연결 확인 및 Terraform 재설치

#### Ansible 연결 오류
```
UNREACHABLE! => {"changed": false, "msg": "SSH timeout"}
```
**해결방법**: SSH 키 설정 및 네트워크 접근성 확인

#### HCL 파서 오류 (Python 3.12)
```
Error: HCL parsing failed
```
**해결방법**: `terraform.tfvars.json` 형식 사용 (이미 적용됨)

### 디버깅 모드 활성화

```bash
# Flask 디버그 모드
export FLASK_DEBUG=1

# Terraform 상세 로그
export TF_LOG=DEBUG

# Ansible 상세 로그
export ANSIBLE_DEBUG=1
```

## 🚀 향후 개발 계획

### 예정 기능
- [ ] 사용자 인증 및 권한 관리
- [ ] 서버 백업 및 복원 기능
- [ ] 모니터링 대시보드 (Prometheus/Grafana)
- [ ] 자동 스케일링 기능
- [ ] 다중 Proxmox 노드 지원
- [ ] Kubernetes 클러스터 자동 배포

### UI 개선
- [ ] 다크 모드 지원
- [ ] 모바일 반응형 개선
- [ ] 실시간 리소스 사용량 차트
- [ ] 서버 로그 실시간 뷰어

## 🤝 기여하기

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📝 라이선스

MIT License - 자세한 내용은 LICENSE 파일을 참조하세요.

## 🆘 지원

- 이슈 트래커: GitHub Issues
- 문서: Wiki 페이지
- 커뮤니티: Discord 채널

---

**즐거운 자동화 되세요! 🚀**