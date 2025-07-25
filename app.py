from flask import Flask, render_template, request, jsonify, redirect, url_for, session
import subprocess
import os
import json
import yaml
from datetime import datetime
import threading
import time
import logging
import tempfile
import secrets
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from database import db
import requests

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

# --- 권한/상수/데코레이터 정의를 상단에 위치 ---
TERRAFORM_DIR = 'terraform'
ANSIBLE_DIR = 'ansible'
PROJECTS_DIR = 'projects'
TFVARS_PATH = os.path.join(TERRAFORM_DIR, 'terraform.tfvars.json')

PERMISSION_LIST = [
    'view_all', 'create_server', 'delete_server', 'assign_roles', 'remove_roles', 'manage_users', 'view_logs', 'manage_roles'
]

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': '로그인이 필요합니다.'}), 401
        user = get_user(session['user_id'])
        if not user or 'admin' != user.get('role'):
            return jsonify({'error': '관리자 권한이 필요합니다.'}), 403
        return f(*args, **kwargs)
    return decorated_function

def permission_required(permission):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                return jsonify({'error': '로그인이 필요합니다.'}), 401
            user = get_user(session['user_id'])
            if not user:
                return jsonify({'error': '사용자 정보를 찾을 수 없습니다.'}), 403
            # admin은 무조건 통과
            if user.get('role') == 'admin':
                return f(*args, **kwargs)
            if permission not in user.get('permissions', []):
                return jsonify({'error': '권한이 없습니다.'}), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator

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

# 파일 기반 사용자 관리
def load_users():
    """users.json에서 사용자 정보 로드 및 permissions 필드 마이그레이션"""
    try:
        with open('users.json', 'r', encoding='utf-8') as f:
            users = json.load(f)
    except FileNotFoundError:
        # 기본 사용자 생성
        users = {
            'admin': {
                'password_hash': generate_password_hash('admin123!'),
                'role': 'admin',
                'email': 'admin@dmcmedia.co.kr',
                'name': '시스템 관리자',
                'created_at': datetime.now().isoformat(),
                'last_login': None,
                'is_active': True,
                'permissions': PERMISSION_LIST.copy()
            }
        }
        save_users(users)
        return users
    # 마이그레이션: permissions 필드가 없으면 추가
    changed = False
    for username, user in users.items():
        if 'permissions' not in user:
            if user.get('role') == 'admin':
                user['permissions'] = PERMISSION_LIST.copy()
            else:
                # 기본 권한: view_all만 부여
                user['permissions'] = ['view_all']
            changed = True
    if changed:
        save_users(users)
    return users

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
    user = get_user(session['user_id'])
    # 세션에 permissions 저장
    session['permissions'] = user.get('permissions', []) if user else []
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
            session['permissions'] = user.get('permissions', [])
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
@permission_required('manage_users')
def list_users():
    """사용자 목록 조회 (권한 필요)"""
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
            'last_login': user_data.get('last_login', ''),
            'permissions': user_data.get('permissions', [])
        }
    return jsonify({'users': safe_users})

@app.route('/users', methods=['POST'])
@permission_required('manage_users')
def create_user():
    """새 사용자 생성 (권한 필요)"""
    data = request.json
    username = data.get('username')
    password = data.get('password')
    name = data.get('name', username)
    email = data.get('email', '')
    role = data.get('role', 'viewer')
    permissions = data.get('permissions')
    if not permissions:
        # 기본 권한: view_all만 부여
        permissions = ['view_all']
    if role == 'admin':
        permissions = PERMISSION_LIST.copy()
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
        'is_active': True,
        'permissions': permissions
    }
    save_users(users)
    return jsonify({'success': True, 'message': f'사용자 {username}이(가) 생성되었습니다.'})

@app.route('/users/<username>/permissions', methods=['POST'])
@permission_required('manage_users')
def change_user_permissions(username):
    data = request.json
    permissions = data.get('permissions', [])
    users = load_users()
    if username not in users:
        return jsonify({'error': '사용자를 찾을 수 없습니다.'}), 404
    if users[username].get('role') == 'admin':
        return jsonify({'error': 'admin 권한은 변경할 수 없습니다.'}), 400
    users[username]['permissions'] = permissions
    save_users(users)
    return jsonify({'success': True, 'message': f'{username}의 권한이 변경되었습니다.'})

