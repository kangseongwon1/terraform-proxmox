# API Reference

본 문서는 `app/routes/*`에 정의된 라우트를 기준으로 재정리한 참조입니다.

## Admin (`/admin`)
- GET `/admin/iam/data` — IAM 데이터(users, all_permissions)
- POST `/admin/api/users` — 사용자 생성
- DELETE `/admin/api/users/<username>` — 사용자 삭제
- POST `/admin/api/users/<username>/password` — 비밀번호 변경
- POST `/admin/iam/<username>/permissions` — 권한 설정
- POST `/admin/iam/<username>/role` — 역할 설정
- 기타 템플릿: `/admin/iam/content`, `/admin`, `/admin/users`

## Auth
- GET/POST `/login` — 로그인
- GET `/logout` — 로그아웃
- POST `/change-password` — 본인 비밀번호 변경(폼/JSON 지원)
- GET `/api/session/check` — 세션 상태
- POST `/api/session/refresh` — 세션 갱신
- GET `/api/current-user` — 현재 사용자 정보(JSON)
- GET `/api/profile` — 프로필(JSON)
- 호환성: `/session/check`, `/session/refresh`

## Servers
- GET `/api/servers` — 서버 목록
- GET `/api/servers/brief` — 간단 목록
- POST `/api/servers` — 생성
- POST `/api/create_servers_bulk` — 다중 생성
- POST `/api/servers/<name>/start|stop|reboot|delete` — 액션
- GET `/api/tasks/status` — 작업 상태
- GET `/api/tasks/config` — 폴링 설정

## Firewall
- GET `/api/firewall/groups` — 그룹 목록
- POST `/api/firewall/groups` — 생성/갱신
- GET `/api/firewall/groups/<group>` — 상세
- DELETE `/api/firewall/groups/<group>` — 삭제
- POST `/api/firewall/groups/<group>/rules` — 룰 추가/갱신
- DELETE `/api/firewall/groups/<group>/rules/<id>` — 룰 삭제
- POST `/api/apply_security_group/<server>` — 적용
- POST `/api/firewall/assign_bulk` — 일괄 적용
- POST `/api/remove_firewall_group/<server>` — 제거

## Notifications (`/api`)
- GET `/api/notifications` — 전체 알림
- GET `/api/notifications/latest` — 최신 알림
- GET `/api/notifications/<id>` — 상세
- POST `/api/notifications/<id>/read` — 읽음
- DELETE `/api/notifications/<id>` — 삭제
- POST `/api/notifications/clear-all` — 전체 삭제
- GET `/api/notifications/unread-count` — 미읽음 수
- GET `/api/notifications/stream` — SSE(옵션)

## Main/Pages
- `/` 대시보드 인덱스
- `/dashboard/content`, `/instances/content`, `/admin/iam/content`, `/firewall/*/content`, `/backups/content` 등 템플릿 로딩용 경로들

## 공통 권한
- `@login_required` + `permission_required('...')`
- 역할·권한 모델은 `docs/PERMISSIONS.md` 참조
