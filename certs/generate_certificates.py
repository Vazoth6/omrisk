import subprocess
import sys
from pathlib import Path

def generate_certificates():
    """Generate SSL certificates using OpenSSL"""
    cert_dir = Path(__file__).parent
    cert_file = cert_dir / "certTwo.pem"
    key_file = cert_dir / "keyTwo.pem"
    
    if cert_file.exists() and key_file.exists():
        print("✅ Certificates already exist")
        return
    
    print("Generating SSL certificates...")
    
    cmd = [
        "openssl", "req", "-x509", "-newkey", "rsa:4096",
        "-keyout", str(key_file),
        "-out", str(cert_file),
        "-days", "365", "-nodes",
        "-subj", "/C=US/ST=State/L=City/O=Organization/CN=localhost"
    ]
    
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        print(f"✅ Certificate: {cert_file}")
        print(f"✅ Private key: {key_file}")
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed: {e.stderr.decode()}")
        sys.exit(1)
    except FileNotFoundError:
        print("❌ OpenSSL not found. Install: sudo apt install openssl")
        sys.exit(1)

if __name__ == "__main__":
    generate_certificates()