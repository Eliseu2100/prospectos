# Melhorias de prospecção e CRM — novembro de 2026

> Análise pedida pelo Eliseu: (1) integrar o `mazyos-scraper` ao CRM, (2) comparar
> o Seriax OS com práticas de mercado de CRM/prospecção, (3) extrair técnicas de
> abordagem e negociação de vídeos.
>
> **Atualização de 04/11/2026 — aprovado e implementado.** O Eliseu aprovou as
> propostas. O que tinha ficado só como recomendação (seção 1) agora está
> implementado e testado: flag `-resume` no scraper, bônus de nicho prioritário
> no score do lead, e o ajuste de "imagem em vez de link" nas mensagens de
> prévia. Ver "O que foi implementado" no fim de cada seção.

---

## 1. `mazyos-scraper` no CRM

**Descoberta principal: o motor já está integrado — só a fonte do binário está
desatualizada.**

O Seriax OS (este projeto) já roda o `google-maps-scraper.exe` como dependência
externa (`backend/jobs.py`, função `_executar_scraper`), chamado com `-input
-results -lang -depth -exit-on-inactivity -geo -zoom -proxies`. O `README.md`
instrui a baixar esse binário em
[`gosom/google-maps-scraper/releases`](https://github.com/gosom/google-maps-scraper/releases/latest).

O `mazzeoia/mazyos-scraper` **é um fork desse mesmo projeto** — mesmo módulo Go
(`github.com/gosom/google-maps-scraper`), mesmo parser de flags
(`runner/runner.go`), então **os comandos que o `jobs.py` já manda funcionam sem
nenhuma mudança de código**. A diferença do fork:

- Interface web própria em português (`localhost:8080`, mapa + painel + planilha) — um produto à parte, não o modo que o CRM usa.
- Uma correção para Windows no driver do Playwright — exatamente o bug que já
  está documentado como problema conhecido no `CLAUDE.md` deste projeto
  ("busca volta vazia com unexpected page type... bug do binário oficial do
  gosom...").
- Mantido pelo próprio Eliseu/MazyOS, então para de depender da sorte de o
  gosom publicar um release novo quando o driver antigo expira.

**Feito:** troquei a fonte recomendada do binário no `README.md` e a nota do
bug conhecido no `CLAUDE.md`, de `gosom/google-maps-scraper` para
`mazzeoia/mazyos-scraper`. Mesmo nome de arquivo depois de renomear
(`google-maps-scraper.exe`), mesmo passo a passo, zero mudança em `jobs.py`.

**Não feito (fica para quando quiser):** o fork do Eliseu carrega recursos que
o upstream do gosom também tem mas o `jobs.py` ainda não usa:

| Flag | O que faz | Por que pode interessar |
|---|---|---|
| `-resume` | Retoma uma busca em arquivo lendo o CSV já existente, sem repetir o que já foi achado | Hoje, se a busca bate o `TIMEOUT_SCRAPER_SEGUNDOS` ou é cancelada, o progresso se perde. Com `-resume`, um "tentar de novo" vira continuação, não reinício |
| `-fast-mode` | Coleta reduzida, mais rápida | Opção de "busca rápida" na tela, pra quem quer volume e não quer esperar 15 min |
| `-extra-reviews` | Coleta mais dados de avaliações | Dá pra evoluir o score do lead além de nota+contagem (ex.: avaliação recente, tendência) |
| `-grid-bbox` | Varre uma área retangular em grade, sem pino manual | Cobre um bairro inteiro de forma sistemática, complementar ao pino+raio atual |
| `-browser-pool-size` / `-pages-per-browser` | Mais concorrência no navegador headless | Pode acelerar buscas grandes (tem contrapartida de uso de CPU/RAM) |

`-fast-mode`, `-extra-reviews`, `-grid-bbox` e a dupla de concorrência ainda
pedem decisão e teste de produto (mudam velocidade, dados coletados ou a UI de
busca por área) — ficam como próximo passo, não implementados agora.

### ✅ Implementado em 04/11/2026: `-resume`

`backend/jobs.py` (`_executar_scraper`) agora sempre passa `-resume`. Conferido
no código-fonte do fork (`runner/filerunner/filerunner.go`) que isso é seguro
mesmo na primeira busca do dia, quando o arquivo de resultados ainda não
existe: `-resume` só lê o que já tem; se não tem nada, cria o arquivo normal,
do zero, sem erro. Incompatível apenas com `-fast-mode`, `-produce` e LeadsDB,
nenhum dos quais o `jobs.py` usa hoje. Teste novo em
`backend/tests/test_jobs.py::TestExecutarScraperSempreRetomavel`. Suíte
completa: 542 testes passando.

**O que existe no `mazyos-scraper` e não deve ser usado:** o repositório
também carrega um aparato de SaaS do projeto original (painel admin com 2FA,
API, workers, Postgres, Docker, integração com "LeadsDB"). Isso é a edição
comercial do gosom, não faz parte do que o CRM precisa — ignorar essa parte.

---

## 2. Comparação com práticas de mercado de CRM e prospecção

Pesquisa na web (fontes no fim da seção). Boa parte do conteúdo é de
fornecedores de CRM, então tratei números sem metodologia clara como
indicativos, não fato.

### O que o Seriax OS já faz bem
- Funil visual, follow-up e diagnóstico em PDF por lead — isso é exatamente o
  que a literatura chama de "qualificação com motivo concreto para a reunião",
  reconhecido como boa prática.
- Nunca repete lead (banco local) e filtra por nota mínima + ausência de site
  próprio — isso é lead scoring básico, já automatizado.
- Dois canais (Maps + Instagram) com o mesmo funil — "combinar canais" é citado
  como prática que aumenta a chance de conversão.

### Lacunas frente ao que o mercado recomenda

1. **Perfil de Cliente Ideal (ICP) explícito.** A prática mais citada como base
   de CRM eficaz é definir o ICP antes de tudo. Hoje o filtro é só "nota ≥ 4,0
   e sem site". Vale somar critério de nicho/porte (ex.: os 100 nichos do
   `templates/cofre-abordagens`), para o scraper e o score priorizarem quem
   mais fecha, não só quem tem nota boa.

   **✅ Implementado em 04/11/2026.** Novo arquivo
   `templates/cofre-abordagens/crm/nichos_prioritarios.json` com os 7 nichos
   da seção "Ordem" de `nichos-prioritarios.md`, cada um com pontos de 4 a 10.
   Novo módulo `backend/prioridade_nicho.py` (mesmo padrão de
   `abordagem.ficha_do_nicho`: lê o arquivo local opcional, casa pela palavra-
   chave mais longa, sem arquivo = 0 ponto, nunca quebra). O ponto é gravado
   no lead (`leads.prioridade_nicho_pontos`, coluna nova) no momento da busca
   — não recalculado a cada leitura, pra ordenar direto no SQL — e somado ao
   score em `rotas_leads.calcular_score`, com o total sempre travado em 100.
   Leads antigos recebem o bônus retroativo na primeira migração depois desta
   mudança (`processar._preencher_prioridade_nicho_retroativa`). Também achei
   e corrigi de passagem um lugar onde o placar mostrado na tela de tarefas
   (`rotas_analytics.py`, "novos quentes") ia ficar **diferente** do placar
   usado pra ordenar — o SQL já contava o bônus de nicho, mas o Python que
   recalculava pra mostrar na tela não tinha a coluna selecionada. Corrigido
   também. 11 testes novos em `backend/tests/test_prioridade_nicho.py`.

   **Não implementado:** as listas `fora_da_prospeccao` e `em_pausa` do mesmo
   arquivo (barbearia, salão, pet de pequeno porte etc.) ficam só documentadas,
   sem excluir nada automaticamente — continua sendo filtro manual seu, como
   já era. O código só soma pontos, nunca tira lead da lista.
2. **Score de lead mais rico.** A pesquisa recomenda atualizar o score com base
   em comportamento (respondeu? abriu o diagnóstico? quanto tempo demorou?),
   não só em dado estático do Maps. Hoje o Seriax OS pontua na entrada; dá pra
   somar um score que suba quando o lead interage (abre o PDF, responde no
   WhatsApp) e caia com o tempo sem resposta — prioriza quem está "quente"
   agora.
3. **Cadência de follow-up por estágio.** Fontes de mercado recomendam mensagens
   automáticas programadas pela posição no funil, não um único re-contato.
   O `templates/cofre-abordagens` já tem a cadência escrita; a melhoria é o
   Seriax OS lembrar automaticamente qual mensagem da cadência mandar e quando,
   por lead.
4. **Medir taxa de conversão por etapa, não só o total.** A fórmula básica
   (conversões ÷ contatos daquela etapa) por etapa do funil aponta onde o
   processo trava — hoje a análise provável é só "quantos leads, quantos
   fecharam". Vale um relatório por etapa (contato → resposta → reunião →
   proposta → contrato), que é também o que o `analista-de-dados` já produz
   para marketing/social — pode ganhar a mesma visão para o funil comercial.
