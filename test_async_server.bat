@echo off
echo 🧪 비동기 서버 생성 테스트 시작
echo ================================================

REM Python 스크립트 실행
python tests/test_async_server_creation.py %*

echo ================================================
echo 테스트 완료
pause
