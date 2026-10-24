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

### Depois da versão 1 (nesta ordem)
1. Janela principal (pywebview).
2. Outras classes: só escrever novas builds em JSON, sem mudar código.
3. Importar builds de sites (Maxroll etc.) como tradutores pro formato próprio.
4. Avaliação automática: detectar a dica sozinho, sem atalho.
5. Ler os itens equipados pela API da Battle.net.

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
| 7 | Outras classes: só builds novas em JSON | próxima |

### Etapa 6 — notas
- `python src/janela.py` liga o overlay (`app.py`) como **processo filho**: Qt e pywebview querem a thread
  principal. Desligar usa `taskkill /T` (o python.exe da .venv é lançador; o filho segura o atalho).
- Overlay → janela: `capturas/historico.jsonl` (`src/historico.py`). Janela → .env: `src/config.py`
  (só ATALHO e SELO_SEGUNDOS; o resto do arquivo fica intacto). Build pra tela: `avaliador.ficha_da_build`.
- Página: só `textContent` (nome de item vem do OCR). Fora do pywebview usa dados de exemplo (`apiDeExemplo`).
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