@app.route('/users/<username>/role', methods=['POST'])
@permission_required('manage_users')
def change_user_role(username):
    data = request.json
    new_role = data.get('role')
    users = load_users()
    if username not in users:
        return jsonify({'error': '사용자를 찾을 수 없습니다.'}), 404
    if new_role == 'admin':
        users[username]['role'] = 'admin'
        users[username]['permissions'] = PERMISSION_LIST.copy()
    else:
        users[username]['role'] = new_role
        # 기존 권한 유지(별도 변경 가능)
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

@app.route('/notifications/add', methods=['POST'])
def add_notification_api():
    data = request.form or request.json
    add_notification(
        type=data.get('type', 'info'),
        title=data.get('title', ''),
        message=data.get('message', ''),
        severity=data.get('type', 'info')
    )
    return jsonify({'success': True})

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
    print("[DEBUG] create_server 진입")
    logger.info("[DEBUG] create_server 진입")
    logger.info(f"[create_server] 요청 데이터: {request.form.to_dict()}")
    try:
        print("[DEBUG] 서버 생성 로직 시작")
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
        # 알림: 서버 생성 시작
        add_notification(
            type='server_create',
            title='서버 생성 시작',
            message=f'프로젝트 "{server_config["project_name"]}"의 서버 생성이 시작되었습니다.',
            severity='info'
        )
        # 백그라운드에서 인프라 생성 시작
        def infra_and_notify():
            try:
                deploy_infrastructure(project_path, server_config)
                # 알림: 서버 생성 완료
                add_notification(
                    type='server_create',
                    title='서버 생성 완료',
                    message=f'프로젝트 "{server_config["project_name"]}"의 서버 생성이 완료되었습니다.',
                    severity='success'
                )
            except Exception as e:
                add_notification(
                    type='server_error',
                    title='서버 생성 실패',
                    message=f'프로젝트 "{server_config["project_name"]}"의 서버 생성 중 오류가 발생했습니다.',
                    details=str(e),
                    severity='error'
                )
        thread = threading.Thread(target=infra_and_notify)
        thread.daemon = True
        thread.start()
        print("[DEBUG] 서버 생성 성공")
        logger.info("[DEBUG] 서버 생성 성공")
        logger.info(f"[create_server] 서버 생성 성공: {request.form.get('project_name')}")
        return jsonify({
            'success': True,
            'message': '서버 생성이 시작되었습니다.',
            'project_name': server_config['project_name']
        })
    except Exception as e:
        logger.exception("[create_server] 서버 생성 중 예외 발생")
        print(f"[DEBUG] 예외 발생: {e}")
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
@permission_required('create_server')
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
    if 'role' not in data or not data['role']:
        data['role'] = ''
    os_type = data.get('os_type', 'rocky')
    data['vm_username'] = get_default_username(os_type)
    data['vm_password'] = get_default_password(os_type)
    if 'disks' in data:
        for disk in data['disks']:
            if 'datastore_id' not in disk or not disk['datastore_id']:
                disk['datastore_id'] = 'local-lvm'
    if 'network_devices' in data:
        for net in data['network_devices']:
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
        import shutil
        from datetime import datetime
        backup_path = TFVARS_PATH + '.bak_' + datetime.now().strftime('%Y%m%d_%H%M%S')
        shutil.copy(TFVARS_PATH, backup_path)
        logger.info(f"[add_server] Terraform 실패로 tfvars.json 백업: {backup_path}")
        del servers[server_name]
        write_servers_to_tfvars(servers)
        logger.info(f"[add_server] Terraform 실패로 서버 정보 삭제: {server_name}")
        return jsonify({'success': False, 'error': 'Terraform apply 실패', 'stdout': out, 'stderr': err}), 500
    # --- VM 생성 후 Proxmox에서 정보 조회 및 DB 저장 ---
    vm_info = get_vm_info_from_proxmox(server_name)
    if not vm_info:
        logger.error(f"[add_server] Proxmox에서 VM 정보 조회 실패: {server_name}")
        return jsonify({'success': False, 'error': 'VM 생성 후 Proxmox 정보 조회 실패'}), 500
    db.add_server(
        name=server_name,
        vmid=vm_info['vmid'],
        status=vm_info.get('status', 'pending'),
        ip_address=vm_info.get('ip_address'),
        role=data['role'],
        os_type=data.get('os_type'),
        cpu=data.get('cpu'),
        memory=data.get('memory')
    )
    logger.info(f"[add_server] DB에 VM 정보 저장 완료: {server_name}, vmid={vm_info['vmid']}")
    return jsonify({'success': True, 'message': f'{server_name} 서버가 추가 및 적용되었습니다.'})

