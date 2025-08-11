from django import template
from ..forms import CommentForm
from ..models import Comment, Notification, CommentVote

register = template.Library()

@register.inclusion_tag('comments/comment_section.html', takes_context=True)
def comment_section(context, page):
    request = context['request']
    user = request.user

    parent_comments_qs = Comment.objects.filter(
        page=page, parent=None, is_approved=True
    ).select_related('user').prefetch_related(
        'user__profile__active_badges', 
        'replies'
    )
    
    parent_comments_list = list(parent_comments_qs)

    if user.is_authenticated:
        unread_notifications = Notification.objects.unread_for_user(user).select_related('comment__user__profile')
        unread_notification_count = unread_notifications.count()
    else:
        unread_notifications = []
        unread_notification_count = 0

    return {
        'page': page,
        'comments': parent_comments_list,
        'comment_count': len(parent_comments_list),
        'form': CommentForm(),
        'request': request,
        'user': user,
        'unread_notifications': unread_notifications,
        'unread_notification_count': unread_notification_count,
    }

@register.simple_tag
def user_vote_status(comment, user):
    if not user.is_authenticated:
        return None
    try:
        vote = CommentVote.objects.get(comment=comment, user=user)
        return 'like' if vote.vote == CommentVote.LIKE else 'dislike'
    except CommentVote.DoesNotExist:
        return None

@register.filter(name='get_username_part')
def get_username_part(value):
    if isinstance(value, str) and '@' in value:
        return value.split('@')[0]
    return value