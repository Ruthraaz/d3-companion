# D3 Companion

App de desktop pessoal pro **Diablo 3**: quando um item cai, você aperta um atalho e o app diz, num selo em cima do jogo, se o item **bate com a sua build** ou não.

O app só **olha a tela** (captura + OCR). Ele não lê a memória do jogo nem se injeta nele, então não viola os termos da Blizzard.

## Como vai funcionar

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
 5. Overlay ──► ✅ "Bate com Dreadlands" / ❌ "Não serve"
```

## Roteiro

| Etapa | O que faz | Status |
|---|---|---|
| 1 | OCR de um print salvo | ✅ funcionando |
| 2 | Parser: texto → item estruturado | ✅ funcionando |
| 3 | Formato de build (JSON) + avaliador | ✅ funcionando |
| 4 | Atalho + captura perto do cursor | ⏳ próxima |
| 5 | Overlay em cima do jogo | |

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
  - Gemas encaixadas no item ainda não são lidas (só conta os soquetes vazios).
  - Um afixo sem número que seja o último da lista seria cortado junto com a descrição.
  - Erros de número do OCR passam direto: `+13% Life` virou `413% Life` (o "+" lido como "4"), `+157` virou `+187`, `+33%` virou `+39%`. O texto não tem como denunciar isso; um dia dá pra testar pré-processamento só na área dos afixos.
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
   python src/avaliador.py samples/set_fiendish_grips.png    # OCR + parser + avaliador
   ```
5. Testes do parser e do avaliador (não precisam do Tesseract, usam os textos salvos em `tests/ocr/`):
   ```
   python -m unittest discover tests
   ```
