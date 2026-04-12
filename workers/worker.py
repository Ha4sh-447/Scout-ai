import os
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from celery import Celery
from celery.signals import setup_logging
from dotenv import load_dotenv

@setup_logging.connect
def config_loggers(*args, **kwargs):
    log_dir = Path("/app/data/logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter('[%(asctime)s: %(levelname)s/%(processName)s] %(name)s - %(message)s')
    
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    
    file_handler = RotatingFileHandler(
        log_dir / "celery_pipeline.log", 
        maxBytes=10*1024*1024, # 10MB
        backupCount=5
    )
    file_handler.setFormatter(formatter)
    
    logger.handlers.clear()
    logger.addHandler(stream_handler)
    logger.addHandler(file_handler)

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

_raw_db_url = os.environ.get("DATABASE_URL", "")
DATABASE_URL = (
    _raw_db_url
    .replace("postgresql+asyncpg://", "db+postgresql+psycopg2://")
    .replace("postgresql://", "db+postgresql+psycopg2://")
    .replace("postgres://", "db+postgresql+psycopg2://")
)

celery_app = Celery(
    "job_agent",
    broker=REDIS_URL,
    backend=DATABASE_URL,
    include=["workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_track_started=True,
    result_expires=86400,
    broker_connection_retry_on_startup=True,
    redis_max_connections=20,
    worker_concurrency=1,
    broker_transport_options={
        "visibility_timeout": 3600,
        "socket_timeout": 30,
        "socket_connect_timeout": 30,
        "socket_keepalive": True,
        "retry_on_timeout": True,
    },
)