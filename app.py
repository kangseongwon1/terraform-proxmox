from flask import Flask, render_template, request, jsonify, redirect, url_for, session
import subprocess
import os
import json
import yaml
from datetime import datetime
import threading
import time
import hcl
import logging
import tempfile
import secrets
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

# .env 파일 로드
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("python-dotenv가 설치되지 않았습니다. pip install python-dotenv")
    pass

# 설정 파일 import
from config import config

app = Flask(__name__)

# 환경 변수에서 설정 로드
config_name = os.environ.get('FLASK_ENV', 'development')
app.config.from_object(config[config_name])

# 보안 헤더 설정 (개발 환경에서는 비활성화)
@app.after_request
def add_security_headers(response):
    # 기존 보안 헤더
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    if not app.config.get('DEBUG', False):
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline' https://code.jquery.com https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; font-src 'self' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com"
    # 캐시 방지 헤더 추가
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

# 로그인 필요 데코레이터
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': '로그인이 필요합니다.'}), 401
        return f(*args, **kwargs)
    return decorated_function

# 관리자 권한 필요 데코레이터
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': '로그인이 필요합니다.'}), 401
        if session.get('role') != 'admin':
            return jsonify({'error': '관리자 권한이 필요합니다.'}), 403
        return f(*args, **kwargs)
    return decorated_function

# 역할별 권한 매핑
ROLE_PERMISSIONS = {
    'admin': [
        'view_all', 'create_server', 'delete_server', 'manage_users',
        'assign_roles', 'view_logs', 'manage_roles'
    ],
    'developer': [
        'view_all', 'create_server', 'delete_server'
    ],
    'operator': [
        'view_all', 'create_server'
    ],
    'viewer': [
        'view_all'
    ]
}

def permission_required(permission):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user_role = session.get('role')
            if not user_role or permission not in ROLE_PERMISSIONS.get(user_role, []):
                return jsonify({'error': '권한이 없습니다.'}), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# 설정
TERRAFORM_DIR = 'terraform'
ANSIBLE_DIR = 'ansible'
PROJECTS_DIR = 'projects'
TFVARS_PATH = os.path.join(TERRAFORM_DIR, 'terraform.tfvars.json')

# 파일 기반 사용자 관리
def load_users():
    """users.json에서 사용자 정보 로드"""
    try:
        with open('users.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        # 기본 사용자 생성
        default_users = {
            'admin': {
                'password_hash': generate_password_hash('admin123!'),
                'role': 'admin',
                'email': 'admin@dmcmedia.co.kr',
                'name': '시스템 관리자',
                'created_at': datetime.now().isoformat(),
                'last_login': None,
                'is_active': True
            }
        }
        save_users(default_users)
        return default_users

def save_users(users):
    """사용자 정보를 users.json에 저장"""
    with open('users.json', 'w', encoding='utf-8') as f:
        json.dump(users, f, indent=2, ensure_ascii=False)

def get_user(username):
    """사용자 정보 조회"""
    users = load_users()
    return users.get(username)

def update_user_login(username):
    """사용자 마지막 로그인 시간 업데이트"""
    users = load_users()
    if username in users:
        users[username]['last_login'] = datetime.now().isoformat()
        save_users(users)

# 초기 사용자 로드
USERS = load_users()

# 알림 관리 함수
def load_notifications():
    """notifications.json에서 알림 데이터 로드"""
    try:
        with open('notifications.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        default_data = {
            "notifications": [],
            "last_id": 0,
            "settings": {
                "max_notifications": 100,
                "auto_clear_days": 7
            }
        }
        save_notifications(default_data)
        return default_data

def save_notifications(data):
    """알림 데이터를 notifications.json에 저장"""
    with open('notifications.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def add_notification(type, title, message, details=None, severity='info'):
    """새 알림 추가"""
    data = load_notifications()
    
    # ID 증가
    data['last_id'] += 1
    
    notification = {
        'id': data['last_id'],
        'type': type,  # 'server_create', 'server_error', 'terraform_error', 'ansible_error'
        'title': title,
        'message': message,
        'details': details,
        'severity': severity,  # 'info', 'warning', 'error', 'success'
        'timestamp': datetime.now().isoformat(),
        'read': False,
        'user_id': session.get('user_id', 'system')
    }
    
    data['notifications'].insert(0, notification)  # 최신 알림을 맨 위에
    
    # 최대 알림 수 제한
    if len(data['notifications']) > data['settings']['max_notifications']:
        data['notifications'] = data['notifications'][:data['settings']['max_notifications']]
    
    save_notifications(data)
    return notification

def get_unread_count():
    """읽지 않은 알림 수 반환"""
    data = load_notifications()
    return len([n for n in data['notifications'] if not n.get('read', False)])

def mark_as_read(notification_id):
    """알림을 읽음으로 표시"""
    data = load_notifications()
    for notification in data['notifications']:
        if notification['id'] == notification_id:
            notification['read'] = True
            break
    save_notifications(data)

# terraform.tfvars.json의 servers map 읽기

def read_servers_from_tfvars():
    with open(TFVARS_PATH, 'r', encoding='utf-8') as f:
        obj = json.load(f)
        return obj.get('servers', {})

def write_servers_to_tfvars(servers, other_vars=None):
    with open(TFVARS_PATH, 'r', encoding='utf-8') as f:
        obj = json.load(f)
    obj['servers'] = servers
    if other_vars:
        obj.update(other_vars)
    with open(TFVARS_PATH, 'w', encoding='utf-8') as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)

# 서버 역할 정의
# 1. 서버 역할 정의에 OS별 패키지 추가
SERVER_ROLES = {
    'web': {
        'name': '웹서버(Nginx)',
        'description': 'Nginx 웹서버를 설치합니다.'
    },
    'was': {
        'name': 'WAS(Python3.12)',
        'description': 'Python 3.12 환경을 설치합니다.'
    },
    'java': {
        'name': 'JAVA(17.0.7)',
        'description': 'OpenJDK 17.0.7 환경을 설치합니다.'
    },
    'search': {
        'name': '검색(Elasticsearch7)',
        'description': 'Elasticsearch 7.17.10 및 OpenJDK 17.0.7을 설치합니다.'
    },
    'ftp': {
        'name': 'FTP(vsftpd)',
        'description': 'vsftpd FTP 서버를 설치합니다.'
    },
    'db': {
        'name': 'DB(MariaDB10.11)',
        'description': 'MariaDB 10.11을 설치하고 root 비밀번호를 초기화합니다.'
    }
}

        

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('index.html', roles=SERVER_ROLES)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = get_user(username)
        if user and user.get('is_active', True) and check_password_hash(user['password_hash'], password):
            session['user_id'] = username
            session['role'] = user['role']
            session['user_name'] = user.get('name', username)
            session['user_email'] = user.get('email', '')
            
            # 마지막 로그인 시간 업데이트
            update_user_login(username)
            
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error='잘못된 사용자명 또는 비밀번호입니다.')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/users', methods=['GET'])
@admin_required
def list_users():
    """사용자 목록 조회 (관리자만)"""
    users = load_users()
    # 비밀번호 해시는 제외하고 반환
    safe_users = {}
    for username, user_data in users.items():
        safe_users[username] = {
            'name': user_data.get('name', username),
            'email': user_data.get('email', ''),
            'role': user_data.get('role', 'user'),
            'is_active': user_data.get('is_active', True),
            'created_at': user_data.get('created_at', ''),
            'last_login': user_data.get('last_login', '')
        }
    return jsonify({'users': safe_users})

