# A ideia

## Por que este projeto existe

O Clock-in nasceu de uma pergunta:

> Qual projeto posso criar que impacte o dia a dia de quem trabalha com dados e o mercado de dados? Algo que ninguém tenha feito ainda, gratuito, útil e que faça diferença de verdade.

Dessa pergunta saem os critérios que toda decisão do projeto precisa respeitar:

| Critério | O que significa na prática |
|---|---|
| Inédito | Fazer o que ninguém faz: medir o conteúdo real, avisar quem depende da base e mostrar a evolução por órgão (ver [PESQUISA.md](PESQUISA.md)) |
| Útil no dia a dia | Entrar na rotina de quem trabalha com dados, não ser só um relatório para ler uma vez |
| Gratuito | Custo zero para quem constrói e para quem usa |
| Impacto no mercado | Tornar o problema visível e criar pressão para que os dados públicos melhorem |

## Em uma frase

Um monitor público e contínuo que diz, para cada base de dados aberta do governo brasileiro, se ela ainda está viva: link funcionando, conteúdo atualizado no prazo e formato estável.

## Por que "Clock-in"

Cada base tem um horário: a periodicidade com que deveria ser atualizada. Se não atualizou no prazo, **não bateu o ponto**. A metáfora rende comunicação simples: "1 em cada 3 bases do governo não bateu o ponto este mês".

Disponibilidade do nome (24/10/2026): `clock-in` livre no PyPI. `clockin` (sem hífen) já existe no PyPI e a palavra é muito usada por apps de ponto de funcionário, mas nenhum projeto de dados usa o nome. Em posts e buscas, escrever junto "dados abertos". Falta checar domínio e registro no INPI.

## Para quem

| Público | Dor | O que o Clock-in entrega |
|---|---|---|
| Engenheiros de dados e empresas que ingerem dados públicos | Pipeline quebra quando a base muda ou para | Alerta antes de quebrar; API para checar o status antes de rodar |
| Jornalistas de dados | Não sabem se o dado está atual antes de publicar | Página da base com status e linha do tempo |
| Pesquisadores | Dados somem ou mudam no meio da pesquisa | Histórico de mudanças e de formato |
| Sociedade civil e controle (CGU, ONGs) | Não há visão de quem mantém os dados vivos | Ranking por órgão, relatório mensal |
| Os próprios órgãos | Não sabem que a base deles está quebrada | Página do órgão com o que precisa de atenção |

## A lacuna que preenchemos

- O **Painel da CGU** mede se a base **foi aberta** (cumprimento do Plano de Dados Abertos). Não acompanha a base depois.
- O **dados.gov.br** tem um selo de atualização, mas na amostra validada ele dizia "não verificável" em 82% dos casos e errou 6 de 18 vezes em que disse "atualizado".
- Ninguém verifica o **conteúdo** (hash, colunas, datas internas), ninguém **avisa quem depende** da base e ninguém mostra a **evolução por órgão**.

## O que juntamos de cada referência

| Verificação | Inspiração | O que acrescentamos |
|---|---|---|
| Inventário de bases | Painel da CGU + API do portal | Cruzar as duas listas |
| Link responde? | MQA (União Europeia) | Checar todo dia e guardar histórico |
| Está em dia? | pocket-watch (Pittsburgh), selo do portal | Data real pelo conteúdo; ritmo inferido quando não há periodicidade |
| Formato mudou? | Ninguém faz | Diff de colunas e tipos entre coletas |
| Conteúdo mudou? | stavangerparking (Noruega) | Hash do arquivo a cada coleta |
| Nota por órgão | Índice da Open Knowledge Brasil, mqa-monitor (Itália), nota de Toronto | Contínua e automática |
| Alertas | Ninguém faz | RSS e webhook por base seguida (e-mail fica para depois, decisão 18) |

**Diferencial central:** medir a verdade pelo **conteúdo**, não pelo metadado declarado. Metadados, `Last-Modified` e `ETag` enganam; hash e datas dentro do arquivo não.

