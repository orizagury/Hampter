"""
Certificate Generator for Hampter Link.
Creates self-signed CA and node certificates for mutual TLS authentication.
"""
import os
from datetime import datetime, timezone, timedelta
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
import ipaddress

CERTS_DIR = "certs"


def ensure_certs_dir():
    """Create certificates directory if it doesn't exist."""
    if not os.path.exists(CERTS_DIR):
        os.makedirs(CERTS_DIR)


def generate_key():
    """Generate a new RSA private key."""
    return rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )


def generate_self_signed_ca(key):
    """Generate a self-signed CA certificate."""
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "TheBurrow"),
        x509.NameAttribute(NameOID.LOCALITY_NAME, "Underground"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "HampterLink"),
        x509.NameAttribute(NameOID.COMMON_NAME, "HampterLink Root CA"),
    ])
    
    now = datetime.now(timezone.utc)
    
    cert = x509.CertificateBuilder().subject_name(
        subject
    ).issuer_name(
        issuer
    ).public_key(
        key.public_key()
    ).serial_number(
        x509.random_serial_number()
    ).not_valid_before(
        now
    ).not_valid_after(
        now + timedelta(days=3650)  # Valid for 10 years
    ).add_extension(
        x509.BasicConstraints(ca=True, path_length=None), critical=True,
    ).sign(key, hashes.SHA256())
    
    return cert


def generate_node_cert(ca_cert, ca_key, node_key, common_name, ip_addr):
    """Generate a node certificate signed by the CA."""
    subject = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "TheBurrow"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "HampterLink"),
        x509.NameAttribute(NameOID.COMMON_NAME, common_name),
    ])
    
    # Subject Alternative Name (SAN) is required for IP addresses in modern TLS
    alt_names = [x509.IPAddress(ipaddress.ip_address(ip_addr))]
    
    now = datetime.now(timezone.utc)
    
    cert = x509.CertificateBuilder().subject_name(
        subject
    ).issuer_name(
        ca_cert.subject
    ).public_key(
        node_key.public_key()
    ).serial_number(
        x509.random_serial_number()
    ).not_valid_before(
        now
    ).not_valid_after(
        now + timedelta(days=3650)
    ).add_extension(
        x509.SubjectAlternativeName(alt_names), critical=False,
    ).sign(ca_key, hashes.SHA256())
    
    return cert


def serialize_key(key, filename):
    """Save a private key to PEM file."""
    filepath = os.path.join(CERTS_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        ))
    print(f"    Saved: {filepath}")


def serialize_cert(cert, filename):
    """Save a certificate to PEM file."""
    filepath = os.path.join(CERTS_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))
    print(f"    Saved: {filepath}")


def main():
    """Generate all required certificates."""
    print("[*] Generating Hampter Link Certificates...")
    ensure_certs_dir()

    # 1. Generate CA
    print("    - Generating CA Key and Certificate...")
    ca_key = generate_key()
    ca_cert = generate_self_signed_ca(ca_key)
    serialize_key(ca_key, "ca_key.pem")
    serialize_cert(ca_cert, "ca_cert.pem")

    # 2. Generate Node Key
    print("    - Generating Node Key...")
    node_key = generate_key()
    serialize_key(node_key, "key.pem")

    # 3. Generate Cert for Node A (192.168.100.1)
    print("    - Generating Certificate for Node A (192.168.100.1)...")
    cert_a = generate_node_cert(ca_cert, ca_key, node_key, "Hampter Node A", "192.168.100.1")
    serialize_cert(cert_a, "cert.pem")

    # 4. Generate Cert for Node B (192.168.100.2) 
    print("    - Generating Certificate for Node B (192.168.100.2)...")
    cert_b = generate_node_cert(ca_cert, ca_key, node_key, "Hampter Node B", "192.168.100.2")
    serialize_cert(cert_b, "cert_b.pem")

    print(f"\n[SUCCESS] Certificates generated in {CERTS_DIR}/")
    print("\nNote: Copy 'cert_b.pem' to Node B and rename to 'cert.pem'")


if __name__ == "__main__":
    main()
