// iam.js
$(function() {
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
      tr.append(`<td class="fw-bold align-middle" style="min-width:120px;">${username} ${isInactive ? '<span class="badge bg-secondary ms-1">비활성</span>' : ''}</td>`);
      tr.append(`<td class="align-middle" style="min-width:180px;">${user.email || ''}</td>`);
      let roleBadge = {
        'admin': 'bg-success',
        'developer': 'bg-info',
        'operator': 'bg-warning',
        'viewer': 'bg-secondary'
      }[user.role] || 'bg-light';
      let roleSel = `<div class="d-flex align-items-center gap-2"><span class="badge ${roleBadge}">${user.role}</span></div>`;
      tr.append(`<td class="align-middle text-center" style="width:110px;">${roleSel}</td>`);
      tr.append(`<td class="align-middle text-center" style="width:120px;"><button class="btn btn-outline-primary btn-sm iam-expand-btn w-100" data-username="${username}"><i class="fas fa-edit"></i> 권한 관리</button></td>`);
      tbody.append(tr);
    });
    tbody.find('tr.iam-user-row').hover(
      function() { $(this).addClass('table-primary'); },
      function() { $(this).removeClass('table-primary'); }
    );
  }

  // 오버레이 권한 카드 렌더링 (왼: 권한 풀, 오: 유저 권한 슬롯)
  function renderPermCardsOverlay(username) {
    const user = USERS[username];
    if (!user) return '';
    let perms = selectedPerms.length ? selectedPerms : user.permissions;
    // 왼쪽: 부여되지 않은 권한, 오른쪽: 부여된 권한
    const unassigned = PERMISSIONS.filter(p => !perms.includes(p));
    const assigned = perms;
    let html = `<div style="display:flex; gap:32px; align-items:flex-start; min-height:220px;">
      <div style="flex:1; min-width:180px; max-width:220px; text-align:center;">
        <i class="fas fa-user-circle fa-2x me-2"></i><span class="fw-bold">${username}</span>
        <span class="badge ms-2 ${user.role==='admin'?'bg-success':user.role==='developer'?'bg-info':user.role==='operator'?'bg-warning':'bg-secondary'}">${user.role}</span>
        <div class="text-muted small mt-1">${user.email || ''}</div>
      </div>
      <div style="flex:1; min-width:180px;">
        <div class="mb-2 fw-bold text-primary">권한 풀</div>
        <div id="perm-pool-list" style="display:flex; flex-direction:column; gap:10px; align-items:stretch; min-height:120px; max-height:180px; overflow-y:auto; background:#f6fafd; border-radius:8px; padding:8px 0;">
          ${unassigned.map(perm => `<button class="perm-pool-btn btn btn-outline-primary text-start d-flex align-items-center gap-2" data-perm="${perm}" draggable="true" style="font-size:1.08em; font-weight:500; padding:8px 14px; border-radius:8px;"><i class="fas fa-key"></i> ${perm}</button>`).join('')}
        </div>
      </div>
      <div style="flex:1; min-width:180px;">
        <div class="mb-2 fw-bold text-success">부여된 권한</div>
        <div id="perm-assigned-list" style="display:flex; flex-direction:column; gap:10px; align-items:stretch; min-height:120px; max-height:180px; overflow-y:auto; background:#f6fff6; border-radius:8px; padding:8px 0;">
          ${assigned.map(perm => `<button class="perm-assigned-btn btn btn-primary text-white text-start d-flex align-items-center gap-2" data-perm="${perm}" draggable="true" style="font-size:1.08em; font-weight:500; padding:8px 14px; border-radius:8px;"><i class="fas fa-key"></i> ${perm}</button>`).join('')}
        </div>
      </div>
    </div>`;
    html += `<div class="text-end mt-4"><button class="btn btn-success btn-sm iam-save-perm-btn" data-username="${username}" disabled style="min-width:90px;"><i class="fas fa-save me-1"></i>적용</button></div>`;
    html += `<div class="mt-3 text-center text-muted small">왼쪽에서 드래그하여 권한을 부여, 오른쪽에서 드래그하여 권한을 해제할 수 있습니다.</div>`;
    return html;
  }

  function loadIAM() {
    $('#iam-loading').removeClass('d-none');
    $.get('/admin/iam', function(res) {
      USERS = res.users;
      PERMISSIONS = res.permissions;
      renderSummary();
      renderTable();
      $('#iam-loading').addClass('d-none');
      overlayUser = null;
      selectedPerms = [];
      $('#iam-overlay').hide();
      $('#iam-overlay-content').empty();
    });
  }

  // 권한 관리 버튼 클릭 시 오버레이 띄우기
  $(document).off('click', '.iam-expand-btn').on('click', '.iam-expand-btn', function(e) {
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
    $('#iam-overlay').fadeOut(120);
    overlayUser = null;
    selectedPerms = [];
    $('#iam-overlay-content').empty();
  });

  // 오버레이 바깥 클릭 시 닫기
  $(document).off('mousedown', '#iam-overlay').on('mousedown', '#iam-overlay', function(e) {
    if (e.target === this) {
      $('#iam-overlay').fadeOut(120);
      overlayUser = null;
      selectedPerms = [];
      $('#iam-overlay-content').empty();
    }
  });

  // 권한 풀에서 드래그 시작
  let dragPerm = null;
  $(document).off('dragstart', '.perm-pool-btn').on('dragstart', '.perm-pool-btn', function(e) {
    dragPerm = $(this).data('perm');
    $(this).addClass('opacity-50');
  });
  $(document).off('dragend', '.perm-pool-btn').on('dragend', '.perm-pool-btn', function(e) {
    dragPerm = null;
    $(this).removeClass('opacity-50');
  });
  // 부여된 권한에서 드래그 시작
  $(document).off('dragstart', '.perm-assigned-btn').on('dragstart', '.perm-assigned-btn', function(e) {
    dragPerm = $(this).data('perm');
    $(this).addClass('opacity-50');
  });
  $(document).off('dragend', '.perm-assigned-btn').on('dragend', '.perm-assigned-btn', function(e) {
    dragPerm = null;
    $(this).removeClass('opacity-50');
  });
  // 드롭: 권한 풀 → 부여된 권한
  $(document).off('dragover', '#perm-assigned-list').on('dragover', '#perm-assigned-list', function(e) {
    e.preventDefault();
  });
  $(document).off('drop', '#perm-assigned-list').on('drop', '#perm-assigned-list', function(e) {
    e.preventDefault();
    if (!dragPerm) return;
    if (!selectedPerms.includes(dragPerm)) {
      selectedPerms.push(dragPerm);
      const html = renderPermCardsOverlay(overlayUser);
      $('#iam-overlay-content').html(html);
      $(`.iam-save-perm-btn[data-username='${overlayUser}']`).prop('disabled', false);
    }
  });
  // 드롭: 부여된 권한 → 권한 풀
  $(document).off('dragover', '#perm-pool-list').on('dragover', '#perm-pool-list', function(e) {
    e.preventDefault();
  });
  $(document).off('drop', '#perm-pool-list').on('drop', '#perm-pool-list', function(e) {
    e.preventDefault();
    if (!dragPerm) return;
    if (selectedPerms.includes(dragPerm)) {
      selectedPerms = selectedPerms.filter(p => p !== dragPerm);
      const html = renderPermCardsOverlay(overlayUser);
      $('#iam-overlay-content').html(html);
      $(`.iam-save-perm-btn[data-username='${overlayUser}']`).prop('disabled', false);
    }
  });
  // 클릭 토글도 지원
  $(document).off('click', '.perm-pool-btn').on('click', '.perm-pool-btn', function() {
    const perm = $(this).data('perm');
    if (!selectedPerms.includes(perm)) {
      selectedPerms.push(perm);
      const html = renderPermCardsOverlay(overlayUser);
      $('#iam-overlay-content').html(html);
      $(`.iam-save-perm-btn[data-username='${overlayUser}']`).prop('disabled', false);
    }
  });
  $(document).off('click', '.perm-assigned-btn').on('click', '.perm-assigned-btn', function() {
    const perm = $(this).data('perm');
    if (selectedPerms.includes(perm)) {
      selectedPerms = selectedPerms.filter(p => p !== perm);
      const html = renderPermCardsOverlay(overlayUser);
      $('#iam-overlay-content').html(html);
      $(`.iam-save-perm-btn[data-username='${overlayUser}']`).prop('disabled', false);
    }
  });

  // 권한 저장 버튼 클릭 (오버레이 내부)
  $(document).off('click', '.iam-save-perm-btn').on('click', '.iam-save-perm-btn', function() {
    const username = $(this).data('username');
    $.ajax({
      url: `/admin/iam/${username}/permissions`,
      method: 'POST',
      contentType: 'application/json',
      data: JSON.stringify({ permissions: selectedPerms }),
      success: function(res) {
        showIAMAlert('success', res.message);
        loadIAM();
      },
      error: function(xhr) {
        showIAMAlert('danger', xhr.responseJSON?.error || '권한 변경 실패');
      }
    });
  });

  // 초기 로드
  loadIAM();
}); 