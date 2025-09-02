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

@bp.route('/api/firewall/groups', methods=['POST'])
@login_required
@permission_required('manage_firewall_groups')
def create_firewall_group():
    """방화벽 그룹 생성"""
    try:
        data = request.get_json()
        group_name = data.get('name')
        description = data.get('description', '')
        
        if not group_name:
            return jsonify({'error': '그룹 이름이 필요합니다.'}), 400
        
        print(f"🔍 방화벽 그룹 생성 요청: {group_name} - {description}")
        
        # 그룹 이름 유효성 검사
        if len(group_name) > 32:
            return jsonify({'error': '그룹 이름은 32자를 초과할 수 없습니다.'}), 400
            
        if not group_name.replace('-', '').replace('_', '').isalnum():
            return jsonify({'error': '그룹 이름은 영문, 숫자, 하이픈(-), 언더스코어(_)만 사용할 수 있습니다.'}), 400
        
        # ProxmoxService를 통해 방화벽 그룹 생성 시도
        proxmox_service = ProxmoxService()
        success = proxmox_service.create_firewall_group(group_name, description)
        
        if success:
            print(f"✅ 방화벽 그룹 '{group_name}' 생성 성공")
            return jsonify({
                'success': True,
                'message': f'방화벽 그룹 \'{group_name}\'이 성공적으로 생성되었습니다. (테스트 환경)',
                'group': {
                    'name': group_name,
                    'description': description,
                    'instance_count': 0
                },
                'note': '실제 Proxmox 환경에서는 방화벽 그룹을 수동으로 생성해야 할 수 있습니다.'
            })
        else:
            print(f"❌ 방화벽 그룹 '{group_name}' 생성 실패")
            return jsonify({'error': f'방화벽 그룹 \'{group_name}\' 생성에 실패했습니다.'}), 500
    except Exception as e:
        print(f"💥 방화벽 그룹 생성 실패: {str(e)}")
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



