#!/bin/bash
# 개발 환경용 Celery 워커 재시작 스크립트

echo "🔄 Celery 워커 재시작 중..."

# Redis 디렉토리로 이동
cd redis

# Celery 워커 재시작
echo "📦 Celery 워커 컨테이너 재시작..."
docker-compose restart celery-worker

# 상태 확인
echo "🔍 Celery 워커 상태 확인..."
sleep 3
docker-compose ps celery-worker

echo "✅ Celery 워커 재시작 완료!"
echo "💡 이제 코드 변경 시 자동으로 재시작됩니다."
