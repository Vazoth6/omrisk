"""
Módulo web para ficheiros estáticos e modelos.
"""

import os
from typing import Optional


def get_html_content() -> str:
    """
    Obtém o conteúdo HTML para o dashboard de streaming.

    Retorna:
        str: Conteúdo HTML como string.
             Se o ficheiro template não for encontrado, retorna uma mensagem de erro.
    """
    # Constrói o caminho completo para o ficheiro index.html
    html_path = os.path.join(os.path.dirname(__file__), 'templates', 'index.html')
    
    # Verifica se o ficheiro existe
    if os.path.exists(html_path):
        # Lê e retorna o conteúdo do ficheiro HTML
        with open(html_path, 'r', encoding='utf-8') as f:
            return f.read()
    else:
        # Fallback: mensagem de erro se o template não for encontrado
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
    Obtém o conteúdo de um ficheiro estático.

    Args:
        filepath: Caminho relativo para o ficheiro estático (ex: 'css/style.css')

    Returns:
        Optional[bytes]: Conteúdo do ficheiro como bytes, ou None se não for encontrado
    """
    # Constrói o caminho completo para o ficheiro estático
    static_path = os.path.join(os.path.dirname(__file__), 'static', filepath)
    
    # Verifica se o ficheiro existe e é um ficheiro regular
    if os.path.exists(static_path) and os.path.isfile(static_path):
        # Lê e retorna o conteúdo do ficheiro em modo binário
        with open(static_path, 'rb') as f:
            return f.read()
    
    return None  # Retorna None se o ficheiro não for encontrado


def get_mime_type(filepath: str) -> str:
    """
    Determina o tipo MIME de um ficheiro estático com base na sua extensão.

    Args:
        filepath: Caminho ou extensão do ficheiro

    Returns:
        str: String do tipo MIME correspondente ao ficheiro
    """
    # Verifica a extensão do ficheiro e retorna o tipo MIME apropriado
    if filepath.endswith('.css'):
        return 'text/css'  # Folhas de estilo CSS
    elif filepath.endswith('.js'):
        return 'application/javascript'  # Ficheiros JavaScript
    elif filepath.endswith('.html'):
        return 'text/html'  # Páginas HTML
    elif filepath.endswith('.png'):
        return 'image/png'  # Imagens PNG
    elif filepath.endswith('.jpg') or filepath.endswith('.jpeg'):
        return 'image/jpeg'  # Imagens JPEG
    elif filepath.endswith('.svg'):
        return 'image/svg+xml'  # Imagens SVG
    else:
        return 'text/plain'  # Tipo MIME padrão para outros ficheiros


# ============================================================
# EXPORTAÇÃO DE SÍMBOLOS PÚBLICOS
# ============================================================
# Lista de funções que podem ser importadas por outros módulos
__all__ = [
    'get_html_content',
    'get_static_file',
    'get_mime_type'
]
