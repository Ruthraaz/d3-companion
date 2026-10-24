# D3 Companion

App de desktop pessoal pro **Diablo 3**: quando um item cai, você aperta um atalho e o app diz, num selo em cima do jogo, se o item **bate com a sua build** ou não.

O app só **olha a tela** (captura + OCR). Ele não lê a memória do jogo nem se injeta nele, então não viola os termos da Blizzard.

![Selo do overlay ao lado da dica do item](docs/previa_selo.png)

## Como funciona

```
[F8 com o mouse no item]
        │
        ▼
 1. Captura da tela perto do cursor
        │
        ▼
 2. OCR (Tesseract) ──► texto cru da dica
        │
        ▼
 3. Parser ──► item estruturado (nome, tipo, atributos)
        │
        ▼
 4. Avaliador ──► compara com as builds (arquivos JSON)
        │
        ▼
 5. Overlay ──► ✅ Dreadlands · Destreza ✓ Crítico ✓ Encaixe ✗
```

A lógica (OCR, parser, avaliador) fica num **núcleo** sem interface (`src/nucleo.py`); o overlay só desenha o que o núcleo entrega.

## Roteiro

| Etapa | O que faz | Status |
|---|---|---|
| 1 | OCR de um print salvo | ✅ funcionando |
| 2 | Parser: texto → item estruturado | ✅ funcionando |
| 3 | Formato de build (JSON) + avaliador | ✅ funcionando |
| 4 | Atalho + captura perto do cursor | ✅ funcionando |
| 5 | Overlay em cima do jogo | ✅ funcionando |
| | **Versão 1:** testar tudo dentro do jogo | ✅ testada em 24/10/2026 |
| 6 | Janela principal (pywebview): builds no boneco, histórico, configurações | ✅ primeira versão |
| 7 | Outras classes (só JSON de build novo) + conferência das builds | ✅ funcionando |
| 8 | Importar builds de sites (Maxroll etc.) | ⏳ próxima |

## O que aprendemos na Etapa 1

- **O OCR lê bem os atributos.** Nome do item, tipo, Destreza, Vitalidade e afixos saíram quase perfeitos.
- **Pré-processar nem sempre ajuda.** Converter pra preto e branco (Otsu) apagou partes de textos finos: `-0.5% Damage` virou `-C.2°. Damage`. Por enquanto, a imagem crua vai melhor.
- **A fonte dos títulos troca "O" por "@"** (`THE CL@AK @F THE GARWULF`). O parser vai ter que corrigir isso.
- **O sinal de menos às vezes some** (`-26.8%` virou `26.8%`). Nos números de "Stat Changes", isso importa.
- **O recorte é essencial.** Quando o print pega a tela de personagem do lado, o OCR mistura tudo. Na Etapa 4, a captura precisa pegar só a dica.

## Etapa 2: o parser

`src/parser.py` transforma o texto do OCR num item em JSON: nome, qualidade, tipo, encaixe, classe, armadura ou DPS/dano, afixos primários e secundários, soquetes e nível. Funciona com itens **lendários, de set e raros**. Itens de set trazem o nome do set e a lista de peças:

```json
"set": { "nome": "Gears of Dreadlands",
         "pecas": [ { "nome": "Antique Vintage Boots", "slot": "Feet" }, ... ] }
```

Gemas lendárias saem com rank e efeitos (o efeito do rank 25 vem marcado com `requer_rank`).

Cada afixo vem com um **modelo** (os números trocados por `#`), que é o que o avaliador da Etapa 3 vai comparar com a build:

```json
{ "texto": "+458 Dexterity", "modelo": "+# Dexterity", "valores": [458] }
```

**Decisões e o que aprendemos:**

