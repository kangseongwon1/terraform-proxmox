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

## 🚀 처음 사용자를 위한 완전 가이드

### 📋 사전 준비사항

#### 1. Proxmox 서버 준비
- Proxmox VE 6.0 이상이 설치된 서버
- 템플릿 VM 준비 (Ubuntu 20.04/22.04, Rocky Linux 8/9 등)
- API 접근 권한이 있는 사용자 계정

#### 2. 클라이언트 환경 준비
- Linux (Ubuntu 20.04+ 권장) 또는 Windows 10/11
- 인터넷 연결 가능한 환경
- 최소 4GB RAM, 10GB 디스크 여유 공간

### 🔧 단계별 설치 가이드

#### 1단계: 리포지토리 클론 및 기본 설치

```bash
# 1. Git 설치 (Ubuntu/Debian)
sudo apt update
sudo apt install git curl wget

# 2. 프로젝트 클론
git clone https://github.com/your-username/terraform-proxmox.git
cd terraform-proxmox

# 3. 실행 권한 부여
chmod +x setup.sh
```

#### 2단계: 필수 소프트웨어 설치

**Linux (Ubuntu/Debian) 사용자:**
```bash
# Python 3.8+ 설치
sudo apt update
sudo apt install python3 python3-pip python3-venv

# Terraform 설치
curl -fsSL https://apt.releases.hashicorp.com/gpg | sudo apt-key add -
sudo apt-add-repository "deb [arch=amd64] https://apt.releases.hashicorp.com $(lsb_release -cs) main"
sudo apt update
sudo apt install terraform

# Ansible 설치
sudo apt install ansible

# 설치 확인
python3 --version
terraform --version
ansible --version
```

**Windows 사용자:**
```powershell
# 1. Chocolatey 설치 (관리자 권한으로 PowerShell 실행)
Set-ExecutionPolicy Bypass -Scope Process -Force
[System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072
iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))

# 2. Python 설치
choco install python

# 3. Terraform 설치
choco install terraform

# 4. Git Bash 설치 (Ansible 사용을 위해)
choco install git

# 5. 설치 확인
python --version
terraform --version
```

## 🔧 Prometheus 권한 문제 해결

Prometheus 설정 파일 업데이트 시 권한 오류가 발생할 수 있습니다:

```bash
# 오류 예시
❌ Prometheus 설정 업데이트 실패: [Errno 13] Permission denied: '/etc/prometheus/prometheus.yml'
```

**해결 방법:**

1. **sudo 권한 설정:**
```bash
# sudo 권한 확인
sudo -l

# 비밀번호 없이 sudo 사용 가능하도록 설정 (선택사항)
sudo visudo
# 다음 줄 추가: username ALL=(ALL) NOPASSWD: /bin/mv, /bin/chown
```

2. **Prometheus 사용자 확인:**
```bash
# prometheus 사용자 존재 확인
id prometheus

# Prometheus 설정 파일 권한 확인
ls -la /etc/prometheus/prometheus.yml
```

3. **자동 해결:**
시스템이 자동으로 다음 방법으로 권한 문제를 해결합니다:
- 임시 파일 생성 (`/tmp/prometheus_config_*.yml`)
- `sudo mv`로 파일 이동
- `sudo chown`으로 소유자 변경

**macOS 사용자:**
```bash
# Homebrew 설치 (없는 경우)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Python 설치
brew install python

# Terraform 설치
brew install terraform

# Ansible 설치
brew install ansible

# 설치 확인
python3 --version
terraform --version
ansible --version
```

#### 3단계: 환경 설정 파일 생성

```bash
# 1. 환경 설정 파일 복사
cp env_template.txt .env

# 2. .env 파일 편집
nano .env
```

`.env` 파일에 다음 내용을 입력하세요:

```env
# Flask 애플리케이션 설정
SECRET_KEY=your-super-secret-key-here
FLASK_ENV=development
DEBUG=true

# Proxmox 서버 설정
PROXMOX_ENDPOINT=https://your-proxmox-server:8006
PROXMOX_USERNAME=root@pam
PROXMOX_PASSWORD=your-proxmox-password
PROXMOX_NODE=pve
PROXMOX_DATASTORE=local-lvm
PROXMOX_TEMPLATE_ID=9000

# 세션 보안 설정
SESSION_COOKIE_SECURE=false
SESSION_COOKIE_HTTPONLY=true
SESSION_COOKIE_SAMESITE=Strict
PERMANENT_SESSION_LIFETIME=3600

# 로깅 설정
LOG_LEVEL=INFO
LOG_FILE=app.log

# SSH 설정
SSH_PRIVATE_KEY_PATH=~/.ssh/id_rsa
SSH_PUBLIC_KEY_PATH=~/.ssh/id_rsa.pub
```

#### 4단계: 자동 설치 스크립트 실행

```bash
# 자동 설치 스크립트 실행
./setup.sh
```

