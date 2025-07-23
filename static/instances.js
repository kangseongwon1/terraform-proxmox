// instances.js
$(function() {
  // 서버 목록 불러오기 (기존 index.html 구조 100% 복원)
  window.loadActiveServers = function() {
    console.log('[instances.js] loadActiveServers 호출');
    $.get('/all_server_status', function(res) {
      console.log('[instances.js] /all_server_status 응답:', res);
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
      console.log('[instances.js] 서버 목록 렌더링 완료');
    }).fail(function(xhr) {
      console.error('[instances.js] /all_server_status 실패:', xhr);
    });
  }
  loadActiveServers();
  $('#list-tab').on('shown.bs.tab', function() {
    console.log('[instances.js] list-tab shown');
    loadActiveServers();
  });

  // 작업 상태 폴링 관리
  let activeTasks = {};
  function pollTaskStatus(task_id, type, name) {
    if (!task_id) return;
    let progressNotified = false;
    activeTasks[task_id] = setInterval(function() {
      $.get('/tasks/status', { task_id }, function(res) {
        if ((res.status === 'progress' || res.status === 'pending') && !progressNotified) {
          addSystemNotification('info', type, `${name} ${type} 중...`);
          progressNotified = true;
        } else if (res.status === 'success') {
          addSystemNotification('success', type, `${name} ${type} 완료`);
          clearInterval(activeTasks[task_id]);
          delete activeTasks[task_id];
          loadActiveServers();
        } else if (res.status === 'error') {
          addSystemNotification('error', type, `${name} ${type} 실패: ${res.message}`);
          clearInterval(activeTasks[task_id]);
          delete activeTasks[task_id];
        }
      });
    }, 5000);
  }

  // 서버 생성 버튼
  $(document).on('click', '#create-server-btn', function() {
    console.log('[instances.js] #create-server-btn 클릭');
    const selectedRole = $('#role-select').val() || '';
    const selectedOS = $('#os-select').val();
    if (!selectedOS) {
      alert('OS를 선택해주세요.');
      return;
    }
    const name = $('input[name="name_basic"]').val();
    if (!name || name.trim() === '') {
      alert('서버 이름을 입력해주세요.');
      return;
    }
    // IP 주소 검증
    let hasError = false;
    $('#network-container-basic').find('.network-ip').each(function() {
      const ip = $(this).val();
      if (!ip || ip.trim() === '') {
        alert('IP 주소를 입력해주세요.');
        hasError = true;
        return false;
      }
    });
    if (hasError) return;
    // 서버 생성
    createBasicServer(name, selectedOS, selectedRole);
  });

  // 기본 서버 생성 함수 (기존 로직 복원)
  function createBasicServer(name, selectedOS, selectedRole) {
    console.log('[instances.js] createBasicServer 호출', name, selectedOS, selectedRole);
    const btn = $('#create-server-btn');
    const originalText = btn.html();
    btn.prop('disabled', true).html('<i class="fas fa-spinner fa-spin me-2"></i>생성 중...');
    $('#creation-status').show();
    $('#status-message').html('서버 생성 진행 중입니다. 잠시만 기다려주세요...');
    const cpu = parseInt($('input[name="cpu_basic"]').val());
    const memory = parseInt($('input[name="memory_basic"]').val());
    const disks = $('#disk-container-basic').find('.disk-item').map(function() {
      return {
        size: parseInt($(this).find('.disk-size').val()),
        interface: $(this).find('.disk-interface').val(),
        datastore_id: $(this).find('.disk-datastore').val()
      };
    }).get();
    const networks = $('#network-container-basic').find('.network-item').map(function() {
      return {
        bridge: $(this).find('.network-bridge').val(),
        ip_address: $(this).find('.network-ip').val(),
        subnet: $(this).find('.network-subnet').val(),
        gateway: $(this).find('.network-gateway').val()
      };
    }).get();
    const osTemplateMapping = {
      'ubuntu': 9000,
      'rocky': 8000,
      'centos': 8001,
      'debian': 9001
    };
    const template_vm_id = osTemplateMapping[selectedOS] || 8000;
    const data = {
      name: name,
      role: selectedRole,
      cpu: cpu,
      memory: memory,
      disks: disks,
      network_devices: networks,
      template_vm_id: template_vm_id
    };
    $('#status-message').html('서버 생성 진행 중입니다. 잠시만 기다려주세요...');
    $.ajax({
      url: '/add_server',
      method: 'POST',
      contentType: 'application/json',
      data: JSON.stringify(data),
      beforeSend: function() {
        console.log('[instances.js] /add_server 요청 전', data);
      },
      success: function(res) {
        console.log('[instances.js] /add_server 성공', res);
        if (res.task_id) {
          pollTaskStatus(res.task_id, '서버 생성', name);
        }
        $('#status-message').html('서버 생성 요청이 접수되었습니다. 진행 상황은 알림에서 확인하세요.');
        setTimeout(function() {
          $('#creation-status').hide();
          btn.prop('disabled', false).html(originalText);
        }, 2000);
      },
      error: function(xhr) {
        console.error('[instances.js] /add_server 실패', xhr);
        $('#status-message').html('서버 생성 실패');
        addSystemNotification('error', '서버 생성', '서버 생성 요청 실패: ' + (xhr.responseJSON?.stderr || xhr.responseJSON?.error || xhr.statusText));
        setTimeout(function() {
          $('#creation-status').hide();
          btn.prop('disabled', false).html(originalText);
        }, 2000);
      }
    });
  }

  // 역할 적용
  $(document).on('click', '.server-role-apply', function() {
    console.log('[instances.js] .server-role-apply 클릭');
    const btn = $(this);
    const tr = btn.closest('tr');
    const server = tr.data('server');
    const role = tr.find('.server-role-select').val();
    btn.prop('disabled', true).html('<i class="fas fa-spinner fa-spin"></i> <span>역할 적용 중...</span>');
    $.post(`/assign_role/${server}`, { role }, function(res) {
      console.log('[instances.js] /assign_role 성공', res);
      btn.prop('disabled', false).html('<i class="fas fa-check"></i> <span>역할 적용</span>');
      loadActiveServers();
      addSystemNotification('success', '역할 변경', '역할이 성공적으로 변경되었습니다.');
    }).fail(function(xhr) {
      console.error('[instances.js] /assign_role 실패', xhr);
      btn.prop('disabled', false).html('<i class="fas fa-check"></i> <span>역할 적용</span>');
      addSystemNotification('error', '역할 변경', xhr.responseJSON?.error || '역할 변경 실패');
    });
  });

  // 역할 삭제
  $(document).on('click', '.server-role-remove', function() {
    console.log('[instances.js] .server-role-remove 클릭');
    const btn = $(this);
    const tr = btn.closest('tr');
    const server = tr.data('server');
    if (!confirm('정말로 이 서버의 역할을 삭제하시겠습니까?')) return;
    btn.prop('disabled', true).html('<i class="fas fa-spinner fa-spin"></i> <span>역할 삭제 중...</span>');
    $.post(`/remove_role/${server}`, {}, function(res) {
      console.log('[instances.js] /remove_role 성공', res);
      btn.prop('disabled', false).html('<i class="fas fa-trash"></i> <span>역할 삭제</span>');
      loadActiveServers();
      addSystemNotification('success', '역할 삭제', '역할이 삭제되었습니다.');
    }).fail(function(xhr) {
      console.error('[instances.js] /remove_role 실패', xhr);
      btn.prop('disabled', false).html('<i class="fas fa-trash"></i> <span>역할 삭제</span>');
      addSystemNotification('error', '역할 삭제', xhr.responseJSON?.error || '역할 삭제 실패');
    });
  });

  // 서버 시작
  $(document).on('click', '.start-btn', function() {
    console.log('[instances.js] .start-btn 클릭');
    const name = $(this).closest('tr').data('server');
    const btn = $(this);
    const originalText = btn.html();
    if (confirm(`${name} 서버를 시작하시겠습니까?`)) {
      btn.prop('disabled', true).html('<i class="fas fa-spinner fa-spin me-1"></i>시작 중...');
      $.post('/start_server/' + name, function(res) {
        console.log('[instances.js] /start_server 성공', res);
        btn.prop('disabled', false).html(originalText);
        loadActiveServers();
        addSystemNotification('success', '서버 시작', `${name} 서버가 시작되었습니다.`);
      }).fail(function(xhr){
        console.error('[instances.js] /start_server 실패', xhr);
        btn.prop('disabled', false).html(originalText);
        addSystemNotification('error', '서버 시작', `시작 실패: ${xhr.responseJSON?.error || xhr.statusText}`);
      });
    }
  });

  // 서버 중지
  $(document).on('click', '.stop-btn', function() {
    console.log('[instances.js] .stop-btn 클릭');
    const name = $(this).closest('tr').data('server');
    const btn = $(this);
    const originalText = btn.html();
    if (confirm(`${name} 서버를 중지하시겠습니까?`)) {
      btn.prop('disabled', true).html('<i class="fas fa-spinner fa-spin me-1"></i>중지 중...');
      $.post('/stop_server/' + name, function(res) {
        console.log('[instances.js] /stop_server 성공', res);
        btn.prop('disabled', false).html(originalText);
        loadActiveServers();
        addSystemNotification('success', '서버 중지', `${name} 서버가 중지되었습니다.`);
      }).fail(function(xhr){
        console.error('[instances.js] /stop_server 실패', xhr);
        btn.prop('disabled', false).html(originalText);
        addSystemNotification('error', '서버 중지', `중지 실패: ${xhr.responseJSON?.error || xhr.statusText}`);
      });
    }
  });

  // 서버 리부팅
  $(document).on('click', '.reboot-btn', function() {
    console.log('[instances.js] .reboot-btn 클릭');
    const name = $(this).closest('tr').data('server');
    const btn = $(this);
    const originalText = btn.html();
    if (confirm(`${name} 서버를 리부팅하시겠습니까?`)) {
      btn.prop('disabled', true).html('<i class="fas fa-spinner fa-spin me-1"></i>리부팅 중...');
      $.post('/reboot_server/' + name, function(res) {
        console.log('[instances.js] /reboot_server 성공', res);
        btn.prop('disabled', false).html(originalText);
        loadActiveServers();
        addSystemNotification('success', '서버 리부팅', `${name} 서버가 리부팅되었습니다.`);
      }).fail(function(xhr){
        console.error('[instances.js] /reboot_server 실패', xhr);
        btn.prop('disabled', false).html(originalText);
        addSystemNotification('error', '서버 리부팅', `리부팅 실패: ${xhr.responseJSON?.error || xhr.statusText}`);
      });
    }
  });

  // 서버 삭제
  $(document).on('click', '.delete-btn', function() {
    console.log('[instances.js] .delete-btn 클릭');
    const name = $(this).closest('tr').data('server');
    const btn = $(this);
    const originalText = btn.html();
    // confirm 없이 바로 삭제 진행
    btn.prop('disabled', true).html('<i class="fas fa-spinner fa-spin me-1"></i>삭제 중...');
    btn.closest('tr').addClass('table-warning');
    $('#delete-status-message').remove();
    $('#active-server-table').before('<div id="delete-status-message" class="alert alert-warning mb-2">서버 삭제 중입니다. 완료까지 수 분 소요될 수 있습니다.</div>');
    $.post('/delete_server/' + name, function(res) {
      console.log('[instances.js] /delete_server 성공', res);
      if (res.task_id) {
        pollTaskStatus(res.task_id, '서버 삭제', name);
      }
      $('#delete-status-message').remove();
      // 삭제중 메시지는 알림에서만 안내
      addSystemNotification('success', '서버 삭제', `${name} 서버가 삭제되었습니다.`);
    }).fail(function(xhr){
      console.error('[instances.js] /delete_server 실패', xhr);
      $('#delete-status-message').remove();
      btn.prop('disabled', false).html(originalText);
      btn.closest('tr').removeClass('table-warning');
      addSystemNotification('error', '서버 삭제', `삭제 요청 실패: ${xhr.responseJSON?.error || xhr.statusText}`);
    });
  });

  // 서버명 클릭 시 상세 모달 표시
  $(document).on('click', '.server-detail-link', function(e) {
    e.preventDefault();
    const name = $(this).data('server');
    // 상세 모달 로드 및 이벤트 연결 (기존 index.html 구조 복원)
    // ... 상세 모달 코드 ...
  });

  // 상세 모달 내 역할 적용/삭제
  $(document).on('click', '.server-detail-role-apply', function() { /* ... */ });
  $(document).on('click', '.server-detail-role-remove', function() { /* ... */ });

  // removeDisk 인라인 이벤트 대체
  $(document).on('click', '.remove-disk-btn', function() {
    const diskItem = $(this).closest('.disk-item');
    const container = diskItem.closest('.disk-container');
    diskItem.remove();
    // 마지막 하나 남았을 때 삭제 버튼 비활성화
    if (container.find('.disk-item').length === 1) {
      container.find('.disk-item:first .btn-outline-danger').prop('disabled', true);
    }
  });

  // 새로고침 버튼 클릭 시 서버 목록 갱신
  $(document).on('click', '.refresh-btn', function() {
    console.log('[instances.js] .refresh-btn 클릭');
    loadActiveServers();
  });

  // 모든 알림 삭제 버튼 핸들러
  $(document).on('click', '#clear-all-notifications', function(e) {
    e.preventDefault();
    if (!confirm('모든 알림을 삭제하시겠습니까?')) return;
    $.post('/notifications/clear-all', function(res) {
      window.systemNotifications = [];
      if (typeof addSystemNotification === 'function') {
        addSystemNotification('success', '알림', '모든 알림이 삭제되었습니다.');
      }
    }).fail(function(xhr) {
      if (typeof addSystemNotification === 'function') {
        addSystemNotification('error', '알림', '알림 삭제 실패: ' + (xhr.responseJSON?.error || xhr.statusText));
      }
    });
    // 즉시 클라이언트 알림 드롭다운 갱신
    if (typeof addSystemNotification === 'function') {
      window.systemNotifications = [];
      addSystemNotification(); // 빈 알림으로 드롭다운 갱신
    }
  });
});

