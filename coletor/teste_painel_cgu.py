"""Mostra os arquivos da base do painel da CGU (Fase 1, tarefa 6).

Script de exploração: descobre o link e o formato do arquivo
antes de escrever o coletor do painel.
"""

import portal

# Id da base "painel-de-monitoramento-de-dados-abertos" (tirado da listagem)
ID_PAINEL = "eda85b50-9d7a-4b01-aca4-bef32b3b8d9a"

with portal.criar_cliente() as cliente:
    base = portal.buscar(cliente, f"{portal.URL_CONJUNTOS}/{ID_PAINEL}").json()

# Um arquivo por linha: título | formato | última atualização | link
for recurso in base["recursos"]:
    print(recurso["titulo"], "|", recurso["formato"], "|", recurso["dataUltimaAtualizacaoArquivo"], "|", recurso["link"])
