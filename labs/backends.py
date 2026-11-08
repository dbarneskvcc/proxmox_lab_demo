import logging

from django.contrib.auth import get_user_model

from . import proxmox

log = logging.getLogger(__name__)


class ProxmoxBackend:
    """
    Django auth backend that checks the username/password against Proxmox.

    There are no passwords stored in Django: if Proxmox issues a ticket, the
    student is in, and a matching Django User is created the first time.
    The ticket is attached to the user as `user.proxmox_auth` so the login view
    can save it in the session and hand the cookie to the browser.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        if not username or not password:
            return None
        try:
            auth = proxmox.get_ticket(username, password)
        except proxmox.ProxmoxError as e:
            log.warning("Proxmox login failed for %s: %s", username, e)
            if request is not None:
                request.proxmox_error = str(e)  # shown on the login page
            return None  # lets Django try the next backend (ModelBackend)

        User = get_user_model()
        user, created = User.objects.get_or_create(username=auth["username"])
        if created:
            user.set_unusable_password()
            user.save()
        user.proxmox_auth = auth
        return user

    def get_user(self, user_id):
        User = get_user_model()
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
