#!/bin/bash
# RFdiffusion base + app 이미지를 빌드/푸시합니다.
# 기본 동작: base와 app을 같은 태그로 빌드/푸시.
# 옵션:
#   --skip-base           base 빌드/푸시를 건너뜁니다(이때 기본 base tag는 'latest').
#   --base-tag <tag>      app이 참조할 base 이미지 태그 지정(미지정 시 기본 동작 참조).
#   --app-tag  <tag>      app 이미지 태그 지정(미지정 시 현재 시간).
#   --no-cache            빌드 캐시 미사용.

set -e

NO_CACHE_ARGS=()
POSITIONAL_TAG=""
SKIP_BASE=0
APP_TAG=""
BASE_TAG=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --no-cache)
            NO_CACHE_ARGS+=(--no-cache)
            shift ;;
        --skip-base)
            SKIP_BASE=1
            shift ;;
        --base-tag)
            [ -n "${2:-}" ] || { echo "❌ --base-tag 인자 필요" >&2; exit 1; }
            BASE_TAG="$2"; shift 2 ;;
        --app-tag)
            [ -n "${2:-}" ] || { echo "❌ --app-tag 인자 필요" >&2; exit 1; }
            APP_TAG="$2"; shift 2 ;;
        *)
            if [ -z "$POSITIONAL_TAG" ]; then
                POSITIONAL_TAG="$1"
            else
                echo "❌ 알 수 없는 추가 인자: $1" >&2
                exit 1
            fi
            shift ;;
    esac
done

export CURL_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt

# --- 변수 설정 ---
DOCKER_USERNAME="mimikyou0607"

BASE_IMAGE_NAME="rfdiffusion-base"
APP_IMAGE_NAME="rfdiffusion-app"

# 태그 결정: 우선순위 (명시 옵션) > (positional) > (기본)
if [ -z "$APP_TAG" ]; then
    if [ -n "$POSITIONAL_TAG" ]; then
        APP_TAG="$POSITIONAL_TAG"
    else
        APP_TAG=$(date +%Y%m%d-%H%M%S)
        echo "⚠️ app 태그가 제공되지 않아 현재 시간($APP_TAG)을 사용합니다."
    fi
fi

if [ -z "$BASE_TAG" ]; then
    if [ "$SKIP_BASE" -eq 1 ]; then
        BASE_TAG="latest"
        echo "ℹ️  --skip-base 사용: base 태그를 'latest'로 사용합니다. (변경: --base-tag <tag>)"
    else
        # base도 빌드하므로 app과 동일 태그 사용
        BASE_TAG="$APP_TAG"
    fi
fi

FULL_BASE_IMAGE_NAME="${DOCKER_USERNAME}/${BASE_IMAGE_NAME}:${BASE_TAG}"
LATEST_BASE_IMAGE_NAME="${DOCKER_USERNAME}/${BASE_IMAGE_NAME}:latest"
FULL_APP_IMAGE_NAME="${DOCKER_USERNAME}/${APP_IMAGE_NAME}:${APP_TAG}"
LATEST_APP_IMAGE_NAME="${DOCKER_USERNAME}/${APP_IMAGE_NAME}:latest"

GITHUB_TOKEN_FILE="github_token.txt"

# --- 사전 확인 ---
if [ ! -f "$GITHUB_TOKEN_FILE" ]; then
    echo "❌ 오류: GitHub 토큰 파일('$GITHUB_TOKEN_FILE')을 찾을 수 없습니다."
    echo "스크립트를 실행하기 전에 토큰 파일을 생성해주세요."
    exit 1
fi

echo "🚀 RFdiffusion 이미지 빌드 및 푸시 시작"
echo "   base: ${FULL_BASE_IMAGE_NAME}  (skip=${SKIP_BASE})"
echo "   app : ${FULL_APP_IMAGE_NAME}"

# --- 1. 베이스 이미지 빌드 및 푸시 ---
if [ "$SKIP_BASE" -eq 0 ]; then
    echo "--- Step 1/2: 베이스 이미지(${FULL_BASE_IMAGE_NAME}) 빌드 및 푸시 ---"
    DOCKER_BUILDKIT=1 docker buildx build \
        -f dockerfile.base \
        "${NO_CACHE_ARGS[@]}" \
        -t "${FULL_BASE_IMAGE_NAME}" \
        -t "${LATEST_BASE_IMAGE_NAME}" \
        --push .
else
    echo "↪️  base 빌드 생략 (--skip-base). 레지스트리에 ${FULL_BASE_IMAGE_NAME} 가 존재해야 합니다."
    if ! docker manifest inspect "${FULL_BASE_IMAGE_NAME}" >/dev/null 2>&1; then
        echo "❌ 레지스트리에 base 이미지가 없습니다: ${FULL_BASE_IMAGE_NAME}" >&2
        echo "   해결: --base-tag latest 사용 또는 --skip-base 없이 실행하여 base를 먼저 푸시" >&2
        exit 1
    fi
fi

# --- 2. 최종 애플리케이션 이미지 빌드 및 푸시 ---
echo "--- Step 2/2: 최종 앱 이미지(${FULL_APP_IMAGE_NAME}) 빌드 및 푸시 ---"
DOCKER_BUILDKIT=1 docker buildx build \
    --secret id=github_token,src=${GITHUB_TOKEN_FILE} \
    --build-arg DOCKER_USERNAME=${DOCKER_USERNAME} \
    --build-arg BASE_IMAGE_NAME=${BASE_IMAGE_NAME} \
    --build-arg BASE_IMAGE_TAG=${BASE_TAG} \
    -f dockerfile \
    "${NO_CACHE_ARGS[@]}" \
    -t "${FULL_APP_IMAGE_NAME}" \
    -t "${LATEST_APP_IMAGE_NAME}" \
    --push .

echo "✅ 모든 이미지가 성공적으로 빌드 및 푸시되었습니다!"
