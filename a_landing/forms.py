from django import forms
from .models import ReviewFormSubmission


class ReviewForm(forms.ModelForm):
    """Form for collecting feedback from users who created accounts but didn't use the app."""
    
    class Meta:
        model = ReviewFormSubmission
        fields = [
            'email',
            'name',
            'why_created_account',
            'added_family_members',
            'created_tasks',
            'created_rewards',
            'what_prevented_usage',
            'feedback',
        ]
        widgets = {
            'email': forms.EmailInput(attrs={
                'class': 'review-form-input',
                'placeholder': 'sinu@email.ee',
                'required': True,
            }),
            'name': forms.TextInput(attrs={
                'class': 'review-form-input',
                'placeholder': 'Sinu nimi (valikuline)',
            }),
            'why_created_account': forms.Textarea(attrs={
                'class': 'review-form-textarea',
                'placeholder': 'Miks lõid konto?',
                'rows': 4,
                'required': True,
            }),
            'added_family_members': forms.CheckboxInput(attrs={
                'class': 'review-form-checkbox',
            }),
            'created_tasks': forms.CheckboxInput(attrs={
                'class': 'review-form-checkbox',
            }),
            'created_rewards': forms.CheckboxInput(attrs={
                'class': 'review-form-checkbox',
            }),
            'what_prevented_usage': forms.Textarea(attrs={
                'class': 'review-form-textarea',
                'placeholder': 'Mis takistas sind rakendust kasutamast?',
                'rows': 4,
            }),
            'feedback': forms.Textarea(attrs={
                'class': 'review-form-textarea',
                'placeholder': 'Kas on veel midagi, mida soovid jagada?',
                'rows': 4,
            }),
        }
        labels = {
            'email': 'E-posti aadress',
            'name': 'Nimi',
            'why_created_account': 'Konto loomise põhjus',
            'added_family_members': 'Kas lisasid pereliikmeid?',
            'created_tasks': 'Kas lisasid ülesandeid?',
            'created_rewards': 'Kas lisasid preemiaid?',
            'what_prevented_usage': 'Mis takistas sind rakendust kasutamast?',
            'feedback': 'Tagasiside või ettepanekud',
        }

