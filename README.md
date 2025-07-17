# 🚀 서버 자동 생성 시스템

Flask + Terraform + Ansible을 사용한 Proxmox 기반 서버 자동 생성 시스템입니다.

## 📁 프로젝트 구조

```
server-automation/
├── app.py                 # Flask 메인 애플리케이션
├── requirements.txt       # Python 의존성
├── .env                  # 환경 설정 파일
├── Dockerfile            # Docker 이미지 빌드
├── docker-compose.yml    # Docker Compose 설정
├── setup.sh             # 설치 스크립트
├── README.md            # 프로젝트 문서
├── templates/           # Flask HTML 템플릿
│   └── index.html       # 메인 웹 인터페이스
├── ansible/             # Ansible 설정
│   └── templates/       # Ansible 템플릿
│       └── nginx.conf.j2
├── terraform/           # Terraform 모듈 (동적 생성)
├── projects/            # 생성된 프로젝트 저장소
└── logs/               # 로그 파일
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
cd server-automation

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
source venv/bin/activate

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

### 서버 역할 지원
- **Web Server**: Nginx 기반 웹 서버
- **Database Server**: MySQL 데이터베이스
- **Application Server**: Python/Node.js 애플리케이션
- **Cache Server**: Redis 캐시 서버
- **Load Balancer**: Nginx 로드 밸런서

### 자동화 기능
- 동적 Terraform 설정 생성
- 역할 기반 Ansible 플레이북 생성
- 멀티 서버 동시 생성
- 네트워크 및 스토리지 설정
- 실시간 배포 상태 모니터링

## 🔧 고급 설정

### Terraform 커스터마이징

생성된 프로젝트의 `main.tf` 파일을 수정하여 고급 설정을 추가할 수 있습니다:

```hcl
# 추가 네트워크 설정
network_device {
  bridge = "vmbr1"
  vlan   = 100
}

# 추가 스토리지 설정
disk {
  interface = "scsi0"
  size      = 100
  file_format = "raw"
  datastore_id = "fast-ssd"
}
```

### Ansible 플레이북 확장

`ansible/playbooks/` 디렉토리에 커스텀 플레이북을 추가할 수 있습니다:

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

## 📊 모니터링

### 배포 상태 확인

```bash
# 특정 프로젝트 상태 확인
curl http://localhost:5000/status/my-project

# 모든 프로젝트 목록
curl http://localhost:5000/projects
```

### 로그 확인

```bash
# Flask 애플리케이션 로그
tail -f logs/app.log

# Terraform 로그
tail -f projects/my-project/terraform.log

# Ansible 로그
tail -f projects/my-project/ansible.log
```

## 🔐 보안 고려사항

### 네트워크 보안
- Proxmox API 접근을 위한 방화벽 설정
- VM 간 네트워크 분리 (VLAN 활용)
- SSH 키 기반 인증 설정

### 접근 제어
- Flask 애플리케이션에 인증 시스템 추가
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

### 디버깅 모드 활성화

```bash
# Flask 디버그 모드
export FLASK_DEBUG=1

# Terraform 상세 로그
export TF_LOG=DEBUG

# Ansible 상세 로그
export ANSIBLE_DEBUG=1
```

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