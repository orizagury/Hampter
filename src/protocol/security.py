import ssl
from cryptography import x509
from cryptography.hazmat.backends import default_backend
import os

class HampterSecurity:
    def __init__(self, cert_path: str, key_path: str, ca_path: str, password: str = None):
        self.cert_path = cert_path
        self.key_path = key_path
        self.ca_path = ca_path
        self.password = password

    def get_ssl_context(self, purpose: ssl.Purpose = ssl.Purpose.SERVER_AUTH) -> ssl.SSLContext:
        """
        Creates a highly secure TLS 1.3 Context.
        If purpose is CLIENT_AUTH, it means we are the Server verifying the Client.
        If purpose is SERVER_AUTH, it means we are the Client verifying the Server.
        """
        
        # We need a context that supports both acting as a server and a client (Peer-to-Peer)
        if purpose == ssl.Purpose.CLIENT_AUTH:
             # We are the server, we want the client to authenticate
            ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            ctx.verify_mode = ssl.CERT_REQUIRED
        else:
            # We are the client connecting to the server
            ctx = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
            ctx.check_hostname = False # In P2P Mesh with IP addressing, hostname verification is tricky unless we map Cert CN to IPs.
                                       # We verify CA trust instead.

        # Load our Identity
        ctx.load_cert_chain(certfile=self.cert_path, keyfile=self.key_path, password=self.password)
        
        # Load the Trust Store (Root CA)
        ctx.load_verify_locations(cafile=self.ca_path)
        
        # Enforce TLS 1.3
        ctx.minimum_version = ssl.TLSVersion.TLSv1_3
        
        return ctx
