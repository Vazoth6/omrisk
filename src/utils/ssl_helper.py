# src/utils/ssl_helper.py
import os
import subprocess

def generate_self_signed_cert(cert_file="certs/certTwo.pem", key_file="certs/&keyTwo.pem"):
    """Generate a self-signed certificate for development"""
    print("Generating self-signed SSL certificate...")
    
    print("\n⚠️  SSL Certificate Generation Required ⚠️")
    print("\nTo generate SSL certificates on Linux:")
    print("1. Install OpenSSL: sudo apt install openssl")
    print("2. Generate certificate:")
    print(f"   openssl req -x509 -newkey rsa:4096 -keyout {key_file} -out {cert_file} -days 365 -nodes -subj \"/C=US/ST=State/L=City/O=Organization/CN=localhost\"")
    
    print("\n⚠️  IMPORTANT: Self-signed certificates will show security warnings in browsers!")
    
    if os.path.exists(cert_file) and os.path.exists(key_file):
        print("✅ Certificates found!")
        return True
    else:
        print("❌ Certificates not found. SSL features will not work.")
        return False

def check_certificates(cert_file="certs/certTwo.pem", key_file="certs/keyTwo.pem"):
    """Check if SSL certificates exist"""
    return os.path.exists(cert_file) and os.path.exists(key_file)