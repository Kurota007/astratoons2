# manga/validator.py
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from decimal import Decimal, InvalidOperation

def validate_rating_range(value):
    """Valida se a nota está entre 0.0 e 10.0 (inclusive)."""
    if value is not None:
        try:
            decimal_value = Decimal(str(value))
        except InvalidOperation:
             raise ValidationError(_('Formato inválido para a nota.'))
        if not (Decimal('0.0') <= decimal_value <= Decimal('10.0')):
            raise ValidationError(
                _('A nota deve estar entre 0.0 e 10.0. Você inseriu %(value)s.'),
                params={'value': decimal_value},
            )