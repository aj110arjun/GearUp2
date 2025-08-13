from django.contrib.auth.decorators import login_required
from django.contrib.auth import update_session_auth_hash
from django.core.mail import send_mail
from django.shortcuts import render, redirect
from django.contrib.auth.models import User

from .forms import ProfileEditForm
from .models import Profile

@login_required(login_url='login')
def account_info(request):
    return render(request, 'user/account.html')


def edit_profile(request):
    # ✅ Create profile if missing
    profile, created = Profile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        form = ProfileEditForm(request.POST, request.FILES, user=request.user, instance=profile)
        
        if form.is_valid():
            user = request.user

            # Update name
            user.first_name = form.cleaned_data['name']
            user.email = form.cleaned_data['email']

            # Password change
            current_password = form.cleaned_data['current_password']
            new_password = form.cleaned_data['new_password']
            confirm_password = form.cleaned_data['confirm_password']

            if new_password:  # ✅ Only run password change if filled
                if not user.check_password(current_password):
                    # messages.error(request, "Current password is incorrect.")
                    return redirect('edit_profile')

                if new_password != confirm_password:
                    # messages.error(request, "New passwords do not match.")
                    return redirect('edit_profile')

                user.set_password(new_password)
                update_session_auth_hash(request, user)  # Keep user logged in

            user.save()
            form.save()
            # messages.success(request, "Profile updated successfully.")
            return redirect('account_info')

    else:
        form = ProfileEditForm(user=request.user, instance=profile)

    return render(request, 'user/edit_profile.html', {'form': form})

def confirm_email(request, user_id, new_email):
    user = User.objects.get(id=user_id)
    user.email = new_email
    user.save()
    # messages.success(request, "Email updated successfully.")
    return redirect('edit_profile')
