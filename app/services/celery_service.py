# This is for setting the Celery service.
from celery import Celery

celery = Celery(
    'Automated_Pen_Testing',
    broker='redis://localhost:6379',  # The port "6379" is the standard port for Redis
    backend='redis://localhost:6379'  # Configure Redis as the result backend
)