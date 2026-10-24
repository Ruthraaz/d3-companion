# D3 Companion — contexto do projeto

Leia este arquivo antes de qualquer trabalho. Ele existe pra que qualquer sessão
continue o projeto sem o Arthur precisar reexplicar tudo.

## Quem é o usuário
- Arthur, estudante de ADS, Python intermediário, um pouco de Go. Quer seguir carreira em backend/dados.
- Projeto pessoal e de portfólio. Joga Diablo 3 **Hardcore Solo Self-Found**, de **Demon Hunter**.
- Fale em **português**, explique cada passo com calma e diga o porquê das decisões.
- Quando ele disser só **"continua"**, siga o roteiro abaixo a partir da próxima etapa pendente.

## Objetivo do app
Item caiu no jogo → Arthur aperta um atalho com o mouse no item → o app captura a dica
(tooltip), lê com OCR, transforma em dados e mostra **num overlay em cima do jogo** se o item
bate com alguma das builds dele e quais afixos batem.

Não é um planejador nem um motor de recomendação (decidido em 24/10/2026). Só "dropou → avaliou".

## Até onde vamos
### Versão 1 (definição de pronto)
A versão 1 está pronta quando: no jogo, com o mouse num item, aperto o atalho e
aparece um selo no overlay com o veredito e os afixos, ex.:
"✅ Dreadlands · Destreza ✓ Crítico ✓ Encaixe ✗".
Vale pras 3 builds de Demon Hunter (Dreadlands, Unhallowed Essence, Legacy of Nightmares).
Na versão 1 as builds são editadas direto nos arquivos JSON (sem janela).

### Visual (decidido em 24/10/2026)
- Overlay (versão 1): PySide6. Selo pequeno, fundo escuro semitransparente,
  borda verde (serve) ou vermelha (não serve), nome da build em destaque,
  afixos com ✓/✗. Aparece ao lado da dica e some sozinho após alguns segundos.
- Janela principal (depois da versão 1): HTML/CSS via pywebview (usa o WebView2
  do Windows, leve, sem Chromium embutido). Mostra o boneco com os espaços,
  as builds, o histórico de itens avaliados e as configurações (atalho, tempo do selo).
  Visual no nível de sites de build (Mobalytics/d4builds).
- Overlay e janela são partes separadas que conversam entre si; a lógica
  (OCR, parser, avaliador) fica num núcleo que as duas usam, sem depender de interface.
- Estilo pode lembrar o Diablo (escuro, dourado, cores de raridade), mas sem
  copiar logo, fonte ou arte da Blizzard.

### Depois da versão 1
Feitos: janela principal (pywebview), outras classes (só JSON), avaliação automática
(feita mas **não funcionou no jogo**; ver notas).

**Novo foco (decidido pelo Arthur em 24/10/2026: "estamos complicando"):** puxar uma build
pronta de um site, mostrar no app e dizer o que é daquela build. Nesta ordem:
1. Chave da Blizzard + dados do jogo (`src/blizzard.py`): habilidades, itens, ícones. ✅
2. Tela nova: boneco com os itens da build + barra de habilidades (6 ativas + 4 passivas), com ícones. ✅
3. Importar do Maxroll: botão "+ Importar" na janela (link de guia ou planner → build + perfil + nome). ✅
   Afixos do Maxroll (`stats` de cada item) viram regras desejáveis do espaço (`regras_do_item`). ✅
4. Herói real vs. build: BattleTag → itens equipados pela API → o que está certo / o que falta.
   (A API só mostra o equipado, e atualiza ao sair do jogo; mochila e baú continuam no F8.)
Não complicar: o "passar o mouse" fica parado; o F8 continua.

**Pedido seguinte do Arthur (24/10/2026):** "puxa todas as builds do site", escolher o boneco (classe)
e ver cada build; no jogo, mostrar itens *parecidos* pra upar; marcador de habilidade, runa e
paragon. Referência: apps de PoE e D4 (lista de builds + overlay). Ordem:
5. Aba Guias: todos os guias do Maxroll por classe (`catalogo()` lê o sitemap, 1×/dia). ✅
   Builds do guia só baixam ao clicar em "Ver builds" (não puxar o site inteiro).
