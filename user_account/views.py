import random
import re
import cloudinary
import cloudinary.uploader
import cloudinary.api

from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache
from django.contrib.auth import update_session_auth_hash
from django.core.mail import send_mail
from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.utils import timezone
from django.conf import settings
from django.core.exceptions import ValidationError


from .forms import ProfileEditForm
from .models import Profile

@login_required(login_url='login')
@never_cache
def account_info(request):
    if not request.session:
        return redirect('login')

    profile, created = Profile.objects.get_or_create(user=request.user)
    success_message = None
    if request.session.get('profile_updated'):
        success_message = "✅ Profile updated successfully!"
        del request.session['profile_updated']
    return render(request, 'user/account.html', { 'profile': profile, 'success_message': success_message})



from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache
from django.contrib.auth import update_session_auth_hash
from django.core.mail import send_mail
from django.utils import timezone
import random
import re
import requests
from django.core.files.base import ContentFile
from .forms import ProfileEditForm
from .models import Profile
import cloudinary.uploader
from django.conf import settings


@login_required(login_url='login')
@never_cache
def edit_profile(request):
    user = request.user
    profile, _ = Profile.objects.get_or_create(user=user)
    has_password = user.has_usable_password()
    error = {}

    if request.method == 'POST':
        # --- NAME & EMAIL ---
        new_name = request.POST.get('name', '').strip()
        new_email = request.POST.get('email', '').strip()
        if new_name:
            if len(new_name) < 3:
                error['name'] = "Name Should contain atleast 3 characters"
            elif not re.match(r'^[A-Za-z\s]+$', new_name):
                error['name'] = "Name should only contain letters and spaces"
            else:
                user.first_name = new_name
        else:
            error['name'] = "Name cannot be empty."

        # --- PROFILE IMAGE ---
        profile_image = request.FILES.get('profile_image')
        if profile_image:
            try:
                upload_result = cloudinary.uploader.upload(profile_image)
                profile.profile_image = upload_result['secure_url']
            except Exception:
                error['profile_image'] = "Uploaded file is invalid or upload failed."
        else:
            # For OAuth users, fetch social image if no profile image exists
            if not profile.profile_image and hasattr(user, 'socialaccount_set'):
                social_accounts = user.socialaccount_set.all()
                if social_accounts.exists():
                    google_account = social_accounts.filter(provider='google').first()
                    if google_account:
                        picture_url = google_account.extra_data.get('picture')
                        if picture_url:
                            try:
                                response = requests.get(picture_url)
                                if response.status_code == 200:
                                    profile.profile_image = picture_url
                            except Exception as e:
                                print("Failed to fetch social profile image:", e)

        # --- EMAIL CHANGE OTP ---
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

        # --- PASSWORD CHANGE ---
        current_password = request.POST.get('current_password', '')
        new_password = request.POST.get('new_password', '')
        confirm_password = request.POST.get('confirm_password', '')

        if new_password:
            if has_password:
                if not user.check_password(current_password):
                    error['cupassword'] = "Current password is incorrect."
            if new_password != confirm_password:
                error['cpassword'] = "New passwords do not match."

            # Strong password validation
            strong_password_pattern = r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@#$!%*?&])[A-Za-z\d@#$!%*?&]{8,}$'
            if not re.match(strong_password_pattern, new_password):
                error['password'] = ("Password must be at least 8 characters long and include one uppercase, "
                                     "one lowercase, one digit, and one special character.")

        # --- SAVE ---
        if not error:
            if new_password:
                user.set_password(new_password)
                update_session_auth_hash(request, user)
            user.save()
            profile.save()
            request.session['profile_updated'] = True
            return redirect('account_info')

    return render(request, 'user/edit_profile.html', {
        'profile': profile,
        'has_password': has_password,
        'error': error,
        'name': user.first_name,
        'email': user.email,
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

            # message = "✅ Email verified and updated successfully!"
            request.session['profile_updated'] = True
            return redirect("account_info")
        # else:
        #     message = "❌ Invalid or expired OTP."

    return render(request, "user/otp/verify_otp.html")

def confirm_email(request, user_id, new_email):
    user = User.objects.get(id=user_id)
    user.email = new_email
    user.save()
    # messages.success(request, "Email updated successfully.")
    return redirect('edit_profile')