// =========================
// 시스템 알림 드롭다운 구현 (상단 네비게이션 notification-list만 사용)
// =========================
(function(){
  // 알림 목록 관리
  window.systemNotifications = window.systemNotifications || [];
  window.addSystemNotification = function(type, title, message) {
    // type: 'success' | 'info' | 'error'
    const now = new Date();
    const timeStr = now.toLocaleTimeString('ko-KR', {hour12:false});
    // 알림 객체 추가 (최대 10개 유지)
    window.systemNotifications.unshift({type, title, message, time: timeStr});
    if (window.systemNotifications.length > 10) window.systemNotifications.length = 10;
    // 드롭다운 렌더링 (상단 네비게이션)
    const $list = $('#notification-list');
    let html = '';
    window.systemNotifications.forEach(function(noti){
      const icon = noti.type==='success' ? 'fa-check-circle text-success' : noti.type==='error' ? 'fa-exclamation-circle text-danger' : 'fa-info-circle text-info';
      html += `
        <li>
          <div class="dropdown-item d-flex align-items-start small">
            <i class="fas ${icon} me-2 mt-1"></i>
            <div class="flex-grow-1">
              <div class="fw-bold">${noti.title}</div>
              <div class="text-muted">${noti.message}</div>
              <div class="text-muted small">${noti.time}</div>
            </div>
          </div>
        </li>
      `;
    });
    if (window.systemNotifications.length === 0) {
      html = '<li class="text-center text-muted py-3">알림이 없습니다</li>';
    }
    $list.html(html);
    // 뱃지 갱신
    const $badge = $('#notification-badge');
    if (window.systemNotifications.length > 0) {
      $badge.text(window.systemNotifications.length).show();
    } else {
      $badge.hide();
    }
  };
})(); 