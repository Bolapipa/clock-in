# Pesquisa: o que já existe

Pesquisa feita em 24/10/2026 em buscadores, GitHub, documentação oficial, artigos acadêmicos e fóruns. O painel da CGU foi aberto num navegador e os indicadores foram lidos diretamente.

## Concorrentes e referências

### Painel de Monitoramento de Dados Abertos (CGU)

- **Faz:** mede se cada órgão abriu as bases prometidas no Plano de Dados Abertos (PDA). Em 15/10/2026: 9.929 bases previstas, 7.285 abertas (73%), 2.165 em atraso (22%), 479 a abrir. Atualização mensal. Permite baixar a base do painel. Cada linha aponta para a página da base no dados.gov.br.
- **Não faz:** acompanhar a base depois de aberta (atualização, links, formato).
- **Aproveitar:** a lista de bases e órgãos como inventário.
- Endereço: https://centralpaineis.cgu.gov.br/visualizar/dadosabertos (relatório Power BI)

### O próprio dados.gov.br

- **Faz:** guarda periodicidade declarada, última atualização dos dados e dos metadados, e calcula um status por base (`statusAtualizacaoConjuntoDados`: `ATUALIZADO`, `DESATUALIZADO`, `INDISPONIVEL`, este último mostrado como "Atualização não verificável").
- **Problema medido:** na amostra, 82% "não verificável"; das 18 "atualizado", 4 tinham todos os links quebrados e 2 estavam paradas há 578 e 1.327 dias. Ver [VALIDACAO.md](VALIDACAO.md).
- **Aproveitar:** a API pública que o próprio site usa. Ver [API_DADOS_GOV.md](API_DADOS_GOV.md).

### Open Knowledge Brasil (Índice de Dados Abertos)

- **Faz:** avaliação periódica e manual da abertura de dados, com ranking de cidades (São Paulo liderou em 2023).
- **Não faz:** monitoramento contínuo e automático.
- **Aproveitar:** a força do ranking público. Possível parceira.

### União Europeia: MQA do data.europa.eu

- **Faz:** nota de qualidade dos metadados (padrão DCAT-AP) e checagem repetida de acessibilidade dos links.
- **Não faz:** avaliar o dado em si nem se está atualizado (dito na própria metodologia).
- **Aproveitar:** a metodologia de nota e a checagem contínua de links.

### pocket-watch (Pittsburgh, EUA)

- **Faz:** script de linha de comando que lista bases atrasadas num portal CKAN e mede a cobertura temporal real dentro das tabelas.
- **Não faz:** site público, ranking, detecção de mudança de formato.
- **Aproveitar:** medir a data real dentro do dado.

### mqa-monitor (Itália)

- **Faz:** registra diariamente a nota MQA do portal italiano, por órgão, com histórico.
- **Aproveitar:** histórico diário e agregação por órgão.

### stavangerparking (Noruega)

- **Lição:** metadados, `Last-Modified` e `ETag` são sinais enganosos; o confiável é comparar o conteúdo (hash) e usar as datas do próprio dado.

### Base dos Dados e Brasil.IO

- **Fazem:** limpam e organizam dados públicos.
- **Não fazem:** fiscalizar quem publica. Possíveis parceiros.

### Base metodológica (não são concorrentes)

- **WU Viena**, "Measures for assessing the data freshness in open data portals": quase nenhum grande portal informa o quanto os dados estão atualizados; propõe métrica pelo histórico de mudanças. Útil para inferir o ritmo das bases que não declaram periodicidade.
- **Prefeitura de Toronto**, "Data Quality Score": nota com peso grande para atualização e metadados, com graus ouro, prata e bronze.

## Evidências da dor

- 21% dos conjuntos federais anunciados como publicados não tinham arquivo para baixar (estudo da UFPB).
- Em 2026, usuários relataram no dados.gov.br que os arquivos de compras públicas e a API do compras.gov.br pararam de ser atualizados.
- Depois da reformulação do portal (2022), pesquisadores relataram links quebrados e API instável por mais de um ano (SciELO).
- O portal só agrega metadados; os arquivos ficam nos servidores dos órgãos.

## O que não conseguimos verificar

- Posts do LinkedIn e threads do Reddit não apareceram nas buscas.
- Não confirmamos se Transparência Brasil ou Fiquem Sabendo têm ferramenta interna parecida.

## Fontes

- Painel da CGU: https://centralpaineis.cgu.gov.br/visualizar/dadosabertos
- Lançamento do painel (2017): https://www.gov.br/cgu/pt-br/governo-aberto/noticias/2017/cgu-lanca-painel-de-monitoramento-de-dados-abertos-do-governo-federal
- Dataset do painel: https://dados.gov.br/dataset/painel-de-monitoramento-de-dados-abertos
- PDA da CGU 2024–2026: https://www.gov.br/cgu/pt-br/acesso-a-informacao/dados-abertos/arquivos/plano-de-dados-abertos-2024.pdf
- dados.gov.br: https://dados.gov.br/dados/conjuntos-dados
- Estudo UFPB: https://periodicos.ufpb.br/index.php/ies/article/view/52469
- SciELO (DGABr): https://www.scielo.br/j/emquestao/a/3zX6Yy9D5kZkxNLwwfWf9VM/?lang=pt
- Compras públicas: https://dados.gov.br/dados/conjuntos-dados/compras-publicas-do-governo-federal
- Brazil Visible (API): https://brazilvisible.org/docs/apis/portais-centrais/portal-dados-abertos/
- Open Knowledge Brasil: https://ok.org.br/noticia/resultados-do-indice-de-dados-abertos-sugerem-que-e-preciso-avancar-na-transparencia-municipal/
- MQA, metodologia: https://data.europa.eu/mqa/methodology
- mqa-monitor: https://github.com/piersoft/mqa-monitor
- pocket-watch: https://github.com/WPRDC/pocket-watch
- stavangerparking: https://github.com/VirtueMe/stavangerparking/issues/45
- Catálogos de dados do Brasil: https://github.com/dadosgovbr/catalogos-dados-brasil
- WU Viena: https://research.wu.ac.at/de/publications/measures-for-assessing-the-data-freshness-in-open-data-portals-3/
- Toronto: https://open.toronto.ca/?p=2194
