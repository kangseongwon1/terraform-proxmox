import sqlite3

def create_tables():
    """proxmox.db에 필요한 테이블들을 생성합니다."""
    try:
        conn = sqlite3.connect('proxmox.db')
        cursor = conn.cursor()
        
        # 사용자 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                name TEXT,
                email TEXT,
                role TEXT DEFAULT 'developer',
                is_active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 알림 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL,
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                details TEXT,
                severity TEXT DEFAULT 'info',
                user_id TEXT,
                is_read BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 서버 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS servers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                vmid INTEGER,
                status TEXT,
                ip_address TEXT,
                role TEXT,
                firewall_group TEXT,
                os_type TEXT,
                cpu INTEGER,
                memory INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 프로젝트 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 기본 관리자 사용자 생성
        cursor.execute('''
            INSERT OR IGNORE INTO users (username, password_hash, name, email, role, is_active)
            VALUES ('admin', 'pbkdf2:sha256:600000$admin123!', 'Administrator', 'admin@example.com', 'admin', 1)
        ''')
        
        # 샘플 서버 데이터 추가
        sample_servers = [
            ('web-server-01', 100, 'running', '192.168.1.100', 'web', 'web-group', 'ubuntu', 2, 4096),
            ('db-server-01', 101, 'stopped', '192.168.1.101', 'database', 'db-group', 'centos', 4, 8192),
            ('app-server-01', 102, 'running', '192.168.1.102', 'application', 'app-group', 'ubuntu', 2, 4096)
        ]
        
        for server in sample_servers:
            cursor.execute('''
                INSERT OR IGNORE INTO servers 
                (name, vmid, status, ip_address, role, firewall_group, os_type, cpu, memory)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', server)
        
        # 샘플 알림 데이터 추가
        sample_notifications = [
            ('server', '서버 시작', 'web-server-01이 성공적으로 시작되었습니다.', None, 'success', None),
            ('system', '시스템 업데이트', '새로운 보안 패치가 적용되었습니다.', None, 'info', None),
            ('user', '사용자 로그인', '관리자가 시스템에 로그인했습니다.', None, 'info', 'admin')
        ]
        
        for notification in sample_notifications:
            cursor.execute('''
                INSERT OR IGNORE INTO notifications 
                (type, title, message, details, severity, user_id)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', notification)
        
        conn.commit()
        print("✅ 테이블 생성 및 샘플 데이터 추가 완료!")
        
        # 생성된 데이터 확인
        cursor.execute("SELECT COUNT(*) FROM users")
        user_count = cursor.fetchone()[0]
        print(f"👥 사용자 수: {user_count}")
        
        cursor.execute("SELECT COUNT(*) FROM servers")
        server_count = cursor.fetchone()[0]
        print(f"🖥️ 서버 수: {server_count}")
        
        cursor.execute("SELECT COUNT(*) FROM notifications")
        notification_count = cursor.fetchone()[0]
        print(f"🔔 알림 수: {notification_count}")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ 테이블 생성 실패: {e}")

if __name__ == "__main__":
    create_tables() 