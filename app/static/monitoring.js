// app/static/monitoring.js
$(document).ready(function() {
    // 전역 변수
    let charts = {};
    let selectedServer = 'all';
    let autoRefresh = true;
    let refreshInterval;
    
    // 서버 목록 (설정 파일에서 가져올 예정)
    const servers = [
        { ip: '192.168.0.10', port: '22', status: 'healthy' },
        { ip: '192.168.0.111', port: '20222', status: 'healthy' },
        { ip: '192.168.0.112', port: '20222', status: 'warning' },
        { ip: '192.168.0.113', port: '20222', status: 'healthy' },
        { ip: '192.168.0.114', port: '20222', status: 'healthy' },
        { ip: '192.168.0.115', port: '20222', status: 'healthy' },
        { ip: '192.168.0.116', port: '20222', status: 'healthy' },
        { ip: '192.168.0.117', port: '20222', status: 'critical' },
        { ip: '192.168.0.118', port: '20222', status: 'healthy' },
        { ip: '192.168.0.119', port: '20222', status: 'healthy' }
    ];

    // 초기화
    init();

    function init() {
        loadServersOverview();
        setupEventListeners();
        initializeCharts();
        startAutoRefresh();
        loadGrafanaDashboard();
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
        const healthy = servers.filter(s => s.status === 'healthy').length;
        const warning = servers.filter(s => s.status === 'warning').length;
        const critical = servers.filter(s => s.status === 'critical').length;

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
            // ● 기호 제거하고 IP:PORT만 표시
            const option = `<option value="${server.ip}">${server.ip}:${server.port}</option>`;
            $select.append(option);
        });
    }

    // 상태 아이콘 반환 (심플하게)
    function getStatusIcon(status) {
        switch(status) {
            case 'healthy': return '●';  // 검은색 원
            case 'warning': return '●';  // 검은색 원
            case 'critical': return '●';  // 검은색 원
            default: return '●';         // 검은색 원
        }
    }

    // 상태 배지 업데이트
    function updateStatusBadge() {
        const selectedServerData = servers.find(s => s.ip === selectedServer) || { status: 'healthy' };
        const $badge = $('#status-badge');
        const $lastUpdate = $('#last-update');

        $badge.removeClass().addClass('badge me-2');
        
        switch(selectedServerData.status) {
            case 'healthy':
                $badge.addClass('bg-success').html('정상');
                break;
            case 'warning':
                $badge.addClass('bg-warning').html('경고');
                break;
            case 'critical':
                $badge.addClass('bg-danger').html('위험');
                break;
        }

        $lastUpdate.text(`마지막 업데이트: ${new Date().toLocaleTimeString()}`);
    }

    // 이벤트 리스너 설정
    function setupEventListeners() {
        // 서버 선택 변경
        $('#server-select').on('change', function() {
            selectedServer = $(this).val();
            updateCharts();
            updateStatusBadge();
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

    // 차트 초기화
    function initializeCharts() {
        // CPU 차트
        charts.cpu = new Chart(document.getElementById('cpuChart'), {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'CPU 사용률 (%)',
                    data: [],
                    borderColor: 'rgb(75, 192, 192)',
                    backgroundColor: 'rgba(75, 192, 192, 0.2)',
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

        // 메모리 차트
        charts.memory = new Chart(document.getElementById('memoryChart'), {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: '메모리 사용률 (%)',
                    data: [],
                    borderColor: 'rgb(255, 99, 132)',
                    backgroundColor: 'rgba(255, 99, 132, 0.2)',
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

        // 디스크 차트
        charts.disk = new Chart(document.getElementById('diskChart'), {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: '디스크 사용률 (%)',
                    data: [],
                    borderColor: 'rgb(54, 162, 235)',
                    backgroundColor: 'rgba(54, 162, 235, 0.2)',
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

        // 네트워크 차트
        charts.network = new Chart(document.getElementById('networkChart'), {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: '네트워크 대역폭 사용률 (%)',
                    data: [],
                    borderColor: 'rgb(255, 205, 86)',
                    backgroundColor: 'rgba(255, 205, 86, 0.2)',
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

    // 차트 업데이트
    function updateCharts() {
        const now = new Date().toLocaleTimeString();
        
        // 샘플 데이터 (실제로는 Prometheus API에서 가져올 예정)
        const cpuUsage = Math.random() * 100;
        const memoryUsage = Math.random() * 100;
        const diskUsage = Math.random() * 100;
        const networkUsage = Math.random() * 100;

        // CPU 차트 업데이트
        updateChart(charts.cpu, now, cpuUsage);
        
        // 메모리 차트 업데이트
        updateChart(charts.memory, now, memoryUsage);
        
        // 디스크 차트 업데이트
        updateChart(charts.disk, now, diskUsage);
        
        // 네트워크 차트 업데이트
        updateChart(charts.network, now, networkUsage);
    }

    // 개별 차트 업데이트
    function updateChart(chart, label, value) {
        chart.data.labels.push(label);
        chart.data.datasets[0].data.push(value);

        // 최대 20개 데이터 포인트 유지
        if (chart.data.labels.length > 20) {
            chart.data.labels.shift();
            chart.data.datasets[0].data.shift();
        }

        chart.update('none');
    }

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
        }, 5000); // 5초마다 업데이트
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

    // Grafana 대시보드 로드
    function loadGrafanaDashboard() {
        // 대시보드 정보 파일에서 URL 가져오기
        $.getJSON('/tmp/dashboard_info.json')
            .done(function(data) {
                const dashboardUrl = data.full_url;
                $('#grafana-dashboard').attr('src', dashboardUrl);
            })
            .fail(function() {
                // 기본 URL 사용
                const defaultUrl = 'http://localhost:3000/d/system_monitoring/system-monitoring-dashboard-10-servers';
                $('#grafana-dashboard').attr('src', defaultUrl);
            });
    }
});