6. Upar: item que não é o da build, mas tem os afixos certos no espaço → "serve por enquanto".
7. Marcadores: destacar habilidade/runa da build e mostrar o paragon (`paragon.data` do perfil:
   4 grupos × 4 atributos).
8. Herói real vs. build (era o passo 4).

### Quem usa
Por enquanto só o Arthur. Se ficar bom, pode virar público. Então, sem fazer
trabalho extra agora, não feche essa porta:
- builds em arquivos JSON separados, nunca dentro do código;
- o avaliador não pode ter nada fixo de Demon Hunter;
- nada de caminho fixo do PC do Arthur no código (usar .env).

## Regras que não mudam
- **Nunca ler a memória do jogo, injetar DLL nem fazer hook de DirectX.** Viola os termos da Blizzard
  e pode banir a conta. O app só **olha a tela**.
- O overlay é uma **janela separada**, transparente, sempre por cima e que deixa o clique passar.
  O jogo precisa estar em **Tela cheia em janela** (Windowed Fullscreen).
- Segredos (caminhos locais, chaves da Battle.net) ficam no `.env`, que nunca vai pro Git.
  Nunca mostrar o valor das chaves (nem em log/terminal); no máximo "existe, N caracteres".
- **Python 3.12** (o 3.15 não tem pacotes pras versões fixadas). Projeto fica em `D:\Projetos\d3-companion`.
- A seção **"Stat Changes if Equipped"** é ignorada: o app compara com a build, não com o item equipado.

## Roteiro
| Etapa | O que faz | Status |
|---|---|---|
| 1 | OCR de print salvo (`src/ocr.py`) | ✅ |
| 2 | Parser texto → JSON (`src/parser.py`, testes em `tests/`) | ✅ (lendários, sets, raros, gemas) |
| 3 | Formato de build em JSON + avaliador (`builds/`, `src/avaliador.py`) | ✅ (formato aprovado em 24/10/2026) |
| 4 | Atalho global + captura perto do cursor (`src/app.py`, `src/captura.py`) | ✅ (testado no jogo em 24/10/2026) |
| 5 | Overlay em cima do jogo (PySide6: `src/overlay.py`, núcleo em `src/nucleo.py`) | ✅ (testado no jogo com gemas) |
| — | **Versão 1:** Arthur testa F8 + selo dentro do jogo; corrigir o que aparecer | ✅ testado no jogo em 24/10/2026 (gemas + equipamentos) |
| 6 | Janela principal (pywebview: `src/janela.py`, página em `src/web/`) | ✅ primeira versão (falta o Arthur usar) |
| 7 | Outras classes: só builds novas em JSON (+ conferência das builds) | ✅ |
| — | Avaliação automática ao passar o mouse (`src/vigia.py`, `captura.olhada_rapida`) | ✅ (falta o Arthur testar no jogo) |
| 8 | Importar builds de sites (Maxroll etc.) como tradutores | próxima |

### Maxroll + tela da build (passos 2 e 3) — notas
- Ícones da Blizzard: Arthur aprovou ("pode prosseguir"). Só o endereço, carregado da Blizzard; nunca salvar.
- Maxroll: `https://planners.maxroll.gg/profiles/load/d3/<n>` (o mesmo que o embed do guia usa); `data` é
  JSON em texto com `profiles[]` (skills `[slug_sem_hifen, letra]`, passives, kanai, items por espaço com
  id da Blizzard e gems). Nomes: `assets-ng.maxroll.gg/d3planner/data.json` (items é LISTA com `ids`
  alternativos; legendaryGems por chave curta "zei"), guardado reduzido em `dados/maxroll/`.
- Letra da runa do Maxroll = `type` da runa na Blizzard (conferido: multishot a=Full Broadside, d=Fire at Will).
- Ordem das ativas no Maxroll: botão esq., dir., 1–4 (`TECLAS` no app.js).
- Guias atuais do Maxroll não têm Dreadlands Strafe nem LoN de DH: essas builds seguem sem habilidades.
- Build ganhou `cubo`, `habilidades`, `fonte` (conferidos em `problemas_da_build`). Item do cubo = "da build"
  no avaliador, sem olhar afixo/Ancient. Unhallowed foi completada com o perfil Solo Push Odyssey (ver `_nota`).
