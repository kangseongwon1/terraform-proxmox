// instances.js - v1.2 (캐시 무효화)
$(function() {
  // 중복 호출 방지를 위한 플래그
  let isInitialized = false;
  
  // 전역 중복 실행 방지 플래그
  if (window.instancesInitialized) {
    console.log('[instances.js] 이미 초기화됨, 중복 실행 방지');
    return;
  }
  window.instancesInitialized = true;
  
  console.log('[instances.js] 초기화 시작');
  
  // 실시간 서버 상태 폴링
  let serverStatusPolling = null;
  let isBulkOperationInProgress = false; // 일괄 작업 진행 상태 플래그
  let taskConfig = null; // Task 설정 정보
  
  // Task 설정 정보 로드
  function loadTaskConfig() {
    if (taskConfig) return Promise.resolve(taskConfig);
    
    return $.get('/api/tasks/config')
      .then(function(config) {
        taskConfig = config;
        console.log('[instances.js] Task 설정 로드 완료:', config);
        return config;
      })
      .fail(function(xhr) {
        console.warn('[instances.js] Task 설정 로드 실패, 기본값 사용:', xhr);
        // 기본값 설정
        taskConfig = {
          timeout: 18000,
          timeout_hours: 5,
          polling_interval: 5000
        };
        return taskConfig;
      });
  }
  
  function startServerStatusPolling() {
    if (serverStatusPolling) {
      clearInterval(serverStatusPolling);
    }
    
    serverStatusPolling = setInterval(function() {
      // 일괄 작업 중에는 폴링 중지
      if (isBulkOperationInProgress) {
        console.log('[instances.js] 일괄 작업 중 - 상태 폴링 건너뜀');
        return;
      }
      
      console.log('[instances.js] 서버 상태 폴링 실행');
      loadActiveServers();
    }, 10000); // 10초마다 상태 업데이트
  }
  
  function stopServerStatusPolling() {
    if (serverStatusPolling) {
      clearInterval(serverStatusPolling);
      serverStatusPolling = null;
    }
  }
  
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
  
  // 시스템 알림 함수 (전역 함수 사용)
  function addSystemNotification(type, title, message) {
    console.log(`[알림] ${type}: ${title} - ${message}`);
    
    // 전역 알림 시스템 사용
    if (typeof window.addSystemNotification === 'function') {
      window.addSystemNotification(type, title, message);
    }
  }
  
  // 알림 모달 함수
  function alertModal(message) {
    alert(message);
  }
  
  // 서버 생성 탭으로 전환
  window.switchToCreateTab = function() {
    const createTab = document.getElementById('create-tab');
    if (createTab) {
      createTab.click();
    }
  };
  
  // 서버 설정 모달 열기 (향후 구현)
  window.openServerConfig = function(serverName) {
    alert(`${serverName} 서버 설정 기능은 곧 추가될 예정입니다.`);
  };
  
  // 서버 로그 보기 (향후 구현)
  window.viewServerLogs = function(serverName) {
    alert(`${serverName} 서버 로그 보기 기능은 곧 추가될 예정입니다.`);
  };
  
  // 서버 백업 (향후 구현)
  window.backupServer = function(serverName) {
    alert(`${serverName} 서버 백업 기능은 곧 추가될 예정입니다.`);
  };
  
  // 서버 목록 불러오기 (리스트 뷰 전용)
  window.loadActiveServers = function() {
    console.log('[instances.js] loadActiveServers 호출');
    
    // 중복 호출 방지
    if (window.loadActiveServers.isLoading) {
      console.log('[instances.js] 이미 로딩 중입니다.');
      return;
    }
    window.loadActiveServers.isLoading = true;
    
    // 방화벽 그룹 목록을 먼저 가져오기
    $.get('/api/firewall/groups', function(fwData) {
      console.log('[instances.js] 방화벽 그룹 API 응답:', fwData);
      const firewallGroups = fwData.groups || [];
      console.log('[instances.js] 처리된 방화벽 그룹:', firewallGroups);
      
      $.get('/api/all_server_status', function(res) {
        console.log('[instances.js] /all_server_status 응답:', res);
        console.log('[instances.js] 서버 개수:', Object.keys(res.servers || {}).length);
        
        // 서버 개수 업데이트
        const serverCount = Object.keys(res.servers || {}).length;
        $('#server-count').text(`${serverCount}개`);
        
        // 서버 데이터 저장 (검색/필터링용)
        window.serversData = res.servers || {};
        window.firewallGroups = firewallGroups;
        
        if (serverCount === 0) {
          showEmptyState();
          window.loadActiveServers.isLoading = false;
          return;
        }
        
        // 리스트 뷰로 렌더링
        console.log('[instances.js] 리스트 뷰 렌더링');
        $('#servers-grid').hide();
        $('#servers-table-container').show();
        renderTableView(res.servers, firewallGroups);
        
        console.log('[instances.js] 서버 목록 로드 완료');
        
        // 실시간 상태 폴링 시작
        startServerStatusPolling();
        
        // 중복 호출 방지 해제
        window.loadActiveServers.isLoading = false;
      }).fail(function(xhr) {
        console.error('[instances.js] /all_server_status 실패:', xhr);
        showErrorState();
        window.loadActiveServers.isLoading = false;
      });
    }).fail(function(xhr) {
      console.error('[instances.js] 방화벽 그룹 목록 조회 실패:', xhr);
      window.loadActiveServers.isLoading = false;
    });
  };
  
  // 현재 뷰 타입 가져오기 (리스트 뷰 전용)
  function getCurrentViewType() {
    return 'table'; // 항상 테이블 뷰
  }
  
  // 빈 상태 표시
  function showEmptyState() {
    const emptyHtml = `
      <div class="empty-state">
        <div class="empty-icon">
          <i class="fas fa-server"></i>
        </div>
        <h3>서버가 없습니다</h3>
        <p>새로운 서버를 생성하여 시작해보세요.</p>
        <button class="btn-modern btn-primary" onclick="switchToCreateTab()">
          <i class="fas fa-plus"></i>
          <span>서버 생성</span>
        </button>
      </div>
    `;
    
    $('#servers-grid').html(emptyHtml);
    $('#servers-table tbody').html('');
  }
  
  // 에러 상태 표시
  function showErrorState() {
    const errorHtml = `
      <div class="empty-state">
        <div class="empty-icon">
          <i class="fas fa-exclamation-triangle"></i>
        </div>
        <h3>서버 정보를 불러오지 못했습니다</h3>
        <p>네트워크 연결을 확인하고 다시 시도해주세요.</p>
        <button class="btn-modern btn-refresh" onclick="loadActiveServers()">
          <i class="fas fa-sync-alt"></i>
          <span>다시 시도</span>
        </button>
      </div>
    `;
    
    $('#servers-grid').html(errorHtml);
    $('#servers-table tbody').html('<tr><td colspan="9" class="text-center text-danger">서버 정보를 불러오지 못했습니다.</td></tr>');
  }
  

  
  // 테이블 뷰 렌더링
  function renderTableView(servers, firewallGroups) {
    // 현재 선택된 서버들 저장
    const selectedServers = getSelectedServerNames();
    console.log('[instances.js] 현재 선택된 서버들:', selectedServers);
    
    let html = '';
    for (const [name, s] of Object.entries(servers)) {
      // 상태 배지
      let statusBadge = '';
      switch(s.status) {
        case 'running': 
          statusBadge = '<span class="status-badge status-success">실행 중</span>';
          break;
        case 'stopped':
          statusBadge = '<span class="status-badge status-stopped">중지됨</span>';
          break;
        case 'paused':
          statusBadge = '<span class="status-badge status-warning">일시정지</span>';
          break;
        default:
          statusBadge = '<span class="status-badge status-unknown">' + s.status + '</span>';
      }
      
      // 역할 상태 표시
      const roleDisplay = s.role ? (window.dashboardRoleMap[s.role] || s.role) : '<span class="text-muted">(설정 안 함)</span>';
      
      // Security Group 상태 표시
      const securityGroupDisplay = s.firewall_group ? s.firewall_group : '<span class="text-muted">(설정 안 함)</span>';
      
      // IP 주소 표시
      const ipAddresses = (s.ip_addresses && s.ip_addresses.length > 0) 
        ? s.ip_addresses.join(', ') 
        : '미할당';
      
      // 메모리 포맷팅 (GB)
      const memoryGB = ((s.memory || 0) / 1024 / 1024 / 1024).toFixed(1);
      
      // 체크박스 상태 복원
      const isChecked = selectedServers.includes(s.name) ? 'checked' : '';
      
      const serverRow = `
        <tr class="server-row" data-server="${s.name}" data-status="${s.status}" data-role="${s.role || ''}" data-memory="${s.memory || 0}" data-cpu="${s.vm_cpu || 0}">
          <td class="select-column">
            <input type="checkbox" class="form-check-input server-checkbox" value="${s.name}" ${isChecked}>
          </td>
          <td class="server-name-cell" style="cursor: pointer;">
            <div class="d-flex align-items-center">
              <i class="fas fa-chevron-right expand-icon me-2" style="transition: transform 0.2s;"></i>
              <strong>${s.name}</strong>
            </div>
          </td>
          <td>${statusBadge}</td>
          <td class="role-column">
            <div class="role-display">
              <i class="fas fa-tag me-1 text-muted"></i>
              ${roleDisplay}
            </div>
          </td>
          <td>${s.vm_cpu || 0}코어</td>
          <td>${memoryGB}GB</td>
          <td>${ipAddresses}</td>
          <td class="security-column">
            <div class="security-group-display">
              <i class="fas fa-shield-alt me-1 text-muted"></i>
              ${securityGroupDisplay}
            </div>
          </td>
          <td>
            <div class="table-actions">
              <button class="btn btn-success btn-sm start-btn" title="시작" ${s.status === 'running' ? 'disabled' : ''}>
                <i class="fas fa-play"></i>
              </button>
              <button class="btn btn-warning btn-sm stop-btn" title="중지" ${s.status === 'stopped' ? 'disabled' : ''}>
                <i class="fas fa-pause"></i>
              </button>
              <button class="btn btn-info btn-sm reboot-btn" title="재시작" ${s.status === 'stopped' ? 'disabled' : ''}>
                <i class="fas fa-redo"></i>
              </button>
              <button class="btn btn-danger btn-sm delete-btn" title="삭제">
                <i class="fas fa-trash"></i>
              </button>
            </div>
          </td>
        </tr>
        <tr class="server-detail-row" data-server="${s.name}" style="display: none;">
          <td colspan="9">
            <div class="server-detail-content p-3 bg-light border-top">
              <div class="row">
                <div class="col-md-6">
                  <h6 class="mb-3"><i class="fas fa-info-circle text-primary"></i> 서버 상세 정보</h6>
                  <div class="row mb-2">
                    <div class="col-4"><strong>VM ID:</strong></div>
                    <div class="col-8">${s.vmid || 'N/A'}</div>
                  </div>
                  <div class="row mb-2">
                    <div class="col-4"><strong>노드:</strong></div>
                    <div class="col-8">${s.node || 'N/A'}</div>
                  </div>
                  <div class="row mb-2">
                    <div class="col-4"><strong>CPU 사용률:</strong></div>
                    <div class="col-8">${format2f(s.cpu_usage || 0)}%</div>
                  </div>
                  <div class="row mb-2">
                    <div class="col-4"><strong>메모리 사용률:</strong></div>
                    <div class="col-8">${format2f(s.memory_usage || 0)}%</div>
                  </div>
                  <div class="row mb-2">
                    <div class="col-4"><strong>디스크 사용률:</strong></div>
                    <div class="col-8">${format2f(s.disk_usage || 0)}%</div>
                  </div>
                </div>
                <div class="col-md-6">
                  <h6 class="mb-3"><i class="fas fa-network-wired text-success"></i> 네트워크 정보</h6>
                  <div class="row mb-2">
                    <div class="col-4"><strong>IP 주소:</strong></div>
                    <div class="col-8">${ipAddresses}</div>
                  </div>
                  <div class="row mb-2">
                    <div class="col-4"><strong>방화벽 그룹:</strong></div>
                    <div class="col-8">${s.firewall_group || '미설정'}</div>
                  </div>
                  <div class="row mb-2">
                    <div class="col-4"><strong>역할:</strong></div>
                    <div class="col-8">${s.role ? window.dashboardRoleMap[s.role] || s.role : '미설정'}</div>
                  </div>
                  <div class="row mb-2">
                    <div class="col-4"><strong>상태:</strong></div>
                    <div class="col-8">${s.status}</div>
                  </div>
                </div>
              </div>
              <div class="mt-3">
                <button class="btn btn-outline-primary btn-sm me-2" onclick="openServerConfig('${s.name}')">
                  <i class="fas fa-cog"></i> 서버 설정
                </button>
                <button class="btn btn-outline-info btn-sm me-2" onclick="viewServerLogs('${s.name}')">
                  <i class="fas fa-file-alt"></i> 로그 보기
                </button>
                <button class="btn btn-outline-warning btn-sm" onclick="backupServer('${s.name}')">
                  <i class="fas fa-download"></i> 백업
                </button>
              </div>
            </div>
          </td>
        </tr>
      `;
      
      html += serverRow;
    }
    
    $('#servers-table tbody').html(html);
    
    // 전체 선택 체크박스 상태 복원
    const totalCheckboxes = $('.server-checkbox').length;
    const checkedCheckboxes = $('.server-checkbox:checked').length;
    
    if (checkedCheckboxes === 0) {
      $('#select-all-servers').prop('indeterminate', false).prop('checked', false);
    } else if (checkedCheckboxes === totalCheckboxes) {
      $('#select-all-servers').prop('indeterminate', false).prop('checked', true);
    } else {
      $('#select-all-servers').prop('indeterminate', true);
    }
    
    // 일괄 작업 도구모음 상태 업데이트
    updateBulkActionsToolbar();
    
    // 서버 이름 클릭 이벤트 바인딩
    $('.server-name-cell').off('click').on('click', function(e) {
      e.stopPropagation();
      const serverName = $(this).closest('tr').data('server');
      const detailRow = $(`.server-detail-row[data-server="${serverName}"]`);
      const expandIcon = $(this).find('.expand-icon');
      
      if (detailRow.is(':visible')) {
        // 상세 정보 접기
        detailRow.slideUp(200);
        expandIcon.css('transform', 'rotate(0deg)');
      } else {
        // 다른 모든 상세 정보 접기
        $('.server-detail-row').slideUp(200);
        $('.expand-icon').css('transform', 'rotate(0deg)');
        
        // 현재 서버 상세 정보 펼치기
        detailRow.slideDown(200);
        expandIcon.css('transform', 'rotate(90deg)');
      }
    });
  }
  
  // 중복 바인딩 방지: 기존 이벤트 제거
  $('#list-tab').off('shown.bs.tab');
  
  // 최초 진입 시 서버 목록 탭이 active면 한 번만 호출
  if ($('#list-tab').hasClass('active')) {
  loadActiveServers();
  }
  
  // 기존 바인딩 제거 후 바인딩
  $('#list-tab').off('shown.bs.tab').on('shown.bs.tab', function() {
    console.log('[instances.js] list-tab shown');
    loadActiveServers();
  });

  // 작업 상태 폴링 관리
  let activeTasks = {};
  function pollTaskStatus(task_id, type, name) {
    if (!task_id) return;
    let progressNotified = false;
    let startTime = Date.now();
    
    // Task 설정 로드 후 폴링 시작
    loadTaskConfig().then(function(config) {
      const TIMEOUT = config.timeout * 1000; // 서버에서 가져온 타임아웃 (밀리초)
      console.log(`[instances.js] Task 폴링 시작: ${task_id}, 타임아웃: ${config.timeout_hours}시간`);
      
      activeTasks[task_id] = setInterval(function() {
        // 클라이언트 측 타임아웃 체크
        const elapsed = Date.now() - startTime;
        if (elapsed > TIMEOUT) {
          console.log(`⏰ 클라이언트 타임아웃: ${task_id}`);
          addSystemNotification('error', type, `${name} ${type} 타임아웃 (${config.timeout_hours}시간 초과)`);
          clearInterval(activeTasks[task_id]);
          delete activeTasks[task_id];
          
          // 일괄 작업 타임아웃 시에도 플래그 해제
          if (type === 'bulk_server_action') {
            isBulkOperationInProgress = false;
            console.log('[instances.js] 일괄 작업 타임아웃 - 자동 새로고침 재활성화');
            updateRefreshButtonState();
          }
          return;
        }
        
        $.get('/api/tasks/status', { task_id }, function(res) {
          console.log(`🔍 Task 상태 조회: ${task_id} - ${res.status} - ${res.message}`);
          
          if ((res.status === 'running' || res.status === 'pending') && !progressNotified) {
            addSystemNotification('info', type, `${name} ${type} 중...`);
            progressNotified = true;
          } else if (res.status === 'completed') {
            addSystemNotification('success', type, `${name} ${type} 완료`);
            clearInterval(activeTasks[task_id]);
            delete activeTasks[task_id];
            
            // 역할 설치 완료 시 버튼 상태 복원
            if (type === 'ansible_role_install') {
              console.log(`🔄 역할 설치 완료, 버튼 상태 복원: ${task_id}`);
              const btn = $(`.server-role-apply[data-server="${name}"]`);
              if (btn.length) {
                btn.prop('disabled', false).html('<i class="fas fa-check"></i> <span>역할 적용</span>');
              }
            }
            
            // 일괄 역할 할당 완료 시 플래그 해제
            if (type === 'assign_roles_bulk') {
              isBulkOperationInProgress = false;
              console.log('[instances.js] 일괄 역할 할당 완료 - 자동 새로고침 재활성화');
              updateRefreshButtonState();
            }
            
            // 일괄 보안그룹 할당 완료 시 플래그 해제
            if (type === 'assign_security_groups_bulk') {
              isBulkOperationInProgress = false;
              console.log('[instances.js] 일괄 보안그룹 할당 완료 - 자동 새로고침 재활성화');
              updateRefreshButtonState();
            }
            
            // 다중 서버 생성 완료 시 폼 복원
            if (type === 'create_servers_bulk') {
              console.log(`🔄 다중 서버 생성 완료, 폼 복원: ${task_id}`);
              restoreServerForm();
            }
            
            // 일괄 작업 완료 시 플래그 해제 및 새로고침
            if (type === 'bulk_server_action') {
              isBulkOperationInProgress = false;
              console.log('[instances.js] 일괄 작업 완료 - 자동 새로고침 재활성화');
              updateRefreshButtonState();
            }
            
            // 서버 목록 즉시 새로고침
            console.log(`🔄 ${type} 완료, 목록 새로고침: ${task_id}`);
            setTimeout(function() {
              loadActiveServers();
            }, 2000); // 2초 후 새로고침 (서버 상태 안정화 대기)
          } else if (res.status === 'failed') {
            addSystemNotification('error', type, `${name} ${type} 실패: ${res.message}`);
            clearInterval(activeTasks[task_id]);
            delete activeTasks[task_id];
            
            // 역할 설치 실패 시 버튼 상태 복원
            if (type === 'ansible_role_install') {
              console.log(`🔄 역할 설치 실패, 버튼 상태 복원: ${task_id}`);
              const btn = $(`.server-role-apply[data-server="${name}"]`);
              if (btn.length) {
                btn.prop('disabled', false).html('<i class="fas fa-check"></i> <span>역할 적용</span>');
              }
            }
            
            // 일괄 역할 할당 실패 시에도 플래그 해제
            if (type === 'assign_roles_bulk') {
              isBulkOperationInProgress = false;
              console.log('[instances.js] 일괄 역할 할당 실패 - 자동 새로고침 재활성화');
              updateRefreshButtonState();
            }
            
            // 일괄 보안그룹 할당 실패 시에도 플래그 해제
            if (type === 'assign_security_groups_bulk') {
              isBulkOperationInProgress = false;
              console.log('[instances.js] 일괄 보안그룹 할당 실패 - 자동 새로고침 재활성화');
              updateRefreshButtonState();
            }
            
            // 다중 서버 생성 실패 시 폼 복원
            if (type === 'create_servers_bulk') {
              console.log(`🔄 다중 서버 생성 실패, 폼 복원: ${task_id}`);
              restoreServerForm();
            }
            
            // 일괄 작업 실패 시에도 플래그 해제
            if (type === 'bulk_server_action') {
              isBulkOperationInProgress = false;
              console.log('[instances.js] 일괄 작업 실패 - 자동 새로고침 재활성화');
              updateRefreshButtonState();
            }
            
            // 실패 시에도 목록 새로고침 (DB 정리 확인)
            console.log(`🔄 ${type} 실패, 목록 새로고침: ${task_id}`);
            setTimeout(function() {
              loadActiveServers();
            }, 1000);
          }
        }).fail(function(xhr, status, error) {
          console.log(`❌ Task 상태 조회 실패: ${task_id} - ${error}`);
          clearInterval(activeTasks[task_id]);
          delete activeTasks[task_id];
          
          // 일괄 작업 AJAX 실패 시에도 플래그 해제
          if (type === 'bulk_server_action') {
            isBulkOperationInProgress = false;
            console.log('[instances.js] 일괄 작업 AJAX 실패 - 자동 새로고침 재활성화');
            updateRefreshButtonState();
          }
        });
      }, config.polling_interval || 5000);
    });
  }

  // AJAX 전역 설정 - 세션 만료 처리
  $.ajaxSetup({
    statusCode: {
      401: function() {
        console.log('[instances.js] AJAX 401 오류 - 세션 만료');
        if (window.sessionManager) {
          window.sessionManager.handleSessionExpired();
        } else {
          window.location.href = '/auth/login';
        }
      }
    }
  });

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
      if (!selectedOS) { 
        alertModal('OS를 선택해주세요.'); 
        return false; 
      }
      if (!baseName || baseName.trim() === '') { 
        alertModal('서버 이름을 입력해주세요.'); 
        return false; 
      }
      if (!count || count < 2) { 
        alertModal('서버 개수는 2 이상이어야 합니다.'); 
        return false; 
      }
      // 네트워크 입력값 검증 (IP, 서브넷, 게이트웨이 모두 필수)
      let hasError = false;
      networks.forEach(function(n, idx) {
        if (!n.ip || !n.subnet || !n.gateway) {
          alertModal(`네트워크 카드 #${idx+1}의 IP, 서브넷, 게이트웨이를 모두 입력해주세요.`);
          hasError = true;
        }
      });
      if (hasError) return false;
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
      $.get('/api/instances/multi-server-summary', function(html) {
        console.log('다중서버 요약 템플릿 로드 성공:', html.substring(0, 100) + '...');
        $('#multiServerSummarySection').html(html);
        
        // 테이블 내용 동적 생성
        let tableRows = '';
        serverList.forEach((s, sidx) => {
          s.networks.forEach((net, nidx) => {
            tableRows += `
              <tr data-sidx="${sidx}" data-nidx="${nidx}">
                ${nidx === 0 ? `
                  <td rowspan="${s.networks.length}">
                    <input type="text" class="form-control form-control-sm summary-name" value="${s.name}" placeholder="서버명">
                  </td>
                  <td rowspan="${s.networks.length}">${s.os}</td>
                  <td rowspan="${s.networks.length}">
                    <input type="number" class="form-control form-control-sm summary-cpu" value="${s.cpu}" min="1" max="32" placeholder="코어">
                  </td>
                  <td rowspan="${s.networks.length}">
                    <input type="number" class="form-control form-control-sm summary-memory" value="${s.memory}" min="1" max="131072" placeholder="MB">
                  </td>
                  <td rowspan="${s.networks.length}">
                    <div class="disk-inputs">
                      ${s.disks.map((d, didx) => `
                        <div class="mb-1">
                          <input type="number" class="form-control form-control-sm summary-disk-size" 
                                 data-disk-idx="${didx}" value="${d.size}" min="1" max="1000" placeholder="GB">
                          <small class="text-muted">${d.interface}/${d.datastore_id}</small>
                        </div>
                      `).join('')}
                    </div>
                  </td>
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
      }).fail(function(xhr, status, error) {
        console.error('다중서버 요약 템플릿 로드 실패:', error);
        console.error('상태:', status);
        console.error('응답:', xhr.responseText);
        alertModal('다중서버 요약 화면을 로드할 수 없습니다: ' + error);
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
            // 서버 기본 정보 반영
            serverList[sidx].name = $(this).find('.summary-name').val();
            serverList[sidx].cpu = parseInt($(this).find('.summary-cpu').val()) || 1;
            serverList[sidx].memory = parseInt($(this).find('.summary-memory').val()) || 1;
            serverList[sidx].role = $(this).find('.summary-role').val();
            
            // 디스크 크기 반영
            $(this).find('.summary-disk-size').each(function() {
              const diskIdx = $(this).data('disk-idx');
              const newSize = parseInt($(this).val()) || 1;
              if (serverList[sidx].disks[diskIdx]) {
                serverList[sidx].disks[diskIdx].size = newSize;
              }
            });
          }
          
          // 네트워크 정보 반영
          serverList[sidx].networks[nidx].bridge = $(this).find('.summary-bridge').val();
          serverList[sidx].networks[nidx].ip = $(this).find('.summary-ip').val();
          serverList[sidx].networks[nidx].subnet = $(this).find('.summary-subnet').val();
          serverList[sidx].networks[nidx].gateway = $(this).find('.summary-gateway').val();
        });
        
        // 유효성 검사
        const errors = [];
        serverList.forEach((s, idx) => {
          if (!s.name || s.name.trim() === '') {
            errors.push(`서버 ${idx + 1}: 서버명을 입력해주세요.`);
          }
          if (s.cpu < 1 || s.cpu > 32) {
            errors.push(`서버 ${s.name}: CPU는 1-32 코어 사이여야 합니다.`);
          }
          if (s.memory < 1 || s.memory > 131072) {
            errors.push(`서버 ${s.name}: 메모리는 1-131072 MB 사이여야 합니다.`);
          }
          s.disks.forEach((disk, diskIdx) => {
            if (disk.size < 1 || disk.size > 1000) {
              errors.push(`서버 ${s.name} 디스크 ${diskIdx + 1}: 디스크 크기는 1-1000 GB 사이여야 합니다.`);
            }
          });
        });
        
        if (errors.length > 0) {
          alertModal('입력 오류:\n' + errors.join('\n'));
          $btn.prop('disabled', false).html('<i class="fas fa-plus me-2"></i>서버 생성');
          $btn.data('processing', false);
          return;
        }
        
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
          url: '/api/create_servers_bulk',
          method: 'POST',
          contentType: 'application/json',
          data: JSON.stringify({servers}),
          success: function(res) {
            if (res.success && res.task_id) {
              addSystemNotification('success', '서버 생성', res.message);
              // 작업 상태 폴링 시작
              pollTaskStatus(res.task_id, 'create_servers_bulk', serverList.map(s => s.name).join(', '));
            } else {
              addSystemNotification('success', '서버 생성', '다중 서버 생성 요청 완료');
              // 서버 생성 폼 복원
              restoreServerForm();
              loadActiveServers();
            }
          },
          error: function(xhr) {
            addSystemNotification('error', '서버 생성', '다중 서버 생성 실패: ' + (xhr.responseJSON?.error || xhr.statusText));
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
    if (!selectedOS) { 
      alertModal('OS를 선택해주세요.'); 
      return false; 
    }
    const name = $('input[name="name_basic"]').val();
    if (!name || name.trim() === '') { 
      alertModal('서버 이름을 입력해주세요.'); 
      return false; 
    }
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
    if (hasError) return false;
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
      url: '/api/servers',
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





  // Security Group 적용
  $(document).off('click', '.server-security-group-apply').on('click', '.server-security-group-apply', function() {
    console.log('[instances.js] .server-security-group-apply 클릭');
    const btn = $(this);
    const tr = btn.closest('tr');
    const server = tr.data('server');
    const securityGroup = tr.find('.server-security-group-select').val();
    
    if (!securityGroup) {
      addSystemNotification('error', 'Security Group 적용', 'Security Group을 선택해주세요.');
      return;
    }
    
    // 시작 알림 추가
    addSystemNotification('info', 'Security Group 적용', `${server} 서버에 ${securityGroup} Security Group을 적용하는 중...`);
    
    btn.prop('disabled', true).html('<i class="fas fa-spinner fa-spin"></i> <span>적용 중...</span>');
    $.ajax({
      url: `/api/apply_security_group/${server}`,
      method: 'POST',
      contentType: 'application/json',
      data: JSON.stringify({ security_group: securityGroup }),
      success: function(res) {
      console.log('[instances.js] /api/apply_security_group 성공', res);
      btn.prop('disabled', false).html('<i class="fas fa-check"></i> <span>적용</span>');
      loadActiveServers();
      addSystemNotification('success', 'Security Group 적용', `${server} 서버에 ${securityGroup} Security Group이 성공적으로 적용되었습니다.`);
      },
      error: function(xhr) {
      console.error('[instances.js] /api/apply_security_group 실패', xhr);
      btn.prop('disabled', false).html('<i class="fas fa-check"></i> <span>적용</span>');
      
      let errorMsg = '알 수 없는 오류';
      if (xhr.status === 403) {
        errorMsg = '권한이 없습니다. Security Group 할당 권한이 필요합니다.';
      } else if (xhr.responseJSON?.error) {
        errorMsg = xhr.responseJSON.error;
      }
      
      addSystemNotification('error', 'Security Group 적용', `${server} 서버 Security Group 적용 실패: ${errorMsg}`);
      }
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
    $.post('/api/servers/' + name + '/start', function(res) {
      console.log('[instances.js] /api/servers/' + name + '/start 성공', res);
      btn.prop('disabled', false).html(originalText);
      // 즉시 상태 업데이트
      setTimeout(function() {
      loadActiveServers();
      }, 1000); // 1초 후 상태 업데이트
      addSystemNotification('success', '서버 시작', `${name} 서버가 시작되었습니다.`);
    }).fail(function(xhr){
      console.error('[instances.js] /api/servers/' + name + '/start 실패', xhr);
      btn.prop('disabled', false).html(originalText);
      
      let errorMsg = xhr.statusText;
      if (xhr.status === 403) {
        errorMsg = '권한이 없습니다. 서버 시작 권한이 필요합니다.';
      } else if (xhr.responseJSON?.error) {
        errorMsg = xhr.responseJSON.error;
      }
      
      addSystemNotification('error', '서버 시작', `${name} 서버 시작 실패: ${errorMsg}`);
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
    $.post('/api/servers/' + name + '/stop', function(res) {
      console.log('[instances.js] /api/servers/' + name + '/stop 성공', res);
      btn.prop('disabled', false).html(originalText);
      // 즉시 상태 업데이트
      setTimeout(function() {
      loadActiveServers();
      }, 1000); // 1초 후 상태 업데이트
      addSystemNotification('success', '서버 중지', `${name} 서버가 중지되었습니다.`);
    }).fail(function(xhr){
      console.error('[instances.js] /api/servers/' + name + '/stop 실패', xhr);
      btn.prop('disabled', false).html(originalText);
      
      let errorMsg = xhr.statusText;
      if (xhr.status === 403) {
        errorMsg = '권한이 없습니다. 서버 중지 권한이 필요합니다.';
      } else if (xhr.responseJSON?.error) {
        errorMsg = xhr.responseJSON.error;
      }
      
      addSystemNotification('error', '서버 중지', `${name} 서버 중지 실패: ${errorMsg}`);
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
    $.post('/api/servers/' + name + '/reboot', function(res) {
      console.log('[instances.js] /api/servers/' + name + '/reboot 성공', res);
      btn.prop('disabled', false).html(originalText);
      // 즉시 상태 업데이트
      setTimeout(function() {
      loadActiveServers();
      }, 2000); // 2초 후 상태 업데이트 (재부팅은 시간이 더 필요)
      addSystemNotification('success', '서버 리부팅', `${name} 서버가 리부팅되었습니다.`);
    }).fail(function(xhr){
      console.error('[instances.js] /api/servers/' + name + '/reboot 실패', xhr);
      btn.prop('disabled', false).html(originalText);
      
      let errorMsg = xhr.statusText;
      if (xhr.status === 403) {
        errorMsg = '권한이 없습니다. 서버 리부팅 권한이 필요합니다.';
      } else if (xhr.responseJSON?.error) {
        errorMsg = xhr.responseJSON.error;
      }
      
      addSystemNotification('error', '서버 리부팅', `${name} 서버 리부팅 실패: ${errorMsg}`);
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
    $.post('/api/servers/' + name + '/delete', function(res) {
      console.log('[instances.js] /api/servers/' + name + '/delete 성공', res);
      if (res.task_id) {
        pollTaskStatus(res.task_id, '서버 삭제', name);
      }
      $('#delete-status-message').remove();
      addSystemNotification('success', '서버 삭제', `${name} 서버 삭제를 시작합니다.`);
    }).fail(function(xhr){
      console.error('[instances.js] /api/servers/' + name + '/delete 실패', xhr);
      $('#delete-status-message').remove();
      btn.prop('disabled', false).html(originalText);
      btn.closest('tr').removeClass('table-warning');
      
      let errorMsg = xhr.statusText;
      if (xhr.status === 403) {
        errorMsg = '권한이 없습니다. 서버 삭제 권한이 필요합니다.';
      } else if (xhr.responseJSON?.error) {
        errorMsg = xhr.responseJSON.error;
      }
      
      addSystemNotification('error', '서버 삭제', `${name} 서버 삭제 실패: ${errorMsg}`);
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
    
    // 일괄 작업 중에는 강제 새로고침 허용
    if (isBulkOperationInProgress) {
      console.log('[instances.js] 일괄 작업 중 강제 새로고침 실행');
      isBulkOperationInProgress = false; // 플래그 해제
      updateRefreshButtonState();
    }
    
    loadActiveServers();
  });

  // 뷰 전환 버튼 클릭 이벤트
  $(document).off('click', '.btn-view').on('click', '.btn-view', function() {
    const viewType = $(this).data('view');
    console.log('[instances.js] 뷰 전환 버튼 클릭:', viewType);
    
    // 활성 버튼 변경
    $('.btn-view').removeClass('active');
    $(this).addClass('active');
    
    console.log('[instances.js] 뷰 컨테이너 전환 시작');
    
    // 뷰 컨테이너 전환
    if (viewType === 'table') {
      console.log('[instances.js] 테이블 뷰로 전환');
      $('#servers-grid').hide();
      $('#servers-table-container').show();
      // 테이블 뷰로 다시 렌더링
      if (window.serversData) {
        renderTableView(window.serversData, window.firewallGroups || []);
      }
    } else {
      console.log('[instances.js] 카드 뷰로 전환');
      $('#servers-table-container').hide();
      $('#servers-grid').show();
      // 카드 뷰로 다시 렌더링
      if (window.serversData) {
        renderCardView(window.serversData, window.firewallGroups || []);
      }
    }
    
    console.log('[instances.js] 뷰 전환 완료');
  });

  // 서버 검색 기능
  $(document).off('input', '#server-search').on('input', '#server-search', function() {
    const searchTerm = $(this).val().toLowerCase();
    console.log('[instances.js] 서버 검색:', searchTerm);
    
    if (!window.serversData) return;
    
    // 검색 결과 필터링
    const filteredServers = {};
    for (const [name, server] of Object.entries(window.serversData)) {
      if (name.toLowerCase().includes(searchTerm) || 
          (server.role && server.role.toLowerCase().includes(searchTerm)) ||
          (server.ip_addresses && server.ip_addresses.some(ip => ip.includes(searchTerm)))) {
        filteredServers[name] = server;
      }
    }
    
    // 현재 뷰에 따라 렌더링
    const currentView = getCurrentViewType();
    if (currentView === 'table') {
      renderTableView(filteredServers, window.firewallGroups || []);
    } else {
      renderCardView(filteredServers, window.firewallGroups || []);
    }
    
    // 검색 결과 개수 업데이트
    const resultCount = Object.keys(filteredServers).length;
    $('#server-count').text(`${resultCount}개`);
  });

  // 전체 선택/해제 체크박스
  $(document).off('change', '#select-all-servers').on('change', '#select-all-servers', function() {
    const isChecked = $(this).is(':checked');
    $('.server-checkbox').prop('checked', isChecked);
    updateBulkActionsToolbar();
  });

  // 개별 서버 체크박스
  $(document).off('change', '.server-checkbox').on('change', '.server-checkbox', function() {
    updateBulkActionsToolbar();
    
    // 전체 선택 체크박스 상태 업데이트
    const totalCheckboxes = $('.server-checkbox').length;
    const checkedCheckboxes = $('.server-checkbox:checked').length;
    
    if (checkedCheckboxes === 0) {
      $('#select-all-servers').prop('indeterminate', false).prop('checked', false);
    } else if (checkedCheckboxes === totalCheckboxes) {
      $('#select-all-servers').prop('indeterminate', false).prop('checked', true);
    } else {
      $('#select-all-servers').prop('indeterminate', true);
    }
  });

  // 대량 작업 도구모음 업데이트
  function updateBulkActionsToolbar() {
    const checkedServers = $('.server-checkbox:checked');
    const count = checkedServers.length;
    
    if (count > 0) {
      $('#bulk-actions-btn').prop('disabled', false);
      $('#bulk-actions-toolbar').addClass('show');
      $('#selected-count').text(count);
    } else {
      $('#bulk-actions-btn').prop('disabled', true);
      $('#bulk-actions-toolbar').removeClass('show');
    }
  }

  // 탭 전환 기능
  $(document).off('click', '.bulk-tab-btn').on('click', '.bulk-tab-btn', function() {
    const tabName = $(this).data('tab');
    
    // 탭 버튼 활성화
    $('.bulk-tab-btn').removeClass('active');
    $(this).addClass('active');
    
    // 탭 내용 전환
    $('.bulk-tab-content').removeClass('active');
    $(`#${tabName}-tab`).addClass('active');
    
    // 설정 탭일 때 보안그룹 목록 로드
    if (tabName === 'settings') {
      loadSecurityGroupsForBulk();
    }
  });

  // 보안그룹 목록 로드 (일괄 설정용)
  function loadSecurityGroupsForBulk() {
    $.get('/api/firewall/groups', function(res) {
      if (res.success) {
        let options = '<option value="">보안그룹을 선택하세요</option>';
        res.groups.forEach(function(group) {
          options += `<option value="${group.name}">${group.name} (${group.description || '설명 없음'})</option>`;
        });
        $('#bulk-security-group-select').html(options);
      }
    }).fail(function(xhr) {
      console.error('보안그룹 목록 로드 실패:', xhr);
      $('#bulk-security-group-select').html('<option value="">로드 실패</option>');
    });
  }

  // 대량 작업 함수들 (새로운 API 사용)
  window.bulkStartServers = function() {
    const serverNames = getSelectedServerNames();
    if (serverNames.length === 0) return;
    
    if (confirm(`선택된 ${serverNames.length}개 서버를 시작하시겠습니까?`)) {
      console.log('[instances.js] 일괄 시작:', serverNames);
      executeBulkAction(serverNames, 'start');
    }
  };

  window.bulkStopServers = function() {
    const serverNames = getSelectedServerNames();
    if (serverNames.length === 0) return;
    
    if (confirm(`선택된 ${serverNames.length}개 서버를 중지하시겠습니까?`)) {
      console.log('[instances.js] 일괄 중지:', serverNames);
      executeBulkAction(serverNames, 'stop');
    }
  };

  window.bulkRebootServers = function() {
    const serverNames = getSelectedServerNames();
    if (serverNames.length === 0) return;
    
    if (confirm(`선택된 ${serverNames.length}개 서버를 재시작하시겠습니까?`)) {
      console.log('[instances.js] 일괄 재시작:', serverNames);
      executeBulkAction(serverNames, 'reboot');
    }
  };

  window.bulkDeleteServers = function() {
    const serverNames = getSelectedServerNames();
    if (serverNames.length === 0) return;
    
    if (confirm(`선택된 ${serverNames.length}개 서버를 삭제하시겠습니까?\n\n⚠️ 이 작업은 되돌릴 수 없습니다!`)) {
      console.log('[instances.js] 일괄 삭제:', serverNames);
      executeBulkAction(serverNames, 'delete');
    }
  };

  // 대량 작업 API 호출
  function executeBulkAction(serverNames, action) {
    console.log(`[instances.js] 대량 작업 실행: ${action} - ${serverNames.length}개 서버`);
    
    // 일괄 작업 시작 플래그 설정
    isBulkOperationInProgress = true;
    console.log('[instances.js] 일괄 작업 시작 - 자동 새로고침 비활성화');
    
    // 새로고침 버튼 상태 업데이트
    updateRefreshButtonState();
    
    // 선택 해제 및 도구모음 숨김
    clearSelection();
    
    // 대량 작업 API 호출
    $.ajax({
      url: '/api/servers/bulk_action',
      method: 'POST',
      contentType: 'application/json',
      data: JSON.stringify({
        server_names: serverNames,
        action: action
      }),
      success: function(res) {
        if (res.success && res.task_id) {
          const actionNames = {
            'start': '시작',
            'stop': '중지',
            'reboot': '재시작', 
            'delete': '삭제'
          };
          const actionName = actionNames[action] || action;
          
          addSystemNotification('success', '대량 작업', res.message);
          
          // 작업 상태 폴링 시작
          pollTaskStatus(res.task_id, 'bulk_server_action', `${serverNames.length}개 서버 ${actionName}`);
        } else {
          addSystemNotification('error', '대량 작업', '대량 작업 요청 실패');
        }
      },
      error: function(xhr) {
        const errorMsg = xhr.responseJSON?.error || xhr.statusText || '알 수 없는 오류';
        addSystemNotification('error', '대량 작업', `대량 작업 실패: ${errorMsg}`);
        console.error('[instances.js] 대량 작업 실패:', xhr);
      }
    });
  }

  window.clearSelection = function() {
    $('.server-checkbox, #select-all-servers').prop('checked', false);
    updateBulkActionsToolbar();
  };



  // 일괄 역할 할당 실행 (설정 탭에서 호출)
  window.executeBulkRoleAssignment = function() {
    const serverNames = getSelectedServerNames();
    const role = $('#bulk-role-select').val();
    
    if (serverNames.length === 0) {
      addSystemNotification('warning', '서버 선택', '할당할 서버를 선택해주세요.');
      return;
    }
    
    if (!role) {
      addSystemNotification('warning', '역할 선택', '할당할 역할을 선택해주세요.');
      return;
    }
    
    console.log(`[instances.js] 일괄 역할 할당: ${serverNames.length}개 서버 - ${role}`);
    
    // 일괄 작업 시작 플래그 설정
    isBulkOperationInProgress = true;
    console.log('[instances.js] 일괄 역할 할당 시작 - 자동 새로고침 비활성화');
    
    // 새로고침 버튼 상태 업데이트
    updateRefreshButtonState();
    
    // 선택 해제 및 도구모음 숨김
    clearSelection();
    
    // 시작 알림
    addSystemNotification('info', '일괄 역할 할당', `${serverNames.length}개 서버에 ${role} 역할을 할당하는 중...`);
    
    // 일괄 역할 할당 API 호출
    $.ajax({
      url: '/api/roles/assign_bulk',
      method: 'POST',
      contentType: 'application/json',
      data: JSON.stringify({
        server_names: serverNames,
        role: role
      }),
      success: function(res) {
        console.log('[instances.js] 일괄 역할 할당 성공:', res);
        
        if (res.task_id) {
          // Task 진행 상황 모니터링
          pollTaskStatus(res.task_id, 'assign_roles_bulk', `${serverNames.length}개 서버`);
        } else {
          // 즉시 완료된 경우
          addSystemNotification('success', '일괄 역할 할당', `${serverNames.length}개 서버에 ${role} 역할이 성공적으로 할당되었습니다.`);
          loadActiveServers();
        }
      },
      error: function(xhr) {
        console.error('[instances.js] 일괄 역할 할당 실패:', xhr);
        
        // 일괄 작업 플래그 해제
        isBulkOperationInProgress = false;
        updateRefreshButtonState();
        
        let errorMsg = '알 수 없는 오류';
        if (xhr.status === 403) {
          errorMsg = '권한이 없습니다. 역할 할당 권한이 필요합니다.';
        } else if (xhr.responseJSON?.error) {
          errorMsg = xhr.responseJSON.error;
        }
        
        addSystemNotification('error', '일괄 역할 할당', `${serverNames.length}개 서버 역할 할당 실패: ${errorMsg}`);
      }
    });
  };

  // 일괄 보안그룹 할당 (새로운 함수)
  window.bulkAssignSecurityGroup = function() {
    const serverNames = getSelectedServerNames();
    const securityGroup = $('#bulk-security-group-select').val();
    
    if (serverNames.length === 0) {
      addSystemNotification('warning', '서버 선택', '할당할 서버를 선택해주세요.');
      return;
    }
    
    if (!securityGroup) {
      addSystemNotification('warning', '보안그룹 선택', '할당할 보안그룹을 선택해주세요.');
      return;
    }
    
    console.log(`[instances.js] 일괄 보안그룹 할당: ${serverNames.length}개 서버 - ${securityGroup}`);
    
    // 일괄 작업 시작 플래그 설정
    isBulkOperationInProgress = true;
    console.log('[instances.js] 일괄 보안그룹 할당 시작 - 자동 새로고침 비활성화');
    
    // 새로고침 버튼 상태 업데이트
    updateRefreshButtonState();
    
    // 선택 해제 및 도구모음 숨김
    clearSelection();
    
    // 시작 알림
    addSystemNotification('info', '일괄 보안그룹 할당', `${serverNames.length}개 서버에 ${securityGroup} 보안그룹을 할당하는 중...`);
    
    // 일괄 보안그룹 할당 API 호출
    $.ajax({
      url: '/api/firewall/assign_bulk',
      method: 'POST',
      contentType: 'application/json',
      data: JSON.stringify({
        server_names: serverNames,
        security_group: securityGroup
      }),
      success: function(res) {
        console.log('[instances.js] 일괄 보안그룹 할당 성공:', res);
        
        if (res.task_id) {
          // Task 진행 상황 모니터링
          pollTaskStatus(res.task_id, 'assign_security_groups_bulk', `${serverNames.length}개 서버`);
        } else {
          // 즉시 완료된 경우
          addSystemNotification('success', '일괄 보안그룹 할당', `${serverNames.length}개 서버에 ${securityGroup} 보안그룹이 성공적으로 할당되었습니다.`);
          loadActiveServers();
        }
      },
      error: function(xhr) {
        console.error('[instances.js] 일괄 보안그룹 할당 실패:', xhr);
        
        // 일괄 작업 플래그 해제
        isBulkOperationInProgress = false;
        updateRefreshButtonState();
        
        let errorMsg = '알 수 없는 오류';
        if (xhr.status === 403) {
          errorMsg = '권한이 없습니다. 보안그룹 할당 권한이 필요합니다.';
        } else if (xhr.responseJSON?.error) {
          errorMsg = xhr.responseJSON.error;
        }
        
        addSystemNotification('error', '일괄 보안그룹 할당', `${serverNames.length}개 서버 보안그룹 할당 실패: ${errorMsg}`);
      }
    });
  };

  // 선택된 서버 이름들 가져오기
  function getSelectedServerNames() {
    return $('.server-checkbox:checked').map(function() {
      return $(this).val();
    }).get();
  }

  // 서버 액션 실행 (기존 함수 활용)
  function executeServerAction(serverName, action) {
    const $serverElement = $(`[data-server="${serverName}"]`);
    let $actionBtn;
    
    switch(action) {
      case 'start':
        $actionBtn = $serverElement.find('.start-btn');
        break;
      case 'stop':
        $actionBtn = $serverElement.find('.stop-btn');
        break;
      case 'reboot':
        $actionBtn = $serverElement.find('.reboot-btn');
        break;
      case 'delete':
        $actionBtn = $serverElement.find('.delete-btn');
        break;
      default:
        return;
    }
    
    if ($actionBtn.length > 0 && !$actionBtn.prop('disabled')) {
      $actionBtn.trigger('click');
    }
  }

  // 모든 알림 삭제 버튼 핸들러
  $(document).off('click', '#clear-all-notifications').on('click', '#clear-all-notifications', async function(e) {
    e.preventDefault();
    const ok = await confirmModal('모든 알림을 삭제하시겠습니까?');
    if (!ok) return;
    $.post('/api/notifications/clear-all', function(res) {
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

  // 일괄 작업 상태에 따른 새로고침 버튼 업데이트
  function updateRefreshButtonState() {
    const $refreshBtn = $('.refresh-btn');
    if (isBulkOperationInProgress) {
      $refreshBtn.addClass('btn-warning').removeClass('btn-refresh');
      $refreshBtn.find('span').text('일괄 작업 중...');
      $refreshBtn.find('i').removeClass('fa-sync-alt').addClass('fa-clock');
      $refreshBtn.prop('title', '일괄 작업 중입니다. 필요시 클릭하여 강제 새로고침');
    } else {
      $refreshBtn.removeClass('btn-warning').addClass('btn-refresh');
      $refreshBtn.find('span').text('새로고침');
      $refreshBtn.find('i').removeClass('fa-clock').addClass('fa-sync-alt');
      $refreshBtn.prop('title', '서버 목록 새로고침');
    }
  }
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
          <div class="dropdown-item d-flex align-items-start small" style="padding: 12px 16px; border-bottom: 1px solid #f0f0f0;">
            <i class="fas ${icon} me-2 mt-1"></i>
            <div class="flex-grow-1">
              <div class="fw-bold mb-1">${noti.title}</div>
              <div class="text-muted" style="word-wrap: break-word; white-space: normal; line-height: 1.5; margin-bottom: 4px;">${noti.message}</div>
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