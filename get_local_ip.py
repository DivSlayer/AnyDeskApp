import netifaces

possibles = ['172', '192', '127']
ports = [9877, 9922, 5041, 2982, 7309]

def get_private_ip_and_subnet():
    default_gws = netifaces.gateways().get('default', {})
    for interface in netifaces.interfaces():
        for addr in netifaces.ifaddresses(interface).get(netifaces.AF_INET, []):
            if (ip := addr['addr']).split('.')[0] in possibles:
                if any(gw[1] == interface for gw in default_gws.values()):
                    return ip, addr['netmask']
    return None, None
