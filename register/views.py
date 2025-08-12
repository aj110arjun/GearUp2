from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.contrib.auth import authenticate, login
from django.views.decorators.cache import never_cache


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
                
        if any(char.isdigit() for char in fullname):
            error['fullname'] = "Invalid Fullname"
            
        if User.objects.filter(username=email).exists():
            error['email'] = "Email already in use"
            
        if not error:
            User.objects.create_user(username=email, email=email, first_name=fullname, password=password1)
            redirect('login')
            
    return render(request, 'user/signup.html', {'error':error})

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
                return redirect('home')
            else:
                error["common"] = "Invalid email or password."
                
    return render(request, 'user/login.html', {'error': error})

