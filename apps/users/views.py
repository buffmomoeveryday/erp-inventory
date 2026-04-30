from django.contrib.auth import authenticate
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest
from django.shortcuts import redirect, render


def login(request: HttpRequest):
    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")

        user = authenticate(request, username=email, password=password)
        if user is not None:
            auth_login(request, user)
            return redirect("dashboard")
        else:
            return render(
                request,
                "users/login.html",
                context={"error": "Invalid credentials"},
            )

    return render(request, "users/login.html")


@login_required
def logout(request: HttpRequest):
    auth_logout(request)
    return redirect("login")
