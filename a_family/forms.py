from django import forms
from allauth.account.forms import SignupForm

from .models import User


class FamilySignupForm(SignupForm):
    role = forms.ChoiceField(
        choices=User.ROLE_CHOICES,
        label="Role",
    )

    def save(self, request):
        user = super().save(request)
        role = self.cleaned_data.get("role", User.ROLE_PARENT)
        user.role = role
        user.save()
        return user

