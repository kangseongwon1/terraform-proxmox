// dashboard.js
$(function() {
  function updateDashboardStats(stats) {
    $('#total-servers').text(stats.total_servers);
    $('#running-servers').text(stats.running_servers);
    $('#stopped-servers').text(stats.stopped_servers);
    $('#total-memory').text(Number(stats.total_memory_gb).toFixed(2));
  }
  function loadDashboardServers() {
    $.get('/all_server_status', function(res) {
      // 서버 목록/카드 등 렌더링은 기존대로...
      if (res.stats) {
        updateDashboardStats(res.stats);
      }
      // 서버 요약 패널 등 추가 렌더링 필요시 여기에...
    });
  }
  // 최초 진입/새로고침/탭 전환 시 항상 최신 상태로 갱신
  loadDashboardServers();
  $('#dashboard-refresh-btn').on('click', loadDashboardServers);
  // 필요시 SPA 해시 변경 등에도 연동
}); 