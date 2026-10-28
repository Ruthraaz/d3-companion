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
Vale pras 3 builds de Demon Hunter (Dreadlands, Unhallowed Essence, Legacy of Nightmares), hoje em `tests/builds/`.
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
- **26/10/2026 — visual novo, pedido do Arthur: parecido com o d4builds** (prints dele): fundo grafite,
  destaque vermelho na aba ativa, título da build em laranja, itens nas cores de raridade. Aba Builds =
  página de build do d4builds (cabeçalho com emblema, sub-abas, equipamento em 2 colunas com uma "roda"
  no meio com cubo + gemas, habilidades numa fileira). Aba Guias = tier list do d4builds (grade de
  classes ao lado). Ícone de classe = ícone de uma habilidade dela, do CDN da Blizzard (`ICONE_DA_CLASSE`).
  Tela de abertura com barra (`#abertura`). Página tem CSP: precisa de `'unsafe-eval'` porque o
  `api.js` do pywebview usa `new Function` (sem isso a ponte com o Python some).

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
6. Upar: item que não é o da build, mas tem os afixos certos no espaço → "serve por enquanto". ✅
   `por_enquanto` no resultado (obrigatórios ok + nota ≥ `NOTA_POR_ENQUANTO` 0.5, ou item certo
   sem Ancient); `Selo.parcial` = borda amarela. Só aparece se nenhuma build bate.
   Ideia do Arthur (26/10/2026): colar o link → o app usa aquela build na hora e, no jogo, diz o
   que o item tem, o que falta e o que deveria ter. Feito: importar já escolhe a build do atalho;
   o selo mostra Tem / Falta / Dica do Místico (`sobrando` = afixos principais fora das regras).
7. Marcadores: nível de cada habilidade/runa (lista "Ao upar") e o paragon da build. ✅
   `paragon.data` do perfil = 4×4 na ordem do jogo: Principal [atributo, Vit, Velocidade, Recurso],
   Ataque [IAS, CDR, CHC, CHD], Defesa [Vida, Armadura, Res, Regen], Utilidade [Área, RCR, LoH, Ouro].
   Conferido: índice 2 é sempre 50 (Velocidade tem teto 50); índice 3 às vezes 0 (Recurso).
   Build guarda `"paragon": {"nivel", "pontos"}`; runa ganhou `nivel` (campo `level` da Blizzard).
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
- **Ponte (27/10/2026):** sem chave no .env, `pegar()` chama `PONTE` (Supabase Edge Function
  `supabase/functions/blizzard/index.ts`, `?caminho=&locale=`, sem Authorization). A função guarda as chaves
  do Arthur nos secrets do Supabase, aceita só os caminhos D3 do app (regex), cache em memória (dados 24 h,
  perfil 5 min), 240 pedidos/min por IP (o índice faz ~135), Verify JWT desligado. 429 e outros erros da
  ponte têm mensagem própria. `D3C_PONTE` no ambiente troca o endereço (vazio = volta a exigir chave).
  Com chave no .env o app fala direto com a Blizzard, como antes. Mudou a função? Arthur cola de novo no painel.
- **Modo gravação (27/10/2026, 1.0.4):** `GRAVACAO=sim` no .env (Configurações). `JanelaSelo(gravacao=True)` não chama
  `SetWindowDisplayAffinity` (o selo aparece no OBS); o vigia para (ele se veria) e o F8 emite `esconder` e espera
  0,15 s antes do print. Feito pro Arthur gravar o vídeo de divulgação.
- **1.0.5 (27/10/2026): idioma + Como conseguir.** (1) Em inglês ainda saíam rótulos em português nas builds do
  Maxroll ("Dano de Tiro Múltiplo", "Dano mín–máx", "Dano da arma") e nomes de habilidade/runa no Meu herói.
  Agora `avaliador._rotulo()` devolve o rótulo já no idioma (t(); dano de habilidade em inglês sai do modelo:
  "Increases Multishot Damage by #% *" -> "Multishot damage"; "(mín. N)" também passa por t()). Quem mostra
  ainda chama t() de novo, sem efeito. `nucleo.dica_do_mistico` compara "Encaixe" nos dois idiomas. janela.py
  usa `nome` (en) ou `nome_pt` conforme `idioma.atual()`. (2) `src/origem.py`: "Como conseguir" de cada item,
  mostrado no detalhe do espaço (app.js `comoConseguir`). Da API: tooltipParams `/artisan/<artesão>/` = forjado;
  typeName "Legendary Gem" = Guardiões da Grande Fenda; `isSeasonRequiredToDrop`. À mão: `ITENS_DO_CACHE`
  (21 itens só do Cache Horádrico dos atos I, II, III e V; o do Ato IV sorteia entre eles; lista conferida na
  wiki do Diablo em 27/10/2026). Resto: regra geral (monstros, Kadala, cubo "raro -> lendário"). Sem detalhes
  (sem internet / item desconhecido) = [] (melhor nada que errado). `visual_da_build` manda `origem` em cada
  item como {texto, vars}; a janela traduz com t().
