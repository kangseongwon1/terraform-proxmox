# 🔧 문제 해결 가이드

## 📋 개요

이 문서는 Proxmox 서버 자동 생성 및 관리 시스템에서 발생할 수 있는 일반적인 문제들과 해결 방법을 설명합니다.

## 🚨 긴급 문제 해결

### 1. 웹 콘솔 접속 불가

#### 증상
- 브라우저에서 `ERR_CONNECTION_REFUSED` 오류
- 웹 페이지가 로드되지 않음

#### 해결 방법
```bash
# 1. 서비스 상태 확인
sudo systemctl status proxmox-manager

# 2. 서비스 재시작
sudo systemctl restart proxmox-manager

# 3. 포트 사용 확인
sudo netstat -tlnp | grep :5000

# 4. 방화벽 확인
sudo ufw status  # Ubuntu
sudo firewall-cmd --list-all  # CentOS
```

#### 예방 방법
```bash
# 서비스 자동 재시작 설정
sudo systemctl enable proxmox-manager
```

### 2. 데이터베이스 오류

#### 증상
- `sqlite3.OperationalError: no such table`
- `database is locked` 오류

#### 해결 방법
```bash
# 1. 데이터베이스 파일 권한 확인
ls -la instance/proxmox_manager.db

# 2. 권한 수정
sudo chown www-data:www-data instance/proxmox_manager.db
sudo chmod 644 instance/proxmox_manager.db

# 3. 데이터베이스 재생성 (주의: 데이터 손실)
rm instance/proxmox_manager.db
python create_tables.py
```

### 3. Proxmox 연결 실패

#### 증상
- `Connection refused` 오류
- API 호출 실패

#### 해결 방법
```bash
# 1. Proxmox 서버 상태 확인
curl -k https://your-proxmox-server:8006/api2/json/version

# 2. 네트워크 연결 확인
ping your-proxmox-server

# 3. 환경 변수 확인
cat .env | grep PROXMOX

# 4. SSL 인증서 문제 해결
export PYTHONHTTPSVERIFY=0  # 임시 해결책
```

## 🔍 일반적인 문제들

### 1. Python 관련 문제

#### 가상환경 문제
```bash
# 증상: ModuleNotFoundError
# 해결 방법
source venv/bin/activate
pip install -r requirements.txt

# 가상환경 재생성
rm -rf venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

#### 버전 호환성 문제
```bash
# Python 버전 확인
python3 --version

# pip 업그레이드
pip install --upgrade pip

# 패키지 버전 확인
pip list | grep -E "(Flask|SQLAlchemy|requests)"
```

### 2. 권한 관련 문제

#### 파일 권한 오류
```bash
# 증상: Permission denied
# 해결 방법
sudo chown -R $USER:$USER /path/to/terraform-proxmox
sudo chmod -R 755 /path/to/terraform-proxmox
sudo chmod 600 .env
```

#### SSH 키 권한 문제
```bash
# SSH 키 권한 확인
ls -la ~/.ssh/

# 권한 수정
chmod 600 ~/.ssh/id_rsa
chmod 644 ~/.ssh/id_rsa.pub
chmod 700 ~/.ssh/

# SSH 에이전트 재시작
eval $(ssh-agent)
ssh-add ~/.ssh/id_rsa
```

### 3. 네트워크 관련 문제

#### 방화벽 문제
```bash
# Ubuntu UFW
sudo ufw status
sudo ufw allow 5000/tcp  # 개발 환경
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS

# CentOS firewalld
sudo firewall-cmd --list-all
sudo firewall-cmd --permanent --add-port=5000/tcp
sudo firewall-cmd --reload
```

#### 포트 충돌
```bash
# 포트 사용 확인
sudo netstat -tlnp | grep :5000

# 프로세스 종료
sudo pkill -f "python.*run.py"
sudo pkill -f "gunicorn"

# 다른 포트 사용
export FLASK_RUN_PORT=5001
python run.py
```

## 🐛 디버깅 방법

### 1. 로그 분석

#### 애플리케이션 로그
```bash
# 실시간 로그 확인
tail -f app.log

# 에러 로그 필터링
grep -i error app.log

# 특정 시간대 로그
grep "2024-01-01" app.log
```

#### 시스템 로그
```bash
# systemd 서비스 로그
sudo journalctl -u proxmox-manager -f

# Nginx 로그
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log

# 시스템 로그
sudo tail -f /var/log/syslog  # Ubuntu
sudo tail -f /var/log/messages  # CentOS
```

### 2. 디버그 모드 활성화

#### Flask 디버그 모드
```bash
# 환경 변수 설정
export FLASK_ENV=development
export FLASK_DEBUG=1

# 애플리케이션 실행
python run.py
```

#### 상세 로깅
```python
# config.py에서 로그 레벨 변경
import logging
logging.basicConfig(level=logging.DEBUG)
```

### 3. API 테스트

#### curl을 사용한 테스트
```bash
# 기본 연결 테스트
curl -I http://localhost:5000

# API 엔드포인트 테스트
curl http://localhost:5000/api/servers

# 인증이 필요한 API 테스트
curl -X POST http://localhost:5000/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=admin123!"
```

#### Postman을 사용한 테스트
1. Postman 설치
2. 새 컬렉션 생성
3. 요청 추가 및 테스트

## 🔧 성능 문제 해결

### 1. 느린 응답 시간

#### 데이터베이스 최적화
```bash
# SQLite 최적화
sqlite3 instance/proxmox_manager.db "PRAGMA optimize;"

