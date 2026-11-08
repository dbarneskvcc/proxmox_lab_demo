import time

from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView, LogoutView
from django.http import JsonResponse
from django.shortcuts import redirect
from django.views import View
from django.views.generic import TemplateView

from . import proxmox
from .sample_data import LABS

SESSION_KEY = "proxmox_auth"
RENEW_AFTER = 5 * 60  # renew on page load if the ticket is older than this (seconds)


class ProxmoxTicketMixin:
    """Shared by views that need the student's Proxmox ticket from the session."""

    def get_proxmox_auth(self, force_renew=False):
        """
        The student's Proxmox ticket from the session, renewed if it's getting old.
        Returns None if there is no usable ticket (they must log in again).
        """
        auth = self.request.session.get(SESSION_KEY)
        if not auth:
            return None

        age = time.time() - auth["issued_at"]
        if age > proxmox.TICKET_LIFETIME - 30:
            return None  # already expired; Proxmox won't renew it

        if force_renew or age > RENEW_AFTER:
            try:
                auth = proxmox.renew_ticket(auth)
            except proxmox.ProxmoxError:
                return None
            self.request.session[SESSION_KEY] = auth
        return auth


class ProxmoxLoginView(LoginView):
    template_name = "labs/login.html"

    def form_valid(self, form):
        response = super().form_valid(form)  # logs the user in to Django
        auth = getattr(form.get_user(), "proxmox_auth", None)
        if auth:
            # Keep the ticket server-side so we can renew it and call the API...
            self.request.session[SESSION_KEY] = auth
            # ...and give it to the browser so the console iframe is logged in.
            proxmox.set_auth_cookie(response, auth["ticket"])
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Set by ProxmoxBackend when the login fails; far more useful than
        # "invalid username or password" when the real problem is the network/cert.
        context["proxmox_error"] = getattr(self.request, "proxmox_error", None)
        return context


class ProxmoxLogoutView(LogoutView):
    # LogoutView only accepts POST, logs out (clearing the session and the stored
    # ticket) and redirects to LOGOUT_REDIRECT_URL. We also remove the browser's cookie.
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        proxmox.clear_auth_cookie(response)
        return response


class WorkspaceView(LoginRequiredMixin, ProxmoxTicketMixin, TemplateView):
    template_name = "labs/workspace.html"

    def get(self, request, *args, **kwargs):
        self.auth = self.get_proxmox_auth()
        if self.auth is None:
            logout(request)
            messages.warning(request, "Your Proxmox session expired. Please log in again.")
            return redirect("login")

        response = super().get(request, *args, **kwargs)
        # Re-send the cookie on every page load so it always matches the newest ticket.
        proxmox.set_auth_cookie(response, self.auth["ticket"])
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            vm_list = proxmox.list_vms(self.auth["ticket"])
            vm_error = None
        except Exception as e:  # show the problem on the page instead of a 500
            vm_list, vm_error = [], str(e)

        # Keyed by VM id, so each lab in LABS can look up its VM.
        vms = {
            vm["vmid"]: {
                "vmid": vm["vmid"],
                "name": vm.get("name", f"vm-{vm['vmid']}"),
                "node": vm["node"],
                "status": vm.get("status", "unknown"),
                "console_url": proxmox.console_url(vm),
            }
            for vm in vm_list
        }

        context.update({
            "labs": LABS,
            "vms": vms,
            "vm_error": vm_error,
            "proxmox_username": self.auth["username"],
        })
        return context


class RefreshTicketView(ProxmoxTicketMixin, View):
    """Called by the workspace page every few minutes to keep the console logged in."""

    http_method_names = ["post"]

    # No LoginRequiredMixin here: it would redirect to the login page, but this is
    # called from JavaScript, which needs a 401 it can react to instead.
    def post(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({"ok": False}, status=401)

        auth = self.get_proxmox_auth(force_renew=True)
        if auth is None:
            return JsonResponse({"ok": False}, status=401)

        response = JsonResponse({"ok": True})
        proxmox.set_auth_cookie(response, auth["ticket"])
        return response
