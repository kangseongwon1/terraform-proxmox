# Docker 설정 파일

이 디렉토리는 Proxmox Manager의 Docker 관련 설정 파일들을 포함합니다.

## 📁 파일 목록

### **Dockerfile.celery**
- Celery 워커와 Flower 모니터링을 위한 Docker 이미지
- Python 3.9 기반
- Celery 4.4.7, Flower 2.0.1 포함
- Redis 연결 설정 포함

## 🚀 **사용 방법**

### **개별 빌드**
```bash
# Celery 이미지 빌드
docker build -f docker/Dockerfile.celery -t proxmox-celery .
```

### **Docker Compose로 실행**
```bash
# Redis + Celery 스택 실행
cd redis
docker-compose up -d
```

## 🔧 **설정 옵션**

### **환경 변수**
- `REDIS_HOST`: Redis 서버 호스트 (기본값: redis)
- `REDIS_PORT`: Redis 포트 (기본값: 6379)
- `REDIS_PASSWORD`: Redis 비밀번호
- `REDIS_DB`: Redis 데이터베이스 번호 (기본값: 0)
- `REDIS_ENABLED`: Redis 활성화 여부 (기본값: true)

### **포트 설정**
- **Redis**: 6379
- **Flower**: 5555

## 📊 **모니터링**

### **Flower 대시보드**
- URL: http://localhost:5555
- Celery 작업 모니터링
- 워커 상태 확인
- 작업 히스토리 조회

### **컨테이너 상태 확인**
```bash
# 모든 컨테이너 상태
docker-compose ps

# 특정 서비스 로그
docker-compose logs celery-worker
docker-compose logs celery-flower
docker-compose logs redis
```

## 🛠️ **문제 해결**

### **빌드 실패**
```bash
# 캐시 없이 재빌드
docker-compose build --no-cache
```

### **연결 문제**
```bash
# 네트워크 확인
docker network ls
docker network inspect redis_proxmox_network
```

### **권한 문제**
```bash
# 볼륨 권한 확인
docker-compose exec celery-worker ls -la /app
```