- **"Stat Changes if Equipped" é ignorado.** O app compara o item com a build, não com o item equipado. De quebra, some o problema do sinal de menos.
- **O lixo fica nas bordas das linhas.** Marcadores de afixo viram `©`, `@`, `*`, e pedaços do cenário grudam no fim (`+1015-1214 Fire Damage iA`). O parser corta isso.
- **Afixos longos quebram em duas linhas** (`...(Demon Hunter` / `Only)`). O parser junta.
- **Correções de palavras** ficam em `CORRECOES` (`Lite`/`Lie` → `Life`, `Kil` → `Kill`, `ofall` → `of all`...). Quando aparecer um erro novo do OCR, é só adicionar lá.
- **A descrição em itálico não vira afixo.** Quando não há "Stat Changes" separando (item já equipado), o parser descarta as linhas do fim da seção que não têm número nem começam com "+". Só corta do fim, pra não perder um afixo sem número no meio da lista (ex.: "Ignores Durability Loss").
- **Sets: a lista de peças é o ponto de apoio.** O OCR lê muito bem a lista (`Nome (Encaixe)`), e o nome do set é a linha logo acima dela. Os afixos acabam ali, então os bônus `(2) Set:` nunca viram afixo.
- **Nome de item de set vem da lista de peças.** O título usa a fonte decorada e sai embaralhado (`LITANY)@FeTHE/UNDAUNTED`), mas a própria peça está na lista em fonte normal. O parser escolhe a peça mais parecida com o título.
- **Raros e mágicos ficam sem nome** (`null`). O nome é aleatório (`Vampiric Source`), sai embaralhado (`LVAmpiRIseURCE`) e não serve pra avaliar o item.
- **Limitações conhecidas:**
  - Gema **lendária** encaixada conta como encaixe (linha `Nome - Rank N`), e os efeitos dela não viram afixo. Gema **comum** encaixada (ex.: diamante no elmo, "Reduces cooldown...") ainda não: o texto dela é igual ao de um afixo, e só o ícone denuncia.
  - Um afixo sem número que seja o último da lista seria cortado junto com a descrição. Os conhecidos ficam numa lista (`AFIXOS_SEM_NUMERO`, ex.: "Ignores Durability Loss").
  - Erros de número do OCR passam direto: `+13% Life` virou `413% Life` (o "+" lido como "4"), `+157` virou `+187`, `+33%` virou `+39%`. O texto não tem como denunciar isso. **Resolvido na Etapa 4:** com o recorte da dica e o OCR ampliado 2x, os três saem certos.
  - Às vezes a armadura sai `null` (o OCR não leu "Armor" ou separou os dígitos: `5 8 1`). O parser prefere `null` a um número errado.

## Etapa 3: builds e avaliador

As builds ficam em `builds/*.json`, num **formato próprio** do app. Se um dia entrarem builds de sites (Maxroll, Icy Veins), elas serão só *traduzidas* pra esse formato; o avaliador (`src/avaliador.py`) só conhece ele.

```json
{
  "formato": 1,
  "nome": "Gears of Dreadlands — Metralhar",
  "classe": "Demon Hunter",
  "exige_ancient": false,
  "todos_os_espacos": { "obrigatorios": ["+# Dexterity"], "desejaveis": ["+# Vitality"] },
  "espacos": {
    "Head":   { "itens": ["Dystopian Goggles"],
                "desejaveis": ["@soquete", "Critical Hit Chance Increased by #%"] },
    "Finger": { "itens": [],
                "desejaveis": ["@soquete", "Critical Hit Damage Increased by #%"] }
  },
  "gemas": ["Bane of the Trapped", "Zei's Stone of Vengeance"]
}
```

- **`espacos`** usa os nomes do jogo/parser (`Head`, `Hands`, `Finger`...). `Weapon` vale pra `1-Hand` e `2-Hand`.
- **`itens`**: quais itens servem no espaço. Lista vazia = qualquer item, desde que tenha os afixos.
- **`todos_os_espacos`**: afixos que valem pra todo espaço (Destreza sempre primeiro).
- **Afixos** usam o `modelo` do parser. `*` vale por qualquer palavra (`+# * Resistance` aceita Cold, Fire...). `@soquete` olha os soquetes do item. Pra exigir um valor: `{ "modelo": "+# Dexterity", "minimo": 400 }`.
- **`exige_ancient`** pode ser trocado por espaço (no Legacy of Nightmares, os anéis do set não precisam ser Ancient).

