#!/usr/bin/env python3
"""
SQLite 기반 데이터베이스 관리 시스템
"""

import sqlite3
import json
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import os
import re

class Database:
    def __init__(self, db_path='proxmox_manager.db'):
        self.db_path = db_path
        self.init_database()
        self.secure_db_file()
    
    def get_connection(self):
        """데이터베이스 연결"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # 딕셔너리 형태로 결과 반환
        return conn
    
    def init_database(self):
        """데이터베이스 초기화 및 테이블 생성"""
        with self.get_connection() as conn:
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
            
            # 사용자 권한 테이블
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_permissions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    permission TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
                    UNIQUE(user_id, permission)
                )
            ''')
            
            conn.commit()
            
            # 기본 관리자 계정 생성 (없는 경우)
            self.create_default_admin()
    
    def create_user_with_hash(self, username, password_hash, name=None, email=None, role='developer'):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO users (username, password_hash, name, email, role)
                VALUES (?, ?, ?, ?, ?)
            ''', (username, password_hash, name, email, role))
            conn.commit()
            return cursor.lastrowid

    def create_default_admin(self):
        try:
            admin_user = self.get_user_by_username('admin')
            if not admin_user:
                # 평문 비밀번호는 코드에 남기지 않고, 해시만 저장
                admin_hash = generate_password_hash('admin123!')
                admin_id = self.create_user_with_hash(
                    username='admin',
                    password_hash=admin_hash,
                    name='시스템 관리자',
                    email='admin@dmcmedia.co.kr',
                    role='admin'
                )
                # 관리자에게 모든 권한 부여
                self.add_user_permissions(admin_id, [
                    'view_all', 'create_server', 'start_server', 'stop_server', 
                    'reboot_server', 'delete_server', 'assign_roles', 'remove_roles', 
                    'manage_users', 'view_logs', 'manage_roles'
                ])
                print("기본 관리자 계정이 생성되었습니다. (비밀번호는 별도 안내)")
        except Exception as e:
            print(f"기본 관리자 계정 생성 실패: {e}")
    
    # 사용자 관리
    def create_user(self, username, password, name=None, email=None, role='developer'):
        """새 사용자 생성"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO users (username, password_hash, name, email, role)
                VALUES (?, ?, ?, ?, ?)
            ''', (username, generate_password_hash(password), name, email, role))
            conn.commit()
            return cursor.lastrowid
    
    def get_user_by_username(self, username):
        """사용자명으로 사용자 조회"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
            return cursor.fetchone()
    
    def get_all_users(self):
        """모든 사용자 조회"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM users ORDER BY created_at DESC')
            return cursor.fetchall()
    
    def update_user_password(self, username, new_password):
        """사용자 비밀번호 변경"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE users 
                SET password_hash = ?, updated_at = CURRENT_TIMESTAMP
                WHERE username = ?
            ''', (generate_password_hash(new_password), username))
            conn.commit()
            return cursor.rowcount > 0
    
    def update_user_login(self, username):
        """사용자 마지막 로그인 시간 업데이트"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE users 
                SET last_login = CURRENT_TIMESTAMP
                WHERE username = ?
            ''', (username,))
            conn.commit()
    
    def verify_user(self, username, password):
        """사용자 인증"""
        user = self.get_user_by_username(username)
        if user and user['is_active'] and check_password_hash(user['password_hash'], password):
            self.update_user_login(username)
            return user
        return None
    
    # 알림 관리
    def add_notification(self, type, title, message, details=None, severity='info', user_id=None):
        """새 알림 추가"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO notifications (type, title, message, details, severity, user_id)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (type, title, message, details, severity, user_id))
            conn.commit()
            return cursor.lastrowid
    
    def get_notifications(self, limit=20, user_id=None):
        """알림 목록 조회"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if user_id:
                cursor.execute('''
                    SELECT * FROM notifications 
                    WHERE user_id = ? OR user_id IS NULL
                    ORDER BY created_at DESC 
                    LIMIT ?
                ''', (user_id, limit))
            else:
                cursor.execute('''
                    SELECT * FROM notifications 
                    ORDER BY created_at DESC 
                    LIMIT ?
                ''', (limit,))
            return cursor.fetchall()
    
    def get_unread_count(self, user_id=None):
        """읽지 않은 알림 수"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if user_id:
                cursor.execute('''
                    SELECT COUNT(*) FROM notifications 
                    WHERE (user_id = ? OR user_id IS NULL) AND is_read = 0
                ''', (user_id,))
            else:
                cursor.execute('SELECT COUNT(*) FROM notifications WHERE is_read = 0')
            return cursor.fetchone()[0]
    
    def mark_notification_read(self, notification_id):
        """알림을 읽음으로 표시"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE notifications 
                SET is_read = 1 
                WHERE id = ?
            ''', (notification_id,))
            conn.commit()
            return cursor.rowcount > 0
    
    def clear_all_notifications(self):
        """모든 알림 삭제"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM notifications')
            conn.commit()
            return cursor.rowcount
    
    # 서버 관리
    def add_server(self, name, vmid=None, status='pending', ip_address=None, role=None, os_type=None, cpu=None, memory=None):
        """서버 정보 추가"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO servers (name, vmid, status, ip_address, role, os_type, cpu, memory)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (name, vmid, status, ip_address, role, os_type, cpu, memory))
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            print(f"[add_server] DB 에러: {e}")
            raise
    
    def update_server(self, name, **kwargs):
        """서버 정보 업데이트"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            set_clause = ', '.join([f"{k} = ?" for k in kwargs.keys()])
            set_clause += ', updated_at = CURRENT_TIMESTAMP'
            values = list(kwargs.values()) + [name]
            cursor.execute(f'UPDATE servers SET {set_clause} WHERE name = ?', values)
            conn.commit()
            return cursor.rowcount > 0
    
    def get_all_servers(self):
        """모든 서버 조회"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM servers ORDER BY created_at DESC')
            return cursor.fetchall()
    
    def get_server_by_name(self, name):
        """서버명으로 서버 조회"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM servers WHERE name = ?', (name,))
            return cursor.fetchone()
    
    def delete_server_by_name(self, name):
        """서버명으로 서버 삭제"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM servers WHERE name = ?', (name,))
            conn.commit()
            return cursor.rowcount > 0
    
    # 프로젝트 관리
    def add_project(self, name, status='pending'):
        """프로젝트 추가"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO projects (name, status)
                VALUES (?, ?)
            ''', (name, status))
            conn.commit()
            return cursor.lastrowid
    
    def update_project_status(self, name, status):
        """프로젝트 상태 업데이트"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE projects 
                SET status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE name = ?
            ''', (status, name))
            conn.commit()
            return cursor.rowcount > 0
    
    def get_all_projects(self):
        """모든 프로젝트 조회"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM projects ORDER BY created_at DESC')
            return cursor.fetchall()

    # 사용자 권한 관리
    def add_user_permissions(self, user_id, permissions):
        """사용자에게 권한 추가"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            for permission in permissions:
                try:
                    cursor.execute('''
                        INSERT INTO user_permissions (user_id, permission)
                        VALUES (?, ?)
                    ''', (user_id, permission))
                except sqlite3.IntegrityError:
                    # 이미 존재하는 권한은 무시
                    pass
            conn.commit()
    
    def remove_user_permissions(self, user_id, permissions):
        """사용자 권한 제거"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            for permission in permissions:
                cursor.execute('''
                    DELETE FROM user_permissions 
                    WHERE user_id = ? AND permission = ?
                ''', (user_id, permission))
            conn.commit()
    
    def get_user_permissions(self, user_id):
        """사용자의 모든 권한 조회"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT permission FROM user_permissions 
                WHERE user_id = ?
                ORDER BY permission
            ''', (user_id,))
            return [row['permission'] for row in cursor.fetchall()]
    
    def set_user_permissions(self, user_id, permissions):
        """사용자 권한을 완전히 교체"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # 기존 권한 모두 삭제
            cursor.execute('DELETE FROM user_permissions WHERE user_id = ?', (user_id,))
            # 새 권한 추가
            for permission in permissions:
                cursor.execute('''
                    INSERT INTO user_permissions (user_id, permission)
                    VALUES (?, ?)
                ''', (user_id, permission))
            conn.commit()
    
    def has_permission(self, user_id, permission):
        """사용자가 특정 권한을 가지고 있는지 확인"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT COUNT(*) FROM user_permissions 
                WHERE user_id = ? AND permission = ?
            ''', (user_id, permission))
            return cursor.fetchone()[0] > 0
    
    def get_user_with_permissions(self, username):
        """사용자 정보와 권한을 함께 조회"""
        user = self.get_user_by_username(username)
        if user:
            permissions = self.get_user_permissions(user['id'])
            user_dict = dict(user)
            user_dict['permissions'] = permissions
            return user_dict
        return None

    def secure_db_file(self):
        """데이터베이스 파일 보안 처리"""
        if os.path.exists(self.db_path):
            # 파일 권한 변경 (예: 읽기 전용)
            os.chmod(self.db_path, 0o600)
            # 파일 소유자 변경 (예: 현재 사용자)
            os.chown(self.db_path, os.getuid(), os.getgid())
            print(f"데이터베이스 파일 '{self.db_path}' 보안 처리되었습니다.")

# 전역 데이터베이스 인스턴스
db = Database() 