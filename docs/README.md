# Terraform Proxmox Manager

> **Proxmox 가상화 환경을 위한 통합 관리 시스템**

Terraform Proxmox Manager는 Proxmox VE 환경에서 가상머신을 자동으로 생성, 관리, 모니터링하는 통합 솔루션입니다. 웹 기반 UI를 통해 서버 생성부터 모니터링까지 모든 작업을 간편하게 수행할 수 있습니다.

## 🚀 주요 기능

### 📊 **서버 관리**
- **대량 서버 생성/삭제**: Terraform을 통한 자동화된 VM 생성
- **역할 기반 설정**: Web, WAS, DB 서버별 자동화된 설정
- **실시간 상태 모니터링**: 서버 상태 및 리소스 사용량 추적

### 🔧 **자동화 & 설정**
- **Ansible 통합**: 서버 생성 후 자동 소프트웨어 설치 및 설정
- **Cloud-init 지원**: 초기 VM 설정 자동화
- **SSH 키 관리**: Vault를 통한 안전한 SSH 키 저장 및 관리

### 📈 **모니터링 & 알림**
- **Prometheus + Grafana**: 실시간 시스템 모니터링
- **Node Exporter**: 서버별 메트릭 수집
- **알림 시스템**: 서버 상태 변경 시 실시간 알림

### 🔐 **보안 & 백업**
- **HashiCorp Vault**: 민감한 정보 암호화 저장
- **자동 백업**: Proxmox 백업 시스템 통합
- **방화벽 관리**: 서버별 방화벽 규칙 자동 설정

## 🏗️ 시스템 아키텍처

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Web UI        │    │   Flask API     │    │   Terraform     │
│   (Frontend)    │◄──►│   (Backend)     │◄──►│   (Infrastructure)│
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │                       ▼                       │
         │              ┌─────────────────┐              │
         │              │   SQLite DB     │              │
         │              │   (Metadata)    │              │
         │              └─────────────────┘              │
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Grafana       │    │   Vault         │    │   Proxmox VE    │
│   (Monitoring)  │    │   (Secrets)     │    │   (Hypervisor)  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       │                       │
┌─────────────────┐              │                       │
│   Prometheus    │              │                       │
│   (Metrics)     │              │                       │
└─────────────────┘              │                       │
         │                       │                       │
         ▼                       │                       │
┌─────────────────┐              │                       │
│   Node Exporter │              │                       │
│   (Agents)      │              │                       │
└─────────────────┘              │                       │
                                 ▼                       │
                        ┌─────────────────┐              │
                        │   Ansible       │              │
                        │   (Configuration)│              │
                        └─────────────────┘              │
                                                         │
                                                         ▼
                                                ┌─────────────────┐
                                                │   Virtual       │
                                                │   Machines      │
                                                └─────────────────┘
```

## 🛠️ 기술 스택

| 구성 요소 | 기술 | 버전 |
|----------|------|------|
| **Frontend** | HTML5, CSS3, JavaScript | - |
| **Backend** | Python Flask | 2.3+ |
| **Database** | SQLite | 3.x |
| **Infrastructure** | Terraform | 1.5+ |
| **Configuration** | Ansible | 2.14+ |
| **Monitoring** | Prometheus + Grafana | Latest |
| **Secrets** | HashiCorp Vault | 1.14+ |
| **Virtualization** | Proxmox VE | 7.4+ |
| **Container** | Docker + Docker Compose | Latest |

## 📋 요구사항

### 시스템 요구사항
- **OS**: Rocky Linux 8+ / CentOS 8+ / RHEL 8+
- **CPU**: 4 Core 이상
- **Memory**: 8GB 이상
- **Storage**: 50GB 이상 여유 공간
- **Network**: 인터넷 연결 필요

### 소프트웨어 요구사항
- **Python**: 3.8+
- **Docker**: 20.10+
- **Docker Compose**: 2.0+
- **Terraform**: 1.5+
- **Ansible**: 2.14+
- **Git**: 2.30+

## 🚀 빠른 시작

### 1. 저장소 클론
```bash
git clone https://github.com/your-org/terraform-proxmox.git
cd terraform-proxmox
```

### 2. 자동 설치 실행
```bash
chmod +x install_complete_system.sh
sudo ./install_complete_system.sh
```

### 3. 웹 UI 접속
```bash
# 브라우저에서 접속
http://your-server-ip:5000
```

## 📚 문서

- **[설치 가이드](INSTALLATION.md)** - 상세한 설치 및 설정 방법
- **[시스템 아키텍처](ARCHITECTURE.md)** - 전체 시스템 구조 및 구성 요소
- **[API 레퍼런스](API_REFERENCE.md)** - REST API 문서
- **[운영 가이드](OPERATION_GUIDE.md)** - 일상적인 운영 및 관리 방법
- **[문제 해결](TROUBLESHOOTING.md)** - 자주 발생하는 문제 및 해결 방법
- **[변경 이력](CHANGELOG.md)** - 버전별 변경 사항

## 🤝 기여하기

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다. 자세한 내용은 [LICENSE](LICENSE) 파일을 참조하세요.

## 📞 지원

- **Issues**: [GitHub Issues](https://github.com/your-org/terraform-proxmox/issues)
- **Discussions**: [GitHub Discussions](https://github.com/your-org/terraform-proxmox/discussions)
- **Wiki**: [GitHub Wiki](https://github.com/your-org/terraform-proxmox/wiki)

## 🏆 주요 특징

- ✅ **완전 자동화**: 서버 생성부터 모니터링까지 원클릭
- ✅ **확장 가능**: 마이크로서비스 아키텍처로 쉬운 확장
- ✅ **보안 중심**: Vault 기반 비밀 정보 관리
- ✅ **모니터링 통합**: Prometheus + Grafana 완전 통합
- ✅ **클라우드 네이티브**: Docker 기반 컨테이너화
- ✅ **개발자 친화적**: REST API 및 상세한 문서 제공

---

**Made with ❤️ for Proxmox Community**
