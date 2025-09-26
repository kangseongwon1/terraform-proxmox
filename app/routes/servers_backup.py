"""
?œë²„ ê´€ë¦?ê´€???¼ìš°??"""
from flask import Blueprint, request, jsonify, render_template, current_app
from flask_login import login_required, current_user
from functools import wraps
from app.models import Server, User, UserPermission
from app.services import ProxmoxService, TerraformService, AnsibleService, NotificationService
from app.utils.os_classifier import classify_os_type, get_default_username, get_default_password
from app.utils.redis_utils import redis_utils
from app import db
import json
import os
import subprocess
import threading
import time
import uuid
import logging
from datetime import datetime
from app.routes.auth import permission_required

# ë¡œê±° ?¤ì •
logger = logging.getLogger(__name__)

bp = Blueprint('servers', __name__)


# ?„ì—­ ?‘ì—… ?íƒœ dict
tasks = {}

def _remove_from_known_hosts(ip_address: str) -> bool:
    """SSH known_hosts ?Œì¼?ì„œ ?¹ì • IP ?œê±°"""
    try:
        # ?¬ìš©?????”ë ‰? ë¦¬??.ssh/known_hosts ?Œì¼ ê²½ë¡œ
        home_dir = os.path.expanduser('~')
        known_hosts_path = os.path.join(home_dir, '.ssh', 'known_hosts')
        
        if not os.path.exists(known_hosts_path):
            logger.info(f"known_hosts ?Œì¼??ì¡´ì¬?˜ì? ?ŠìŒ: {known_hosts_path}")
            return True
        
        # ssh-keygen ëª…ë ¹?´ë¡œ ?´ë‹¹ IP?????œê±°
        try:
            result = subprocess.run([
                'ssh-keygen', '-R', ip_address
            ], capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                logger.info(f"ssh-keygen?¼ë¡œ {ip_address} ?œê±° ?±ê³µ")
                return True
            else:
                logger.warning(f"ssh-keygen ?¤í–‰ ê²°ê³¼: {result.stderr}")
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            logger.warning(f"ssh-keygen ?¤í–‰ ?¤íŒ¨: {e}")
        
        # ssh-keygen???¤íŒ¨?˜ë©´ ?˜ë™?¼ë¡œ ?Œì¼ ?¸ì§‘
        try:
            logger.info(f"?”§ ?˜ë™?¼ë¡œ known_hosts?ì„œ {ip_address} ?œê±° ?œë„...")
            
            # ë°±ì—… ?Œì¼ ?ì„±
            backup_path = f"{known_hosts_path}.backup.{int(time.time())}"
            subprocess.run(['cp', known_hosts_path, backup_path], check=True)
            
            # ?´ë‹¹ IPê°€ ?¬í•¨???¼ì¸ ?œê±°
            with open(known_hosts_path, 'r') as f:
                lines = f.readlines()
            
            # IPê°€ ?¬í•¨?˜ì? ?Šì? ?¼ì¸?¤ë§Œ ? ì?
            filtered_lines = []
            removed_count = 0
            
            for line in lines:
                if ip_address not in line:
                    filtered_lines.append(line)
                else:
                    removed_count += 1
                    logger.info(f"?—‘ï¸??œê±°???¼ì¸: {line.strip()}")
            
            # ?˜ì •???´ìš©???Œì¼???°ê¸°
            with open(known_hosts_path, 'w') as f:
                f.writelines(filtered_lines)
            
            logger.info(f"known_hosts ?˜ë™ ?¸ì§‘ ?„ë£Œ: {removed_count}ê°??¼ì¸ ?œê±°")
            return True
            
        except Exception as manual_error:
            logger.error(f"known_hosts ?˜ë™ ?¸ì§‘ ?¤íŒ¨: {manual_error}")
            return False
            
    except Exception as e:
        logger.error(f"known_hosts ?œê±° ì¤??¤ë¥˜: {e}")
        return False

def create_task(status, type, message):
    task_id = str(uuid.uuid4())
    tasks[task_id] = {
        'status': status, 
        'type': type, 
        'message': message,
        'created_at': time.time(),
        'timeout': 18000  # 5?œê°„ ?€?„ì•„??    }
    logger.info(f"?”§ Task ?ì„±: {task_id} - {status} - {message}")
    return task_id

def update_task(task_id, status, message=None):
    if task_id in tasks:
        tasks[task_id]['status'] = status
        if message:
            tasks[task_id]['message'] = message
        logger.info(f"?”§ Task ?…ë°?´íŠ¸: {task_id} - {status} - {message}")
    else:
        logger.error(f"Taskë¥?ì°¾ì„ ???†ìŒ: {task_id}")

def check_task_timeout():
    """Task ?€?„ì•„??ì²´í¬"""
    current_time = time.time()
    for task_id, task_info in list(tasks.items()):
        if task_info['status'] == 'running':
            elapsed_time = current_time - task_info['created_at']
            if elapsed_time > task_info['timeout']:
                timeout_hours = task_info['timeout'] / 3600
                logger.info(f"??Task ?€?„ì•„?? {task_id} (ê²½ê³¼?œê°„: {elapsed_time:.1f}ì´? ?¤ì •???€?„ì•„?? {timeout_hours:.1f}?œê°„)")
                update_task(task_id, 'failed', f'?‘ì—… ?€?„ì•„??({timeout_hours:.1f}?œê°„ ì´ˆê³¼)')

@bp.route('/api/tasks/status')
def get_task_status():
    task_id = request.args.get('task_id')
    logger.info(f"?” Task ?íƒœ ì¡°íšŒ: {task_id}")
    logger.info(f"?“‹ ?„ì¬ Tasks: {list(tasks.keys())}")
    
    # ?€?„ì•„??ì²´í¬
    check_task_timeout()
    
    if not task_id:
        return jsonify({'error': 'task_idê°€ ?„ìš”?©ë‹ˆ??'}), 400
    
    if task_id not in tasks:
        logger.error(f"Taskë¥?ì°¾ì„ ???†ìŒ (404): {task_id}")
        # 404 ?ëŸ¬ ??taskë¥??ë™?¼ë¡œ ì¢…ë£Œ ?íƒœë¡?ë³€ê²?        tasks[task_id] = {
            'status': 'failed', 
            'type': 'unknown', 
            'message': 'Taskë¥?ì°¾ì„ ???†ì–´ ?ë™ ì¢…ë£Œ??,
            'created_at': time.time(),
            'timeout': 18000
        }
        logger.info(f"?”§ Task ?ë™ ì¢…ë£Œ ì²˜ë¦¬: {task_id}")
        return jsonify(tasks[task_id])
    
    return jsonify(tasks[task_id])

@bp.route('/api/tasks/config')
def get_task_config():
    """Task ?¤ì • ?•ë³´ ?œê³µ (?€?„ì•„????"""
    return jsonify({
        'timeout': 18000,  # 5?œê°„ (ì´??¨ìœ„)
        'timeout_hours': 5,  # 5?œê°„ (?œê°„ ?¨ìœ„)
        'polling_interval': 5000  # ?´ë§ ê°„ê²© (ë°€ë¦¬ì´ˆ ?¨ìœ„)
    })

@bp.route('/api/servers', methods=['GET'])
@permission_required('view_all')
def list_servers():
    """?œë²„ ëª©ë¡ ì¡°íšŒ"""
    try:
        servers = Server.query.all()
        return jsonify({
            'success': True,
            'servers': [server.to_dict() for server in servers]
        })
    except Exception as e:
        logger.error(f"?œë²„ ëª©ë¡ ì¡°íšŒ ?¤íŒ¨: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/servers/brief', methods=['GET'])
@permission_required('view_all')
def get_servers_brief():
    """ì§€?•í•œ ?œë²„?¤ì˜ ê²½ëŸ‰ ?•ë³´(??• /ë³´ì•ˆê·¸ë£¹/OS/IP)ë§?ë°˜í™˜"""
    try:
        names_param = request.args.get('names', '')
        if not names_param:
            return jsonify({'success': True, 'servers': {}})
        names = [n.strip() for n in names_param.split(',') if n.strip()]
        if not names:
            return jsonify({'success': True, 'servers': {}})

        servers = Server.query.filter(Server.name.in_(names)).all()
        result = {}
        for s in servers:
            result[s.name] = {
                'name': s.name,
                'role': s.role or '',
                'firewall_group': s.firewall_group,
                'os_type': s.os_type,
                'ip_addresses': [s.ip_address] if s.ip_address else []
            }
        return jsonify({'success': True, 'servers': result})
    except Exception as e:
        logger.error(f"ê²½ëŸ‰ ?œë²„ ?•ë³´ ì¡°íšŒ ?¤íŒ¨: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/debug/servers', methods=['GET'])
@login_required
def debug_servers():
    """?œë²„ ?”ë²„ê¹??•ë³´"""
    try:
        servers = Server.query.all()
        debug_info = []
        for server in servers:
            debug_info.append({
                'id': server.id,
                'name': server.name,
                'vmid': server.vmid,
                'status': server.status,
                'role': server.role,
                'firewall_group': server.firewall_group,
                'created_at': str(server.created_at) if server.created_at else None,
                'updated_at': str(server.updated_at) if server.updated_at else None
            })
        return jsonify({
            'success': True,
            'servers': debug_info
        })
    except Exception as e:
        logger.error(f"?œë²„ ?”ë²„ê¹??•ë³´ ì¡°íšŒ ?¤íŒ¨: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/servers', methods=['POST'])
@permission_required('create_server')
def create_server():
    """?œë²„ ?ì„±"""
    try:
        data = request.get_json()
        server_name = data.get('name')
        cpu = data.get('cpu', 2)
        memory = data.get('memory', 2048)
        role = data.get('role', '')
        disks = data.get('disks', [])
        network_devices = data.get('network_devices', [])
        template_vm_id = data.get('template_vm_id', 8000)
        vm_username = data.get('vm_username', 'rocky')
        vm_password = data.get('vm_password', 'rocky123')
        
        # IP ì£¼ì†Œë¥?network_devices?ì„œ ì¶”ì¶œ
        ip_address = ''
        if network_devices:
            ip_addresses = [device.get('ip_address', '') for device in network_devices if device.get('ip_address')]
            ip_address = ', '.join(ip_addresses) if ip_addresses else ''
        
        if not server_name:
            return jsonify({'error': '?œë²„ ?´ë¦„???„ìš”?©ë‹ˆ??'}), 400
        
        # ?œë²„ ?´ë¦„ ì¤‘ë³µ ?•ì¸
        existing_server = Server.query.filter_by(name=server_name).first()
        if existing_server:
            return jsonify({'error': '?´ë? ì¡´ì¬?˜ëŠ” ?œë²„ ?´ë¦„?…ë‹ˆ??'}), 400
        
        # Task ?ì„±
        task_id = create_task('running', 'create_server', f'?œë²„ {server_name} ?ì„± ì¤?..')
        
        def create_server_task():
            try:
                from app import create_app
                app = create_app()
                with app.app_context():
                    logger.info(f"?”§ ?œë²„ ?ì„± ?‘ì—… ?œì‘: {server_name}")
                    
                    # Terraform ?œë¹„??ì´ˆê¸°??                    terraform_service = TerraformService()
                    
                    # Proxmox ?œë¹„??ì´ˆê¸°??                    proxmox_service = ProxmoxService()
                    
                    # ?œí”Œë¦??´ë¦„ ê°€?¸ì˜¤ê¸?(template_vm_idê°€ ?ˆëŠ” ê²½ìš°)
                    template_name = 'rocky-9-template'  # ê¸°ë³¸ê°?                    if template_vm_id:
                        try:
                            # Proxmox?ì„œ ?œí”Œë¦??•ë³´ ì¡°íšŒ
                            headers, error = proxmox_service.get_proxmox_auth()
                            if not error:
                                vms, vm_error = proxmox_service.get_proxmox_vms(headers)
                                if not vm_error:
                                    for vm in vms:
                                        if vm.get('vmid') == template_vm_id:
                                            template_name = vm.get('name', 'rocky-9-template')
                                            break
                        except Exception as e:
                            logger.warning(f"?œí”Œë¦??•ë³´ ì¡°íšŒ ?¤íŒ¨: {e}")
                            template_name = 'rocky-9-template'
                    
                    # OS ?€???™ì  ë¶„ë¥˜
                    os_type = classify_os_type(template_name)
                    
                    # ê¸°ë³¸ ?¬ìš©?ëª…/ë¹„ë?ë²ˆí˜¸ ?¤ì • (?¬ìš©?ê? ?…ë ¥?˜ì? ?Šì? ê²½ìš°)
                    current_vm_username = vm_username if vm_username else get_default_username(os_type)
                    current_vm_password = vm_password if vm_password else get_default_password(os_type)
                    
                    # ?œë²„ ?¤ì • ?ì„±
                    # .env ?Œì¼??ì§ì ‘ ?½ì–´?¤ëŠ” ?¨ìˆ˜
                    def load_env_file():
                        """?„ë¡œ?íŠ¸ ë£¨íŠ¸??.env ?Œì¼??ì§ì ‘ ?½ì–´???•ì…”?ˆë¦¬ë¡?ë°˜í™˜"""
                        env_vars = {}
                        try:
                            # ?„ë¡œ?íŠ¸ ë£¨íŠ¸ ê²½ë¡œ ì°¾ê¸° (app/routes/servers.py -> app -> project_root)
                            current_dir = os.path.dirname(os.path.abspath(__file__))
                            project_root = os.path.dirname(os.path.dirname(current_dir))
                            env_file = os.path.join(project_root, '.env')
                            
                            if os.path.exists(env_file):
                                with open(env_file, 'r', encoding='utf-8') as f:
                                    for line in f:
                                        line = line.strip()
                                        if line and not line.startswith('#') and '=' in line:
                                            key, value = line.split('=', 1)
                                            env_vars[key.strip()] = value.strip()
                                print(f"?”§ .env ?Œì¼ ë¡œë“œ ?±ê³µ: {env_file}")
                            else:
                                print(f"? ï¸ .env ?Œì¼??ì°¾ì„ ???†ìŠµ?ˆë‹¤: {env_file}")
                            
                            return env_vars
                        except Exception as e:
                            print(f"? ï¸ .env ?Œì¼ ?½ê¸° ?¤íŒ¨: {e}")
                            return {}

                    # ?¬ìš©ë²?                    env_vars = load_env_file()
                    hdd_datastore = env_vars.get('PROXMOX_HDD_DATASTORE')
                    ssd_datastore = env_vars.get('PROXMOX_SSD_DATASTORE')

                    logger.info(f"?”§ .env?ì„œ ?½ì? datastore ?¤ì •:")
                    logger.info(f"   PROXMOX_HDD_DATASTORE: {hdd_datastore}")
                    logger.info(f"   PROXMOX_SSD_DATASTORE: {ssd_datastore}")

                    # ?”ìŠ¤???¤ì • ???íƒœ ë¡œê·¸
                    logger.info(f"?”§ ?”ìŠ¤???¤ì • ???íƒœ:")
                    for i, disk in enumerate(disks):
                        logger.info(f"   ?”ìŠ¤??{i}: {disk}")

                    # ?”ìŠ¤???¤ì •??datastore ?ë™ ?¤ì •
                    for i, disk in enumerate(disks):
                        logger.info(f"?”§ ?”ìŠ¤??{i} ì²˜ë¦¬ ?œì‘: {disk}")
                        
                        if 'disk_type' not in disk:
                            disk['disk_type'] = 'hdd'
                            logger.info(f"?”§ ?”ìŠ¤??{i}: disk_type??'hdd'ë¡??¤ì •")
                        if 'file_format' not in disk:
                            disk['file_format'] = 'auto'
                            logger.info(f"?”§ ?”ìŠ¤??{i}: file_format??'auto'ë¡??¤ì •")
                        
                        # datastore_idê°€ ?†ìœ¼ë©?"auto"ë¡??¤ì • (Terraform?ì„œ ?˜ê²½ë³€???¬ìš©)
                        if 'datastore_id' not in disk:
                            disk['datastore_id'] = 'auto'
                            logger.info(f"?”§ ?”ìŠ¤??{i}: datastore_idë¥?'auto'ë¡??¤ì • (Terraform?ì„œ ?˜ê²½ë³€???¬ìš©)")
                        elif disk['datastore_id'] == 'local-lvm':
                            # local-lvm?€ ê¸°ë³¸ê°’ì´ë¯€ë¡?autoë¡?ë³€ê²½í•˜???˜ê²½ë³€???¬ìš©
                            disk['datastore_id'] = 'auto'
                            logger.info(f"?”§ ?”ìŠ¤??{i}: local-lvm??autoë¡?ë³€ê²?(?˜ê²½ë³€???¬ìš©)")
                        else:
                            logger.info(f"?”§ ?”ìŠ¤??{i}: datastore_idê°€ ?´ë? ?¤ì •?? {disk['datastore_id']}")

                    # ?”ìŠ¤???¤ì • ???íƒœ ë¡œê·¸
                    logger.info(f"?”§ ?”ìŠ¤???¤ì • ???íƒœ:")
                    for i, disk in enumerate(disks):
                        logger.info(f"   ?”ìŠ¤??{i}: {disk}")
                    
                    server_data = {
                        'name': server_name,
                        'cpu': cpu,
                        'memory': memory,
                        'role': role,
                        'os_type': os_type,  # ?™ì ?¼ë¡œ ë¶„ë¥˜??OS ?€??                        'disks': disks,
                        'network_devices': network_devices,
                        'template_vm_id': template_vm_id,
                        'vm_username': current_vm_username,
                        'vm_password': current_vm_password
                    }
                    logger.info(f"?”§ ?œë²„ ?¤ì • ?ì„± ?œì‘: {json.dumps(server_data, indent=2)}")
                    
                    try:
                        config_success = terraform_service.create_server_config(server_data)
                        logger.info(f"?”§ ?œë²„ ?¤ì • ?ì„± ê²°ê³¼: {config_success}")
                        
                        if not config_success:
                            error_msg = '?œë²„ ?¤ì • ?ì„± ?¤íŒ¨'
                            logger.error(f"{error_msg}")
                            update_task(task_id, 'failed', error_msg)
                            return
                    except Exception as config_error:
                        error_msg = f'?œë²„ ?¤ì • ?ì„± ì¤??ˆì™¸ ë°œìƒ: {str(config_error)}'
                        logger.error(f"{error_msg}")
                        import traceback
                        traceback.print_exc()
                        update_task(task_id, 'failed', error_msg)
                        return
                    
                    # ?¸í”„??ë°°í¬
                    logger.info(f"?”§ ?¸í”„??ë°°í¬ ?œì‘: {server_name}")
                    try:
                        deploy_success, deploy_message = terraform_service.deploy_infrastructure()
                        logger.info(f"?”§ ?¸í”„??ë°°í¬ ê²°ê³¼: success={deploy_success}, message={deploy_message}")
                        
                        if not deploy_success:
                            logger.error(f"?¸í”„??ë°°í¬ ?¤íŒ¨: {deploy_message}")
                            update_task(task_id, 'failed', f'?¸í”„??ë°°í¬ ?¤íŒ¨: {deploy_message}')
                            return
                    except Exception as deploy_error:
                        error_msg = f"?¸í”„??ë°°í¬ ì¤??ˆì™¸ ë°œìƒ: {str(deploy_error)}"
                        logger.error(f"{error_msg}")
                        import traceback
                        traceback.print_exc()
                        update_task(task_id, 'failed', error_msg)
                        return
                    
                    # Proxmox?ì„œ ?¤ì œ VM ?ì„± ?•ì¸
                    proxmox_service = ProxmoxService()
                    vm_exists = proxmox_service.check_vm_exists(server_name)
                    
                    if not vm_exists:
                        update_task(task_id, 'failed', 'Proxmox?ì„œ VM??ì°¾ì„ ???†ìŠµ?ˆë‹¤.')
                        return
                    
                    # VM ID ê°€?¸ì˜¤ê¸?                    vm_id = None
                    try:
                        # Terraform output?ì„œ VM ID ê°€?¸ì˜¤ê¸?                        terraform_output = terraform_service.output()
                        logger.info(f"?” Terraform output ?„ì²´: {terraform_output}")
                        
                        if 'vm_ids' in terraform_output:
                            vm_ids_data = terraform_output['vm_ids']
                            logger.info(f"?” vm_ids ?°ì´?? {vm_ids_data}")
                            
                            # Terraform output êµ¬ì¡°: {"vm_ids": {"value": {"test1": 110}}}
                            if 'value' in vm_ids_data and server_name in vm_ids_data['value']:
                                vm_id = vm_ids_data['value'][server_name]
                                logger.info(f"?” Terraform output?ì„œ VM ID ì¡°íšŒ: {server_name} = {vm_id}")
                        
                        # VM IDê°€ ?†ìœ¼ë©?Proxmox API?ì„œ ì¡°íšŒ
                        if not vm_id:
                            vm_exists, vm_info = proxmox_service.check_vm_exists(server_name)
                            if vm_exists and vm_info:
                                vm_id = vm_info.get('vmid')
                                logger.info(f"?” Proxmox API?ì„œ VM ID ì¡°íšŒ: {server_name} = {vm_id}")
                    except Exception as e:
                        logger.warning(f"VM ID ì¡°íšŒ ?¤íŒ¨: {e}")
                        import traceback
                        traceback.print_exc()
                    
                    # IP ì£¼ì†Œ ì²˜ë¦¬ (ë¦¬ìŠ¤?¸ì¸ ê²½ìš° ë¬¸ì?´ë¡œ ë³€??
                    ip_address_str = ip_address
                    if isinstance(ip_address, list):
                        ip_address_str = ', '.join(ip_address) if ip_address else ''
                    
                    # DB???œë²„ ?•ë³´ ?€??(VM ID ?¬í•¨)
                    new_server = Server(
                        name=server_name,
                        vmid=vm_id,  # VM ID ì¶”ê?
                        ip_address=ip_address_str,  # IP ì£¼ì†Œ ì¶”ê? (ë¬¸ì?´ë¡œ ë³€??
                        role=role,  # ??•  ?•ë³´ ì¶”ê?
                        status='stopped',  # ì´ˆê¸° ?íƒœ??ì¤‘ì???                        cpu=cpu,
                        memory=memory,
                        os_type=os_type  # OS ?€??ì¶”ê?
                    )
                    db.session.add(new_server)
                    db.session.commit()
                    logger.info(f"DB???œë²„ ?€???„ë£Œ: {server_name} (ID: {new_server.id}, VM ID: {vm_id})")
                    
                    # Node Exporter ?ë™ ?¤ì¹˜ (ëª¨ë‹ˆ?°ë§??
                    ansible_service = AnsibleService()
                    node_exporter_installed = False
                    try:
                        # IP ì£¼ì†Œ?ì„œ ì²?ë²ˆì§¸ IP ì¶”ì¶œ (Node Exporter ?¤ì¹˜??
                        server_ip = ip_address_str.split(',')[0].strip() if ip_address_str else ''
                        if server_ip:
                            logger.info(f"?”§ Node Exporter ?ë™ ?¤ì¹˜ ?œì‘: {server_name} ({server_ip})")
                            node_exporter_installed = ansible_service._install_node_exporter_if_needed(server_name, server_ip)
                            if node_exporter_installed:
                                logger.info(f"Node Exporter ?¤ì¹˜ ?„ë£Œ: {server_name}")
                            else:
                                logger.warning(f"Node Exporter ?¤ì¹˜ ?¤íŒ¨: {server_name}")
                        else:
                            logger.warning(f"IP ì£¼ì†Œê°€ ?†ì–´ Node Exporter ?¤ì¹˜ ?¤í‚µ: {server_name}")
                    except Exception as e:
                        logger.warning(f"Node Exporter ?¤ì¹˜ ì¤??¤ë¥˜: {e}")
                    
                    # Ansible???µí•œ ??• ë³??Œí”„?¸ì›¨???¤ì¹˜ (Node Exporter??ë³„ë„ ?¤ì¹˜)
                    if role and role != 'none':
                        logger.info(f"?”§ Ansible ??•  ? ë‹¹ ?œì‘: {server_name} - {role}")
                        try:
                            # ?œë²„ ?ì„± ?œì—????• ë§??¤ì¹˜ (Node Exporter???„ì—??ë³„ë„ ?¤ì¹˜)
                            ansible_success, ansible_message = ansible_service.run_playbook(
                                role=role,
                                extra_vars={},  # Node Exporter ?¤ì¹˜ ë³€???œê±°
                                target_server=server_ip
                            )
                            
                            if ansible_success:
                                logger.info(f"Ansible ??•  ? ë‹¹ ?±ê³µ: {server_name} - {role}")
                                update_task(task_id, 'completed', f'?œë²„ {server_name} ?ì„± ë°?{role} ??•  ? ë‹¹ ?„ë£Œ')
                                # ?±ê³µ ?Œë¦¼ ?ì„±
                                NotificationService.create_server_notification(
                                    server_name, 'create', 'success', 
                                    f'?œë²„ {server_name} ?ì„± ë°?{role} ??•  ? ë‹¹???„ë£Œ?˜ì—ˆ?µë‹ˆ?? Node Exporter: {"?¤ì¹˜?? if node_exporter_installed else "?¤ì¹˜ ?ˆë¨"}'
                                )
                            else:
                                logger.warning(f"Ansible ??•  ? ë‹¹ ?¤íŒ¨: {server_name} - {role}, ë©”ì‹œì§€: {ansible_message}")
                                update_task(task_id, 'completed', f'?œë²„ {server_name} ?ì„± ?„ë£Œ (Ansible ?¤íŒ¨: {ansible_message})')
                                # ë¶€ë¶??±ê³µ ?Œë¦¼ ?ì„±
                                NotificationService.create_server_notification(
                                    server_name, 'create', 'warning', 
                                    f'?œë²„ {server_name} ?ì„± ?„ë£Œ (Ansible ?¤íŒ¨: {ansible_message})'
                                )
                        except Exception as ansible_error:
                            logger.warning(f"Ansible ?¤í–‰ ì¤??¤ë¥˜: {str(ansible_error)}")
                            update_task(task_id, 'completed', f'?œë²„ {server_name} ?ì„± ?„ë£Œ (Ansible ?¤ë¥˜: {str(ansible_error)})')
                            # ë¶€ë¶??±ê³µ ?Œë¦¼ ?ì„±
                            NotificationService.create_server_notification(
                                server_name, 'create', 'warning', 
                                f'?œë²„ {server_name} ?ì„± ?„ë£Œ (Ansible ?¤ë¥˜: {str(ansible_error)})'
                            )
                    else:
                        update_task(task_id, 'completed', f'?œë²„ {server_name} ?ì„± ?„ë£Œ')
                        # ?±ê³µ ?Œë¦¼ ?ì„±
                        NotificationService.create_server_notification(
                            server_name, 'create', 'success', 
                            f'?œë²„ {server_name} ?ì„±???„ë£Œ?˜ì—ˆ?µë‹ˆ??'
                        )
                    
                    # Prometheus ?¤ì • ?…ë°?´íŠ¸ (?œë²„ ?ì„± ?„ë£Œ ??
                    try:
                        from app.services.prometheus_service import PrometheusService
                        prometheus_service = PrometheusService()
                        prometheus_updated = prometheus_service.update_prometheus_config()
                        
                        if prometheus_updated:
                            logger.info(f"Prometheus ?¤ì • ?…ë°?´íŠ¸ ?„ë£Œ: {server_name}")
                        else:
                            logger.warning(f"Prometheus ?¤ì • ?…ë°?´íŠ¸ ?¤íŒ¨: {server_name}")
                            print(prometheus_service.get_manual_setup_instructions())
                    except Exception as e:
                        logger.warning(f"Prometheus ?¤ì • ?…ë°?´íŠ¸ ì¤??¤ë¥˜: {e}")
                        logger.info("?”§ Prometheus ?˜ë™ ?¤ì •???„ìš”?????ˆìŠµ?ˆë‹¤.")
                    
                    # Node Exporter ?¤ì¹˜ ?±ê³µ ?¬ë??€ ê´€ê³„ì—†??Prometheus ?¤ì • ?…ë°?´íŠ¸
                    if not node_exporter_installed and server_ip:
                        logger.info(f"?”§ Node Exporter ?¤ì¹˜ ?¤íŒ¨?ˆì?ë§?Prometheus ?¤ì •?€ ?…ë°?´íŠ¸: {server_ip}")
                        try:
                            from app.services.prometheus_service import PrometheusService
                            prometheus_service = PrometheusService()
                            prometheus_updated = prometheus_service.update_prometheus_config()
                            if prometheus_updated:
                                logger.info(f"Prometheus ?¤ì • ?…ë°?´íŠ¸ ?„ë£Œ (Node Exporter ?¤íŒ¨ ??: {server_ip}")
                        except Exception as e:
                            logger.warning(f"Prometheus ?¤ì • ?…ë°?´íŠ¸ ì¤??¤ë¥˜ (Node Exporter ?¤íŒ¨ ??: {e}")
                    
                    logger.info(f"?œë²„ ?ì„± ?„ë£Œ: {server_name}")
                    
            except Exception as e:
                logger.error(f"?œë²„ ?ì„± ?‘ì—… ?¤íŒ¨: {str(e)}")
                update_task(task_id, 'failed', f'?œë²„ ?ì„± ì¤??¤ë¥˜: {str(e)}')
                
                # ?¤íŒ¨ ?Œë¦¼ ?ì„±
                try:
                    NotificationService.create_server_notification(
                        server_name, 'create', 'error', 
                        f'?œë²„ {server_name} ?ì„± ì¤??¤ë¥˜ê°€ ë°œìƒ?ˆìŠµ?ˆë‹¤: {str(e)}'
                    )
                except Exception as notif_error:
                    logger.warning(f"?¤íŒ¨ ?Œë¦¼ ?ì„± ?¤íŒ¨: {str(notif_error)}")
                
                # ?¤íŒ¨ ???•ë¦¬ ?‘ì—…
                try:
                    # tfvars?ì„œ ?¤ì • ?œê±°
                    terraform_service = TerraformService()
                    terraform_service.remove_server_config(server_name)
                    
                    # DB?ì„œ ?œë²„ ?? œ
                    failed_server = Server.query.filter_by(name=server_name).first()
                    if failed_server:
                        db.session.delete(failed_server)
                        db.session.commit()
                except Exception as cleanup_error:
                    logger.error(f"?•ë¦¬ ?‘ì—… ?¤íŒ¨: {str(cleanup_error)}")
        
        # ë°±ê·¸?¼ìš´?œì—???œë²„ ?ì„± ?‘ì—… ?¤í–‰
        thread = threading.Thread(target=create_server_task)
        thread.start()
        
        return jsonify({
            'success': True,
            'task_id': task_id,
            'message': f'?œë²„ {server_name} ?ì„±???œì‘?˜ì—ˆ?µë‹ˆ??'
        })
        
    except Exception as e:
        logger.error(f"?œë²„ ?ì„± ?¤íŒ¨: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/create_servers_bulk', methods=['POST'])
@permission_required('create_server')
def create_servers_bulk():
    """?¤ì¤‘ ?œë²„ ?ì„±"""
    try:
        data = request.get_json()
        servers_data = data.get('servers', [])
        
        if not servers_data:
            return jsonify({'error': '?œë²„ ?°ì´?°ê? ?„ìš”?©ë‹ˆ??'}), 400
        
        # ?œë²„ ?´ë¦„ ì¤‘ë³µ ?•ì¸
        server_names = [server.get('name') for server in servers_data if server.get('name')]
        for server_name in server_names:
            existing_server = Server.query.filter_by(name=server_name).first()
            if existing_server:
                return jsonify({'error': f'?´ë? ì¡´ì¬?˜ëŠ” ?œë²„ ?´ë¦„?…ë‹ˆ?? {server_name}'}), 400
        
        # Task ?ì„±
        task_id = create_task('running', 'create_servers_bulk', f'{len(servers_data)}ê°??œë²„ ?ì„± ì¤?..')
        
        def create_servers_bulk_task():
            try:
                from app import create_app
                app = create_app()
                with app.app_context():
                    logger.info(f"?”§ ?¤ì¤‘ ?œë²„ ?ì„± ?‘ì—… ?œì‘: {len(servers_data)}ê°??œë²„")
                    
                    # Terraform ?œë¹„??ì´ˆê¸°??                    terraform_service = TerraformService()
                    
                    # ê¸°ì¡´ tfvars ë¡œë“œ
                    try:
                        tfvars = terraform_service.load_tfvars()
                        logger.info(f"?”§ ê¸°ì¡´ tfvars ë¡œë“œ ?„ë£Œ: {len(tfvars.get('servers', {}))}ê°??œë²„")
                    except Exception as e:
                        logger.error(f"ê¸°ì¡´ tfvars ë¡œë“œ ?¤íŒ¨: {e}")
                        # ê¸°ë³¸ êµ¬ì¡° ?ì„±
                        tfvars = {
                            'servers': {},
                            'proxmox_endpoint': current_app.config.get('PROXMOX_ENDPOINT'),
                            'proxmox_username': current_app.config.get('PROXMOX_USERNAME'),
                            'proxmox_password': current_app.config.get('PROXMOX_PASSWORD'),
                            'proxmox_node': current_app.config.get('PROXMOX_NODE'),
                            'vm_username': current_app.config.get('VM_USERNAME', 'rocky'),
                            'vm_password': current_app.config.get('VM_PASSWORD', 'rocky123'),
                            'ssh_keys': current_app.config.get('SSH_KEYS', '')
                        }
                    
                    # ?œë²„ ?¤ì • ì¶”ê?
                    for server_data in servers_data:
                        server_name = server_data.get('name')
                        if not server_name:
                            continue
                        
                        # ?œë²„ë³?ê¸°ë³¸ê°??¤ì •
                        server_config = {
                            'name': server_name,
                            'cpu': server_data.get('cpu', 2),
                            'memory': server_data.get('memory', 2048),
                            'role': server_data.get('role', ''),
                            'os_type': server_data.get('os_type', ''), 
                            'disks': server_data.get('disks', []),
                            'network_devices': server_data.get('network_devices', []),
                            'template_vm_id': server_data.get('template_vm_id', 8000),
                            'vm_username': server_data.get('vm_username', tfvars.get('vm_username', 'rocky')),
                            'vm_password': server_data.get('vm_password', tfvars.get('vm_password', 'rocky123'))
                        }
                        
                        # ?”ìŠ¤???¤ì •??ê¸°ë³¸ê°?ì¶”ê? ë°?datastore ?ë™ ?¤ì •
                        import os
                        # ?˜ê²½ë³€?˜ì—??ì§ì ‘ datastore ?¤ì • ê°€?¸ì˜¤ê¸?                        hdd_datastore = os.environ.get('PROXMOX_HDD_DATASTORE')
                        ssd_datastore = os.environ.get('PROXMOX_SSD_DATASTORE')
                        
                        for disk in server_config['disks']:
                            if 'disk_type' not in disk:
                                disk['disk_type'] = 'hdd'
                            if 'file_format' not in disk:
                                disk['file_format'] = 'auto'
                            # datastore_idê°€ "auto"?´ê±°???†ìœ¼ë©??˜ê²½ë³€?˜ì—??ê°€?¸ì˜¨ datastore ?¬ìš©
                            if 'datastore_id' not in disk or disk['datastore_id'] == 'auto':
                                if disk['disk_type'] == 'hdd':
                                    disk['datastore_id'] = hdd_datastore if hdd_datastore else 'local-lvm'
                                elif disk['disk_type'] == 'ssd':
                                    disk['datastore_id'] = ssd_datastore if ssd_datastore else 'local'
                                else:
                                    disk['datastore_id'] = hdd_datastore if hdd_datastore else 'local-lvm'
                                
                                logger.info(f"?”§ {server_name}: {disk['disk_type']} ?”ìŠ¤??datastore ?ë™ ?¤ì •: {disk['datastore_id']}")
                        
                        tfvars['servers'][server_name] = server_config
                        logger.info(f"?”§ ?œë²„ ?¤ì • ì¶”ê?: {server_name}")
                    
                    # tfvars ?Œì¼ ?€??                    try:
                        save_success = terraform_service.save_tfvars(tfvars)
                        if not save_success:
                            error_msg = 'tfvars ?Œì¼ ?€???¤íŒ¨'
                            logger.error(f"{error_msg}")
                            update_task(task_id, 'failed', error_msg)
                            return
                        logger.info(f"tfvars ?Œì¼ ?€???„ë£Œ: {len(tfvars['servers'])}ê°??œë²„")
                    except Exception as save_error:
                        error_msg = f'tfvars ?Œì¼ ?€??ì¤??ˆì™¸ ë°œìƒ: {str(save_error)}'
                        logger.error(f"{error_msg}")
                        import traceback
                        traceback.print_exc()
                        update_task(task_id, 'failed', error_msg)
                        return
                    
                    # ?ˆë¡œ ?ì„±???œë²„?¤ì— ?€??targeted apply ?¤í–‰
                    logger.info(f"?”§ Targeted Terraform apply ?œì‘: {len(servers_data)}ê°??œë²„")
                    try:
                        # ?ˆë¡œ ?ì„±???œë²„?¤ë§Œ ?€?ìœ¼ë¡?targeted apply ?¤í–‰
                        new_server_targets = []
                        for server_data in servers_data:
                            server_name = server_data.get('name')
                            if server_name:
                                # Terraform ëª¨ë“ˆ ë¦¬ì†Œ???€ê²??•ì‹: module.server["?œë²„?´ë¦„"]
                                target = f'module.server["{server_name}"]'
                                new_server_targets.append(target)
                        
                        logger.info(f"?”§ Targeted apply ?€?? {new_server_targets}")
                        apply_success, apply_message = terraform_service.apply(targets=new_server_targets)
                        logger.info(f"?”§ Terraform apply ê²°ê³¼: success={apply_success}, message_length={len(apply_message) if apply_message else 0}")
                        
                        if not apply_success:
                            logger.error(f"Terraform apply ?¤íŒ¨: {apply_message}")
                            update_task(task_id, 'failed', f'Terraform apply ?¤íŒ¨: {apply_message}')
                            return
                    except Exception as apply_error:
                        error_msg = f"Terraform apply ì¤??ˆì™¸ ë°œìƒ: {str(apply_error)}"
                        logger.error(f"{error_msg}")
                        import traceback
                        traceback.print_exc()
                        update_task(task_id, 'failed', error_msg)
                        return
                    
                    # Proxmox?ì„œ ?¤ì œ VM ?ì„± ?•ì¸
                    proxmox_service = ProxmoxService()
                    created_servers = []
                    failed_servers = []
                    
                    # ?œí”Œë¦??•ë³´ë¥???ë²ˆì— ì¡°íšŒ (?¨ìœ¨???¥ìƒ)
                    template_cache = {}
                    try:
                        headers, error = proxmox_service.get_proxmox_auth()
                        if not error:
                            vms, vm_error = proxmox_service.get_proxmox_vms(headers)
                            if not vm_error:
                                for vm in vms:
                                    template_cache[vm.get('vmid')] = vm.get('name', 'rocky-9-template')
                    except Exception as e:
                        logger.warning(f"?œí”Œë¦??•ë³´ ì¡°íšŒ ?¤íŒ¨: {e}")
                    
                    for server_data in servers_data:
                        server_name = server_data.get('name')
                        if not server_name:
                            continue
                        
                        vm_exists = proxmox_service.check_vm_exists(server_name)
                        if vm_exists:
                            created_servers.append(server_name)
                            
                            # IP ì£¼ì†Œë¥?network_devices?ì„œ ì¶”ì¶œ (?´ë? ?„ì—??ì²˜ë¦¬?ˆì?ë§??¤ì‹œ ?•ì¸)
                            ip_address_str = ''
                            network_devices = server_data.get('network_devices', [])
                            if network_devices:
                                ip_addresses = [device.get('ip_address', '') for device in network_devices if device.get('ip_address')]
                                ip_address_str = ', '.join(ip_addresses) if ip_addresses else ''
                            
                            # OS ?€???™ì  ë¶„ë¥˜ (ìºì‹œ???•ë³´ ?¬ìš©)
                            template_vm_id = server_data.get('template_vm_id', 8000)
                            template_name = template_cache.get(template_vm_id, 'rocky-9-template')
                            os_type = classify_os_type(template_name)
                            
                            # VM ID ê°€?¸ì˜¤ê¸?                            vm_id = None
                            try:
                                # Terraform output?ì„œ VM ID ê°€?¸ì˜¤ê¸?                                terraform_output = terraform_service.output()
                                logger.info(f"?” Terraform output ?„ì²´: {terraform_output}")
                                
                                if 'vm_ids' in terraform_output:
                                    vm_ids_data = terraform_output['vm_ids']
                                    logger.info(f"?” vm_ids ?°ì´?? {vm_ids_data}")
                                    
                                    # Terraform output êµ¬ì¡°: {"vm_ids": {"value": {"test1": 110}}}
                                    if 'value' in vm_ids_data and server_name in vm_ids_data['value']:
                                        vm_id = vm_ids_data['value'][server_name]
                                        logger.info(f"?” Terraform output?ì„œ VM ID ì¡°íšŒ: {server_name} = {vm_id}")
                                
                                # VM IDê°€ ?†ìœ¼ë©?Proxmox API?ì„œ ì¡°íšŒ
                                if not vm_id:
                                    vm_exists, vm_info = proxmox_service.check_vm_exists(server_name)
                                    if vm_exists and vm_info:
                                        vm_id = vm_info.get('vmid')
                                        logger.info(f"?” Proxmox API?ì„œ VM ID ì¡°íšŒ: {server_name} = {vm_id}")
                            except Exception as e:
                                logger.warning(f"VM ID ì¡°íšŒ ?¤íŒ¨: {e}")
                                import traceback
                                traceback.print_exc()
                            
                            # DB???œë²„ ?•ë³´ ?€??(VM ID ?¬í•¨)
                            new_server = Server(
                                name=server_name,
                                vmid=vm_id,  # VM ID ì¶”ê?
                                ip_address=ip_address_str,  # IP ì£¼ì†Œ ì¶”ê?
                                cpu=server_data.get('cpu', 2),
                                memory=server_data.get('memory', 2048),
                                role=server_data.get('role', ''),
                                status='running',
                                os_type=os_type,  # OS ?€??ì¶”ê?
                                created_at=datetime.utcnow()
                            )
                            
                            try:
                                db.session.add(new_server)
                                db.session.commit()
                                logger.info(f"?œë²„ DB ?€???„ë£Œ: {server_name}")
                            except Exception as db_error:
                                logger.warning(f"?œë²„ DB ?€???¤íŒ¨: {server_name} - {db_error}")
                                db.session.rollback()
                        else:
                            failed_servers.append(server_name)
                            logger.error(f"VM ?ì„± ?•ì¸ ?¤íŒ¨: {server_name}")
                    
                    # Node Exporter ?ë™ ?¤ì¹˜ (?ì„±???œë²„?¤ì— ?€??
                    if created_servers:
                        logger.info(f"?”§ ?ì„±???œë²„?¤ì— Node Exporter ?ë™ ?¤ì¹˜ ?œì‘: {len(created_servers)}ê°?)
                        ansible_service = AnsibleService()
                        
                        # ?œë²„ IP ?˜ì§‘
                        server_ips = []
                        for server_name in created_servers:
                            try:
                                server = Server.query.filter_by(name=server_name).first()
                                if server and server.ip_address:
                                    server_ip = server.ip_address.split(',')[0].strip()
                                    server_ips.append(server_ip)
                                    logger.info(f"?”§ Node Exporter ?¤ì¹˜ ?€?? {server_name} ({server_ip})")
                                else:
                                    logger.warning(f"?œë²„ IP ?•ë³´ ?†ìŒ: {server_name}")
                            except Exception as e:
                                logger.warning(f"?œë²„ IP ?˜ì§‘ ì¤??¤ë¥˜ ({server_name}): {e}")
                        
                        # ?¼ê´„ ?¤ì¹˜ ?¤í–‰ (Node Exporter ?¬í•¨)
                        if server_ips:
                            logger.info(f"?”§ Node Exporter ?¼ê´„ ?¤ì¹˜ ?œì‘: {len(server_ips)}ê°??œë²„")
                            success, result = ansible_service.run_playbook(
                                role='node_exporter',
                                extra_vars={'install_node_exporter': True},
                                limit_hosts=','.join(server_ips)
                            )
                            
                            if success:
                                logger.info(f"Node Exporter ?¼ê´„ ?¤ì¹˜ ?±ê³µ: {len(server_ips)}ê°??œë²„")
                            else:
                                logger.error(f"Node Exporter ?¼ê´„ ?¤ì¹˜ ?¤íŒ¨: {result}")
                        else:
                            logger.warning(f"Node Exporter ?¤ì¹˜??? íš¨???œë²„ IPê°€ ?†ìŒ")
                    
                    # Prometheus ?¤ì • ?…ë°?´íŠ¸ (?€???œë²„ ?ì„± ?„ë£Œ ??
                    try:
                        from app.services.prometheus_service import PrometheusService
                        prometheus_service = PrometheusService()
                        prometheus_updated = prometheus_service.update_prometheus_config()
                        
                        if prometheus_updated:
                            logger.info(f"Prometheus ?¤ì • ?…ë°?´íŠ¸ ?„ë£Œ: {len(created_servers)}ê°??œë²„")
                        else:
                            logger.warning(f"Prometheus ?¤ì • ?…ë°?´íŠ¸ ?¤íŒ¨")
                    except Exception as e:
                        logger.warning(f"Prometheus ?¤ì • ?…ë°?´íŠ¸ ì¤??¤ë¥˜: {e}")
                    
                    # ê²°ê³¼ ë©”ì‹œì§€ ?ì„±
                    if created_servers and not failed_servers:
                        success_msg = f'ëª¨ë“  ?œë²„ ?ì„± ?„ë£Œ: {", ".join(created_servers)}'
                        update_task(task_id, 'completed', success_msg)
                        logger.info(f"{success_msg}")
                        # ?±ê³µ ?Œë¦¼ ?ì„±
                        for server_name in created_servers:
                            try:
                                NotificationService.create_server_notification(
                                    server_name, 'create', 'success', 
                                    f'?œë²„ {server_name} ?ì„±???„ë£Œ?˜ì—ˆ?µë‹ˆ??'
                                )
                            except Exception as notif_error:
                                logger.warning(f"?Œë¦¼ ?ì„± ?¤íŒ¨: {str(notif_error)}")
                    elif created_servers and failed_servers:
                        partial_msg = f'?¼ë? ?œë²„ ?ì„± ?„ë£Œ. ?±ê³µ: {", ".join(created_servers)}, ?¤íŒ¨: {", ".join(failed_servers)}'
                        update_task(task_id, 'completed', partial_msg)
                        logger.warning(f"{partial_msg}")
                        # ë¶€ë¶??±ê³µ ?Œë¦¼ ?ì„±
                        for server_name in created_servers:
                            try:
                                NotificationService.create_server_notification(
                                    server_name, 'create', 'success', 
                                    f'?œë²„ {server_name} ?ì„±???„ë£Œ?˜ì—ˆ?µë‹ˆ??'
                                )
                            except Exception as notif_error:
                                logger.warning(f"?Œë¦¼ ?ì„± ?¤íŒ¨: {str(notif_error)}")
                        for server_name in failed_servers:
                            try:
                                NotificationService.create_server_notification(
                                    server_name, 'create', 'error', 
                                    f'?œë²„ {server_name} ?ì„±???¤íŒ¨?ˆìŠµ?ˆë‹¤.'
                                )
                            except Exception as notif_error:
                                logger.warning(f"?Œë¦¼ ?ì„± ?¤íŒ¨: {str(notif_error)}")
                    else:
                        error_msg = f'ëª¨ë“  ?œë²„ ?ì„± ?¤íŒ¨: {", ".join(failed_servers)}'
                        update_task(task_id, 'failed', error_msg)
                        logger.error(f"{error_msg}")
                        # ?¤íŒ¨ ?Œë¦¼ ?ì„±
                        for server_name in failed_servers:
                            try:
                                NotificationService.create_server_notification(
                                    server_name, 'create', 'error', 
                                    f'?œë²„ {server_name} ?ì„±???¤íŒ¨?ˆìŠµ?ˆë‹¤.'
                                )
                            except Exception as notif_error:
                                logger.warning(f"?Œë¦¼ ?ì„± ?¤íŒ¨: {str(notif_error)}")
                    
                    # Prometheus ?¤ì • ?…ë°?´íŠ¸ (?¤ì¤‘ ?œë²„ ?ì„± ?„ë£Œ ??
                    if created_servers:
                        try:
                            from app.services.prometheus_service import PrometheusService
                            prometheus_service = PrometheusService()
                            prometheus_updated = prometheus_service.update_prometheus_config()
                            
                            if prometheus_updated:
                                logger.info(f"Prometheus ?¤ì • ?…ë°?´íŠ¸ ?„ë£Œ: {len(created_servers)}ê°??œë²„")
                            else:
                                logger.warning(f"Prometheus ?¤ì • ?…ë°?´íŠ¸ ?¤íŒ¨")
                                print(prometheus_service.get_manual_setup_instructions())
                        except Exception as e:
                            logger.warning(f"Prometheus ?¤ì • ?…ë°?´íŠ¸ ì¤??¤ë¥˜: {e}")
                            logger.info("?”§ Prometheus ?˜ë™ ?¤ì •???„ìš”?????ˆìŠµ?ˆë‹¤.")
                    
            except Exception as e:
                error_msg = f'?¤ì¤‘ ?œë²„ ?ì„± ?‘ì—… ì¤??ˆì™¸ ë°œìƒ: {str(e)}'
                logger.error(f"{error_msg}")
                import traceback
                traceback.print_exc()
                update_task(task_id, 'failed', error_msg)
        
        # ë°±ê·¸?¼ìš´?œì—???‘ì—… ?¤í–‰
        thread = threading.Thread(target=create_servers_bulk_task)
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'success': True,
            'message': f'{len(servers_data)}ê°??œë²„ ?ì„± ?‘ì—…???œì‘?˜ì—ˆ?µë‹ˆ??',
            'task_id': task_id
        })
        
    except Exception as e:
        logger.error(f"?¤ì¤‘ ?œë²„ ?ì„± API ?¤ë¥˜: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/servers/bulk_action', methods=['POST'])
@permission_required('manage_server')
def bulk_server_action():
    """?€???œë²„ ?‘ì—… ì²˜ë¦¬"""
    try:
        data = request.get_json()
        server_names = data.get('server_names', [])
        action = data.get('action')  # start, stop, reboot, delete
        
        if not server_names:
            return jsonify({'error': '?œë²„ ëª©ë¡???„ìš”?©ë‹ˆ??'}), 400
            
        if not action:
            return jsonify({'error': '?‘ì—… ? í˜•???„ìš”?©ë‹ˆ??'}), 400
            
        if action not in ['start', 'stop', 'reboot', 'delete']:
            return jsonify({'error': 'ì§€?í•˜ì§€ ?ŠëŠ” ?‘ì—…?…ë‹ˆ??'}), 400
        
        logger.info(f"?”§ ?€???œë²„ ?‘ì—…: {action} - {len(server_names)}ê°??œë²„")
        
        # Task ?ì„±
        task_id = create_task('running', 'bulk_server_action', f'{len(server_names)}ê°??œë²„ {action} ?‘ì—… ì¤?..')
        
        def bulk_action_task():
            try:
                from app import create_app
                app = create_app()
                with app.app_context():
                    logger.info(f"?”§ ?€???œë²„ ?‘ì—… ?œì‘: {action} - {server_names}")
                    
                    # ?? œ ?‘ì—…?€ Terraform ê¸°ë°˜?¼ë¡œ ì²˜ë¦¬
                    if action == 'delete':
                        success_servers, failed_servers = process_bulk_delete_terraform(server_names)
                    else:
                        # ê¸°ì¡´ Proxmox API ê¸°ë°˜ ?‘ì—… (start, stop, reboot)
                        success_servers, failed_servers = process_bulk_proxmox_action(server_names, action)
                    
                    # ê²°ê³¼ ë©”ì‹œì§€ ?ì„±
                    action_names = {
                        'start': '?œì‘',
                        'stop': 'ì¤‘ì?', 
                        'reboot': '?¬ì‹œ??,
                        'delete': '?? œ'
                    }
                    action_name = action_names.get(action, action)
                    
                    if success_servers and not failed_servers:
                        success_msg = f'ëª¨ë“  ?œë²„ {action_name} ?„ë£Œ: {", ".join(success_servers)}'
                        update_task(task_id, 'completed', success_msg)
                        logger.info(f"{success_msg}")
                        
                        # ?€???‘ì—… ?„ë£Œ ???œë²„ ?Œë¦¼ ?ì„±
                        from app.models.notification import Notification
                        notification = Notification(
                            type='bulk_server_action',
                            title='?€???‘ì—…',
                            message=success_msg,
                            severity='success',
                            details=f'?‘ì—… ? í˜•: {action_name}\n?±ê³µ???œë²„: {", ".join(success_servers)}'
                        )
                        db.session.add(notification)
                        db.session.commit()
                        logger.info(f"?”” ?€???‘ì—… ?„ë£Œ ?Œë¦¼ ?ì„±: {success_msg}")
                        
                    elif success_servers and failed_servers:
                        partial_msg = f'?¼ë? ?œë²„ {action_name} ?„ë£Œ. ?±ê³µ: {", ".join(success_servers)}, ?¤íŒ¨: {len(failed_servers)}ê°?
                        update_task(task_id, 'completed', partial_msg)
                        logger.warning(f"{partial_msg}")
                        logger.warning(f"?¤íŒ¨ ?ì„¸: {failed_servers}")
                        
                        # ë¶€ë¶??±ê³µ ???œë²„ ?Œë¦¼ ?ì„±
                        from app.models.notification import Notification
                        notification = Notification(
                            type='bulk_server_action',
                            title='?€???‘ì—…',
                            message=partial_msg,
                            severity='warning',
                            details=f'?‘ì—… ? í˜•: {action_name}\n?±ê³µ???œë²„: {", ".join(success_servers)}\n?¤íŒ¨???œë²„: {len(failed_servers)}ê°?
                        )
                        db.session.add(notification)
                        db.session.commit()
                        logger.info(f"?”” ?€???‘ì—… ë¶€ë¶??±ê³µ ?Œë¦¼ ?ì„±: {partial_msg}")
                        
                    else:
                        error_msg = f'ëª¨ë“  ?œë²„ {action_name} ?¤íŒ¨: {len(failed_servers)}ê°?
                        update_task(task_id, 'failed', error_msg)
                        logger.error(f"{error_msg}")
                        logger.error(f"?¤íŒ¨ ?ì„¸: {failed_servers}")
                        
                        # ?¤íŒ¨ ???œë²„ ?Œë¦¼ ?ì„±
                        from app.models.notification import Notification
                        notification = Notification(
                            type='bulk_server_action',
                            title='?€???‘ì—…',
                            message=error_msg,
                            severity='error',
                            details=f'?‘ì—… ? í˜•: {action_name}\n?¤íŒ¨???œë²„: {len(failed_servers)}ê°?
                        )
                        db.session.add(notification)
                        db.session.commit()
                        logger.info(f"?”” ?€???‘ì—… ?¤íŒ¨ ?Œë¦¼ ?ì„±: {error_msg}")
                        
            except Exception as e:
                error_msg = f'?€???œë²„ ?‘ì—… ì¤??ˆì™¸ ë°œìƒ: {str(e)}'
                logger.error(f"{error_msg}")
                import traceback
                traceback.print_exc()
                update_task(task_id, 'failed', error_msg)
        
        # ë°±ê·¸?¼ìš´?œì—???‘ì—… ?¤í–‰
        thread = threading.Thread(target=bulk_action_task)
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'success': True,
            'message': f'{len(server_names)}ê°??œë²„ {action} ?‘ì—…???œì‘?˜ì—ˆ?µë‹ˆ??',
            'task_id': task_id
        })
        
    except Exception as e:
        logger.error(f"?€???œë²„ ?‘ì—… API ?¤ë¥˜: {str(e)}")
        return jsonify({'error': str(e)}), 500

def process_bulk_delete_terraform(server_names):
    """Terraform ê¸°ë°˜ ?€???œë²„ ?? œ"""
    success_servers = []
    failed_servers = []
    
    try:
        logger.info(f"?—‘ï¸?Terraform ê¸°ë°˜ ?€???? œ ?œì‘: {server_names}")
        
        # 1. ?œë²„ ì¡´ì¬ ?•ì¸ ë°?? íš¨??ê²€??        valid_servers = []
        for server_name in server_names:
            server = Server.query.filter_by(name=server_name).first()
            if not server:
                failed_servers.append(f"{server_name}: ?œë²„ë¥?ì°¾ì„ ???†ìŒ")
                continue
            valid_servers.append(server_name)
        
        if not valid_servers:
            logger.info("??? íš¨???œë²„ê°€ ?†ìŠµ?ˆë‹¤.")
            return success_servers, failed_servers
        
        # 2. Proxmox APIë¥??µí•´ ?œë²„?¤ì„ ë¨¼ì? ì¤‘ì? (shutdown ?€??stop ?¬ìš©)
        from app.services.proxmox_service import ProxmoxService
        import time
        proxmox_service = ProxmoxService()
        
        logger.info(f"?›‘ ?œë²„ ì¤‘ì? ?¨ê³„ ?œì‘: {valid_servers}")
        for server_name in valid_servers:
            try:
                logger.info(f"?›‘ {server_name} ì¤‘ì? ì¤?..")
                stop_result = proxmox_service.stop_vm(server_name)
                if stop_result['success']:
                    logger.info(f"{server_name} ì¤‘ì? ?±ê³µ")
                else:
                    logger.warning(f"{server_name} ì¤‘ì? ?¤íŒ¨: {stop_result['message']}")
                    # ì¤‘ì? ?¤íŒ¨?´ë„ ê³„ì† ì§„í–‰ (?´ë? ì¤‘ì????íƒœ?????ˆìŒ)
            except Exception as e:
                logger.warning(f"{server_name} ì¤‘ì? ì¤??ˆì™¸ ë°œìƒ: {e}")
                # ?ˆì™¸ ë°œìƒ?´ë„ ê³„ì† ì§„í–‰
        
        # ?œë²„ ì¤‘ì? ??? ì‹œ ?€ê¸?(?„ì „??ì¤‘ì??˜ë„ë¡?
        logger.info("???œë²„ ì¤‘ì? ?„ë£Œ ?€ê¸?ì¤?.. (5ì´?")
        time.sleep(5)
        
        # 3. Terraform ?¤ì •?ì„œ ?? œ???œë²„???œê±°
        terraform_service = TerraformService()
        tfvars = terraform_service.load_tfvars()
        
        deleted_from_tfvars = []
        for server_name in valid_servers:
            if 'servers' in tfvars and server_name in tfvars['servers']:
                del tfvars['servers'][server_name]
                deleted_from_tfvars.append(server_name)
                logger.info(f"?—‘ï¸?tfvars.json?ì„œ {server_name} ?œê±°")
        
        if not deleted_from_tfvars:
            logger.info("??tfvars.json?ì„œ ?? œ???œë²„ë¥?ì°¾ì„ ???†ìŠµ?ˆë‹¤.")
            for server_name in valid_servers:
                failed_servers.append(f"{server_name}: tfvars.json?ì„œ ì°¾ì„ ???†ìŒ")
            return success_servers, failed_servers
        
        # 4. tfvars.json ?€??        terraform_service.save_tfvars(tfvars)
        logger.info(f"?’¾ tfvars.json ?…ë°?´íŠ¸ ?„ë£Œ: {len(deleted_from_tfvars)}ê°??œë²„ ?œê±°")
        
        # 5. Terraform destroy with targeted resources
        destroy_targets = []
        for server_name in deleted_from_tfvars:
            target = f'module.server["{server_name}"]'
            destroy_targets.append(target)
        
        logger.info(f"?”¥ Terraform destroy ?¤í–‰ - ?€?? {destroy_targets}")
        destroy_success, destroy_message = terraform_service.destroy_targets(destroy_targets)
        
        if destroy_success:
            logger.info(f"Terraform destroy ?±ê³µ: {deleted_from_tfvars}")
            
            # 5. SSH known_hosts ?•ë¦¬ (?? œ???œë²„?¤ì˜ IP ?œê±°)
            try:
                for server_name in deleted_from_tfvars:
                    server = Server.query.filter_by(name=server_name).first()
                    if server and server.ip_address:
                        # IP ì£¼ì†Œ?ì„œ ì²?ë²ˆì§¸ IP ì¶”ì¶œ
                        first_ip = server.ip_address.split(',')[0].strip()
                        if first_ip:
                            _remove_from_known_hosts(first_ip)
                            logger.info(f"?§¹ SSH known_hosts?ì„œ {first_ip} ?œê±° ?„ë£Œ")
            except Exception as e:
                logger.warning(f"SSH known_hosts ?•ë¦¬ ì¤??¤ë¥˜: {e}")
            
            # 6. Prometheus ?¤ì • ?…ë°?´íŠ¸ (?? œ???œë²„???œê±°)
            try:
                from app.services.prometheus_service import PrometheusService
                prometheus_service = PrometheusService()
                prometheus_updated = prometheus_service.update_prometheus_config()
                
                if prometheus_updated:
                    logger.info(f"Prometheus ?¤ì • ?…ë°?´íŠ¸ ?„ë£Œ: {len(deleted_from_tfvars)}ê°??œë²„ ?œê±°")
                else:
                    logger.warning(f"Prometheus ?¤ì • ?…ë°?´íŠ¸ ?¤íŒ¨")
            except Exception as e:
                logger.warning(f"Prometheus ?¤ì • ?…ë°?´íŠ¸ ì¤??¤ë¥˜: {e}")
            
            # 6. DB?ì„œ ?œë²„ ?œê±°
            for server_name in deleted_from_tfvars:
                server = Server.query.filter_by(name=server_name).first()
                if server:
                    db.session.delete(server)
                    logger.info(f"?—‘ï¸?DB?ì„œ {server_name} ?œê±°")
            
            db.session.commit()
            success_servers.extend(deleted_from_tfvars)
            
        else:
            logger.error(f"Terraform destroy ?¤íŒ¨: {destroy_message}")
            # destroy ?¤íŒ¨ ??tfvars.json ë³µì›
            for server_name in deleted_from_tfvars:
                server = Server.query.filter_by(name=server_name).first()
                if server:
                    # ?œë²„ ?•ë³´ë¥??¤ì‹œ tfvars??ì¶”ê? (ë³µì›)
                    if 'servers' not in tfvars:
                        tfvars['servers'] = {}
                    tfvars['servers'][server_name] = {
                        'cores': server.cores,
                        'memory': server.memory,
                        'disk': server.disk,
                        'role': server.role or 'web'
                    }
                failed_servers.append(f"{server_name}: Terraform destroy ?¤íŒ¨")
            
            # tfvars.json ë³µì›
            terraform_service.save_tfvars(tfvars)
            logger.info("?”„ tfvars.json ë³µì› ?„ë£Œ")
        
    except Exception as e:
        error_msg = f"?€???? œ ì¤??ˆì™¸ ë°œìƒ: {str(e)}"
        logger.error(f"{error_msg}")
        for server_name in server_names:
            if server_name not in success_servers:
                failed_servers.append(f"{server_name}: {error_msg}")
    
    return success_servers, failed_servers

def process_bulk_proxmox_action(server_names, action):
    """Proxmox API ê¸°ë°˜ ?€???œë²„ ?‘ì—… (start, stop, reboot)"""
    success_servers = []
    failed_servers = []
    
    try:
        proxmox_service = ProxmoxService()
        
        for server_name in server_names:
            try:
                logger.info(f"?”§ ?œë²„ ?‘ì—… ì²˜ë¦¬: {server_name} - {action}")
                
                # ?œë²„ ì¡´ì¬ ?•ì¸
                server = Server.query.filter_by(name=server_name).first()
                if not server:
                    failed_servers.append(f"{server_name}: ?œë²„ë¥?ì°¾ì„ ???†ìŒ")
                    continue
                
                # Proxmox API ?¸ì¶œ
                if action == 'start':
                    result = proxmox_service.start_vm(server_name)
                elif action == 'stop':
                    result = proxmox_service.stop_vm(server_name)
                elif action == 'reboot':
                    result = proxmox_service.reboot_vm(server_name)
                else:
                    failed_servers.append(f"{server_name}: ì§€?í•˜ì§€ ?ŠëŠ” ?‘ì—…")
                    continue
                
                if result.get('success', False):
                    success_servers.append(server_name)
                    
                    # DB ?íƒœ ?…ë°?´íŠ¸
                    if action == 'start':
                        server.status = 'running'
                    elif action == 'stop':
                        server.status = 'stopped'
                    # reboot???íƒœë¥?running?¼ë¡œ ? ì?
                    
                    db.session.commit()
                    logger.info(f"{server_name} {action} ?±ê³µ")
                else:
                    error_msg = result.get('message', '?????†ëŠ” ?¤ë¥˜')
                    failed_servers.append(f"{server_name}: {error_msg}")
                    logger.error(f"{server_name} {action} ?¤íŒ¨: {error_msg}")
                    
            except Exception as server_error:
                error_msg = f"{server_name}: {str(server_error)}"
                failed_servers.append(error_msg)
                logger.error(f"{server_name} ì²˜ë¦¬ ì¤??¤ë¥˜: {server_error}")
    
    except Exception as e:
        error_msg = f"?€??Proxmox ?‘ì—… ì¤??ˆì™¸ ë°œìƒ: {str(e)}"
        logger.error(f"{error_msg}")
        for server_name in server_names:
            if server_name not in success_servers:
                failed_servers.append(f"{server_name}: {error_msg}")
    
    return success_servers, failed_servers

@bp.route('/api/servers/<server_name>/start', methods=['POST'])
@permission_required('start_server')
def start_server(server_name):
    """?œë²„ ?œì‘"""
    try:
        from app.services.proxmox_service import ProxmoxService
        proxmox_service = ProxmoxService()
        
        server = Server.query.filter_by(name=server_name).first()
        if not server:
            return jsonify({'error': '?œë²„ë¥?ì°¾ì„ ???†ìŠµ?ˆë‹¤.'}), 404
        
        if proxmox_service.start_server(server_name):
            server.status = 'running'
            db.session.commit()
            return jsonify({'success': True, 'message': f'?œë²„ {server_name}ê°€ ?œì‘?˜ì—ˆ?µë‹ˆ??'})
        else:
            return jsonify({'error': f'?œë²„ {server_name} ?œì‘???¤íŒ¨?ˆìŠµ?ˆë‹¤.'}), 500
    except Exception as e:
        logger.error(f"?œë²„ ?œì‘ ?¤íŒ¨: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/servers/<server_name>/stop', methods=['POST'])
@permission_required('stop_server')
def stop_server(server_name):
    """?œë²„ ì¤‘ì?"""
    try:
        from app.services.proxmox_service import ProxmoxService
        proxmox_service = ProxmoxService()
        
        server = Server.query.filter_by(name=server_name).first()
        if not server:
            return jsonify({'error': '?œë²„ë¥?ì°¾ì„ ???†ìŠµ?ˆë‹¤.'}), 404
        
        if proxmox_service.stop_server(server_name):
            server.status = 'stopped'
            db.session.commit()
            return jsonify({'success': True, 'message': f'?œë²„ {server_name}ê°€ ì¤‘ì??˜ì—ˆ?µë‹ˆ??'})
        else:
            return jsonify({'error': f'?œë²„ {server_name} ì¤‘ì????¤íŒ¨?ˆìŠµ?ˆë‹¤.'}), 500
    except Exception as e:
        logger.error(f"?œë²„ ì¤‘ì? ?¤íŒ¨: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/servers/<server_name>/reboot', methods=['POST'])
@permission_required('reboot_server')
def reboot_server(server_name):
    """?œë²„ ?¬ë???""
    try:
        from app.services.proxmox_service import ProxmoxService
        proxmox_service = ProxmoxService()
        
        server = Server.query.filter_by(name=server_name).first()
        if not server:
            return jsonify({'error': '?œë²„ë¥?ì°¾ì„ ???†ìŠµ?ˆë‹¤.'}), 404
        
        if proxmox_service.reboot_server(server_name):
            return jsonify({'success': True, 'message': f'?œë²„ {server_name}ê°€ ?¬ë??…ë˜?ˆìŠµ?ˆë‹¤.'})
        else:
            return jsonify({'error': f'?œë²„ {server_name} ?¬ë??…ì— ?¤íŒ¨?ˆìŠµ?ˆë‹¤.'}), 500
    except Exception as e:
        logger.error(f"?œë²„ ?¬ë????¤íŒ¨: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/servers/<server_name>/delete', methods=['POST'])
@permission_required('delete_server')
def delete_server(server_name):
    """?œë²„ ?? œ"""
    try:
        server = Server.query.filter_by(name=server_name).first()
        if not server:
            return jsonify({'error': '?œë²„ë¥?ì°¾ì„ ???†ìŠµ?ˆë‹¤.'}), 404
        
        logger.info(f"?”§ ?œë²„ ?? œ ?œì‘: {server_name}")
        
        # ?™ê¸°?ìœ¼ë¡??œë²„ ?? œ ?¤í–‰
        success_servers, failed_servers = process_bulk_delete_terraform([server_name])
        
        if success_servers and server_name in success_servers:
            logger.info(f"?œë²„ ?? œ ?„ë£Œ: {server_name}")
            return jsonify({
                'success': True,
                'message': f'?œë²„ {server_name}ê°€ ?? œ?˜ì—ˆ?µë‹ˆ??'
            })
        else:
            # ?¤íŒ¨ ?ì¸ ë©”ì‹œì§€ ì¶”ì¶œ
            failure_reason = "?????†ëŠ” ?¤ë¥˜"
            for failed in failed_servers:
                if server_name in failed:
                    failure_reason = failed.split(": ", 1)[1] if ": " in failed else failed
                    break
                        
            logger.error(f"?œë²„ ?? œ ?¤íŒ¨: {failure_reason}")
            return jsonify({
                'success': False,
                'error': f'?œë²„ ?? œ ?¤íŒ¨: {failure_reason}'
            }), 500
        
    except Exception as e:
        logger.error(f"?œë²„ ?? œ ?¤íŒ¨: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/all_server_status', methods=['GET'])
@login_required
def get_all_server_status():
    """ëª¨ë“  ?œë²„ ?íƒœ ì¡°íšŒ (Redis ìºì‹± ?ìš©)"""
    try:
        # Redis ìºì‹œ ?•ì¸
        cache_key = "servers:all_status"
        cached_data = redis_utils.get_cache(cache_key)
        if cached_data:
            logger.info("?“¦ Redis ìºì‹œ?ì„œ ?œë²„ ?íƒœ ?°ì´??ë¡œë“œ")
            return jsonify(cached_data)
        
        logger.info("?Œ ?œë²„ ?íƒœ ?°ì´??ì¡°íšŒ (ìºì‹œ ë¯¸ìŠ¤)")
        from app.services.proxmox_service import ProxmoxService
        proxmox_service = ProxmoxService()
        
        # get_all_vms ?¨ìˆ˜ ?¬ìš© (?µê³„ ?•ë³´ ?¬í•¨)
        result = proxmox_service.get_all_vms()
        
        if result['success']:
            # ê¸°ì¡´ êµ¬ì¡°?€ ?¸í™˜?±ì„ ?„í•´ ?°ì´??ë³€??            servers = result['data']['servers']
            stats = result['data']['stats']
            
            # DB?ì„œ ?œë²„ ?•ë³´ ê°€?¸ì???ë³‘í•© (??• , ë°©í™”ë²?ê·¸ë£¹ ?•ë³´)
            db_servers = Server.query.all()
            db_server_map = {s.name: s for s in db_servers}
            
            # Proxmox ?°ì´?°ì— DB ?•ë³´ ë³‘í•©
            for vm_key, server_data in servers.items():
                server_name = server_data.get('name')
                if server_name and server_name in db_server_map:
                    db_server = db_server_map[server_name]
                    # DB????• ê³?ë°©í™”ë²?ê·¸ë£¹ ?•ë³´ë¥?Proxmox ?°ì´?°ì— ì¶”ê?
                    server_data['role'] = db_server.role
                    server_data['firewall_group'] = db_server.firewall_group
                    server_data['os_type'] = db_server.os_type
                    logger.info(f"?”§ ?œë²„ '{server_name}' DB ?•ë³´ ë³‘í•©: role={db_server.role}, firewall_group={db_server.firewall_group}")
            
            # ?µê³„ ?•ë³´ë¥??¬í•¨?˜ì—¬ ë°˜í™˜
            response_data = {
                'success': True,
                'servers': servers,
                'stats': stats
            }
            
            # Redis??ìºì‹œ ?€??(2ë¶?
            redis_utils.set_cache(cache_key, response_data, expire=120)
            logger.info("?’¾ ?œë²„ ?íƒœ ?°ì´?°ë? Redis??ìºì‹œ ?€??)
            
            return jsonify(response_data)
        else:
            # ?¤íŒ¨ ??ê¸°ë³¸ êµ¬ì¡°ë¡?ë°˜í™˜
            return jsonify({
                'success': False,
                'servers': {},
                'stats': {
                    'total_servers': 0,
                    'running_servers': 0,
                    'stopped_servers': 0,
                    'node_total_cpu': 0,
                    'node_total_memory_gb': 0,
                    'vm_total_cpu': 0,
                    'vm_total_memory_gb': 0,
                    'vm_used_cpu': 0,
                    'vm_used_memory_gb': 0,
                    'cpu_usage_percent': 0,
                    'memory_usage_percent': 0
                }
            })
        
    except Exception as e:
        logger.error(f"?œë²„ ?íƒœ ì¡°íšŒ ?¤íŒ¨: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/servers/async', methods=['POST'])
@permission_required('create_server')
def create_server_async_endpoint():
    """ë¹„ë™ê¸??œë²„ ?ì„±"""
    try:
        # ì§€???„í¬?¸ë¡œ ?œí™˜ ì°¸ì¡° ë°©ì?
        from app.tasks.server_tasks import create_server_async
        data = request.get_json()
        server_name = data.get('name')
        cpu = data.get('cpu', 2)
        memory = data.get('memory', 4)
        disk = data.get('disk', 20)
        os_type = data.get('os_type', 'ubuntu')
        role = data.get('role', '')
        firewall_group = data.get('firewall_group', '')
        
        if not server_name:
            return jsonify({'error': '?œë²„ ?´ë¦„???„ìš”?©ë‹ˆ??'}), 400
        
        # ?œë²„ ?´ë¦„ ì¤‘ë³µ ?•ì¸
        existing_server = Server.query.filter_by(name=server_name).first()
        if existing_server:
            return jsonify({'error': '?´ë? ì¡´ì¬?˜ëŠ” ?œë²„ ?´ë¦„?…ë‹ˆ??'}), 400
        
        # ?œë²„ ?¤ì • êµ¬ì„±
        server_config = {
            'name': server_name,
            'cpu': cpu,
            'memory': memory,
            'disk': disk,
            'os_type': os_type,
            'role': role,
            'firewall_group': firewall_group
        }
        
        # Celery ?‘ì—… ?¤í–‰
        task = create_server_async.delay(server_config)
        
        logger.info(f"?? ë¹„ë™ê¸??œë²„ ?ì„± ?‘ì—… ?œì‘: {server_name} (Task ID: {task.id})")
        
        return jsonify({
            'success': True,
            'task_id': task.id,
            'message': f'?œë²„ {server_name} ?ì„± ?‘ì—…???œì‘?˜ì—ˆ?µë‹ˆ??',
            'status': 'queued'
        })
        
    except Exception as e:
        logger.error(f"ë¹„ë™ê¸??œë²„ ?ì„± ?¤íŒ¨: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/servers/bulk_action/async', methods=['POST'])
@permission_required('manage_server')
def bulk_server_action_async_endpoint():
    """ë¹„ë™ê¸??€???œë²„ ?‘ì—…"""
    try:
        # ì§€???„í¬?¸ë¡œ ?œí™˜ ì°¸ì¡° ë°©ì?
        from app.tasks.server_tasks import bulk_server_action_async
        data = request.get_json()
        server_names = data.get('server_names', [])
        action = data.get('action')
        
        if not server_names:
            return jsonify({'error': '?œë²„ ëª©ë¡???„ìš”?©ë‹ˆ??'}), 400
            
        if not action:
            return jsonify({'error': '?‘ì—… ? í˜•???„ìš”?©ë‹ˆ??'}), 400
            
        if action not in ['start', 'stop', 'reboot', 'delete']:
            return jsonify({'error': 'ì§€?í•˜ì§€ ?ŠëŠ” ?‘ì—…?…ë‹ˆ??'}), 400
        
        # Celery ?‘ì—… ?¤í–‰
        task = bulk_server_action_async.delay(server_names, action)
        
        logger.info(f"?? ë¹„ë™ê¸??€???œë²„ ?‘ì—… ?œì‘: {action} - {len(server_names)}ê°??œë²„ (Task ID: {task.id})")
        
        return jsonify({
            'success': True,
            'task_id': task.id,
            'message': f'{len(server_names)}ê°??œë²„ {action} ?‘ì—…???œì‘?˜ì—ˆ?µë‹ˆ??',
            'status': 'queued'
        })
        
    except Exception as e:
        logger.error(f"ë¹„ë™ê¸??€???œë²„ ?‘ì—… ?¤íŒ¨: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/tasks/<task_id>/status', methods=['GET'])
@login_required
def get_task_status_async(task_id):
    """ë¹„ë™ê¸??‘ì—… ?íƒœ ì¡°íšŒ"""
    try:
        # Celery ?‘ì—… ?íƒœ ì¡°íšŒ
        task = celery_app.AsyncResult(task_id)
        
        if task.state == 'PENDING':
            response = {
                'task_id': task_id,
                'status': 'pending',
                'message': '?‘ì—… ?€ê¸?ì¤?..',
                'progress': 0
            }
        elif task.state == 'PROGRESS':
            response = {
                'task_id': task_id,
                'status': 'running',
                'message': task.info.get('status', '?‘ì—… ì§„í–‰ ì¤?..'),
                'progress': task.info.get('current', 0),
                'total': task.info.get('total', 100)
            }
        elif task.state == 'SUCCESS':
            response = {
                'task_id': task_id,
                'status': 'completed',
                'message': task.info.get('message', '?‘ì—… ?„ë£Œ'),
                'result': task.result
            }
        elif task.state == 'FAILURE':
            response = {
                'task_id': task_id,
                'status': 'failed',
                'message': str(task.info),
                'error': str(task.info)
            }
        else:
            response = {
                'task_id': task_id,
                'status': task.state.lower(),
                'message': f'?‘ì—… ?íƒœ: {task.state}'
            }
        
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"?‘ì—… ?íƒœ ì¡°íšŒ ?¤íŒ¨: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/proxmox_storage', methods=['GET'])
def proxmox_storage():
    """Proxmox ?¤í† ë¦¬ì? ?•ë³´ ì¡°íšŒ"""
    try:
        from app.services.proxmox_service import ProxmoxService
        proxmox_service = ProxmoxService()
        
        storage_info = proxmox_service.get_storage_info()
        
        return jsonify({
            'success': True,
            'data': storage_info.get('data', [])  # storage ???€??data ?¤ë¡œ ë°˜í™˜
        })
    except Exception as e:
        logger.error(f"?¤í† ë¦¬ì? ?•ë³´ ì¡°íšŒ ?¤íŒ¨: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/sync_servers', methods=['POST'])
@login_required
def sync_servers():
    """ê¸°ì¡´ ?œë²„ë¥?DB???™ê¸°??""
    try:
        logger.info("?”§ ?œë²„ ?™ê¸°???œì‘")
        from app.services.proxmox_service import ProxmoxService
        proxmox_service = ProxmoxService()
        
        # Proxmox?ì„œ ?œë²„ ëª©ë¡ ê°€?¸ì˜¤ê¸?        vm_list = proxmox_service.get_vm_list()
        logger.info(f"?”§ Proxmox?ì„œ ê°€?¸ì˜¨ ?œë²„: {[vm['name'] for vm in vm_list]}")
        
        synced_count = 0
        
        for vm in vm_list:
            # DB?ì„œ ?œë²„ ?•ì¸
            existing_server = Server.query.filter_by(name=vm['name']).first()
            if not existing_server:
                # ???œë²„ ?ì„±
                new_server = Server(
                    name=vm['name'],
                    vmid=vm['vmid'],
                    status=vm['status'],
                    ip_address=vm.get('ip_addresses', [None])[0] if vm.get('ip_addresses') else None
                )
                db.session.add(new_server)
                synced_count += 1
                logger.info(f"?œë²„ ?™ê¸°?? {vm['name']}")
            else:
                # ê¸°ì¡´ ?œë²„ ?•ë³´ ?…ë°?´íŠ¸
                existing_server.vmid = vm['vmid']
                existing_server.status = vm['status']
                existing_server.ip_address = vm.get('ip_addresses', [None])[0] if vm.get('ip_addresses') else None
                logger.info(f"?”„ ?œë²„ ?•ë³´ ?…ë°?´íŠ¸: {vm['name']}")
        
        db.session.commit()
        logger.info(f"?œë²„ ?™ê¸°???„ë£Œ: {synced_count}ê°??œë²„ ì¶”ê???)
        
        return jsonify({
            'success': True, 
            'message': f'{synced_count}ê°??œë²„ê°€ DB???™ê¸°?”ë˜?ˆìŠµ?ˆë‹¤.'
        })
        
    except Exception as e:
        logger.error(f"?œë²„ ?™ê¸°???¤íŒ¨: {str(e)}")
        return jsonify({'error': str(e)}), 500

# ê¸°ì¡´ ?œë²„ ê´€???¼ìš°?¸ë“¤ (?¸í™˜??? ì?)
@bp.route('/')
@login_required
@permission_required('view_all')
def index():
    """?œë²„ ëª©ë¡ ?˜ì´ì§€"""
    servers = Server.query.all()
    return render_template('servers/index.html', servers=servers)

@bp.route('/create', methods=['GET', 'POST'])
@login_required
@permission_required('create_server')
def create():
    """?œë²„ ?ì„± ?˜ì´ì§€"""
    if request.method == 'POST':
        data = request.get_json()
        server_name = data.get('name')
        cpu = data.get('cpu', 2)
        memory = data.get('memory', 2048)
        
        if not server_name:
            return jsonify({'error': '?œë²„ ?´ë¦„???„ìš”?©ë‹ˆ??'}), 400
        
        # ?œë²„ ?´ë¦„ ì¤‘ë³µ ?•ì¸
        existing_server = Server.query.filter_by(name=server_name).first()
        if existing_server:
            return jsonify({'error': '?´ë? ì¡´ì¬?˜ëŠ” ?œë²„ ?´ë¦„?…ë‹ˆ??'}), 400
        
        # Task ?ì„±
        task_id = create_task('running', 'create_server', f'?œë²„ {server_name} ?ì„± ì¤?..')
        
        def create_server_background():
            try:
                from app import create_app
                app = create_app()
                with app.app_context():
                    logger.info(f"?”§ ?œë²„ ?ì„± ?‘ì—… ?œì‘: {server_name}")
                    
                    # Terraform ?œë¹„??ì´ˆê¸°??                    terraform_service = TerraformService()
                    
                    # ?œë²„ ?¤ì • ?ì„±
                    server_data = {
                        'name': server_name,
                        'cpu': cpu,
                        'memory': memory
                    }
                    config_success = terraform_service.create_server_config(server_data)
                    
                    if not config_success:
                        update_task(task_id, 'failed', f'?œë²„ ?¤ì • ?ì„± ?¤íŒ¨')
                        return
                    
                    # ?¸í”„??ë°°í¬
                    deploy_success, deploy_message = terraform_service.deploy_infrastructure()
                    
                    if not deploy_success:
                        update_task(task_id, 'failed', f'?¸í”„??ë°°í¬ ?¤íŒ¨: {deploy_message}')
                        return
                    
                    # Proxmox?ì„œ ?¤ì œ VM ?ì„± ?•ì¸
                    proxmox_service = ProxmoxService()
                    vm_exists = proxmox_service.check_vm_exists(server_name)
                    
                    if not vm_exists:
                        update_task(task_id, 'failed', 'Proxmox?ì„œ VM??ì°¾ì„ ???†ìŠµ?ˆë‹¤.')
                        return
                    
                    # VM ID ê°€?¸ì˜¤ê¸?                    vm_id = None
                    try:
                        # Terraform output?ì„œ VM ID ê°€?¸ì˜¤ê¸?                        terraform_output = terraform_service.output()
                        logger.info(f"?” Terraform output ?„ì²´: {terraform_output}")
                        
                        if 'vm_ids' in terraform_output:
                            vm_ids_data = terraform_output['vm_ids']
                            logger.info(f"?” vm_ids ?°ì´?? {vm_ids_data}")
                            
                            # Terraform output êµ¬ì¡°: {"vm_ids": {"value": {"test1": 110}}}
                            if 'value' in vm_ids_data and server_name in vm_ids_data['value']:
                                vm_id = vm_ids_data['value'][server_name]
                                logger.info(f"?” Terraform output?ì„œ VM ID ì¡°íšŒ: {server_name} = {vm_id}")
                        
                        # VM IDê°€ ?†ìœ¼ë©?Proxmox API?ì„œ ì¡°íšŒ
                        if not vm_id:
                            vm_exists, vm_info = proxmox_service.check_vm_exists(server_name)
                            if vm_exists and vm_info:
                                vm_id = vm_info.get('vmid')
                                logger.info(f"?” Proxmox API?ì„œ VM ID ì¡°íšŒ: {server_name} = {vm_id}")
                    except Exception as e:
                        logger.warning(f"VM ID ì¡°íšŒ ?¤íŒ¨: {e}")
                        import traceback
                        traceback.print_exc()
                    
                    # ê¸°ë³¸ê°??¤ì • (???¨ìˆ˜?ì„œ??role, os_type, ip_addressê°€ ?•ì˜?˜ì? ?ŠìŒ)
                    role = ''  # ê¸°ë³¸ê°?                    os_type = 'rocky'  # ê¸°ë³¸ê°?                    ip_address_str = ''  # ê¸°ë³¸ê°?                    
                    # DB???œë²„ ?•ë³´ ?€??(VM ID ?¬í•¨)
                    new_server = Server(
                        name=server_name,
                        vmid=vm_id,  # VM ID ì¶”ê?
                        ip_address=ip_address_str,  # IP ì£¼ì†Œ ì¶”ê? (ë¬¸ì?´ë¡œ ë³€??
                        role=role,  # ??•  ?•ë³´ ì¶”ê?
                        status='stopped',  # ì´ˆê¸° ?íƒœ??ì¤‘ì???                        cpu=cpu,
                        memory=memory,
                        os_type=os_type  # OS ?€??ì¶”ê?
                    )
                    db.session.add(new_server)
                    db.session.commit()
                    logger.info(f"DB???œë²„ ?€???„ë£Œ: {server_name} (ID: {new_server.id}, VM ID: {vm_id})")
                    
                    # Node Exporter ?ë™ ?¤ì¹˜ (ëª¨ë‹ˆ?°ë§?? - IPê°€ ?†ëŠ” ê²½ìš° ?¤í‚µ
                    ansible_service = AnsibleService()
                    node_exporter_installed = False
                    if ip_address_str:
                        try:
                            server_ip = ip_address_str.split(',')[0].strip()
                            logger.info(f"?”§ Node Exporter ?ë™ ?¤ì¹˜ ?œì‘: {server_name} ({server_ip})")
                            node_exporter_installed = ansible_service._install_node_exporter_if_needed(server_name, server_ip)
                            if node_exporter_installed:
                                logger.info(f"Node Exporter ?¤ì¹˜ ?„ë£Œ: {server_name}")
                            else:
                                logger.warning(f"Node Exporter ?¤ì¹˜ ?¤íŒ¨: {server_name}")
                        except Exception as e:
                            logger.warning(f"Node Exporter ?¤ì¹˜ ì¤??¤ë¥˜: {e}")
                    else:
                        logger.warning(f"IP ì£¼ì†Œê°€ ?†ì–´ Node Exporter ?¤ì¹˜ ?¤í‚µ: {server_name}")
                    
                    # Ansible???µí•œ ??• ë³??Œí”„?¸ì›¨???¤ì¹˜ (Node Exporter ?¬í•¨)
                    if role and role != 'none':
                        logger.info(f"?”§ Ansible ??•  ? ë‹¹ ?œì‘: {server_name} - {role}")
                        try:
                            ansible_service = AnsibleService()
                            # ?œë²„ ?ì„± ?œì—??Node Exporter???¨ê»˜ ?¤ì¹˜
                            ansible_success, ansible_message = ansible_service.run_playbook(
                                role=role,
                                extra_vars={'install_node_exporter': True},
                                target_server=ip_address_str
                            )
                            
                            if ansible_success:
                                logger.info(f"Ansible ??•  ? ë‹¹ ?±ê³µ: {server_name} - {role}")
                            else:
                                logger.warning(f"Ansible ??•  ? ë‹¹ ?¤íŒ¨: {server_name} - {role}, ë©”ì‹œì§€: {ansible_message}")
                        except Exception as ansible_error:
                            logger.warning(f"Ansible ?¤í–‰ ì¤??¤ë¥˜: {str(ansible_error)}")
                    
                    update_task(task_id, 'completed', f'?œë²„ {server_name} ?ì„± ?„ë£Œ')
                    logger.info(f"?œë²„ ?ì„± ?„ë£Œ: {server_name}")
                    
            except Exception as e:
                logger.error(f"?œë²„ ?ì„± ?‘ì—… ?¤íŒ¨: {str(e)}")
                update_task(task_id, 'failed', f'?œë²„ ?ì„± ì¤??¤ë¥˜: {str(e)}')
        
        thread = threading.Thread(target=create_server_background)
        thread.start()
        
        return jsonify({
            'success': True,
            'task_id': task_id,
            'message': f'?œë²„ {server_name} ?ì„±???œì‘?˜ì—ˆ?µë‹ˆ??'
        })
    
    return render_template('servers/create.html')

@bp.route('/<int:server_id>')
@login_required
@permission_required('view_all')
def detail(server_id):
    """?œë²„ ?ì„¸ ?˜ì´ì§€"""
    server = Server.query.get_or_404(server_id)
    return render_template('servers/detail.html', server=server)



@bp.route('/status')
@login_required
@permission_required('view_all')
def status():
    """?œë²„ ?íƒœ ì¡°íšŒ"""
    servers = Server.query.all()
    return jsonify([server.to_dict() for server in servers]) 


@bp.route('/api/ansible/status', methods=['GET'])
@login_required
def check_ansible_status():
    """Ansible ?¤ì¹˜ ?íƒœ ?•ì¸"""
    try:
        ansible_service = AnsibleService()
        is_installed, message = ansible_service.check_ansible_installation()
        
        return jsonify({
            'success': True,
            'installed': is_installed,
            'message': message
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'installed': False,
            'message': f'Ansible ?íƒœ ?•ì¸ ?¤íŒ¨: {str(e)}'
        }), 500

@bp.route('/api/assign_role/<server_name>', methods=['POST'])
@login_required
@permission_required('assign_roles')
def assign_role_to_server(server_name):
    """?œë²„????•  ? ë‹¹ (DB ê¸°ë°˜ + Ansible ?¤í–‰)"""
    try:
        logger.info(f"?”§ ??•  ? ë‹¹ ?”ì²­: {server_name}")
        
        data = request.get_json()
        role = data.get('role')
        logger.info(f"?”§ ? ë‹¹????• : {role}")
        
        # ë¹?ë¬¸ì?´ë„ ?ˆìš© (??•  ?œê±°)
        if role is None:
            return jsonify({'error': '??• (role)??ì§€?•í•´???©ë‹ˆ??'}), 400
        
        # AnsibleServiceë¥??µí•´ ??•  ? ë‹¹ (DB ?…ë°?´íŠ¸ + Ansible ?¤í–‰)
        ansible_service = AnsibleService()
        success, message = ansible_service.assign_role_to_server(server_name, role)
        
        if success:
            return jsonify({
                'success': True,
                'message': message
            })
        else:
            return jsonify({'error': message}), 500
            
    except Exception as e:
        logger.error(f"??•  ? ë‹¹ ?¤íŒ¨: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@bp.route('/api/remove_role/<server_name>', methods=['POST'])
@permission_required('remove_role')
def remove_role(server_name):
    """?œë²„?ì„œ ??•  ?œê±°"""
    try:
        from app import db
        server = Server.query.filter_by(name=server_name).first()
        if not server:
            return jsonify({'error': '?œë²„ë¥?ì°¾ì„ ???†ìŠµ?ˆë‹¤.'}), 404
        
        server.role = None
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': f'?œë²„ {server_name}?ì„œ ??• ???œê±°?˜ì—ˆ?µë‹ˆ??'
        })
    except Exception as e:
        logger.error(f"??•  ?œê±° ?¤íŒ¨: {str(e)}")
        return jsonify({'error': str(e)}), 500



@bp.route('/api/server/config/<server_name>', methods=['GET'])
@permission_required('view_all')
def get_server_config(server_name):
    """?œë²„ ?¤ì • ì¡°íšŒ"""
    try:
        from app.services.proxmox_service import ProxmoxService
        proxmox_service = ProxmoxService()
        
        result = proxmox_service.get_server_config(server_name)
        if result['success']:
            return jsonify(result)
        else:
            return jsonify({'error': result.get('message', '?œë²„ ?¤ì • ì¡°íšŒ ?¤íŒ¨')}), 500
            
    except Exception as e:
        logger.error(f"?œë²„ ?¤ì • ì¡°íšŒ ?¤íŒ¨: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/server/config/<server_name>', methods=['PUT'])
@permission_required('view_all')
def update_server_config(server_name):
    """?œë²„ ?¤ì • ?…ë°?´íŠ¸"""
    try:
        data = request.get_json()
        
        from app.services.proxmox_service import ProxmoxService
        proxmox_service = ProxmoxService()
        
        result = proxmox_service.update_server_config(server_name, data)
        if result['success']:
            return jsonify(result)
        else:
            return jsonify({'error': result.get('message', '?œë²„ ?¤ì • ?…ë°?´íŠ¸ ?¤íŒ¨')}), 500
            
    except Exception as e:
        logger.error(f"?œë²„ ?¤ì • ?…ë°?´íŠ¸ ?¤íŒ¨: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/server/logs/<server_name>', methods=['GET'])
@permission_required('view_all')
def get_server_logs(server_name):
    """?œë²„ ë¡œê·¸ ì¡°íšŒ"""
    try:
        from app.services.proxmox_service import ProxmoxService
        proxmox_service = ProxmoxService()
        
        result = proxmox_service.get_server_logs(server_name)
        if result['success']:
            return jsonify(result)
        else:
            return jsonify({'error': result.get('message', '?œë²„ ë¡œê·¸ ì¡°íšŒ ?¤íŒ¨')}), 500
            
    except Exception as e:
        logger.error(f"?œë²„ ë¡œê·¸ ì¡°íšŒ ?¤íŒ¨: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/server/disk/<server_name>', methods=['POST'])
@permission_required('view_all')
def add_server_disk(server_name):
    """?œë²„ ?”ìŠ¤??ì¶”ê?"""
    try:
        data = request.get_json()
        
        from app.services.proxmox_service import ProxmoxService
        proxmox_service = ProxmoxService()
        
        result = proxmox_service.add_server_disk(server_name, data)
        if result['success']:
            return jsonify(result)
        else:
            return jsonify({'error': result.get('message', '?”ìŠ¤??ì¶”ê? ?¤íŒ¨')}), 500
            
    except Exception as e:
        logger.error(f"?”ìŠ¤??ì¶”ê? ?¤íŒ¨: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/server/disk/<server_name>/<device>', methods=['DELETE'])
@permission_required('view_all')
def remove_server_disk(server_name, device):
    """?œë²„ ?”ìŠ¤???œê±°"""
    try:
        from app.services.proxmox_service import ProxmoxService
        proxmox_service = ProxmoxService()
        
        result = proxmox_service.remove_server_disk(server_name, device)
        if result['success']:
            return jsonify(result)
        else:
            return jsonify({'error': result.get('message', '?”ìŠ¤???œê±° ?¤íŒ¨')}), 500
            
    except Exception as e:
        logger.error(f"?”ìŠ¤???œê±° ?¤íŒ¨: {str(e)}")
        return jsonify({'error': str(e)}), 500    

@bp.route('/api/roles/assign_bulk', methods=['POST'])
@permission_required('assign_roles')
def assign_role_bulk():
    """?¤ì¤‘ ?œë²„????•  ? ë‹¹"""
    try:
        logger.info(f"?”§ ?¤ì¤‘ ?œë²„ ??•  ? ë‹¹ ?”ì²­")
        
        data = request.get_json()
        server_names = data.get('server_names', [])
        role = data.get('role')
        
        logger.info(f"?”§ ?€???œë²„?? {server_names}")
        logger.info(f"?”§ ? ë‹¹????• : {role}")
        
        if not server_names:
            return jsonify({'error': '?œë²„ ëª©ë¡??ì§€?•í•´???©ë‹ˆ??'}), 400
        
        if not role or role == '':
            return jsonify({'error': '??• (role)??ì§€?•í•´???©ë‹ˆ??'}), 400
        
        # "none" ê°’ì„ ??•  ?´ì œë¡?ì²˜ë¦¬
        if role == 'none':
            logger.info(f"?”§ ??•  ?´ì œ ?”ì²­?¼ë¡œ ë³€?? none ??None")
            role = None
        
        # AnsibleServiceë¥??µí•´ ??ë²ˆì— ??•  ? ë‹¹ (?™ì  ?¸ë²¤? ë¦¬ + --limit)
        ansible_service = AnsibleService()
        # DB?ì„œ ?€???œë²„ ?•ë³´ ?˜ì§‘ (IP ?„ìˆ˜)
        db_servers = Server.query.filter(Server.name.in_(server_names)).all()
        target_servers = []
        missing = []
        for s in db_servers:
            if s.ip_address:
                target_servers.append({'ip_address': s.ip_address})
            else:
                missing.append(s.name)
        
        # ??•  ?´ì œ??ê²½ìš° ë³„ë„ ì²˜ë¦¬ (Ansible ?¤í–‰ ?†ì´ DBë§??…ë°?´íŠ¸)
        if role is None:
            logger.info(f"?”§ ??•  ?´ì œ: DB?ì„œë§???•  ?œê±°")
            updated_count = 0
            for server in db_servers:
                server.role = None
                updated_count += 1
            
        from app import db
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'{updated_count}ê°??œë²„?ì„œ ??• ???´ì œ?˜ì—ˆ?µë‹ˆ??',
            'targets': [s.name for s in db_servers],
            'missing_ip': missing
        })
        
        if not target_servers:
            return jsonify({'error': '? íƒ???œë²„?¤ì— ? íš¨??IPê°€ ?†ìŠµ?ˆë‹¤.'}), 400
        
        success, message = ansible_service.run_role_for_multiple_servers(target_servers, role)
        logger.info(f"?”§ ?¼ê´„ ??•  ?¤í–‰ ê²°ê³¼: success={success}")

        # ?¤í–‰ ê²°ê³¼ ë°˜ì˜: DB ?…ë°?´íŠ¸ ë°??Œë¦¼ ?ì„±
        try:
            from app import db
            from app.models.notification import Notification

            if success:
                # DB????•  ë°˜ì˜
                updated = 0
                for s in db_servers:
                    # ?€?ì— ?¬í•¨???œë²„ë§?                    if s.ip_address and any(t['ip_address'] == s.ip_address for t in target_servers):
                        s.role = role
                        updated += 1
                        # ?±ê³µ ?Œë¦¼ ?ì„±
                        n = Notification.create_notification(
                            type='ansible_role',
                            title=f"?œë²„ {s.name} ??•  ? ë‹¹ ?„ë£Œ",
                            message=f"??•  '{role}'???±ê³µ?ìœ¼ë¡??ìš©?˜ì—ˆ?µë‹ˆ??",
                            # Ansible stdout(?±ê³µ ë¡œê·¸)??detailsë¡??€??(ê¸¸ë©´ ê·¸ë?ë¡??€?? UI?ì„œ ëª¨ë‹¬ë¡??œì‹œ)
                            details=message,
                            severity='success'
                        )
                        logger.info(f"?Œë¦¼ ?ì„±: id={n.id} ?œë²„={s.name}")
                db.session.commit()
                logger.info(f"?¼ê´„ ??•  DB ?…ë°?´íŠ¸ ?„ë£Œ: {updated}ê°??œë²„")
            else:
                # ?¤íŒ¨ ?Œë¦¼(?”ì•½)
                for s in db_servers:
                    n = Notification.create_notification(
                        type='ansible_role',
                        title=f"?œë²„ {s.name} ??•  ? ë‹¹ ?¤íŒ¨",
                        message="Ansible ?¤í–‰ ì¤??¤ë¥˜ê°€ ë°œìƒ?ˆìŠµ?ˆë‹¤.",
                        details=message,
                        severity='error'
                    )
                    logger.info(f"?Œë¦¼ ?ì„±: id={n.id} ?œë²„={s.name} (?¤íŒ¨)")
        except Exception as notify_err:
            logger.warning(f"?¼ê´„ ??•  ?Œë¦¼/DB ë°˜ì˜ ì¤??¤ë¥˜: {notify_err}")

        return jsonify({
            'success': success,
            'message': message,
            'targets': [s['ip_address'] for s in target_servers],
            'missing_ip': missing
        })
        
    except Exception as e:
        logger.error(f"?¤ì¤‘ ?œë²„ ??•  ? ë‹¹ ?¤íŒ¨: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# ?„ë½??API ?”ë“œ?¬ì¸?¸ë“¤ ì¶”ê?

@bp.route('/api/server_status/<server_name>', methods=['GET'])
@login_required
def get_server_status(server_name):
    """?œë²„ ?íƒœ ì¡°íšŒ"""
    try:
        from app.services.proxmox_service import ProxmoxService
        proxmox_service = ProxmoxService()
        result = proxmox_service.get_server_status(server_name)
        
        if result['success']:
            return jsonify(result['data'])
        else:
            return jsonify({'error': result['message']}), 500
    except Exception as e:
        logger.error(f"?œë²„ ?íƒœ ì¡°íšŒ ?¤íŒ¨: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/roles/available', methods=['GET'])
@login_required
def get_available_roles():
    """?¬ìš© ê°€?¥í•œ ??•  ëª©ë¡ ì¡°íšŒ"""
    try:
        roles = {
            'web': {'name': '?¹ì„œë²?, 'description': '???œë¹„???œê³µ'},
            'was': {'name': 'WAS', 'description': '? í”Œë¦¬ì??´ì…˜ ?œë²„'},
            'db': {'name': 'DB', 'description': '?°ì´?°ë² ?´ìŠ¤ ?œë²„'},
            'java': {'name': 'JAVA', 'description': '?ë°” ?œë²„'},
            'search': {'name': 'ê²€??, 'description': 'ê²€???œë²„'},
            'ftp': {'name': 'FTP', 'description': '?Œì¼ ?œë²„'}
        }
        
        return jsonify({
            'success': True,
            'roles': roles
        })
        
    except Exception as e:
        logger.error(f"??•  ëª©ë¡ ì¡°íšŒ ?¤íŒ¨: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/roles/validate/<role_name>', methods=['GET'])
@login_required
def validate_role(role_name):
    """??•  ? íš¨??ê²€??""
    try:
        valid_roles = ['web', 'was', 'db', 'java', 'search', 'ftp']
        
        if role_name in valid_roles:
            return jsonify({
                'success': True,
                'valid': True,
                'message': f'??•  "{role_name}"?€ ? íš¨?©ë‹ˆ??
            })
        else:
            return jsonify({
                'success': True,
                'valid': False,
                'message': f'??•  "{role_name}"?€ ? íš¨?˜ì? ?ŠìŠµ?ˆë‹¤'
            })
            
    except Exception as e:
        logger.error(f"??•  ? íš¨??ê²€???¤íŒ¨: {str(e)}")
        return jsonify({'error': str(e)}), 500 

#@bp.route.*datastores', methods=['GET'])
@login_required
def get_datastores():
    """?¬ìš© ê°€?¥í•œ datastore ëª©ë¡ ì¡°íšŒ (DB ìºì‹±)"""
    try:
        from app.models.datastore import Datastore
        
        # DB?ì„œ datastore ëª©ë¡ ì¡°íšŒ
        db_datastores = Datastore.query.filter_by(enabled=True).all()
        
        # DB??datastoreê°€ ?†ìœ¼ë©?Proxmox?ì„œ ê°€?¸ì????€??        if not db_datastores:
            logger.info("?”§ DB??datastore ?•ë³´ê°€ ?†ìŒ. Proxmox?ì„œ ê°€?¸ì????€??ì¤?..")
            
            # Proxmox?ì„œ datastore ëª©ë¡ ê°€?¸ì˜¤ê¸?            proxmox_service = ProxmoxService()
            proxmox_datastores = proxmox_service.get_datastores()
            
            # ?˜ê²½ë³€?˜ì—??ê¸°ë³¸ datastore ?¤ì • ê°€?¸ì˜¤ê¸?(ì´ˆê¸° ?¤ì •??
            def load_env_file():
                """?„ë¡œ?íŠ¸ ë£¨íŠ¸??.env ?Œì¼??ì§ì ‘ ?½ì–´???•ì…”?ˆë¦¬ë¡?ë°˜í™˜"""
                env_vars = {}
                try:
                    current_dir = os.path.dirname(os.path.abspath(__file__))
                    project_root = os.path.dirname(os.path.dirname(current_dir))
                    env_file = os.path.join(project_root, '.env')
                    
                    if os.path.exists(env_file):
                        with open(env_file, 'r', encoding='utf-8') as f:
                            for line in f:
                                line = line.strip()
                                if line and not line.startswith('#') and '=' in line:
                                    key, value = line.split('=', 1)
                                    env_vars[key.strip()] = value.strip()
                        logger.info(f"?”§ .env ?Œì¼ ë¡œë“œ ?±ê³µ: {env_file}")
                    else:
                        logger.warning(f"? ï¸ .env ?Œì¼??ì°¾ì„ ???†ìŠµ?ˆë‹¤: {env_file}")
                    
                    return env_vars
                except Exception as e:
                    logger.error(f"? ï¸ .env ?Œì¼ ?½ê¸° ?¤íŒ¨: {e}")
                    return {}
            
            env_vars = load_env_file()
            hdd_datastore = env_vars.get('PROXMOX_HDD_DATASTORE', 'local-lvm')
            ssd_datastore = env_vars.get('PROXMOX_SSD_DATASTORE', 'local')
            
            # Proxmox datastoreë¥?DB???€??            for datastore in proxmox_datastores:
                db_datastore = Datastore(
                    id=datastore['id'],
                    name=datastore['id'],
                    type=datastore.get('type', 'unknown'),
                    size=datastore.get('size', 0),
                    used=datastore.get('used', 0),
                    available=datastore.get('available', 0),
                    content=datastore.get('content', ''),
                    enabled=datastore.get('enabled', True),
                    is_default_hdd=datastore['id'] == hdd_datastore,
                    is_default_ssd=datastore['id'] == ssd_datastore
                )
                db.session.add(db_datastore)
        
            db.session.commit()
            logger.info(f"?”§ {len(proxmox_datastores)}ê°?datastoreë¥?DB???€???„ë£Œ")
        
        # ?€?¥ëœ datastore ?¤ì‹œ ì¡°íšŒ
        db_datastores = Datastore.query.filter_by(enabled=True).all()
        
        # DB?ì„œ ê¸°ë³¸ datastore ?¤ì • ê°€?¸ì˜¤ê¸?        def get_default_datastores():
            """DB?ì„œ ê¸°ë³¸ datastore ?¤ì •??ê°€?¸ì˜´"""
            try:
                # DB?ì„œ ê¸°ë³¸ HDD datastore ì¡°íšŒ
                default_hdd = Datastore.query.filter_by(is_default_hdd=True, enabled=True).first()
                # DB?ì„œ ê¸°ë³¸ SSD datastore ì¡°íšŒ
                default_ssd = Datastore.query.filter_by(is_default_ssd=True, enabled=True).first()
                
                hdd_datastore = default_hdd.id if default_hdd else 'local-lvm'
                ssd_datastore = default_ssd.id if default_ssd else 'local'
                
                logger.info(f"?”§ DB?ì„œ ê¸°ë³¸ datastore ?¤ì •: HDD={hdd_datastore}, SSD={ssd_datastore}")
                return hdd_datastore, ssd_datastore
            except Exception as e:
                logger.error(f"? ï¸ DB?ì„œ ê¸°ë³¸ datastore ?¤ì • ì¡°íšŒ ?¤íŒ¨: {e}")
                # .env ?Œì¼?ì„œ fallback
                return get_default_datastores_from_env()
        
        def get_default_datastores_from_env():
            """?˜ê²½ë³€?˜ì—??ê¸°ë³¸ datastore ?¤ì •??ê°€?¸ì˜´ (fallback)"""
            try:
                current_dir = os.path.dirname(os.path.abspath(__file__))
                project_root = os.path.dirname(os.path.dirname(current_dir))
                env_file = os.path.join(project_root, '.env')
                
                hdd_datastore = 'local-lvm'
                ssd_datastore = 'local'
                
                if os.path.exists(env_file):
                    with open(env_file, 'r', encoding='utf-8') as f:
                        for line in f:
                            line = line.strip()
                            if line and not line.startswith('#') and '=' in line:
                                key, value = line.split('=', 1)
                                if key.strip() == 'PROXMOX_HDD_DATASTORE':
                                    hdd_datastore = value.strip()
                                elif key.strip() == 'PROXMOX_SSD_DATASTORE':
                                    ssd_datastore = value.strip()
                
                logger.info(f"?”§ .env?ì„œ ê¸°ë³¸ datastore ?¤ì •: HDD={hdd_datastore}, SSD={ssd_datastore}")
                return hdd_datastore, ssd_datastore
            except Exception as e:
                logger.error(f"? ï¸ .env ?Œì¼ ?½ê¸° ?¤íŒ¨: {e}")
                return 'local-lvm', 'local'
        
        hdd_datastore, ssd_datastore = get_default_datastores()
        
        # DB datastoreë¥??¬ë§·??        formatted_datastores = []
        for datastore in db_datastores:
            formatted_datastores.append({
                'id': datastore.id,
                'name': datastore.name,
                'type': datastore.type,
                'size': datastore.size,
                'used': datastore.used,
                'available': datastore.available,
                'is_default_hdd': datastore.id == hdd_datastore,
                'is_default_ssd': datastore.id == ssd_datastore
            })
        
        return jsonify({
            'success': True,
            'datastores': formatted_datastores,
            'default_hdd': hdd_datastore,
            'default_ssd': ssd_datastore
        })
        
    except Exception as e:
        logger.error(f"Datastore ëª©ë¡ ì¡°íšŒ ?¤íŒ¨: {str(e)}")
        return jsonify({'error': str(e)}), 500

#@bp.route.*datastores/refresh', methods=['POST'])
@login_required
def refresh_datastores():
    """datastore ?•ë³´ ?ˆë¡œê³ ì¹¨ (Proxmox?ì„œ ?¤ì‹œ ê°€?¸ì???DB ?…ë°?´íŠ¸)"""
    try:
        from app.models.datastore import Datastore
        
        # ê¸°ì¡´ datastore ?•ë³´ ?? œ
        Datastore.query.delete()
        db.session.commit()
        logger.info("?”§ ê¸°ì¡´ datastore ?•ë³´ ?? œ ?„ë£Œ")
        
        # Proxmox?ì„œ datastore ëª©ë¡ ê°€?¸ì˜¤ê¸?        proxmox_service = ProxmoxService()
        proxmox_datastores = proxmox_service.get_datastores()
        
        # ?˜ê²½ë³€?˜ì—??ê¸°ë³¸ datastore ?¤ì • ê°€?¸ì˜¤ê¸?        def load_env_file():
            """?„ë¡œ?íŠ¸ ë£¨íŠ¸??.env ?Œì¼??ì§ì ‘ ?½ì–´???•ì…”?ˆë¦¬ë¡?ë°˜í™˜"""
            env_vars = {}
            try:
                current_dir = os.path.dirname(os.path.abspath(__file__))
                project_root = os.path.dirname(os.path.dirname(current_dir))
                env_file = os.path.join(project_root, '.env')
                
                if os.path.exists(env_file):
                    with open(env_file, 'r', encoding='utf-8') as f:
                        for line in f:
                            line = line.strip()
                            if line and not line.startswith('#') and '=' in line:
                                key, value = line.split('=', 1)
                                env_vars[key.strip()] = value.strip()
                    logger.info(f"?”§ .env ?Œì¼ ë¡œë“œ ?±ê³µ: {env_file}")
                else:
                    logger.warning(f"? ï¸ .env ?Œì¼??ì°¾ì„ ???†ìŠµ?ˆë‹¤: {env_file}")
                
                return env_vars
            except Exception as e:
                logger.error(f"? ï¸ .env ?Œì¼ ?½ê¸° ?¤íŒ¨: {e}")
                return {}
        
        env_vars = load_env_file()
        hdd_datastore = env_vars.get('PROXMOX_HDD_DATASTORE', 'local-lvm')
        ssd_datastore = env_vars.get('PROXMOX_SSD_DATASTORE', 'local')
        
        # Proxmox datastoreë¥?DB???€??        for datastore in proxmox_datastores:
            db_datastore = Datastore(
                id=datastore['id'],
                name=datastore['id'],
                type=datastore.get('type', 'unknown'),
                size=datastore.get('size', 0),
                used=datastore.get('used', 0),
                available=datastore.get('available', 0),
                content=datastore.get('content', ''),
                enabled=datastore.get('enabled', True),
                is_default_hdd=datastore['id'] == hdd_datastore,
                is_default_ssd=datastore['id'] == ssd_datastore
            )
            db.session.add(db_datastore)
        
        db.session.commit()
        logger.info(f"?”§ {len(proxmox_datastores)}ê°?datastoreë¥?DB???ˆë¡œ ?€???„ë£Œ")
        
        return jsonify({
            'success': True,
            'message': f'{len(proxmox_datastores)}ê°?datastore ?•ë³´ë¥??ˆë¡œê³ ì¹¨?ˆìŠµ?ˆë‹¤.',
            'count': len(proxmox_datastores)
        })
        
    except Exception as e:
        logger.error(f"Datastore ?ˆë¡œê³ ì¹¨ ?¤íŒ¨: {str(e)}")
        return jsonify({'error': str(e)}), 500

#@bp.route.*datastores/default', methods=['POST'])
@login_required
def set_default_datastores():
    """ê¸°ë³¸ datastore ?¤ì • ë³€ê²?""
    try:
        from app.models.datastore import Datastore
        
        data = request.get_json()
        hdd_datastore_id = data.get('hdd_datastore_id')
        ssd_datastore_id = data.get('ssd_datastore_id')
        
        if not hdd_datastore_id or not ssd_datastore_id:
            return jsonify({'error': 'HDD?€ SSD datastore IDê°€ ?„ìš”?©ë‹ˆ??'}), 400
        
        # ê¸°ì¡´ ê¸°ë³¸ ?¤ì • ?´ì œ
        Datastore.query.filter_by(is_default_hdd=True).update({'is_default_hdd': False})
        Datastore.query.filter_by(is_default_ssd=True).update({'is_default_ssd': False})
        
        # ?ˆë¡œ??ê¸°ë³¸ ?¤ì •
        hdd_datastore = Datastore.query.filter_by(id=hdd_datastore_id).first()
        ssd_datastore = Datastore.query.filter_by(id=ssd_datastore_id).first()
        
        if not hdd_datastore:
            return jsonify({'error': f'HDD datastoreë¥?ì°¾ì„ ???†ìŠµ?ˆë‹¤: {hdd_datastore_id}'}), 404
        if not ssd_datastore:
            return jsonify({'error': f'SSD datastoreë¥?ì°¾ì„ ???†ìŠµ?ˆë‹¤: {ssd_datastore_id}'}), 404
        
        hdd_datastore.is_default_hdd = True
        ssd_datastore.is_default_ssd = True
        
        db.session.commit()
        
        logger.info(f"?”§ ê¸°ë³¸ datastore ?¤ì • ë³€ê²? HDD={hdd_datastore_id}, SSD={ssd_datastore_id}")
        
        return jsonify({
            'success': True, 
            'message': 'ê¸°ë³¸ datastore ?¤ì •??ë³€ê²½ë˜?ˆìŠµ?ˆë‹¤.',
            'hdd_datastore': hdd_datastore_id,
            'ssd_datastore': ssd_datastore_id
        })
        
    except Exception as e:
        logger.error(f"ê¸°ë³¸ datastore ?¤ì • ë³€ê²??¤íŒ¨: {str(e)}")
        return jsonify({'error': str(e)}), 500    
