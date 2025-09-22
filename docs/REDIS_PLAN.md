# Redis 도입 계획

## 도입 목적
- 캐시: 빈번한 조회(API 응답/서버 목록/권한 등)
- 세션: 서버 확장 대비 서버간 세션 공유(Flask-Session Redis 백엔드)
- 작업큐: 비동기 작업(긴 Ansible/Terraform 트리거)을 Celery + Redis로

## 아키텍처 제안
- Redis 단일 인스턴스(초기) → 필요 시 클러스터
- Flask: Flask-Session(서버측 세션 저장소로 Redis)
- 작업큐: Celery(브로커/백엔드 Redis)

## 적용 단계
1) 의존성 추가 및 docker-compose.redis.yml 제공
2) 세션 스토리지 교체(옵션 스위치로 로컬/Redis 선택)
3) 캐시 레이어 추가(권한/설정/서버요약 TTL 캐시)
4) 작업큐 마이그레이션(알림과 연동)

## 장애/운영
- Redis 불가 시 로컬 세션/폴백 동작
- 모니터링 대시보드에 Redis 지표 추가
