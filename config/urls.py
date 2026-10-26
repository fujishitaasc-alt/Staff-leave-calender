from django.contrib import admin
from django.urls import path
from django.contrib.auth import views as auth
from leave import views

urlpatterns = [
    path("", views.calendar_view, name="calendar"),
    path("mine/", views.mine, name="mine"),
    path("new/", views.edit, name="new"),
    path("leave/<int:pk>/", views.edit, name="edit"),
    path("leave/<int:pk>/cancel/", views.cancel, name="cancel"),
    path("login/", auth.LoginView.as_view(), name="login"),
    path("logout/", auth.LogoutView.as_view(), name="logout"),
    path(
        "password/",
        auth.PasswordChangeView.as_view(
            template_name="registration/password.html", success_url="/mine/"
        ),
        name="password_change",
    ),
    path("admin/", admin.site.urls),
]
