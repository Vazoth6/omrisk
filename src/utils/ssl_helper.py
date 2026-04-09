import ssl
import os
from pathlib import Path

def setup_ssl() -> ssl.SSLContext | None:
    """Setup SSL context if certificates exist"""
    cert_dir = Path("certs")
    cert_file = cert_dir / "cert.pem"
    key_file = cert_dir / "key.pem"
    
    if cert_file.exists() and key_file.exists():
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(certfile=str(cert_file), keyfile=str(key_file))
        print("✅ SSL enabled")
        return context
    
    print("⚠️  SSL disabled (certificates not found)")
    print("   Run: cd certs && python generate_certificates.py")
    return None