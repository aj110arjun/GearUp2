import pyotp
import time
import re

from django.core.mail import send_mail
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.contrib.auth import authenticate, login, logout
from django.views.decorators.cache import never_cache
from django.contrib import messages
from allauth.socialaccount.models import SocialAccount
from django.contrib.auth.password_validation import validate_password
from django.core.paginator import Paginator


### User Views
def custom_404(request, exception):
    return render(request, "404.html", status=404)

# signup view

@never_cache
def user_signup(request):
    if request.user.is_authenticated:
        return redirect('home')

    error = {}
    if request.method == 'POST':
        fullname = request.POST['fullname']
        email = request.POST['email']
        password1 = request.POST['password1']
        password2 = request.POST['password2']

        if not fullname or not email or not password1 or not password2:
            error['common'] = "All fields are required"

        if password1 != password2:
            error['password'] = "Both password must match"

        if password1:
            if len(password1) < 8:
                error['password1'] = "Length of password must be atleast 8"
            else:
                try:
                    # Django built-in strong password validation
                    validate_password(password1)
                except ValidationError as e:
                    error['password1'] = "\n".join(e.messages)

        if email:
            try:
                validate_email(email)
            except ValidationError:
                error['email'] = "Invalid Email"

            if User.objects.filter(username=email).exists():
                error['email'] = "Email already in use"

        if fullname:
            if not re.match(r'^[A-Za-z\s]+$', fullname):
                error['fullname'] = "Fullname must contain only letters and spaces"

            if len(fullname) < 3:
                error['fullname'] = "fullname should contain at least 3 characters"

        if not error:
            secret = pyotp.random_base32()
            totp = pyotp.TOTP(secret, interval=120)  # 1 minute expiry
            otp = totp.now()

            request.session["signup_data"] = {
                "fullname": fullname,
                "email": email,
                "password": password1,
                "secret": secret,
                "otp_time": time.time()
            }

            send_mail(
                "Your OTP Code",
                f"Your OTP code is: {otp}\n(It expires in 1 minute)",
                None,
                [email],
                fail_silently=False,
            )

            return redirect("verify_otp")

    return render(request, 'user/signup.html', {'error': error})


# login view
@never_cache
def user_login(request):
    if request.user.is_authenticated:
        return redirect('home')
        
    error={}
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        
        if not email or not password:
            error["common"]="All fields are required"
            
        if not error:
            user = authenticate(request, username=email, password=password)
            if user is not None:
                login(request, user)
                request.session.set_expiry(86400)
                return redirect('home')
            else:
                error["common"] = "Invalid email or password."
                
    return render(request, 'user/login.html', {'error': error})

def verify_otp(request):
    error = {}
    signup_data = request.session.get("signup_data")
    if not signup_data:
        return redirect('signup')

    # Check if OTP expired (more than 60 seconds past otp_time)
    otp_expired = time.time() - signup_data.get("otp_time", 0) > 120

    if request.method == 'POST' and not otp_expired:
        entered_otp = request.POST.get("otp")
        totp = pyotp.TOTP(signup_data["secret"], interval=120)
        if totp.verify(entered_otp):
            username = signup_data["email"]
            password = signup_data["password"]
            fullname = signup_data["fullname"]
            user = User.objects.create_user(
                username=username,
                email=username,
                password=password,
                first_name=fullname
            )
            login(request, user)
            del request.session["signup_data"]
            return redirect('home')
        else:
            error["otp"] = "Invalid or expired otp"
    elif request.method == "POST" and otp_expired:
        error["otp"] = "OTP has expired, please resend to get a new one."

    return render(request, "user/otp/verify_otp.html", {'error': error, 'otp_expired': otp_expired})


def resend_otp(request):
    signup_data = request.session.get("signup_data")

    if not signup_data:
        return redirect('signup')

    # Use the same secret stored in session
    totp = pyotp.TOTP(signup_data["secret"], interval=120)
    new_otp = totp.now()

    # Update otp_time to current time (reset timer)
    signup_data["otp_time"] = time.time()
    request.session["signup_data"] = signup_data  # Save session with updated time

    # Send OTP via email
    send_mail(
        "Your OTP Code",
        f"Your new OTP is: {new_otp}. It will expire in 60 seconds.",
        "noreply@yourdomain.com",
        [signup_data["email"]],
    )

    messages.success(request, "A new OTP has been sent to your email.")
    return redirect("verify_otp")


# logout view
def logout_view(request):
    logout(request)
    request.session.flush()
    return redirect('login')

def forgot_password(request):
    error = {}
    if request.method == "POST":
        email = request.POST.get("email")
        if not email:
            error["email"] = "Email is required"
        else:
            try:
                user = User.objects.get(username=email)
                # Generate OTP
                secret = pyotp.random_base32()
                totp = pyotp.TOTP(secret, interval=60)  
                otp = totp.now()

                # Store in session
                request.session["reset_data"] = {
                    "email": email,
                    "secret": secret,
                    "time": time.time()
                }

                # Send mail
                send_mail(
                    "Password Reset OTP",
                    f"Your OTP is {otp} (valid for 1 min)",
                    None,
                    [email],
                    fail_silently=False
                )
                return redirect("reset_password")
            except User.DoesNotExist:
                error["email"] = "No account found with this email"

    return render(request, "user/forgot_password.html", {"error": error})


def reset_password(request):
    error = {}
    reset_data = request.session.get("reset_data")
    if not reset_data:
        return redirect("forgot_password")

    if request.method == "POST":
        otp = request.POST.get("otp")
        new_password = request.POST.get("password")
        confirm_password = request.POST.get("confirm_password")

        totp = pyotp.TOTP(reset_data["secret"], interval=60)
        if not totp.verify(otp):
            error["otp"] = "Invalid or expired OTP"
        elif not new_password or not confirm_password:
            error["password"] = "Password fields are required"
        elif new_password != confirm_password:
            error["password"] = "Passwords do not match"
        elif len(new_password) < 6:
            error["password"] = "Password must be at least 6 characters"
        else:
            user = User.objects.get(username=reset_data["email"])
            user.set_password(new_password)
            user.save()
            del request.session["reset_data"]
            messages.success(request, "Password reset successfully. Please login.")
            return redirect("login")

    return render(request, "user/reset_password.html", {"error": error})



# Admin Views

# login view 
def admin_login(request):
    # If already logged in as staff, redirect to dashboard
    if request.user.is_authenticated and request.user.is_staff:
        return redirect('dashboard')

    if request.method == "POST":
        error={}
        username = request.POST.get("username").strip()
        password = request.POST.get("password").strip()

        user = authenticate(request, username=username, password=password)

        if user is not None:
            if user.is_staff:  # Check if user is admin/staff
                login(request, user)
                return redirect('dashboard')
            else:
                error['admin'] = "You do not have admin access."
        else:
            error['admin'] = "Invalid username or password"
        if error:
            return render(request, "custom_admin/login.html", {'error':error})
            

    return render(request, "custom_admin/login.html")

def user_list(request):
    users = User.objects.exclude(is_staff=True).order_by("-date_joined")
    context = {
        "users": users,
    }
    return render(request, 'custom_admin/users/user_list.html', context)

def account_inactive_view(request):
    return render(request, 'accounts/account_inactive.html')

def toggle_user_status(request, user_id):
    user = get_object_or_404(User, id=user_id)
    if user.is_active:
        user.is_active = False
    else:
        user.is_active = True
    user.save()
    return redirect('user_list')


def admin_logout_view(request):
    logout(request)
    request.session.flush()
    return redirect('admin_login')

