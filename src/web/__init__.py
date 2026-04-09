# src/web/__init__.py
"""
Web module for static files and templates
"""

import os

def get_html_content():
    """Get the HTML content for the streaming dashboard"""
    html_path = os.path.join(os.path.dirname(__file__), 'templates', 'index.html')
    if os.path.exists(html_path):
        with open(html_path, 'r', encoding='utf-8') as f:
            return f.read()
    else:
        # Fallback to embedded HTML (will be moved to template file later)
        return get_embedded_html()

def get_embedded_html():
    """Get the embedded HTML content (from original code)"""
    # This will contain the HTML from the original code
    # For now, return a placeholder
    return """<!DOCTYPE html>
<html>
<head><title>OMRisk Video Streaming</title></head>
<body>
    <h1>Video Streaming Dashboard</h1>
    <p>Loading...</p>
</body>
</html>"""

__all__ = [
    'get_html_content'
]