이 스크립트는 다음 작업을 자동으로 수행합니다:
- Python 가상환경 생성
- 필요한 Python 패키지 설치
- Terraform 초기화
- 기본 디렉토리 구조 생성

#### 5단계: SSH 키 설정

```bash
# SSH 키 생성 (없는 경우)
ssh-keygen -t rsa -b 4096 -C "your-email@example.com"

# SSH 키를 Proxmox에 등록
# Proxmox 웹 UI → Datacenter → SSH Keys에서 공개키 등록
cat ~/.ssh/id_rsa.pub
```

#### 6단계: Terraform 설정 확인

```bash
# terraform 디렉토리로 이동
cd terraform

# Terraform 초기화
terraform init

# 설정 확인
terraform plan
```

### 🚀 애플리케이션 실행

#### 방법 1: 직접 실행 (권장)

**Linux/macOS:**
```bash
# 1. 가상환경 활성화
source venv/bin/activate

# 2. Flask 애플리케이션 실행
python app.py
```

**Windows:**
```cmd
# 1. 가상환경 활성화
venv\Scripts\activate

# 2. Flask 애플리케이션 실행
python app.py
```

#### 방법 2: 백그라운드 실행

**Linux/macOS:**
```bash
# 1. 가상환경 활성화
source venv/bin/activate

# 2. 백그라운드에서 실행
nohup python app.py > app.log 2>&1 &

# 3. 프로세스 확인
ps aux | grep python
```

**Windows:**
```cmd
# 1. 가상환경 활성화
venv\Scripts\activate

# 2. 백그라운드에서 실행 (새 명령 프롬프트 창에서)
start /B python app.py > app.log 2>&1
```

### 🌐 웹 인터페이스 접속

1. 웹 브라우저에서 `http://localhost:5000` 접속
2. 기본 로그인 정보:
   - **사용자명**: `admin`
   - **비밀번호**: `admin123!`

### 📝 첫 번째 서버 생성하기

#### 1. 로그인 후 대시보드 확인
- 서버 목록, 스토리지 정보 등 확인

#### 2. 새 서버 생성
1. **인스턴스** 메뉴 클릭
2. **서버 생성** 버튼 클릭
3. 서버 정보 입력:
   - **서버명**: `test-server-01`
   - **역할**: `웹서버(Nginx)`
   - **CPU**: `2`
   - **메모리**: `4096` (4GB)
   - **네트워크**: IP 주소 설정
4. **생성** 버튼 클릭

#### 3. 생성 과정 모니터링
- 알림 센터에서 진행 상황 확인
- 서버 상태가 "running"이 될 때까지 대기

### 🔍 문제 해결

#### 일반적인 오류와 해결방법

**1. Proxmox 연결 오류**
```bash
Error: failed to connect to Proxmox API
```
**해결방법**:
- `.env` 파일의 Proxmox 설정 확인
- Proxmox 서버가 실행 중인지 확인
- 방화벽 설정 확인 (포트 8006)

**2. Terraform 초기화 오류**
```bash
Error: Failed to install provider
```
**해결방법**:
```bash
cd terraform
rm -rf .terraform
terraform init
```

**3. SSH 연결 오류**
```bash
UNREACHABLE! => {"changed": false, "msg": "SSH timeout"}
```
**해결방법**:
- SSH 키가 Proxmox에 등록되었는지 확인
- 네트워크 연결 확인
- VM의 SSH 서비스가 실행 중인지 확인

**4. 권한 오류**
```bash
Error: Permission denied
```
**해결방법**:
```bash
# Linux/macOS: 파일 권한 확인 및 수정
chmod +x setup.sh
chmod 600 .env

# Windows: 관리자 권한으로 실행
# 명령 프롬프트를 관리자 권한으로 실행 후 다시 시도
```

**5. Windows에서 가상환경 활성화 오류**
```cmd
Error: 'venv' is not recognized as an internal or external command
```
**해결방법**:
```cmd
# PowerShell에서 실행 정책 변경
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# 또는 cmd에서 직접 실행
venv\Scripts\activate.bat
```

**6. Windows에서 SSH 키 생성 오류**
```cmd
Error: ssh-keygen command not found
```
**해결방법**:
```cmd
# Git Bash 설치 후 Git Bash에서 실행
# 또는 WSL(Windows Subsystem for Linux) 사용
wsl ssh-keygen -t rsa -b 4096 -C "your-email@example.com"
```

### 📚 추가 설정

#### Vault 설정 (선택사항)
```bash
# Vault 설치 (Ubuntu)
curl -fsSL https://apt.releases.hashicorp.com/gpg | sudo apt-key add -
sudo apt-add-repository "deb [arch=amd64] https://apt.releases.hashicorp.com $(lsb_release -cs) main"
sudo apt update
sudo apt install vault

# Vault 시작
vault server -dev
```

#### 모니터링 설정
```bash
# 로그 확인
tail -f app.log

# 시스템 리소스 모니터링
htop
```

### 🆘 지원 및 도움말