- Janela: `Api.visual(id)` → `blizzard.visual_da_build` (ícones + pt); `Api.abrir_link` só aceita maxroll.gg.
- Link de guia: lemos o HTML do guia e pegamos `data-d3planner-id="<n>"`. Guias trazem planners da
  Enchantress (classe vem "wizard"!) → `e_de_seguidor` pelo nome. Planner de 1 perfil: `data` é o próprio
  perfil (sem `profiles`). Runa "x" = sem runa → "".
- `Api.buscar_maxroll` guarda os planners em memória; `Api.importar_maxroll` grava com `salvar_build`
  (nunca sobrescreve: _2, _3) e a página reinicia o overlay (ele só lê builds/ ao abrir).
- Catálogo: `guia_do_link` tira nome e classe do endereço ("-demon-hunter-guide"; suporte usa
  "zbarb", "zmonk", "zwiz", "znecromancer"). Um guia não termina em "-guide" (skeletal-mage-rat).
  `fonte.guia` = link do guia de onde a build veio (a aba Guias marca "No app").
- Guia mostra só builds da classe dele (`builds_do_heroi`): o de Arachyr Spiders (WD) tem um "DH Speed".
- A classe escolhida (`estado.classe` no app.js) é a mesma nas abas Guias e Builds; Builds só lista
  as builds dela. "Todas" continua sendo todas as builds, de todas as classes.
- Overlay recebe `D3_JANELA_PID` e fecha sozinho se a janela morrer (`processo_vivo`). Antes, fechar
  o terminal do abrir.bat deixava o overlay órfão segurando a trava → o próximo ficava "parado".
- Afixos: `stats` do data.json tem name/format/secondary/args. `format` "%.1f%%" → "#%" (`modelo_do_formato`).
  `wpn*` (dano elemental da arma) vem SEM format e args 2 → "+#-# Cold Damage". `skill_<classe>_<skill>` →
  "Increases <Nome> Damage by #% *" (o "*" engole o "(Demon Hunter Only)"). Mudou o que guardamos do
  data.json? Sobe `VERSAO_DO_CACHE` pra baixar de novo.
- Testes que comparam resultados usam só `tests/builds_dos_testes.py` (as 3 originais); a conferência
  olha todas. Assim importar uma build não quebra teste.
- Arthur importou "Shadow Impale" (guia shadow-impale, perfil Sanc: Solo Push) em 24/10/2026.
- Cuidado no `el()` do app.js: qualquer valor vira atributo (`disabled: null` desativa!). Use spread condicional.

### Dados da Blizzard (passo 1 do novo foco) — notas
- `src/blizzard.py`: token client_credentials em `https://oauth.battle.net/token`, API em
  `https://us.api.blizzard.com/d3/data/...`. Só biblioteca padrão (urllib), sem `requests`.
- Cache de cada resposta em `dados/blizzard/<locale>/` (fora do Git). Índice de itens (~2192, de
  135 tipos, ~20 s na 1ª vez) em `dados/blizzard/indice_de_itens.json`. `--atualizar` apaga o cache.
- Nomes em inglês (como o jogo/OCR/builds); `nome_pt`/`descricao_pt` (pt_BR) pra mostrar.
- Ícones: só o endereço (`blzmedia-a.akamaihd.net/d3/icons/{skills/64|items/large}/<icon>.png`),
  carregado direto da Blizzard; **nunca salvar a imagem no projeto** (proposto ao Arthur, falta ele confirmar).
- `chave_do_nome`: troca apóstrofo curvo ANTES de tirar acento (senão o ’ some e "Zei’s" não acha).
- `python src/blizzard.py` confere os itens/gemas das builds contra o índice (com sugestão).
- Testes com uma Blizzard falsa (`FalsaBlizzard`), sem internet nem chaves.

### Avaliação automática — notas
- **Não mostrou selo no jogo do Arthur** (24/10/2026). Overlay subia sem erro; a simulação com
  print de samples/ funcionava. Suspeita: na tela inteira, o fundo escuro/inventário gruda na
  dica e o bloco preto não passa no filtro. Diagnóstico ficou em `capturas/diagnostico.bat`,
  mas o Arthur decidiu focar em outra coisa. Retomar só se ele pedir.
