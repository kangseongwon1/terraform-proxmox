// app/static/monitoring.js
$(document).ready(function() {
    // ============================================================================
    // 🚀 모니터링 시스템 설정 변수들
    // ============================================================================
    
    // API 엔드포인트 설정
    const API_BASE_URL = '/monitoring';
    const SERVERS_API = `${API_BASE_URL}/servers`;
    
    // 서버 상태 정의
    const SERVER_STATUS = {
        HEALTHY: 'healthy',
        WARNING: 'warning',
        CRITICAL: 'critical'
    };
    
    // ============================================================================
    // 🔧 전역 변수들
    // ============================================================================
    let selectedServer = 'all';
    let servers = [];
    let grafanaDashboardInfo = null;
    
    // ============================================================================
    // �� 초기화 및 메인 실행
    // ============================================================================
    init();
    
    function init() {
        loadServersData();
        setupEventListeners();
        initializeGrafanaDashboard(); // iframe만 사용
    }
    
    // ============================================================================
    // �� 서버 데이터 로딩 및 관리
    // ============================================================================
    
    // 서버 데이터 로딩
    function loadServersData() {
        $.getJSON(SERVERS_API)
            .then(function(response) {
                if (response.success) {
                    servers = response.data;
                    loadServersOverview();
                    populateServerDropdown(); // 서버 드롭다운 채우기
                }
            })
            .catch(function(error) {
                console.error('서버 데이터 로딩 실패:', error);
                // 기본 서버 목록 사용 (서버 이름 포함)
                servers = [
                    {ip: '192.168.0.10', port: '22', status: 'healthy', name: 'Web-Server-01', role: 'web', vmid: 100},
                    {ip: '192.168.0.111', port: '20222', status: 'healthy', name: 'DB-Server-01', role: 'database', vmid: 101},
                    {ip: '192.168.0.112', port: '20222', status: 'warning', name: 'App-Server-01', role: 'application', vmid: 102},
                    {ip: '192.168.0.113', port: '20222', status: 'healthy', name: 'Cache-Server-01', role: 'cache', vmid: 103},
                    {ip: '192.168.0.114', port: '20222', status: 'healthy', name: 'Web-Server-02', role: 'web', vmid: 104},
                    {ip: '192.168.0.115', port: '20222', status: 'healthy', name: 'DB-Server-02', role: 'database', vmid: 105},
                    {ip: '192.168.0.116', port: '20222', status: 'healthy', name: 'App-Server-02', role: 'application', vmid: 106},
                    {ip: '192.168.0.117', port: '20222', status: 'critical', name: 'Monitor-Server-01', role: 'monitoring', vmid: 107},
                    {ip: '192.168.0.118', port: '20222', status: 'healthy', name: 'Backup-Server-01', role: 'backup', vmid: 108},
                    {ip: '192.168.0.119', port: '20222', status: 'healthy', name: 'Proxy-Server-01', role: 'proxy', vmid: 109}
                ];
                loadServersOverview();
                populateServerDropdown(); // 서버 드롭다운 채우기
            });
    }
    
    // 서버 개요 로딩
    function loadServersOverview() {
        updateSummaryPanels();
        updateStatusBadge();
    }
    
    // 요약 패널 업데이트
    function updateSummaryPanels() {
        try {
            console.log('updateSummaryPanels 호출됨');
            
            // 서버 데이터 검증
            if (!servers || !Array.isArray(servers)) {
                console.warn('서버 데이터가 없거나 유효하지 않습니다.');
                servers = [];
            }
            
            const total = servers.length;
            const healthy = servers.filter(s => s.status === 'healthy').length;
            const warning = servers.filter(s => s.status === 'warning').length;
            const critical = servers.filter(s => s.status === 'critical').length;
            
            console.log(`서버 통계: 전체=${total}, 정상=${healthy}, 경고=${warning}, 위험=${critical}`);
            
            // 요약 패널 업데이트
            $('#total-servers').text(total);
            $('#healthy-servers').text(healthy);
            $('#warning-servers').text(warning);
            $('#critical-servers').text(critical);
            
            // 상태별 배지 색상 업데이트
            updateStatusBadge();
            
        } catch (error) {
            console.error('요약 패널 업데이트 오류:', error);
            // 오류 발생 시 기본값 설정
            $('#total-servers').text('0');
            $('#healthy-servers').text('0');
            $('#warning-servers').text('0');
            $('#critical-servers').text('0');
        }
    }
    
    // 서버 드롭다운 채우기 - 서버 이름 기반
    function populateServerDropdown() {
        try {
            console.log('populateServerDropdown 호출됨');
            
            const select = $('#server-select');
            select.empty();
            
            // 서버 데이터 검증
            if (!servers || !Array.isArray(servers)) {
                console.warn('서버 드롭다운 초기화: 서버 데이터가 없습니다.');
                servers = [];
            }
            
            // 전체 서버 옵션 추가
            select.append('<option value="all">🖥️ 전체 서버</option>');
            
            // 개별 서버 옵션 추가 (서버 이름 기반)
            if (servers.length > 0) {
                servers.forEach(server => {
                    // 서버 이름과 IP를 함께 표시
                    const displayName = `${server.name} (${server.ip})`;
                    const option = `<option value="${server.ip}" data-name="${server.name}">${displayName}</option>`;
                    select.append(option);
                });
                console.log(`${servers.length}개 서버 옵션 추가됨 (이름 기반)`);
            } else {
                // 서버가 없을 때 기본 옵션 추가
                select.append('<option value="none" disabled>서버가 없습니다</option>');
                console.log('서버가 없어서 기본 옵션만 표시');
            }
            
        } catch (error) {
            console.error('서버 드롭다운 초기화 오류:', error);
            // 오류 발생 시 기본 옵션만 표시
            const select = $('#server-select');
            select.empty();
            select.append('<option value="all">🖥️ 전체 서버</option>');
            select.append('<option value="none" disabled>서버 로드 실패</option>');
        }
    }
    
    // 상태 배지 업데이트
    function updateStatusBadge() {
        const selectedServerData = servers.find(s => s.ip === selectedServer) || { status: SERVER_STATUS.HEALTHY };
        const $badge = $('#status-badge');
        const $lastUpdate = $('#last-update');

        $badge.removeClass().addClass('badge me-2');
        
        switch(selectedServerData.status) {
            case SERVER_STATUS.HEALTHY:
                $badge.addClass('bg-success').html('정상');
                break;
            case SERVER_STATUS.WARNING:
                $badge.addClass('bg-warning').html('경고');
                break;
            case SERVER_STATUS.CRITICAL:
                $badge.addClass('bg-danger').html('위험');
                break;
        }

        $lastUpdate.text(`마지막 업데이트: ${new Date().toLocaleTimeString()}`);
    }
    
    // ============================================================================
    // �� 이벤트 리스너 및 사용자 인터페이스
    // ============================================================================
    
    // 이벤트 리스너 설정
    function setupEventListeners() {
        // 서버 선택 변경
        $('#server-select').on('change', function() {
            selectedServer = $(this).val();
            updateStatusBadge();
            window.updateGrafanaDashboard(); // 서버 선택 변경 시 Grafana 대시보드 업데이트
        });

        // 새로고침 버튼
        $('#refresh-btn').on('click', function() {
            refreshData();
        });

        // Grafana 대시보드 새로고침 버튼
        $('#grafana-refresh-btn').on('click', function() {
            window.refreshGrafanaDashboard();
        });

        // Grafana 전체화면 버튼
        $('#grafana-fullscreen-btn').on('click', function() {
            openGrafanaFullscreen();
        });
    }
    
    // ============================================================================
    // 🎯 Grafana 대시보드 iframe 임베딩 관리
    // ============================================================================
    
    // Grafana 대시보드 초기화
    function initializeGrafanaDashboard() {
        console.log('Grafana 대시보드 초기화 시작');
        
        // Grafana 대시보드 정보 가져오기
        $.getJSON('/monitoring/grafana-dashboard')
            .then(function(response) {
                if (response.success && response.data) {
                    grafanaDashboardInfo = response.data;
                    console.log('Grafana 대시보드 정보 로드 완료:', grafanaDashboardInfo);
                    
                    // 초기 대시보드 표시
                    displayGrafanaDashboard('all');
                } else {
                    console.error('Grafana 대시보드 정보 로드 실패:', response);
                    showGrafanaError('Grafana 대시보드 정보를 가져올 수 없습니다.');
                }
            })
            .catch(function(error) {
                console.error('Grafana 대시보드 초기화 실패:', error);
                showGrafanaError('Grafana 대시보드에 연결할 수 없습니다.');
            });
    }
    
    // Grafana 대시보드 표시
    function displayGrafanaDashboard(selectedServer) {
        if (!grafanaDashboardInfo) {
            console.warn('Grafana 대시보드 정보가 없습니다.');
            return;
        }
        
        console.log('Grafana 대시보드 표시:', selectedServer);
        
        // 로딩 표시
        $('#grafana-loading').show();
        $('#grafana-dashboard').hide();
        hideGrafanaError();
        
        // 서버별 임베드 URL 생성
        const embedUrl = generateGrafanaEmbedUrl(selectedServer);
        console.log('생성된 임베드 URL:', embedUrl);
        
        // iframe 생성 및 설정
        const iframe = document.createElement('iframe');
        iframe.src = embedUrl;
        iframe.width = '100%';
        iframe.height = '800';
        iframe.frameBorder = '0';
        iframe.allowFullscreen = true;
        iframe.style.border = 'none';
        iframe.style.borderRadius = '8px';
        iframe.style.boxShadow = '0 2px 8px rgba(0,0,0,0.1)';
        
        // iframe 로드 완료 이벤트
        iframe.onload = function() {
            console.log('Grafana 대시보드 로드 완료');
            $('#grafana-loading').hide();
            $('#grafana-dashboard').show();
        };
        
        // iframe 로드 오류 이벤트
        iframe.onerror = function() {
            console.error('Grafana 대시보드 로드 실패');
            $('#grafana-loading').hide();
            showGrafanaError('Grafana 대시보드를 로드할 수 없습니다.');
        };
        
        // 기존 iframe 제거 후 새 iframe 추가
        const container = document.getElementById('grafana-dashboard');
        container.innerHTML = '';
        container.appendChild(iframe);
    }
    
    // Grafana 임베드 URL 생성 - 개선된 서버 필터링
    function generateGrafanaEmbedUrl(selectedServer) {
        if (!grafanaDashboardInfo) {
            return '';
        }
        
        const baseUrl = grafanaDashboardInfo.base_url;
        const dashboardUid = grafanaDashboardInfo.dashboard_uid;
        const orgId = grafanaDashboardInfo.org_id;
        
        // 기본 임베드 URL (자동 새로고침 포함)
        let embedUrl = `${baseUrl}/d/${dashboardUid}?orgId=${orgId}&theme=light&kiosk=tv&autofitpanels&refresh=5s`;
        
        // 서버별 필터링 - 여러 형식 시도
        if (selectedServer && selectedServer !== 'all') {
            // 다양한 Grafana 변수 형식 시도
            const serverFilters = [
                `&var-instance=${selectedServer}:9100`,  // 기본 형식
                `&var-instance=${selectedServer}`,       // 포트 없이
                `&var-server=${selectedServer}:9100`,   // server 변수명
                `&var-server=${selectedServer}`,        // server 변수명, 포트 없이
                `&var-host=${selectedServer}:9100`,     // host 변수명
                `&var-host=${selectedServer}`,          // host 변수명, 포트 없이
                `&var-target=${selectedServer}:9100`,   // target 변수명
                `&var-target=${selectedServer}`,        // target 변수명, 포트 없이
                `&var-node=${selectedServer}:9100`,     // node 변수명
                `&var-node=${selectedServer}`           // node 변수명, 포트 없이
            ];
            
            // 첫 번째 형식 사용 (실제로는 Grafana 대시보드 설정에 따라 조정 필요)
            embedUrl += serverFilters[0];
            console.log(`서버 필터링 적용: ${selectedServer} -> ${serverFilters[0]}`);
        }
        
        // 시간 범위 설정 (최근 1시간)
        const now = new Date();
        const oneHourAgo = new Date(now.getTime() - 60 * 60 * 1000);
        embedUrl += `&from=${oneHourAgo.getTime()}&to=${now.getTime()}`;
        
        return embedUrl;
    }
    
    // Grafana 오류 표시
    function showGrafanaError(message) {
        const errorHtml = `
            <div class="alert alert-warning d-flex align-items-center" role="alert">
                <i class="fas fa-exclamation-triangle me-2"></i>
                <div>
                    <strong>Grafana 대시보드 오류:</strong> ${message}
                </div>
            </div>
        `;
        $('#grafana-dashboard').html(errorHtml).show();
    }
    
    // Grafana 오류 숨기기
    function hideGrafanaError() {
        $('#grafana-dashboard .alert').remove();
    }
    
    // 서버 선택 변경 시 Grafana 대시보드 업데이트
    window.updateGrafanaDashboard = function() {
        const selectedServer = $('#server-select').val();
        const selectedOption = $('#server-select option:selected');
        const serverName = selectedOption.data('name') || selectedOption.text();
        
        console.log('선택된 서버로 Grafana 대시보드 업데이트:', {
            server: serverName,
            ip: selectedServer,
            option: selectedOption.text()
        });
        
        if (selectedServer && grafanaDashboardInfo) {
            displayGrafanaDashboard(selectedServer);
        }
    };
    
    // Grafana 대시보드 새로고침
    window.refreshGrafanaDashboard = function() {
        const selectedServer = $('#server-select').val() || 'all';
        console.log('Grafana 대시보드 새로고침:', selectedServer);
        
        // 로딩 표시
        $('#grafana-loading').show();
        $('#grafana-dashboard').hide();
        hideGrafanaError();
        
        // 대시보드 다시 로드
        displayGrafanaDashboard(selectedServer);
    };
    
    // Grafana 전체화면 열기
    function openGrafanaFullscreen() {
        if (!grafanaDashboardInfo) {
            alert('Grafana 대시보드 정보가 없습니다.');
            return;
        }
        
        const selectedServer = $('#server-select').val() || 'all';
        const embedUrl = generateGrafanaEmbedUrl(selectedServer);
        
        if (embedUrl) {
            // 새 창에서 Grafana 대시보드 열기
            window.open(embedUrl, '_blank', 'width=1920,height=1080,scrollbars=yes,resizable=yes');
        } else {
            alert('전체화면 모드를 열 수 없습니다.');
        }
    }
    
    // Grafana 필터 초기화
    window.resetGrafanaFilter = function() {
        $('#server-select').val('all');
        updateGrafanaDashboard();
        console.log('Grafana 필터 초기화됨');
    };
    
    // 데이터 새로고침 (요약 패널만)
    function refreshData() {
        updateSummaryPanels();
        updateStatusBadge();
    }
});