5. **Risco de conformidade no WhatsApp.** Tanto a pesquisa de mercado quanto o
   próprio aviso do `README.md` do `mazyos-scraper`/ProspectOS batem na mesma
   tecla: mensagem fria em massa no WhatsApp tem risco real de bloqueio de
   número, porque a Meta exige opt-in para contato iniciado pela empresa.
   O sistema já avisa sobre isso — vale manter o volume moderado (o ritmo de
   ~30 contatos/dia do Eliseu já está dentro de uma faixa razoável) e não tratar
   "mandar em massa" como meta.

### Fontes
- [UFMS — TCC sobre CRM e Perfil Ideal do Cliente](https://repositorio.ufms.br/retrieve/4fbf7390-7876-416d-9e4c-c2b582398531/14528.pdf)
- [Nimble — CRM Best Practices for Lead Scoring & Qualification](https://www.nimble.com/blog/crm-best-practices-for-lead-scoring-qualification)
- [Infobip — WhatsApp lead generation](https://www.infobip.com/blog/whatsapp-lead-generation)
- [Zenvia — Prospecção B2B](https://zenvia.com/blog/prospeccao-b2b/)
- [Agendor — técnicas combinadas de prospecção](https://www.agendor.com.br/blog/tecnicas-combinadas-prospeccao/)

---

## 3. Técnicas de abordagem, conversão e negociação

### Sobre o vídeo que você mandou primeiro (`potKGcx8wmg`)

Esse link não era sobre vendas — era um vlog de brasileiros no Japão. O Eliseu
confirmou que passou o link errado e mandou o certo (seção "Vídeo C" abaixo).

Para a parte "pesquise vídeos no YouTube", busquei de verdade (os resultados
do buscador padrão não trazem vídeo do YouTube, então abri o YouTube com
navegador) e assisti dois vídeos realmente sobre o tema. Resumo com timestamp
embutido no racional — scripts prontos para adaptar na `cofre-abordagens` e na
`auditoria-perfil`.

#### Vídeo A — venda de sites para pequenos negócios (canal sobre prospecção, convidado "Primo")
<https://www.youtube.com/watch?v=eIhI1--zjDg>

- **Nunca abra com a oferta.** Testaram três primeiras mensagens; "Olha, eu
  tô vendendo site..." leva a ignorar/denunciar como spam. As que funcionaram:
  um "oi/boa tarde" simples (a pessoa responde pensando que é cliente), e
  melhor ainda: **elogio específico sem pedir nada** — "Boa noite, tava
  olhando o Instagram de vocês e também encontrei [empresa] no Google Maps.
  Achei muito legal o espaço e o projeto de vocês." Prepara a conversa sem
  parecer fechamento.
- **Venda o site como redutor de atrito, não como vitrine.** O argumento que
  mais converteu não foi "sua empresa precisa de site", foi "o site reduz a
  curiosidade antes do WhatsApp, poupa seu tempo explicando a mesma coisa pra
  quem já tá decidido a comprar" — dor concreta do dono do negócio, não estética.
- **Prévia (MVP) só no começo.** Nas primeiras ~30 mensagens/3 a 5 vendas, vale
  montar uma prévia do site antes de fechar — converte muito mais, mas não
  escala (não dá pra fazer 30 prévias pra 30 leads). Depois disso, a técnica
  muda: montar **um layout por nicho** (ex.: estética automotiva) e reaproveitar
  a mesma estrutura, só troca logo/dados pro próximo lead do mesmo nicho — é
  exatamente o que o `templates/kit-vertical` já prepara, só falta documentar
  esse uso explicitamente como estratégia de prospecção, não só de entrega.
- **Preço com margem para negociar.** Cobrar com uma margem embutida
  ("cobro 1000, mas se fechar hoje, 800") é visto como válido e bem recebido —
  o cliente sente que ganhou desconto, você não perde margem real.
  Para quem não tem orçamento para o valor cheio: fracionar em entrada menor +
  mensalidade (cobre suporte e ajustes), em vez de empurrar desconto.
- **Fechar na mesma reunião/call.** Esse foi o ponto mais repetido: se você sai
  da call sem fechar, o lead esfria. A objeção mais comum em negócio familiar
  é "preciso conversar com meu sócio/marido" — quando acontece, o ciclo vira
  dias a semanas, as vezes meses; é normal, não é "venda perdida", mas current
  priorizar fechar no primeiro contato quente sempre que possível.

#### Vídeo B — fechar clientes de social media rápido
<https://www.youtube.com/watch?v=XaTNVxJTO5M>

- **Quatro etapas sempre presentes:** primeiro contato → reunião de
  qualificação → proposta → fechamento (com contrato assinado — "não esqueça
  do contrato"). O vídeo bate numa tecla que vale repetir para a equipe: quase
  todo mundo que não fecha cliente está travando na primeira etapa (vergonha de
  abordar), não no resto do processo.
- **O gancho de qualificação é o diagnóstico gratuito**, não a oferta direta.
  "Oi, sou social media, quero atender sua empresa" não funciona; oferecer uma
  "análise gratuita de Instagram" como desculpa pra marcar a reunião, sim —
  é o mesmo mecanismo que a `auditoria-perfil` já usa e que o próprio
  prospecção de sites já faz (nota no Maps sem site). Vale deixar explícito que
  essa é a técnica-mãe das duas frentes (sites e redes sociais), não só do
  site.
- **"Social selling" para prospecção leve no Instagram:** escolher ~10 perfis
  dentro do ICP, seguir e interagir de verdade (comentar, responder stories)
  sem vender nada, só depois que a pessoa interagir de volta mandar um
  elogio aberto tipo "Admiro muito seu Instagram, é tão bonito, é você mesmo
  que faz?" e esperar a resposta abrir a porta pra oferecer o diagnóstico.
  Isso é uma alternativa de abordagem pelo Instagram, complementar ao
  WhatsApp frio do `cofre-abordagens` — vale um conjunto de mensagens
  equivalente lá.
- **Eventos de nicho, não eventos de marketing.** Ir a congressos do nicho do
  cliente (fisioterapia, estética, etc.), dominar uma estratégia de rede
  social de verdade antes de ir, e oferecer a mesma análise gratuita ali —
  não é um canal que o Eliseu usa hoje (prospecção é majoritariamente WhatsApp),
  mas é uma opção de canal a considerar para contas maiores/recorrência.
- **Conteúdo como prospecção passiva**: Reels/TikTok formato tutorial que
  resolvem um problema real (não conteúdo de marketing genérico), terminando
  com "comenta aqui que eu analiso seu Instagram" — vira porta de entrada pro
  direct/WhatsApp.

#### Vídeo C — o vídeo certo que o Eliseu mandou: "Estou prospectando clientes com Grok Bot e Claude Code"
<https://www.youtube.com/watch?v=MOluZHvWLqY>

Vídeo de 32 minutos de um vendedor de sites/tráfego mostrando a própria
esteira: usa um assistente de IA com uma "skill de prospecção" (que já abre o
scraper do Google Maps — o mesmo `gosom/google-maps-scraper` que o Seriax OS
usa) pra filtrar leads, gerar um preview de site e as mensagens, depois passa
tudo pra um bot pago (Grok, da xAI, ~R$130/mês) que manda as mensagens e faz o
follow-up automático no WhatsApp, Instagram e LinkedIn.

- **Confirma o funil, com um filtro mais fino do que o nosso.** Exemplo real
  mostrado (nicho de marcenaria em São Paulo): 389 empresas no Maps → 309 com
  nota ≥ 4 (igual nosso `NOTA_MINIMA`) → 183 com 15+ avaliações (filtro que a
  gente **não tem**) → 64 sem site → 55 com telefone/WhatsApp → 53 na cidade
  certa → 10 finalistas, batendo mais três critérios: CNPJ com mais de 3 anos,
  não ser MEI, e não ter anúncio ativo no Google. Esses três últimos exigem
  integração nova (consulta de CNPJ, checagem de anúncio ativo) — fica como
  ideia de backlog, não implementei agora.
- **A prévia do site vai como imagem anexada na primeira mensagem, nunca como
  link puro.** Motivo dado: quem recebe mensagem de número novo não clica em
  link, mas abre uma imagem. Essa é a lição mais concreta e diretamente
  aplicável do vídeo — **implementada** (ver abaixo).
- **Benchmark de taxa de resposta em prospecção fria automatizada:** no
  exemplo mostrado, 116 contatos disparados (WhatsApp + e-mail), 58 na
  sequência completa, 6 respostas humanas — uns 10% de resposta humana sobre
  quem recebeu a sequência toda. Útil como referência: se o Eliseu mandar uma
  sequência completa e tiver uma resposta humana a cada 10, está dentro do
  normal do mercado, não é sinal de que a mensagem está errada.
- **Fechar direto pelo WhatsApp, sem call, é prática comum** nesse nicho —
  bate com o que o Vídeo A já mostrou (fechar rápido, aproveitar o calor do
  primeiro contato).
- **O "cofre de abordagens" (50 mensagens + 100 nichos) que esse criador vende
  numa comunidade paga é, na prática, a mesma peça que o nosso
  `templates/cofre-abordagens` já é** — vale ler como validação de que o
  material do Eliseu está alinhado com o que o mercado tá cobrando por
  conhecimento agora, não como algo para copiar (já temos).
- **Não é recomendação comprar o Grok.** O workflow (IA qualifica e prepara →
  bot dispara com intervalo (o vídeo usa 5 min, a régua do Cofre já pede isso)
  → humano assume quando responde) é o mesmo desenho do piloto automático que
  o Seriax OS já tem, só que com uma ferramenta paga de terceiros no lugar da
  Evolution API que já usamos. Não há necessidade de trocar.

### ✅ Implementado em 04/11/2026: imagem em vez de link na prévia

`WA-09` e `WA-10` (`templates/cofre-abordagens/mensagens/`) pediam "posso
mandar o link" — exatamente o oposto do que o Vídeo C mostra funcionar melhor.
Reescrevi as duas para anexar o print/imagem da prévia já na primeira
mensagem, com o link como segundo passo pra quem já se interessou. Acrescentei
a regra como item 6 da "regra de ouro" no `README.md` do Cofre.
**Não atualizado:** `cofre-tudo.txt` e `banco-de-abordagens.html` (galerias
agregadas, não o arquivo-fonte de cada mensagem) ainda têm o texto antigo das
duas mensagens — ficam levemente fora de sincronia até alguém regenerá-los.

### Síntese para aplicar

1. Levar a régua "nunca abrir com a oferta, abrir com elogio + fato concreto"
   para o `cofre-abordagens` — ela já existe no tom de voz do Eliseu
   (CLAUDE.md cita exatamente esse padrão com o exemplo da PeleBella's), então
   é formalizar o que já é praticado, não inventar.
2. Nomear "diagnóstico gratuito" como a técnica única por trás de prospecção de
   site (nota no Maps + sem site) e de redes sociais (`auditoria-perfil`), e
   deixar isso explícito pro Eliseu e para o `executivo-de-contas` usarem a
   mesma lógica ao vender os dois serviços.
3. Documentar a reutilização de layout por nicho como argumento comercial
   ("você entra num padrão já testado no seu nicho"), não só como atalho de
   produção interno.
4. Adicionar ao roteiro de objeções do `cofre-abordagens` a objeção "preciso
   falar com meu sócio/marido", com a orientação de cadência de dias a semanas,
   em vez de tratar como lead perdido.

---

## Resumo do que ficou pendente de decisão do Eliseu

- [x] `-resume` em `jobs.py` — aprovado e implementado em 04/11/2026.
- [x] Critério de nicho no score do lead (item 2.1) — aprovado e implementado
      em 04/11/2026.
- [x] Imagem em vez de link na prévia (WA-09, WA-10) — aprovado e implementado
      em 04/11/2026.
- [ ] Decidir se cria um conjunto de mensagens de Instagram (social selling)
      no `cofre-abordagens`, ao lado do que já existe pra WhatsApp. Ainda não
      criado — o Eliseu aprovou a proposta em geral, mas este item específico
      pede o mesmo cuidado de tom/régua anti-cara-de-IA das demais mensagens
      do Cofre; fica para uma próxima rodada dedicada a isso.
- [ ] Confirmar se quer que eu documente "diagnóstico gratuito" como técnica
      central nos materiais de venda de redes sociais.
- [ ] Decidir sobre os critérios extras do Vídeo C (CNPJ > 3 anos, não ser MEI,
      não ter anúncio ativo no Google) — pedem integração nova, não só config.
- [ ] Atualizar `cofre-tudo.txt` e `banco-de-abordagens.html` pra refletir o
      texto novo de WA-09/WA-10 (ficaram fora de sincronia).