- Pedido do Arthur (24/10/2026): "só passar o mouse por cima do item" em vez de apertar F8.
- `app.vigiar` (thread): a cada 0,25 s, print + `olhada_rapida` (~40 ms) → assinatura (posição,
  tamanho, hash do bloco preto, prefixada com BUILD_ATIVA) → `Vigia.olhar` decide
  NADA/AVALIAR/GUARDADO/ESCONDER. OCR só em dica nova e estável; resultado guardado (LRU 40).
- Só com a janela "Diablo III" em primeiro plano (`captura.jogo_em_foco`).
- Selo fora dos prints (`WDA_EXCLUDEFROMCAPTURE`) — essencial, senão o vigia vê o próprio selo.
- No automático o selo é fixo (`segundos=0`), some quando a dica some; no F8 some em SELO_SEGUNDOS.
- `AUTOMATICO=sim|nao` no .env (padrão sim), relido a cada 1 s; toggle na aba Configurações.
- Erro no automático (não era item) não vai pro histórico nem salva print (`salvar_sem_dica=False`).

### Etapa 7 — notas
- Nada de classe fixa no código; modelo pra outra classe em `builds/exemplos/` (não é carregada).
- `avaliador.ler_builds` confere cada build (`problemas_da_build`): build com erro fica de fora, com
  mensagem em português + sugestão (difflib). Aparece no terminal do overlay e na aba Builds.
  `python src/avaliador.py --conferir [pasta]`. Chaves com `_` são comentário.

### Etapa 6 — notas
- `python src/janela.py` liga o overlay (`app.py`) como **processo filho**: Qt e pywebview querem a thread
  principal. Desligar usa `taskkill /T` (o python.exe da .venv é lançador; o filho segura o atalho).
- Overlay → janela: `capturas/historico.jsonl` (`src/historico.py`). Janela → .env: `src/config.py`
  (só ATALHO e SELO_SEGUNDOS; o resto do arquivo fica intacto). Build pra tela: `avaliador.ficha_da_build`.
- Página: só `textContent` (nome de item vem do OCR). Fora do pywebview usa dados de exemplo (`apiDeExemplo`).
- **Build escolhida** (pedido do Arthur, 24/10/2026): clicar numa build na janela = o F8 avalia só com ela;
  "Todas" = todas. Fica em `BUILD_ATIVA` no .env (id = nome do arquivo da build); `app.py` relê a cada F8
  (`avaliador.builds_escolhidas`). Id que sumiu → volta pra todas.
- **Só um overlay por vez** (mutex `Local\D3Companion.Overlay` no `app.py`): um `app.py` esquecido no
  terminal segurava o F8 com código antigo e o selo "ignorava" a build escolhida.
- Ainda não tem: editar build pela janela (decisão da v1: builds só no JSON), screenshot no README.

Em 24/10/2026 o selo dos 7 equipamentos de `samples/` foi conferido fora do jogo (mesmo caminho do F8)
e saiu certo: sets da build certa, lendário fora da build com "Não serve" + motivo, raro com ✓/✗ por afixo.
No jogo (mesmo dia): corrigidos nome de set com "Ignores Durability Loss", gema lendária encaixada
(conta como encaixe) e selo tampando a dica do item equipado (`grupo_de_dicas`). Limitação aberta:
gema comum encaixada é lida como afixo. Pendente do Arthur: revisar gemas/itens das builds.

### Etapa 5 — notas
- Builds ganharam `apelido` (nome curto no selo) e `rotulo` por afixo (ex.: "Destreza"). Sem eles, usa nome/modelo.
- `nucleo.py` não importa Qt: `avaliar_print`, `montar_selo`, `caixa_na_tela`, `posicao_do_selo` (testados em
  `tests/test_nucleo.py`). `overlay.py` só desenha. A futura janela (pywebview) deve usar o mesmo núcleo.
- `QT_ENABLE_HIGHDPI_SCALING=0` no app: o selo usa pixels reais, iguais aos do print e do mouse.
- `SELO_SEGUNDOS` no `.env` (padrão 6).

