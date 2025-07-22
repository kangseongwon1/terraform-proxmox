// instances.js
$(function() {
  // 서버 목록 불러오기 (기존 index.html 구조 100% 복원)
  function loadActiveServers() {
    $.get('/all_server_status', function(res) {
      let html = '';
      for (const [name, s] of Object.entries(res.servers)) {
        // 상태별 배지 색상 결정
        let statusBadge = '';
        switch(s.status) {
          case 'running': statusBadge = '<span class="badge bg-success">실행 중</span>'; break;
          case 'stopped': statusBadge = '<span class="badge bg-secondary">중지됨</span>'; break;
          case 'paused': statusBadge = '<span class="badge bg-warning">일시정지</span>'; break;
          case 'suspended': statusBadge = '<span class="badge bg-info">일시중단</span>'; break;
          default: statusBadge = '<span class="badge bg-dark">' + s.status + '</span>';
        }
        // 역할 드롭다운
        let roleOptions = '<option value="">(선택 안 함)</option>';
        for (const [k, v] of Object.entries(window.dashboardRoleMap)) {
          roleOptions += `<option value="${k}"${s.role===k?' selected':''}>${v}</option>`;
        }
        html += `<tr data-server="${name}">
          <td><a href="#" class="server-detail-link" data-server="${name}"><strong>${s.name}</strong></a></td>
          <td>
            <div class="d-flex align-items-center gap-2">
              <select class="form-select form-select-sm server-role-select" style="min-width:110px;">
                ${roleOptions}
              </select>
              <button class="btn btn-outline-primary btn-sm server-role-apply"><i class="fas fa-check"></i> <span>역할 적용</span></button>
              <button class="btn btn-outline-danger btn-sm server-role-remove"${s.role?'':' disabled'}><i class="fas fa-trash"></i> <span>역할 삭제</span></button>
            </div>
          </td>
          <td>${parseInt(s.cpu || 0)}코어</td>
          <td>${format2f((s.memory || 0) / 1024 / 1024 / 1024)}GB</td>
          <td>${(s.network_devices && s.network_devices.length > 0) ? s.network_devices.map(nd=>nd.ip_address).join(', ') : '-'}</td>
          <td>${statusBadge}</td>
          <td>
            <div class="btn-group" role="group">
              <button class="btn btn-success btn-sm start-btn" title="시작" ${s.status === 'running' ? 'disabled' : ''}>
                <i class="fas fa-play"></i> 시작
              </button>
              <button class="btn btn-info btn-sm stop-btn" title="중지" ${s.status === 'stopped' ? 'disabled' : ''}>
                <i class="fas fa-pause"></i> 중지
              </button>
              <button class="btn btn-warning btn-sm reboot-btn" title="리부팅" ${s.status === 'stopped' ? 'disabled' : ''}>
                <i class="fas fa-redo"></i> 리부팅
              </button>
              <button class="btn btn-danger btn-sm delete-btn" title="삭제">
                <i class="fas fa-trash"></i> 삭제
              </button>
            </div>
          </td>
        </tr>`;
      }
      $('#active-server-table tbody').html(html);
    });
  }
  loadActiveServers();
  // 탭 전환 시 서버 목록 새로고침
  $('#list-tab').on('shown.bs.tab', function() {
    loadActiveServers();
  });
  // 역할 적용/삭제, 서버 액션 버튼 등 기존 이벤트 핸들러도 index.html과 동일하게 추가되어야 함
}); 