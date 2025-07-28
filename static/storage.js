// storage.js
$(function() {
  console.log('[storage.js] storage.js loaded');
ㄱ  
  // 숫자 포맷팅 함수 (index.html에서 가져옴)
  function format2f(val) {
    if (isNaN(val) || !isFinite(val)) return "0.00";
    return Number(val).toFixed(2);
  }
  function loadStorageInfo() {
    console.log('[storage.js] loadStorageInfo 호출');
    
    // 로딩 상태 표시
    $('#storage-table tbody').html('<tr><td colspan="5" class="text-center text-muted py-4">스토리지 정보를 불러오는 중...</td></tr>');
    
    // 실제 API 연동
    $.get('/proxmox_storage', function(res) {
      const storages = res.storages || [];
      let html = '';
      
      if (storages.length === 0) {
        html = '<tr><td colspan="5" class="text-center text-muted py-4">등록된 스토리지가 없습니다.</td></tr>';
      } else {
        storages.forEach(function(s) {
          const usedPercent = s.total > 0 ? Math.round((s.used / s.total) * 100) : 0;
          const totalGB = format2f(s.total / 1024 / 1024 / 1024);
          const availableGB = format2f((s.total - s.used) / 1024 / 1024 / 1024);
          const storageType = s.type === 'lvmthin' ? 'HDD' : (s.type === 'dir' ? 'SSD' : s.type);
          
          html += `<tr>
            <td>${s.storage}</td>
            <td>${storageType}</td>
            <td>${totalGB}</td>
            <td>${availableGB}</td>
            <td>
              <div class='progress' style='height: 16px;'>
                <div class='progress-bar' role='progressbar' style='width: ${usedPercent}%;'>${usedPercent}%</div>
              </div>
            </td>
          </tr>`;
        });
      }
      
      $('#storage-table tbody').html(html);
      console.log('[storage.js] 스토리지 테이블 렌더링 완료');
    }).fail(function(xhr) {
      console.error('[storage.js] 스토리지 정보 로드 실패:', xhr);
      $('#storage-table tbody').html('<tr><td colspan="5" class="text-center text-danger py-4">스토리지 정보를 불러오지 못했습니다.</td></tr>');
    });
  }
  loadStorageInfo();
  $('#storage-refresh-btn').on('click', function() {
    console.log('[storage.js] #storage-refresh-btn 클릭');
    loadStorageInfo();
  });

  
}); 