@app.route('/delete_server/<server_name>', methods=['POST'])
@permission_required('delete_server')
def delete_server(server_name):
    logger.info(f"[delete_server] 요청: {server_name}")
    try:
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
    except Exception as e:
        logger.exception("[delete_server] 서버 삭제 중 예외 발생")
        return jsonify({'success': False, 'error': str(e)}), 500

def proxmox_api_auth():
    proxmox_url = app.config['PROXMOX_ENDPOINT']
    username = app.config['PROXMOX_USERNAME']
    password = app.config['PROXMOX_PASSWORD']
    auth_url = f"{proxmox_url}/api2/json/access/ticket"
    auth_data = {'username': username, 'password': password}
    resp = requests.post(auth_url, data=auth_data, verify=False)
    if resp.status_code != 200:
        return None
    data = resp.json()['data']
    return {
        'ticket': data['ticket'],
        'csrf': data['CSRFPreventionToken']
    }

def proxmox_vm_action(vmid, action):
    proxmox_url = app.config['PROXMOX_ENDPOINT']
    node = app.config['PROXMOX_NODE']
    auth = proxmox_api_auth()
    if not auth:
        return False, 'Proxmox 인증 실패'
    url = f"{proxmox_url}/api2/json/nodes/{node}/qemu/{vmid}/status/{action}"
    headers = {
        'Cookie': f'PVEAuthCookie={auth["ticket"]}',
        'CSRFPreventionToken': auth['csrf']
    }
    resp = requests.post(url, headers=headers, verify=False)
    if resp.status_code == 200:
        return True, None
    else:
        return False, resp.text

