FROM --platform=linux/amd64 nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04

ARG PADDLE_VERSION=3.3.1
ARG PADDLE_GPU_INDEX_URL=https://www.paddlepaddle.org.cn/packages/stable/cu129/
ARG PYPI_INDEX_URL=https://pypi.org/simple

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
ENV PIP_TRUSTED_HOST=pypi.tuna.tsinghua.edu.cn
ENV PADDLE_PDX_MODEL_SOURCE=bos
ENV PADDLEX_MODEL_HEALTHCHECK_TIMEOUT=10
ENV PADDLE_OCR_DEVICE=gpu:0
WORKDIR /app

RUN set -eux; \
    sed -i \
      -e 's|http://archive.ubuntu.com/ubuntu/|https://mirrors.aliyun.com/ubuntu/|g' \
      -e 's|http://security.ubuntu.com/ubuntu/|https://mirrors.aliyun.com/ubuntu/|g' \
      /etc/apt/sources.list; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
      curl \
      libgomp1 \
      libglib2.0-0 \
      libgl1 \
      libsm6 \
      libxext6 \
      libxrender1 \
      poppler-utils \
      python3 \
      python3-pip \
      python3-venv; \
    ln -sf /usr/bin/python3 /usr/local/bin/python; \
    ln -sf /usr/bin/pip3 /usr/local/bin/pip; \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt

RUN set -eux; \
    python -m pip install --upgrade pip setuptools wheel; \
    grep -Ev '^paddlepaddle(==|-gpu==)' /app/requirements.txt > /app/requirements-gpu.txt; \
    python -m pip install "paddlepaddle-gpu==${PADDLE_VERSION}" -i "${PADDLE_GPU_INDEX_URL}"; \
    python -m pip install -i "${PYPI_INDEX_URL}" -r /app/requirements-gpu.txt

COPY app /app/app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
