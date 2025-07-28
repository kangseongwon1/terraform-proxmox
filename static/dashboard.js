// dashboard.js
$(function() {
  console.log('[dashboard.js] dashboard.js loaded');
  
  // 숫자 포맷팅 함수
  function format2f(val) {
    if (isNaN(val) || !isFinite(val)) return "0.00";
    return Number(val).toFixed(2);
  }
  
  // 역할명 매핑(한글명)
  window.dashboardRoleMap = {
    web: '웹서버',
    was: 'WAS',
    java: 'JAVA',
    search: '검색',
    ftp: 'FTP',
    db: 'DB'
  };
  
  function updateDashboardStats(stats) {
    console.log('[dashboard.js] updateDashboardStats', stats);
    $('#total-servers').text(stats.total_servers);
    $('#running-servers').text(stats.running_servers);
    $('#stopped-servers').text(stats.stopped_servers);
    $('#total-memory').text(Number(stats.total_memory_gb).toFixed(2));
  }
  
  // 대시보드 서버 요약 패널 렌더링
  function loadDashboardServers() {
    console.log('[dashboard.js] loadDashboardServers 호출');
    $('#dashboard-server-panels').html('<div class="text-center text-muted">서버 정보를 불러오는 중...</div>');
    
    $.get('/all_server_status', function(res) {
      console.log('[dashboard.js] /all_server_status 응답:', res);
      const servers = res.servers || {};
      let html = '';
      
      const statusBadge = s => {
        switch(s.status) {
          case 'running': return '<span class="badge bg-success">실행 중</span>';
          case 'stopped': return '<span class="badge bg-secondary">중지됨</span>';
          case 'paused': return '<span class="badge bg-warning">일시정지</span>';
          case 'suspended': return '<span class="badge bg-info">일시중단</span>';
          default: return `<span class="badge bg-dark">${s.status}</span>`;
        }
      };
      
      const roleName = s => window.dashboardRoleMap && window.dashboardRoleMap[s.role] ? window.dashboardRoleMap[s.role] : (s.role || '-');
      const ipList = s => (s.network_devices && s.network_devices.length > 0) ? s.network_devices.map(nd=>nd.ip_address).join(', ') : '-';
      const serverArr = Object.entries(servers);
      
      if (serverArr.length === 0) {
        html = '<div class="text-center text-muted">등록된 서버가 없습니다.</div>';
      } else {
        html = '<div class="row g-3">';
        serverArr.forEach(([name, s]) => {
          html += `<div class="col-md-4 col-lg-3">
            <div class="dashboard-card h-100 p-3" style="min-height:170px;">
              <div class="d-flex align-items-center mb-2">
                <i class="fas fa-server fa-lg me-2 text-primary"></i>
                <span class="fw-bold">${s.name}</span>
              </div>
              <div class="mb-1"><i class="fas fa-tag me-1"></i> <span class="badge bg-primary">${roleName(s)}</span></div>
              <div class="mb-1"><i class="fas fa-microchip me-1"></i> ${parseInt(s.cpu || 0)}코어 <i class="fas fa-memory ms-2 me-1"></i> ${format2f((s.memory || 0) / 1024 / 1024 / 1024)}GB</div>
              <div class="mb-1"><i class="fas fa-network-wired me-1"></i> ${ipList(s)}</div>
              <div class="mb-1">${statusBadge(s)}</div>
            </div>
          </div>`;
        });
        html += '</div>';
      }
      
      $('#dashboard-server-panels').html(html);
      
      // 통계 업데이트
      if (res.stats) {
        updateDashboardStats(res.stats);
      }
    }).fail(function(xhr) {
      console.error('[dashboard.js] /all_server_status 실패:', xhr);
      $('#dashboard-server-panels').html('<div class="text-center text-danger">서버 정보를 불러오지 못했습니다.</div>');
    });
  }
  
  // 대시보드 스토리지 요약 패널 렌더링
  function loadDashboardStorage() {
    console.log('[dashboard.js] loadDashboardStorage 호출');
    $('#dashboard-storage-panel').html('<div class="text-center text-muted py-4">스토리지 정보를 불러오는 중...</div>');
    
    $.get('/proxmox_storage', function(res) {
      const storages = res.storages || [];
      let html = '';
      
      if (storages.length === 0) {
        html = '<div class="text-center text-muted py-4">등록된 스토리지가 없습니다.</div>';
      } else {
        html = '<div class="table-responsive"><table class="table table-sm table-bordered mb-0"><thead><tr>' +
          '<th>스토리지명</th><th>타입</th><th>총 용량(GB)</th><th>사용 가능(GB)</th><th>사용률</th></tr></thead><tbody>';
        storages.forEach(function(s) {
          const usedPercent = s.total > 0 ? Math.round((s.used / s.total) * 100) : 0;
          const storageType = (s.type === 'lvmthin' || s.type === 'lvm' || s.storage === 'local' || s.storage === 'local-lvm') ? 'HDD' : (s.type === 'dir' ? 'SSD' : s.type);
          html += `<tr>
            <td>${s.storage}</td>
            <td>${storageType}</td>
            <td>${format2f(s.total / 1024 / 1024 / 1024)}</td>
            <td>${format2f((s.total - s.used) / 1024 / 1024 / 1024)}</td>
            <td>
              <div class='progress' style='height: 16px;'>
                <div class='progress-bar' role='progressbar' style='width: ${usedPercent}%;'>${usedPercent}%</div>
              </div>
            </td>
          </tr>`;
        });
        html += '</tbody></table></div>';
      }
      
      $('#dashboard-storage-panel').html(html);
    }).fail(function(xhr) {
      console.error('[dashboard.js] 스토리지 정보 로드 실패:', xhr);
      $('#dashboard-storage-panel').html('<div class="text-center text-danger py-4">스토리지 정보를 불러오지 못했습니다.</div>');
    });
  }
  
  // 최초 진입/새로고침/탭 전환 시 항상 최신 상태로 갱신
  loadDashboardServers();
  loadDashboardStorage();
  
  // 새로고침 버튼 이벤트
  $('#dashboard-refresh-btn').on('click', function() {
    console.log('[dashboard.js] #dashboard-refresh-btn 클릭');
    loadDashboardServers();
  });
  
  $('#dashboard-storage-refresh-btn').on('click', function() {
    console.log('[dashboard.js] #dashboard-storage-refresh-btn 클릭');
    loadDashboardStorage();
  });
}); 
