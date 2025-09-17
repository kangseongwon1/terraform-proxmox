# Terraform Targeted Apply 및 서버 상태 보호

## 문제 상황

기존에 다중 서버 생성 시 `terraform apply`가 전체 인프라에 대해 실행되어, 기존 서버들의 상태(running, stop, shutdown, reboot)에 영향을 주는 문제가 있었습니다.

## 원인

Terraform의 선언적 특성상, `terraform apply`는 `tfvars.json`에 정의된 모든 서버의 상태를 실제 인프라와 일치시키려고 시도합니다. 만약 기존 서버가 수동으로 중지되었거나 상태가 변경되었다면, Terraform이 이를 원래 상태로 되돌리려고 할 수 있습니다.

## 해결 방법

### 1. Targeted Apply 구현

새로 생성되는 서버들만 대상으로 `terraform apply`를 실행하도록 개선했습니다.

#### TerraformService 수정
- `apply()` 메서드에 `targets` 매개변수 추가
- 특정 리소스만 대상으로 적용할 수 있도록 지원

```python
def apply(self, targets: List[str] = None) -> Tuple[bool, str]:
    """Terraform 적용
    
    Args:
        targets: 특정 리소스만 대상으로 적용할 때 사용 (예: ["module.server[\"server1\"]"])
    """
```

#### create_servers_bulk API 수정
- 새로 생성될 서버들만 대상으로 targeted apply 실행
- 기존 서버들의 상태에 영향을 주지 않음

```python
# 새로 생성될 서버들만 대상으로 targeted apply 실행
new_server_targets = []
for server_data in servers_data:
    server_name = server_data.get('name')
    if server_name:
        # Terraform 모듈 리소스 타겟 형식: module.server["서버이름"]
        target = f'module.server["{server_name}"]'
        new_server_targets.append(target)

apply_success, apply_message = terraform_service.apply(targets=new_server_targets)
```

### 2. VM 상태 보호 설정

Terraform 모듈에서 VM의 전원 상태 변경을 무시하도록 설정을 추가했습니다.

#### lifecycle 설정 개선
```hcl
lifecycle {
  ignore_changes = [
    disk,
    # VM의 전원 상태 변경 무시 (수동으로 중지/시작된 경우)
    started
  ]
}
```

#### started 속성 추가
```hcl
# VM 생성 후 자동 시작 (기본값: true)
started = true
```

## 효과

1. **기존 서버 상태 보호**: 다중 서버 생성 시 기존 서버들의 상태가 변경되지 않습니다.
2. **선택적 적용**: 새로 생성되는 서버들만 대상으로 Terraform이 적용됩니다.
3. **수동 상태 변경 허용**: 사용자가 수동으로 서버를 중지/시작해도 Terraform이 이를 되돌리지 않습니다.

## 사용 예시

```bash
# 기존 방식 (전체 인프라 적용)
terraform apply -auto-approve

# 새로운 방식 (특정 서버만 적용)
terraform apply -auto-approve -target=module.server["new-server-1"] -target=module.server["new-server-2"]
```

## 주의사항

1. **Targeted Apply 제한사항**: Terraform의 targeted apply는 의존성 문제를 일으킬 수 있으므로, 새로 생성되는 서버들 간의 의존성이 없는 경우에만 사용합니다.
2. **상태 동기화**: 주기적으로 전체 `terraform apply`를 실행하여 상태를 동기화하는 것을 권장합니다.
3. **모니터링**: 서버 생성 후 Proxmox에서 실제 VM 생성 여부를 확인하는 로직이 포함되어 있습니다.

## 관련 파일

- `app/services/terraform_service.py`: TerraformService 클래스 수정
- `app/routes/servers.py`: create_servers_bulk API 수정
- `terraform/modules/server/main.tf`: VM 리소스 설정 개선 