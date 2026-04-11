# src/web/__init__.py
"""
Web module for static files and templates
"""

import os
from typing import Optional

def get_html_content() -> str:
    """
    Get the HTML content for the streaming dashboard
    
    Returns:
        HTML content as string
    """
    html_path = os.path.join(os.path.dirname(__file__), 'templates', 'index.html')
    if os.path.exists(html_path):
        with open(html_path, 'r', encoding='utf-8') as f:
            return f.read()
    else:
        # Fallback to error message if template not found
        return """<!DOCTYPE html>
<html>
<head><title>Error</title></head>
<body>
    <h1>Template not found</h1>
    <p>The index.html template file could not be loaded.</p>
</body>
</html>"""

def get_static_file(filepath: str) -> Optional[bytes]:
    """
    Get a static file's content
    
    Args:
        filepath: Relative path to static file (e.g., 'css/style.css')
    
    Returns:
        File content as bytes, or None if not found
    """
    static_path = os.path.join(os.path.dirname(__file__), 'static', filepath)
    if os.path.exists(static_path) and os.path.isfile(static_path):
        with open(static_path, 'rb') as f:
            return f.read()
    return None

def get_mime_type(filepath: str) -> str:
    """
    Get MIME type for a static file
    
    Args:
        filepath: File path or extension
    
    Returns:
        MIME type string
    """
    if filepath.endswith('.css'):
        return 'text/css'
    elif filepath.endswith('.js'):
        return 'application/javascript'
    elif filepath.endswith('.html'):
        return 'text/html'
    elif filepath.endswith('.png'):
        return 'image/png'
    elif filepath.endswith('.jpg') or filepath.endswith('.jpeg'):
        return 'image/jpeg'
    elif filepath.endswith('.svg'):
        return 'image/svg+xml'
    else:
        return 'text/plain'

__all__ = [
    'get_html_content',
    'get_static_file',
    'get_mime_type'
]