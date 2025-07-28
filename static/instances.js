// instances.js
$(function() {
  // 숫자를 소수점 2자리까지 포맷팅하는 함수
  function format2f(num) {
    return parseFloat(num).toFixed(2);
  }
  
  // 서버 역할 매핑
  window.dashboardRoleMap = {
    'web': '웹서버(Nginx)',
    'was': 'WAS(Python3.12)',
    'java': 'JAVA(17.0.7)',
    'search': '검색(Elasticsearch7)',
    'ftp': 'FTP(vsftpd)',
    'db': 'DB(MariaDB10.11)'
  };
  
  // 시스템 알림 함수
  function addSystemNotification(type, title, message) {
    console.log(`[알림] ${type}: ${title} - ${message}`);
    // 실제 알림 UI는 나중에 구현
  }
  
  // 알림 모달 함수
  function alertModal(message) {
    alert(message);
  }
  
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

  // 서버 생성 버튼 (단일/다중 모드 분기, 중복 바인딩 제거)
  $(document).off('click', '#create-server-btn').on('click', '#create-server-btn', async function(e) {
    // 중복 실행 방지
    if ($(this).data('processing')) return;
    $(this).data('processing', true);
    
    const mode = $('#server_mode').val();
    if (mode === 'multi') {
      // 다중 서버 로직 (기존 다중 서버 코드)
      e.preventDefault();
      // 입력값 수집
      const count = parseInt($('#multi-server-count').val());
      const baseName = $('input[name="name_basic"]').val();
      const selectedRole = $('#role-select').val() || '';
      const selectedOS = $('#os-select').val();
      const cpu = parseInt($('input[name="cpu_basic"]').val());
      const memory = parseInt($('input[name="memory_basic"]').val());
      // 디스크/네트워크 정보 복제
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
          ip: $(this).find('.network-ip').val(),
          subnet: $(this).find('.network-subnet').val(),
          gateway: $(this).find('.network-gateway').val()
        };
      }).get();
      if (!selectedOS) { await alertModal('OS를 선택해주세요.'); return; }
      if (!baseName || baseName.trim() === '') { await alertModal('서버 이름을 입력해주세요.'); return; }
      if (!count || count < 2) { alertModal('서버 개수는 2 이상이어야 합니다.'); return; }
      // 네트워크 입력값 검증 (IP, 서브넷, 게이트웨이 모두 필수)
      let hasError = false;
      networks.forEach(function(n, idx) {
        if (!n.ip || !n.subnet || !n.gateway) {
          alertModal(`네트워크 카드 #${idx+1}의 IP, 서브넷, 게이트웨이를 모두 입력해주세요.`);
          hasError = true;
        }
      });
      if (hasError) return;
      // 서버별 정보 생성 (IP 자동 증가, 네트워크 여러 개 지원)
      function ipAdd(ip, add) {
        const parts = ip.split('.').map(Number);
        parts[3] += add;
        if (parts[3] > 254) parts[3] = 254;
        return parts.join('.')
      }
      const serverList = [];
      for (let i = 0; i < count; i++) {
        // 네트워크 여러 개 지원: 각 네트워크의 ip만 i만큼 증가
        const nets = networks.map((net, ni) => {
          const newNet = {...net};
          if (i > 0 && newNet.ip) {
            newNet.ip = ipAdd(net.ip, i);
          }
          return newNet;
        });
        serverList.push({
          name: `${baseName}-${i+1}`,
          role: selectedRole,
          os: selectedOS,
          cpu: cpu,
          memory: memory,
          disks: JSON.parse(JSON.stringify(disks)),
          networks: nets
        });
      }
      // 역할 select 옵션 생성
      let roleOptions = '<option value="">(선택 안 함)</option>';
      for (const [k, v] of Object.entries(window.dashboardRoleMap)) {
        roleOptions += `<option value="${k}">${v}</option>`;
      }
      // 서버 생성 폼을 다중 서버 요약 화면으로 교체
      $('#create-server-form').html('<div id="multiServerSummarySection"></div>');
      
      // 요약 섹션 로드
      $.get('/instances/multi-server-summary', function(html) {
        $('#multiServerSummarySection').html(html);
        
        // 테이블 내용 동적 생성
        let tableRows = '';
        serverList.forEach((s, sidx) => {
          s.networks.forEach((net, nidx) => {
            tableRows += `
              <tr data-sidx="${sidx}" data-nidx="${nidx}">
                ${nidx === 0 ? `
                  <td rowspan="${s.networks.length}">${s.name}</td>
                  <td rowspan="${s.networks.length}">${s.os}</td>
                  <td rowspan="${s.networks.length}">${s.cpu}</td>
                  <td rowspan="${s.networks.length}">${s.memory}</td>
                  <td rowspan="${s.networks.length}">${s.disks.map(d=>`${d.size}GB/${d.interface}/${d.datastore_id}`).join('<br>')}</td>
                  <td rowspan="${s.networks.length}">
                    <select class="form-select form-select-sm summary-role">${roleOptions.replace(`value=\"${s.role}\"`, `value=\"${s.role}\" selected`)}</select>
                  </td>
                ` : ''}
                <td><input type="text" class="form-control form-control-sm summary-bridge" value="${net.bridge}"></td>
                <td><input type="text" class="form-control form-control-sm summary-ip" value="${net.ip}"></td>
                <td><input type="text" class="form-control form-control-sm summary-subnet" value="${net.subnet}"></td>
                <td><input type="text" class="form-control form-control-sm summary-gateway" value="${net.gateway}"></td>
              </tr>
            `;
          });
        });
        
        $('#multi-server-summary-tbody').html(tableRows);
        
        // 페이지를 요약 섹션으로 스크롤
        $('#multiServerSummarySection')[0].scrollIntoView({ behavior: 'smooth' });
      });
      // 서버 생성 버튼 클릭 시 - 중복 바인딩 방지
      $(document).off('click', '#multi-server-final-create').on('click', '#multi-server-final-create', function() {
        const $btn = $(this);
        const $section = $('#multiServerSummarySection');
        
        // 중복 실행 방지
        if ($btn.data('processing')) return;
        $btn.data('processing', true);
        
        // 버튼 비활성화로 중복 클릭 방지
        $btn.prop('disabled', true).html('<i class="fas fa-spinner fa-spin me-2"></i>생성 중...');
        
        // 수정된 값 반영
        $('#multiServerSummarySection tbody tr').each(function() {
          const sidx = $(this).data('sidx');
          const nidx = $(this).data('nidx');
          if (nidx === 0) {
            // 역할 select 반영
            serverList[sidx].role = $(this).find('.summary-role').val();
          }
          serverList[sidx].networks[nidx].bridge = $(this).find('.summary-bridge').val();
          serverList[sidx].networks[nidx].ip = $(this).find('.summary-ip').val();
          serverList[sidx].networks[nidx].subnet = $(this).find('.summary-subnet').val();
          serverList[sidx].networks[nidx].gateway = $(this).find('.summary-gateway').val();
        });
        
        // 서버 정보 배열 생성
        const servers = serverList.map(s => ({
          name: s.name,
          role: s.role,
          cpu: s.cpu,
          memory: s.memory,
          disks: s.disks,
          network_devices: s.networks.map(net => ({
            bridge: net.bridge,
            ip_address: net.ip,
            subnet: net.subnet,
            gateway: net.gateway
          })),
          template_vm_id: (function(){
            const osMap = { 'ubuntu': 9000, 'rocky': 8000, 'centos': 8001, 'debian': 9001 };
            return osMap[s.os] || 8000;
          })()
        }));
        
        // 한 번에 서버 정보 배열 전송
        $.ajax({
          url: '/create_servers_bulk',
          method: 'POST',
          contentType: 'application/json',
          data: JSON.stringify({servers}),
          success: function(res) {
            addSystemNotification('success', '서버 생성', '다중 서버 생성 요청 완료');
            // 서버 생성 폼 복원
            restoreServerForm();
            loadActiveServers();
          },
          error: function(xhr) {
            addSystemNotification('error', '서버 생성', '다중 서버 생성 실패: ' + (xhr.responseJSON?.stderr || xhr.responseJSON?.error || xhr.statusText));
            // 서버 생성 폼 복원
            restoreServerForm();
            loadActiveServers();
          },
          complete: function() {
            // 버튼 상태 복원
            $btn.prop('disabled', false).html('서버 생성');
          }
        });
            });
      
      // 취소 버튼 클릭 시 서버 생성 폼으로 되돌리기
      $(document).off('click', '#multi-server-cancel').on('click', '#multi-server-cancel', function() {
        // 중복 실행 방지
        if ($(this).data('processing')) return;
        $(this).data('processing', true);
        
        // 서버 생성 폼 복원
        restoreServerForm();
        
        // 작업 완료 후 처리 상태 해제
        $(this).data('processing', false);
      });
      
      return; // 다중 서버 모드에서는 여기서 종료
    }
    
    // 단일 서버 로직 (기존 단일 서버 코드)
    const selectedRole = $('#role-select').val() || '';
    const selectedOS = $('#os-select').val();
    if (!selectedOS) { await alertModal('OS를 선택해주세요.'); return; }
    const name = $('input[name="name_basic"]').val();
    if (!name || name.trim() === '') { await alertModal('서버 이름을 입력해주세요.'); return; }
    // IP 주소 검증
    let hasError = false;
    $('#network-container-basic').find('.network-ip').each(function() {
      const ip = $(this).val();
      if (!ip || ip.trim() === '') {
        alertModal('IP 주소를 입력해주세요.');
        hasError = true;
        return false;
      }
    });
    if (hasError) return;
    // 서버 생성
    createBasicServer(name, selectedOS, selectedRole);
  });

