// Nuvem do montador (contas pelo Supabase, só pra salvar builds).
// Vazio = sem contas: os botões da nuvem nem aparecem e o montador funciona igual.
//
// Pra ligar, rode na pasta do projeto (ele preenche aqui E libera o endereço na CSP do montar.html):
//   python ferramentas/nuvem.py https://SEU-PROJETO.supabase.co SUA_CHAVE_PUBLICA
//
// Só a chave PÚBLICA: "anon" (começa com eyJ...) ou "publishable" (sb_publishable_...).
// Ela é feita pra ficar no site; quem protege os dados é o RLS (ferramentas/supabase.sql).
// A "service_role" ou "secret" (sb_secret_...) NUNCA vai aqui nem em lugar nenhum do repositório.
window.D3C_NUVEM = { url: "", chave: "" };
