from flask import Flask, render_template, request, jsonify, redirect, url_for
import subprocess
import os
import json
import yaml
from datetime import datetime
import threading
import time
import hcl

# ssh 추가 해야함. 

app = Flask(__name__)

# 설정
TERRAFORM_DIR = 'terraform'
ANSIBLE_DIR = 'ansible'
PROJECTS_DIR = 'projects'
TFVARS_PATH = os.path.join(TERRAFORM_DIR, 'terraform.tfvars')

# terraform.tfvars의 servers map 읽기
def read_servers_from_tfvars():
    with open(TFVARS_PATH, 'r', encoding='utf-8') as f:
        data = f.read()
        obj = hcl.loads(data)
        return obj.get('servers', {})

# terraform.tfvars의 servers map 저장
def write_servers_to_tfvars(servers, other_vars=None):
    with open(TFVARS_PATH, 'r', encoding='utf-8') as f:
        data = f.read()
        obj = hcl.loads(data)
    obj['servers'] = servers
    # 나머지 변수 보존
    if other_vars:
        obj.update(other_vars)
    # HCL 포맷으로 저장 (간단히 json.dumps로 예시, 실제로는 hcl 포맷 라이브러리 권장)
    with open(TFVARS_PATH, 'w', encoding='utf-8') as f:
        import json
        f.write('servers = ' + json.dumps(servers, indent=2) + '\n')
        for k, v in obj.items():
            if k != 'servers':
                if isinstance(v, str):
                    f.write(f'{k} = "{v}"\n')
                elif isinstance(v, list):
                    f.write(f'{k} = {json.dumps(v)}\n')
                else:
                    f.write(f'{k} = {v}\n')

# 서버 역할 정의
# 1. 서버 역할 정의에 OS별 패키지 추가
SERVER_ROLES = {
    'web': {
        'name': 'Web Server',
        'packages': {
            'ubuntu': ['nginx', 'certbot'],
            'rocky': ['nginx']
        },
        'services': ['nginx']
    },
    'db': {
        'name': 'Database Server', 
        'packages': {
            'ubuntu': ['mysql-server', 'mysql-client'],
            'rocky': ['mysql-server', 'mysql']
        },
        'services': ['mysqld']  # Rocky에서는 mysqld
    },
    'app': {
        'name': 'Application Server',
        'packages': {
            'ubuntu': ['python3', 'python3-pip', 'nodejs', 'npm'],
            'rocky': ['python3', 'python3-pip', 'nodejs', 'npm']
        },
        'services': []
    },
    'cache': {
        'name': 'Cache Server',
        'packages': {
            'ubuntu': ['redis-server'],
            'rocky': ['redis']
        },
        'services': {
            'ubuntu': ['redis-server'],
            'rocky': ['redis']
        }
    },
    'lb': {
        'name': 'Load Balancer',
        'packages': {
            'ubuntu': ['nginx'],
            'rocky': ['nginx']
        },
        'services': ['nginx']
    }
}

        

