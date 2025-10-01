"""
서버 관련 Celery 작업
"""
from celery import current_task
from app.celery_app import celery_app
from app.services import ProxmoxService, TerraformService, AnsibleService
from app.models import Server, Notification
from app import db
import logging
import time

logger = logging.getLogger(__name__)

@celery_app.task(bind=True)
def create_server_async(self, server_config):
    """비동기 서버 생성 작업"""
    try:
        task_id = self.request.id
        logger.info(f"🚀 비동기 서버 생성 시작: {server_config['name']} (Task ID: {task_id})")
        
        # 작업 상태 업데이트
        self.update_state(
            state='PROGRESS',
            meta={'current': 0, 'total': 100, 'status': '서버 생성 준비 중...'}
        )
        
        # Terraform 서비스 초기화 (환경 변수 기반)
        import os
        
        # 원격 서버 설정 확인 (단순화)
        remote_config = None
        if os.getenv('TERRAFORM_REMOTE_ENABLED', 'false').lower() == 'true':
            remote_config = {
                'host': os.getenv('TERRAFORM_REMOTE_HOST'),
                'port': int(os.getenv('TERRAFORM_REMOTE_PORT', 22)),
                'username': os.getenv('TERRAFORM_REMOTE_USERNAME'),
                'password': os.getenv('TERRAFORM_REMOTE_PASSWORD'),  # 선택사항
                'key_file': os.getenv('TERRAFORM_REMOTE_KEY_FILE'),  # 선택사항
                'terraform_dir': os.getenv('TERRAFORM_REMOTE_DIR', '/opt/terraform')
            }
            terraform_service = TerraformService(remote_server=remote_config)
        else:
            # 로컬 실행 (기본값) - 로컬 terraform 디렉토리 사용
            terraform_service = TerraformService()  # 기본 terraform 디렉토리 사용
        
        # 1단계: Terraform 파일 생성
        self.update_state(
            state='PROGRESS',
            meta={'current': 20, 'total': 100, 'status': 'Terraform 파일 생성 중...'}
        )
        
        terraform_result = terraform_service.create_server_config(server_config)
        if not terraform_result:
            raise Exception("Terraform 파일 생성 실패")
        
        # 2단계: Terraform 실행
        self.update_state(
            state='PROGRESS',
            meta={'current': 40, 'total': 100, 'status': 'Terraform 실행 중...'}
        )
        
        # Terraform 타겟 형식으로 변환 (module.server["서버명"])
        target = f'module.server["{server_config["name"]}"]'
        apply_result = terraform_service.apply([target])
        if not apply_result[0]:  # apply 메서드는 (success, message) 튜플 반환
            raise Exception(f"Terraform 실행 실패: {apply_result[1]}")
        
        # 3단계: 서버 정보 DB 저장
        self.update_state(
            state='PROGRESS',
            meta={'current': 60, 'total': 100, 'status': '서버 정보 저장 중...'}
        )
        
        # disk 값 추출 (disks 배열에서 첫 번째 디스크 크기 사용)
        disk_size = server_config.get('disk')
        if disk_size is None and 'disks' in server_config and len(server_config['disks']) > 0:
            disk_size = server_config['disks'][0].get('size', 20)  # 기본값 20GB
        
        server = Server(
            name=server_config['name'],
            cpu=server_config['cpu'],
            memory=server_config['memory'],
            disk=disk_size or 20,  # 기본값 20GB
            os_type=server_config.get('os_type', 'ubuntu'),
            role=server_config.get('role', ''),
            firewall_group=server_config.get('firewall_group', ''),
            status='creating'
        )
        
        db.session.add(server)
        db.session.commit()
        
        # 4단계: 서버 상태 확인 (Proxmox 타임아웃 무시)
        self.update_state(
            state='PROGRESS',
            meta={'current': 80, 'total': 100, 'status': '서버 상태 확인 중...'}
        )
        
        # Proxmox에서 서버 상태 확인 (재시도 로직 포함)
        max_retries = 3
        retry_count = 0
        success = False
        
        while retry_count < max_retries and not success:
            try:
                proxmox_service = ProxmoxService()
                # 서버가 존재하고 실행 중인지 확인
                server_info = proxmox_service.get_server_info(server_config['name'])
                
                if server_info and server_info.get('status') == 'running':
                    server.status = 'running'
                    db.session.commit()
                    success = True
                    
                    # 성공 알림 생성
                    notification = Notification(
                        type='server_creation',
                        title='서버 생성 완료',
                        message=f'서버 {server_config["name"]}이 성공적으로 생성되었습니다.',
                        severity='success',
                        details=f'서버명: {server_config["name"]}\nCPU: {server_config["cpu"]}코어\n메모리: {server_config["memory"]}GB'
                    )
                    db.session.add(notification)
                    db.session.commit()
                    
                    logger.info(f"✅ 비동기 서버 생성 완료: {server_config['name']}")
                    break
                else:
                    # 서버가 존재하지만 실행되지 않은 경우 시작 시도
                    if proxmox_service.start_server(server_config['name']):
                        server.status = 'running'
                        db.session.commit()
                        success = True
                        logger.info(f"✅ 서버 시작 성공: {server_config['name']}")
                        break
                    else:
                        retry_count += 1
                        if retry_count < max_retries:
                            logger.warning(f"⚠️ 서버 시작 실패, 재시도 {retry_count}/{max_retries}")
                            time.sleep(5)  # 5초 대기 후 재시도
                        else:
                            server.status = 'stopped'
                            db.session.commit()
                            logger.error(f"❌ 서버 시작 실패 (최대 재시도 횟수 초과): {server_config['name']}")
                            
            except Exception as e:
                retry_count += 1
                if retry_count < max_retries:
                    logger.warning(f"⚠️ Proxmox 상태 확인 실패, 재시도 {retry_count}/{max_retries}: {e}")
                    time.sleep(5)  # 5초 대기 후 재시도
                else:
                    logger.error(f"❌ Proxmox 상태 확인 실패 (최대 재시도 횟수 초과): {e}")
                    server.status = 'unknown'
                    db.session.commit()
                    break
        
        # 최종 결과 처리
        if success:
            return {
                'success': True,
                'message': f'서버 {server_config["name"]} 생성 완료',
                'server_name': server_config['name'],
                'task_id': task_id
            }
        else:
            # 실패 처리: 서버 삭제 및 알림 생성
            try:
                proxmox_service = ProxmoxService()
                if proxmox_service.delete_server(server_config['name']):
                    logger.info(f"🗑️ 실패한 서버 삭제 완료: {server_config['name']}")
            except Exception as e:
                logger.warning(f"⚠️ 실패한 서버 삭제 실패: {e}")
            
            # 실패 알림 생성
            notification = Notification(
                type='server_creation',
                title='서버 생성 실패',
                message=f'서버 {server_config["name"]} 생성에 실패했습니다.',
                severity='error',
                details=f'서버명: {server_config["name"]}\n상태: {server.status}\n재시도 횟수: {max_retries}'
            )
            db.session.add(notification)
            db.session.commit()
            
            # 실패한 작업 정리
            server.status = 'failed'
            db.session.commit()
            
            # Celery 작업 실패 처리
            raise Exception(f'서버 {server_config["name"]} 생성 실패 (최대 재시도 횟수 초과)')
            
    except Exception as e:
        error_msg = str(e)
        logger.error(f"❌ 비동기 서버 생성 실패: {error_msg}")
        
        # 실패 알림 생성
        notification = Notification(
            type='server_creation',
            title='서버 생성 실패',
            message=f'서버 {server_config["name"]} 생성에 실패했습니다.',
            severity='error',
            details=f'오류: {error_msg}'
        )
        db.session.add(notification)
        db.session.commit()
        
        # 예외를 발생시키지 않고 결과만 반환
        return {
            'success': False,
            'error': error_msg,
            'message': f'서버 {server_config["name"]} 생성 실패'
        }

