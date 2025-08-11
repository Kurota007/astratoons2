# Em comments/signals.py

import logging
from django.db import models
from django.dispatch import receiver
from .models import Comment, Notification # MUDANÇA: Adicionado 'Notification'

# Configura um logger para registrar eventos importantes, uma prática melhor que 'print'
logger = logging.getLogger(__name__)

@receiver(models.signals.pre_save, sender=Comment)
def deletar_imagem_antiga_ao_atualizar(sender, instance, **kwargs):
    """
    Dispara ANTES de um comentário ser salvo.
    Verifica se a imagem foi alterada ou removida e, em caso afirmativo,
    deleta o arquivo de imagem antigo do disco.
    """
    if not instance.pk:
        return

    try:
        comentario_antigo = Comment.objects.get(pk=instance.pk)
    except Comment.DoesNotExist:
        return

    if comentario_antigo.image:
        if comentario_antigo.image != instance.image:
            try:
                comentario_antigo.image.delete(save=False)
                logger.info(f"Imagem antiga '{comentario_antigo.image.name}' deletada com sucesso na atualização.")
            except Exception as e:
                logger.error(f"FALHA ao deletar a imagem antiga '{comentario_antigo.image.name}'. Erro: {e}")

@receiver(models.signals.post_delete, sender=Comment)
def deletar_imagem_ao_excluir_comentario(sender, instance, **kwargs):
    """
    Dispara DEPOIS que um comentário é deletado do banco de dados.
    Deleta o arquivo de imagem correspondente do disco.
    """
    if instance.image:
        try:
            instance.image.delete(save=False)
            logger.info(f"Imagem '{instance.image.name}' do comentário deletado com sucesso.")
        except Exception as e:
            logger.error(f"FALHA ao deletar a imagem '{instance.image.name}'. Erro: {e}")

# =================================================================== #
#          NOVA FUNÇÃO: CRIAÇÃO DE NOTIFICAÇÕES                     #
# =================================================================== #

@receiver(models.signals.post_save, sender=Comment)
def create_reply_notification(sender, instance, created, **kwargs):
    """
    Dispara DEPOIS que um comentário é salvo.
    Cria uma notificação se o comentário for uma nova resposta.
    """
    # Roda apenas na criação de um NOVO comentário que seja uma RESPOSTA
    if created and instance.parent:
        recipient = instance.parent.user
        actor = instance.user

        # Não cria notificação se o usuário estiver respondendo a si mesmo
        if recipient != actor:
            Notification.objects.create(
                user=recipient,      # O autor do comentário original
                comment=instance     # A nova resposta que foi criada
            )
            logger.info(f"Notificação criada para {recipient.username} sobre resposta de {actor.username}.")