"""
Minimal Proxmox VE API client: everything the lab site needs to log a student in
and show their VM console in an <iframe>.

How the login works
-------------------
1. POST /api2/json/access/ticket with the student's Proxmox username and password.
   Proxmox returns a *ticket* (valid for 2 hours) and a CSRFPreventionToken.
2. The ticket is what Proxmox's own web UI stores in a cookie named
   "PVEAuthCookie". If the student's browser has that cookie when it loads
   https://pve.../?console=kvm&novnc=1&vmid=..., the console page is already
   logged in -- so the <iframe> just works.
3. Our Django site can't set a cookie *for another site*, but it can set one for
   a parent domain both sites share (".kvcc.lab"), which the browser then sends
   to pve.kvcc.lab too. That's set_auth_cookie() below.
4. Tickets expire after 2 hours. Sending the current ticket as the password to
   /access/ticket returns a fresh one, so we renew it while the student works.

API docs: https://pve.proxmox.com/pve-docs/api-viewer/
"""

import time
from urllib.parse import quote, urlencode

import requests
import urllib3
from django.conf import settings

COOKIE_NAME = "PVEAuthCookie"
TICKET_LIFETIME = 2 * 60 * 60  # seconds; fixed by Proxmox

if settings.PROXMOX_VERIFY_SSL is False:
    # We've chosen to trust the self-signed cert; don't warn on every request.
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class ProxmoxError(Exception):
    pass


def _api(path):
    return f"{settings.PROXMOX_URL.rstrip('/')}/api2/json{path}"


def full_username(username):
    """Proxmox usernames include a realm: "student1" -> "student1@pve"."""
    if "@" not in username:
        username = f"{username}@{settings.PROXMOX_DEFAULT_REALM}"
    return username


def get_ticket(username, password):
    """
    Log in to Proxmox. `password` may also be a still-valid ticket, which renews it.

    Returns {"username", "ticket", "csrf_token", "issued_at"}.
    Raises ProxmoxError if the login is refused or Proxmox can't be reached.
    """
    try:
        r = requests.post(
            _api("/access/ticket"),
            data={"username": full_username(username), "password": password},
            verify=settings.PROXMOX_VERIFY_SSL,
            timeout=10,
        )
    except requests.RequestException as e:
        raise ProxmoxError(f"Could not reach Proxmox at {settings.PROXMOX_URL}: {e}") from e

    if r.status_code == 401:
        raise ProxmoxError("Proxmox rejected the username or password.")
    r.raise_for_status()

    data = r.json()["data"]
    if data.get("NeedTFA"):
        # Two-factor accounts get a half-finished ticket; not handled in this sample.
        raise ProxmoxError("This account uses two-factor authentication, which this sample doesn't support.")

    return {
        "username": data["username"],
        "ticket": data["ticket"],
        # Needed only for POST/PUT/DELETE calls made *with the ticket* (e.g. starting a VM).
        "csrf_token": data["CSRFPreventionToken"],
        "issued_at": time.time(),
    }


def renew_ticket(auth):
    """Exchange a still-valid ticket for a new one (resets the 2-hour clock)."""
    return get_ticket(auth["username"], auth["ticket"])


def list_vms(ticket):
    """
    VMs and containers this user can see. Proxmox filters the list by the user's
    permissions, so a student only gets the VMs they've been granted.
    """
    r = requests.get(
        _api("/cluster/resources"),
        params={"type": "vm"},
        # Server-side calls authenticate exactly like the browser does: with the cookie.
        headers={"Cookie": f"{COOKIE_NAME}={quote(ticket, safe='')}"},
        verify=settings.PROXMOX_VERIFY_SSL,
        timeout=10,
    )
    if r.status_code == 401:
        raise ProxmoxError("Proxmox ticket is no longer valid.")
    r.raise_for_status()
    return r.json()["data"]


def console_url(vm):
    """URL of the noVNC console page for a VM from list_vms(), for use in an <iframe>."""
    params = {
        "console": "lxc" if vm["type"] == "lxc" else "kvm",
        "novnc": 1,
        "vmid": vm["vmid"],
        "vmname": vm.get("name", ""),
        "node": vm["node"],
        "resize": "scale",  # shrink/grow the VM display to fit the iframe
    }
    return f"{settings.PROXMOX_URL.rstrip('/')}/?{urlencode(params)}"


def set_auth_cookie(response, ticket):
    """
    Give the student's browser the PVEAuthCookie so the console iframe is logged in.

    The value is URL-encoded, like Proxmox's own UI does it; Proxmox decodes it.
    (Unencoded, the "=" and "/" in a ticket would make Django wrap it in quotes.)
    """
    response.set_cookie(
        COOKIE_NAME,
        quote(ticket, safe=""),
        max_age=TICKET_LIFETIME,
        domain=settings.PROXMOX_COOKIE_DOMAIN or None,
        path="/",
        secure=settings.PROXMOX_COOKIE_SECURE,
        # Proxmox's own UI reads this cookie from JavaScript, so we match it and
        # leave it readable rather than HttpOnly.
        httponly=False,
        # Lax is sent with iframe loads as long as both sites are under the same
        # parent domain (and, in some browsers, use the same http/https scheme).
        samesite="Lax",
    )


def clear_auth_cookie(response):
    response.delete_cookie(
        COOKIE_NAME,
        domain=settings.PROXMOX_COOKIE_DOMAIN or None,
        path="/",
        samesite="Lax",
    )
