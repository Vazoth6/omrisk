# utils/network.py
import socket
import platform
import sys

def get_ip_address():
    """Get the local IP address of the machine"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip_address = s.getsockname()[0]
        s.close()
        return ip_address
    except Exception:
        try:
            hostname = socket.gethostname()
            return socket.gethostbyname(hostname)
        except:
            return "127.0.0.1"

def check_port_available(port, host='127.0.0.1'):
    """Check if a port is available"""
    try:
        test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        test_socket.settimeout(1)
        result = test_socket.connect_ex((host, port))
        test_socket.close()
        return result != 0
    except:
        return False

def get_system_info():
    """Get system information"""
    return {
        'hostname': socket.gethostname(),
        'platform': platform.platform(),
        'python_version': sys.version,
        'ip_address': get_ip_address()
    }