
# Ansible 
- role (역할)
- 트리 구조 설명
- 변수
- 사용 방법

## role (역할)
Ansible role은 Playbook을 구성하는 방식을 더 구조적이고 재사용 가능하게 만드는 기능입니다. 역할(Role)은 특정 작업을 수행하는 데 필요한 tasks, handlers, variables, templates, files 등을 하나의 디렉터리 구조로 정리하여 관리합니다. 이를 통해 코드의 가독성과 유지 보수성을 높이고, 여러 프로젝트에서 동일한 구성을 쉽게 재사용할 수 있습니다. 

역할로는 서버에 설치된 어플리케이션 모듈을 기준으로 다음처럼 설정했습니다.
- nginx             # Front WEB
- java              # Front API 
- elasticsearch     # 검색엔진 
- Kafka/Logstash    # 통계 작업을 위한 추출 ("impression", "click", "video_impression" etc...)
- kibana            # 검색엔진 UI, 대시보드 등 제공
- redis             # 캐시DB
- python            # FAST API 


## 트리 구조 설명
- **tasks/**:
    - 이 디렉토리는 역할의 주요 작업을 정의하는 곳입니다.
    - `main.yml` 파일은 이 역할에서 실행할 주요 작업 목록을 포함합니다.
    - 작업들은 여러 개의 YAML 파일로 나누어 관리할 수도 있습니다.
- **handlers/**:
    - 핸들러는 특정 작업이 완료된 후 호출되는 작업입니다.
    - `main.yml` 파일에는 변경 사항이 있을 때만 실행해야 하는 작업이 정의됩니다. 예를 들어, 서비스를 재시작하는 작업이 여기에 포함될 수 있습니다.
- **defaults/**:
    - 기본 변수의 값을 정의하는 곳입니다.
    - `main.yml` 파일에서 역할을 사용할 때 기본값을 설정할 수 있습니다. 사용자가 변수를 재정의할 수 있도록 합니다.
- **vars/**:
    - 이 디렉토리에는 역할에서 사용할 수 있는 변수들이 정의됩니다.
    - 기본 변수와는 달리, 이 변수들은 사용자에 의해 오버라이드되지 않습니다. `main.yml` 파일에 정의됩니다.
- **files/**:
    - 이 디렉토리는 역할에서 사용할 파일들을 저장하는 곳입니다.
    - Ansible 플레이북에서 파일을 전송하거나 복사할 때 이 디렉토리에 있는 파일을 참조할 수 있습니다.
- **templates/**:
    - Jinja2 템플릿 파일을 저장하는 곳입니다.
    - 템플릿 파일은 동적으로 내용을 생성할 수 있으며, `copy` 모듈이나 `template` 모듈을 통해 대상 호스트로 복사할 수 있습니다.
- **meta/**:
    - 역할에 대한 메타데이터를 정의하는 곳입니다.
    - `main.yml` 파일에는 역할의 의존성, 저자, 라이센스 정보 등이 포함됩니다.
- **README.md**:
    - 역할에 대한 설명과 사용법, 예제 등을 포함하는 문서 파일입니다.
    - 다른 사용자나 개발자가 이 역할을 사용할 때 유용한 정보를 제공합니다.

## 변수
- 경로: roles/서비스/vars   

사용 방법 예시
```
### roles/서비스/vars/main.yml
---
# vars file for nginx
nginx_conf_dir: "/etc/nginx/conf.d"
```

```
### roles/서비스/main.yaml
- name: Check if nginx configuration files are present
  stat:
    path: "{{ nginx_conf_dir }}/default.conf"
```


## 사용방법 
1. 실행 방법
`ansible-playbook mustad_role.yaml`

2. 대상 호스트 및 역할 설정
`vi mustad_role.yaml`

```
- name: MustAD service 
  hosts: Front   # hosts 값을 inventory hosts 에 설정한 값으로 수정
  become: yes    # root 로 수행할 건지 묻는 의미 (sudo 의 의미)

  roles:
    - nginx      # nginx 는 roles 아래 있는 역할 이름 
```

3. 변경하고자 하는 것이 있을 경우, 
`roles/{{서비스}}/vars` 나, `roles/{{서비스}}/defaults` 에 변수가 정의되어 있으며, 주로 경로나 파일 이름이 지정되어 있습니다.
어플리케이션 설치 버전이 올라갔다던가, 경로를 변경하고 싶다던가 할 때, 해당 내용을 변경하면 됩니다.
 또 설치 과정을 수정하고 싶다던가, 템플릿에 변경이 필요하다면 
실제 동작하는 프로세스에 대해선 `tasks/main.yaml` 에 있고, 주로 shell 언어로 이뤄져 있으므로 shell 을 활용해 수정하면 됩니다.. 
템플릿에 대해선 `templates/main.ymal` 에 코드는 주로 jinja2 언어로 이뤄져 있습니다. 템플릿 변수를 좀 더 지정하고 싶거나, 최적화 하고 싶다면 여기서 작업하시면 됩니다.

#### 번외) 테스트를 하거나 원래 상태로 되돌리고 싶을 때, 미리 만들어 둔 {{서비스}}_del.yaml 가 있으니 아래처럼 활용하시면 됩니다.
`ansible-playbook nginx_del.yaml`