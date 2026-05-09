create extension if not exists pgcrypto;

create table if not exists public.tasks (
    id uuid primary key default gen_random_uuid(),
    title text not null,
    owner text default '',
    status text not null default 'Pendiente',
    priority text not null default 'Media',
    due_date date,
    description text default '',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint tasks_status_check check (status in ('Pendiente', 'En progreso', 'Bloqueada', 'Terminada')),
    constraint tasks_priority_check check (priority in ('Alta', 'Media', 'Baja'))
);

create or replace function public.set_updated_at()
returns trigger as $$
begin
    new.updated_at = now();
    return new;
end;
$$ language plpgsql;

drop trigger if exists set_tasks_updated_at on public.tasks;
create trigger set_tasks_updated_at
before update on public.tasks
for each row
execute function public.set_updated_at();

alter table public.tasks enable row level security;

drop policy if exists "tasks_select_policy" on public.tasks;
drop policy if exists "tasks_insert_policy" on public.tasks;
drop policy if exists "tasks_update_policy" on public.tasks;
drop policy if exists "tasks_delete_policy" on public.tasks;

create policy "tasks_select_policy"
on public.tasks for select
using (true);

create policy "tasks_insert_policy"
on public.tasks for insert
with check (true);

create policy "tasks_update_policy"
on public.tasks for update
using (true)
with check (true);

create policy "tasks_delete_policy"
on public.tasks for delete
using (true);

grant usage on schema public to anon, authenticated, service_role;
grant select, insert, update, delete on public.tasks to anon, authenticated, service_role;