- **Atualização pelo app (27/10/2026, a partir da 1.0.3):** `src/atualizar.py`. `versao_nova()` lê
  `api.github.com/repos/Ruthraaz/d3-companion/releases/latest` (erro = None, faixa não aparece); o instalador só vale
  com nome `D3-Companion-Setup-X.Y.Z.exe`, URL exata `releases/download/vX.Y.Z/...`, `digest` sha256 e tamanho <= 400 MB.
  `baixar()` confere tamanho + SHA-256. `instalar()` roda `cmd /c ping -n 4 127.0.0.1 >nul & "<setup>" /SILENT ...`
  /DIR="<pasta do .exe>" (atualiza onde está; o Arthur tinha instalado em D: sem a chave no registro) (o `timeout` do Windows falha sem console) e a janela fecha (overlay.desligar + destroy). O .iss tem um 2º [Run]
  com `Check: WizardSilent` que reabre o app. Só instala sozinho com `unins000.exe` ao lado do .exe (instalado);
  zip/código = abre a página. Release sem o Setup no nome certo quebra o botão: sempre publicar os dois arquivos.
- **Regiões (27/10/2026):** `REGIOES = us, eu, kr, tw`; `pegar(..., regiao=)` troca o host
  (`{regiao}.api.blizzard.com`, mesmo token; dados do jogo sempre de us). Na ponte vai `&regiao=` só fora de us
  (a 1.0.2 sem o parâmetro continua funcionando). `heroi.herois` pergunta as 4 em paralelo; 404 =
  `NaoEncontrado` (subclasse de ErroBlizzard; antes comparava o texto em português e quebrava em inglês).
  Cada herói tem `regiao`; o JS manda de volta em `comparar_heroi(..., regiao)`.

### .exe (26/10/2026) — notas
- `ferramentas/empacotar.py` (PyInstaller 6.22.3, onedir, windowed). Entrada `src/d3companion.py`
  (`--overlay` = app.py). Caminhos todos em `src/pastas.py`: no .exe, `PROGRAMA` = `sys._MEIPASS`
  (`_internal/`) e `SEUS` = `%APPDATA%\D3 Companion` (.env, builds, capturas, dados).
- Tesseract copiado DEPOIS do PyInstaller (com `--add-data` ele duplicava as DLLs: +100 MB).
- Testado em 26/10/2026 com APPDATA temporário: janela abre, copia as builds, desenha;
  `--overlay` sobe (parou na trava porque o overlay do Arthur estava aberto). Zip ~133 MB.
- Sem assinatura digital: SmartScreen avisa (explicado no LEIA-ME.txt e no site).

### Habilidades e seguidor (26/10/2026) — notas
- Pedido do Arthur (com prints do d4builds e das janelas do jogo): a roda é **só das gemas** (p0/p2/p4);
  cubo virou 3 cartas embaixo do boneco. Sub-abas novas **Habilidades** (estilo janela Skills: mouse,
  barra 1–4, passivas) e **Seguidor** (estilo painel do Templário: itens + 4 habilidades por nível).
- `maxroll.seguidor_do_perfil`: `follower` + `followerItems` + `followerSkills`. data.json do Maxroll tem
  `followerSkills[código].id` = slug da Blizzard (cache subiu pra VERSAO 3). Sem ele, guarda o código em
  minúsculas, que é igual ao `icon` da Blizzard: `_visual_do_seguidor` acha por slug ou por ícone.
