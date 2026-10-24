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
| 3 | Formato de build (JSON) + avaliador | ⏳ próxima |
| 4 | Atalho + captura perto do cursor | |
| 5 | Overlay em cima do jogo | |

## O que aprendemos na Etapa 1

- **O OCR lê bem os atributos.** Nome do item, tipo, Destreza, Vitalidade e afixos saíram quase perfeitos.
- **Pré-processar nem sempre ajuda.** Converter pra preto e branco (Otsu) apagou partes de textos finos: `-0.5% Damage` virou `-C.2°. Damage`. Por enquanto, a imagem crua vai melhor.
- **A fonte dos títulos troca "O" por "@"** (`THE CL@AK @F THE GARWULF`). O parser vai ter que corrigir isso.
- **O sinal de menos às vezes some** (`-26.8%` virou `26.8%`). Nos números de "Stat Changes", isso importa.
- **O recorte é essencial.** Quando o print pega a tela de personagem do lado, o OCR mistura tudo. Na Etapa 4, a captura precisa pegar só a dica.

## Etapa 2: o parser

`src/parser.py` transforma o texto do OCR num item em JSON: nome, qualidade, tipo, encaixe, classe, armadura ou DPS/dano, afixos primários e secundários, soquetes e nível. Gemas lendárias saem com rank e efeitos (o efeito do rank 25 vem marcado com `requer_rank`).

Cada afixo vem com um **modelo** (os números trocados por `#`), que é o que o avaliador da Etapa 3 vai comparar com a build:

```json
{ "texto": "+458 Dexterity", "modelo": "+# Dexterity", "valores": [458] }
```

**Decisões e o que aprendemos:**

- **"Stat Changes if Equipped" é ignorado.** O app compara o item com a build, não com o item equipado. De quebra, some o problema do sinal de menos.
- **O lixo fica nas bordas das linhas.** Marcadores de afixo viram `©`, `@`, `*`, e pedaços do cenário grudam no fim (`+1015-1214 Fire Damage iA`). O parser corta isso.
- **Afixos longos quebram em duas linhas** (`...(Demon Hunter` / `Only)`). O parser junta.
- **Correções de palavras** ficam em `CORRECOES` (por enquanto só `Lite` → `Life`). Quando aparecer um erro novo do OCR, é só adicionar lá.
- **Limitações conhecidas:** gemas encaixadas no item ainda não são lidas (só conta os soquetes vazios); e se a dica não tiver "Stat Changes" (item já equipado), o texto em itálico da descrição pode entrar como afixo.

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
   ```
5. Testes do parser (não precisam do Tesseract, usam os textos salvos em `tests/ocr/`):
   ```
   python -m unittest discover tests
   ```
