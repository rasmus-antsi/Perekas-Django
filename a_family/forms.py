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
        
        # Get role from POST data to determine email requirement
        role = None
        has_email = None
        if self.data:
            role = self.data.get('role')
            has_email = self.data.get('has_email')
        
        # Username is now visible and required
        if 'username' in self.fields:
            self.fields['username'].required = True
            self.fields['username'].widget = forms.TextInput(attrs={
                'placeholder': 'Sinu kasutajanimi',
            })
            self.fields['username'].label = 'Kasutajanimi'
        
        # Email handling - required for parents, optional for children
        if 'email' in self.fields:
            if role == User.ROLE_CHILD:
                # For children, email is only required if they selected "has_email"
                if has_email == 'yes':
                    self.fields['email'].required = True
                else:
                    self.fields['email'].required = False
                    self.fields['email'].widget = forms.EmailInput(attrs={
                        'placeholder': 'sinu@email.ee',
                        'style': 'display: none;' if has_email != 'yes' else '',
                    })
            else:
                # For parents, email is always required
                self.fields['email'].required = True
                self.fields['email'].widget.attrs.update({
                    'placeholder': 'sinu@email.ee',
                })
        
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
        email = self.cleaned_data.get('email', '')
        role = self.cleaned_data.get('role') or self.data.get('role')
        has_email = self.data.get('has_email')
        
        # Email is required for parents
        if role == User.ROLE_PARENT and not email:
            raise ValidationError('Lapsevanemate kontol peab olema e-posti aadress.')
        
        # For children, email is required only if they selected "has_email"
        if role == User.ROLE_CHILD:
            if has_email == 'yes' and not email:
                raise ValidationError('Palun sisesta oma e-posti aadress.')
            elif has_email == 'no':
                # Children without email - set to None
                return None
        
        # Check if email already exists (if provided)
        if email:
            if User.objects.filter(email=email).exists():
                raise ValidationError('See e-posti aadress on juba kasutuses.')
        
        return email or None
    
    def clean(self):
        cleaned_data = super().clean()
        role = cleaned_data.get('role') or self.data.get('role')
        has_email = self.data.get('has_email')
        
        # For children without email, remove email from cleaned_data entirely
        # This prevents allauth from trying to save it
        if role == User.ROLE_CHILD and has_email == 'no':
            if 'email' in cleaned_data:
                del cleaned_data['email']
            return cleaned_data
        
        # For parents and children with email, validate email is provided
        email = cleaned_data.get('email', '') or None
        
        # Ensure email is provided for parents
        if role == User.ROLE_PARENT and not email:
            self.add_error('email', 'Lapsevanemate kontol peab olema e-posti aadress.')
        
        # For children, ensure email is provided if they selected "has_email"
        if role == User.ROLE_CHILD and has_email == 'yes' and not email:
            self.add_error('email', 'Palun sisesta oma e-posti aadress.')
        
        return cleaned_data

    def clean_username(self):
        username = self.cleaned_data.get('username', '').strip()
        if not username:
            raise ValidationError('Kasutajanimi on kohustuslik.')
        
        # Check if username already exists
        if User.objects.filter(username=username).exists():
            raise ValidationError('See kasutajanimi on juba kasutuses.')
        
        # Validate username format
        if not re.match(r'^[\w.@+-]+$', username):
            raise ValidationError('Kasutajanimi võib sisaldada ainult tähti, numbreid ja märke: . @ + - _')
        
        return username

    def save(self, request):
        # Get role and email info before saving
        role = self.cleaned_data.get("role", User.ROLE_PARENT)
        has_email = self.data.get('has_email')
        
        # For children without email, email should already be removed in clean()
        # But double-check here to be safe
        is_child_without_email = (role == User.ROLE_CHILD and has_email == 'no')
        
        if is_child_without_email:
            # Ensure email is not in cleaned_data
            if 'email' in self.cleaned_data:
                del self.cleaned_data['email']
        
        # Save user through allauth (without email if child without email)
        # The adapter's save_user will handle setting email=None
        user = super().save(request)
        
        # Update user fields
        user.first_name = self.cleaned_data.get('first_name', '')
        user.last_name = self.cleaned_data.get('last_name', '')
        user.birthdate = self.cleaned_data.get('birthdate')
        user.role = role
        
        # For children without email, ensure email is None (adapter should handle this, but double-check)
        if is_child_without_email:
            user.email = None
        
        # Save the user with all updates
        try:
            user.save(update_fields=['first_name', 'last_name', 'birthdate', 'role', 'email'])
        except Exception as e:
            # If we get an IntegrityError about email being NOT NULL, the migration hasn't been run
            if 'NOT NULL constraint failed: auth_user.email' in str(e) or ('email' in str(e).lower() and 'NOT NULL' in str(e)):
                from django.core.exceptions import ValidationError
                raise ValidationError(
                    'Andmebaasi migratsioon pole veel rakendatud. Palun kontakteeru toega või oota mõni hetk.'
                ) from e
            raise
        
        # Delete any EmailAddress records that allauth might have created
        if is_child_without_email:
            try:
                from allauth.account.models import EmailAddress
                EmailAddress.objects.filter(user=user).delete()
            except Exception:
                pass  # Ignore errors if EmailAddress doesn't exist or is already deleted
        
        return user


class CreateFamilyForm(forms.Form):
    name = forms.CharField(
        max_length=255,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'auth-field-minimal',
            'placeholder': 'Sisesta pere nimi',
            'autofocus': True,
        }),
        label='Pere nimi',
    )

    def clean_name(self):
        name = self.cleaned_data.get('name', '').strip()
        if not name:
            raise ValidationError('Pere nimi on kohustuslik.')
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

