#!/usr/bin/env python3
"""
admin 사용자 비밀번호 및 권한 수정 스크립트 (일회용)
"""

from database import db
from werkzeug.security import check_password_hash, generate_password_hash

# 모든 권한 목록
PERMISSION_LIST = [
    'view_all', 'create_server', 'start_server', 'stop_server', 'reboot_server', 
    'delete_server', 'assign_roles', 'remove_roles', 'manage_users', 'view_logs', 
    'manage_roles', 'manage_storage', 'manage_network'
]

def fix_admin_user():
    """admin 사용자의 비밀번호와 권한을 수정"""
    
    print("🔧 admin 사용자 수정 시작...")
    
    # 1. admin 사용자 확인
    admin_user = db.get_user_by_username('admin')
    if not admin_user:
        print("❌ admin 사용자를 찾을 수 없습니다.")
        return
    
    print(f"✅ admin 사용자 발견: ID={admin_user['id']}")
    
    # 2. 비밀번호 확인 및 수정
    test_password = 'admin123!'
    if not check_password_hash(admin_user['password_hash'], test_password):
        print("🔑 admin 사용자 비밀번호를 admin123!로 업데이트합니다...")
        db.update_user_password('admin', test_password)
        print("✅ 비밀번호 업데이트 완료")
    else:
        print("✅ 비밀번호가 이미 올바르게 설정되어 있습니다.")
    
    # 3. 권한 확인 및 수정
    admin_permissions = db.get_user_permissions(admin_user['id'])
    all_permissions = set(PERMISSION_LIST)
    current_permissions = set(admin_permissions)
    
    print(f"📋 현재 권한: {sorted(current_permissions)}")
    print(f"📋 필요한 권한: {sorted(all_permissions)}")
    
    # 누락된 권한이 있으면 추가
    missing_permissions = all_permissions - current_permissions
    if missing_permissions:
        print(f"🔧 누락된 권한 추가: {sorted(missing_permissions)}")
        db.add_user_permissions(admin_user['id'], list(missing_permissions))
        print("✅ 권한 추가 완료")
    else:
        print("✅ 모든 권한이 이미 부여되어 있습니다.")
    
    # 4. 최종 확인
    final_permissions = db.get_user_permissions(admin_user['id'])
    print(f"🎯 최종 권한 목록: {sorted(final_permissions)}")
    
    print("🎉 admin 사용자 수정 완료!")

if __name__ == "__main__":
    fix_admin_user() 