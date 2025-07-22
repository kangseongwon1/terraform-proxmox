// iam.js
$(function() {
  let PERMISSIONS = [];
  let USERS = {};
  function showIAMAlert(type, msg) {
    const alert = $('#iam-alert');
    alert.removeClass('d-none alert-success alert-danger alert-info').addClass('alert-' + type).text(msg).show();
    setTimeout(() => alert.hide(), 2000);
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
      <div class='card iam-summary-card border-primary'>
        <div class='card-body text-center'>
          <div class='fw-bold text-primary mb-1'><i class='fas fa-users'></i> 전체 사용자</div>
          <div class='fs-4'>${total}</div>
        </div>
      </div>
      <div class='card iam-summary-card border-success'>
        <div class='card-body text-center'>
          <div class='fw-bold text-success mb-1'><i class='fas fa-user-crown'></i> 관리자</div>
          <div class='fs-4'>${admin}</div>
        </div>
      </div>
      <div class='card iam-summary-card border-info'>
        <div class='card-body text-center'>
          <div class='fw-bold text-info mb-1'><i class='fas fa-user-gear'></i> 개발자</div>
          <div class='fs-4'>${dev}</div>
        </div>
      </div>
      <div class='card iam-summary-card border-warning'>
        <div class='card-body text-center'>
          <div class='fw-bold text-warning mb-1'><i class='fas fa-user-cog'></i> 오퍼레이터</div>
          <div class='fs-4'>${op}</div>
        </div>
      </div>
      <div class='card iam-summary-card border-secondary'>
        <div class='card-body text-center'>
          <div class='fw-bold text-secondary mb-1'><i class='fas fa-user'></i> 뷰어</div>
          <div class='fs-4'>${viewer}</div>
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
      let tr = $('<tr>').toggleClass('iam-admin-row', isAdmin);
      tr.append(`<td><i class="fas fa-user-circle iam-profile-icon"></i></td>`);
      tr.append(`<td class="fw-bold">${username}</td>`);
      tr.append(`<td>${user.email || ''}</td>`);
      let roleSel = `<select class="form-select form-select-sm iam-role-select" data-username="${username}" ${isAdmin ? 'disabled' : ''}>
        <option value="admin" ${user.role==='admin'?'selected':''}>admin</option>
        <option value="developer" ${user.role==='developer'?'selected':''}>developer</option>
        <option value="operator" ${user.role==='operator'?'selected':''}>operator</option>
        <option value="viewer" ${user.role==='viewer'?'selected':''}>viewer</option>
      </select>`;
      tr.append(`<td>${roleSel}</td>`);
      let permHtml = '<div class="d-flex flex-wrap justify-content-center gap-1">';
      PERMISSIONS.forEach(perm => {
        const checked = user.permissions.includes(perm) ? 'checked' : '';
        permHtml += `<div class="form-check form-check-inline mb-1">
          <input type="checkbox" class="form-check-input iam-perm-checkbox" data-username="${username}" data-perm="${perm}" ${checked} ${isAdmin ? 'disabled' : ''}>
          <label class="form-check-label small">${perm}</label>
        </div>`;
      });
      permHtml += '</div>';
      tr.append(`<td>${permHtml}</td>`);
      tr.append(`<td><button class="btn btn-primary btn-sm iam-save-btn" data-username="${username}" ${isAdmin ? 'disabled' : ''}>저장</button></td>`);
      tbody.append(tr);
    });
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
    $.post(`/admin/iam/${username}/role`, JSON.stringify({ role: newRole }), function(res) {
      showIAMAlert('success', res.message);
      loadIAM();
    }).fail(function(xhr) {
      showIAMAlert('danger', xhr.responseJSON?.error || '역할 변경 실패');
    });
  });
  // 권한 저장
  $(document).on('click', '.iam-save-btn', function() {
    const username = $(this).data('username');
    const perms = [];
    $(`.iam-perm-checkbox[data-username='${username}']:checked`).each(function() {
      perms.push($(this).data('perm'));
    });
    $.post(`/admin/iam/${username}/permissions`, JSON.stringify({ permissions: perms }), function(res) {
      showIAMAlert('success', res.message);
      loadIAM();
    }).fail(function(xhr) {
      showIAMAlert('danger', xhr.responseJSON?.error || '권한 변경 실패');
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