"""
WSGI config for VGSync project.

It exposes the WSGI callable as a module-level variable named ``application``.
"""

import os
import logging
from django.core.wsgi import get_wsgi_application

logger = logging.getLogger(__name__)
logger.info("Loading WSGI application...")

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'main.settings')

application = get_wsgi_application()
logger.info("WSGI application loaded successfully")
