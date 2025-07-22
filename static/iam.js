// iam.js
$(function() {
  let PERMISSIONS = [];
  let USERS = {};
  function showIAMAlert(type, msg) {
    const alert = $('#iam-alert');
    alert.removeClass('d-none alert-success alert-danger alert-info').addClass('alert-' + type).html(`<i class="fas fa-info-circle me-2"></i>${msg}`).fadeIn(200);
    setTimeout(() => alert.fadeOut(200), 2000);
  }
  function renderSummary() {
    // 요약 카드: 전체 유저 수, 역할별 수
    const users = Object.values(USERS);
    const total = users.length;
    const admin = users.filter(u=>u.role==='admin').length;
    const dev = users.filter(u=>u.role==='developer').length;
    const op = users.filter(u=>u.role==='operator').length;
    const viewer = users.filter(u=>u.role==='viewer').length;
    const html = `
      <div class='row g-3 mb-3'>
        <div class='col'>
          <div class='card text-center border-primary h-100'>
            <div class='card-body'>
              <div class='fw-bold text-primary mb-1'><i class='fas fa-users'></i> 전체 사용자</div>
              <div class='fs-3'>${total}</div>
            </div>
          </div>
        </div>
        <div class='col'>
          <div class='card text-center border-success h-100'>
            <div class='card-body'>
              <div class='fw-bold text-success mb-1'><i class='fas fa-user-crown'></i> 관리자</div>
              <div class='fs-3'>${admin}</div>
            </div>
          </div>
        </div>
        <div class='col'>
          <div class='card text-center border-info h-100'>
            <div class='card-body'>
              <div class='fw-bold text-info mb-1'><i class='fas fa-user-gear'></i> 개발자</div>
              <div class='fs-3'>${dev}</div>
            </div>
          </div>
        </div>
        <div class='col'>
          <div class='card text-center border-warning h-100'>
            <div class='card-body'>
              <div class='fw-bold text-warning mb-1'><i class='fas fa-user-cog'></i> 오퍼레이터</div>
              <div class='fs-3'>${op}</div>
            </div>
          </div>
        </div>
        <div class='col'>
          <div class='card text-center border-secondary h-100'>
            <div class='card-body'>
              <div class='fw-bold text-secondary mb-1'><i class='fas fa-user'></i> 뷰어</div>
              <div class='fs-3'>${viewer}</div>
            </div>
          </div>
        </div>
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
      let tr = $('<tr>').toggleClass('iam-admin-row', isAdmin).toggleClass('table-secondary', isInactive);
      // 프로필/상태
      tr.append(`<td><i class="fas fa-user-circle iam-profile-icon ${isInactive ? 'text-muted' : ''}"></i></td>`);
      // 사용자명
      tr.append(`<td class="fw-bold align-middle">${username} ${isInactive ? '<span class="badge bg-secondary ms-1">비활성</span>' : ''}</td>`);
      // 이메일
      tr.append(`<td class="align-middle">${user.email || ''}</td>`);
      // 역할 드롭다운 + 뱃지
      let roleBadge = {
        'admin': 'bg-success',
        'developer': 'bg-info',
        'operator': 'bg-warning',
        'viewer': 'bg-secondary'
      }[user.role] || 'bg-light';
      let roleSel = `<div class="d-flex align-items-center gap-2">
        <select class="form-select form-select-sm iam-role-select" data-username="${username}" ${isAdmin ? 'disabled' : ''}>
          <option value="admin" ${user.role==='admin'?'selected':''}>admin</option>
          <option value="developer" ${user.role==='developer'?'selected':''}>developer</option>
          <option value="operator" ${user.role==='operator'?'selected':''}>operator</option>
          <option value="viewer" ${user.role==='viewer'?'selected':''}>viewer</option>
        </select>
        <span class="badge ${roleBadge}">${user.role}</span>
      </div>`;
      tr.append(`<td class="align-middle">${roleSel}</td>`);
      // 권한 토글/뱃지
      let permHtml = '<div class="d-flex flex-wrap gap-1 justify-content-center">';
      PERMISSIONS.forEach(perm => {
        const checked = user.permissions.includes(perm) ? 'checked' : '';
        permHtml += `<div class="form-check form-switch mb-1">
          <input type="checkbox" class="form-check-input iam-perm-checkbox" data-username="${username}" data-perm="${perm}" ${checked} ${isAdmin ? 'disabled' : ''}>
          <label class="form-check-label small ms-1">${perm}</label>
        </div>`;
      });
      permHtml += '</div>';
      tr.append(`<td class="align-middle">${permHtml}</td>`);
      // 저장/변경 버튼
      tr.append(`<td class="align-middle"><button class="btn btn-outline-primary btn-sm iam-save-btn" data-username="${username}" ${isAdmin ? 'disabled' : ''}><i class="fas fa-save me-1"></i>저장</button></td>`);
      tbody.append(tr);
    });
    // 행 hover 효과
    tbody.find('tr').hover(
      function() { $(this).addClass('table-primary'); },
      function() { $(this).removeClass('table-primary'); }
    );
  }
  function loadIAM() {
    $('#iam-loading').removeClass('d-none');
    $.get('/admin/iam', function(res) {
      USERS = res.users;
      PERMISSIONS = res.permissions;
      renderSummary();
      renderTable();
      $('#iam-loading').addClass('d-none');
    });
  }
  // 역할 변경
  $(document).on('change', '.iam-role-select', function() {
    const username = $(this).data('username');
    const newRole = $(this).val();
    $.ajax({
      url: `/admin/iam/${username}/role`,
      method: 'POST',
      contentType: 'application/json',
      data: JSON.stringify({ role: newRole }),
      success: function(res) {
        showIAMAlert('success', res.message);
        loadIAM();
      },
      error: function(xhr) {
        showIAMAlert('danger', xhr.responseJSON?.error || '역할 변경 실패');
      }
    });
  });
  // 권한 저장
  $(document).on('click', '.iam-save-btn', function() {
    const username = $(this).data('username');
    const perms = [];
    $(`.iam-perm-checkbox[data-username='${username}']:checked`).each(function() {
      perms.push($(this).data('perm'));
    });
    $.ajax({
      url: `/admin/iam/${username}/permissions`,
      method: 'POST',
      contentType: 'application/json',
      data: JSON.stringify({ permissions: perms }),
      success: function(res) {
        showIAMAlert('success', res.message);
        loadIAM();
      },
      error: function(xhr) {
        showIAMAlert('danger', xhr.responseJSON?.error || '권한 변경 실패');
      }
    });
  });
  // 체크박스 변경 시 저장 버튼 활성화
  $(document).on('change', '.iam-perm-checkbox', function() {
    const username = $(this).data('username');
    $(`.iam-save-btn[data-username='${username}']`).removeAttr('disabled');
  });
  // 초기 로드
  loadIAM();
}); 