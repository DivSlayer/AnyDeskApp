import ssl

ssl_context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
# Treat your self-signed cert as a CA root:
ssl_context.load_verify_locations('cert.pem')
# If you used "CN=localhost" but are connecting to 127.0.0.1 or an IP:
ssl_context.check_hostname = False
