# core/views.py

from django.shortcuts import render
from django.contrib.auth.decorators import user_passes_test
import shutil  # Importe a biblioteca para uso de disco
import os      # Importe para verificações de caminho

def is_staff(user):
    return user.is_staff

@user_passes_test(is_staff)
def disk_usage_view(request):
    path_to_check = '/'  # O caminho que queremos analisar, ex: a raiz do disco
    context = {
        'header_title': 'Uso de Disco',
        'header_icon': 'cogs',  # Um ícone de engrenagem para a ferramenta
        'path_checked': path_to_check,
        'total_gb': None,
        'used_gb': None,
        'free_gb': None,
        'percent_used': None,
        'error_message': None,
    }

    try:
        if os.path.exists(path_to_check):
            # shutil.disk_usage retorna os valores em BYTES
            total_bytes, used_bytes, free_bytes = shutil.disk_usage(path_to_check)

            # --- Conversão para Gigabytes (GB) ---
            # 1 GB = 1024*1024*1024 bytes
            bytes_in_gb = 1024 ** 3
            
            context['total_gb'] = round(total_bytes / bytes_in_gb, 2)
            context['used_gb'] = round(used_bytes / bytes_in_gb, 2)
            context['free_gb'] = round(free_bytes / bytes_in_gb, 2)

            # --- Cálculo da Porcentagem ---
            if total_bytes > 0:
                context['percent_used'] = round((used_bytes / total_bytes) * 100, 2)
            else:
                context['percent_used'] = 0
        else:
            context['error_message'] = f"O caminho especificado '{path_to_check}' não existe."

    except Exception as e:
        # Captura qualquer outro erro que possa ocorrer (ex: permissões)
        context['error_message'] = f"Ocorreu um erro inesperado: {e}"

    return render(request, 'core/disk_usage.html', context)