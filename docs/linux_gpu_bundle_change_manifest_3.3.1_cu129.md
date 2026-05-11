# 3.3.1 + cu129 小修改目录

本文列出这次为 `PaddlePaddle/PaddleOCR 3.3.1 + cu129` 离线 GPU 刷新涉及的替换文件，方便服务器上逐个替换。

## clinical-data-system

- `scripts/package_linux_gpu_offline_bundle.sh`
- `deploy/offline/paddle-ocr-api-gpu.Dockerfile`
- `deploy/linux/docker-compose.prod.gpu.yml`
- `docs/linux_migration_paddle_ocr_and_clinical_system.md`
- `docs/linux_gpu_bundle_refresh_3.3.1_cu129.md`
- `docs/linux_gpu_bundle_change_manifest_3.3.1_cu129.md`

## paddle-ocr-api

- `requirements.txt`
- `app/ocr_engine.py`
- `app/main.py`

## 说明

- `paddle-ocr-api/requirements.txt`：版本固定到 `3.3.1`
- `paddle-ocr-api/app/ocr_engine.py`：保留 GPU 初始化失败自动回退 CPU 的保护逻辑
- `paddle-ocr-api/app/main.py`：保留启动预热与真实健康检查状态
- `clinical-data-system/scripts/package_linux_gpu_offline_bundle.sh`：负责清理旧离线产物，并产出新版命名的 GPU 离线包
