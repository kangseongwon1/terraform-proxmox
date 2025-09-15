#!/bin/bash
# Proxmox Manager 모니터링 시스템 시작 스크립트

set -e

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 로그 함수
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Docker 설치 확인
check_docker() {
    log_info "Docker 설치 확인 중..."
    if ! command -v docker &> /dev/null; then
        log_error "Docker가 설치되지 않았습니다."
        log_info "Docker 설치 후 다시 시도해주세요."
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose가 설치되지 않았습니다."
        log_info "Docker Compose 설치 후 다시 시도해주세요."
        exit 1
    fi
    
    log_success "Docker 및 Docker Compose 확인 완료"
}

# 디렉토리 생성
create_directories() {
    log_info "필요한 디렉토리 생성 중..."
    mkdir -p prometheus_data
    mkdir -p grafana_data
    mkdir -p grafana/provisioning/datasources
    mkdir -p grafana/provisioning/dashboards
    mkdir -p grafana/dashboards
    
    # 권한 설정
    chmod 755 prometheus_data
    chmod 755 grafana_data
    chmod 755 grafana/provisioning/datasources
    chmod 755 grafana/provisioning/dashboards
    chmod 755 grafana/dashboards
    
    log_success "디렉토리 생성 완료"
}

# 기존 컨테이너 정리
cleanup_containers() {
    log_info "기존 모니터링 컨테이너 정리 중..."
    docker-compose down 2>/dev/null || true
    log_success "기존 컨테이너 정리 완료"
}

# 모니터링 시스템 시작
start_monitoring() {
    log_info "모니터링 시스템 시작 중..."
    docker-compose up -d
    
    # 컨테이너 상태 확인
    sleep 5
    if docker-compose ps | grep -q "Up"; then
        log_success "모니터링 시스템 시작 완료"
    else
        log_error "모니터링 시스템 시작 실패"
        docker-compose logs
        exit 1
    fi
}

# 서비스 상태 확인
check_services() {
    log_info "서비스 상태 확인 중..."
    
    # Prometheus 확인
    if curl -s http://localhost:9090/-/healthy > /dev/null; then
        log_success "Prometheus: http://localhost:9090"
    else
        log_warning "Prometheus 연결 실패"
    fi
    
    # Grafana 확인
    if curl -s http://localhost:3000/api/health > /dev/null; then
        log_success "Grafana: http://localhost:3000 (admin/admin123)"
    else
        log_warning "Grafana 연결 실패"
    fi
}

# 메인 실행
main() {
    log_info "Proxmox Manager 모니터링 시스템 시작"
    
    check_docker
    create_directories
    cleanup_containers
    start_monitoring
    check_services
    
    log_success "모니터링 시스템 설정 완료!"
    echo ""
    echo "📊 모니터링 대시보드:"
    echo "  - Prometheus: http://localhost:9090"
    echo "  - Grafana: http://localhost:3000 (admin/admin123)"
    echo ""
    echo "🔧 관리 명령어:"
    echo "  - 중지: docker-compose down"
    echo "  - 재시작: docker-compose restart"
    echo "  - 로그 확인: docker-compose logs"
    echo "  - 상태 확인: docker-compose ps"
}

# 스크립트 실행
main "$@"
