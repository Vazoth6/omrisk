import os
from dataclasses import dataclass
import socket

@dataclass
class Config:
    # Server settings
    HTTP_PORT: int = int(os.getenv('HTTP_PORT', 8000))
    WS_PORT: int = int(os.getenv('WS_PORT', 3001))
    HOST: str = '0.0.0.0'
    
    # Camera settings
    CAMERA_WIDTH: int = 1280
    CAMERA_HEIGHT: int = 720
    TARGET_FPS: int = 30
    JPEG_QUALITY: int = 70
    
    # Metrics settings
    MAX_METRIC_SAMPLES: int = 1000
    SUMMARY_INTERVAL: int = 10  # seconds
    
    @property
    def SERVER_IP(self) -> str:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"

config = Config()