**Como o avaliador decide:** o item **bate** quando é permitido no espaço, tem todos os obrigatórios, é Ancient (se exigido) e não é de outra classe. A **nota** é a fração dos desejáveis que ele tem (0 a 1). Quando não bate, o `motivo` diz a primeira regra que falhou.

```
Fiendish Grips — Set Gloves
✅ Unhallowed Essence — Multidisparo: Item da build: Fiendish Grips (nota 0.67)
     tem: +# Vitality, Critical Hit Chance Increased by #%
❌ Gears of Dreadlands — Metralhar: A build pede: Gas Powered Automail Forearm (nota 0.67)
❌ Legacy of Nightmares: Precisa ser Ancient (nota 0.67)
```

**A revisar nas builds:** só as peças dos sets (vistas nos prints) estão preenchidas; os outros espaços estão com `itens: []`. As **gemas** são um palpite inicial. A prioridade de afixos segue a referência geral do Icy Veins.

## Etapa 4: atalho e captura

`src/app.py` espera o **F8**. Ao apertar, tira um print de uma faixa da tela em volta do mouse, recorta só a dica (`src/captura.py`), lê com OCR e mostra no terminal o veredito de cada build. Cada recorte fica salvo em `capturas/` (fora do Git) pra investigar erros e virar exemplo de teste.

O atalho usa o `RegisterHotKey` do próprio Windows: nada de ler memória ou se injetar no jogo.

**Como a dica é achada:** o miolo da dica é quase **preto puro** (valores 0–4) e as bordas da esquerda e da direita são linhas claras que vão de cima a baixo. O app procura um **par de colunas** com linhas claras longas e da mesma altura, com o miolo majoritariamente preto entre elas, e sem outra borda longa no meio. Se houver duas dicas (a do item e a do equipado), fica com a mais perto do mouse.

**O que aprendemos (medido nos 9 prints, contra um gabarito conferido nas imagens):**

| Como o OCR recebe a imagem | Acertos (afixos + nomes + armadura) |
|---|---|
| Imagem inteira (como era antes) | 49/53 |
| Recorte justo da dica | 40/53 |
| Recorte + folga de 70 px em cima | 44/53 |
| **Recorte + folga + ampliar 2x** | **52/53** |

- **"A maior área preta" não funciona.** O fundo do jogo e as grades do inventário encostam na dica e a área vaza pra tela toda. As bordas verticais são o que separa a dica do resto.
- **O título fica acima das bordas laterais** (nos itens de set), então o recorte precisa de folga em cima.
- **"Linha clara longa" também engana (visto no jogo).** Quando a dica encosta no painel do inventário, a moldura do painel emenda na borda da dica e a "borda" subia até o topo da tela. Agora um pixel só conta como borda se a **maioria dos 10 pixels ao lado (pra dentro) for preta**: ao lado do miolo da dica são 7–10; ao lado da grade do inventário, ~3. No topo, o enfeite do banner do título tapa o miolo, então a borda é esticada pra cima enquanto o vão estreito da moldura dupla continua preto. O print real ficou em `samples/jogo_zei_abaixo_do_inventario.png`, com teste.
- **Ampliar 2x foi o que mais ajudou.** Com isso, todos os afixos e nomes saem certos, inclusive os números que antes saíam errados (`413% Life` → `+13% Life`, `+187` → `+157`). Ampliar 3x piorou.
- **A moldura do título vira letra solta** (`E PAIN ENHANCER`). O parser descarta letra isolada nas pontas do nome.
- A armadura (número grande, fonte serifada) ainda falha às vezes; o parser devolve `null` em vez de um número errado.

## Etapa 5: o overlay

`src/overlay.py` (PySide6) desenha o **selo**: fundo escuro semitransparente, borda verde (serve) ou vermelha (não serve), nome da build em dourado e os afixos com ✓/✗. Ele aparece **à direita da dica** (ou à esquerda, se não couber) e some sozinho depois de `SELO_SEGUNDOS` (padrão 6, ajustável no `.env`).

