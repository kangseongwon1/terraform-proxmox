from celery import Celery
import os
from app import create_app  # 앱 팩토리 불러오기

def create_celery_app():
    flask_app = create_app()  # Flask 앱 생성

    # Redis 브로커 설정 (비밀번호 지원)
    redis_host = os.getenv('REDIS_HOST', 'localhost')
    redis_port = os.getenv('REDIS_PORT', 6379)
    redis_db = os.getenv('REDIS_DB', 0)
    redis_password = os.getenv('REDIS_PASSWORD')

    if redis_password:
        broker_url = f"redis://:{redis_password}@{redis_host}:{redis_port}/{redis_db}"
    else:
        broker_url = f"redis://{redis_host}:{redis_port}/{redis_db}"

    # 백엔드 URL 설정 (환경 변수 우선)
    backend_url = os.getenv('CELERY_RESULT_BACKEND', broker_url)
    
    celery = Celery(
        'proxmox_manager',
        broker=broker_url,
        backend=backend_url,  # 환경 변수 또는 브로커 URL 사용
        include=['app.tasks.server_tasks', 'app.tasks.test_tasks']
    )

    # 간단하고 안전한 Celery 설정
    celery.conf.update(
        task_serializer='json',
        accept_content=['json'],
        result_serializer='json',
        timezone='Asia/Seoul',
        enable_utc=True,
        task_time_limit=1800,
        task_soft_time_limit=1500,
        worker_prefetch_multiplier=1,
        task_acks_late=True,
        worker_disable_rate_limits=True,
        result_expires=3600,
        # 결과 저장 활성화 (Redis 백엔드 사용)
        task_ignore_result=False,
        task_store_eager_result=False,
        task_always_eager=False,
        # Redis 연결 설정
        broker_connection_retry_on_startup=True,
        broker_connection_retry=True,
        broker_connection_max_retries=10,
        # 태스크 추적 활성화
        task_track_started=True,
        task_send_sent_event=True,
        # 시간 동기화 문제 해결
        worker_hijack_root_logger=False,
        worker_log_color=False,
        # 시간 차이 허용 범위 증가
        worker_max_tasks_per_child=1000,
        # 시간 동기화 경고 무시
        worker_direct=True,
        worker_pool_restarts=True,
    )

    # Flask 컨텍스트 자동 주입
    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with flask_app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask
    return celery

celery_app = create_celery_app()