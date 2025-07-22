// iam.js
$(function() {
  let PERMISSIONS = [];
  let USERS = {};
  let expandedUser = null; // 현재 권한 카드가 펼쳐진 사용자
  let changedPerms = {}; // 변경된 권한 임시 저장

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
      let tr = $('<tr>').toggleClass('iam-admin-row', isAdmin).toggleClass('table-secondary', isInactive).addClass('iam-user-row').attr('data-username', username);
      tr.append(`<td><i class="fas fa-user-circle iam-profile-icon ${isInactive ? 'text-muted' : ''}"></i></td>`);
      tr.append(`<td class="fw-bold align-middle">${username} ${isInactive ? '<span class="badge bg-secondary ms-1">비활성</span>' : ''}</td>`);
      tr.append(`<td class="align-middle">${user.email || ''}</td>`);
      let roleBadge = {
        'admin': 'bg-success',
        'developer': 'bg-info',
        'operator': 'bg-warning',
        'viewer': 'bg-secondary'
      }[user.role] || 'bg-light';
      let roleSel = `<div class="d-flex align-items-center gap-2">
        <span class="badge ${roleBadge}">${user.role}</span>
      </div>`;
      tr.append(`<td class="align-middle">${roleSel}</td>`);
      tr.append(`<td class="align-middle text-center"><button class="btn btn-outline-primary btn-sm iam-expand-btn" data-username="${username}"><i class="fas fa-edit"></i> 권한 관리</button></td>`);
      tbody.append(tr);
      // 권한 카드 영역(펼침)
      let permRow = $(`<tr class="iam-perm-row" data-username="${username}" style="display:none;"><td colspan="5"></td></tr>`);
      tbody.append(permRow);
    });
    // 행 hover 효과
    tbody.find('tr.iam-user-row').hover(
      function() { $(this).addClass('table-primary'); },
      function() { $(this).removeClass('table-primary'); }
    );
  }

  // 권한 카드 렌더링
  function renderPermCards(username) {
    const user = USERS[username];
    if (!user) return '';
    let perms = changedPerms[username] || user.permissions;
    let html = `<div class="d-flex flex-wrap gap-2 mb-2">`;
    PERMISSIONS.forEach(perm => {
      const active = perms.includes(perm);
      html += `<div class="card perm-card ${active ? 'border-primary bg-primary text-white' : 'border-light'}" data-perm="${perm}" style="min-width:120px;cursor:pointer;transition:all 0.2s;">
        <div class="card-body py-2 px-3 text-center">
          <i class="fas fa-key me-1"></i>${perm}
        </div>
      </div>`;
    });
    html += '</div>';
    html += `<div class="text-end"><button class="btn btn-success btn-sm iam-save-perm-btn" data-username="${username}" disabled><i class="fas fa-save me-1"></i>저장</button></div>`;
    return html;
  }

  // 테이블 렌더링 및 이벤트 바인딩
  function loadIAM() {
    $('#iam-loading').removeClass('d-none');
    $.get('/admin/iam', function(res) {
      USERS = res.users;
      PERMISSIONS = res.permissions;
      renderSummary();
      renderTable();
      $('#iam-loading').addClass('d-none');
      expandedUser = null;
      changedPerms = {};
    });
  }

  // 사용자 행 클릭 시 권한 카드 펼침/닫기
  $(document).on('click', '.iam-expand-btn', function(e) {
    e.stopPropagation();
    const username = $(this).data('username');
    // 이미 펼쳐진 경우 닫기
    if (expandedUser === username) {
      $(`.iam-perm-row[data-username='${username}']`).hide().empty();
      expandedUser = null;
      return;
    }
    // 다른 유저 펼침 닫기
    $('.iam-perm-row').hide().empty();
    expandedUser = username;
    // 권한 카드 렌더링
    const html = renderPermCards(username);
    $(`.iam-perm-row[data-username='${username}']`).show().find('td').html(html);
  });

  // 권한 카드 클릭 토글
  $(document).on('click', '.perm-card', function() {
    const username = expandedUser;
    if (!username) return;
    let perms = changedPerms[username] || [...USERS[username].permissions];
    const perm = $(this).data('perm');
    if (perms.includes(perm)) {
      perms = perms.filter(p => p !== perm);
    } else {
      perms.push(perm);
    }
    changedPerms[username] = perms;
    // 카드 UI 갱신
    const html = renderPermCards(username);
    $(`.iam-perm-row[data-username='${username}'] td`).html(html);
    // 저장 버튼 활성화
    $(`.iam-save-perm-btn[data-username='${username}']`).prop('disabled', false);
  });

  // 권한 저장 버튼 클릭
  $(document).on('click', '.iam-save-perm-btn', function() {
    const username = $(this).data('username');
    const perms = changedPerms[username] || USERS[username].permissions;
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

  // 초기 로드
  loadIAM();
}); 