# Windows 환경에서 Ansible 설치 및 설정 가이드

## 문제 상황
Windows 환경에서 Ansible을 실행할 때 `[WinError 2] 지정된 파일을 찾을 수 없습니다` 오류가 발생하는 경우가 있습니다.

## 해결 방법

### 1. Python을 통한 Ansible 설치 (권장)

```bash
# pip를 사용하여 Ansible 설치
pip install ansible

# 설치 확인
python -m ansible --version
```

### 2. WSL (Windows Subsystem for Linux) 사용 (가장 안정적)

#### 2.1 WSL 설치
```powershell
# 관리자 권한으로 PowerShell 실행
wsl --install
```

#### 2.2 Ubuntu 설치 후 Ansible 설치
```bash
# Ubuntu 패키지 업데이트
sudo apt update

# Ansible 설치
sudo apt install ansible

# 설치 확인
ansible --version
```

### 3. Chocolatey를 통한 설치

```powershell
# Chocolatey 설치 (관리자 권한 필요)
Set-ExecutionPolicy Bypass -Scope Process -Force; [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))

# Ansible 설치
choco install ansible
```

### 4. 수동 설치

1. [Ansible 공식 릴리즈 페이지](https://github.com/ansible/ansible/releases)에서 Windows용 바이너리 다운로드
2. 압축 해제 후 PATH에 추가

## 환경 변수 설정

### SSH 키 설정
```bash
# SSH 키 생성 (없는 경우)
ssh-keygen -t rsa -b 4096

# 환경 변수 설정
set SSH_PRIVATE_KEY_PATH=C:\Users\%USERNAME%\.ssh\id_rsa
set SSH_USER=rocky
```

### Ansible 설정 파일
`ansible.cfg` 파일을 프로젝트 루트에 생성:

```ini
[defaults]
host_key_checking = False
inventory = ansible/inventory
roles_path = ansible/roles
```

## 테스트

### 1. Ansible 설치 확인
```bash
ansible --version
```

### 2. 연결 테스트
```bash
# 단일 서버 테스트
ansible all -i ansible/inventory -m ping

# 특정 서버 테스트
ansible 192.168.1.100 -i ansible/inventory -m ping
```

## 문제 해결

### 1. PATH 문제
Ansible이 PATH에 추가되지 않은 경우:
```powershell
# 현재 PATH 확인
echo $env:PATH

# Ansible 경로 추가 (예시)
$env:PATH += ";C:\Python39\Scripts"
```

### 2. 권한 문제
관리자 권한으로 PowerShell을 실행하여 설치를 진행하세요.

### 3. Python 버전 문제
Python 3.8 이상을 사용하는 것을 권장합니다.

## 권장 사항

1. **WSL 사용**: Windows에서 Ansible을 사용할 때 가장 안정적인 방법
2. **Python 가상환경**: 프로젝트별로 독립적인 환경 구성
3. **SSH 키 관리**: 보안을 위해 SSH 키를 적절히 관리

## 관련 파일

- `app/services/ansible_service.py`: Ansible 서비스 로직
- `ansible/`: Ansible 설정 및 역할 파일들
- `config.py`: SSH 설정 