@celery_app.task(bind=True)
def bulk_server_action_async(self, server_names, action):
    """비동기 대량 서버 작업"""
    try:
        task_id = self.request.id
        logger.info(f"🚀 비동기 대량 서버 작업 시작: {action} - {len(server_names)}개 서버 (Task ID: {task_id})")
        
        success_servers = []
        failed_servers = []
        
        total_servers = len(server_names)
        
        for i, server_name in enumerate(server_names):
            try:
                # 작업 상태 업데이트
                progress = int((i / total_servers) * 100)
                self.update_state(
                    state='PROGRESS',
                    meta={
                        'current': progress,
                        'total': 100,
                        'status': f'{server_name} {action} 처리 중... ({i+1}/{total_servers})'
                    }
                )
                
                proxmox_service = ProxmoxService()
                
                if action == 'start':
                    if proxmox_service.start_server(server_name):
                        success_servers.append(server_name)
                    else:
                        failed_servers.append(server_name)
                elif action == 'stop':
                    if proxmox_service.stop_server(server_name):
                        success_servers.append(server_name)
                    else:
                        failed_servers.append(server_name)
                elif action == 'reboot':
                    if proxmox_service.reboot_server(server_name):
                        success_servers.append(server_name)
                    else:
                        failed_servers.append(server_name)
                elif action == 'delete':
                    if proxmox_service.delete_server(server_name):
                        # DB에서도 삭제
                        server = Server.query.filter_by(name=server_name).first()
                        if server:
                            db.session.delete(server)
                            db.session.commit()
                        success_servers.append(server_name)
                    else:
                        failed_servers.append(server_name)
                
            except Exception as e:
                logger.error(f"서버 {server_name} {action} 실패: {str(e)}")
                failed_servers.append(server_name)
        
        # 결과에 따른 알림 생성
        if success_servers and not failed_servers:
            # 모든 서버 성공
            notification = Notification(
                type='bulk_server_action',
                title='대량 작업 완료',
                message=f'모든 서버 {action} 완료: {", ".join(success_servers)}',
                severity='success',
                details=f'작업 유형: {action}\n성공한 서버: {", ".join(success_servers)}'
            )
        elif success_servers and failed_servers:
            # 부분 성공
            notification = Notification(
                type='bulk_server_action',
                title='대량 작업 부분 완료',
                message=f'일부 서버 {action} 완료. 성공: {len(success_servers)}개, 실패: {len(failed_servers)}개',
                severity='warning',
                details=f'작업 유형: {action}\n성공한 서버: {", ".join(success_servers)}\n실패한 서버: {", ".join(failed_servers)}'
            )
        else:
            # 모든 서버 실패
            notification = Notification(
                type='bulk_server_action',
                title='대량 작업 실패',
                message=f'모든 서버 {action} 실패: {len(failed_servers)}개',
                severity='error',
                details=f'작업 유형: {action}\n실패한 서버: {", ".join(failed_servers)}'
            )
        
        db.session.add(notification)
        db.session.commit()
        
        logger.info(f"✅ 비동기 대량 서버 작업 완료: {action} - 성공: {len(success_servers)}개, 실패: {len(failed_servers)}개")
        
        return {
            'success': True,
            'message': f'대량 서버 {action} 작업 완료',
            'success_servers': success_servers,
            'failed_servers': failed_servers,
            'task_id': task_id
        }
        
    except Exception as e:
        logger.error(f"❌ 비동기 대량 서버 작업 실패: {str(e)}")
        
        # 작업 실패 상태 업데이트
        self.update_state(
            state='FAILURE',
            meta={'error': str(e)}
        )
        
        raise
