// app/static/monitoring.js
$(document).ready(function() {
    // ============================================================================
    // 🚀 모니터링 시스템 설정 변수들
    // ============================================================================
    
    // API 엔드포인트 설정
    const API_BASE_URL = '/monitoring';
    const METRICS_API = `${API_BASE_URL}/simple-metrics`;
    const SUMMARY_API = `${API_BASE_URL}/summary`;
    const SERVERS_API = `${API_BASE_URL}/servers`;
    const REALTIME_API = `${API_BASE_URL}/real-time-metrics`;
    const CHART_DATA_API = `${API_BASE_URL}/chart-data`;
    
    // 차트 설정
    const CHART_UPDATE_INTERVAL = 5000; // 5초
    const MAX_DATA_POINTS = 20; // 최대 데이터 포인트 수
    
    // 서버 상태 정의
    const SERVER_STATUS = {
        HEALTHY: 'healthy',
        WARNING: 'warning',
        CRITICAL: 'critical'
    };
    
    // 메트릭 타입 정의
    const METRIC_TYPES = {
        CPU: 'cpu',
        MEMORY: 'memory',
        DISK: 'disk',
        NETWORK: 'network'
    };
    
    // ============================================================================
    // 🔧 전역 변수들
    // ============================================================================
    let charts = {};
    let selectedServer = 'all';
    let autoRefresh = true;
    let refreshInterval;
    let servers = [];
    
    // ============================================================================
    // 🚀 초기화 및 메인 실행
    // ============================================================================
    init();
    
    function init() {
        loadServersData();
        setupEventListeners();
        initializeCharts();
        startAutoRefresh();
    }
    
    // ============================================================================
    // 📋 서버 데이터 로딩 및 관리
    // ============================================================================
    
    // 서버 데이터 로딩
    function loadServersData() {
        $.getJSON(SERVERS_API)
            .then(function(response) {
                if (response.success) {
                    servers = response.data;
                    loadServersOverview();
                }
            })
            .catch(function(error) {
                console.error('서버 데이터 로딩 실패:', error);
                // 기본 서버 목록 사용
                servers = [
                    {ip: '192.168.0.10', port: '22', status: 'healthy'},
                    {ip: '192.168.0.111', port: '20222', status: 'healthy'},
                    {ip: '192.168.0.112', port: '20222', status: 'warning'},
                    {ip: '192.168.0.113', port: '20222', status: 'healthy'},
                    {ip: '192.168.0.114', port: '20222', status: 'healthy'},
                    {ip: '192.168.0.115', port: '20222', status: 'healthy'},
                    {ip: '192.168.0.116', port: '20222', status: 'healthy'},
                    {ip: '192.168.0.117', port: '20222', status: 'critical'},
                    {ip: '192.168.0.118', port: '20222', status: 'healthy'},
                    {ip: '192.168.0.119', port: '20222', status: 'healthy'}
                ];
                loadServersOverview();
            });
    }
    
    // 서버 개요 로딩
    function loadServersOverview() {
        updateSummaryPanels();
        populateServerDropdown();
        updateStatusBadge();
    }
    
    // 요약 패널 업데이트
    function updateSummaryPanels() {
        const total = servers.length;
        const healthy = servers.filter(s => s.status === SERVER_STATUS.HEALTHY).length;
        const warning = servers.filter(s => s.status === SERVER_STATUS.WARNING).length;
        const critical = servers.filter(s => s.status === SERVER_STATUS.CRITICAL).length;

        $('#total-servers').text(total);
        $('#healthy-servers').text(healthy);
        $('#warning-servers').text(warning);
        $('#critical-servers').text(critical);
    }
    
    // 서버 드롭다운 채우기
    function populateServerDropdown() {
        const $select = $('#server-select');
        $select.find('option:not(:first)').remove();

        servers.forEach(server => {
            const option = `<option value="${server.ip}">${server.ip}:${server.port}</option>`;
            $select.append(option);
        });
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
    // 🎯 이벤트 리스너 및 사용자 인터페이스
    // ============================================================================
    
    // 이벤트 리스너 설정
    function setupEventListeners() {
        // 서버 선택 변경
        $('#server-select').on('change', function() {
            selectedServer = $(this).val();
            updateCharts();
            updateStatusBadge();
            updateGrafanaDashboard(); // 서버 선택 변경 시 Grafana 대시보드 업데이트
        });

        // 새로고침 버튼
        $('#refresh-btn').on('click', function() {
            refreshData();
        });

        // 자동 새로고침 토글
        $('#auto-refresh').on('change', function() {
            autoRefresh = $(this).is(':checked');
            if (autoRefresh) {
                startAutoRefresh();
            } else {
                stopAutoRefresh();
            }
        });

        // Grafana 대시보드 새로고침 버튼
        $('#grafana-refresh-btn').on('click', function() {
            refreshGrafanaDashboard();
        });

        // Grafana 전체화면 버튼
        $('#grafana-fullscreen-btn').on('click', function() {
            openGrafanaFullscreen();
        });
    }
    
    // ============================================================================
    // 📊 차트 초기화 및 관리
    // ============================================================================
    
    // 차트 초기화
    function initializeCharts() {
        // CPU 차트
        charts.cpu = createChart('cpuChart', 'CPU 사용률 (%)', 'rgb(75, 192, 192)');
        
        // 메모리 차트
        charts.memory = createChart('memoryChart', '메모리 사용률 (%)', 'rgb(255, 99, 132)');
        
        // 디스크 차트
        charts.disk = createChart('diskChart', '디스크 사용률 (%)', 'rgb(54, 162, 235)');
        
        // 네트워크 차트
        charts.network = createChart('networkChart', '네트워크 대역폭 사용률 (%)', 'rgb(255, 205, 86)');
    }
    
    // 차트 생성 헬퍼 함수
    function createChart(canvasId, label, borderColor) {
        return new Chart(document.getElementById(canvasId), {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: label,
                    data: [],
                    borderColor: borderColor,
                    backgroundColor: borderColor.replace('rgb', 'rgba').replace(')', ', 0.2)'),
                    borderWidth: 2,
                    tension: 0.1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 100
                    }
                }
            }
        });
    }
    
    // ============================================================================
    // 🔄 차트 업데이트 및 데이터 관리
    // ============================================================================
    
    // 차트 업데이트
    function updateCharts() {
        const now = new Date().toLocaleTimeString();
        
        if (selectedServer === 'all') {
            // 전체 서버 선택 시 실시간 API에서 데이터 가져오기
            fetchRealTimeMetrics(now, 'all');
        } else {
            // 특정 서버 선택 시 해당 서버 메트릭 가져오기
            fetchRealTimeMetrics(now, selectedServer);
        }
    }
    
    // 실시간 메트릭 가져오기
    function fetchRealTimeMetrics(now, serverIp) {
        $.getJSON(REALTIME_API, { server: serverIp, type: 'all' })
            .then(function(response) {
                if (response.success) {
                    const data = response.data;
                    const metrics = data.metrics;
                    
                    // 각 차트 업데이트
                    if (metrics.cpu_usage !== null) {
                        updateChart(charts.cpu, now, metrics.cpu_usage);
                    }
                    if (metrics.memory_usage !== null) {
                        updateChart(charts.memory, now, metrics.memory_usage);
                    }
                    if (metrics.disk_usage !== null) {
                        updateChart(charts.disk, now, metrics.disk_usage);
                    }
                    if (metrics.network_usage !== null) {
                        updateChart(charts.network, now, metrics.network_usage);
                    }
                    
                    console.log('실시간 메트릭 업데이트 완료:', serverIp, metrics);
                }
            })
            .catch(function(error) {
                console.error('실시간 메트릭 가져오기 실패:', error);
                updateChartWithSampleData(now);
            });
    }
    
    // 시계열 차트 데이터 가져오기 (향후 확장용)
    function fetchChartData(serverIp, metricType) {
        $.getJSON(CHART_DATA_API, { 
            server: serverIp, 
            type: metricType, 
            points: MAX_DATA_POINTS 
        })
            .then(function(response) {
                if (response.success) {
                    console.log('차트 데이터 로드 완료:', response.data);
                    // 향후 시계열 차트 구현 시 사용
                }
            })
            .catch(function(error) {
                console.error('차트 데이터 가져오기 실패:', error);
            });
    }
    
    // 샘플 데이터로 차트 업데이트 (폴백용)
    function updateChartWithSampleData(now) {
        const cpuUsage = Math.random() * 100;
        const memoryUsage = Math.random() * 100;
        const diskUsage = Math.random() * 100;
        const networkUsage = Math.random() * 100;

        updateChart(charts.cpu, now, cpuUsage);
        updateChart(charts.memory, now, memoryUsage);
        updateChart(charts.disk, now, diskUsage);
        updateChart(charts.network, now, networkUsage);
    }
    
    // 개별 차트 업데이트
    function updateChart(chart, label, value) {
        chart.data.labels.push(label);
        chart.data.datasets[0].data.push(value);

        // 최대 데이터 포인트 수 유지
        if (chart.data.labels.length > MAX_DATA_POINTS) {
            chart.data.labels.shift();
            chart.data.datasets[0].data.shift();
        }

        chart.update('none');
    }
    
    // ============================================================================
    // 🔄 자동 새로고침 및 데이터 관리
    // ============================================================================
    
    // 자동 새로고침 시작
    function startAutoRefresh() {
        if (refreshInterval) {
            clearInterval(refreshInterval);
        }
        refreshInterval = setInterval(() => {
            if (autoRefresh) {
                updateCharts();
                updateStatusBadge();
            }
        }, CHART_UPDATE_INTERVAL);
    }
    
    // 자동 새로고침 중지
    function stopAutoRefresh() {
        if (refreshInterval) {
            clearInterval(refreshInterval);
            refreshInterval = null;
        }
    }
    
    // 데이터 새로고침
    function refreshData() {
        updateCharts();
        updateStatusBadge();
        updateSummaryPanels();
    }

    // 서버 선택 변경 시 Grafana 대시보드 업데이트
    function updateGrafanaDashboard() {
        const selectedServer = $('#server-select').val();
        console.log('선택된 서버로 Grafana 대시보드 업데이트:', selectedServer);
        
        if (selectedServer && window.grafanaDashboardInfo) {
            displayGrafanaDashboard(selectedServer);
        }
    }
    
    // Grafana 대시보드 컨트롤 함수들
    function refreshGrafanaDashboard() {
        const selectedServer = $('#server-select').val() || 'all';
        console.log('Grafana 대시보드 새로고침:', selectedServer);
        
        // 로딩 표시
        $('#grafana-loading').show();
        $('#grafana-dashboard').hide();
        hideGrafanaError();
        
        // 대시보드 다시 로드
        displayGrafanaDashboard(selectedServer);
    }
    
    function openGrafanaFullscreen() {
        if (!window.grafanaDashboardInfo) {
            alert('Grafana 대시보드 정보가 없습니다.');
            return;
        }
        
        const selectedServer = $('#server-select').val() || 'all';
        const embedUrl = `/monitoring/grafana-dashboard/embed?server=${selectedServer}`;
        
        // 새 창에서 Grafana 대시보드 열기
        $.ajax({
            url: embedUrl,
            method: 'GET',
            success: function(response) {
                if (response.success && response.data) {
                    const fullscreenUrl = response.data.embed_url;
                    window.open(fullscreenUrl, '_blank', 'width=1920,height=1080,scrollbars=yes,resizable=yes');
                } else {
                    alert('전체화면 모드를 열 수 없습니다.');
                }
            },
            error: function() {
                alert('전체화면 모드를 열 수 없습니다.');
            }
        });
    }
});