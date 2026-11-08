from django.urls import path

from . import views

urlpatterns = [
    path("", views.WorkspaceView.as_view(), name="workspace"),
    path("login/", views.ProxmoxLoginView.as_view(), name="login"),
    path("logout/", views.ProxmoxLogoutView.as_view(), name="logout"),
    path("proxmox/refresh/", views.RefreshTicketView.as_view(), name="refresh_ticket"),
]
