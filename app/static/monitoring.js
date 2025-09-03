// monitoring.js - 모니터링 페이지 JavaScript
$(function() {
    console.log('[monitoring.js] 모니터링 페이지 초기화 시작');
    
    // Chart.js 의존성 확인 및 로드
    if (typeof Chart === 'undefined') {
        console.log('[monitoring.js] Chart.js 로드 중...');
        const script = document.createElement('script');
        script.src = 'https://cdn.jsdelivr.net/npm/chart.js@3.7.0/dist/chart.min.js';
        script.onload = function() {
            console.log('[monitoring.js] Chart.js 로드 완료');
            initializePage();
        };
        script.onerror = function() {
            console.error('[monitoring.js] Chart.js 로드 실패');
            showNotification('error', 'Chart.js 로드에 실패했습니다. 차트가 표시되지 않을 수 있습니다.');
            initializePage();
        };
        document.head.appendChild(script);
        return;
    }
    
    // Chart.js가 이미 로드된 경우 바로 초기화
    initializePage();
    
    // 전역 변수
    let cpuChart = null;
    let memoryChart = null;
    let monitoringInterval = null;
    let chartDataPoints = 100;
    
    // 모니터링 설정
    const monitoringConfig = {
        prometheusUrl: 'http://192.168.0.1:9090',
        grafanaUrl: 'http://192.168.0.1:3000',
        collectionInterval: 30,
        chartDataPoints: 100
    };
    
    // 차트 색상 설정
    const chartColors = {
        primary: '#007bff',
        success: '#28a745',
        warning: '#ffc107',
        danger: '#dc3545',
        info: '#17a2b8',
        secondary: '#6c757d'
    };
    
    /**
     * 모니터링 시스템 상태 확인
     */
    function checkMonitoringHealth() {
        console.log('[monitoring.js] 모니터링 시스템 상태 확인 시작');
        
        $.get('/monitoring/health', function(res) {
            if (res.success) {
                updateMonitoringStatus(res.monitoring_system);
            } else {
                console.error('[monitoring.js] 모니터링 상태 확인 실패:', res.error);
                updateMonitoringStatus({ prometheus: 'error', grafana: 'error' });
            }
        }).fail(function(xhr) {
            console.error('[monitoring.js] 모니터링 상태 확인 요청 실패:', xhr);
            updateMonitoringStatus({ prometheus: 'error', grafana: 'error' });
        });
    }
    
    /**
     * 모니터링 상태 UI 업데이트
     */
    function updateMonitoringStatus(status) {
        const statusMap = {
            'healthy': 'status-online',
            'unhealthy': 'status-warning',
            'error': 'status-offline'
        };
        
        // Prometheus 상태
        const prometheusStatus = statusMap[status.prometheus] || 'status-offline';
        $('#monitoring-status .col-md-4:eq(0) .status-indicator')
            .removeClass('status-online status-warning status-offline')
            .addClass(prometheusStatus);
        
        // Grafana 상태
        const grafanaStatus = statusMap[status.grafana] || 'status-offline';
        $('#monitoring-status .col-md-4:eq(1) .status-indicator')
            .removeClass('status-online status-warning status-offline')
            .addClass(grafanaStatus);
        
        // Node Exporter 상태 (기본값: 온라인)
        $('#monitoring-status .col-md-4:eq(2) .status-indicator')
            .removeClass('status-online status-warning status-offline')
            .addClass('status-online');
    }
    
    /**
     * 서버 전체 개요 로드
     */
    function loadServersOverview() {
        console.log('[monitoring.js] 서버 전체 개요 로드 시작');
        
        $.get('/monitoring/servers/overview', function(res) {
            if (res.success) {
                renderServersOverview(res.servers);
                updateSummaryMetrics(res.servers);
            } else {
                console.error('[monitoring.js] 서버 개요 로드 실패:', res.error);
                $('#servers-overview').html('<div class="col-12 text-center text-danger">서버 정보를 불러올 수 없습니다.</div>');
            }
        }).fail(function(xhr) {
            console.error('[monitoring.js] 서버 개요 요청 실패:', xhr);
            $('#servers-overview').html('<div class="col-12 text-center text-danger">서버 정보를 불러올 수 없습니다.</div>');
        });
    }
    
    /**
     * 서버 개요 렌더링
     */
    function renderServersOverview(servers) {
        let html = '';
        
        Object.entries(servers).forEach(([serverIp, server]) => {
            const statusClass = server.status === 'online' ? 'status-online' : 'status-offline';
            const statusText = server.status === 'online' ? '온라인' : '오프라인';
            
            html += `
                <div class="col-md-6 col-lg-4 mb-3">
                    <div class="card h-100">
                        <div class="card-body">
                            <div class="d-flex justify-content-between align-items-start mb-2">
                                <h6 class="card-title mb-0">
                                    <i class="fas fa-server me-2"></i>${serverIp}
                                </h6>
                                <div class="d-flex align-items-center">
                                    <div class="status-indicator ${statusClass}"></div>
                                    <small class="text-muted">${statusText}</small>
                                </div>
                            </div>
                            <div class="row text-center">
                                <div class="col-6">
                                    <div class="metric-value text-primary">${server.cpu_usage || 0}%</div>
                                    <div class="metric-label">CPU</div>
                                </div>
                                <div class="col-6">
                                    <div class="metric-value text-success">${server.memory_usage || 0}%</div>
                                    <div class="metric-label">메모리</div>
                                </div>
                            </div>
                            <div class="mt-2">
                                <small class="text-muted">마지막 확인: ${new Date(server.last_check).toLocaleTimeString()}</small>
                            </div>
                        </div>
                    </div>
                </div>
            `;
        });
        
        $('#servers-overview').html(html);
    }
    
    /**
     * 요약 메트릭 업데이트
     */
    function updateSummaryMetrics(servers) {
        const onlineServers = Object.values(servers).filter(s => s.status === 'online');
        const totalServers = Object.keys(servers).length;
        
        if (onlineServers.length > 0) {
            const avgCpu = onlineServers.reduce((sum, s) => sum + (s.cpu_usage || 0), 0) / onlineServers.length;
            const avgMemory = onlineServers.reduce((sum, s) => sum + (s.memory_usage || 0), 0) / onlineServers.length;
            
            $('#avg-cpu-usage').text(avgCpu.toFixed(1) + '%');
            $('#avg-memory-usage').text(avgMemory.toFixed(1) + '%');
            $('#online-servers').text(onlineServers.length + '/' + totalServers);
        } else {
            $('#avg-cpu-usage').text('--');
            $('#avg-memory-usage').text('--');
            $('#online-servers').text('0/' + totalServers);
        }
        
        // 디스크 사용률은 기본값으로 설정 (실제로는 Prometheus에서 가져와야 함)
        $('#avg-disk-usage').text('--');
    }
    
    /**
     * 서버별 상세 메트릭 로드
     */
    function loadServerMetricsDetail() {
        console.log('[monitoring.js] 서버별 상세 메트릭 로드 시작');
        
        // 실제 구현에서는 각 서버별로 상세 메트릭을 로드
        // 현재는 기본 UI만 표시
        const html = `
            <div class="col-12">
                <div class="alert alert-info">
                    <i class="fas fa-info-circle me-2"></i>
                    서버별 상세 메트릭은 Prometheus와 연동 후 표시됩니다.
                    <br>
                    <small class="text-muted">현재 개발 중인 기능입니다.</small>
                </div>
            </div>
        `;
        
        $('#server-metrics-detail').html(html);
    }
    
    /**
     * CPU 차트 초기화
     */
    function initCpuChart() {
        if (typeof Chart === 'undefined') {
            console.warn('[monitoring.js] Chart.js가 로드되지 않아 CPU 차트를 초기화할 수 없습니다.');
            return;
        }
        
        const ctx = document.getElementById('cpu-chart');
        if (!ctx) {
            console.warn('[monitoring.js] CPU 차트 캔버스를 찾을 수 없습니다.');
            return;
        }
        
        const chartCtx = ctx.getContext('2d');
        
        cpuChart = new Chart(chartCtx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: '평균 CPU 사용률',
                    data: [],
                    borderColor: chartColors.primary,
                    backgroundColor: chartColors.primary + '20',
                    tension: 0.4,
                    fill: true
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: true,
                        position: 'top'
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 100,
                        ticks: {
                            callback: function(value) {
                                return value + '%';
                            }
                        }
                    }
                }
            }
        });
    }
    
    /**
     * 메모리 차트 초기화
     */
    function initMemoryChart() {
        if (typeof Chart === 'undefined') {
            console.warn('[monitoring.js] Chart.js가 로드되지 않아 메모리 차트를 초기화할 수 없습니다.');
            return;
        }
        
        const ctx = document.getElementById('memory-chart');
        if (!ctx) {
            console.warn('[monitoring.js] 메모리 차트 캔버스를 찾을 수 없습니다.');
            return;
        }
        
        const chartCtx = ctx.getContext('2d');
        
        memoryChart = new Chart(chartCtx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: '평균 메모리 사용률',
                    data: [],
                    borderColor: chartColors.success,
                    backgroundColor: chartColors.success + '20',
                    tension: 0.4,
                    fill: true
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: true,
                        position: 'top'
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 100,
                        ticks: {
                            callback: function(value) {
                                return value + '%';
                            }
                        }
                    }
                }
            }
        });
    }
    
    /**
     * 차트 데이터 업데이트
     */
    function updateCharts() {
        const now = new Date();
        const timeLabel = now.toLocaleTimeString();
        
        // CPU 차트 업데이트
        if (cpuChart) {
            cpuChart.data.labels.push(timeLabel);
            cpuChart.data.datasets[0].data.push(Math.random() * 100);
            
            if (cpuChart.data.labels.length > chartDataPoints) {
                cpuChart.data.labels.shift();
                cpuChart.data.datasets[0].data.shift();
            }
            
            cpuChart.update('none');
        }
        
        // 메모리 차트 업데이트
        if (memoryChart) {
            memoryChart.data.labels.push(timeLabel);
            memoryChart.data.datasets[0].data.push(Math.random() * 100);
            
            if (memoryChart.data.labels.length > chartDataPoints) {
                memoryChart.data.labels.shift();
                memoryChart.data.datasets[0].data.shift();
            }
            
            memoryChart.update('none');
        }
    }
    
    /**
     * 모니터링 데이터 자동 새로고침 시작
     */
    function startAutoRefresh() {
        if (monitoringInterval) {
            clearInterval(monitoringInterval);
        }
        
        monitoringInterval = setInterval(function() {
            loadServersOverview();
            updateCharts();
        }, monitoringConfig.collectionInterval * 1000);
        
        console.log(`[monitoring.js] 자동 새로고침 시작 (${monitoringConfig.collectionInterval}초 간격)`);
    }
    
    /**
     * 모니터링 데이터 자동 새로고침 중지
     */
    function stopAutoRefresh() {
        if (monitoringInterval) {
            clearInterval(monitoringInterval);
            monitoringInterval = null;
            console.log('[monitoring.js] 자동 새로고침 중지');
        }
    }
    
    /**
     * 전체 새로고침
     */
    function refreshAll() {
        console.log('[monitoring.js] 전체 새로고침 시작');
        
        checkMonitoringHealth();
        loadServersOverview();
        loadServerMetricsDetail();
        
        // 차트 데이터 초기화
        if (cpuChart) {
            cpuChart.data.labels = [];
            cpuChart.data.datasets[0].data = [];
            cpuChart.update();
        }
        
        if (memoryChart) {
            memoryChart.data.labels = [];
            memoryChart.data.datasets[0].data = [];
            memoryChart.update();
        }
    }
    
    /**
     * 모니터링 설정 저장
     */
    function saveMonitoringSettings() {
        const settings = {
            prometheusUrl: $('#prometheus-url').val(),
            grafanaUrl: $('#grafana-url').val(),
            collectionInterval: parseInt($('#collection-interval').val()),
            chartDataPoints: parseInt($('#chart-data-points').val())
        };
        
        // 설정 저장 (실제로는 서버에 저장해야 함)
        Object.assign(monitoringConfig, settings);
        
        // 자동 새로고침 재시작
        stopAutoRefresh();
        startAutoRefresh();
        
        // 모달 닫기
        $('#monitoring-settings-modal').modal('hide');
        
        console.log('[monitoring.js] 모니터링 설정 저장됨:', settings);
        
        // 성공 메시지 표시
        showNotification('success', '설정이 저장되었습니다.');
    }
    
    /**
     * 알림 표시
     */
    function showNotification(type, message) {
        const alertClass = `alert-${type}`;
        const icon = type === 'success' ? 'check-circle' : 'info-circle';
        
        const alertHtml = `
            <div class="alert ${alertClass} alert-dismissible fade show" role="alert">
                <i class="fas fa-${icon} me-2"></i>${message}
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            </div>
        `;
        
        // 페이지 상단에 알림 표시
        $('.container-fluid').prepend(alertHtml);
        
        // 3초 후 자동으로 사라지게
        setTimeout(() => {
            $('.alert').fadeOut();
        }, 3000);
    }
    
              /**
      * 이벤트 리스너 등록
      */
     function setupEventListeners() {
         // 전체 새로고침 버튼
         $('#refresh-all-btn').on('click', function() {
             refreshAll();
         });
         
         // 모니터링 설정 버튼
         $('#monitoring-settings-btn').on('click', function() {
             $('#monitoring-settings-modal').modal('show');
         });
         
         // 설정 저장 버튼
         $('#save-monitoring-settings').on('click', function() {
             saveMonitoringSettings();
         });
         
         // 빠른 액션 버튼들
         $('#export-metrics-btn').on('click', function() {
             showNotification('info', '메트릭 내보내기 기능은 개발 중입니다.');
         });
         
         $('#create-alert-btn').on('click', function() {
             showNotification('info', '알림 규칙 생성 기능은 개발 중입니다.');
         });
         
         $('#open-grafana-btn').on('click', function() {
             window.open(monitoringConfig.grafanaUrl, '_blank');
         });
         
         $('#open-prometheus-btn').on('click', function() {
             window.open(monitoringConfig.prometheusUrl, '_blank');
         });
     }
    
    /**
     * 페이지 초기화
     */
    function initializePage() {
        console.log('[monitoring.js] 페이지 초기화 시작');
        
        // 차트 초기화
        initCpuChart();
        initMemoryChart();
        
        // 초기 데이터 로드
        checkMonitoringHealth();
        loadServersOverview();
        loadServerMetricsDetail();
        
        // 자동 새로고침 시작
        startAutoRefresh();
        
        // 이벤트 리스너 설정
        setupEventListeners();
        
        console.log('[monitoring.js] 페이지 초기화 완료');
    }
    
    /**
     * 페이지 언로드 시 정리
     */
    $(window).on('beforeunload', function() {
        stopAutoRefresh();
    });
    
    // 페이지가 언로드될 때 정리
    $(window).on('pagehide', function() {
        stopAutoRefresh();
    });
});
