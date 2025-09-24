"""
Celery 애플리케이션 설정
"""
from celery import Celery
import os

def create_celery_app():
    """Celery 애플리케이션 생성"""
    
    # Redis 브로커 설정
    broker_url = f"redis://{os.getenv('REDIS_HOST', 'localhost')}:{os.getenv('REDIS_PORT', 6379)}/{os.getenv('REDIS_DB', 0)}"
    
    celery = Celery(
        'proxmox_manager',
        broker=broker_url,
        backend=broker_url,
        include=['app.tasks.server_tasks']
    )
    
    # Celery 설정
    celery.conf.update(
        task_serializer='json',
        accept_content=['json'],
        result_serializer='json',
        timezone='Asia/Seoul',
        enable_utc=True,
        task_track_started=True,
        task_time_limit=1800,  # 30분
        task_soft_time_limit=1500,  # 25분
        worker_prefetch_multiplier=1,
        task_acks_late=True,
        worker_disable_rate_limits=True,
        result_expires=3600,  # 1시간
    )
    
    return celery

# Celery 인스턴스 생성
celery_app = create_celery_app()