@app.route('/stop_server/<server_name>', methods=['POST'])
@permission_required('delete_server')
def stop_server(server_name):
    logger.info(f"[stop_server] 요청: {server_name}")
    try:
        server = db.get_server_by_name(server_name)
        if not server or not server['vmid']:
            return jsonify({'success': False, 'error': 'DB에서 VMID 정보를 찾을 수 없습니다.'}), 400
        vmid = server['vmid']
        ok, err = proxmox_vm_action(vmid, 'stop')
        if ok:
            logger.info(f"[stop_server] VM 중지 요청: vmid={vmid}")
            return jsonify({'success': True, 'message': f'{server_name} 서버가 중지되었습니다.'})
        else:
            logger.error(f"[stop_server] 중지 실패: {err}")
            return jsonify({'success': False, 'error': err}), 500
    except Exception as e:
        logger.exception(f"[stop_server] 예외 발생: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/reboot_server/<server_name>', methods=['POST'])
@permission_required('delete_server')
def reboot_server(server_name):
    logger.info(f"[reboot_server] 요청: {server_name}")
    try:
        server = db.get_server_by_name(server_name)
        if not server or not server['vmid']:
            return jsonify({'success': False, 'error': 'DB에서 VMID 정보를 찾을 수 없습니다.'}), 400
        vmid = server['vmid']
        ok, err = proxmox_vm_action(vmid, 'reset')
        if ok:
            logger.info(f"[reboot_server] VM 리부팅 요청: vmid={vmid}")
            return jsonify({'success': True, 'message': f'{server_name} 서버가 리부팅되었습니다.'})
        else:
            logger.error(f"[reboot_server] 리부팅 실패: {err}")
            return jsonify({'success': False, 'error': err}), 500
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

# 기타 projects 디렉토리, 동적 파일 생성, ansible/terraform 파일 생성 관련 코드 모두 삭제
# app.py는 변수 전달 및 결과 처리만 담당

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

def get_vm_info_from_proxmox(server_name):
    """Proxmox API에서 VM 이름으로 vmid, ip 등 정보 조회"""
    proxmox_url = app.config['PROXMOX_ENDPOINT']
    username = app.config['PROXMOX_USERNAME']
    password = app.config['PROXMOX_PASSWORD']
    node = app.config['PROXMOX_NODE']
    # 인증
    auth_url = f"{proxmox_url}/api2/json/access/ticket"
    auth_data = {'username': username, 'password': password}
    auth_response = requests.post(auth_url, data=auth_data, verify=False)
    if auth_response.status_code != 200:
        return None
    ticket = auth_response.json()['data']['ticket']
    csrf_token = auth_response.json()['data']['CSRFPreventionToken']
    headers = {
        'Cookie': f'PVEAuthCookie={ticket}',
        'CSRFPreventionToken': csrf_token
    }
    # VM 목록 조회
    vms_url = f"{proxmox_url}/api2/json/nodes/{node}/qemu"
    vms_response = requests.get(vms_url, headers=headers, verify=False)
    if vms_response.status_code != 200:
        return None
    vms = vms_response.json().get('data', [])
    for vm in vms:
        if vm['name'] == server_name:
            # IP 정보는 별도 API 필요할 수 있음
            return {
                'vmid': vm['vmid'],
                'status': vm.get('status', ''),
                'ip_address': None  # 필요시 별도 조회
            }
    return None

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
    logger.info(f"[assign_role] 서버: {server_name}, 요청 데이터: {request.form.to_dict() if request.form else request.json}")
    try:
        role = request.form.get('role') if request.form else request.json.get('role')
        if not role:
            return jsonify({'success': False, 'error': '역할(role)을 지정해야 합니다.'}), 400
        servers = read_servers_from_tfvars()
        if server_name not in servers:
            return jsonify({'success': False, 'error': '서버를 찾을 수 없습니다.'}), 404
        server = servers[server_name]
        ip = None
        if 'network_devices' in server and server['network_devices']:
            ip = server['network_devices'][0].get('ip_address')
        if not ip:
            return jsonify({'success': False, 'error': '서버의 IP 정보를 찾을 수 없습니다.'}), 400
        username = server.get('vm_username', get_default_username(server.get('os_type', 'rocky')))
        # 임시 인벤토리 파일 생성
        import datetime, tempfile, os
        now_str = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        log_dir = os.path.join('logs')
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, f'assign_role_{server_name}_{now_str}.log')
        with tempfile.NamedTemporaryFile('w', delete=False, dir='/tmp', prefix=f'inventory_{server_name}_', suffix='.ini') as f:
            f.write(f'{server_name} ansible_host={ip} ansible_user={username} ansible_ssh_common_args="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"\n')
            inventory_path = f.name
        # ansible-playbook 실행
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

@app.route('/admin/iam', methods=['GET'])
@admin_required
def admin_iam_page():
    return render_template('admin_iam.html')

@app.route('/admin/iam/<username>/permissions', methods=['POST'])
@admin_required
def admin_iam_set_permissions(username):
    data = request.json
    permissions = data.get('permissions', [])
    users = load_users()
    if username not in users:
        return jsonify({'error': '사용자를 찾을 수 없습니다.'}), 404
    if users[username].get('role') == 'admin':
        return jsonify({'error': '관리자 권한은 변경할 수 없습니다.'}), 400
    users[username]['permissions'] = permissions
    save_users(users)
    return jsonify({'success': True, 'message': f'{username}의 권한이 변경되었습니다.'})

@app.route('/admin/iam/<username>/role', methods=['POST'])
@admin_required
def admin_iam_set_role(username):
    data = request.json
    new_role = data.get('role')
    users = load_users()
    if username not in users:
        return jsonify({'error': '사용자를 찾을 수 없습니다.'}), 404
    if new_role == 'admin':
        users[username]['role'] = 'admin'
        users[username]['permissions'] = PERMISSION_LIST.copy()
    else:
        users[username]['role'] = new_role
        # 기존 권한 유지
    save_users(users)
    return jsonify({'success': True, 'message': f'{username}의 역할이 {new_role}로 변경되었습니다.'})

if __name__ == '__main__':
    # 필요한 디렉토리 생성
    os.makedirs(PROJECTS_DIR, exist_ok=True)
    os.makedirs('templates', exist_ok=True)
    
    app.run(debug=True, host='0.0.0.0', port=5000)