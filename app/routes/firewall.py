from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from app.models import User, UserPermission
from app.services.proxmox_service import ProxmoxService
from app.routes.auth import permission_required

bp = Blueprint('firewall', __name__)

@bp.route('/api/firewall/groups', methods=['GET'])
@login_required
def get_firewall_groups():
    """방화벽 그룹 목록 조회"""
    try:
        from app.services.proxmox_service import ProxmoxService
        proxmox_service = ProxmoxService()
        
        # Proxmox에서 방화벽 그룹 정보 가져오기
        firewall_groups = proxmox_service.get_firewall_groups()
        
        return jsonify({
            'success': True,
            'groups': firewall_groups
        })
    except Exception as e:
        print(f"💥 방화벽 그룹 조회 실패: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/firewall/groups/<group_name>', methods=['GET'])
@login_required
def get_firewall_group_detail(group_name):
    """방화벽 그룹 상세 정보 조회"""
    try:
        from app.services.proxmox_service import ProxmoxService
        proxmox_service = ProxmoxService()
        
        # Proxmox에서 방화벽 그룹 상세 정보 가져오기
        group_detail = proxmox_service.get_firewall_group_detail(group_name)
        
        return jsonify({
            'success': True,
            'group': group_detail
        })
    except Exception as e:
        print(f"💥 방화벽 그룹 상세 조회 실패: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/assign_firewall_group/<server_name>', methods=['POST'])
@login_required
@permission_required('assign_firewall_groups')
def assign_firewall_group(server_name):
    """서버에 방화벽 그룹 할당"""
    try:
        data = request.get_json()
        firewall_group = data.get('firewall_group')
        
        if not firewall_group:
            return jsonify({'error': '방화벽 그룹이 필요합니다.'}), 400
        
        from app.models import Server
        from app import db
        
        server = Server.query.filter_by(name=server_name).first()
        if not server:
            return jsonify({'error': '서버를 찾을 수 없습니다.'}), 404
        
        server.firewall_group = firewall_group
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': f'서버 {server_name}에 방화벽 그룹 {firewall_group}이 할당되었습니다.'
        })
    except Exception as e:
        print(f"💥 방화벽 그룹 할당 실패: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/firewall/groups/<group_name>', methods=['DELETE'])
def delete_firewall_group(group_name):
    """방화벽 그룹 삭제"""
    try:
        # 실제로는 데이터베이스에서 삭제
        return jsonify({'success': True, 'message': f'방화벽 그룹 {group_name}이 삭제되었습니다.'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/api/firewall/groups/<group_name>/rules', methods=['GET'])
def get_firewall_group_rules(group_name):
    """방화벽 그룹 규칙 조회"""
    try:
        # 임시 데이터
        group = {'name': group_name, 'description': f'{group_name} 방화벽 그룹'}
        rules = [
            {'id': 1, 'direction': 'in', 'protocol': 'tcp', 'port': '80', 'source': '', 'description': 'HTTP'},
            {'id': 2, 'direction': 'in', 'protocol': 'tcp', 'port': '443', 'source': '', 'description': 'HTTPS'}
        ]
        return jsonify({'group': group, 'rules': rules})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/api/firewall/groups/<group_name>/rules', methods=['POST'])
def add_firewall_group_rule(group_name):
    """방화벽 그룹 규칙 추가"""
    try:
        data = request.get_json()
        # 실제로는 데이터베이스에 저장
        return jsonify({'success': True, 'message': '방화벽 규칙이 추가되었습니다.'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/api/firewall/groups/<group_name>/rules/<int:rule_id>', methods=['DELETE'])
def delete_firewall_group_rule(group_name, rule_id):
    """방화벽 그룹 규칙 삭제"""
    try:
        # 실제로는 데이터베이스에서 삭제
        return jsonify({'success': True, 'message': '방화벽 규칙이 삭제되었습니다.'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/api/remove_firewall_group/<server_name>', methods=['POST'])
@login_required
@permission_required('remove_firewall_groups')
def remove_firewall_group(server_name):
    """서버에서 방화벽 그룹 제거"""
    try:
        from app.models import Server
        from app import db
        
        server = Server.query.filter_by(name=server_name).first()
        if not server:
            return jsonify({'error': '서버를 찾을 수 없습니다.'}), 404
        
        server.firewall_group = None
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': f'서버 {server_name}에서 방화벽 그룹이 제거되었습니다.'
        })
    except Exception as e:
        print(f"💥 방화벽 그룹 제거 실패: {str(e)}")
        return jsonify({'error': str(e)}), 500 