## Formato da ferramenta

Regra: **custo zero**, para quem constrói e para quem usa (ver [ROADMAP.md](ROADMAP.md#princípio-custo-zero)).

1. **Motor de coleta** (o coração): pipeline diário em camadas Bronze, Silver e Gold, em Python e DuckDB, rodando no GitHub Actions.
2. **API estática**: o motor gera arquivos JSON com o status de cada base, de cada órgão e o resumo do Brasil. Sem servidor e sem custo. O site é o primeiro cliente dela.
3. **Site público** (o rosto): página por base, por órgão, visão geral e ranking. Gera impacto e pressão pública.
4. **Alertas** (o dia a dia): seguir uma base e ser avisado quando atrasar, quebrar ou mudar de formato.

Depois, se houver demanda: biblioteca Python / CLI ("checar a base X antes de rodar meu pipeline"), extensão de navegador que mostra o status real dentro do dados.gov.br, portais estaduais e municipais.

## Como chega às pessoas

Tudo sai da mesma coleta diária e chega por quatro canais gratuitos.

| Canal | Para quem | O que a pessoa faz com ele |
|---|---|---|
| API estática | Engenheiros de dados e empresas | O pipeline consulta o status antes de ingerir e para se a base estiver quebrada ou mudou de formato |
| Site público | Jornalistas, pesquisadores, qualquer pessoa | Abre a página da base e entende em segundos se o dado é confiável |
| Alertas (RSS e webhook) | Quem depende de uma base específica | Recebe o aviso no Slack, Teams, Discord ou leitor de RSS antes do pipeline quebrar |
| Relatório mensal e ranking | Sociedade, órgãos, imprensa | Vê quem mantém os dados vivos; o ranking público cria pressão para corrigir |

O canal que muda a rotina é a **API**. Hoje o engenheiro descobre o problema quando o pipeline quebra ou, pior, ingere dado velho sem perceber. Com o Clock-in, a primeira tarefa do job vira uma checagem:

```python
import requests

# Consulta o status da base antes de ingerir (endereço definitivo na Fase 6)
status = requests.get("https://clock-in.vercel.app/api/bases/compras-publicas.json").json()

# Interrompe o job se a base estiver quebrada ou se o formato mudou
if status["status"] in ("FORA_DO_AR", "PARADA") or status["schema_mudou"]:
    raise Exception(f"Base com problema: {status['motivo']}")
```

Funciona em qualquer ferramenta que faça um `GET`: Databricks, Airflow, Azure Data Factory, dbt, scripts. Detalhes técnicos em [ARQUITETURA.md](ARQUITETURA.md).

## Como isso faz diferença

1. **Economiza horas** de quem depende de dados públicos: o aviso chega antes do pipeline quebrar.
2. **Torna o problema visível**: rankings públicos geram pressão (prefeituras passaram a disputar o índice da Open Knowledge Brasil).
3. **Complementa o governo**: a CGU cuida da abertura; o Clock-in cuida do que vem depois. Abre portas para parcerias.
4. **Gera conteúdo desde o começo**: "medi 19.602 bases do governo e..." é notícia e portfólio.
5. **Usa engenharia de dados de verdade**: ingestão incremental, schema drift, qualidade de dados, camadas Medallion, aplicadas a um bem público.

## Riscos

- Pode existir algo pequeno que não encontramos (LinkedIn é difícil de pesquisar).
- O governo pode criar algo parecido. Nesse caso, o projeto vira prova de conceito, o que também tem valor.
- A API do portal não é documentada oficialmente e exige sessão do navegador; pode mudar sem aviso (ver [API_DADOS_GOV.md](API_DADOS_GOV.md)).
- Servidores de órgãos podem bloquear acessos automatizados: coletar com calma e se identificar.
- Ranking injusto prejudica a credibilidade: separar "não verificável" de "desatualizado" e publicar a regra.
