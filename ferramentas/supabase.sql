-- D3 Companion — "Salvar builds na nuvem" (Supabase, plano grátis).
--
-- Rodar UMA vez no painel do Supabase: SQL Editor → New query → colar tudo → Run.
-- Pode rodar de novo sem medo: cada parte confere se já existe.
--
-- O que fica guardado: o id da conta (o Supabase cria ao entrar com Discord/Google)
-- e as builds. Nada de e-mail, nome ou foto nesta tabela.
--
-- Quem lê e escreve: o site, com a chave pública (anon/publishable). Ela é pública
-- de propósito; quem protege os dados é o RLS lá embaixo: cada pessoa só enxerga,
-- cria, muda e apaga as PRÓPRIAS builds (user_id = auth.uid()).

create table if not exists public.builds (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null default auth.uid() references auth.users (id) on delete cascade,
  nome       text not null check (char_length(nome) between 1 and 60),
  classe     text not null check (classe in ('Barbarian', 'Crusader', 'Demon Hunter', 'Monk',
                                             'Necromancer', 'Witch Doctor', 'Wizard')),
  -- A build no mesmo formato do link do montador (builds/*.json do app).
  -- Uma build normal tem 2–5 KB; 50 KB é folga de sobra.
  dados      jsonb not null check (jsonb_typeof(dados) = 'object' and octet_length(dados::text) <= 50000),
  criado     timestamptz not null default now(),
  alterado   timestamptz not null default now()
);

create index if not exists builds_user_id on public.builds (user_id);

-- ------------------------------------------------------------ RLS: só o dono

alter table public.builds enable row level security;
alter table public.builds force row level security;

drop policy if exists "dono le"     on public.builds;
drop policy if exists "dono cria"   on public.builds;
drop policy if exists "dono altera" on public.builds;
drop policy if exists "dono apaga"  on public.builds;

-- (select auth.uid()) em vez de auth.uid(): o Postgres calcula uma vez por consulta.
create policy "dono le"     on public.builds for select to authenticated using ((select auth.uid()) = user_id);
create policy "dono cria"   on public.builds for insert to authenticated with check ((select auth.uid()) = user_id);
create policy "dono altera" on public.builds for update to authenticated
  using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy "dono apaga"  on public.builds for delete to authenticated using ((select auth.uid()) = user_id);

-- Visitante sem conta (papel anon) não mexe na tabela de jeito nenhum.
revoke all on public.builds from anon, public;
grant select, insert, update, delete on public.builds to authenticated;

-- ------------------------------------------------------------ limites e datas

-- No máximo 50 builds por conta (o plano grátis tem 500 MB; isso segura abuso).
-- O id e o dono não mudam depois de criados; "alterado" é sempre a hora do servidor.
create or replace function public.builds_antes_de_gravar()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if tg_op = 'INSERT' then
    if (select count(*) from public.builds where user_id = new.user_id) >= 50 then
      raise exception 'Limite de 50 builds por conta.' using errcode = 'check_violation';
    end if;
    new.criado := now();
  else
    new.id := old.id;
    new.user_id := old.user_id;
    new.criado := old.criado;
  end if;
  new.alterado := now();
  return new;
end;
$$;

drop trigger if exists builds_antes_de_gravar on public.builds;
create trigger builds_antes_de_gravar
  before insert or update on public.builds
  for each row execute function public.builds_antes_de_gravar();

-- ------------------------------------------------------------ apagar a conta (LGPD)

-- Botão "Apagar minha conta" do site: apaga a conta de quem chamou (e, pelo
-- "on delete cascade", todas as builds dela). Só a própria conta: auth.uid().
-- security definer porque o papel authenticated não pode mexer em auth.users.
create or replace function public.apagar_minha_conta()
returns void
language plpgsql
security definer
set search_path = ''
as $$
begin
  if auth.uid() is null then
    raise exception 'Precisa estar conectado.' using errcode = 'insufficient_privilege';
  end if;
  delete from auth.users where id = auth.uid();
end;
$$;

revoke all on function public.apagar_minha_conta() from public, anon;
grant execute on function public.apagar_minha_conta() to authenticated;
