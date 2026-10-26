from django.contrib.auth import logout
from django.shortcuts import redirect


class ActiveStaffMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and not request.user.is_active:
            logout(request)
            return redirect("/login/")
        response = self.get_response(request)
        response["Cache-Control"] = "no-store, private"
        return response
