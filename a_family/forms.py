from datetime import date
import re

from django import forms
from django.core.exceptions import ValidationError
from allauth.account.forms import SignupForm

from .models import User, Family


class FamilySignupForm(SignupForm):
    first_name = forms.CharField(
        max_length=150,
        required=True,
        label="Eesnimi",
        widget=forms.TextInput(attrs={
            'placeholder': 'Sinu eesnimi',
            'autofocus': True,
        })
    )
    last_name = forms.CharField(
        max_length=150,
        required=True,
        label="Perekonnanimi",
        widget=forms.TextInput(attrs={
            'placeholder': 'Sinu perekonnanimi',
        })
    )
    birthdate = forms.DateField(
        required=True,
        label="Sünniaeg",
        widget=forms.DateInput(attrs={
            'type': 'date',
            'max': date.today().isoformat(),
        })
    )
    role = forms.ChoiceField(
        choices=User.ROLE_CHOICES,
        label="Roll",
        widget=forms.RadioSelect(attrs={
            'class': 'role-radio',
        })
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make email required and set placeholder
        if 'email' in self.fields:
            self.fields['email'].widget.attrs.update({
                'placeholder': 'sinu@email.ee',
            })
        # Hide username field - we'll auto-generate it
        if 'username' in self.fields:
            self.fields['username'].required = False
            self.fields['username'].widget = forms.HiddenInput()
        # Update password field placeholders
        if 'password1' in self.fields:
            self.fields['password1'].widget.attrs.update({
                'placeholder': 'Vähemalt 8 märki, 1 number ja suurtäht',
            })
        if 'password2' in self.fields:
            self.fields['password2'].widget.attrs.update({
                'placeholder': 'Korda parooli',
            })

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email:
            # Check if email already exists
            if User.objects.filter(email=email).exists():
                raise ValidationError('See e-posti aadress on juba kasutuses.')
        return email

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if username:
            return username

        email = self.cleaned_data.get('email') or self.data.get('email', '')
        base_username = email.split('@')[0] if email else 'perekas'
        base_username = re.sub(r'[^\w.@+-]', '', base_username.lower()) or 'perekas'

        username_candidate = base_username
        counter = 1
        while User.objects.filter(username=username_candidate).exists():
            username_candidate = f"{base_username}{counter}"
            counter += 1
        return username_candidate

    def save(self, request):
        user = super().save(request)
        user.first_name = self.cleaned_data.get('first_name', '')
        user.last_name = self.cleaned_data.get('last_name', '')
        user.birthdate = self.cleaned_data.get('birthdate')
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

