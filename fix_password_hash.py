#!/usr/bin/env python3
"""
비밀번호 해시 수정 스크립트
"""

import sqlite3
from werkzeug.security import generate_password_hash

def fix_password_hashes():
    """비밀번호 해시를 현재 지원되는 형식으로 수정"""
    db_path = 'instance/proxmox_manager.db'
    
    print(f"🔧 비밀번호 해시 수정 시작: {db_path}")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 현재 사용자들의 비밀번호 해시 확인
        cursor.execute("SELECT id, username, password_hash FROM users")
        users = cursor.fetchall()
        
        print(f"📋 사용자 수: {len(users)}")
        
        for user_id, username, password_hash in users:
            print(f"🔍 사용자: {username}")
            print(f"  기존 해시: {password_hash}")
            
            # scrypt 해시인 경우 새로운 해시로 변경
            if password_hash and 'scrypt:' in password_hash:
                print(f"  ⚠️ scrypt 해시 발견, 새로운 해시로 변경")
                
                # admin 사용자는 'admin123!'로, 다른 사용자는 'password'로 설정
                if username == 'admin':
                    new_password = 'admin123!'
                else:
                    new_password = 'password'
                
                new_hash = generate_password_hash(new_password)
                print(f"  새 해시: {new_hash}")
                
                cursor.execute(
                    "UPDATE users SET password_hash = ? WHERE id = ?",
                    (new_hash, user_id)
                )
                print(f"  ✅ 비밀번호 해시 업데이트 완료")
            else:
                print(f"  ✅ 기존 해시 유지")
        
        conn.commit()
        print("✅ 모든 비밀번호 해시 수정 완료")
        
        # 수정된 사용자 정보 확인
        cursor.execute("SELECT username, password_hash FROM users")
        updated_users = cursor.fetchall()
        
        print(f"\n📋 수정된 사용자 정보:")
        for username, password_hash in updated_users:
            print(f"  - {username}: {password_hash[:50]}...")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ 비밀번호 해시 수정 실패: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    fix_password_hashes() 