- `Blizzard.seguidor(quem)` (`/d3/data/follower/templar`, pt_BR: Templário, Vigarista, Sibila).
- Ícones do seguidor: `skills/64/<icon>.png` (conferido: 200).
- Detalhe do lado: aparece em Equipamento e Habilidades; em Habilidades começa na 1ª habilidade.

### Builds de cada um + Paragon (26/10/2026) — notas
- Pedido do Arthur: builds que vinham no app estavam bugadas (faltando itens). Agora o app **não traz builds**:
  `builds/*.json` no .gitignore (só `builds/exemplos/` no Git), o .exe não empacota `builds/` (antes empacotava
  a pasta local inteira!) e `pastas.preparar()` só cria a pasta. Tela vazia da aba Builds = "Monte a sua lista"
  com o colar link aberto. Botão **Remover** (2 cliques) → `Api.remover_build` → `maxroll.remover_build`
  (id só `[A-Za-z0-9_-]`, arquivo direto em builds/; se era a do atalho, volta pra "todas").
- As 3 builds feitas à mão (Dreadlands, LoN, Unhallowed) viraram dados de teste em `tests/builds/`
  (`PASTA_DOS_TESTES` em `tests/builds_dos_testes.py`). As importadas pelo Arthur continuam no PC dele, fora do Git.
- Paragon: Arthur achava que Destreza era a prioridade (o 3950 aparecia primeiro). Agora são passos
  numerados por grupo (`ORDEM_DO_PARAGON` no app.js), com "Todo o resto" por último no Principal. O Maxroll
  só guarda números (conferido no planner 236100095), a ordem é a comum dos guias.
- Fora do app, `?vazio` na URL simula app recém-instalado.

### Site (26/10/2026) — notas
- `docs/` = GitHub Pages (branch main, pasta /docs, `.nojekyll`). Endereço: https://ruthraaz.github.io/d3-companion/
- `docs/site.js` lê `api.github.com/.../releases/latest` e aponta o botão pro zip; só aceita link
  `github.com/Ruthraaz/d3-companion/releases/download/`. Sem versão publicada: 404 e o botão leva à página de Releases.
- CSP própria (`connect-src https://api.github.com`). Nenhuma imagem/print do jogo no site:
  a dica e o selo da capa são HTML/CSS; `img/janela.png` é a tela de exemplo do app (sem ícones).

### Montar build no site (26/10/2026) — notas
- Pedido: "Fazer o site ser igual o app e adicionar o sistema de montar build ... só que no site o cara nao vai
  poder usar o sistema de avaliacao in-game".
- `docs/montar.html/js/css` + `docs/app.css` (cópia de `src/web/estilo.css`, testado em tests/test_site.py).
- `docs/dados/jogo.json` gerado por `ferramentas/dados_do_site.py` (cache da API Blizzard + planner do Maxroll
  pros afixos). Só nomes/códigos de ícone; imagens ficam no CDN (`blzmedia-a.akamaihd.net`, única origem de img na CSP).
- Link: `montar.html#b=` + base64url(deflate-raw(JSON da build)). App: `link_do_site.build_do_link` (https, host,
  caminho, ≤20000 chars, ≤200 KB aberto, força `fonte={"site":"montar"}`, tira "id"/"_*") e `Api.importar_do_site`.
- Rascunho por classe em localStorage ("d3c-montar-v2"; o v1 é apagado). Ainda falta: seguidor no montador.

### Montar no app + dica do item (26/10/2026) — notas
- Pedido: "Quando passar o mouse por cima mostrar oque a gema faz, se for possivel ou os itens no geral. e fazer o
  sistema de montar builds para os usuarios conseguirem criar suas builds no app/site".
- Fonte única em `src/web/` (montar.js/css, dica.js, dados/); `docs/` tem cópias (`dados_do_site.py --so-copiar`,
  teste `test_copias_do_site_estao_em_dia`). `.gitignore` libera `docs/dados/` e `src/web/dados/`.
- montar.js é um IIFE (`window.Montador.iniciar(raiz, {modo, carregar, salvar, aoSalvar})`, `.abrir(build, id)`);
  acha tudo por `data-m` dentro de `[data-montador]` (o app tem os mesmos ids na aba Builds). montar.css também
  fica dentro de `[data-montador]`. app.js: seletores de sub-aba presos a `#painel-builds`.
