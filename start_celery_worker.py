#!/usr/bin/env python3
"""
Celery 워커 시작 스크립트
환경변수를 로드한 후 Celery 워커를 시작합니다.
"""
import os
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv('/app/.env')

# 환경변수 확인
print("🔧 환경변수 로드 완료")
print(f"VAULT_ADDR: {os.getenv('VAULT_ADDR')}")
print(f"TF_VAR_vault_token: {os.getenv('TF_VAR_vault_token')}")
print(f"TF_VAR_vault_address: {os.getenv('TF_VAR_vault_address')}")

# Celery 워커 시작
if __name__ == '__main__':
    from celery import Celery
    from app.celery_app import celery_app
    
    print("🚀 Celery 워커 시작...")
    celery_app.worker_main(['worker', '--loglevel=info', '--concurrency=2'])
