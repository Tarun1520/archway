# Laya, the open-source decision model, on CPU (the free server has no GPU; its short yes/no questions are quick).
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 HF_HOME=/models
# The CPU build of PyTorch first (much smaller than the default build), then Laya and its server.
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu \
 && pip install "laya[serve]==0.4.8"

RUN useradd --create-home --uid 10002 laya && mkdir -p /models && chown laya /models
USER laya

ENV LAYA_HOST=0.0.0.0 LAYA_PORT=8100 LAYA_MODELS=english,typed-decisions LAYA_AUTO_TASK=1 LAYA_LOG_LEVEL=warning
EXPOSE 8100
CMD ["laya-serve"]
