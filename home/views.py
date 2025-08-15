from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache
from django.views.decorators.cache import cache_control


@never_cache
@login_required(login_url='login')
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def home(request):
    if not request.user.is_authenticated:
        return redirect('login')
    return render(request, 'user/index.html')
#



# Admin Views

@login_required(login_url='admin_login')
def dashboard(request):
    return render(request, 'custom_admin/dashboard.html')