- Api: `dados_do_jogo("jogo"|"dicas")`, `salvar_montada(build, id)` (passa por `link_do_site.build_montada`,
  ≤200 KB; com id usa `maxroll.regravar_build`, que só grava por cima de build com fonte "montar"),
  `build_para_montar(id)`.
- dicas.json: `{itens: {nome_en: {n, t, p?, s?, f?}}, sets: {nome_set: [bônus]}}`. Poder = spans laranja
  (`d3-color-ffff8000`); sem laranja, azul fora "Engastes" (ex.: RoRG). Faixa cinza vai junto no item, não na gema.
  Texto puro (HTMLParser no gerador; dica.js usa textContent).

### Divulgar + limpeza + segurança do site (26/10/2026) — notas
- Pedido: "Faz o site ser divulgavel e o app tambem ... antes faça uma melhora no site ele esta com resultados
  salvos ja limpe, nao se esqueca da cyberseguranca".
- Limpeza: `docs/previa_selo.png` era print do jogo (arte da Blizzard) → saiu do Git (cópia local em `capturas/`,
  que é ignorada). `img/janela.webp` antigo (builds que vinham junto) → `img/janela.png` novo. Rascunho do montador
  agora é `d3c-montar-v2` (apaga o v1) e só guarda classe com conteúdo (`temConteudo`).
- Imagens: `ferramentas/vitrine.py` (Edge headless numa CÓPIA de src/web com vitrine.css que esconde `img` e
  vitrine.js que abre Montar e a dica; sem CSP só na cópia) → `docs/img/janela.png` (en), `janela.pt.png` (pt, `--lang=pt-BR`) e `compartilhar.png` (1200x630, PIL, en).
  Nunca usar CopyFromScreen.
- Divulgar: Open Graph/Twitter com URL absoluta + canonical (index e montar), robots.txt, sitemap.xml, 404.html,
  `.well-known/security.txt` (Expires daqui a 1 ano: renovar!), botão "Mandar o site pra um amigo" (site.js,
  endereço fixo), "Compartilhar" no montador do site (só com navigator.share), em Configurações do app
  "Indique pra um amigo" (`Api.abrir_site`, endereço fixo). README com cara de vitrine.
- Segurança: frame-buster no site.js e no montador do site (Pages não manda frame-ancestors/X-Frame-Options);
  `SECURITY.md`; `.github/dependabot.yml` (pip, semanal); testes `TestSegurancaDoSite` (CSP rígida em toda página,
  sem script/evento/style inline, noopener, sem innerHTML/eval no JS, lista fechada de imagens, og:image própria,
  security.txt válido e sem e-mail). Exemplos de BattleTag viraram "Jogador#1234" (nada do nome do Arthur no código).
- Varredura (valores do .env + e-mail + pasta do usuário) no histórico inteiro do Git: nada encontrado.

### Inglês + português (26/10/2026) — notas
- Pedido: "transforma o app e o site em ingles para atender um publico geral". Arthur escolheu **inglês +
  português**: inglês por padrão; português quando o navegador/Windows está em português; botão pra trocar.
- `src/web/idioma.js` (cópia em docs/): chave = frase em português; `src/web/dados/en.json` = pt → en.
  `Idioma.t(frase, {vars})`, `Idioma.aplicar()` traduz `[data-t]` (textos + placeholder/title/aria-label/alt/
  content), `[data-trocar-idioma]` vira o botão. Site: escolha em localStorage `d3c-idioma`, senão navigator.languages.
- montar.js: `t()`, `nomeDaClasse/nomeDaHab/nomeDaRuna` (em inglês usa h.n e runa[3]; runas agora
  `[letra, nome_pt, nivel, nome_en]`). Rótulo do afixo de habilidade sai no idioma da hora ("{hab} damage").
- Dicas: `dados_do_site.py` gera também `dicas.en.json` (locale en_US); o site carrega um ou outro.
- Página inicial: `docs/index.html` em inglês, `docs/pt/index.html` em português (caminhos `../`), hreflang +
  x-default, sitemap com pt/. `site.js`: sem escolha guardada e navegador pt → `pt/`; o link de idioma guarda a
  escolha (sem laço de redirecionamento). 404 em inglês com linha em português.
- Testes `TestIdioma`: toda frase `t("...")` do JS e todo `[data-t]` do montar.html têm tradução, variáveis
  `{x}` iguais nos dois idiomas, nomes do montador/afixos/atributos traduzidos, dicas.en, páginas pt/en.
