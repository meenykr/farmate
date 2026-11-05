FROM mcr.microsoft.com/devcontainers/python:1-3.12-bookworm

RUN find /etc/apt/sources.list.d -maxdepth 1 -type f \
      \( -iname '*yarn*.list' -o -iname '*yarn*.sources' \) \
      -delete \
    && apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-kor tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/* \
    && tesseract --list-langs 2>/dev/null | grep -Fxq kor \
    && tesseract --list-langs 2>/dev/null | grep -Fxq eng
