import os
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
import datetime
import ipaddress

CERTS_DIR = "certs"

def ensure_certs_dir():
    if not os.path.exists(CERTS_DIR):
        os.makedirs(CERTS_DIR)

def generate_key():
    return rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )

def generate_self_signed_ca(key):
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, u"US"),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, u"TheBurrow"),
        x509.NameAttribute(NameOID.LOCALITY_NAME, u"Underground"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, u"HampterLink"),
        x509.NameAttribute(NameOID.COMMON_NAME, u"HampterLink Root CA"),
    ])
    cert = x509.CertificateBuilder().subject_name(
        subject
    ).issuer_name(
        issuer
    ).public_key(
        key.public_key()
    ).serial_number(
        x509.random_serial_number()
    ).not_valid_before(
        datetime.datetime.utcnow()
    ).not_valid_after(
        # Valid for 10 years
        datetime.datetime.utcnow() + datetime.timedelta(days=3650)
    ).add_extension(
        x509.BasicConstraints(ca=True, path_length=None), critical=True,
    ).sign(key, hashes.SHA256())
    return cert

def generate_node_cert(ca_cert, ca_key, node_key, common_name, ip_addr):
    subject = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, u"US"),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, u"TheBurrow"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, u"HampterLink"),
        x509.NameAttribute(NameOID.COMMON_NAME, common_name),
    ])
    
    # Subject Alternative Name (SAN) is required for IP addresses in modern TLS
    alt_names = [x509.IPAddress(ipaddress.ip_address(ip_addr))]
    
    cert = x509.CertificateBuilder().subject_name(
        subject
    ).issuer_name(
        ca_cert.subject
    ).public_key(
        node_key.public_key()
    ).serial_number(
        x509.random_serial_number()
    ).not_valid_before(
        datetime.datetime.utcnow()
    ).not_valid_after(
        datetime.datetime.utcnow() + datetime.timedelta(days=3650)
    ).add_extension(
        x509.SubjectAlternativeName(alt_names), critical=False,
    ).sign(ca_key, hashes.SHA256())
    return cert

def serialize_key(key, filename):
    with open(os.path.join(CERTS_DIR, filename), "wb") as f:
        f.write(key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        ))

def serialize_cert(cert, filename):
    with open(os.path.join(CERTS_DIR, filename), "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))

def main():
    print("[*] Generating Hampter Link Certificates...")
    ensure_certs_dir()

    # 1. Generate CA
    print("    - Generating CA Key and Certificate...")
    ca_key = generate_key()
    ca_cert = generate_self_signed_ca(ca_key)
    serialize_key(ca_key, "ca_key.pem")
    serialize_cert(ca_cert, "ca_cert.pem")

    # 2. Generate Node Key (Shared for simplicity in this demo, or unique per node)
    print("    - Generating Node Key...")
    node_key = generate_key()
    serialize_key(node_key, "key.pem")

    # 3. Generate Cert for Node A (192.168.100.1)
    print("    - Generating Certificate for Node A (192.168.100.1)...")
    cert_a = generate_node_cert(ca_cert, ca_key, node_key, u"Hampter Node A", "192.168.100.1")
    serialize_cert(cert_a, "cert.pem") # Saving as default 'cert.pem' for now

    # In a real deployment, we'd generate cert_b.pem separately and copy it to the other Pi
    
    print(f"[SUCCESS] Certificates generated in {CERTS_DIR}/")

if __name__ == "__main__":
    main()
