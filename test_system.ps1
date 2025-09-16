# 🚀 Proxmox Manager 시스템 테스트 스크립트 (PowerShell)
# 이 스크립트는 프로젝트의 모든 기능을 종합적으로 테스트합니다.

param(
    [switch]$SkipFlask,
    [switch]$ReportOnly
)

# 오류 발생 시 스크립트 종료
$ErrorActionPreference = "Stop"

# 색상 함수들
function Write-Info {
    param([string]$Message)
    Write-Host "[INFO] $Message" -ForegroundColor Blue
}

function Write-Success {
    param([string]$Message)
    Write-Host "[SUCCESS] $Message" -ForegroundColor Green
}

function Write-Warning {
    param([string]$Message)
    Write-Host "[WARNING] $Message" -ForegroundColor Yellow
}

function Write-Error {
    param([string]$Message)
    Write-Host "[ERROR] $Message" -ForegroundColor Red
}

# 헤더 출력
function Show-Header {
    Write-Host "==================================================================" -ForegroundColor Cyan
    Write-Host "🚀 Proxmox Manager 시스템 테스트" -ForegroundColor Cyan
    Write-Host "==================================================================" -ForegroundColor Cyan
    Write-Host "시작 시간: $(Get-Date)" -ForegroundColor Cyan
    Write-Host "작업 디렉토리: $(Get-Location)" -ForegroundColor Cyan
    Write-Host "==================================================================" -ForegroundColor Cyan
}

# 환경 확인
function Test-Environment {
    Write-Info "환경 확인 중..."
    
    # Python 확인
    try {
        $pythonVersion = python --version 2>&1
        Write-Success "Python 확인 완료: $pythonVersion"
    }
    catch {
        Write-Error "Python이 설치되지 않았거나 PATH에 없습니다."
        exit 1
    }
    
    # 가상환경 확인
    if (-not (Test-Path "venv")) {
        Write-Warning "가상환경이 없습니다. 생성 중..."
        python -m venv venv
    }
    
    # 가상환경 활성화
    if ($IsWindows -or $env:OS -eq "Windows_NT") {
        & "venv\Scripts\Activate.ps1"
    } else {
        & "venv/bin/Activate.ps1"
    }
    
    # 필수 패키지 확인
    Write-Info "필수 패키지 확인 중..."
    pip install -q -r requirements.txt
    
    Write-Success "환경 확인 완료"
}

# Flask 애플리케이션 상태 확인
function Test-FlaskApp {
    if ($SkipFlask) {
        Write-Info "Flask 애플리케이션 확인을 건너뜁니다."
        return $true
    }
    
    Write-Info "Flask 애플리케이션 상태 확인 중..."
    
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:5000" -TimeoutSec 5 -UseBasicParsing
        Write-Success "Flask 애플리케이션이 실행 중입니다."
        return $true
    }
    catch {
        Write-Warning "Flask 애플리케이션이 실행되지 않았습니다."
        Write-Info "Flask 애플리케이션을 시작합니다..."
        
        # 백그라운드에서 Flask 앱 시작
        $job = Start-Job -ScriptBlock {
            Set-Location $using:PWD
            python run.py
        }
        
        # Flask 앱이 시작될 때까지 대기
        for ($i = 1; $i -le 30; $i++) {
            Start-Sleep -Seconds 2
            try {
                $response = Invoke-WebRequest -Uri "http://localhost:5000" -TimeoutSec 5 -UseBasicParsing
                Write-Success "Flask 애플리케이션이 시작되었습니다. (Job ID: $($job.Id))"
                $global:FlaskJob = $job
                return $true
            }
            catch {
                # 계속 대기
            }
        }
        
        Write-Error "Flask 애플리케이션 시작 실패"
        Stop-Job $job
        Remove-Job $job
        return $false
    }
}

# Flask 애플리케이션 정리
function Stop-FlaskApp {
    if ($global:FlaskJob) {
        Write-Info "Flask 애플리케이션 종료 중... (Job ID: $($global:FlaskJob.Id))"
        Stop-Job $global:FlaskJob
        Remove-Job $global:FlaskJob
        $global:FlaskJob = $null
    }
}

# 테스트 실행
function Invoke-Tests {
    Write-Info "테스트 실행 중..."
    
    # 로그 디렉토리 생성
    if (-not (Test-Path "logs")) {
        New-Item -ItemType Directory -Path "logs" | Out-Null
    }
    
    # 테스트 실행
    try {
        python tests/run_tests.py --all
        if ($LASTEXITCODE -eq 0) {
            Write-Success "모든 테스트가 성공적으로 완료되었습니다."
            return $true
        } else {
            Write-Error "일부 테스트가 실패했습니다."
            return $false
        }
    }
    catch {
        Write-Error "테스트 실행 중 오류 발생: $_"
        return $false
    }
}

# 보고서 생성
function New-TestReport {
    Write-Info "테스트 보고서 생성 중..."
    
    if (Test-Path "logs/overall_test_report.json") {
        Write-Success "테스트 보고서가 생성되었습니다: logs/overall_test_report.json"
        
        # 간단한 요약 출력
        Write-Host ""
        Write-Host "==================================================================" -ForegroundColor Cyan
        Write-Host "📊 테스트 결과 요약" -ForegroundColor Cyan
        Write-Host "==================================================================" -ForegroundColor Cyan
        
        try {
            $report = Get-Content "logs/overall_test_report.json" | ConvertFrom-Json
            $summary = $report.summary
            
            Write-Host "전체 테스트: $($summary.total_tests)" -ForegroundColor White
            Write-Host "통과: $($summary.passed_tests)" -ForegroundColor Green
            Write-Host "실패: $($summary.failed_tests)" -ForegroundColor Red
            Write-Host "성공률: $([math]::Round($summary.success_rate, 1))%" -ForegroundColor Yellow
            
            if ($summary.overall_success) {
                Write-Host "🎉 전체 테스트 성공! (75% 이상 통과)" -ForegroundColor Green
            } else {
                Write-Host "⚠️ 전체 테스트 실패! (75% 미만 통과)" -ForegroundColor Red
            }
        }
        catch {
            Write-Warning "테스트 보고서를 파싱할 수 없습니다."
            Write-Host "logs/overall_test_report.json 파일을 확인하세요." -ForegroundColor Yellow
        }
        
        Write-Host "==================================================================" -ForegroundColor Cyan
    } else {
        Write-Warning "테스트 보고서를 찾을 수 없습니다."
    }
}

# 정리 작업
function Invoke-Cleanup {
    Write-Info "정리 작업 중..."
    Stop-FlaskApp
    Write-Success "정리 작업 완료"
}

# 메인 함수
function Main {
    Show-Header
    
    try {
        # 환경 확인
        Test-Environment
        
        # 보고서만 생성하는 경우
        if ($ReportOnly) {
            New-TestReport
            return
        }
        
        # Flask 애플리케이션 확인/시작
        if (-not (Test-FlaskApp)) {
            Write-Error "Flask 애플리케이션을 시작할 수 없습니다."
            exit 1
        }
        
        # 테스트 실행
        if (-not (Invoke-Tests)) {
            Write-Error "테스트 실행 실패"
            exit 1
        }
        
        # 보고서 생성
        New-TestReport
        
        Write-Success "시스템 테스트가 완료되었습니다."
        Write-Host "종료 시간: $(Get-Date)" -ForegroundColor Cyan
    }
    catch {
        Write-Error "테스트 실행 중 오류 발생: $_"
        exit 1
    }
    finally {
        Invoke-Cleanup
    }
}

# 스크립트 실행
Main
