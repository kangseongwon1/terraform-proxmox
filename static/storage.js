// storage.js
$(function() {
  console.log('[storage.js] storage.js loaded');
  function loadStorageInfo() {
    console.log('[storage.js] loadStorageInfo 호출');
    // 실제 API 연동 필요
    $('#storage-table tbody').html('<tr><td>ssd</td><td>SSD</td><td>1759.32</td><td>1735.15</td><td>12%</td></tr>');
    console.log('[storage.js] 스토리지 테이블 렌더링 완료');
  }
  loadStorageInfo();
  $('#storage-refresh-btn').on('click', function() {
    console.log('[storage.js] #storage-refresh-btn 클릭');
    loadStorageInfo();
  });
}); 