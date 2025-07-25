# 시스템 아키텍처 개요

- IaC: Terraform, Ansible로 인프라 및 소프트웨어 자동화
- 웹앱: Flask 기반 Python 앱
- 환경별(dev/prod) 분리, 모듈화, 역할별 관리

## 주요 구성요소
- terraform/: 인프라 코드, 환경별 분리
- ansible/: 서버 소프트웨어 설치/설정 자동화
- app/: 웹/백엔드 서비스, 도메인별 분리
- docs/: 문서, 운영/아키텍처/가이드 등 