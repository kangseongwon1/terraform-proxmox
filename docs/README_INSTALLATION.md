# 🚀 Proxmox Manager - 원클릭 설치

## ⚡ 초고속 설치 (30초)

```bash
# 1. 실행 권한 설정
chmod +x quick_start.sh

# 2. 설치 실행
./quick_start.sh

# 3. 브라우저에서 접속
# http://서버IP:5000
```

**끝!** 🎉

## 📦 설치되는 것들

- ✅ **Python + Flask** 웹 애플리케이션
- ✅ **Docker + Docker Compose** 컨테이너 환경  
- ✅ **Terraform** 인프라 자동화
- ✅ **Ansible** 서버 구성 관리
- ✅ **HashiCorp Vault** 보안 시크릿 관리
- ✅ **Prometheus + Grafana** 모니터링 시스템
- ✅ **Node Exporter** 시스템 메트릭
- ✅ **데이터베이스** 자동 초기화
- ✅ **보안 설정** 방화벽, SSH 키

## 🎯 지원 OS

- **Rocky Linux** ✅
- **CentOS** ✅  
- **RHEL** ✅
- **Ubuntu** ✅
- **Debian** ✅

## 📋 설치 중 입력 정보

- **Proxmox 서버 주소**: `https://prox.dmcmedia.co.kr:8006`
- **Proxmox 사용자명**: `root@pam`  
- **Proxmox 비밀번호**: 관리자 비밀번호

## 🌐 설치 완료 후 접속

| 서비스 | URL | 설명 |
|--------|-----|------|
| **관리 콘솔** | `http://서버IP:5000` | 메인 웹 인터페이스 |
| **Grafana** | `http://서버IP:3000` | 모니터링 대시보드 |
| **Prometheus** | `http://서버IP:9090` | 메트릭 서버 |
| **Vault** | `http://서버IP:8200` | 보안 관리 |

## 🔧 관리 명령어

```bash
# 서비스 상태 확인
ps aux | grep python

# 로그 확인  
tail -f app.log

# Vault 상태
docker exec vault-dev vault status

# 서비스 중지
kill $(cat flask.pid)
docker-compose -f docker-compose.vault.yml down
```

## 🆘 문제 해결

### 설치 실패
```bash
# 재설치
./install_complete_system.sh
```

### Vault 오류
```bash
# Vault 재시작
./vault.sh
```

### Terraform 오류
```bash
# 환경변수 확인
env | grep TF_VAR
```

## 📚 상세 가이드

더 자세한 정보는 [COMPLETE_INSTALLATION_GUIDE.md](COMPLETE_INSTALLATION_GUIDE.md)를 참조하세요.

---

**🎊 원클릭으로 Proxmox Manager를 설치하고 관리하세요!**
