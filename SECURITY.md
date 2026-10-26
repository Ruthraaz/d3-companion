# Segurança

## Achou uma falha? Conte em particular

**Não abra issue pública.** Use o botão **Report a vulnerability** na aba
[Security](https://github.com/Ruthraaz/d3-companion/security/advisories/new) do repositório:
só quem cuida do projeto vê. Diga o que acontece, como repetir e qual versão.
A resposta vem o quanto antes, e a correção sai numa versão nova.

*Found a security issue? Please report it privately through
[Security → Report a vulnerability](https://github.com/Ruthraaz/d3-companion/security/advisories/new),
not as a public issue.*

## Versões cuidadas

Só a versão mais nova (a da página de [Releases](https://github.com/Ruthraaz/d3-companion/releases/latest)).

## O que o D3 Companion faz (e não faz)

- **Só olha a tela** quando você aperta o atalho (captura + OCR). Não lê a memória do jogo,
  não se injeta nele e não mexe no DirectX.
- **Suas chaves da Blizzard** ficam só no `.env` do seu PC (`%APPDATA%\D3 Companion`), nunca no
  GitHub, no site ou nos logs.
- **Internet:** só a API oficial da Blizzard, o Maxroll (quando você cola um link ou abre um guia)
  e o GitHub (ver a versão nova). Toda resposta tem limite de tamanho.
- **Builds de fora** (link do Maxroll, link do site, aba Montar) são conferidas antes de gravar:
  endereço, tamanho, formato e nome de arquivo seguro.
- **Site** (GitHub Pages): sem servidor, sem cadastro, sem cookies, sem rastreador. A build
  montada fica no seu navegador e, no link, depois do `#` (que o navegador não manda pra servidor
  nenhum). Cada página tem CSP: só scripts do próprio site, nada de script inline.

O app não é assinado digitalmente (por isso o SmartScreen avisa). Baixe só da página de
Releases deste repositório e confira o SHA-256 que vem nas notas da versão.