# 사용자 생성 시 기본 role='viewer' 적용
@app.route('/users', methods=['POST'])
@admin_required
def create_user():
    """새 사용자 생성 (관리자만)"""
    data = request.json
    username = data.get('username')
    password = data.get('password')
    name = data.get('name', username)
    email = data.get('email', '')
    # 기본 역할은 viewer, admin만 변경 가능
    role = data.get('role', 'viewer')
    if role not in ROLE_PERMISSIONS:
        role = 'viewer'
    
    if not username or not password:
        return jsonify({'error': '사용자명과 비밀번호는 필수입니다.'}), 400
    
    users = load_users()
    if username in users:
        return jsonify({'error': '이미 존재하는 사용자명입니다.'}), 400
    
    users[username] = {
        'password_hash': generate_password_hash(password),
        'role': role,
        'email': email,
        'name': name,
        'created_at': datetime.now().isoformat(),
        'last_login': None,
        'is_active': True
    }
    
    save_users(users)
    return jsonify({'success': True, 'message': f'사용자 {username}이(가) 생성되었습니다.'})

# 사용자 역할 변경 (관리자만)
@app.route('/users/<username>/role', methods=['POST'])
@admin_required
def change_user_role(username):
    data = request.json
    new_role = data.get('role')
    if new_role not in ROLE_PERMISSIONS:
        return jsonify({'error': '존재하지 않는 역할입니다.'}), 400
    users = load_users()
    if username not in users:
        return jsonify({'error': '사용자를 찾을 수 없습니다.'}), 404
    users[username]['role'] = new_role
    save_users(users)
    return jsonify({'success': True, 'message': f'{username}의 역할이 {new_role}로 변경되었습니다.'})

@app.route('/change-password', methods=['POST'])
@login_required
def change_password():
    """현재 사용자의 비밀번호 변경"""
    data = request.json
    current_password = data.get('current_password')
    new_password = data.get('new_password')
    confirm_password = data.get('confirm_password')
    
    if not all([current_password, new_password, confirm_password]):
        return jsonify({'error': '모든 필드를 입력해주세요.'}), 400
    
    if new_password != confirm_password:
        return jsonify({'error': '새 비밀번호가 일치하지 않습니다.'}), 400
    
    if len(new_password) < 6:
        return jsonify({'error': '새 비밀번호는 최소 6자 이상이어야 합니다.'}), 400
    
    user_id = session.get('user_id')
    users = load_users()
    
    if user_id not in users:
        return jsonify({'error': '사용자를 찾을 수 없습니다.'}), 404
    
    # 현재 비밀번호 확인
    if not check_password_hash(users[user_id]['password_hash'], current_password):
        return jsonify({'error': '현재 비밀번호가 올바르지 않습니다.'}), 400
    
    # 새 비밀번호로 업데이트
    users[user_id]['password_hash'] = generate_password_hash(new_password)
    save_users(users)
    
    # 알림 추가
    add_notification(
        type='password_change',
        title='비밀번호 변경',
        message=f'사용자 {user_id}의 비밀번호가 변경되었습니다.',
        severity='info'
    )
    
    return jsonify({'success': True, 'message': '비밀번호가 성공적으로 변경되었습니다.'})

@app.route('/profile', methods=['GET'])
@login_required
def get_profile():
    """현재 사용자 프로필 조회"""
    user_id = session.get('user_id')
    users = load_users()
    
    if user_id not in users:
        return jsonify({'error': '사용자를 찾을 수 없습니다.'}), 404
    
    user_data = users[user_id]
    return jsonify({
        'username': user_id,
        'name': user_data.get('name', user_id),
        'email': user_data.get('email', ''),
        'role': user_data.get('role', 'user'),
        'created_at': user_data.get('created_at', ''),
        'last_login': user_data.get('last_login', '')
    })

@app.route('/profile-page')
@login_required
def profile_page():
    """프로필 페이지 렌더링"""
    return render_template('profile.html')

@app.route('/notifications', methods=['GET'])
@login_required
def get_notifications():
    """알림 목록 조회"""
    data = load_notifications()
    limit = request.args.get('limit', 20, type=int)
    notifications = data['notifications'][:limit]
    return jsonify({
        'notifications': notifications,
        'unread_count': get_unread_count()
    })

@app.route('/notifications/<int:notification_id>/read', methods=['POST'])
@login_required
def mark_notification_read(notification_id):
    """알림을 읽음으로 표시"""
    mark_as_read(notification_id)
    return jsonify({'success': True})

@app.route('/notifications/unread-count', methods=['GET'])
@login_required
def get_unread_notification_count():
    """읽지 않은 알림 수 조회"""
    return jsonify({'unread_count': get_unread_count()})

@app.route('/notifications/clear-all', methods=['POST'])
@login_required
def clear_all_notifications():
    """모든 알림 삭제"""
    data = load_notifications()
    data['notifications'] = []
    data['last_id'] = 0
    save_notifications(data)
    return jsonify({'success': True, 'message': '모든 알림이 삭제되었습니다.'})