### Etapa 4 — notas
- Pipeline do app: F8 → print em volta do mouse → `recortar_dica` (par de bordas verticais + miolo preto,
  folga de 70 px em cima) → OCR **ampliado 2x** → parser → avaliador. Medido: 52/53 no gabarito.
- Borda da dica = pixel claro com **≥7 de 10 vizinhos pretos** pra dentro (senão a moldura do
  inventário emenda na borda). Print real que falhar no jogo: copiar de `capturas/` pra `samples/`
  e virar teste (ex.: `jogo_zei_abaixo_do_inventario.png`).
- `tests/ocr_recorte/` = saída REAL do app; `tests/test_captura.py` compara com o gabarito das imagens.
  Se mudar o recorte ou o OCR, **regenere** esses textos (`texto_da_dica`) e rode os testes.
- Recortes do app ficam em `capturas/` (fora do Git). Prints do jogo com erro de leitura viram exemplos novos.

### Pendências da Etapa 2 — ✅ resolvidas em 24/10/2026
Tudo abaixo está feito e testado (17 testes). Saída de set: campo `"set": {"nome", "pecas": [{"nome", "slot"}]}`;
raros saem com `"nome": null`. Limitações que ficaram estão no README.

Exemplos em `samples/` (adicionados em 24/10/2026):
- `set_fiendish_grips.png` (Unhallowed Essence), `set_antique_vintage_boots.png` (Gears of Dreadlands),
  `set_litany_of_the_undaunted.png` (Legacy of Nightmares) — itens de set com "Stat Changes".
- `set_cains_scrivener_equipado.png` — item de set **já equipado** (sem "Stat Changes").
- `raro_vampiric_source_equipado.png` — item **raro** (amarelo), equipado.

O parser precisa:
1. Ler o **nome do set** e a **lista de peças** com o espaço de cada uma, ex.: `"Gears of Dreadlands"`,
   `"Antique Vintage Boots (Feet)"`. O OCR lê essa parte muito bem.
2. Funcionar com **raros**. O título dos raros sai bagunçado no OCR (`LVampiniseuRCE`), mas o nome
   de raro é aleatório e não importa; o que importa são tipo, espaço e afixos.
3. Novas correções de OCR vistas: `Lie` → `Life`, `Kil` → `Kill`.
Gere os `.txt` em `tests/ocr/` e crie testes pra cada caso.

## Etapa 3: formato de build (decisões já tomadas)
- O app tem **um formato de build próprio** (JSON). Sites como Maxroll/Icy Veins, se um dia entrarem,
  serão só **tradutores** (padrão *adapter*) pra esse formato. O avaliador só conhece o formato próprio.
- Por enquanto as builds são escritas **à mão**. O D3 está em modo de manutenção, então builds quase não mudam.
- Uma build define, por espaço: o item desejado (se houver) e a **prioridade de afixos**, separando
  **obrigatórios** de **desejáveis**. Usar o "modelo" do afixo do parser (`+# Dexterity`) pra comparar.
- Builds iniciais (Demon Hunter): **Gears of Dreadlands** (Metralhar + skill primária),
  **Unhallowed Essence** (Multidisparo + gerador) e **Legacy of Nightmares** (sem set, itens Ancient).
- Prioridade de afixos de referência (leveling/geral, Icy Veins): Destreza sempre primeiro; elmo:
  encaixe, chance de crítico; peitoral/calças: encaixes; luvas: chance e dano crítico; anéis/amuleto:
  encaixe, chance e dano crítico; arma: dano alto, Destreza, encaixe.
- Antes de codar a Etapa 3, **mostre ao Arthur o formato JSON proposto** e espere o ok.
- ✅ Feito: formato descrito no README. Pendente do Arthur: revisar as **gemas** (palpite inicial) e
  preencher os itens dos espaços fora do set (hoje `itens: []` = qualquer item com os afixos).

## Forma de trabalhar
- Ao fim de cada etapa: rode os testes, atualize o README (roteiro e "o que aprendemos"),
  faça commit e push. Mensagens de commit em português.
- Só uma sessão mexe no repositório por vez. Antes de começar, rode `git pull`.
