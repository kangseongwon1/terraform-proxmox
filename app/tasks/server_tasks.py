"""
서버 관련 Celery 작업
"""
from celery import current_task
from app.celery_app import celery_app
from app.services import ProxmoxService, TerraformService, AnsibleService
from app.models import Server, Notification
from app import db
import logging

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
        
        # Terraform 서비스 초기화
        terraform_service = TerraformService()
        
        # 1단계: Terraform 파일 생성
        self.update_state(
            state='PROGRESS',
            meta={'current': 20, 'total': 100, 'status': 'Terraform 파일 생성 중...'}
        )
        
        terraform_result = terraform_service.create_server(server_config)
        if not terraform_result['success']:
            raise Exception(f"Terraform 파일 생성 실패: {terraform_result['message']}")
        
        # 2단계: Terraform 실행
        self.update_state(
            state='PROGRESS',
            meta={'current': 40, 'total': 100, 'status': 'Terraform 실행 중...'}
        )
        
        apply_result = terraform_service.apply_server(server_config['name'])
        if not apply_result['success']:
            raise Exception(f"Terraform 실행 실패: {apply_result['message']}")
        
        # 3단계: 서버 정보 DB 저장
        self.update_state(
            state='PROGRESS',
            meta={'current': 60, 'total': 100, 'status': '서버 정보 저장 중...'}
        )
        
        server = Server(
            name=server_config['name'],
            cpu=server_config['cpu'],
            memory=server_config['memory'],
            disk=server_config['disk'],
            os_type=server_config.get('os_type', 'ubuntu'),
            role=server_config.get('role', ''),
            firewall_group=server_config.get('firewall_group', ''),
            status='creating'
        )
        
        db.session.add(server)
        db.session.commit()
        
        # 4단계: 서버 시작 대기
        self.update_state(
            state='PROGRESS',
            meta={'current': 80, 'total': 100, 'status': '서버 시작 대기 중...'}
        )
        
        proxmox_service = ProxmoxService()
        if proxmox_service.start_server(server_config['name']):
            server.status = 'running'
            db.session.commit()
            
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
            
            return {
                'success': True,
                'message': f'서버 {server_config["name"]} 생성 완료',
                'server_name': server_config['name'],
                'task_id': task_id
            }
        else:
            raise Exception("서버 시작 실패")
            
    except Exception as e:
        logger.error(f"❌ 비동기 서버 생성 실패: {str(e)}")
        
        # 실패 알림 생성
        notification = Notification(
            type='server_creation',
            title='서버 생성 실패',
            message=f'서버 {server_config["name"]} 생성에 실패했습니다.',
            severity='error',
            details=f'오류: {str(e)}'
        )
        db.session.add(notification)
        db.session.commit()
        
        # 작업 실패 상태 업데이트 (간단한 형태로)
        error_msg = str(e)
        logger.error(f"❌ 서버 생성 실패: {error_msg}")
        
        # 백엔드가 없으므로 상태 업데이트 생략
        
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
