#!/usr/bin/env python3
"""
기존 서버들의 OS 정보를 Rocky Linux로 업데이트
"""

import sqlite3
import os

def update_server_os():
    """기존 서버들의 OS 정보를 Rocky Linux로 업데이트"""
    
    # DB 파일 경로
    db_path = 'instance/kproxmox_manager.db'
    
    if not os.path.exists(db_path):
        print(f"❌ DB 파일을 찾을 수 없습니다: {db_path}")
        return
    
    try:
        # DB 연결
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 현재 서버 목록 조회
        cursor.execute("SELECT name, os_type FROM servers")
        servers = cursor.fetchall()
        
        print(f"🔍 현재 서버 목록 ({len(servers)}개):")
        for server in servers:
            print(f"  - {server[0]}: {server[1] or 'None'}")
        
        # OS 정보가 None이거나 비어있는 서버들을 Rocky Linux로 업데이트
        update_count = 0
        for server in servers:
            if not server[1] or server[1] == '':
                cursor.execute(
                    "UPDATE servers SET os_type = 'rocky' WHERE name = ?",
                    (server[0],)
                )
                update_count += 1
                print(f"✅ {server[0]}: rocky로 업데이트")
        
        # 변경사항 저장
        conn.commit()
        
        print(f"\n📊 업데이트 완료: {update_count}개 서버")
        
        # 업데이트 후 확인
        cursor.execute("SELECT name, os_type FROM servers")
        updated_servers = cursor.fetchall()
        
        print(f"\n🔍 업데이트 후 서버 목록:")
        for server in updated_servers:
            print(f"  - {server[0]}: {server[1]}")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ 업데이트 실패: {e}")

if __name__ == '__main__':
    update_server_os()
