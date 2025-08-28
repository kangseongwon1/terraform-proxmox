"""
알림 관련 라우트
"""
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from app.models import Notification
from app.routes.auth import permission_required
from app import db
import logging

logger = logging.getLogger(__name__)

bp = Blueprint('notification', __name__, url_prefix='/api')

@bp.route('/notifications', methods=['GET'])
@login_required
def get_notifications():
    """알림 목록 조회"""
    try:
        # user_id가 None인 알림도 포함 (시스템 알림)
        notifications = Notification.query.filter(
            (Notification.user_id == current_user.id) | (Notification.user_id.is_(None))
        ).order_by(Notification.created_at.desc()).all()
        
        notification_data = []
        for notification in notifications:
            notification_data.append({
                'id': notification.id,
                'title': notification.title,
                'message': notification.message,
                'details': notification.details,
                'severity': notification.severity,
                'is_read': notification.is_read,
                'created_at': notification.created_at.isoformat() if notification.created_at else None
            })
        
        return jsonify({'notifications': notification_data})
    except Exception as e:
        print(f"💥 알림 목록 조회 실패: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/notifications/<int:notification_id>/read', methods=['POST'])
@login_required
def mark_notification_read(notification_id):
    """알림 읽음 표시"""
    try:
        notification = Notification.query.filter_by(id=notification_id, user_id=current_user.id).first()
        
        if not notification:
            return jsonify({'error': '알림을 찾을 수 없습니다.'}), 404
        
        notification.is_read = True
        db.session.commit()
        
        return jsonify({'success': True, 'message': '알림이 읽음으로 표시되었습니다.'})
    except Exception as e:
        print(f"💥 알림 읽음 표시 실패: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/notifications/unread-count', methods=['GET'])
@login_required
def get_unread_notification_count():
    """읽지 않은 알림 개수"""
    try:
        count = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
        return jsonify({
            'success': True,
            'count': count
        })
    except Exception as e:
        print(f"💥 읽지 않은 알림 개수 조회 실패: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/notifications/<int:notification_id>', methods=['DELETE'])
@login_required
def delete_notification(notification_id):
    """개별 알림 삭제"""
    try:
        # user_id가 None인 시스템 알림도 삭제 가능하도록 수정
        notification = Notification.query.filter(
            (Notification.id == notification_id) & 
            ((Notification.user_id == current_user.id) | (Notification.user_id.is_(None)))
        ).first()
        
        if not notification:
            return jsonify({'error': '알림을 찾을 수 없습니다.'}), 404
        
        db.session.delete(notification)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': '알림이 삭제되었습니다.'
        })
        
    except Exception as e:
        print(f"💥 개별 알림 삭제 실패: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/notifications/clear-all', methods=['POST'])
@login_required
def clear_all_notifications():
    """모든 알림 삭제"""
    try:
        # user_id가 None인 시스템 알림도 삭제 가능하도록 수정
        Notification.query.filter(
            (Notification.user_id == current_user.id) | (Notification.user_id.is_(None))
        ).delete()
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': '모든 알림이 삭제되었습니다.'
        })
        
    except Exception as e:
        print(f"💥 모든 알림 삭제 실패: {str(e)}")
        return jsonify({'error': str(e)}), 500 