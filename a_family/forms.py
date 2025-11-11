from django import forms
from allauth.account.forms import SignupForm

from .models import UserProfile


class FamilySignupForm(SignupForm):
    role = forms.ChoiceField(
        choices=UserProfile.ROLE_CHOICES,
        label="Role",
        widget=forms.Select(attrs={"class": "auth-select"}),
    )

    def save(self, request):
        user = super().save(request)
        role = self.cleaned_data.get("role", UserProfile.ROLE_PARENT)
        UserProfile.objects.update_or_create(
            user=user,
            defaults={"role": role},
        )
        return user