@app.route('/')
def index():
    return render_template('index.html', roles=SERVER_ROLES)

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
def create_server():
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
        
        return jsonify({
            'success': True,
            'message': '서버 생성이 시작되었습니다.',
            'project_name': server_config['project_name']
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/servers', methods=['GET'])
def list_servers():
    servers = read_servers_from_tfvars()
    return jsonify({'servers': servers})

def run_terraform_apply():
    import subprocess
    result = subprocess.run(['terraform', 'apply', '-auto-approve'], cwd=TERRAFORM_DIR, capture_output=True, text=True)
    return result.returncode == 0, result.stdout, result.stderr

def run_ansible_playbook():
    # 실제 환경에 맞게 inventory, playbook 경로 조정 필요
    import subprocess
    result = subprocess.run(['ansible-playbook', '-i', 'inventory', 'playbook.yml'], cwd=ANSIBLE_DIR, capture_output=True, text=True)
    return result.returncode == 0, result.stdout, result.stderr

@app.route('/add_server', methods=['POST'])
def add_server():
    data = request.json
    servers = read_servers_from_tfvars()
    server_name = data['name']
    servers[server_name] = data
    write_servers_to_tfvars(servers)
    ok, out, err = run_terraform_apply()
    if not ok:
        return jsonify({'success': False, 'error': 'Terraform apply 실패', 'stdout': out, 'stderr': err}), 500
    # Ansible 실행 (옵션)
    # ans_ok, ans_out, ans_err = run_ansible_playbook()
    # if not ans_ok:
    #     return jsonify({'success': False, 'error': 'Ansible 실패', 'stdout': ans_out, 'stderr': ans_err}), 500
    return jsonify({'success': True, 'message': f'{server_name} 서버가 추가 및 적용되었습니다.'})

@app.route('/delete_server/<server_name>', methods=['POST'])
def delete_server(server_name):
    servers = read_servers_from_tfvars()
    if server_name in servers:
        del servers[server_name]
        write_servers_to_tfvars(servers)
        ok, out, err = run_terraform_apply()
        if not ok:
            return jsonify({'success': False, 'error': 'Terraform apply 실패', 'stdout': out, 'stderr': err}), 500
        # Ansible 실행 (옵션)
        # ans_ok, ans_out, ans_err = run_ansible_playbook()
        # if not ans_ok:
        #     return jsonify({'success': False, 'error': 'Ansible 실패', 'stdout': ans_out, 'stderr': ans_err}), 500
        return jsonify({'success': True, 'message': f'{server_name} 서버가 삭제 및 적용되었습니다.'})
    else:
        return jsonify({'success': False, 'error': '서버를 찾을 수 없습니다.'}), 404

@app.route('/stop_server/<server_name>', methods=['POST'])
def stop_server(server_name):
    # Proxmox CLI 또는 ansible-playbook 등으로 중지 구현 (예시)
    # 여기서는 ansible-playbook 예시
    try:
        # ansible-playbook -i inventory playbook.yml --extra-vars "target=<server_name> action=stop"
        result = subprocess.run([
            'ansible-playbook', '-i', 'inventory', 'playbook.yml',
            '--extra-vars', f"target={server_name} action=stop"
        ], cwd=ANSIBLE_DIR, capture_output=True, text=True)
        if result.returncode == 0:
            return jsonify({'success': True, 'message': f'{server_name} 서버가 중지되었습니다.'})
        else:
            return jsonify({'success': False, 'error': result.stderr}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/reboot_server/<server_name>', methods=['POST'])
def reboot_server(server_name):
    # Proxmox CLI 또는 ansible-playbook 등으로 리부팅 구현 (예시)
    try:
        # ansible-playbook -i inventory playbook.yml --extra-vars "target=<server_name> action=reboot"
        result = subprocess.run([
            'ansible-playbook', '-i', 'inventory', 'playbook.yml',
            '--extra-vars', f"target={server_name} action=reboot"
        ], cwd=ANSIBLE_DIR, capture_output=True, text=True)
        if result.returncode == 0:
            return jsonify({'success': True, 'message': f'{server_name} 서버가 리부팅되었습니다.'})
        else:
            return jsonify({'success': False, 'error': result.stderr}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

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
  
  disk {{
    interface = "scsi0"
    size      = {config['disks'][0] if config['disks'] else '20'}
    file_format = "qcow2"
    datastore_id = var.proxmox_datastore
  }}
  
  {generate_additional_disks(config['disks'][1:] if len(config['disks']) > 1 else [])}
  
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
        'ubuntu': 'ubuntu',
        'rocky': 'rocky'
    }
    return defaults.get(os_type, 'rocky')

def get_default_password(os_type):
    """OS별 기본 비밀번호 반환"""
    defaults = {
        'ubuntu': 'ubuntu123',
        'rocky': 'rocky123'
    }
    return defaults.get(os_type, 'rocky123') 

def generate_additional_disks(disks):
    """추가 디스크 생성"""
    disk_configs = []
    for i, disk_size in enumerate(disks):
        disk_config = f"""
  disk {{
    interface = "scsi{i+1}"
    size      = {disk_size}
    file_format = "qcow2"
    datastore_id = var.proxmox_datastore
  }}"""
        disk_configs.append(disk_config)
    return ''.join(disk_configs)

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
    for i, ip in enumerate(config['ip_addresses']):
        inventory += f"{config['project_name']}-{config['role']}-{i+1} ansible_host={ip} ansible_user={config['os_type']} ansible_ssh_common_args='-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null'\n"
    
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

if __name__ == '__main__':
    # 필요한 디렉토리 생성
    os.makedirs(PROJECTS_DIR, exist_ok=True)
    os.makedirs('templates', exist_ok=True)
    
    app.run(debug=True, host='0.0.0.0', port=5000)