- **문서**: 이 README.md 파일 참조
- **이슈**: GitHub Issues 페이지에서 문제 보고
- **커뮤니티**: Discord 채널 또는 포럼 참여

---

## 🚀 빠른 시작

### **방법 1: 빠른 설치 (권장)**

```bash
# 1. 리포지토리 클론
git clone <repository-url>
cd terraform-proxmox

# 2. 빠른 설치 실행 (Linux/macOS)
chmod +x quick_setup.sh
./quick_setup.sh

# 3. .env 파일 편집 (자동으로 생성됨)
nano .env  # 실제 값으로 수정

# 4. Flask 애플리케이션 시작
source venv/bin/activate
python run.py
```

### **방법 2: 수동 설치**

```bash
# 1. 리포지토리 클론
git clone <repository-url>
cd terraform-proxmox

# 2. 환경 설정
cp env_template.txt .env
nano .env  # 실제 값으로 수정

# 3. 자동 설치 스크립트 실행
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

#### 디스크 타입별 파일 포맷 자동 설정

SSD나 NVMe 디스크에 대해 자동으로 `raw` 포맷을 사용하도록 설정할 수 있습니다:

```json
{
  "servers": {
    "web-server-01": {
      "name": "web-server-01",
      "role": "web",
      "cpu": 2,
      "memory": 4096,
      "disks": [
        {
          "size": 50,
          "interface": "scsi0",
          "datastore_id": "local-lvm",
          "disk_type": "ssd",        // SSD 디스크
          "file_format": "auto"      // 자동으로 raw 포맷 사용
        },
        {
          "size": 100,
          "interface": "scsi1", 
          "datastore_id": "local-lvm",
          "disk_type": "hdd",        // HDD 디스크
          "file_format": "auto"      // 자동으로 qcow2 포맷 사용
        }
      ],
      "network_devices": [
        {
          "bridge": "vmbr0",
          "ip_address": "192.168.1.100",
          "subnet": "24",
          "gateway": "192.168.1.1"
        }
      ],
      "template_vm_id": 9000
    }
  }
}
```

#### 수동 파일 포맷 지정

특정 디스크에 대해 수동으로 파일 포맷을 지정할 수도 있습니다:

```json
{
  "disks": [
    {
      "size": 50,
      "interface": "scsi0",
      "datastore_id": "local-lvm",
      "disk_type": "ssd",
      "file_format": "raw"           // 수동으로 raw 포맷 지정
    },
    {
      "size": 100,
      "interface": "scsi1",
      "datastore_id": "local-lvm", 
      "disk_type": "hdd",
      "file_format": "qcow2"         // 수동으로 qcow2 포맷 지정
    }
  ]
}
```

#### 네트워크 설정 커스터마이징

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
# API 관련 
- app/routes/__init__.py : 초기화 
- app/routes/admin.py : 사용자 관리 기능 
- app/routes/api.py : 엔드포인트 라우팅 기능
- app/routes/auth.py : 인증 기능
- app/routes/firewall.py : 방화벽 기능
- app/routes/main.py : 랜더링 기능
- app/routes/notification.py : 알람 기능
- app/routes/servers.py : 서버 생성/삭제/재부팅/정지, 서버 목록 등 확인 기능

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

# 프로젝트 구조 리팩토링 계획

이 프로젝트는 확장성과 유지보수성을 위해 아래와 같은 베스트 프랙티스 구조로 리팩토링될 예정입니다.

```
project-root/
│
├── docs/                  # 전체 시스템 문서, 아키텍처, 운영 가이드 등
├── scripts/               # 반복 작업 자동화 스크립트
├── terraform/             # IaC: 인프라 코드 (환경별 분리)
│   ├── modules/
│   ├── envs/
│   │   ├── dev/
│   │   └── prod/
│   ├── variables.tf
│   ├── outputs.tf
│   └── README.md
├── ansible/               # 구성 관리: Ansible 역할, 인벤토리, 플레이북
│   ├── roles/
│   ├── group_vars/
│   ├── host_vars/
│   ├── inventory/
│   ├── playbooks/
│   └── README.md
├── app/                   # 웹/백엔드 앱 소스 (Flask 등)
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── models/
│   ├── routes/
│   ├── services/
│   ├── templates/
│   ├── static/
│   └── tests/
├── requirements.txt       # Python 의존성 명시
├── .env.example           # 환경 변수 예시 파일
├── .gitlab-ci.yml         # CI/CD 파이프라인 예시
├── .gitignore
└── README.md
```

- docs/: 시스템 문서, 아키텍처, 운영 가이드 등
- scripts/: 반복 작업 자동화 스크립트
- terraform/: 환경별 분리, 모듈화
- ansible/: 역할/환경별 분리, 플레이북, 변수 관리
- app/: 서비스/도메인별 분리, 테스트, 환경설정
- requirements.txt, .env.example 등 의존성/환경 변수 관리
- CI/CD 파이프라인 예시 포함

---

이 구조로 순차적으로 리팩토링을 진행합니다.