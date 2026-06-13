import socket

possibles = ['172', '192', '127']
ports = [9877, 9922, 5041, 2982, 7309]

def get_private_ip_and_subnet():
    try:
        # Connect to an external address to determine the default route interface IP
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))  # Doesn't actually send data
            ip = s.getsockname()[0]
        if ip.split('.')[0] in possibles:
            return ip, None  # socket alone can't retrieve the subnet mask
    except OSError:
        pass
    return None, None