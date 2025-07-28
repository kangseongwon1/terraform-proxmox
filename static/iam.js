// iam.js
$(function() {
  console.log('[iam.js] iam.js loaded');
  let PERMISSIONS = [];
  let USERS = {};
  let overlayUser = null;
  let selectedPerms = [];

  function showIAMAlert(type, msg) {
    const alert = $('#iam-alert');
    alert.removeClass('d-none alert-success alert-danger alert-info').addClass('alert-' + type).html(`<i class="fas fa-info-circle me-2"></i>${msg}`).fadeIn(200);
    setTimeout(() => alert.fadeOut(200), 2000);
  }

  function renderSummary() {
    const users = Object.values(USERS);
    const total = users.length;
    const admin = users.filter(u=>u.role==='admin').length;
    const dev = users.filter(u=>u.role==='developer').length;
    const op = users.filter(u=>u.role==='operator').length;
    const viewer = users.filter(u=>u.role==='viewer').length;
    const html = `
      <div class='row g-3 mb-3'>
        <div class='col'><div class='card text-center border-primary h-100'><div class='card-body'><div class='fw-bold text-primary mb-1'><i class='fas fa-users'></i> 전체 사용자</div><div class='fs-3'>${total}</div></div></div></div>
        <div class='col'><div class='card text-center border-success h-100'><div class='card-body'><div class='fw-bold text-success mb-1'><i class='fas fa-user-crown'></i> 관리자</div><div class='fs-3'>${admin}</div></div></div></div>
        <div class='col'><div class='card text-center border-info h-100'><div class='card-body'><div class='fw-bold text-info mb-1'><i class='fas fa-user-gear'></i> 개발자</div><div class='fs-3'>${dev}</div></div></div></div>
        <div class='col'><div class='card text-center border-warning h-100'><div class='card-body'><div class='fw-bold text-warning mb-1'><i class='fas fa-user-cog'></i> 오퍼레이터</div><div class='fs-3'>${op}</div></div></div></div>
        <div class='col'><div class='card text-center border-secondary h-100'><div class='card-body'><div class='fw-bold text-secondary mb-1'><i class='fas fa-user'></i> 뷰어</div><div class='fs-3'>${viewer}</div></div></div></div>
      </div>
    `;
    $('#iam-summary-row').html(html);
  }

  function renderTable() {
    const tbody = $('#iam-user-tbody');
    tbody.empty();
    Object.entries(USERS).forEach(([username, user]) => {
      const isAdmin = user.role === 'admin';
      const isInactive = user.is_active === false;
      let tr = $('<tr>').toggleClass('iam-admin-row', isAdmin).toggleClass('table-secondary', isInactive).addClass('iam-user-row').attr('data-username', username);
      tr.append(`<td class="align-middle text-center" style="width:48px;"><i class="fas fa-user-circle iam-profile-icon ${isInactive ? 'text-muted' : ''}"></i></td>`);
      tr.append(`<td class="fw-bold align-middle" style="min-width:100px;">${username} ${isInactive ? '<span class="badge bg-secondary ms-1">비활성</span>' : ''}</td>`);
      tr.append(`<td class="align-middle" style="min-width:180px;">${user.email || ''}</td>`);
      let roleBadge = {
        'admin': 'bg-success',
        'developer': 'bg-info',
        'operator': 'bg-warning',
        'viewer': 'bg-secondary'
      }[user.role] || 'bg-light';
      let roleSel = `<div class="d-flex align-items-center gap-2"><span class="badge ${roleBadge}">${user.role}</span></div>`;
      tr.append(`<td class="align-middle text-center" style="width:110px;">${roleSel}</td>`);
      tr.append(`<td class="align-middle text-center" style="width:140px;"><button class="btn btn-outline-primary btn-sm iam-expand-btn w-100" data-username="${username}"><i class="fas fa-edit"></i> 권한 관리</button></td>`);
      tbody.append(tr);
    });
    tbody.find('tr.iam-user-row').hover(
      function() { $(this).addClass('table-primary'); },
      function() { $(this).removeClass('table-primary'); }
    );
  }

  // 오버레이 권한 카드 렌더링 (개선된 UI)
  function renderPermCardsOverlay(username) {
    const user = USERS[username];
    if (!user) return '';
    let perms = selectedPerms.length ? selectedPerms : user.permissions;
    // 왼쪽: 부여되지 않은 권한, 오른쪽: 부여된 권한
    const unassigned = PERMISSIONS.filter(p => !perms.includes(p));
    const assigned = perms;
    
    // 권한 설명 매핑
    const permDescriptions = {
      'view_all': '모든 리소스 조회',
      'create_server': '서버 생성',
      'delete_server': '서버 삭제',
      'start_server': '서버 시작',
      'stop_server': '서버 중지',
      'manage_users': '사용자 관리',
      'manage_roles': '역할 관리',
      'view_logs': '로그 조회',
      'manage_storage': '스토리지 관리',
      'manage_network': '네트워크 관리'
    };
    
    let html = `
      <div class="iam-overlay-header mb-4">
        <div class="d-flex align-items-center">
          <div class="iam-user-avatar me-3">
            <i class="fas fa-user-circle fa-3x text-primary"></i>
          </div>
          <div>
            <h5 class="mb-1">${username}</h5>
            <div class="d-flex align-items-center gap-2">
              <span class="badge ${user.role==='admin'?'bg-success':user.role==='developer'?'bg-info':user.role==='operator'?'bg-warning':'bg-secondary'} fs-6">${user.role}</span>
              <span class="text-muted">${user.email || ''}</span>
            </div>
          </div>
        </div>
      </div>
      
      <div class="iam-permissions-container">
        <div class="row g-4">
          <!-- 권한 풀 -->
          <div class="col-md-6">
            <div class="iam-perm-section">
              <div class="iam-section-header">
                <i class="fas fa-plus-circle text-primary me-2"></i>
                <h6 class="mb-0">사용 가능한 권한</h6>
                <span class="badge bg-primary ms-2">${unassigned.length}</span>
              </div>
              <div id="perm-pool-list" class="iam-perm-list">
                ${unassigned.length > 0 ? unassigned.map(perm => `
                  <div class="iam-perm-item" data-perm="${perm}" draggable="true">
                    <div class="iam-perm-content">
                      <i class="fas fa-key text-primary me-2"></i>
                      <div class="iam-perm-info">
                        <div class="iam-perm-name">${perm}</div>
                        <div class="iam-perm-desc">${permDescriptions[perm] || '권한 설명'}</div>
                      </div>
                      <i class="fas fa-arrow-right text-muted"></i>
                    </div>
                  </div>
                `).join('') : '<div class="iam-empty-state"><i class="fas fa-check-circle text-success fa-2x mb-2"></i><div>모든 권한이 부여되었습니다</div></div>'}
              </div>
            </div>
          </div>
          
          <!-- 부여된 권한 -->
          <div class="col-md-6">
            <div class="iam-perm-section">
              <div class="iam-section-header">
                <i class="fas fa-check-circle text-success me-2"></i>
                <h6 class="mb-0">부여된 권한</h6>
                <span class="badge bg-success ms-2">${assigned.length}</span>
              </div>
              <div id="perm-assigned-list" class="iam-perm-list">
                ${assigned.length > 0 ? assigned.map(perm => `
                  <div class="iam-perm-item assigned" data-perm="${perm}" draggable="true">
                    <div class="iam-perm-content">
                      <i class="fas fa-key text-success me-2"></i>
                      <div class="iam-perm-info">
                        <div class="iam-perm-name">${perm}</div>
                        <div class="iam-perm-desc">${permDescriptions[perm] || '권한 설명'}</div>
                      </div>
                      <i class="fas fa-arrow-left text-muted"></i>
                    </div>
                  </div>
                `).join('') : '<div class="iam-empty-state"><i class="fas fa-exclamation-circle text-warning fa-2x mb-2"></i><div>부여된 권한이 없습니다</div></div>'}
              </div>
            </div>
          </div>
        </div>
      </div>
      
      <div class="iam-overlay-footer mt-4">
        <div class="d-flex justify-content-between align-items-center">
          <div class="iam-help-text">
            <i class="fas fa-info-circle text-info me-1"></i>
            <small class="text-muted">드래그하거나 클릭하여 권한을 이동할 수 있습니다</small>
          </div>
          <div class="iam-actions">
            <button class="btn btn-outline-secondary btn-sm me-2" id="iam-cancel-btn">
              <i class="fas fa-times me-1"></i>취소
            </button>
            <button class="btn btn-success btn-sm iam-save-perm-btn" data-username="${username}" disabled>
              <i class="fas fa-save me-1"></i>변경사항 적용
            </button>
          </div>
        </div>
      </div>
    `;
    return html;
  }

  function loadIAM() {
    console.log('[iam.js] loadIAM 호출');
    $('#iam-loading').removeClass('d-none');
    $.get('/admin/iam', function(res) {
      console.log('[iam.js] /admin/iam 응답:', res);
      USERS = res.users;
      PERMISSIONS = res.permissions;
      renderSummary();
      renderTable();
      $('#iam-loading').addClass('d-none');
      overlayUser = null;
      selectedPerms = [];
      $('#iam-overlay').hide();
      $('#iam-overlay-content').empty();
    }).fail(function(xhr) {
      console.error('[iam.js] /admin/iam 실패:', xhr);
    });
  }

  // 권한 관리 버튼 클릭 시 오버레이 띄우기
  $(document).off('click', '.iam-expand-btn').on('click', '.iam-expand-btn', function(e) {
    console.log('[iam.js] .iam-expand-btn 클릭', $(this).data('username'));
    e.stopPropagation();
    const username = $(this).data('username');
    overlayUser = username;
    selectedPerms = [...USERS[username].permissions];
    const html = renderPermCardsOverlay(username);
    $('#iam-overlay-content').html(html);
    $('#iam-overlay').fadeIn(120);
  });

  // 오버레이 닫기
  $(document).off('click', '#iam-overlay-close').on('click', '#iam-overlay-close', function() {
    console.log('[iam.js] #iam-overlay-close 클릭');
    $('#iam-overlay').fadeOut(120);
    overlayUser = null;
    selectedPerms = [];
    $('#iam-overlay-content').empty();
  });

  // 오버레이 바깥 클릭 시 닫기
  $(document).off('mousedown', '#iam-overlay').on('mousedown', '#iam-overlay', function(e) {
    if (e.target === this) {
      console.log('[iam.js] #iam-overlay 바깥 클릭');
      $('#iam-overlay').fadeOut(120);
      overlayUser = null;
      selectedPerms = [];
      $('#iam-overlay-content').empty();
    }
  });

  // 새로운 권한 아이템 드래그 앤 드롭
  let dragPerm = null;
  $(document).off('dragstart', '.iam-perm-item').on('dragstart', '.iam-perm-item', function(e) {
    dragPerm = $(this).data('perm');
    $(this).addClass('dragging');
  });
  $(document).off('dragend', '.iam-perm-item').on('dragend', '.iam-perm-item', function(e) {
    dragPerm = null;
    $(this).removeClass('dragging');
  });
  
  // 드롭 영역 설정
  $(document).off('dragover', '.iam-perm-list').on('dragover', '.iam-perm-list', function(e) {
    e.preventDefault();
    $(this).addClass('drag-over');
  });
  $(document).off('dragleave', '.iam-perm-list').on('dragleave', '.iam-perm-list', function(e) {
    $(this).removeClass('drag-over');
  });
  $(document).off('drop', '.iam-perm-list').on('drop', '.iam-perm-list', function(e) {
    e.preventDefault();
    $(this).removeClass('drag-over');
    if (!dragPerm) return;
    
    const isAssignedList = $(this).attr('id') === 'perm-assigned-list';
    const isPoolList = $(this).attr('id') === 'perm-pool-list';
    
    if (isAssignedList && !selectedPerms.includes(dragPerm)) {
      // 권한 풀 → 부여된 권한
      selectedPerms.push(dragPerm);
      const html = renderPermCardsOverlay(overlayUser);
      $('#iam-overlay-content').html(html);
      $(`.iam-save-perm-btn[data-username='${overlayUser}']`).prop('disabled', false);
    } else if (isPoolList && selectedPerms.includes(dragPerm)) {
      // 부여된 권한 → 권한 풀
      selectedPerms = selectedPerms.filter(p => p !== dragPerm);
      const html = renderPermCardsOverlay(overlayUser);
      $('#iam-overlay-content').html(html);
      $(`.iam-save-perm-btn[data-username='${overlayUser}']`).prop('disabled', false);
    }
  });
  
  // 클릭으로 권한 이동
  $(document).off('click', '.iam-perm-item').on('click', '.iam-perm-item', function() {
    const perm = $(this).data('perm');
    const isAssigned = $(this).hasClass('assigned');
    
    if (isAssigned) {
      // 부여된 권한 → 권한 풀
      if (selectedPerms.includes(perm)) {
        selectedPerms = selectedPerms.filter(p => p !== perm);
        const html = renderPermCardsOverlay(overlayUser);
        $('#iam-overlay-content').html(html);
        $(`.iam-save-perm-btn[data-username='${overlayUser}']`).prop('disabled', false);
      }
    } else {
      // 권한 풀 → 부여된 권한
      if (!selectedPerms.includes(perm)) {
        selectedPerms.push(perm);
        const html = renderPermCardsOverlay(overlayUser);
        $('#iam-overlay-content').html(html);
        $(`.iam-save-perm-btn[data-username='${overlayUser}']`).prop('disabled', false);
      }
    }
  });
  
  // 취소 버튼
  $(document).off('click', '#iam-cancel-btn').on('click', '#iam-cancel-btn', function() {
    $('#iam-overlay').fadeOut(120);
    overlayUser = null;
    selectedPerms = [];
    $('#iam-overlay-content').empty();
  });

  // 권한 저장 버튼 클릭 (오버레이 내부)
  $(document).off('click', '.iam-save-perm-btn').on('click', '.iam-save-perm-btn', function() {
    console.log('[iam.js] .iam-save-perm-btn 클릭', $(this).data('username'), selectedPerms);
    const username = $(this).data('username');
    $.ajax({
      url: `/admin/iam/${username}/permissions`,
      method: 'POST',
      contentType: 'application/json',
      data: JSON.stringify({ permissions: selectedPerms }),
      beforeSend: function() {
        console.log('[iam.js] /admin/iam/permissions 요청 전', username, selectedPerms);
      },
      success: function(res) {
        console.log('[iam.js] /admin/iam/permissions 성공', res);
        showIAMAlert('success', res.message);
        loadIAM();
      },
      error: function(xhr) {
        console.error('[iam.js] /admin/iam/permissions 실패', xhr);
        showIAMAlert('danger', xhr.responseJSON?.error || '권한 변경 실패');
      }
    });
  });

  // 초기 로드
  loadIAM();
}); 