// storage.js
$(function() {
  function loadStorageInfo() {
    // 실제 API 연동 필요
    $('#storage-table tbody').html('<tr><td>ssd</td><td>SSD</td><td>1759.32</td><td>1735.15</td><td>12%</td></tr>');
  }
  loadStorageInfo();
  $('#storage-refresh-btn').on('click', function() {
    loadStorageInfo();
  });
}); 