from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.http import HttpResponseBadRequest, JsonResponse
from django.urls import reverse

from wagtail.models import Page
from manga.models import MangaChapterPage

from .forms import CommentForm
from .models import Comment, Notification, CommentVote

@login_required
@require_POST
def post_comment(request):
    form = CommentForm(request.POST, request.FILES)
    if form.is_valid():
        page_id = request.POST.get('page_id')
        if not page_id: return HttpResponseBadRequest("ID da página não encontrado.")
        try: page = Page.objects.get(id=page_id).specific
        except Page.DoesNotExist: return HttpResponseBadRequest("Página não encontrada.")
        new_comment = form.save(commit=False)
        new_comment.page = page
        new_comment.user = request.user
        parent_id = request.POST.get('parent_id')
        if parent_id:
            try: new_comment.parent = Comment.objects.get(id=parent_id)
            except Comment.DoesNotExist: return HttpResponseBadRequest("Comentário pai não encontrado.")
        text = form.cleaned_data.get('content', '')
        use_bold = form.cleaned_data.get('use_bold', False)
        use_italic = form.cleaned_data.get('use_italic', False)
        if use_italic: text = f"*{text}*"
        if use_bold: text = f"**{text}**"
        new_comment.content = text
        new_comment.save()
        messages.success(request, 'Seu comentário foi adicionado!')
        anchor = f'#comment-{new_comment.id}'
        redirect_url = page.get_url()
        if isinstance(page, MangaChapterPage):
            try:
                manga = page.get_parent().specific
                redirect_url = reverse('manga:chapter_reader', kwargs={'manga_slug': manga.slug, 'chapter_slug': page.slug})
            except Exception: pass
        return redirect(redirect_url + anchor)
    else:
        error_message = "Houve um erro no seu comentário. "
        if form.errors:
            first_error_key = next(iter(form.errors))
            error_message += form.errors[first_error_key][0]
        messages.error(request, error_message)
        page_id = request.POST.get('page_id')
        redirect_url = request.META.get('HTTP_REFERER', '/')
        if page_id:
            try:
                page = Page.objects.get(id=page_id).specific
                return redirect(page.get_url() + '#comments')
            except Page.DoesNotExist: return redirect(redirect_url)
        return redirect(redirect_url)


@login_required
@require_POST
def delete_comment(request, comment_id):
    comment = get_object_or_404(Comment, id=comment_id)
    page = comment.page.specific
    if request.user == comment.user or request.user.is_staff:
        comment.delete()
        messages.success(request, "Comentário excluído com sucesso.")
    else:
        messages.error(request, "Você não tem permissão para excluir este comentário.")
    redirect_url = page.get_url()
    if isinstance(page, MangaChapterPage):
        try:
            manga = page.get_parent().specific
            redirect_url = reverse('manga:chapter_reader', kwargs={'manga_slug': manga.slug, 'chapter_slug': page.slug})
        except Exception: pass
    return redirect(redirect_url + '#comments')


@login_required
def notification_list(request):
    notifications = Notification.objects.filter(recipient=request.user).order_by('-created_at')
    return render(request, 'comments/notifications.html', {'notifications': notifications})


@login_required
def mark_notification_as_read(request, notification_id):
    notification = get_object_or_404(Notification, id=notification_id, recipient=request.user)
    notification.is_read = True
    notification.save()
    target_comment = notification.comment
    page = target_comment.page.specific
    anchor = f'#comment-{target_comment.id}'
    redirect_url = page.get_url()
    if isinstance(page, MangaChapterPage):
        try:
            manga = page.get_parent().specific
            redirect_url = reverse('manga:chapter_reader', kwargs={'manga_slug': manga.slug, 'chapter_slug': page.slug})
        except Exception: pass
    return redirect(redirect_url + anchor)


@login_required
@require_POST
def vote_comment(request):
    comment_id = request.POST.get('comment_id')
    vote_type = request.POST.get('vote_type')

    if not comment_id or not vote_type:
        return JsonResponse({'status': 'error', 'message': 'Dados inválidos.'}, status=400)

    comment = get_object_or_404(Comment, id=comment_id)
    
    vote_value = CommentVote.LIKE if vote_type == 'like' else CommentVote.DISLIKE

    try:
        existing_vote = CommentVote.objects.get(comment=comment, user=request.user)
        if existing_vote.vote == vote_value:
            existing_vote.delete()
            action = 'vote_removed'
        else:
            existing_vote.vote = vote_value
            existing_vote.save()
            action = 'vote_changed'
    except CommentVote.DoesNotExist:
        CommentVote.objects.create(comment=comment, user=request.user, vote=vote_value)
        action = 'vote_created'
    
    return JsonResponse({
        'status': 'ok',
        'action': action,
        'likes': comment.likes,
        'dislikes': comment.dislikes,
    })

@login_required
@require_POST
def mark_all_as_read(request):
    if request.user.is_authenticated:
        request.user.notifications.filter(is_read=False).update(is_read=True)
    return JsonResponse({'status': 'ok'})