from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _


class SimplePasswordValidator:
    """
    Relaxed password validator intended for family use:
    - Minimum length (default 6 characters)
    - Optional maximum length (omit for unlimited)
    - At least one uppercase letter (optional)
    - At least one digit (optional)
    """

    def __init__(
        self,
        min_length=6,
        max_length=None,
        require_number=True,
        require_uppercase=True,
    ):
        self.min_length = min_length
        self.max_length = max_length
        self.require_number = require_number
        self.require_uppercase = require_uppercase

    def validate(self, password, user=None):
        errors = []

        if len(password) < self.min_length:
            errors.append(
                _('Parool peab olema vähemalt {min} märki pikk.').format(
                    min=self.min_length,
                )
            )

        if self.max_length is not None and len(password) > self.max_length:
            errors.append(
                _('Parool ei tohi olla pikem kui {max} märki.').format(
                    max=self.max_length,
                )
            )

        if self.require_number and not any(char.isdigit() for char in password):
            errors.append(_('Parool peab sisaldama vähemalt ühte numbrit.'))

        if self.require_uppercase and not any(char.isupper() for char in password):
            errors.append(_('Parool peab sisaldama vähemalt ühte suurtähte.'))

        if errors:
            raise ValidationError(errors)

    def get_help_text(self):
        parts = [
            _('Parool peab olema vähemalt {min} märki pikk.').format(
                min=self.min_length,
            )
        ]
        if self.max_length is not None:
            parts.append(
                _('Parool ei tohi olla pikem kui {max} märki.').format(
                    max=self.max_length,
                )
            )
        if self.require_number:
            parts.append(_('Sisaldama vähemalt ühe numbri.'))
        if self.require_uppercase:
            parts.append(_('Sisaldama vähemalt ühe suurtähe.'))
        return ' '.join(parts)

