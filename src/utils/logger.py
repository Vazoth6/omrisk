# src/utils/logger.py
import logging
from datetime import datetime

def setup_logger(name: str, level=logging.INFO):
    """Setup a logger with console handler"""
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    if not logger.handlers:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    return logger

class Logger:
    """Simple logger for the application"""
    
    def __init__(self, name="VideoStreaming"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)
        
        # Only add handler if none exist
        if not self.logger.handlers:
            # Create console handler
            ch = logging.StreamHandler()
            ch.setLevel(logging.INFO)
            
            # Create formatter
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            ch.setFormatter(formatter)
            
            # Add handler to logger
            self.logger.addHandler(ch)
    
    def info(self, message):
        self.logger.info(message)
    
    def error(self, message):
        self.logger.error(message)
    
    def warning(self, message):
        self.logger.warning(message)
    
    def debug(self, message):
        self.logger.debug(message)

# Global logger instance
app_logger = Logger()