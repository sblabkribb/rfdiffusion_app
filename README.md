# RFdiffusion Serverless on RunPod

이 저장소는 RFdiffusion 추론을 컨테이너로 패키징해 RunPod Serverless에서 실행하는 예제/템플릿입니다. 베이스 이미지에 RFdiffusion과 LigandMPNN을 설치하고, 앱 이미지는 RunPod Serverless 핸들러(`handler.py`)를 포함합니다. 로컬에서 테스트·호출할 수 있는 노트북(`rfdiffusion_app.ipynb`)도 제공합니다.

## 구성 요소
- `dockerfile.base`: PyTorch 1.13.1 + CUDA 11.6 기반. RFdiffusion, LigandMPNN 설치 및 모델 다운로드 스크립트 준비. 추가 파이썬 의존성(`omegaconf`, `hydra-core`, `opt_einsum`) 포함.
- `dockerfile`: 베이스 이미지를 기반으로 `handler.py` 복사, `runpod` SDK 설치, 엔트리포인트 설정.
- `handler.py`: RunPod Serverless 워커 진입점. 입력 PDB(base64)와 Hydra 인자 리스트를 받아 RFdiffusion 추론 실행 후 결과 ZIP(base64) 반환. 모델 캐시 자동 탐색/다운로드 지원.
- `build_and_push.sh`: 베이스/앱 이미지를 빌드하고 Docker Hub로 푸시하는 스크립트.
- `rfdiffusion_app.ipynb`: 로컬에서 RunPod Serverless 엔드포인트(`/runsync`)를 호출하는 예제 노트북.

## 사전 준비
- Docker 및 Docker Hub 로그인/푸시 권한
- RunPod 계정 및 Serverless Endpoint 생성 권한
- 권장 GPU: A40(48GB) / A10(24GB). T4(16GB)는 작업 축소 권장. L4/4090(ADA)은 CUDA 12 계열이므로 본 베이스(CUDA 11.6)와 호환에 유의.
- 네트워크 볼륨: 15~50GB 권장(최소 10GB). 최초 1회 모델 다운로드 후 캐시.

## 빌드 · 푸시
스크립트 상단의 `DOCKER_USERNAME`을 본인의 Docker Hub 사용자명으로 설정하세요.

- 베이스/앱 모두 빌드·푸시(동일 태그 사용, 권장)
  - `bash build_and_push.sh --app-tag 20251031-120000`
- 베이스는 건너뛰고 앱만 푸시(레지스트리에 해당 베이스 태그가 이미 존재해야 함)
  - `bash build_and_push.sh --skip-base --app-tag 20251031-120000`
  - 특정 베이스 태그 사용: `bash build_and_push.sh --skip-base --base-tag <base-tag> --app-tag <app-tag>`
- 캐시 미사용
  - `bash build_and_push.sh --no-cache --app-tag <tag>`

결과 이미지
- 베이스: `docker.io/<DOCKER_USERNAME>/rfdiffusion-base:<tag>`
- 앱: `docker.io/<DOCKER_USERNAME>/rfdiffusion-app:<tag>`

## RunPod Serverless 설정
RunPod 콘솔 → Serverless → New Endpoint
- Image: `docker.io/<DOCKER_USERNAME>/rfdiffusion-app:<tag>`
- Command: 비워두면 `dockerfile`의 `CMD` 사용(`python -u handler.py`)
- GPU: A40 또는 A10 권장, Concurrency 1부터 시작
- Timeout: 1800~3600초 권장(작업 규모에 맞게)
- Network Volume: 15~50GB 권장, 마운트 경로 예: `/runpod-volume`
- Env Vars(권장): `RF_MODEL_DIR=/runpod-volume/rfdiffusion_models`
  - 미지정 시 `handler.py`가 `RUNPOD_*` 마운트 경로 및 `/workspace/network_storage` 등을 순회 탐색 후 필요 시 자동 다운로드합니다.

## 노트북 사용법(rfdiffusion_app.ipynb)
목적: 로컬에서 PDB 파일을 base64로 인코딩해 RunPod Serverless 엔드포인트로 전송하고, 결과 ZIP(base64)을 수신해 파일로 저장합니다.

### .env 설정(권장)
프로젝트 루트에 `.env` 파일을 만들고 다음과 같이 입력하세요.

```
RUNPOD_API_KEY=rpa_...(새로 발급한 키)
ENDPOINT_ID=n4q9uzty70zzsu
```

`.env`는 `.gitignore`에 포함되어 Git에 커밋되지 않습니다. 노트북은 환경변수를 우선 사용하도록 구성하세요. 필요 시 아래 스니펫으로 `.env`를 읽어올 수 있습니다(선택).

```
import os, pathlib
env_path = pathlib.Path('.env')
if env_path.exists():
    for line in env_path.read_text(encoding='utf-8').splitlines():
        line=line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        k,v = line.split('=',1)
        os.environ.setdefault(k.strip(), v.strip())
```

### Windows에서 환경변수로 설정(대안)
- 현재 세션만: `$env:RUNPOD_API_KEY='rpa_...'`, `$env:ENDPOINT_ID='n4q9uzty70zzsu'`
- 영구 설정(새 터미널 필요): `setx RUNPOD_API_KEY "rpa_..."`, `setx ENDPOINT_ID "n4q9uzty70zzsu"`

