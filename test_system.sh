#!/bin/bash

# 🚀 Proxmox Manager 시스템 테스트 스크립트
# 이 스크립트는 프로젝트의 모든 기능을 종합적으로 테스트합니다.

set -e  # 오류 발생 시 스크립트 종료

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 로그 함수들
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

# 헤더 출력
print_header() {
    echo "=================================================================="
    echo "🚀 Proxmox Manager 시스템 테스트"
    echo "=================================================================="
    echo "시작 시간: $(date)"
    echo "작업 디렉토리: $(pwd)"
    echo "=================================================================="
}

# 환경 확인
check_environment() {
    log_info "환경 확인 중..."
    
    # Python 확인
    if ! command -v python3 &> /dev/null; then
        log_error "Python3가 설치되지 않았습니다."
        exit 1
    fi
    
    # 가상환경 확인
    if [ ! -d "venv" ]; then
        log_warning "가상환경이 없습니다. 생성 중..."
        python3 -m venv venv
    fi
    
    # 가상환경 활성화
    source venv/bin/activate
    
    # 필수 패키지 확인
    log_info "필수 패키지 확인 중..."
    pip install -q -r requirements.txt
    
    log_success "환경 확인 완료"
}

# Flask 애플리케이션 상태 확인
check_flask_app() {
    log_info "Flask 애플리케이션 상태 확인 중..."
    
    # Flask 앱이 실행 중인지 확인
    if curl -s http://localhost:5000 > /dev/null 2>&1; then
        log_success "Flask 애플리케이션이 실행 중입니다."
        return 0
    else
        log_warning "Flask 애플리케이션이 실행되지 않았습니다."
        log_info "Flask 애플리케이션을 시작합니다..."
        
        # 백그라운드에서 Flask 앱 시작
        nohup python run.py > logs/flask_app.log 2>&1 &
        FLASK_PID=$!
        
        # Flask 앱이 시작될 때까지 대기
        for i in {1..30}; do
            if curl -s http://localhost:5000 > /dev/null 2>&1; then
                log_success "Flask 애플리케이션이 시작되었습니다. (PID: $FLASK_PID)"
                echo $FLASK_PID > logs/flask_app.pid
                return 0
            fi
            sleep 2
        done
        
        log_error "Flask 애플리케이션 시작 실패"
        return 1
    fi
}

# Flask 애플리케이션 정리
cleanup_flask_app() {
    if [ -f "logs/flask_app.pid" ]; then
        FLASK_PID=$(cat logs/flask_app.pid)
        if kill -0 $FLASK_PID 2>/dev/null; then
            log_info "Flask 애플리케이션 종료 중... (PID: $FLASK_PID)"
            kill $FLASK_PID
            rm -f logs/flask_app.pid
        fi
    fi
}

# 테스트 실행
run_tests() {
    log_info "테스트 실행 중..."
    
    # 로그 디렉토리 생성
    mkdir -p logs
    
    # 테스트 실행
    python tests/run_tests.py --all
    
    if [ $? -eq 0 ]; then
        log_success "모든 테스트가 성공적으로 완료되었습니다."
    else
        log_error "일부 테스트가 실패했습니다."
        return 1
    fi
}

# 보고서 생성
generate_report() {
    log_info "테스트 보고서 생성 중..."
    
    if [ -f "logs/overall_test_report.json" ]; then
        log_success "테스트 보고서가 생성되었습니다: logs/overall_test_report.json"
        
        # 간단한 요약 출력
        echo ""
        echo "=================================================================="
        echo "📊 테스트 결과 요약"
        echo "=================================================================="
        
        # JSON에서 요약 정보 추출
        if command -v jq &> /dev/null; then
            echo "전체 테스트: $(jq -r '.summary.total_tests' logs/overall_test_report.json)"
            echo "통과: $(jq -r '.summary.passed_tests' logs/overall_test_report.json)"
            echo "실패: $(jq -r '.summary.failed_tests' logs/overall_test_report.json)"
            echo "성공률: $(jq -r '.summary.success_rate' logs/overall_test_report.json)%"
        else
            echo "jq가 설치되지 않아 상세 요약을 표시할 수 없습니다."
            echo "logs/overall_test_report.json 파일을 확인하세요."
        fi
        
        echo "=================================================================="
    else
        log_warning "테스트 보고서를 찾을 수 없습니다."
    fi
}

# 정리 작업
cleanup() {
    log_info "정리 작업 중..."
    cleanup_flask_app
    log_success "정리 작업 완료"
}

# 메인 함수
main() {
    print_header
    
    # 트랩 설정 (스크립트 종료 시 정리 작업 실행)
    trap cleanup EXIT
    
    # 환경 확인
    check_environment
    
    # Flask 애플리케이션 확인/시작
    if ! check_flask_app; then
        log_error "Flask 애플리케이션을 시작할 수 없습니다."
        exit 1
    fi
    
    # 테스트 실행
    if ! run_tests; then
        log_error "테스트 실행 실패"
        exit 1
    fi
    
    # 보고서 생성
    generate_report
    
    log_success "시스템 테스트가 완료되었습니다."
    echo "종료 시간: $(date)"
}

# 스크립트 실행
main "$@"
