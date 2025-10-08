from allauth.account.adapter import DefaultAccountAdapter
from django.contrib import messages
from django.shortcuts import redirect

class CustomAccountAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request):
        # You can control who can sign up here if you want
        return True

    def respond_user_inactive(self, request, user):
        # Add message for inactive users
        messages.error(request, "Your account is inactive. Please contact support.")
        return redirect('account_login')  # Redirect to your login page
