# core/api_views.py
import json
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from django.db.models import Count, Q

from wagtail.models import Page
from .models import ReactionType, UserReaction

@login_required
@require_POST
def toggle_reaction(request):
    try:
        data = json.loads(request.body)
        page_id = data.get('page_id')
        reaction_type_id = data.get('reaction_type_id') # Este valor é uma string, ex: 'surprised'
        if not all([page_id, reaction_type_id]):
            raise KeyError("Faltando page_id ou reaction_type_id.")
    except (json.JSONDecodeError, KeyError) as e:
        return JsonResponse({'status': 'error', 'message': f'Dados inválidos: {e}'}, status=400)

    page = get_object_or_404(Page, pk=page_id)
    
    # --- CORREÇÃO AQUI ---
    # Mudamos de volta para buscar pelo campo de texto 'type_id' em vez do 'pk' numérico.
    # Isso resolve o erro 'ValueError'.
    # Assumindo que seu modelo ReactionType tem um campo CharField/SlugField chamado 'type_id'.
    reaction_type = get_object_or_404(ReactionType, type_id=reaction_type_id)
    # ---------------------
    
    existing_reaction = UserReaction.objects.filter(user=request.user, page=page).first()
    
    user_reacted_with = None

    if existing_reaction:
        if existing_reaction.reaction_type == reaction_type:
            existing_reaction.delete()
        else:
            existing_reaction.reaction_type = reaction_type
            existing_reaction.save()
            user_reacted_with = reaction_type.type_id # Usamos o 'type_id' para a resposta
    else:
        UserReaction.objects.create(user=request.user, page=page, reaction_type=reaction_type)
        user_reacted_with = reaction_type.type_id # Usamos o 'type_id' para a resposta
        
    # Pega as contagens atualizadas usando o 'type_id' para consistência
    counts = ReactionType.objects.annotate(
        count=Count('user_reactions', filter=Q(user_reactions__page=page))
    ).values('type_id', 'count')
    
    return JsonResponse({
        'status': 'ok',
        'counts': list(counts),
        'user_reacted_with': user_reacted_with,
    })