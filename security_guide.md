# 🔒 Proxmox Manager 보안 가이드

## 🚨 중요 보안 설정

### 1. 환경 변수 설정 (필수!)
```bash
# 환경 변수 템플릿을 .env로 복사
cp env_template.txt .env

# .env 파일 편집하여 실제 값으로 변경
nano .env

# 파일 권한 설정 (소유자만 읽기/쓰기)
chmod 600 .env
```

### 2. 필수 환경 변수
다음 환경 변수는 **반드시** 설정해야 합니다:
```bash
# Flask 보안
SECRET_KEY=your-super-secret-key-change-this

# Proxmox 설정 (하드코딩된 값 사용 금지!)
PROXMOX_ENDPOINT=https://your-proxmox-server:8006
PROXMOX_USERNAME=root@pam
PROXMOX_PASSWORD=your-secure-password
PROXMOX_NODE=pve
PROXMOX_DATASTORE=local-lvm
```

### 3. 보안 강화된 시작
```bash
# 일반 시작 (권장하지 않음)
python app.py

# 보안 검증 후 시작 (권장)
python start_secure.py
```

### 4. 강력한 SECRET_KEY 생성
```bash
# Python에서 안전한 SECRET_KEY 생성
python3 -c "import secrets; print(secrets.token_hex(32))"

# 또는 OpenSSL 사용
openssl rand -hex 32
```

### 5. SSH 키 생성 (없는 경우)
```bash
ssh-keygen -t rsa -b 4096 -f ~/.ssh/id_rsa -N ""
chmod 600 ~/.ssh/id_rsa
chmod 644 ~/.ssh/id_rsa.pub
```

### 6. 방화벽 설정
```bash
# UFW 방화벽 활성화 (Ubuntu)
sudo ufw enable
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP (HTTPS로 리다이렉트)
sudo ufw allow 443/tcp   # HTTPS
sudo ufw deny 5000/tcp   # Flask 개발 포트 차단
```

### 7. HTTPS 설정 (Nginx + Let's Encrypt)
```bash
# Nginx 설치
sudo apt install nginx certbot python3-certbot-nginx

# SSL 인증서 발급
sudo certbot --nginx -d your-domain.com

# Nginx 설정 예시
sudo nano /etc/nginx/sites-available/proxmox-manager
```

### 8. 데이터베이스 보안
```bash
# MariaDB 보안 설정
sudo mysql_secure_installation

# 사용자 생성 및 권한 설정
mysql -u root -p
CREATE DATABASE proxmox_manager;
CREATE USER 'proxmox_user'@'localhost' IDENTIFIED BY 'strong_password';
GRANT ALL PRIVILEGES ON proxmox_manager.* TO 'proxmox_user'@'localhost';
FLUSH PRIVILEGES;
```

## 🔐 인증 시스템

### 기본 로그인 정보
- **사용자명**: admin
- **비밀번호**: admin123! (반드시 변경하세요!)

### 비밀번호 변경 방법
```python
# Python에서 새 비밀번호 해시 생성
from werkzeug.security import generate_password_hash
print(generate_password_hash('your-new-password'))
```

## 🛡️ 추가 보안 권장사항

### 1. 정기적인 업데이트
```bash
# 시스템 업데이트
sudo apt update && sudo apt upgrade

# Python 패키지 업데이트
pip install --upgrade -r requirements.txt
```

### 2. 로그 모니터링
```bash
# 로그 파일 모니터링
tail -f /var/log/proxmox-manager/app.log

# 실패한 로그인 시도 모니터링
grep "Failed login" /var/log/proxmox-manager/app.log
```

### 3. 백업 설정
```bash
# 중요 파일 백업
sudo tar -czf backup-$(date +%Y%m%d).tar.gz \
  terraform/ ansible/ .env config.py
```

### 4. 프로세스 모니터링
```bash
# systemd 서비스로 등록
sudo nano /etc/systemd/system/proxmox-manager.service
```

## 🚨 보안 체크리스트

- [ ] .env 파일이 .gitignore에 포함되어 있는가?
- [ ] .env 파일의 권한이 600으로 설정되어 있는가?
- [ ] SECRET_KEY가 강력한 랜덤 값으로 설정되었는가?
- [ ] config.py에 하드코딩된 비밀번호가 없는가?
- [ ] HTTPS가 적용되었는가?
- [ ] 방화벽이 활성화되었는가?
- [ ] 기본 비밀번호가 변경되었는가?
- [ ] 로그 파일이 적절히 관리되고 있는가?
- [ ] 정기적인 백업이 설정되었는가?
- [ ] 시스템 업데이트가 자동화되었는가?

## ⚠️ 주의사항

### config.py 보안 문제 해결
- **문제**: config.py에 하드코딩된 비밀번호가 노출될 수 있음
- **해결**: 환경 변수 필수화로 하드코딩된 값 제거
- **검증**: `python start_secure.py`로 보안 검증 후 시작

### 파일 권한 관리
```bash
# 민감한 파일들의 권한 설정
chmod 600 .env
chmod 600 config.py
chmod 600 ~/.ssh/id_rsa
chmod 644 ~/.ssh/id_rsa.pub
```

## 📞 보안 이슈 신고

보안 취약점을 발견하셨다면 즉시 관리자에게 연락하세요. 