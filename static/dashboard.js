// dashboard.js
$(function() {
  // 서버/스토리지 요약 정보 불러오기 예시
  function loadDashboardSummary() {
    // 실제 API 연동 필요
    $('#total-servers').text('3');
    $('#running-servers').text('2');
    $('#stopped-servers').text('1');
    $('#total-memory').text('64');
  }
  loadDashboardSummary();
  // 새로고침 버튼 이벤트
  $('#dashboard-refresh-btn, #dashboard-storage-refresh-btn').on('click', function() {
    loadDashboardSummary();
  });
}); 