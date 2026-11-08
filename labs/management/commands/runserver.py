"""
`python manage.py runserver`, but over HTTPS.

Why: the Proxmox console runs on https://pve..., and browsers only send the
PVEAuthCookie into the <iframe> if this site is *also* HTTPS (http vs https
counts as a different site). So in this project the normal runserver command
is replaced with this one. Usage is unchanged:

    python manage.py runserver labs.example.com:8000

The first run creates a self-signed certificate in certs/ (ignored by Git).
Browsers will warn about it once; that's expected for a dev certificate.

This file is picked up instead of Django's own runserver because the `labs`
app is listed before `django.contrib.staticfiles` in INSTALLED_APPS.
"""

import datetime
import ipaddress
import ssl

from django.conf import settings
from django.contrib.staticfiles.management.commands.runserver import Command as StaticfilesRunserver
from django.core.servers.basehttp import WSGIServer

CERT_DIR = settings.BASE_DIR / "certs"
CERT_FILE = CERT_DIR / "dev.crt"
KEY_FILE = CERT_DIR / "dev.key"


class HTTPSWSGIServer(WSGIServer):
    ssl_context = None  # set by the command before the server starts

    def server_activate(self):
        super().server_activate()
        # do_handshake_on_connect=False: the TLS handshake happens in each
        # request's own thread (finish_request below), not while accepting.
        # Otherwise one idle connection -- browsers open spare ones in advance --
        # would block the whole server.
        self.socket = self.ssl_context.wrap_socket(
            self.socket, server_side=True, do_handshake_on_connect=False
        )

    def finish_request(self, request, client_address):
        try:
            request.settimeout(30)
            request.do_handshake()
            request.settimeout(None)
        except (ssl.SSLError, OSError):
            # e.g. the browser rejecting our self-signed certificate, or an
            # idle spare connection being closed. Nothing to serve.
            return
        super().finish_request(request, client_address)

    def setup_environ(self):
        super().setup_environ()
        self.base_environ["HTTPS"] = "on"  # so Django's request.is_secure() is True


class Command(StaticfilesRunserver):
    help = "Starts a lightweight web server for development over HTTPS (self-signed certificate)."
    protocol = "https"
    server_cls = HTTPSWSGIServer

    def inner_run(self, *args, **options):
        if not (CERT_FILE.exists() and KEY_FILE.exists()):
            self.stdout.write(f"Creating a self-signed development certificate in {CERT_DIR} ...")
            create_dev_certificate()
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(CERT_FILE, KEY_FILE)
        HTTPSWSGIServer.ssl_context = context
        super().inner_run(*args, **options)


def create_dev_certificate():
    """Self-signed certificate valid for ALLOWED_HOSTS, localhost and 127.0.0.1."""
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    names = {"localhost", "127.0.0.1", *(h for h in settings.ALLOWED_HOSTS if h and not h.startswith(".") and h != "*")}
    san = []
    for name in sorted(names):
        try:
            san.append(x509.IPAddress(ipaddress.ip_address(name)))
        except ValueError:
            san.append(x509.DNSName(name))

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Django development server")])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=365))
        .add_extension(x509.SubjectAlternativeName(san), critical=False)
        .sign(key, hashes.SHA256())
    )

    CERT_DIR.mkdir(exist_ok=True)
    KEY_FILE.write_bytes(key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    ))
    CERT_FILE.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
