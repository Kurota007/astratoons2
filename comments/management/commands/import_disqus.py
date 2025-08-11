# comments/management/commands/import_disqus.py
import xml.etree.ElementTree as ET
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils.dateparse import parse_datetime
from urllib.parse import urlparse

from wagtail.models import Page
from comments.models import Comment

# Pega o modelo de usuário customizado do seu projeto
User = get_user_model()

class Command(BaseCommand):
    help = 'Importa comentários de um arquivo XML de exportação do Disqus.'

    def add_arguments(self, parser):
        parser.add_argument('xml_file', type=str, help='O caminho para o arquivo XML do Disqus.')

    def handle(self, *args, **options):
        xml_file = options['xml_file']
        self.stdout.write(self.style.SUCCESS(f"Iniciando importação do arquivo: {xml_file}"))

        # --- PARTE 1: Parsear o XML ---
        try:
            tree = ET.parse(xml_file)
            root = tree.getroot()
        except ET.ParseError as e:
            self.stderr.write(self.style.ERROR(f"Erro ao ler o arquivo XML: {e}"))
            return
        except FileNotFoundError:
            self.stderr.write(self.style.ERROR(f"Arquivo não encontrado: {xml_file}"))
            return
        
        # Namespace usado pelo Disqus no XML
        NS = {'dsq': 'http://disqus.com/DTD/2.0'}

        # --- PARTE 2: Mapear Threads (Páginas) ---
        # O Disqus associa comentários a uma "thread", que é identificada por uma URL.
        threads_map = {}
        self.stdout.write("Mapeando threads do Disqus para páginas do Wagtail...")
        for thread_node in root.findall('dsq:thread', NS):
            thread_id = thread_node.get('{http://disqus.com/disqus.com/DTD/1.0}id')
            link = thread_node.find('dsq:link', NS).text
            
            # Tenta encontrar a página correspondente no Wagtail a partir da URL
            try:
                path = urlparse(link).path
                # O Wagtail guarda as URLs das páginas em 'url_path'. 
                # Precisamos do path exato, ex: /mago-do-infinito/capitulo-01/
                page = Page.objects.get(url_path__endswith=path).specific
                threads_map[thread_id] = page
                self.stdout.write(f"  -> Encontrado: '{link}' -> Página '{page.title}'")
            except Page.DoesNotExist:
                self.stdout.write(self.style.WARNING(f"  -> AVISO: Nenhuma página encontrada para a URL: {link}"))
            except Page.MultipleObjectsReturned:
                self.stdout.write(self.style.WARNING(f"  -> AVISO: Múltiplas páginas encontradas para a URL: {link}. Usando a primeira."))
                page = Page.objects.filter(url_path__endswith=path).first().specific
                threads_map[thread_id] = page

        # --- PARTE 3: Mapear Autores (Usuários) ---
        # Tenta encontrar os usuários no seu banco de dados pelo e-mail ou nome de usuário.
        # Se não encontrar, cria um usuário "fantasma" ou pula o comentário.
        
        # --- PARTE 4: Importar Comentários ---
        # Vamos precisar de um mapa para conectar as respostas aos comentários pais.
        disqus_id_to_local_comment = {}
        
        # Limpa comentários existentes para evitar duplicatas ao rodar de novo
        self.stdout.write(self.style.WARNING("Limpando todos os comentários existentes..."))
        Comment.objects.all().delete()

        self.stdout.write("Iniciando importação dos comentários...")
        comments_to_create = []
        
        # O XML do Disqus geralmente lista os comentários em ordem cronológica,
        # o que ajuda a garantir que o pai de uma resposta já tenha sido processado.
        for post_node in root.findall('dsq:post', NS):
            thread_id = post_node.find('dsq:thread', NS).get('{http://disqus.com/disqus.com/DTD/1.0}id')

            if thread_id not in threads_map:
                continue  # Pula comentários de páginas que não encontramos

            page = threads_map[thread_id]
            disqus_id = post_node.get('{http://disqus.com/disqus.com/DTD/1.0}id')
            author_email = post_node.find('dsq:author/dsq:email', NS).text
            author_username = post_node.find('dsq:author/dsq:name', NS).text
            message = post_node.find('dsq:message', NS).text
            created_at = parse_datetime(post_node.find('dsq:createdAt', NS).text)

            # Encontra o usuário no seu banco.
            user = User.objects.filter(email__iexact=author_email).first()
            if not user:
                user = User.objects.filter(username__iexact=author_username).first()

            if not user:
                self.stdout.write(self.style.WARNING(f"  -> AVISO: Usuário '{author_username}' ({author_email}) não encontrado. Pulando comentário."))
                continue

            parent_comment = None
            parent_node = post_node.find('dsq:parent', NS)
            if parent_node is not None:
                parent_disqus_id = parent_node.get('{http://disqus.com/disqus.com/DTD/1.0}id')
                if parent_disqus_id in disqus_id_to_local_comment:
                    parent_comment = disqus_id_to_local_comment[parent_disqus_id]
            
           
            comment = Comment(
                page=page,
                user=user,
                parent=parent_comment,
                content=message,
                created_at=created_at # Força a data de criação original
            )
            comments_to_create.append(comment)

        self.stdout.write(f"Criando {len(comments_to_create)} comentários no banco de dados...")
        created_comments = Comment.objects.bulk_create(comments_to_create)


        self.stdout.write(self.style.SUCCESS(f"Importação concluída! {len(created_comments)} comentários foram criados."))