// Ponte do D3 Companion para a API da Blizzard (Supabase Edge Function).
//
// Pra que serve: o jogador não precisa criar chave nenhuma. O app pede
//   GET .../functions/v1/blizzard?caminho=/d3/data/hero/barbarian&locale=pt_BR
// (e &regiao=eu|kr|tw pro perfil de outras regiões; sem regiao = us, Américas)
// e esta função pede à Blizzard com as chaves do dono do projeto, que ficam
// nos "Secrets" do Supabase (BLIZZARD_CLIENT_ID e BLIZZARD_CLIENT_SECRET),
// nunca no Git nem no app.
//
// Proteções:
//   - só caminhos do Diablo 3 que o app usa (lista abaixo); o resto é 400;
//   - só GET; respostas guardadas na memória (dados do jogo 24 h, perfil 5 min);
//   - limite por IP (o índice de itens faz ~135 pedidos de uma vez, por isso
//     o limite é folgado); passou disso, 429.
//
// Publicar: Supabase → Edge Functions → nome "blizzard", com "Verify JWT" desligado.

const URL_TOKEN = "https://oauth.battle.net/token";
const REGIOES = new Set(["us", "eu", "kr", "tw"]);

const CAMINHOS = [
  /^\/d3\/data\/item-type$/,
  /^\/d3\/data\/item-type\/[a-z0-9-]{1,60}$/,
  /^\/d3\/data\/item\/[A-Za-z0-9_-]{1,120}$/,
  /^\/d3\/data\/hero\/[a-z-]{3,20}$/,
  /^\/d3\/data\/hero\/[a-z-]{3,20}\/skill\/[a-z0-9-]{1,60}$/,
  /^\/d3\/data\/follower\/(templar|scoundrel|enchantress)$/,
  /^\/d3\/profile\/[A-Za-z0-9%_-]{3,100}\/(hero\/\d{1,12}(\/items)?)?$/,
];
const LOCALES = new Set(["en_US", "pt_BR"]);

const POR_MINUTO = 240;
const MAXIMO_NO_CACHE = 500;
const DIA = 24 * 60 * 60 * 1000;
const CINCO_MINUTOS = 5 * 60 * 1000;

let token = "";
let tokenVence = 0;
const cache = new Map<string, { corpo: string; vence: number }>();
const pedidosPorIp = new Map<string, { inicio: number; quantos: number }>();

function resposta(status: number, corpo: string, segundos = 0): Response {
  const headers: Record<string, string> = { "Content-Type": "application/json; charset=utf-8" };
  if (segundos) headers["Cache-Control"] = `public, max-age=${segundos}`;
  return new Response(corpo, { status, headers });
}

function erro(status: number, mensagem: string): Response {
  return resposta(status, JSON.stringify({ erro: mensagem }));
}

function passouDoLimite(ip: string): boolean {
  const agora = Date.now();
  const dele = pedidosPorIp.get(ip);
  if (!dele || agora - dele.inicio > 60_000) {
    if (pedidosPorIp.size > 5000) pedidosPorIp.clear(); // não cresce pra sempre
    pedidosPorIp.set(ip, { inicio: agora, quantos: 1 });
    return false;
  }
  dele.quantos++;
  return dele.quantos > POR_MINUTO;
}

async function tokenValido(): Promise<string> {
  if (token && Date.now() < tokenVence) return token;
  const id = Deno.env.get("BLIZZARD_CLIENT_ID") ?? "";
  const segredo = Deno.env.get("BLIZZARD_CLIENT_SECRET") ?? "";
  if (!id || !segredo) throw new Error("faltam os secrets BLIZZARD_CLIENT_ID e BLIZZARD_CLIENT_SECRET");
  const r = await fetch(URL_TOKEN, {
    method: "POST",
    headers: {
      Authorization: "Basic " + btoa(`${id}:${segredo}`),
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: "grant_type=client_credentials",
  });
  if (!r.ok) throw new Error(`token: ${r.status}`);
  const dados = await r.json();
  token = dados.access_token;
  tokenVence = Date.now() + ((dados.expires_in ?? 3600) - 60) * 1000;
  return token;
}

Deno.serve(async (pedido) => {
  if (pedido.method !== "GET") return erro(405, "só GET");

  const parametros = new URL(pedido.url).searchParams;
  const caminho = parametros.get("caminho") ?? "";
  const locale = parametros.get("locale") ?? "en_US";
  const regiao = parametros.get("regiao") ?? "us";
  if (!LOCALES.has(locale) || !REGIOES.has(regiao) || !CAMINHOS.some((c) => c.test(caminho))) {
    return erro(400, "caminho não permitido");
  }

  const ip = (pedido.headers.get("x-forwarded-for") ?? "").split(",")[0].trim() || "?";
  if (passouDoLimite(ip)) return erro(429, "muitos pedidos; tente de novo em um minuto");

  const ehPerfil = caminho.startsWith("/d3/profile/");
  const chave = `${regiao} ${locale} ${caminho}`;
  const url = `https://${regiao}.api.blizzard.com${caminho}?locale=${locale}`;
  const guardado = cache.get(chave);
  if (guardado && Date.now() < guardado.vence) return resposta(200, guardado.corpo);

  try {
    let r = await fetch(url, {
      headers: { Authorization: "Bearer " + (await tokenValido()) },
    });
    if (r.status === 401) { // token venceu antes da hora: pede outro uma vez
      token = "";
      r = await fetch(url, {
        headers: { Authorization: "Bearer " + (await tokenValido()) },
      });
    }
    if (r.status === 404) return erro(404, "a Blizzard não conhece esse caminho");
    if (!r.ok) return erro(502, `a Blizzard respondeu ${r.status}`);
    const corpo = await r.text();
    if (cache.size >= MAXIMO_NO_CACHE) cache.delete(cache.keys().next().value!); // sai o mais velho
    cache.set(chave, { corpo, vence: Date.now() + (ehPerfil ? CINCO_MINUTOS : DIA) });
    return resposta(200, corpo, ehPerfil ? 0 : 3600);
  } catch (e) {
    console.error(e);
    return erro(502, "não consegui falar com a Blizzard");
  }
});
