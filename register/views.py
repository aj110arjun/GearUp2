from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.core.validators import validate_email
from django.core.exceptions import ValidationError


def user_signup(request):
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

def user_login(request):
    return render(request, 'user/login.html')

