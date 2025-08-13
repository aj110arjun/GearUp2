import random

from django.contrib.auth.decorators import login_required
from django.contrib.auth import update_session_auth_hash
from django.core.mail import send_mail
from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.utils import timezone
from django.conf import settings

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
            new_name = form.cleaned_data['name']
            new_email = form.cleaned_data['email']

            # Update name (safe to apply immediately)
            user.first_name = new_name

            # Handle email change with OTP
            if new_email and new_email != user.email:
                otp = str(random.randint(100000, 999999))
                profile.pending_email = new_email
                profile.email_otp = otp
                profile.otp_expiry = timezone.now() + timezone.timedelta(minutes=10)
                profile.save()

                send_mail(
                    "Email Verification OTP",
                    f"Your OTP to verify your new email is: {otp}",
                    settings.DEFAULT_FROM_EMAIL,
                    [new_email],
                )

                request.session['otp_for_email_change'] = True
                return redirect('verify_email_otp')

            # Handle password change
            current_password = form.cleaned_data['current_password']
            new_password = form.cleaned_data['new_password']
            confirm_password = form.cleaned_data['confirm_password']

            if new_password:
                if not user.check_password(current_password):
                    error['cupassword'] = "Current password is incorrect."
                if new_password != confirm_password:
                    error['cpassword'] = "New passwords do not match."
                if len(new_password) < 6:
                    error['password'] = "Password must be at least 6 characters"

            # Save changes if no errors
            if not error:
                if new_password:
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
        'profile': profile,
        'error': error
    })


@login_required(login_url='login')
def verify_email_otp(request):
    profile = request.user.profile
    message = None

    if request.method == 'POST':
        entered_otp = request.POST.get("otp")

        if (
            profile.email_otp == entered_otp and
            profile.otp_expiry and
            timezone.now() <= profile.otp_expiry
        ):
            request.user.email = profile.pending_email
            request.user.save()

            profile.pending_email = ""
            profile.email_otp = ""
            profile.otp_expiry = None
            profile.save()

            message = "✅ Email verified and updated successfully!"
            request.session['profile_updated'] = True
            return redirect("account_info")
        else:
            message = "❌ Invalid or expired OTP."

    return render(request, "user/otp/verify_otp.html", {"message": message})

def confirm_email(request, user_id, new_email):
    user = User.objects.get(id=user_id)
    user.email = new_email
    user.save()
    # messages.success(request, "Email updated successfully.")
    return redirect('edit_profile')
