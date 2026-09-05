# Revisão da interface — 5 de setembro de 2026

## Objetivo e âmbito

Modernizar a apresentação do Forma Flow, mantendo as regras de negócio, os dados,
as permissões e a separação entre acompanhamento interno e decisões oficiais.
A interface continua baseada nos templates Django, sem dependências externas de
estilo, fontes ou bibliotecas JavaScript.

## Alterações

- Identidade em verde-esmeralda, fundo claro, tipografia consistente, ícones SVG
  locais e cartões com espaçamento e hierarquia visual comuns.
- Página inicial com explicação do projeto e ilustração de um percurso claramente
  identificado como exemplo, sem apresentar dados fictícios como indicadores reais.
- Barra lateral com indicação da página atual, avisos e acesso à conta. Em ecrãs
  pequenos, transforma-se num menu com controlo de foco, tecla Escape e fundo de fecho.
- Painel com os mesmos indicadores reais, tarefas prioritárias, distribuição por
  estado e candidaturas recentes. As tabelas adaptam-se a cartões no telemóvel.
- Navegação comum entre resumo, documentos, acompanhamento e financeiro. Os quatro
  separadores permanecem visíveis no telemóvel.
- Listagens com filtros, contagem de resultados, estados diferenciados e mensagens
  específicas para uma lista vazia ou uma pesquisa sem resultados.
- Checklist com progresso calculado a partir dos requisitos resolvidos.
- Formulários com campos, escolhas, ajudas e erros consistentes; opção de mostrar
  a palavra-passe; grupos de opções identificados por legendas; identificadores
  únicos nos formulários que coexistem na mesma página.
- Páginas de autenticação, recuperação de acesso, erros e administração técnica
  alinhadas com a identidade visual. O tema da administração preserva os seus controlos.

## Acessibilidade e segurança

A navegação e os formulários continuam utilizáveis sem JavaScript. Foram mantidos
os rótulos dos campos, o foco visível, a ligação para saltar para o conteúdo,
as mensagens de erro e os textos dos estados, para não depender apenas da cor.
As animações respeitam a preferência de movimento reduzido.

As alterações aos identificadores HTML não mudam os nomes enviados nos formulários.
Os controlos de permissões, CSRF, versões e idempotência permanecem intactos.
A política de segurança de conteúdos não foi alargada. Foi corrigida a apresentação
da página de erro quando o pedido é rejeitado antes da autenticação.

## Verificação

- 201 testes Django aprovados, incluindo regressões para a página de erro e para
  a unicidade dos identificadores e associação das etiquetas nos formulários financeiros.
- Verificações de qualidade e formatação Python aprovadas; JavaScript sem erros de sintaxe.
- Revisão em Microsoft Edge local: página inicial, autenticação, painel, candidaturas,
  documentos, acompanhamento, financeiro, empresas, regras e avisos.
- Verificação de dimensões entre 320 e 1920 píxeis nas páginas exercitadas, incluindo
  ecrãs intermédios; sem transbordo horizontal da página nos cenários verificados.
- Ensaios de navegação móvel, Escape, foco por teclado, mostrar/ocultar palavra-passe
  e navegação sem JavaScript.
- Ensaios de entrada e saída de sessão com quatro perfis fictícios, pesquisa sem
  resultados e reposição de filtros, criação de rascunho e apresentação de erros de
  validação no registo, na nova candidatura e na associação de formação.
- Verificação de entrega numa instalação temporária limpa aprovada, incluindo
  migrações, cenário de demonstração idempotente e verificações da configuração.

Os ensaios de navegador usam uma base SQLite separada e informação fictícia.
Esta revisão não constitui uma certificação de acessibilidade nem substitui ensaios
em dispositivos físicos, noutros motores de navegador ou a validação de produção
com PostgreSQL. Não foi efetuada uma publicação pública.
