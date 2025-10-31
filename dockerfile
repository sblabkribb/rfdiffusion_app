# Dockerfile
ARG DOCKER_USERNAME=mimikyou0607
ARG BASE_IMAGE_NAME=rfdiffusion-base
ARG BASE_IMAGE_TAG=latest

FROM ${DOCKER_USERNAME}/${BASE_IMAGE_NAME}:${BASE_IMAGE_TAG}

WORKDIR /workspace/app
COPY handler.py .
RUN pip install --no-cache-dir runpod
CMD ["python", "-u", "handler.py"]
