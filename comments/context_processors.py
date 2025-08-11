from .models import Notification

def notifications(request):
    """
    Disponibiliza as notificações do usuário logado para todos os templates.
    """
    if request.user.is_authenticated:
        # !!! MUDANÇA IMPORTANTE AQUI !!!
        # Trocamos a busca através de 'request.user.notifications' por uma
        # busca direta e mais explícita no modelo Notification.
        unread_notifications = Notification.objects.filter(user=request.user, is_read=False)
        
        unread_count = unread_notifications.count()
        
        return {
            'unread_notifications': unread_notifications,
            'unread_notification_count': unread_count,
        }
    
    return {}