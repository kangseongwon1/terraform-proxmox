// app/static/monitoring.js
$(document).ready(function() {
    // ============================================================================
    // 🚀 모니터링 시스템 설정 변수들
    // ============================================================================
    
    // Grafana 설정
    const GRAFANA_BASE_URL = 'http://localhost:3000';
    const GRAFANA_DASHBOARD_UID = 'system_monitoring';
    const GRAFANA_DASHBOARD_TITLE = 'system-monitoring-dashboard-10-servers';
    
    // Prometheus 설정
    const PROMETHEUS_BASE_URL = 'http://localhost:9090';
    const NODE_EXPORTER_PORT = '9100';
    
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
    // ��️ 서버 목록 (설정 파일에서 가져올 예정)
    // ============================================================================
    const servers = [
        { ip: '192.168.0.10', port: '22', status: SERVER_STATUS.HEALTHY },
        { ip: '192.168.0.111', port: '20222', status: SERVER_STATUS.HEALTHY },
        { ip: '192.168.0.112', port: '20222', status: SERVER_STATUS.WARNING },
        { ip: '192.168.0.113', port: '20222', status: SERVER_STATUS.HEALTHY },
        { ip: '192.168.0.114', port: '20222', status: SERVER_STATUS.HEALTHY },
        { ip: '192.168.0.115', port: '20222', status: SERVER_STATUS.HEALTHY },
        { ip: '192.168.0.116', port: '20222', status: SERVER_STATUS.HEALTHY },
        { ip: '192.168.0.117', port: '20222', status: SERVER_STATUS.CRITICAL },
        { ip: '192.168.0.118', port: '20222', status: SERVER_STATUS.HEALTHY },
        { ip: '192.168.0.119', port: '20222', status: SERVER_STATUS.HEALTHY }
    ];
    
    // ============================================================================
    // 🔧 전역 변수들
    // ============================================================================
    let charts = {};
    let selectedServer = 'all';
    let autoRefresh = true;
    let refreshInterval;
    
    // ============================================================================
    // �� 초기화 및 메인 실행
    // ============================================================================
    init();
    
    function init() {
        loadServersOverview();
        setupEventListeners();
        initializeCharts();
        startAutoRefresh();
        loadGrafanaDashboard();
    }
    
    // ============================================================================
    // 📋 서버 개요 및 UI 관리
    // ============================================================================
    
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
    // �� 이벤트 리스너 및 사용자 인터페이스
    // ============================================================================
    
    // 이벤트 리스너 설정
    function setupEventListeners() {
        // 서버 선택 변경
        $('#server-select').on('change', function() {
            selectedServer = $(this).val();
            updateCharts();
            updateStatusBadge();
            updateGrafanaDashboard();
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
    }
    
    // ============================================================================
    // �� 차트 초기화 및 관리
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
            // 전체 서버 선택 시 샘플 데이터 사용
            updateChartWithSampleData(now);
        } else {
            // 특정 서버 선택 시 실제 Prometheus 데이터 사용
            updateChartWithRealData(now, selectedServer);
        }
    }
    
    // 실제 데이터로 차트 업데이트
    function updateChartWithRealData(now, serverIp) {
        Promise.all([
            fetchPrometheusMetrics(serverIp, METRIC_TYPES.CPU),
            fetchPrometheusMetrics(serverIp, METRIC_TYPES.MEMORY),
            fetchPrometheusMetrics(serverIp, METRIC_TYPES.DISK),
            fetchPrometheusMetrics(serverIp, METRIC_TYPES.NETWORK)
        ]).then(function([cpuUsage, memoryUsage, diskUsage, networkUsage]) {
            updateChart(charts.cpu, now, cpuUsage);
            updateChart(charts.memory, now, memoryUsage);
            updateChart(charts.disk, now, diskUsage);
            updateChart(charts.network, now, networkUsage);
        }).catch(function(error) {
            console.error('메트릭 데이터 가져오기 실패:', error);
            // 실패 시 샘플 데이터 사용
            updateChartWithSampleData(now);
        });
    }
    
    // 샘플 데이터로 차트 업데이트 (전체 서버 선택 시)
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
    // �� Prometheus API 연동
    // ============================================================================
    
    // Prometheus API에서 메트릭 데이터 가져오기
    function fetchPrometheusMetrics(serverIp, metric) {
        const query = getMetricQuery(metric, serverIp);
        const url = `${PROMETHEUS_BASE_URL}/api/v1/query?query=${encodeURIComponent(query)}`;
        
        return $.getJSON(url)
            .then(function(data) {
                if (data.status === 'success' && data.data.result.length > 0) {
                    return parseFloat(data.data.result[0].value[1]);
                }
                return 0;
            })
            .catch(function(error) {
                console.error('Prometheus API 오류:', error);
                return 0;
            });
    }
    
    // 메트릭별 쿼리 생성
    function getMetricQuery(metric, serverIp) {
        const serverInstance = `${serverIp}:${NODE_EXPORTER_PORT}`;
        
        switch(metric) {
            case METRIC_TYPES.CPU:
                return `100 - (avg by (instance) (irate(node_cpu_seconds_total{mode="idle", instance="${serverInstance}"}[5m])) * 100)`;
            case METRIC_TYPES.MEMORY:
                return `(1 - (node_memory_MemAvailable_bytes{instance="${serverInstance}"} / node_memory_MemTotal_bytes{instance="${serverInstance}"})) * 100`;
            case METRIC_TYPES.DISK:
                return `(1 - (node_filesystem_avail_bytes{mountpoint="/", instance="${serverInstance}"} / node_filesystem_size_bytes{mountpoint="/", instance="${serverInstance}"})) * 100`;
            case METRIC_TYPES.NETWORK:
                return `(rate(node_network_receive_bytes_total{instance="${serverInstance}"}[1m]) + rate(node_network_transmit_bytes_total{instance="${serverInstance}"}[1m])) / (1024 * 1024 * 1024) * 100`;
            default:
                return `up{instance="${serverInstance}"}`;
        }
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
    
    // ============================================================================
    // 📊 Grafana 대시보드 연동
    // ============================================================================
    
    // Grafana 대시보드 로드
    function loadGrafanaDashboard() {
        const defaultUrl = `${GRAFANA_BASE_URL}/d/${GRAFANA_DASHBOARD_UID}/${GRAFANA_DASHBOARD_TITLE}`;
        $('#grafana-dashboard').attr('src', defaultUrl);
        console.log('Grafana 대시보드 로드됨:', defaultUrl);
    }
    
    // Grafana 대시보드 업데이트 (서버 선택 시)
    function updateGrafanaDashboard() {
        const baseUrl = `${GRAFANA_BASE_URL}/d/${GRAFANA_DASHBOARD_UID}/${GRAFANA_DASHBOARD_TITLE}`;
        
        if (selectedServer === 'all') {
            // 전체 서버 선택 시 기본 URL 사용
            $('#grafana-dashboard').attr('src', baseUrl);
        } else {
            // 특정 서버 선택 시 해당 서버만 필터링
            const filteredUrl = `${baseUrl}?var-server=${selectedServer}`;
            $('#grafana-dashboard').attr('src', filteredUrl);
        }
        
        console.log('Grafana 대시보드 업데이트:', selectedServer);
    }
});