- App (fase 2): `config.py` IDIOMA ("en"/"pt"; vazio ou inválido = `idioma_do_windows()`, GetUserDefaultUILanguage
  0x16). app.js: `iniciar()` lê a config, `Idioma.escolher(IDIOMA)`, carrega en.json por `Api.dados_do_jogo("en")`
  (aceita jogo, dicas, dicas.en, en), `Idioma.trocar` grava no .env e recarrega. index.html com `data-t`
  (aplicar() junta espaços/quebras da chave). blizzard.py manda `descricao` (en) junto de `descricao_pt`;
  app.js usa `nomeDe/descricaoDe`. Teste lê o HTML com HTMLParser (o mesmo que aplicar() traduz).
- Python (fase 3): `src/idioma.py` `t(frase, **vars)` com o mesmo en.json; idioma = IDIOMA da config (relê
  quando o .env muda). `D3C_IDIOMA=pt|en` no ambiente manda mais (todo test_*.py põe "pt" depois do sys.path).
  Selo (nucleo), motivos (avaliador) e erros de blizzard/heroi/maxroll/janela/link_do_site/config passam por t().
  Frases com variável viram modelo (`"Build {id} não encontrada."`, `!r` → `repr()`). O avaliador agora manda
  `item_da_build` (o selo não depende mais do texto do motivo). Teste: o `ast` acha todo `t("...")` do src/*.py.
- Texto em CSS (`content:`) não passa por t(): usar `attr(data-...)` com o texto do JS (ex.: "no atalho" do chip).
  O histórico de exemplo (apiDeExemplo) é montado na hora com t(); o de verdade fica no idioma em que foi gravado.
- Cache do navegador segura o site.css velho no teste local: recarregar o próprio .css com Ctrl+Shift+R.

### Contas: salvar builds na nuvem (26/10/2026) — notas
- Pedido: contas **só pra salvar builds na nuvem**, login Discord/Google via Supabase (plano grátis). O Arthur cria o
  projeto e os apps OAuth sozinho (passo a passo no README, "Passo a passo pro Arthur ligar a nuvem"). Até lá, o
  `docs/config-nuvem.js` fica vazio e a barra da nuvem nem aparece.
- Banco: `ferramentas/supabase.sql` (roda no SQL Editor, pode repetir). Tabela `builds` (id, user_id default auth.uid()
  on delete cascade, nome ≤60, classe das 7, dados jsonb ≤50000 bytes, criado, alterado). RLS enable + force, 4 políticas
  `to authenticated` com `(select auth.uid()) = user_id`; anon sem grant. Gatilho `builds_antes_de_gravar`: máx. 50 por
  conta, id/dono/criado não mudam, alterado = now(). `apagar_minha_conta()` security definer (search_path '') apaga
  `auth.users where id = auth.uid()`. Nada de e-mail na tabela (LGPD).
- Site: `docs/nuvem.js` + `nuvem.css` (só do site, não são cópias). supabase-js **2.117.3** UMD do jsDelivr com SRI sha384
  (conferido contra o hash do jsDelivr); carregado só ao clicar em Entrar ou com sessão guardada (`sb-<ref>-auth-token`)
  ou na volta do login (`?code=`). PKCE; `redirectTo` = a própria página; depois tira `?code=` do endereço (o `#b=` fica).
  "Sair" = `signOut({scope: "local"})`. Só aceita chave `sb_publishable_` ou JWT com role anon (o resto desliga a nuvem).
- CSP do montar.html: `script-src 'self' <URL exata do supabase.js>`; `connect-src 'self'` + o Project URL depois de
  `python ferramentas/nuvem.py <url> <chave>` (ele recusa service_role/sb_secret_; `--desligar` volta). Teste confere
  que o connect-src bate com o config.
- montar.js ganhou `paraNuvem/marcarNuvem/esquecerNuvem/daNuvem/nomeDaClasse` e `Montador.noSite` (promessa: idioma +
  montador prontos). Rascunho guarda `nuvem` = id da build na nuvem que "Salvar na nuvem" altera ("Começar de novo" esquece).
- Privacidade: seção `#nuvem` na página inicial (en e pt), dentro de "Security and privacy".
- Teste no navegador sem config: barra escondida, supabase-js não baixa, sem erro. Com config falsa + Supabase falso
  (só na aba): salvar/alterar/listar/abrir/apagar funcionando; o supabase-js real carrega com SRI e CSP.
- **App (para depois):** o app já importa builds pelo link do site. Pra ver as builds da nuvem no app: botão "Entrar"
  em Configurações abrindo o navegador do sistema no login do Supabase com PKCE e redirect pra
  `http://127.0.0.1:<porta>/callback` (servidor local só durante o login, igual a CLIs); guardar só o refresh token
  no `.env` (nunca na página, igual às chaves da Blizzard); listar com a mesma tabela via `urllib` (REST
  `/rest/v1/builds` com a chave pública + token) e gravar cada uma com `link_do_site.build_montada` +
  `salvar_build`. Precisa pôr `http://127.0.0.1/**` nas Redirect URLs do Supabase.

### Instalador, abertura e prints (27/10/2026)
- Arthur: abrir pelo abrir.bat deixava cmd + Python na barra. abrir.bat agora usa `start "" pythonw` (sem console).
- `.exe`: `--splash` (imagem `gerar_abertura` no empacotar.py) aparece no clique; `janela.fechar_abertura` fecha no
  `events.shown`. O overlay (mesmo .exe, `--overlay`) sobe com `PYINSTALLER_SUPPRESS_SPLASH_SCREEN=1`. Tk vai junto
  (`_tcl_data`/`_tk_data`) mesmo com `--exclude-module tkinter`.
- Instalador: Inno Setup 6 (instalado por winget, com o OK do Arthur), `ferramentas/instalador.iss`, chamado pelo
  empacotar.py (acha o ISCC.exe em %LOCALAPPDATA%\Programs\Inno Setup 6 ou Program Files, ou env ISCC). Por usuário,
  sem admin; AppId fixo (não trocar); InstallDelete do `_internal` velho; desinstalar não mexe em %APPDATA%.
  Testado: instalar silencioso em pasta temporária, abrir, desinstalar. O site baixa o `-Setup-<v>.exe` (cai no zip).
- Prints: `MAXIMO_SEM_DICA = 20` (tela inteira, até ~4 MB cada) além do limite de 200; Configurações mostra
  quantos/quanto ocupam (`Api.capturas`) e "Apagar prints" (dois cliques; `limpar_capturas(maximo=0)`, só os do app).
  A mecânica não muda: recorte continua PNG, o histórico fica (sem miniatura).

### Licença (26/10/2026)
- MIT, em `LICENSE` (titular: Ruthraaz), com aviso de que nomes/ícones do jogo são da Blizzard e o Tesseract tem a
  licença dele. Vai no zip como `LICENSE.txt`; link no rodapé do site (en e pt) e no topo do README.

### Segurança (26/10/2026) — notas
- Pente fino pedido pelo Arthur. Tudo em `tests/test_seguranca.py`; resumo no README ("Segurança e privacidade").
- `src/rede.py`: `ler()` (limite de 20 MB em toda resposta) e `link_seguro()` (abrir_link só https://maxroll.gg).
- BattleTag: nome `[^\W_]{2,12}` + `quote(safe="")` (antes "/" e "." passavam pro caminho da API).
- `capturas/`: `limpar_capturas()` guarda só as 200 imagens mais novas (o print sem dica é a tela inteira).
- Pillow 10.4.0 → 13.0.0 (OSV: dezenas de CVEs na 10.4; 0 na 13.0). Conferir de novo antes de cada versão do .exe.

### Meu herói (BattleTag, 8g) — notas
- `src/heroi.py`: API de perfil `/d3/profile/{Nome-1234}/`, `/hero/{id}`, `/hero/{id}/items`. Funciona com o
  token client_credentials (não precisa de login do jogador). 404 `NOTFOUND` = BattleTag errada/outra região.
- Perfil nunca vai pro cache: `Blizzard.pegar(..., guardar=False)`.
- Item da API → mesmo formato do parser (`item_do_perfil`): qualidade/tipo de `typeName`, linhas
  "Caldesann" ignoradas, `encantado` = linha com `tooltip-icon-enchant` em `attributesHtml`.
- Avaliador: com `encantado`, `sobrando` só pode ser ele (o Místico só troca o mesmo afixo).
- **Não guardar perfil de jogador no repositório**: testes usam dados inventados (`tests/test_heroi.py`).

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