O selo é uma janela separada do jogo: fica sempre por cima, **deixa o clique passar** e **nunca pega o foco** — senão o jogo em tela cheia poderia minimizar. Antes de cada print, o selo anterior é escondido pra não confundir a detecção da dica.

**Rótulos e apelidos nas builds:** pra caber no selo, cada afixo pode ter um `rotulo` curto e cada build um `apelido`:

```json
"apelido": "Dreadlands",
"obrigatorios": [{ "modelo": "+# Dexterity", "rotulo": "Destreza" }]
```

Sem `rotulo`, o selo mostra o próprio modelo; sem `apelido`, o nome da build. Tudo fica no JSON, nada no código.

**Primeiro teste no jogo (24/10/2026):** gemas e equipamentos com selo certo. Três problemas apareceram e viraram testes com os prints reais (`samples/jogo_*.png`):
- **Dica encostada no inventário** não era achada (veja a Etapa 4).
- **"Hallowed Condemnation" saía "Condemnation"**: o afixo "Ignores **Durability** Loss" era confundido com o rodapé "Durability: 29/29" e a leitura parava antes da lista do set. Agora o fim é `Durability:` com dois-pontos.
- **O selo tampava a dica do item equipado** quando o jogo mostra as duas lado a lado pra comparar. Agora o app acha as dicas coladas na do item e põe o selo do lado de fora do grupo.
- E uma gema lendária encaixada virava afixo do item e não contava como encaixe.

**Como as partes conversam:** o F8 é ouvido numa thread separada, que faz o trabalho pesado (print + OCR, ~1 s) sem travar a interface e manda o resultado pro selo por um *sinal* do Qt. O núcleo (`src/nucleo.py`) monta o texto e a posição do selo sem depender de interface, então tudo isso tem teste sem abrir janela.

## Etapa 6: a janela principal

`python src/janela.py` abre a janela e **liga o overlay junto** (fechar a janela desliga os dois). Três abas:

- **Escolher a build:** clicar numa build faz o atalho avaliar **só com ela** (o selo fala só dela); "Todas" avalia com todas. Vale na hora, sem reiniciar: a escolha vai pro `.env` (`BUILD_ATIVA`) e o overlay relê a cada F8. O histórico mostra com qual build cada item foi avaliado.
- **Builds:** cada build num "boneco" com os 12 espaços. Verde = a build pede um item específico; dourado = qualquer item com os afixos; tracejado = a build não fala do espaço, então valem só as regras gerais (`todos_os_espacos`). Clicando num espaço aparecem os afixos obrigatórios, os desejáveis e as gemas.
- **Histórico:** cada item avaliado no jogo, com a miniatura do recorte e o mesmo selo do overlay. Filtro "Serve / Não serve". Item novo chega sozinho (a janela confere a cada 1,5 s).
- **Configurações:** atalho e tempo do selo, gravados no `.env` (o resto do arquivo fica intacto). Valor inválido não é gravado e a mensagem diz o porquê. As mensagens do overlay (ex.: "F8 ocupado") aparecem aqui também.

**Como as partes conversam.** O overlay (Qt) e a janela (pywebview) querem, os dois, a thread principal — então são **dois processos**. A janela liga o `app.py` como processo filho; o overlay grava cada avaliação em `capturas/historico.jsonl` (uma linha JSON por item) e a janela lê esse arquivo. O JavaScript chama o Python pela ponte do pywebview (`window.pywebview.api`). Nada de rede nem servidor.

**O que aprendemos:**
- **O `python.exe` da `.venv` é só um lançador:** ele abre *outro* `python.exe`, e é esse filho que segura o atalho. Desligar só o processo que a janela abriu deixava o F8 ocupado; por isso o desligamento usa `taskkill /T` (derruba a árvore).
- **Espaço que a build não define não é "não serve".** O avaliador ainda aplica as regras gerais nele (ex.: Destreza). A primeira versão da tela dizia o contrário; a `ficha_da_build` (no avaliador, testada) agora devolve os 12 espaços com `definido: true/false`.
- **Nome de item vem do OCR**, então a página monta tudo com `textContent`, nunca `innerHTML`.
- **Aberta no navegador comum, a página usa dados de exemplo** — dá pra mexer no visual sem jogo nem app.

