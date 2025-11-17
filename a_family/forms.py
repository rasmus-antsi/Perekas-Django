from django import forms
from django.core.exceptions import ValidationError
from allauth.account.forms import SignupForm

from .models import User, Family


class FamilySignupForm(SignupForm):
    role = forms.ChoiceField(
        choices=User.ROLE_CHOICES,
        label="Roll",
    )

    def save(self, request):
        user = super().save(request)
        role = self.cleaned_data.get("role", User.ROLE_PARENT)
        user.role = role
        user.save()
        return user


class CreateFamilyForm(forms.Form):
    name = forms.CharField(
        max_length=255,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'auth-field-minimal',
            'placeholder': 'Sisesta perekonna nimi',
            'autofocus': True,
        }),
        label='Perekonna nimi',
    )

    def clean_name(self):
        name = self.cleaned_data.get('name', '').strip()
        if not name:
            raise ValidationError('Perekonna nimi on kohustuslik.')
        return name


class JoinFamilyForm(forms.Form):
    join_code = forms.CharField(
        max_length=8,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'auth-field-minimal',
            'placeholder': 'Sisesta 8-kohaline kood',
            'autofocus': True,
            'style': 'text-transform: uppercase;',
            'size': '8',
        }),
        label='Perekonna kood',
    )

    def clean_join_code(self):
        join_code = self.cleaned_data.get('join_code', '').strip().upper()
        if not join_code:
            raise ValidationError('Perekonna kood on kohustuslik.')
        if len(join_code) != 8:
            raise ValidationError('Perekonna kood peab olema täpselt 8 märki.')
        if not Family.objects.filter(join_code=join_code).exists():
            raise ValidationError('Vale pere kood. Palun kontrolli ja proovi uuesti.')
        return join_code

