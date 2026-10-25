# Validação (24/10/2026)

Objetivo: provar com dados reais que o problema existe antes de construir o produto.

Os scripts usados estão em [`validacao/scripts/`](../validacao/scripts) e os resultados em [`validacao/resultados/`](../validacao/resultados). Eles são **ferramentas de pesquisa** escritas durante a validação, não o código do produto: o motor do Clock-in será escrito do zero, seguindo o [roadmap](ROADMAP.md).

## Parte A: censo do portal

**Método:** percorrer a listagem pública do dados.gov.br (`/api/publico/conjuntos-dados/buscar`, filtro `dadosAbertos=true`), 100 bases por página, com 1,5 s de pausa entre páginas. Foram lidas **todas as 19.602 bases abertas**. Resultado compacto em [`censo-2026-10-24.csv`](../validacao/resultados/censo-2026-10-24.csv), que serve de linha de base histórica.

**Resultados:**

| Indicador | Bases | % |
|---|---|---|
| Portal diz "atualizado" (`conjuntoDadosEstaAtualizado = true`) | 319 | 2% |
| Portal **não** diz "atualizado" | 19.283 | 98% |
| Sem nenhuma data de atualização dos dados | 5.709 | 29% |
| Última atualização dos dados há até 1 mês | 1.350 | 7% |
| Entre 1 e 6 meses | 1.920 | 10% |
| Entre 6 e 12 meses | 1.186 | 6% |
| Entre 1 e 2 anos | 1.460 | 7% |
| Entre 2 e 5 anos | 5.416 | 28% |
| Mais de 5 anos | 2.427 | 12% |
| **Última atualização há mais de 1 ano** | **9.303** | **47%** |
| Sem nenhum recurso (arquivo ou link) | 19 | 0,1% |

**Achado sobre os órgãos:** o campo `organizationTitle` da listagem atribui **18.636 bases (95%) à CGU**, inclusive bases claramente de outros órgãos (UFAM, ANS). O portal agrega por quem fez a coleta (harvest), não por quem publica. Para o ranking por órgão, o Clock-in precisa descobrir o **publicador real** (responsável técnico, e-mail, domínio dos links, órgão no painel da CGU). Tarefa registrada na Fase 1 do roadmap.

## Parte B: prova real numa amostra

**Método:** sorteio reprodutível (semente 42) de 120 bases do censo. Para cada uma: buscar o detalhe no portal (`/api/publico/conjuntos-dados/{slug}`) e testar até 4 links de arquivos com `HEAD` (ou `GET` com `Range` quando o servidor recusa `HEAD`), timeout de 20 s, registrando status HTTP, tipo, tamanho e `Last-Modified`. Uma base falhou na leitura do detalhe: **119 analisadas, 314 links testados**. Resultado bruto em [`prova-amostra.json`](../validacao/resultados/prova-amostra.json).

### O selo do portal

| Status mostrado pelo portal | Bases | % |
|---|---|---|
| Atualização não verificável (`INDISPONIVEL`) | 97 | 82% |
| Atualizado | 18 | 15% |
| Desatualizado | 4 | 3% |

Das **18 bases que o portal marca como "Atualizado"**:
- 4 estavam com **todos os links quebrados**;
- 2 estavam **paradas** segundo a data do servidor: "Cursos da Pós-Graduação Stricto" (anual, 578 dias) e "Relatório de Ouvidoria" (semestral, 1.327 dias).

Ou seja, **6 de 18 (33%) vereditos "atualizado" estavam errados**.

### Saúde dos links (314 links)

| Resultado | Links | % |
|---|---|---|
| OK (2xx) | 227 | 72% |
| 502 Bad Gateway | 34 | 11% |
| Erro de conexão, DNS ou SSL | 14 | 4% |
| 520 (erro de origem via proxy) | 12 | 4% |
| 404 Não encontrado | 9 | 3% |
| Timeout | 6 | 2% |
| 503 Indisponível | 5 | 2% |
| 403, 400, 401, 500 | 7 | 2% |
| **Total com falha** | **87** | **28%** |

Por base: **16 de 119 (13%) com todos os links quebrados** e **40 (34%) com pelo menos um**.

### Periodicidade

| Situação | Bases |
|---|---|
| Não declara periodicidade comparável ("-", sob demanda, outras) | 82 (69%) |
| Declara, mas a data real não é verificável no servidor | 27 |
| Declara, data verificável e **em dia** | 7 |
| Declara, data verificável e **atrasada** | 3 |

A periodicidade vem escrita de formas diferentes ("Anual", "ANUAL", "quadrimestral"): é preciso normalizar.

## Conclusões

1. **O problema é real e grande:** quase metade das bases não muda há mais de um ano, 28% dos links falham e o selo do portal é quase sempre "não verificável".
2. **O selo do portal não é confiável:** um terço dos "atualizado" estava errado. Isso justifica medir pelo conteúdo.
3. **Mudança no desenho:** 69% das bases não declaram periodicidade. O Clock-in precisa **inferir o ritmo** de cada base pelo histórico de mudanças do conteúdo (inspiração: artigo da WU Viena), além de usar a periodicidade declarada quando ela existe.
4. **`Last-Modified` não basta:** em 27 bases com periodicidade, o servidor não informava data. Confirmar pelo hash do conteúdo e pelas datas dentro do arquivo.
5. **Órgão:** o ranking por órgão exige descobrir o publicador real; o campo da listagem atribui quase tudo à CGU.

## Ressalvas

- **Foto de um dia só.** Erros 502, 503 e 520 podem ser temporários. O motor deve testar várias vezes antes de declarar "fora do ar" (por exemplo, 3 falhas seguidas em dias diferentes).
- **Amostra de 119 bases.** Boa para mostrar a dimensão do problema, não para afirmar percentuais exatos do portal inteiro. A Fase 2 do roadmap mede todos os links.
- **`Last-Modified`** é informado pelo servidor e pode estar errado (ver lição do stavangerparking em [PESQUISA.md](PESQUISA.md)).
- **"Mais de 1 ano sem atualização" não é sinônimo de "atrasada":** bases anuais ou históricas podem estar corretas. O status final depende do prazo esperado de cada base.
- A API do portal não é documentada oficialmente e pode mudar (ver [API_DADOS_GOV.md](API_DADOS_GOV.md)).

## Próximo uso destes dados

- Linha de base para comparar a evolução quando o motor estiver rodando.
- Material para o primeiro post no LinkedIn (com as ressalvas acima).
