# core/templatetags/reaction_tags.py
from django import template
from django.db.models import Count
from django.db import models 
from core.models import ReactionType, UserReaction

register = template.Library()

@register.inclusion_tag('core/tags/reaction_section.html', takes_context=True)
def reaction_section(context, page):
    request = context['request']
    
    # Pega todos os tipos de reações disponíveis, ordenados
    reaction_types = ReactionType.objects.all()

    # Anota cada tipo de reação com a contagem de reações para a página atual
    reaction_types_with_counts = reaction_types.annotate(
        count=Count('user_reactions', filter=models.Q(user_reactions__page=page))
    )
    
    user_reaction = None
    if request.user.is_authenticated:
        # Verifica se o usuário atual já reagiu a esta página
        user_reaction = UserReaction.objects.filter(user=request.user, page=page).first()

    return {
        'page': page,
        'request': request,
        'reaction_types_with_counts': reaction_types_with_counts,
        'user_reaction_type_id': user_reaction.reaction_type.type_id if user_reaction else None,
    }