// 서버 생성 폼 복원 함수
function restoreServerForm() {
  // 서버 생성 폼 다시 로드
  $.get('/instances/content', function(html) {
    // create-server-form 부분만 추출
    const formHtml = $(html).find('#create-server-form').html();
    $('#create-server-form').html(formHtml);
    
    // 폼 초기화
    initializeServerForm();
  });
}

// 서버 생성 폼 초기화 함수
function initializeServerForm() {
  // 다중 서버 옵션 숨기기
  $('#multi-server-options').hide();
  
  // 서버 모드 단일로 설정
  $('#server_mode').val('single');
  $('.mode-card').removeClass('active');
  $('.mode-card[data-mode="single"]').addClass('active');
  
  // 폼 필드 초기화
  $('#create-server-form')[0].reset();
  
  // 디스크/네트워크 기본값 설정
  $('.disk-size').val('20');
  $('.disk-interface').val('scsi0');
  $('.disk-datastore').val('local-lvm');
  $('.network-subnet').val('24');
  
  // 첫 번째 디스크/네트워크의 삭제 버튼 비활성화
  $('.remove-disk-btn:first').prop('disabled', true);
  $('.remove-network-btn:first').prop('disabled', true);
}

  // 기본 서버 생성 함수 (기존 로직 복원)
  function createBasicServer(name, selectedOS, selectedRole) {
    console.log('[instances.js] createBasicServer 호출', name, selectedOS, selectedRole);
    const btn = $('#create-server-btn');
    const originalText = btn.html();
    
    // 중복 실행 방지 해제
    btn.data('processing', false);
    
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
        ip_address: $(this).find('.network-ip').val(), // 순수 IP만
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
      url: '/create_server',
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
  $(document).off('click', '.server-role-apply').on('click', '.server-role-apply', function() {
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
  $(document).off('click', '.server-role-remove').on('click', '.server-role-remove', async function() {
    console.log('[instances.js] .server-role-remove 클릭');
    const btn = $(this);
    const tr = btn.closest('tr');
    const server = tr.data('server');
    const ok = await confirmModal('정말로 이 서버의 역할을 삭제하시겠습니까?');
    if (!ok) return;
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
  $(document).off('click', '.start-btn').on('click', '.start-btn', async function() {
    console.log('[instances.js] .start-btn 클릭');
    const name = $(this).closest('tr').data('server');
    const btn = $(this);
    const originalText = btn.html();
    const ok = await confirmModal(`${name} 서버를 시작하시겠습니까?`);
    if (!ok) return;
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
  });

  // 서버 중지
  $(document).off('click', '.stop-btn').on('click', '.stop-btn', async function() {
    console.log('[instances.js] .stop-btn 클릭');
    const name = $(this).closest('tr').data('server');
    const btn = $(this);
    const originalText = btn.html();
    const ok = await confirmModal(`${name} 서버를 중지하시겠습니까?`);
    if (!ok) return;
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
  });

  // 서버 리부팅
  $(document).off('click', '.reboot-btn').on('click', '.reboot-btn', async function() {
    console.log('[instances.js] .reboot-btn 클릭');
    const name = $(this).closest('tr').data('server');
    const btn = $(this);
    const originalText = btn.html();
    const ok = await confirmModal(`${name} 서버를 리부팅하시겠습니까?`);
    if (!ok) return;
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
  });

  // 서버 삭제 버튼 안전하게 중복 바인딩 없이 처리
  $(document).off('click', '.delete-btn').on('click', '.delete-btn', async function() {
    console.log('[instances.js] .delete-btn 클릭');
    const name = $(this).closest('tr').data('server');
    const btn = $(this);
    const originalText = btn.html();
    // confirm 없이 바로 삭제 진행 또는 confirmModal 사용 시 await
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
      addSystemNotification('success', '서버 삭제', `${name} 서버 삭제를 시작합니다.`);
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
  $(document).off('click', '.server-detail-role-apply').on('click', '.server-detail-role-apply', function() { /* ... */ });
  $(document).off('click', '.server-detail-role-remove').on('click', '.server-detail-role-remove', function() { /* ... */ });

  // 디스크 삭제 버튼 클릭 시 (중복 바인딩 방지)
  $(document).off('click', '.remove-disk-btn').on('click', '.remove-disk-btn', function() {
    const diskItem = $(this).closest('.disk-item');
    const container = diskItem.closest('.disk-container');
    diskItem.remove();
    // 마지막 하나 남았을 때 삭제 버튼 비활성화
    if (container.find('.disk-item').length === 1) {
      container.find('.disk-item:first .btn-outline-danger').prop('disabled', true);
    }
  });

  // 새로고침 버튼 클릭 시 서버 목록 갱신
  $(document).off('click', '.refresh-btn').on('click', '.refresh-btn', function() {
    console.log('[instances.js] .refresh-btn 클릭');
    loadActiveServers();
  });

  // 모든 알림 삭제 버튼 핸들러
  $(document).off('click', '#clear-all-notifications').on('click', '#clear-all-notifications', async function(e) {
    e.preventDefault();
    const ok = await confirmModal('모든 알림을 삭제하시겠습니까?');
    if (!ok) return;
    $.post('/notifications/clear-all', function(res) {
      window.systemNotifications = [];
      // 알림 드롭다운만 갱신(성공 알림은 띄우지 않음)
      if (typeof addSystemNotification === 'function') {
        addSystemNotification(); // 빈 알림으로 드롭다운 갱신
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

  // 네트워크 추가 버튼 클릭 시 네트워크 입력란 추가 (중복 바인딩 방지)
  $(document).off('click', '.add-network-btn').on('click', '.add-network-btn', function() {
    const $container = $('#network-container-basic');
    const $item = $container.find('.network-item').first().clone();
    $item.find('input, select').val('');
    $item.find('.remove-network-btn').prop('disabled', false);
    $container.append($item);
  });

  // 디스크 추가 버튼 클릭 시 디스크 입력란 추가 (중복 바인딩 방지)
  $(document).off('click', '.add-disk-btn').on('click', '.add-disk-btn', function() {
    const $container = $('#disk-container-basic');
    const $item = $container.find('.disk-item').first().clone();
    $item.find('input, select').val('');
    $item.find('.remove-disk-btn').prop('disabled', false);
    $container.append($item);
  });

  // 네트워크 삭제 버튼 클릭 시 (중복 바인딩 방지)
  $(document).off('click', '.remove-network-btn').on('click', '.remove-network-btn', function() {
    const $item = $(this).closest('.network-item');
    const $container = $item.closest('.network-container');
    $item.remove();
    // 마지막 하나 남았을 때 삭제 버튼 비활성화
    if ($container.find('.network-item').length === 1) {
      $container.find('.network-item:first .remove-network-btn').prop('disabled', true);
    }
  });

  // 카드형 서버 생성 모드 UI 연동 (중복 바인딩 방지)
  $(document).off('click', '.mode-card').on('click', '.mode-card', function() {
    $('.mode-card').removeClass('active');
    $(this).addClass('active');
    const mode = $(this).data('mode');
    $('#server_mode').val(mode);
    if (mode === 'multi') {
      $('#multi-server-options').show();
      $('#create-server-btn').text('다음');
    } else {
      $('#multi-server-options').hide();
      $('#create-server-btn').text('서버 생성');
    }
  });

  // 다중 서버 모드: 다음 버튼 클릭 시 요약/수정 모달 표시
  // 이 부분은 이미 위에서 처리되었으므로 제거
});

// =========================
// 시스템 알림 드롭다운 구현 (상단 네비게이션 notification-list만 사용)
// =========================
(function(){
  // 알림 목록 관리
  window.systemNotifications = window.systemNotifications || [];
  window.addSystemNotification = function(type, title, message) {
    if (typeof type === 'undefined' && typeof title === 'undefined' && typeof message === 'undefined') {
      // 알림 추가 없이 드롭다운만 갱신
      const $list = $('#notification-list');
      let html = '';
      if (!window.systemNotifications || window.systemNotifications.length === 0) {
        html = '<li class="text-center text-muted py-3">알림이 없습니다</li>';
      }
      $list.html(html);
      $('#notification-badge').hide();
      return;
    }
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

// Bootstrap 기반 커스텀 confirm 모달 함수
window.confirmModal = function(message) {
  return new Promise(function(resolve) {
    // 기존 confirm 모달이 있으면 제거
    $('#customConfirmModal').remove();
    const html = `
      <div class="modal fade" id="customConfirmModal" tabindex="-1">
        <div class="modal-dialog">
          <div class="modal-content">
            <div class="modal-header">
              <h5 class="modal-title">확인</h5>
              <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
            </div>
            <div class="modal-body">
              <div>${message}</div>
            </div>
            <div class="modal-footer">
              <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">취소</button>
              <button type="button" class="btn btn-primary" id="customConfirmOk">확인</button>
            </div>
          </div>
        </div>
      </div>`;
    $('body').append(html);
    const modal = new bootstrap.Modal(document.getElementById('customConfirmModal'));
    modal.show();
    $('#customConfirmOk').off('click').on('click', function() {
      modal.hide();
      resolve(true);
    });
    $('#customConfirmModal').on('hidden.bs.modal', function(){
      $('#customConfirmModal').remove();
      resolve(false);
    });
  });
};

// Bootstrap 기반 커스텀 alert 모달 함수
window.alertModal = function(message) {
  return new Promise(function(resolve) {
    $('#customAlertModal').remove();
    const html = `
      <div class="modal fade" id="customAlertModal" tabindex="-1">
        <div class="modal-dialog">
          <div class="modal-content">
            <div class="modal-header">
              <h5 class="modal-title">알림</h5>
              <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
            </div>
            <div class="modal-body">
              <div>${message}</div>
            </div>
            <div class="modal-footer">
              <button type="button" class="btn btn-primary" id="customAlertOk">확인</button>
            </div>
          </div>
        </div>
      </div>`;
    $('body').append(html);
    const modal = new bootstrap.Modal(document.getElementById('customAlertModal'));
    modal.show();
    $('#customAlertOk').off('click').on('click', function() {
      modal.hide();
      resolve();
    });
    $('#customAlertModal').on('hidden.bs.modal', function(){
      $('#customAlertModal').remove();
      resolve();
    });
  });
}; 