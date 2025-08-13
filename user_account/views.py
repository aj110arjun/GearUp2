from django.contrib.auth.decorators import login_required
from django.contrib.auth import update_session_auth_hash
from django.core.mail import send_mail
from django.shortcuts import render, redirect
from django.contrib.auth.models import User

from .forms import ProfileEditForm
from .models import Profile

@login_required(login_url='login')
def account_info(request):
    profile, created = Profile.objects.get_or_create(user=request.user)
    success_message = None
    if request.session.get('profile_updated'):
        success_message = "✅ Profile updated successfully!"
        del request.session['profile_updated']
    return render(request, 'user/account.html', { 'profile': profile, 'success_message': success_message})

@login_required(login_url='login')
def edit_profile(request):
    error = {}
    profile, created = Profile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        form = ProfileEditForm(request.POST, request.FILES, user=request.user, instance=profile)
        
        if form.is_valid():
            user = request.user

            # Update name & email
            user.first_name = form.cleaned_data['name']
            user.email = form.cleaned_data['email']

            # Handle password change
            current_password = form.cleaned_data['current_password']
            new_password = form.cleaned_data['new_password']
            confirm_password = form.cleaned_data['confirm_password']

            if new_password:
                if not user.check_password(current_password):
                    error['cupassword'] = "Current password is incorrect."
                if new_password != confirm_password:
                    error['cpassword'] = "New passwords do not match."
                if len(new_password)<6:
                    error['password'] = "Password must be atleast 6 characters"

            # If there are no password errors, save
            if not error:
                user.set_password(new_password)
                update_session_auth_hash(request, user)  
                user.save()
                form.save()
                request.session['profile_updated'] = True
                return redirect('account_info')
    else:
        form = ProfileEditForm(user=request.user, instance=profile)

    return render(request, 'user/edit_profile.html', {
        'form': form,
        'profile': profile,  # ✅ send profile to template
        'error': error
    })

def confirm_email(request, user_id, new_email):
    user = User.objects.get(id=user_id)
    user.email = new_email
    user.save()
    # messages.success(request, "Email updated successfully.")
    return redirect('edit_profile')