# 인덱스 생성
sqlite3 instance/proxmox_manager.db "CREATE INDEX IF NOT EXISTS idx_servers_name ON servers(name);"
```

#### 메모리 사용량 최적화
```bash
# 프로세스 메모리 확인
ps aux | grep python

# 가비지 컬렉션 강제 실행
python -c "import gc; gc.collect()"
```

### 2. 동시 접속 문제

#### Gunicorn 설정 최적화
```bash
# 워커 수 조정
gunicorn -w 8 -b 0.0.0.0:5000 "app:app"

# 타임아웃 설정
gunicorn -w 4 --timeout 120 -b 0.0.0.0:5000 "app:app"
```

#### 데이터베이스 연결 풀
```python
# config.py
SQLALCHEMY_ENGINE_OPTIONS = {
    'pool_size': 20,
    'pool_recycle': 3600,
    'pool_pre_ping': True
}
```

## 🛠️ 유지보수 작업

### 1. 정기적인 점검

#### 시스템 상태 확인
```bash
# 디스크 사용량 확인
df -h

# 메모리 사용량 확인
free -h

# CPU 사용량 확인
top

# 로그 파일 크기 확인
du -sh /var/log/*
```

#### 데이터베이스 백업
```bash
# 자동 백업 스크립트
#!/bin/bash
BACKUP_DIR="/backup/proxmox-manager"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR
cp instance/proxmox_manager.db $BACKUP_DIR/db_$DATE.db

# 30일 이전 백업 삭제
find $BACKUP_DIR -name "*.db" -mtime +30 -delete
```

### 2. 업데이트 및 패치

#### Python 패키지 업데이트
```bash
# 패키지 업데이트 확인
pip list --outdated

# 안전한 업데이트
pip install --upgrade pip
pip install --upgrade -r requirements.txt
```

#### 시스템 업데이트
```bash
# Ubuntu
sudo apt update && sudo apt upgrade

# CentOS
sudo yum update
```

## 📞 지원 및 문의

### 1. 문제 보고

문제를 보고할 때 다음 정보를 포함하세요:

#### 필수 정보
- **운영체제**: Ubuntu 22.04 LTS
- **Python 버전**: 3.8.10
- **에러 메시지**: 전체 에러 로그
- **재현 단계**: 문제 발생 과정
- **예상 동작**: 정상적인 동작

#### 선택 정보
- **하드웨어 사양**: CPU, 메모리, 디스크
- **네트워크 환경**: 방화벽, 프록시 설정
- **관련 로그**: 애플리케이션, 시스템 로그

### 2. 디버그 정보 수집

#### 시스템 정보 수집
```bash
# 시스템 정보
uname -a
cat /etc/os-release

# Python 환경 정보
python3 --version
pip list

# 네트워크 정보
ip addr show
netstat -tlnp

# 디스크 정보
df -h
```

#### 애플리케이션 정보 수집
```bash
# 설정 파일 확인
cat .env

# 데이터베이스 상태 확인
sqlite3 instance/proxmox_manager.db ".schema"

# 로그 파일 수집
tar -czf logs.tar.gz app.log /var/log/nginx/*.log
```

## 🚨 긴급 복구 절차

### 1. 서비스 복구

#### 완전 재시작
```bash
# 모든 서비스 중지
sudo systemctl stop proxmox-manager
sudo systemctl stop nginx

# 프로세스 강제 종료
sudo pkill -f "python.*run.py"
sudo pkill -f "gunicorn"

# 서비스 재시작
sudo systemctl start nginx
sudo systemctl start proxmox-manager

# 상태 확인
sudo systemctl status proxmox-manager
sudo systemctl status nginx
```

#### 데이터베이스 복구
```bash
# 백업에서 복구
cp /backup/proxmox-manager/db_latest.db instance/proxmox_manager.db

# 권한 설정
sudo chown www-data:www-data instance/proxmox_manager.db
sudo chmod 644 instance/proxmox_manager.db
```

### 2. 롤백 절차

#### 코드 롤백
```bash
# 이전 버전으로 롤백
git log --oneline
git checkout <commit-hash>

# 의존성 재설치
pip install -r requirements.txt

# 서비스 재시작
sudo systemctl restart proxmox-manager
```

#### 설정 롤백
```bash
# 설정 파일 백업에서 복구
cp .env.backup .env

# 서비스 재시작
sudo systemctl restart proxmox-manager
```

## 📚 추가 리소스

### 1. 공식 문서
- [Flask 공식 문서](https://flask.palletsprojects.com/)
- [Terraform 공식 문서](https://www.terraform.io/docs)
- [Ansible 공식 문서](https://docs.ansible.com/)
- [Proxmox API 문서](https://pve.proxmox.com/pve-docs/api-viewer/)

### 2. 커뮤니티 리소스
- [GitHub Issues](https://github.com/username/terraform-proxmox/issues)
- [Stack Overflow](https://stackoverflow.com/questions/tagged/flask)
- [Reddit r/Proxmox](https://www.reddit.com/r/Proxmox/)

### 3. 도구 및 유틸리티
- [Postman](https://www.postman.com/) - API 테스트
- [SQLite Browser](https://sqlitebrowser.org/) - 데이터베이스 관리
- [htop](https://htop.dev/) - 시스템 모니터링

---

이 문서는 일반적인 문제 해결 방법을 제공합니다. 추가 도움이 필요하면 팀에 문의하세요.


