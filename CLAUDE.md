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
| 3 | Formato de build em JSON + avaliador | próxima |
| 4 | Atalho global + captura perto do cursor | |
| 5 | Overlay em cima do jogo (PySide6) | |

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

## Forma de trabalhar
- Ao fim de cada etapa: rode os testes, atualize o README (roteiro e "o que aprendemos"),
  faça commit e push. Mensagens de commit em português.
- Só uma sessão mexe no repositório por vez. Antes de começar, rode `git pull`.
