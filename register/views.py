import pyotp
import time

from django.core.mail import send_mail
from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.contrib.auth import authenticate, login, logout
from django.views.decorators.cache import never_cache


### User Views

# signup view
@never_cache
def user_signup(request):
    if request.user.is_authenticated:
        return redirect('home')
    error={}
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
            if len(password1)<6:
                error['password1'] = "Length of password must be above 6"
                
        if email:
            try:
                validate_email(email)
            except ValidationError:
                error['email'] = "Invalid Email"
                
        if any(char.isdigit() for char in fullname) or "_" in fullname:
            error['fullname'] = "Invalid Fullname"
            
        if len(fullname)<3:
            error['fullname'] = "fullname should contain atleast 3 characters"
        
        if User.objects.filter(username=email).exists():
            error['email'] = "Email already in use"
            
        if not error:
            secret = pyotp.random_base32()
            totp = pyotp.TOTP(secret, interval=60)  # 1 minute expiry
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
            
    return render(request, 'user/signup.html', {'error':error})

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
    error={}
    signup_data = request.session.get("signup_data")
    
    if not signup_data:
        return redirect('signup')

    if request.method == 'POST':
        entered_otp = request.POST.get("otp")
        totp = pyotp.TOTP(signup_data["secret"], interval=60)
        
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
    return render(request, "user/otp/verify_otp.html", {'error': error})

# logout view
def logout_view(request):
    logout(request)
    request.session.flush()
    return redirect('login')


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

