"""
Servidor de streaming de vídeo OmRisk
"""

__version__ = "1.0.0"
__author__ = "OMRisk Team"

from . import camera
from . import metrics
from . import server
from . import utils
from . import web

__all__ = [
    'camera',
    'metrics', 
    'server',
    'utils',
    'web'
]