// instances.js
$(function() {
  // 서버 목록 불러오기 예시
  function loadActiveServers() {
    // 실제 API 연동 필요
    $('#active-server-table tbody').html('<tr><td>server01</td><td>web</td><td>2</td><td>4GB</td><td>192.168.0.10</td><td><span class="badge bg-success">실행 중</span></td><td>-</td></tr>');
  }
  loadActiveServers();
  // 탭 전환 시 서버 목록 새로고침
  $('#list-tab').on('shown.bs.tab', function() {
    loadActiveServers();
  });
}); 