### 노트북 셀 구성 및 실행 순서
- 의존성 확인 셀: `requests` 등 네트워크 관련 패키지 버전 확인/업데이트
- 설정 셀: 환경변수에서 값을 읽도록 설정
  - `RUNPOD_API_KEY = os.getenv("RUNPOD_API_KEY", "")`
  - `ENDPOINT_ID = os.getenv("ENDPOINT_ID", "n4q9uzty70zzsu")`
  - `API_URL = f"https://api.runpod.ai/v2/{ENDPOINT_ID}/runsync"`
  - `PDB_FILE_PATH = "./inputs/insulin_target.pdb"` (필요 시 변경)
  - `commands = [...]` RFdiffusion Hydra 인자 리스트(예시 포함)
- 1단계: PDB 파일을 읽어 base64 문자열(`pdb_b64`)로 변환
- 2단계: `payload` 구성 후 `requests.post(API_URL, json=payload, headers=...)`로 `/runsync` 호출
- 3단계: 응답 처리. 성공 시 `result_zip_b64`를 디코딩해 `rfdiffusion_result.zip`으로 저장, `stdout/stderr` 일부 출력

### commands 예시
- `contigmap.contigs=[A1-150/0 70-100]`
- `ppi.hotspot_res=[A59,A83,A91]`
- `inference.num_designs=3`
- `denoiser.noise_scale_ca=0`
- `denoiser.noise_scale_frame=0`

## 요청 페이로드 예시
JSON 예시

```json
{
  "input": {
    "pdb_file": "<BASE64_PDB>",
    "commands": [
      "inference.num_designs=1",
      "inference.seed=42"
    ],
    "model_directory_path": "/runpod-volume/rfdiffusion_models"
  }
}
```

cURL 예시(`/runsync`)

```bash
curl -X POST "https://api.runpod.ai/v2/<ENDPOINT_ID>/runsync" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $RUNPOD_API_KEY" \
  -d @payload.json
```

Python 예시(`requests`)

```python
import os, json, base64, requests
API_URL = f"https://api.runpod.ai/v2/{os.environ['ENDPOINT_ID']}/runsync"
headers = {"Authorization": f"Bearer {os.environ['RUNPOD_API_KEY']}", "Content-Type": "application/json"}
with open("input.pdb", "rb") as f:
    pdb_b64 = base64.b64encode(f.read()).decode()
payload = {"input": {"pdb_file": pdb_b64, "commands": ["inference.num_designs=1"], "model_directory_path": "/runpod-volume/rfdiffusion_models"}}
r = requests.post(API_URL, json=payload, headers=headers, timeout=1800)
r.raise_for_status()
print(r.json())
```

## 작동 방식 요약
- 컨테이너 시작 시 `handler.py`가 RunPod 워커로 기동하고 요청 대기
- 요청 수신 시
  - 입력 PDB를 임시 디렉터리에 저장
  - 모델 디렉터리 결정: `model_directory_path` → `RF_MODEL_DIR` → `RUNPOD_*` 마운트 경로 → 기본(`/workspace/rfdiffusion_models` 유사)
  - 모델 미존재 시 `/app/RFdiffusion/scripts/download_models.sh`를 통해 다운로드 후 대상 경로로 복사
  - `scripts/run_inference.py` 실행, 출력물을 ZIP으로 묶어 base64로 반환

## 문제 해결(Troubleshooting)
- 401 Unauthorized
  - `Authorization: Bearer <RUNPOD_API_KEY>` 확인. 발급 상태/복사 오류/개행 섞임 여부 점검
- 모델 다운로드 실패
  - 사내 CA/인증서 이슈로 `wget`에 `--no-check-certificate`가 필요할 수 있음. 베이스에 옵션 반영됨. 네트워크 볼륨 권장
- `download_models.py` 부재
  - 리포 최신화로 `download_models.sh` 사용. `handler.py`는 `.sh`를 우선 사용하도록 구현됨
- 베이스/앱 이미지 태그 불일치
  - `--skip-base` 사용 시 `--base-tag`가 레지스트리에 실제 존재하는지 확인
- 메모리/VRAM 부족
  - `inference.num_designs=1`로 축소, 컨텍스트 축소, 대용량 GPU(A40/A100) 권장
- SSL 검증 오류
  - 요청 측 환경이라면 `requests.post(..., verify=False)` 임시 사용 또는 조직 루트 CA를 신뢰 저장소에 추가
- 서버 측 모듈 누락
  - `ModuleNotFoundError: omegaconf` 또는 `hydra-core` 또는 `opt_einsum` 발생 시 베이스 이미지에 해당 패키지가 설치돼야 합니다. `dockerfile.base` 수정 후 베이스 포함 전체 빌드·푸시하세요

## 보안/주의
- RunPod API 키와 PDB 같은 민감 데이터는 저장소에 커밋하지 마세요
- `.gitignore`에 `github_token.txt`, `.env`가 포함되어 있습니다
- 과거에 키가 노트북에 노출되었다면 RunPod 콘솔에서 즉시 키를 회전(재발급)하세요

## 참고
- RFdiffusion: https://github.com/RosettaCommons/RFdiffusion
- LigandMPNN: https://github.com/dauparas/LigandMPNN
- RunPod Serverless Docs: https://www.runpod.io/serverless