@app.route('/projects', methods=['GET'])
def list_projects():
    """프로젝트(서버 그룹) 리스트 반환"""
    try:
        projects = [d for d in os.listdir(PROJECTS_DIR) if os.path.isdir(os.path.join(PROJECTS_DIR, d))]
        return jsonify({'projects': projects})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/delete_project/<project_name>', methods=['POST'])
def delete_project(project_name):
    """프로젝트(서버 그룹) 삭제"""
    project_path = os.path.join(PROJECTS_DIR, project_name)
    if not os.path.exists(project_path):
        return jsonify({'success': False, 'error': 'Project not found'}), 404
    try:
        # terraform destroy 실행
        subprocess.run(['terraform', 'destroy', '-auto-approve'], cwd=project_path, check=True)
        # 디렉토리 삭제
        import shutil
        shutil.rmtree(project_path)
        return jsonify({'success': True, 'message': f'{project_name} 프로젝트가 삭제되었습니다.'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/create_server', methods=['POST'])
@permission_required('create_server')
def create_server():
    logger.info(f"[create_server] 요청 데이터: {request.form.to_dict()}")
    try:
        # 2. 폼 데이터 수집 시 OS 타입 추가
        server_config = {
            'role': request.form.get('role'),
            'os_type': request.form.get('os_type', 'ubuntu'),  # OS 타입 추가
            'count': int(request.form.get('count', 1)),
            'cpu': int(request.form.get('cpu', 2)),
            'memory': int(request.form.get('memory', 2048)),
            'disks': request.form.getlist('disk'),
            'network_devices': int(request.form.get('network_devices', 1)),
            'ip_addresses': request.form.getlist('ip_address'),
            'project_name': request.form.get('project_name', f'project_{datetime.now().strftime("%Y%m%d_%H%M%S")}')
        }
        
        # 프로젝트 디렉토리 생성 (이미 존재하면 에러 반환)
        project_path = os.path.join(PROJECTS_DIR, server_config['project_name'])
        if os.path.exists(project_path):
            return jsonify({'success': False, 'error': '동일한 프로젝트명이 이미 존재합니다. 다른 이름을 사용하세요.'}), 400
        os.makedirs(project_path, exist_ok=False)
        
        # Terraform 파일 생성
        create_terraform_files(project_path, server_config)
        
        # Ansible 플레이북 생성
        create_ansible_playbook(project_path, server_config)
        
        # 백그라운드에서 인프라 생성 시작
        thread = threading.Thread(target=deploy_infrastructure, args=(project_path, server_config))
        thread.daemon = True
        thread.start()
        
        # 알림 추가
        add_notification(
            type='server_create',
            title='서버 생성 시작',
            message=f'프로젝트 "{server_config["project_name"]}"의 서버 생성이 시작되었습니다.',
            severity='info'
        )
        
        logger.info(f"[create_server] 서버 생성 성공: {request.form.get('project_name')}")
        return jsonify({
            'success': True,
            'message': '서버 생성이 시작되었습니다.',
            'project_name': server_config['project_name']
        })
        
    except Exception as e:
        logger.exception("[create_server] 서버 생성 중 예외 발생")
        # 에러 알림 추가
        add_notification(
            type='server_error',
            title='서버 생성 실패',
            message=f'프로젝트 "{server_config["project_name"]}"의 서버 생성 중 오류가 발생했습니다.',
            details=str(e),
            severity='error'
        )
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/servers', methods=['GET'])
@permission_required('view_all')
def list_servers():
    servers = read_servers_from_tfvars()
    return jsonify({'servers': servers})

def run_terraform_apply():
    import subprocess
    # terraform init 먼저 실행
    subprocess.run(['terraform', 'init', '-input=false'], cwd=TERRAFORM_DIR, capture_output=True, text=True)
    result = subprocess.run(['terraform', 'apply', '-auto-approve'], cwd=TERRAFORM_DIR, capture_output=True, text=True)
    return result.returncode == 0, result.stdout, result.stderr

def run_ansible_playbook():
    # 실제 환경에 맞게 inventory, playbook 경로 조정 필요
    import subprocess
    result = subprocess.run(['ansible-playbook', '-i', 'inventory', 'playbook.yml'], cwd=ANSIBLE_DIR, capture_output=True, text=True)
    return result.returncode == 0, result.stdout, result.stderr

# 넷마스크를 CIDR로 변환하는 함수 추가
def netmask_to_cidr(netmask):
    try:
        return str(sum([bin(int(x)).count('1') for x in netmask.split('.')]))
    except Exception:
        return netmask  # 변환 실패 시 원래 값 반환

@app.route('/add_server', methods=['POST'])
def add_server():
    data = request.json
    logger.info(f"[add_server] 요청: {data}")
    servers = read_servers_from_tfvars()
    server_name = data['name']
    if not server_name:
        logger.error("[add_server] 서버 이름 누락")
        return jsonify({'success': False, 'error': '서버 이름(name)을 입력해야 합니다.'}), 400
    if server_name in servers:
        logger.error(f"[add_server] 중복 서버 이름: {server_name}")
        return jsonify({'success': False, 'error': f'이미 동일한 이름({server_name})의 서버가 존재합니다.'}), 400
    # 역할 값이 없으면 빈 값으로 저장
    if 'role' not in data or not data['role']:
        data['role'] = ''
    # OS별 계정/비밀번호 저장
    os_type = data.get('os_type', 'rocky')
    data['vm_username'] = get_default_username(os_type)
    data['vm_password'] = get_default_password(os_type)
    # disks의 모든 요소에 datastore_id가 반드시 포함되도록 보정
    if 'disks' in data:
        for disk in data['disks']:
            if 'datastore_id' not in disk or not disk['datastore_id']:
                disk['datastore_id'] = 'local-lvm'
    # network_devices의 각 요소에 subnet, gateway가 누락되면 기본값 보정 (예: subnet=24, gateway='')
    if 'network_devices' in data:
        for net in data['network_devices']:
            # subnet이 넷마스크 표기면 CIDR로 변환
            if 'subnet' in net and '.' in str(net['subnet']):
                net['subnet'] = netmask_to_cidr(net['subnet'])
            if 'subnet' not in net or not net['subnet']:
                net['subnet'] = '24'
            if 'gateway' not in net:
                net['gateway'] = ''
    servers[server_name] = data
    write_servers_to_tfvars(servers)
    ok, out, err = run_terraform_apply()
    logger.info(f"[add_server] terraform apply 결과: ok={ok}, stdout={out}, stderr={err}")
    if not ok:
        # 실패 시 tfvars.json 백업
        import shutil
        from datetime import datetime
        backup_path = TFVARS_PATH + '.bak_' + datetime.now().strftime('%Y%m%d_%H%M%S')
        shutil.copy(TFVARS_PATH, backup_path)
        logger.info(f"[add_server] Terraform 실패로 tfvars.json 백업: {backup_path}")
        # 실패한 서버 정보 삭제
        del servers[server_name]
        write_servers_to_tfvars(servers)
        logger.info(f"[add_server] Terraform 실패로 서버 정보 삭제: {server_name}")
        return jsonify({'success': False, 'error': 'Terraform apply 실패', 'stdout': out, 'stderr': err}), 500
    logger.info(f"[add_server] 서버 추가 및 적용 완료: {server_name}")
    return jsonify({'success': True, 'message': f'{server_name} 서버가 추가 및 적용되었습니다.'})

@app.route('/delete_server/<server_name>', methods=['POST'])
@permission_required('delete_server')
def delete_server(server_name):
    logger.info(f"[delete_server] 서버: {server_name}")
    servers = read_servers_from_tfvars()
    if server_name in servers:
        del servers[server_name]
        write_servers_to_tfvars(servers)
        ok, out, err = run_terraform_apply()
        logger.info(f"[delete_server] terraform apply 결과: ok={ok}, stdout={out}, stderr={err}")
        if not ok:
            logger.error(f"[delete_server] Terraform apply 실패: {err}")
            return jsonify({'success': False, 'error': 'Terraform apply 실패', 'stdout': out, 'stderr': err}), 500
        logger.info(f"[delete_server] 서버 삭제 및 적용 완료: {server_name}")
        return jsonify({'success': True, 'message': f'{server_name} 서버가 삭제 및 적용되었습니다.'})
    else:
        logger.error(f"[delete_server] 서버를 찾을 수 없음: {server_name}")
        return jsonify({'success': False, 'error': '서버를 찾을 수 없습니다.'}), 404

@app.route('/stop_server/<server_name>', methods=['POST'])
def stop_server(server_name):
    logger.info(f"[stop_server] 요청: {server_name}")
    try:
        # ansible-playbook -i inventory playbook.yml --extra-vars "target=<server_name> action=stop"
        result = subprocess.run([
            'ansible-playbook', '-i', 'inventory', 'playbook.yml',
            '--extra-vars', f"target={server_name} action=stop"
        ], cwd=ANSIBLE_DIR, capture_output=True, text=True)
        if result.returncode == 0:
            logger.info(f"[stop_server] VM 중지 요청: vmid={target_vm['vmid']}")
            return jsonify({'success': True, 'message': f'{server_name} 서버가 중지되었습니다.'})
        else:
            logger.error(f"[stop_server] 중지 실패: {result.stderr}")
            return jsonify({'success': False, 'error': result.stderr}), 500
    except Exception as e:
        logger.exception(f"[stop_server] 예외 발생: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/reboot_server/<server_name>', methods=['POST'])
def reboot_server(server_name):
    logger.info(f"[reboot_server] 요청: {server_name}")
    try:
        # ansible-playbook -i inventory playbook.yml --extra-vars "target=<server_name> action=reboot"
        result = subprocess.run([
            'ansible-playbook', '-i', 'inventory', 'playbook.yml',
            '--extra-vars', f"target={server_name} action=reboot"
        ], cwd=ANSIBLE_DIR, capture_output=True, text=True)
        if result.returncode == 0:
            logger.info(f"[reboot_server] VM 리부팅 요청: vmid={target_vm['vmid']}")
            return jsonify({'success': True, 'message': f'{server_name} 서버가 리부팅되었습니다.'})
        else:
            logger.error(f"[reboot_server] 리부팅 실패: {result.stderr}")
            return jsonify({'success': False, 'error': result.stderr}), 500
    except Exception as e:
        logger.exception(f"[reboot_server] 예외 발생: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/server_status/<server_name>', methods=['GET'])
@login_required
def get_server_status(server_name):
    """특정 서버의 상태를 Proxmox에서 가져오기"""
    try:
        import requests
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        # Proxmox API 설정 (환경 변수에서 가져오기)
        proxmox_url = app.config['PROXMOX_ENDPOINT']
        username = app.config['PROXMOX_USERNAME']
        password = app.config['PROXMOX_PASSWORD']
        
        # API 인증
        auth_url = f"{proxmox_url}/api2/json/access/ticket"
        auth_data = {
            'username': username,
            'password': password
        }
        
        auth_response = requests.post(auth_url, data=auth_data, verify=False)
        if auth_response.status_code != 200:
            return jsonify({'error': 'Proxmox 인증 실패'}), 401
        
        auth_result = auth_response.json()
        if 'data' not in auth_result:
            return jsonify({'error': '인증 토큰을 가져올 수 없습니다'}), 401
        
        ticket = auth_result['data']['ticket']
        csrf_token = auth_result['data']['CSRFPreventionToken']
        
        # VM 목록 가져오기
        headers = {
            'Cookie': f'PVEAuthCookie={ticket}',
            'CSRFPreventionToken': csrf_token
        }
        
        # 모든 노드에서 VM 검색
        nodes_url = f"{proxmox_url}/api2/json/nodes"
        nodes_response = requests.get(nodes_url, headers=headers, verify=False)
        
        if nodes_response.status_code != 200:
            return jsonify({'error': '노드 정보를 가져올 수 없습니다'}), 500
        
        nodes = nodes_response.json().get('data', [])
        
        # 모든 노드에서 VM 검색
        for node in nodes:
            node_name = node['node']
            vms_url = f"{proxmox_url}/api2/json/nodes/{node_name}/qemu"
            vms_response = requests.get(vms_url, headers=headers, verify=False)
            
            if vms_response.status_code == 200:
                vms = vms_response.json().get('data', [])
                for vm in vms:
                    if vm['name'] == server_name:
                        # VM 상태 정보 반환
                        status_info = {
                            'name': vm['name'],
                            'status': vm['status'],  # running, stopped, paused 등
                            'vmid': vm['vmid'],
                            'node': node_name,
                            'cpu': vm.get('cpu', 0),
                            'memory': vm.get('mem', 0),
                            'maxmem': vm.get('maxmem', 0),
                            'uptime': vm.get('uptime', 0),
                            'disk': vm.get('disk', 0),
                            'maxdisk': vm.get('maxdisk', 0)
                        }
                        return jsonify(status_info)
        
        return jsonify({'error': f'서버 {server_name}을 찾을 수 없습니다'}), 404
        
    except Exception as e:
        return jsonify({'error': f'서버 상태 확인 실패: {str(e)}'}), 500

@app.route('/all_server_status', methods=['GET'])
@login_required
def get_all_server_status():
    """모든 서버의 상태를 Proxmox에서 가져오기"""
    try:
        import requests
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        # Proxmox API 설정 (환경 변수에서 가져오기)
        proxmox_url = app.config['PROXMOX_ENDPOINT']
        username = app.config['PROXMOX_USERNAME']
        password = app.config['PROXMOX_PASSWORD']
        
        # API 인증
        auth_url = f"{proxmox_url}/api2/json/access/ticket"
        auth_data = {
            'username': username,
            'password': password
        }
        
        auth_response = requests.post(auth_url, data=auth_data, verify=False)
        if auth_response.status_code != 200:
            return jsonify({'error': 'Proxmox 인증 실패'}), 401
        
        auth_result = auth_response.json()
        if 'data' not in auth_result:
            return jsonify({'error': '인증 토큰을 가져올 수 없습니다'}), 401
        
        ticket = auth_result['data']['ticket']
        csrf_token = auth_result['data']['CSRFPreventionToken']
        
        # VM 목록 가져오기
        headers = {
            'Cookie': f'PVEAuthCookie={ticket}',
            'CSRFPreventionToken': csrf_token
        }
        
        # 모든 노드에서 VM 검색
        nodes_url = f"{proxmox_url}/api2/json/nodes"
        nodes_response = requests.get(nodes_url, headers=headers, verify=False)
        
        if nodes_response.status_code != 200:
            return jsonify({'error': '노드 정보를 가져올 수 없습니다'}), 500
        
        nodes = nodes_response.json().get('data', [])
        
        all_servers = {}
        total_memory = 0
        running_count = 0
        stopped_count = 0
        
        # 모든 노드에서 VM 검색
        for node in nodes:
            node_name = node['node']
            vms_url = f"{proxmox_url}/api2/json/nodes/{node_name}/qemu"
            vms_response = requests.get(vms_url, headers=headers, verify=False)
            
            if vms_response.status_code == 200:
                vms = vms_response.json().get('data', [])
                for vm in vms:
                    # terraform.tfvars.json에 있는 서버만 필터링
                    servers = read_servers_from_tfvars()
                    if vm['name'] in servers:
                        server_data = servers[vm['name']]
                        # IP 정보 추출 (network_devices 또는 ip_addresses)
                        ip_list = []
                        if 'network_devices' in server_data and server_data['network_devices']:
                            ip_list = [nd.get('ip_address') for nd in server_data['network_devices'] if nd.get('ip_address')]
                        elif 'ip_addresses' in server_data and server_data['ip_addresses']:
                            ip_list = server_data['ip_addresses']
                        status_info = {
                            'name': vm['name'],
                            'status': vm['status'],  # running, stopped, paused 등
                            'vmid': vm['vmid'],
                            'node': node_name,
                            'cpu': vm.get('cpu', 0),
                            'memory': vm.get('mem', 0),
                            'maxmem': vm.get('maxmem', 0),
                            'uptime': vm.get('uptime', 0),
                            'disk': vm.get('disk', 0),
                            'maxdisk': vm.get('maxdisk', 0),
                            'role': server_data.get('role', 'unknown'),
                            'ip_addresses': ip_list
                        }
                        all_servers[vm['name']] = status_info
                        
                        # 통계 계산
                        if vm['status'] == 'running':
                            running_count += 1
                            total_memory += vm.get('maxmem', 0)
                        else:
                            stopped_count += 1
        
        # 통계 정보 추가
        stats = {
            'total_servers': len(all_servers),
            'running_servers': running_count,
            'stopped_servers': stopped_count,
            'total_memory_gb': round(total_memory / (1024 * 1024 * 1024), 1)
        }
        
        return jsonify({
            'servers': all_servers,
            'stats': stats
        })
        
    except Exception as e:
        return jsonify({'error': f'서버 상태 확인 실패: {str(e)}'}), 500

@app.route('/proxmox_storage', methods=['GET'])
def proxmox_storage():
    logger.info("[proxmox_storage] 스토리지 정보 요청")
    try:
        import requests
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        proxmox_url = "https://prox.dmcmedia.co.kr:8006"
        username = "root@pam"
        password = "dmc1234)(*&"
        node = "prox"
        
        # API 인증
        auth_url = f"{proxmox_url}/api2/json/access/ticket"
        auth_data = {
            'username': username,
            'password': password
        }
        auth_response = requests.post(auth_url, data=auth_data, verify=False)
        if auth_response.status_code != 200:
            return {'error': 'Proxmox 인증 실패'}, 401
        auth_result = auth_response.json()
        ticket = auth_result['data']['ticket']
        csrf_token = auth_result['data']['CSRFPreventionToken']
        headers = {
            'Cookie': f'PVEAuthCookie={ticket}',
            'CSRFPreventionToken': csrf_token
        }
        # 스토리지 정보 조회
        storage_url = f"{proxmox_url}/api2/json/nodes/{node}/storage"
        storage_response = requests.get(storage_url, headers=headers, verify=False)
        logger.info(f"[proxmox_storage] Proxmox 응답: {storage_response.status_code}, {storage_response.text}")
        if storage_response.status_code != 200:
            logger.error("[proxmox_storage] 스토리지 정보를 가져올 수 없습니다")
            return {'error': '스토리지 정보를 가져올 수 없습니다'}, 500
        storages = storage_response.json().get('data', [])
        # 용량 정보만 추출
        result = []
        for s in storages:
            if 'total' in s and 'used' in s:
                result.append({
                    'storage': s.get('storage'),
                    'type': s.get('type'),
                    'total': s.get('total', 0),
                    'used': s.get('used', 0)
                })
        logger.info(f"[proxmox_storage] 반환: {result}")
        return {'storages': result}
    except Exception as e:
        logger.exception(f"[proxmox_storage] 예외 발생: {e}")
        return {'error': str(e)}, 500

def create_terraform_files(project_path, config):
    """Terraform 파일 생성 - OS별 템플릿 ID 지원"""
    # OS별 템플릿 ID 매핑
    template_mapping = {
        'rocky': 8000, 
        'ubuntu': 9000 # Rocky Linux 8 템플릿 ID
    }
    
    template_id = template_mapping.get(config['os_type'], 8000)
    
    # main.tf 생성
    main_tf = f"""
terraform {{
  required_providers {{
    proxmox = {{
      source  = "bpg/proxmox"
      version = "~> 0.40"
    }}
  }}
}}

provider "proxmox" {{
  endpoint = var.proxmox_endpoint
  username = var.proxmox_username
  password = var.proxmox_password
  insecure = true
}}

resource "proxmox_virtual_environment_vm" "server" {{
  count = {config['count']}
  name  = "${{var.project_name}}-{config['role']}-${{count.index + 1}}"
  
  node_name = var.proxmox_node
  
  cpu {{
    cores = {config['cpu']}
  }}
  
  memory {{
    dedicated = {config['memory']}
  }}
  
  {generate_disk_blocks(config['disks'])}
  
  {generate_network_devices(config['network_devices'], config['ip_addresses'])}
  
  initialization {{
    user_account {{
      username = var.vm_username
      password = var.vm_password
      keys    = var.ssh_keys
    }}
    
    ip_config {{
      ipv4 {{
        address = "${{var.ip_addresses[count.index]}}/24"
        gateway = var.gateway
      }}
    }}
  }}
  
  operating_system {{
    type = "l26"
  }}
  
  clone {{
    vm_id = var.template_vm_id
  }}

}}

output "vm_ips" {{
  value = proxmox_virtual_environment_vm.server[*].ipv4_addresses
}}

output "vm_names" {{
  value = proxmox_virtual_environment_vm.server[*].name
}}
"""
    
    # variables.tf 생성
    variables_tf = """
variable "proxmox_endpoint" {
  description = "Proxmox VE endpoint"
  type        = string
}

variable "proxmox_username" {
  description = "Proxmox VE username"
  type        = string
}

variable "proxmox_password" {
  description = "Proxmox VE password"
  type        = string
}

variable "proxmox_node" {
  description = "Proxmox VE node name"
  type        = string
}

variable "proxmox_datastore" {
  description = "Proxmox VE datastore"
  type        = string
}

variable "project_name" {
  description = "Project name"
  type        = string
}

variable "vm_username" {
  description = "VM username"
  type        = string
}

variable "vm_password" {
  description = "VM password"
  type        = string
}

variable "ssh_keys" {
  description = "ssh keys"
  type        = list(string)
}

variable "template_vm_id" {
  description = "Template VM ID"
  type        = number
}

variable "ip_addresses" {
  description = "IP addresses for VMs"
  type        = list(string)
}

variable "gateway" {
  description = "Gateway IP"
  type        = string
}
"""

    # terraform.tfvars 생성
    tfvars = f"""
proxmox_endpoint = "https://prox.dmcmedia.co.kr:8006"
proxmox_username = "root@pam"
proxmox_password = "dmc1234)(*&"
proxmox_node = "prox"
proxmox_datastore = "local-lvm"
project_name = "{config['project_name']}"
vm_username = "{get_default_username(config['os_type'])}"
vm_password = "{get_default_password(config['os_type'])}"
ssh_keys = ["ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQC5YjxN0N+Xbuv3RJwcUxBXqwlueHXNMidIXHagPO6xXovqo/ypq1EHMKJKXKQND1G2pACX1EIDIF/6gLFVOAMn1tzeiMttn4UskHLGz+oM7PMS3uFnVIN/uBQNDlYxKcyiYvdrP+mxiQsa7lyuxYfcAySoFx64l+giAGppKNuDPBz2SPY87I+V06/+eo6Rnd2XHmJvqpVclEwezZ+WQfkFYRKxxnWAWl2m6apdio2kPyRxEwCP19moyVlQhm5b+IAoktHgaDYFr1YrQ9J/QCSVYkiG3IDCOwI4k+O0MaV5Uelj0NaTDv4Pb2Dv2/86VPTrKOucSs8o0JqboHjKtfEKfmDym25YnTaF+tXGzPkAk8b3l7oESC2SFvPTO3lyiE84dGniQNtJg9YwUb5NxynOk9yydd0L3E6ikfTpdokwjd49GgE/KxkcZjhrxLwUMyJ0SLf/vqaRc9GmTn7JTeqnObMhArXjHuTXmfcL2Q9DYEREVfioWLgu7CPxfdS2+fc= dmc_dev@localhost.localdomain"]
template_vm_id = {template_id}
ip_addresses = {json.dumps(config['ip_addresses'])}
gateway = "192.168.0.1"
os_type = "{config['os_type']}"
"""

    # 파일 저장
    with open(os.path.join(project_path, 'main.tf'), 'w') as f:
        f.write(main_tf)
    
    with open(os.path.join(project_path, 'variables.tf'), 'w') as f:
        f.write(variables_tf)
    
    with open(os.path.join(project_path, 'terraform.tfvars'), 'w') as f:
        f.write(tfvars)

def get_default_username(os_type):
    """OS별 기본 사용자명 반환"""
    defaults = {
        'rocky': 'rocky',
        'ubuntu': 'ubuntu'
    }
    return defaults.get(os_type, 'rocky')

def get_default_password(os_type):
    """OS별 기본 비밀번호 반환"""
    defaults = {
        'rocky': 'rocky123',
        'ubuntu': 'ubuntu123'
    }
    return defaults.get(os_type, 'rocky123') 

def generate_disk_blocks(disks):
    blocks = []
    for idx, disk in enumerate(disks):
        iface = disk.get('interface') or f'scsi{idx}'
        size = disk.get('size', 20)
        datastore = disk.get('datastore_id', 'local-lvm')
        blocks.append(f'''
  disk {{
    interface = "{iface}"
    size      = {size}
    file_format = "qcow2"
    datastore_id = "{datastore}"
  }}''')
    return '\n'.join(blocks)

def generate_network_devices(device_count, ip_addresses):
    """네트워크 디바이스 생성"""
    network_configs = []
    for i in range(device_count):
        network_config = f"""
  network_device {{
    bridge = "vmbr{i}"
  }}"""
        network_configs.append(network_config)
    return ''.join(network_configs)

def create_ansible_playbook(project_path, config):
    """Ansible 플레이북 생성"""
    role_info = SERVER_ROLES.get(config['role'], {})
    os_type = config['os_type']
    
    # 인벤토리 파일 생성
    inventory = f"""
[{config['role']}_servers]
"""
    username = get_default_username(os_type)
    for i, ip in enumerate(config['ip_addresses']):
        inventory += f"{config['project_name']}-{config['role']}-{i+1} ansible_host={ip} ansible_user={username} ansible_ssh_common_args='-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null'\n"
    
    # 플레이북 생성
    playbook = {
        'name': f'Configure {role_info.get("name", config["role"])} servers',
        'hosts': f'{config["role"]}_servers',
        'become': True,
        'tasks': [
            {
                'name': 'Update apt cache',
                'apt': {
                    'update_cache': True,
                    'cache_valid_time': 3600
                },
                'when': 'ansible_os_family == "Debian"'
            },
            {
                'name': 'Install required packages',
                'apt': {
                    'name': role_info.get('packages', []),
                    'state': 'present'
                },
                'when': 'ansible_os_family == "Debian"'
            },
            {
                'name': 'Update package cache (Rocky/RHEL)',
                'yum': {
                    'update_cache': True
                },
                'when': 'ansible_os_family == "RedHat"'
            }
        ]
    }

    # OS별 패키지 설치
    packages = role_info.get('packages', {})
    if isinstance(packages, dict):
        ubuntu_packages = packages.get('ubuntu', [])
        rocky_packages = packages.get('rocky', [])
        
        if ubuntu_packages:
            playbook['tasks'].append({
                'name': 'Install required packages (Ubuntu)',
                'apt': {
                    'name': ubuntu_packages,
                    'state': 'present'
                },
                'when': 'ansible_os_family == "Debian"'
            })
        
        if rocky_packages:
            playbook['tasks'].append({
                'name': 'Install required packages (Rocky)',
                'yum': {
                    'name': rocky_packages,
                    'state': 'present'
                },
                'when': 'ansible_os_family == "RedHat"'
            })
    

   # 서비스 시작 (OS별 서비스명 고려)
    services = role_info.get('services', [])
    if isinstance(services, dict):
        # OS별 서비스명이 다른 경우
        ubuntu_services = services.get('ubuntu', [])
        rocky_services = services.get('rocky', [])
        
        for service in ubuntu_services:
            playbook['tasks'].append({
                'name': f'Start and enable {service} (Ubuntu)',
                'systemd': {
                    'name': service,
                    'state': 'started',
                    'enabled': True
                },
                'when': 'ansible_os_family == "Debian"'
            })
        
        for service in rocky_services:
            playbook['tasks'].append({
                'name': f'Start and enable {service} (Rocky)',
                'systemd': {
                    'name': service,
                    'state': 'started',
                    'enabled': True
                },
                'when': 'ansible_os_family == "RedHat"'
            })
    else:
        # 공통 서비스명인 경우
        for service in services:
            playbook['tasks'].append({
                'name': f'Start and enable {service}',
                'systemd': {
                    'name': service,
                    'state': 'started',
                    'enabled': True
                }
            })
    
    # Rocky Linux 전용 설정
    if os_type == 'rocky':
        playbook['tasks'].extend([
            {
                'name': 'Enable EPEL repository',
                'yum': {
                    'name': 'epel-release',
                    'state': 'present'
                }
            },
            {
                'name': 'Disable SELinux (if needed)',
                'selinux': {
                    'state': 'permissive',
                    'policy': 'targeted'
                },
                'when': 'ansible_selinux.status == "enabled"'
            }
        ])
    
    # 역할별 특별 설정도 OS별로 분기
    if config['role'] == 'web':
        if os_type == 'ubuntu':
            playbook['tasks'].extend([
                {
                    'name': 'Create nginx config (Ubuntu)',
                    'template': {
                        'src': 'nginx.conf.j2',
                        'dest': '/etc/nginx/sites-available/default'
                    },
                    'when': 'ansible_os_family == "Debian"'
                },
                {
                    'name': 'Enable nginx site (Ubuntu)',
                    'file': {
                        'src': '/etc/nginx/sites-available/default',
                        'dest': '/etc/nginx/sites-enabled/default',
                        'state': 'link'
                    },
                    'when': 'ansible_os_family == "Debian"'
                }
            ])
        elif os_type == 'rocky':
            playbook['tasks'].extend([
                {
                    'name': 'Create nginx config (Rocky)',
                    'template': {
                        'src': 'nginx-rocky.conf.j2',
                        'dest': '/etc/nginx/nginx.conf'
                    },
                    'when': 'ansible_os_family == "RedHat"'
                },
                {
                    'name': 'Open firewall for HTTP (Rocky)',
                    'firewalld': {
                        'service': 'http',
                        'permanent': True,
                        'state': 'enabled'
                    },
                    'when': 'ansible_os_family == "RedHat"'
                }
            ])
    
    elif config['role'] == 'db':
        if os_type == 'ubuntu':
            playbook['tasks'].extend([
                {
                    'name': 'Secure MySQL installation (Ubuntu)',
                    'mysql_user': {
                        'name': 'root',
                        'password': 'mysql_root_password',
                        'login_unix_socket': '/var/run/mysqld/mysqld.sock'
                    },
                    'when': 'ansible_os_family == "Debian"'
                }
            ])
        elif os_type == 'rocky':
            playbook['tasks'].extend([
                {
                    'name': 'Start MySQL service (Rocky)',
                    'systemd': {
                        'name': 'mysqld',
                        'state': 'started',
                        'enabled': True
                    },
                    'when': 'ansible_os_family == "RedHat"'
                },
                {
                    'name': 'Get MySQL temporary password (Rocky)',
                    'shell': "grep 'temporary password' /var/log/mysqld.log | awk '{print $NF}'",
                    'register': 'mysql_temp_password',
                    'when': 'ansible_os_family == "RedHat"'
                }
            ])
    
    # 파일 저장
    with open(os.path.join(project_path, 'inventory'), 'w') as f:
        f.write(inventory)
    
    with open(os.path.join(project_path, 'playbook.yml'), 'w') as f:
        yaml.dump([playbook], f, default_flow_style=False, indent=2)

def deploy_infrastructure(project_path, config):
    """인프라 배포 실행"""
    try:
        # Terraform 초기화
        subprocess.run(['terraform', 'init'], cwd=project_path, check=True)
        
        # Terraform 계획
        subprocess.run(['terraform', 'plan'], cwd=project_path, check=True)
        
        # Terraform 적용
        result = subprocess.run(['terraform', 'apply', '-auto-approve'], 
                              cwd=project_path, check=True, capture_output=True, text=True)
        
        # 생성된 IP 주소 추출
        output_result = subprocess.run(['terraform', 'output', '-json'], 
                                     cwd=project_path, capture_output=True, text=True)
        
        if output_result.returncode == 0:
            outputs = json.loads(output_result.stdout)
            vm_ips = outputs.get('vm_ips', {}).get('value', [])
            
            # 서버가 준비될 때까지 대기
            time.sleep(30)
            
            # Ansible 플레이북 실행
            subprocess.run(['ansible-playbook', '-i', 'inventory', 'playbook.yml'], 
                          cwd=project_path, check=True)
            
            print(f"Infrastructure deployed successfully for project: {config['project_name']}")
            print(f"VM IPs: {vm_ips}")
        
    except subprocess.CalledProcessError as e:
        print(f"Error deploying infrastructure: {e}")
        print(f"Error output: {e.stderr if hasattr(e, 'stderr') else ''}")

@app.route('/status/<project_name>')
def get_status(project_name):
    """프로젝트 상태 조회"""
    project_path = os.path.join(PROJECTS_DIR, project_name)
    
    if not os.path.exists(project_path):
        return jsonify({'error': 'Project not found'}), 404
    
    try:
        # Terraform 상태 확인
        result = subprocess.run(['terraform', 'show', '-json'], 
                              cwd=project_path, capture_output=True, text=True)
        
        if result.returncode == 0:
            state = json.loads(result.stdout)
            return jsonify({
                'project_name': project_name,
                'status': 'deployed',
                'resources': len(state.get('values', {}).get('root_module', {}).get('resources', []))
            })
        else:
            return jsonify({
                'project_name': project_name,
                'status': 'not_deployed',
                'resources': 0
            })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/assign_role/<server_name>', methods=['POST'])
@permission_required('assign_roles')
def assign_role(server_name):
    logger.info(f"[assign_role] 서버: {server_name}, 요청 데이터: {request.form.to_dict()}")
    role = request.form.get('role') or request.json.get('role')
    if not role:
        return jsonify({'success': False, 'error': '역할(role)을 지정해야 합니다.'}), 400
    servers = read_servers_from_tfvars()
    if server_name not in servers:
        return jsonify({'success': False, 'error': '서버를 찾을 수 없습니다.'}), 404
    # 서버 IP/계정 추출
    server = servers[server_name]
    ip = None
    if 'network_devices' in server and server['network_devices']:
        ip = server['network_devices'][0].get('ip_address')
    if not ip:
        return jsonify({'success': False, 'error': '서버의 IP 정보를 찾을 수 없습니다.'}), 400
    username = server.get('vm_username', get_default_username(server.get('os_type', 'rocky')))
    # 임시 인벤토리 파일 생성
    import datetime
    import os
    import tempfile
    now_str = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    log_dir = os.path.join('logs')
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, f'assign_role_{server_name}_{now_str}.log')
    with tempfile.NamedTemporaryFile('w', delete=False, dir='/tmp', prefix=f'inventory_{server_name}_', suffix='.ini') as f:
        f.write(f'{server_name} ansible_host={ip} ansible_user={username} ansible_ssh_common_args="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"\n')
        inventory_path = f.name
    # ansible-playbook 실행
    try:
        result = subprocess.run([
            'ansible-playbook', '-i', inventory_path, 'role_playbook.yml',
            '-e', f'role={role}'
        ], cwd=ANSIBLE_DIR, capture_output=True, text=True)
        os.unlink(inventory_path)
        # 로그 파일 저장
        with open(log_path, 'w', encoding='utf-8') as logf:
            logf.write('=== STDOUT ===\n')
            logf.write(result.stdout)
            logf.write('\n=== STDERR ===\n')
            logf.write(result.stderr)
        if result.returncode == 0:
            # 역할 변경
            server['role'] = role
            servers[server_name] = server
            write_servers_to_tfvars(servers)
            logger.info(f"[assign_role] 역할 할당 성공: {server_name}")
            return jsonify({'success': True, 'message': f'역할({role})이 적용되었습니다.', 'stdout': result.stdout, 'stderr': result.stderr, 'log_path': log_path})
        else:
            logger.error(f"[assign_role] Ansible 실행 실패: {result.stderr}")
            return jsonify({'success': False, 'error': 'Ansible 실행 실패', 'stdout': result.stdout, 'stderr': result.stderr, 'log_path': log_path}), 500
    except Exception as e:
        logger.exception(f"[assign_role] 역할 할당 중 예외 발생: {e}")
        if os.path.exists(inventory_path):
            os.unlink(inventory_path)
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/remove_role/<server_name>', methods=['POST'])
def remove_role(server_name):
    servers = read_servers_from_tfvars()
    if server_name not in servers:
        return jsonify({'success': False, 'error': '서버를 찾을 수 없습니다.'}), 404
    # 역할 제거
    servers[server_name]['role'] = ''
    write_servers_to_tfvars(servers)
    # (옵션) ansible-playbook로 서비스 중지/삭제 역할 실행 가능
    return jsonify({'success': True, 'message': '역할이 삭제되었습니다.'})

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('app.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

if __name__ == '__main__':
    # 필요한 디렉토리 생성
    os.makedirs(PROJECTS_DIR, exist_ok=True)
    os.makedirs('templates', exist_ok=True)
    
    app.run(debug=True, host='0.0.0.0', port=5000)