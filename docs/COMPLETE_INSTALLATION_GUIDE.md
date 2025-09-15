# 🚀 Proxmox Manager 완전 통합 설치 가이드

## 📋 개요

이 가이드는 Proxmox Manager를 **하나의 명령어**로 완전히 설치하고 설정하는 방법을 설명합니다.

## ✨ 포함된 구성요소

- **Python 환경**: Flask 애플리케이션 및 모든 Python 패키지
- **Docker & Docker Compose**: 컨테이너 환경
- **Terraform**: 인프라 자동화
- **Ansible**: 서버 구성 관리
- **HashiCorp Vault**: 보안 시크릿 관리
- **Prometheus**: 메트릭 수집
- **Grafana**: 모니터링 대시보드
- **Node Exporter**: 시스템 메트릭
- **데이터베이스**: SQLite 데이터베이스
- **보안 설정**: 방화벽, SSH 키

## 🎯 지원 운영체제

- **RedHat 계열**: Rocky Linux, CentOS, RHEL, Fedora
- **Debian 계열**: Ubuntu, Debian

## 🚀 빠른 설치 (추천)

### 1단계: 스크립트 다운로드 및 실행

```bash
# 실행 권한 설정
chmod +x quick_start.sh

# 설치 실행
./quick_start.sh
```

**끝!** 🎉

## 🔧 수동 설치 (상세)

### 1단계: 시스템 준비

```bash
# 실행 권한 설정
chmod +x install_complete_system.sh

# 설치 실행
./install_complete_system.sh
```

### 2단계: 설치 과정

스크립트가 자동으로 다음을 수행합니다:

1. **시스템 정보 확인** - OS, 패키지 매니저 확인
2. **필수 패키지 설치** - 개발 도구, Python, 컴파일러
3. **Python 환경 설정** - 가상환경, 패키지 설치
4. **Node.js 설치** - 최신 LTS 버전
5. **Docker 설치** - Docker Engine, Docker Compose
6. **Terraform 설치** - 최신 버전
7. **Ansible 설치** - 자동화 도구
8. **환경변수 설정** - .env 파일 생성 및 설정
9. **Vault 설정** - 보안 시크릿 관리
10. **모니터링 설치** - Prometheus, Grafana
11. **데이터베이스 초기화** - 테이블 생성
12. **보안 설정** - 방화벽, SSH 키
13. **서비스 시작** - 모든 서비스 자동 시작

## 📝 설치 중 입력 정보

설치 중에 다음 정보를 입력해야 합니다:

- **Proxmox 서버 주소**: `https://prox.dmcmedia.co.kr:8006`
- **Proxmox 사용자명**: `root@pam`
- **Proxmox 비밀번호**: Proxmox 관리자 비밀번호

## 🌐 설치 완료 후 접속 정보

| 서비스 | URL | 설명 |
|--------|-----|------|
| **웹 관리 콘솔** | `http://서버IP:5000` | 메인 관리 인터페이스 |
| **Grafana 대시보드** | `http://서버IP:3000` | 모니터링 대시보드 |
| **Prometheus** | `http://서버IP:9090` | 메트릭 수집 서버 |
| **Vault** | `http://서버IP:8200` | 보안 시크릿 관리 |

## 🔧 관리 명령어

### 서비스 상태 확인
```bash
# 모든 서비스 상태 확인
ps aux | grep -E '(python|docker)'

# Flask 애플리케이션 로그
tail -f app.log

# Vault 상태 확인
docker exec vault-dev vault status
```

### 서비스 중지
```bash
# Flask 애플리케이션 중지
kill $(cat flask.pid)

# Vault 컨테이너 중지
docker-compose -f docker-compose.vault.yml down
```

### 서비스 재시작
```bash
# Flask 애플리케이션 재시작
nohup python3 run.py > app.log 2>&1 &
echo $! > flask.pid

# Vault 재시작
docker-compose -f docker-compose.vault.yml restart
```

## 📁 중요 파일

| 파일 | 설명 |
|------|------|
| `.env` | 환경변수 설정 파일 |
| `vault_init.txt` | Vault 초기화 정보 (보안 중요!) |
| `app.log` | Flask 애플리케이션 로그 |
| `flask.pid` | Flask 프로세스 ID |
| `requirements.txt` | Python 패키지 목록 |

## 🔒 보안 설정

### Vault 토큰 관리
```bash
# Vault 토큰 확인
cat vault_init.txt | grep "Root Token"

# Vault 재초기화 (필요시)
./vault.sh
```

### 방화벽 포트
- **5000**: Flask 웹 애플리케이션
- **3000**: Grafana 대시보드
- **9090**: Prometheus
- **8200**: Vault

## 🚨 문제 해결

### 설치 실패 시
```bash
# 로그 확인
tail -f app.log

# 서비스 상태 확인
systemctl status docker
docker ps -a

# 수동 재설치
./install_complete_system.sh
```

### Vault 연결 오류
```bash
# Vault 재시작
docker-compose -f docker-compose.vault.yml restart

# 환경변수 확인
echo $VAULT_TOKEN
echo $TF_VAR_vault_token
```

### Terraform 오류
```bash
# Terraform 초기화
cd terraform && terraform init

# 환경변수 확인
env | grep TF_VAR
```

## 📞 지원

문제가 발생하면 다음을 확인하세요:

1. **로그 파일**: `app.log`, `audit.log`
2. **서비스 상태**: `ps aux | grep python`
3. **Docker 상태**: `docker ps -a`
4. **네트워크 연결**: `curl -I http://localhost:5000`

## 🎉 다음 단계

설치 완료 후:

1. **웹 브라우저**에서 관리 콘솔 접속
2. **Proxmox 연결** 테스트
3. **첫 번째 VM** 생성 테스트
4. **모니터링 설정** 확인
5. **보안 설정** 검토

---

**🎊 축하합니다! Proxmox Manager가 성공적으로 설치되었습니다!**