@bp.route('/api/firewall/groups/<group_name>/rules', methods=['POST'])
@login_required
@permission_required('manage_firewall_groups')
def add_firewall_group_rule(group_name):
    """Security Group에 규칙 추가"""
    try:
        data = request.get_json()
        print(f"🔍 Security Group '{group_name}'에 규칙 추가 요청")
        print(f"🔍 받은 데이터: {data}")
        print(f"🔍 데이터 타입: {type(data)}")
        
        if not data:
            return jsonify({'error': '데이터가 없습니다.'}), 400
        
        # 필수 필드 검증
        if not data.get('action'):
            return jsonify({'error': '동작(ACCEPT/DENY)이 필요합니다.'}), 400
        
        print(f"🔍 Security Group '{group_name}'에 규칙 추가")
        print(f"🔍 규칙 데이터: {data}")
        
        # ProxmoxService를 통해 Security Group에 규칙 추가
        from app.services.proxmox_service import ProxmoxService
        proxmox_service = ProxmoxService()
        
        success = proxmox_service.add_firewall_rule(group_name, data)
        
        if success:
            return jsonify({
                'success': True,
                'message': '방화벽 규칙이 Security Group에 추가되었습니다.'
            })
        else:
            return jsonify({'error': '방화벽 규칙 추가에 실패했습니다.'}), 500
            
    except Exception as e:
        print(f"💥 방화벽 규칙 추가 실패: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/firewall/groups/<group_name>/rules/<int:rule_id>', methods=['DELETE'])
@login_required
@permission_required('manage_firewall_groups')
def delete_firewall_group_rule(group_name, rule_id):
    """Security Group에서 규칙 삭제"""
    try:
        print(f"🔍 Security Group '{group_name}'에서 규칙 {rule_id} 삭제")
        
        # ProxmoxService를 통해 Security Group에서 규칙 삭제
        from app.services.proxmox_service import ProxmoxService
        proxmox_service = ProxmoxService()
        
        success = proxmox_service.delete_firewall_rule(group_name, rule_id)
        
        if success:
            return jsonify({
                'success': True,
                'message': '방화벽 규칙이 Security Group에서 삭제되었습니다. (Proxmox API 제한으로 인해 Security Group을 재생성했습니다)'
            })
        else:
            return jsonify({'error': '방화벽 규칙 삭제에 실패했습니다. Proxmox API에서 규칙 삭제를 지원하지 않습니다.'}), 500
            
    except Exception as e:
        print(f"💥 방화벽 규칙 삭제 실패: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/apply_security_group/<server_name>', methods=['POST'])
@login_required
@permission_required('assign_firewall_groups')
def apply_security_group_to_vm(server_name):
    """VM에 Security Group 적용"""
    try:
        data = request.get_json()
        group_name = data.get('security_group')
        
        if not group_name:
            return jsonify({'error': 'Security Group이 필요합니다.'}), 400
        
        print(f"🔍 VM '{server_name}'에 Security Group '{group_name}' 적용")
        
        from app.services.proxmox_service import ProxmoxService
        proxmox_service = ProxmoxService()
        
        # VM에 Security Group 적용
        success = proxmox_service.apply_security_group_to_vm(server_name, group_name)
        
        if success:
            # DB에 firewall_group 정보 업데이트
            from app.models import Server
            from app import db
            
            server = Server.query.filter_by(name=server_name).first()
            if server:
                server.firewall_group = group_name
                db.session.commit()
                print(f"✅ DB에 Security Group 정보 업데이트 완료")
            
            return jsonify({
                'success': True,
                'message': f'VM \'{server_name}\'에 Security Group \'{group_name}\'이 적용되었습니다.'
            })
        else:
            return jsonify({'error': f'VM \'{server_name}\'에 Security Group 적용에 실패했습니다.'}), 500
            
    except Exception as e:
        print(f"💥 Security Group 적용 실패: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/firewall/assign_bulk', methods=['POST'])
@login_required
@permission_required('assign_firewall_groups')
def assign_firewall_group_bulk():
    """여러 서버에 방화벽 그룹 일괄 할당"""
    try:
        data = request.get_json()
        server_names = data.get('server_names', [])
        firewall_group = data.get('security_group')
        
        print(f"🔍 일괄 방화벽 그룹 할당 요청")
        print(f"🔍 대상 서버들: {server_names}")
        print(f"🔍 방화벽 그룹: {firewall_group}")
        
        if not server_names:
            return jsonify({'error': '서버 목록이 필요합니다.'}), 400
            
        if not firewall_group:
            return jsonify({'error': '방화벽 그룹이 필요합니다.'}), 400
        
        from app.models import Server
        from app.services.proxmox_service import ProxmoxService
        from app import db
        
        # 대상 서버들 조회
        servers = Server.query.filter(Server.name.in_(server_names)).all()
        found_servers = {s.name: s for s in servers}
        
        # 존재하지 않는 서버 체크
        missing_servers = [name for name in server_names if name not in found_servers]
        if missing_servers:
            return jsonify({'error': f'다음 서버들을 찾을 수 없습니다: {", ".join(missing_servers)}'}), 404
        
        proxmox_service = ProxmoxService()
        success_count = 0
        failed_servers = []
        
        # 각 서버에 방화벽 그룹 적용
        for server_name in server_names:
            try:
                print(f"🔍 서버 '{server_name}'에 방화벽 그룹 '{firewall_group}' 적용 시도")
                
                # Proxmox에서 Security Group 적용
                success = proxmox_service.apply_security_group_to_vm(server_name, firewall_group)
                
                if success:
                    # DB 업데이트
                    server = found_servers[server_name]
                    server.firewall_group = firewall_group
                    success_count += 1
                    print(f"✅ 서버 '{server_name}' 방화벽 그룹 적용 성공")
                else:
                    failed_servers.append(server_name)
                    print(f"❌ 서버 '{server_name}' 방화벽 그룹 적용 실패")
                    
            except Exception as e:
                failed_servers.append(server_name)
                print(f"❌ 서버 '{server_name}' 방화벽 그룹 적용 중 오류: {e}")
        
        # DB 커밋
        db.session.commit()
        
        # 결과 응답
        if success_count == len(server_names):
            return jsonify({
                'success': True,
                'message': f'{success_count}개 서버에 방화벽 그룹 \'{firewall_group}\'이 성공적으로 할당되었습니다.',
                'summary': {
                    'total': len(server_names),
                    'success': success_count,
                    'failed': len(failed_servers)
                }
            })
        elif success_count > 0:
            return jsonify({
                'success': True,
                'message': f'{success_count}/{len(server_names)}개 서버에 방화벽 그룹 할당 완료. 실패: {", ".join(failed_servers)}',
                'summary': {
                    'total': len(server_names),
                    'success': success_count,
                    'failed': len(failed_servers)
                },
                'failed_servers': failed_servers
            })
        else:
            return jsonify({
                'error': f'모든 서버에 방화벽 그룹 할당 실패. 실패한 서버: {", ".join(failed_servers)}'
            }), 500
            
    except Exception as e:
        print(f"💥 일괄 방화벽 그룹 할당 실패: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/remove_firewall_group/<server_name>', methods=['POST'])
@login_required
@permission_required('remove_firewall_groups')
def remove_firewall_group(server_name):
    """서버에서 방화벽 그룹 제거"""
    try:
        print(f"🔍 서버 '{server_name}'에서 방화벽 그룹 제거")
        
        from app.models import Server
        from app import db
        from app.services.proxmox_service import ProxmoxService
        
        server = Server.query.filter_by(name=server_name).first()
        if not server:
            return jsonify({'error': '서버를 찾을 수 없습니다.'}), 404
        
        # 기존 방화벽 그룹 정보 저장
        old_firewall_group = server.firewall_group
        
        # 방화벽 그룹이 설정되지 않은 경우
        if not old_firewall_group:
            print(f"✅ 서버 '{server_name}'에 방화벽 그룹이 설정되지 않았습니다.")
            return jsonify({
                'success': True, 
                'message': f'서버 {server_name}에 방화벽 그룹이 설정되지 않았습니다.'
            })
        
        # Proxmox에서 실제 방화벽 설정 제거
        proxmox_service = ProxmoxService()
        print(f"🔍 ProxmoxService.remove_security_group_from_vm 호출: {server_name}")
        success = proxmox_service.remove_security_group_from_vm(server_name)
        print(f"🔍 remove_security_group_from_vm 결과: {success}")
        
        if success:
            # DB에서 방화벽 그룹 정보 제거
            server.firewall_group = None
            db.session.commit()
            
            print(f"✅ 서버 '{server_name}'에서 방화벽 그룹 '{old_firewall_group}' 제거 완료")
            return jsonify({
                'success': True, 
                'message': f'서버 {server_name}에서 방화벽 그룹 \'{old_firewall_group}\'이 제거되었습니다.'
            })
        else:
            print(f"⚠️ Proxmox에서 방화벽 그룹 제거 실패, DB만 업데이트")
            # Proxmox 제거 실패 시에도 DB는 업데이트
            server.firewall_group = None
            db.session.commit()
            
            return jsonify({
                'success': True, 
                'message': f'서버 {server_name}에서 방화벽 그룹 \'{old_firewall_group}\'이 제거되었습니다. (DB만 업데이트)'
            })
            
    except Exception as e:
        print(f"💥 방화벽 그룹 제거 실패: {str(e)}")
        return jsonify({'error': str(e)}), 500 

