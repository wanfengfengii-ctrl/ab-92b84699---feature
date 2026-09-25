FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=8000

WORKDIR /app

# 零第三方依赖：直接复制应用代码与测试。
COPY app/ ./app/
COPY tests/ ./tests/
COPY scripts/ ./scripts/
RUN chmod +x ./scripts/verify.sh ./scripts/healthcheck.py

EXPOSE 8000

# 容器级健康检查：请求 /healthz，供 Compose 判定就绪状态。
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=5 \
    CMD ["python3", "scripts/healthcheck.py"]

CMD ["python3", "-m", "app.server"]
