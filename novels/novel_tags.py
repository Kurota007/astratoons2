from django import template
from django.template.defaultfilters import stringfilter

register = template.Library()

@register.filter
@stringfilter
def replace_string(value, arg):
    """
    Replaces all occurrences of arg in value.
    Usage: {{ my_string|replace_string:"old,new" }}
    arg should be a string with old and new values separated by a comma.
    """
    if ',' not in arg:
        return value # Or raise an error, or return as is
    old, new = arg.split(',', 1)
    return value.replace(old, new)