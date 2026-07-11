FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN groupadd --system parser && useradd --system --gid parser parser
COPY requirements.txt ./
RUN pip install --no-cache-dir --requirement requirements.txt
COPY --chown=parser:parser what_if_parse.py ./

USER parser
WORKDIR /output
ENTRYPOINT ["python", "/app/what_if_parse.py"]
CMD ["--help"]