## Etapa 7: outras classes

O código não tem nada fixo de Demon Hunter: o que muda de uma classe pra outra (atributo principal, itens, gemas) está todo no JSON da build. Pra jogar de outra classe:

1. Copie `builds/exemplos/modelo_barbaro.json` para `builds/` com outro nome (ex.: `builds/barbaro_redemoinho.json`). A pasta `exemplos/` não é carregada pelo app.
2. Troque `classe` (`Barbarian`, `Crusader`, `Demon Hunter`, `Monk`, `Necromancer`, `Witch Doctor`, `Wizard`), o atributo principal (`+# Strength`, `+# Intelligence`, `+# Dexterity`) e os itens e gemas, com os nomes em inglês, do jeito que o jogo mostra.
3. Confira:
   ```
   python src/avaliador.py --conferir
   ```

Chave que começa com `_` é comentário (`"_nota": "..."`): o JSON não tem comentário de verdade e o app ignora essas chaves.

**A conferência das builds.** Antes, um JSON errado tinha dois jeitos de dar problema: uma vírgula faltando **derrubava o app inteiro**, e um erro de digitação (`"Hand"` no lugar de `"Hands"`, `"desejavel"` no lugar de `"desejaveis"`) fazia a regra **sumir calada**, e o item passava a "servir" sem você saber por quê. Agora toda build é conferida ao carregar:
- build com problema **fica de fora** e as outras continuam funcionando;
- o problema aparece no terminal do overlay e num aviso vermelho na aba Builds, em português e com sugestão (`Espaço 'Hand' não existe. Quis dizer 'Hands'?`);
- JSON quebrado diz a linha e a coluna.

O que a conferência **não** pega: um `modelo` escrito certo no formato mas que não bate com nenhum afixo do jogo (ex.: `"+# Strenght"`). Pra isso não tem lista oficial de afixos no projeto; o jeito é testar com um print (`python src/avaliador.py <print.png>`).

## Como rodar (Windows)

O projeto usa **Python 3.12**. Versões mais novas (ex.: 3.15) não têm pacotes prontos para as versões fixadas no `requirements.txt` (Pillow 10.4, NumPy 1.26).

1. Instale o **Python 3.12** e o **Tesseract** (instalador da UB Mannheim):
   ```
   winget install --id Python.Python.3.12 -e
   winget install --id UB-Mannheim.TesseractOCR -e
   ```
2. No terminal, dentro da pasta do projeto:
   ```
   py -3.12 -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```
3. Se o Tesseract não estiver em `C:\Program Files\Tesseract-OCR\`, copie `.env.example` para `.env` e ajuste o `TESSERACT_CMD` com o caminho certo.
4. Rode:
   ```
   python src/ocr.py samples/lendario_cloak_garwulf.png      # só o OCR (texto cru)
   python src/parser.py samples/lendario_cloak_garwulf.png   # OCR + parser (JSON)
   python src/avaliador.py samples/set_fiendish_grips.png    # recorte + OCR + parser + avaliador
   python src/app.py --testar samples/set_fiendish_grips.png # mostra o selo desse print no meio da tela
   ```
5. **No jogo:** deixe o Diablo 3 em **Tela cheia em janela** (Windowed Fullscreen), rode `python src/janela.py` (janela + overlay) ou só `python src/app.py` (só o overlay), passe o mouse num item e aperte **F8**. O selo aparece ao lado da dica (e o resumo no terminal).
   Se outro programa já usar o F8, o app avisa quais teclas estão livres; troque com `ATALHO=` no `.env` (ex.: `ATALHO=Ctrl+F8`).
6. Testes (não precisam do Tesseract, usam os textos salvos em `tests/ocr/` e `tests/ocr_recorte/`):
   ```
   python -m unittest discover tests
   ```
