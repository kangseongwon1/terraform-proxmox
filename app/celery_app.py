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

    celery = Celery(
        'proxmox_manager',
        broker=broker_url,
        backend='cache+memory://',  # Redis 대신 메모리 백엔드 사용
        include=['app.tasks.server_tasks', 'app.tasks.test_tasks']
    )

    celery.conf.update(
        task_serializer='json',
        accept_content=['json'],
        result_serializer='json',
        timezone='Asia/Seoul',
        enable_utc=True,
        task_track_started=True,
        task_time_limit=1800,
        task_soft_time_limit=1500,
        worker_prefetch_multiplier=1,
        task_acks_late=True,
        worker_disable_rate_limits=True,
        result_expires=3600,
        # Redis 백엔드 호환성 설정
        result_backend_transport_options={
            'master_name': 'mymaster',
            'visibility_timeout': 3600,
        },
        # 예외 처리 완전 비활성화
        task_ignore_result=True,  # 결과 저장 비활성화
        task_store_eager_result=False,
        task_always_eager=False,
        # Redis 연결 설정
        broker_connection_retry_on_startup=True,
        broker_connection_retry=True,
        broker_connection_max_retries=10,
        # 예외 정보 저장 완전 비활성화
        task_store_errors_even_if_ignored=False,
        task_ignore_result_on_task_failure=True,  # 실패 시 결과 무시
        # 백엔드 안전 모드
        result_backend_max_retries=3,
        result_backend_retry_delay=1,
        # 예외 추적 비활성화
        task_track_started=False,
        task_send_sent_event=False,
    )

    # Flask 컨텍스트 자동 주입
    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with flask_app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask
    return celery

celery_app = create_celery_app()