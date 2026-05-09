from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any

import pandas as pd
import streamlit as st

try:
    import certifi
except ImportError:  # pragma: no cover - handled in the UI
    certifi = None

try:
    from pymongo import MongoClient
    from pymongo.errors import PyMongoError
except ImportError:  # pragma: no cover - handled in the UI
    MongoClient = None
    PyMongoError = Exception

try:
    from supabase import Client, create_client
except ImportError:  # pragma: no cover - handled in the UI
    Client = None
    create_client = None


STATUSES = ["Pendiente", "En progreso", "Bloqueada", "Terminada"]
PRIORITIES = ["Alta", "Media", "Baja"]


@dataclass(frozen=True)
class CloudConfig:
    supabase_url: str
    supabase_key: str
    mongo_uri: str
    mongo_database: str
    mongo_comments_collection: str
    mongo_events_collection: str

    @property
    def supabase_ready(self) -> bool:
        return bool(self.supabase_url and self.supabase_key and create_client)

    @property
    def mongo_ready(self) -> bool:
        return bool(self.mongo_uri and MongoClient)


def read_secret(section: str, key: str, env_name: str, default: str = "") -> str:
    try:
        section_values = st.secrets.get(section, {})
        if key in section_values:
            return str(section_values[key])
        if env_name in st.secrets:
            return str(st.secrets[env_name])
    except Exception:
        pass
    return os.getenv(env_name, default)


def load_config() -> CloudConfig:
    return CloudConfig(
        supabase_url=read_secret("supabase", "url", "SUPABASE_URL"),
        supabase_key=read_secret("supabase", "key", "SUPABASE_KEY"),
        mongo_uri=read_secret("mongodb", "uri", "MONGODB_URI"),
        mongo_database=read_secret("mongodb", "database", "MONGODB_DATABASE", "tarea_semana8"),
        mongo_comments_collection=read_secret(
            "mongodb", "comments_collection", "MONGODB_COMMENTS_COLLECTION", "comments"
        ),
        mongo_events_collection=read_secret("mongodb", "events_collection", "MONGODB_EVENTS_COLLECTION", "events"),
    )


@st.cache_resource(show_spinner=False)
def get_supabase_client(url: str, key: str) -> Any | None:
    if not url or not key or create_client is None:
        return None
    return create_client(url, key)


@st.cache_resource(show_spinner=False)
def get_mongo_database(uri: str, database_name: str) -> Any | None:
    if not uri or MongoClient is None:
        return None

    options: dict[str, Any] = {"serverSelectionTimeoutMS": 5000}
    if certifi is not None:
        options["tlsCAFile"] = certifi.where()

    client = MongoClient(uri, **options)
    client.admin.command("ping")
    return client[database_name]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def seed_demo_data() -> None:
    st.session_state.setdefault(
        "demo_tasks",
        [
            {
                "id": "demo-1",
                "title": "Configurar Supabase",
                "owner": "Equipo",
                "status": "En progreso",
                "priority": "Alta",
                "due_date": str(date.today()),
                "description": "Ejecutar supabase_schema.sql y guardar la URL y key en Streamlit Cloud.",
                "created_at": utc_now_iso(),
            },
            {
                "id": "demo-2",
                "title": "Conectar MongoDB Atlas",
                "owner": "Equipo",
                "status": "Pendiente",
                "priority": "Media",
                "due_date": str(date.today()),
                "description": "Crear el cluster y copiar el connection string en los secretos.",
                "created_at": utc_now_iso(),
            },
        ],
    )
    st.session_state.setdefault(
        "demo_comments",
        {
            "demo-1": [
                {
                    "task_id": "demo-1",
                    "author": "Sistema",
                    "body": "Este comentario se guardara en MongoDB cuando agregues MONGODB_URI.",
                    "created_at": utc_now_iso(),
                }
            ]
        },
    )
    st.session_state.setdefault("demo_events", [])


def normalize_task(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(row.get("id", "")),
        "title": row.get("title", ""),
        "owner": row.get("owner", ""),
        "status": row.get("status", "Pendiente"),
        "priority": row.get("priority", "Media"),
        "due_date": row.get("due_date") or "",
        "description": row.get("description", ""),
        "created_at": row.get("created_at", ""),
    }


def fetch_tasks(supabase: Any | None) -> list[dict[str, Any]]:
    if supabase is None:
        seed_demo_data()
        return [normalize_task(task) for task in st.session_state["demo_tasks"]]

    response = supabase.table("tasks").select("*").order("created_at", desc=True).execute()
    return [normalize_task(task) for task in (response.data or [])]


def create_task(supabase: Any | None, payload: dict[str, Any]) -> None:
    if supabase is None:
        seed_demo_data()
        st.session_state["demo_tasks"].insert(0, {"id": f"demo-{uuid.uuid4().hex[:8]}", **payload, "created_at": utc_now_iso()})
        return

    supabase.table("tasks").insert(payload).execute()


def update_task_status(supabase: Any | None, task_id: str, status: str) -> None:
    if supabase is None:
        seed_demo_data()
        for task in st.session_state["demo_tasks"]:
            if task["id"] == task_id:
                task["status"] = status
                return
        return

    supabase.table("tasks").update({"status": status, "updated_at": utc_now_iso()}).eq("id", task_id).execute()


def delete_task(supabase: Any | None, task_id: str) -> None:
    if supabase is None:
        seed_demo_data()
        st.session_state["demo_tasks"] = [task for task in st.session_state["demo_tasks"] if task["id"] != task_id]
        st.session_state["demo_comments"].pop(task_id, None)
        return

    supabase.table("tasks").delete().eq("id", task_id).execute()


def fetch_comments(mongo_db: Any | None, collection_name: str, task_id: str) -> list[dict[str, Any]]:
    if mongo_db is None:
        seed_demo_data()
        return st.session_state["demo_comments"].get(task_id, [])

    comments = mongo_db[collection_name].find({"task_id": task_id}, {"_id": 0}).sort("created_at", -1)
    return list(comments)


def add_comment(mongo_db: Any | None, collection_name: str, task_id: str, author: str, body: str) -> None:
    comment = {"task_id": task_id, "author": author, "body": body, "created_at": utc_now_iso()}

    if mongo_db is None:
        seed_demo_data()
        st.session_state["demo_comments"].setdefault(task_id, []).insert(0, comment)
        return

    mongo_db[collection_name].insert_one(comment)


def log_event(mongo_db: Any | None, collection_name: str, action: str, detail: str) -> None:
    event = {"action": action, "detail": detail, "created_at": utc_now_iso()}

    if mongo_db is None:
        seed_demo_data()
        st.session_state["demo_events"].insert(0, event)
        return

    mongo_db[collection_name].insert_one(event)


def fetch_events(mongo_db: Any | None, collection_name: str) -> list[dict[str, Any]]:
    if mongo_db is None:
        seed_demo_data()
        return st.session_state["demo_events"][:20]

    return list(mongo_db[collection_name].find({}, {"_id": 0}).sort("created_at", -1).limit(20))


def task_label(task: dict[str, Any]) -> str:
    owner = task["owner"] or "Sin responsable"
    return f"{task['title']} - {owner} - {task['id'][:8]}"


def build_task_dataframe(tasks: list[dict[str, Any]]) -> pd.DataFrame:
    rows = [
        {
            "Titulo": task["title"],
            "Responsable": task["owner"],
            "Estado": task["status"],
            "Prioridad": task["priority"],
            "Fecha limite": task["due_date"],
        }
        for task in tasks
    ]
    return pd.DataFrame(rows)


def render_service_status(config: CloudConfig, supabase: Any | None, mongo_db: Any | None) -> None:
    st.sidebar.header("Servicios")
    st.sidebar.caption("La app usa Streamlit Cloud como hosting, Supabase como base relacional y MongoDB como bitacora.")
    st.sidebar.write(f"Supabase: {'conectado' if supabase is not None else 'modo demo'}")
    st.sidebar.write(f"MongoDB: {'conectado' if mongo_db is not None else 'modo demo'}")
    st.sidebar.write("Streamlit Cloud: listo para desplegar desde GitHub")

    with st.sidebar.expander("Secretos esperados"):
        st.code(
            """[supabase]
url = "https://TU-PROYECTO.supabase.co"
key = "TU_SUPABASE_KEY"

[mongodb]
uri = "mongodb+srv://USUARIO:CLAVE@cluster.mongodb.net/?retryWrites=true&w=majority"
database = "tarea_semana8"
comments_collection = "comments"
events_collection = "events"
""",
            language="toml",
        )

    if not config.supabase_ready:
        st.sidebar.warning("Falta configurar Supabase o instalar sus dependencias.")
    if not config.mongo_ready:
        st.sidebar.warning("Falta configurar MongoDB o instalar sus dependencias.")


def main() -> None:
    st.set_page_config(page_title="Tarea Semana 8", page_icon="cloud", layout="wide")

    config = load_config()
    supabase = None
    mongo_db = None

    try:
        supabase = get_supabase_client(config.supabase_url, config.supabase_key) if config.supabase_ready else None
    except Exception as exc:
        st.sidebar.error(f"No se pudo conectar a Supabase: {exc}")

    try:
        mongo_db = get_mongo_database(config.mongo_uri, config.mongo_database) if config.mongo_ready else None
    except PyMongoError as exc:
        st.sidebar.error(f"No se pudo conectar a MongoDB: {exc}")
    except Exception as exc:
        st.sidebar.error(f"No se pudo inicializar MongoDB: {exc}")

    render_service_status(config, supabase, mongo_db)

    st.title("Gestor de tareas en la nube")
    st.caption("Supabase guarda las tareas, MongoDB guarda comentarios y eventos, y Streamlit Cloud publica la interfaz.")

    if supabase is None or mongo_db is None:
        st.info("La app esta en modo demo hasta que agregues los secretos de Supabase y MongoDB en Streamlit Cloud.")

    try:
        tasks = fetch_tasks(supabase)
    except Exception as exc:
        st.error(f"No se pudieron cargar las tareas desde Supabase: {exc}")
        tasks = fetch_tasks(None)

    total_tasks = len(tasks)
    finished_tasks = sum(1 for task in tasks if task["status"] == "Terminada")
    blocked_tasks = sum(1 for task in tasks if task["status"] == "Bloqueada")

    metric_cols = st.columns(3)
    metric_cols[0].metric("Tareas", total_tasks)
    metric_cols[1].metric("Terminadas", finished_tasks)
    metric_cols[2].metric("Bloqueadas", blocked_tasks)

    task_tab, comment_tab, config_tab = st.tabs(["Tareas", "Comentarios y bitacora", "Configuracion"])

    with task_tab:
        form_col, list_col = st.columns([0.95, 1.45], gap="large")

        with form_col:
            st.subheader("Nueva tarea")
            with st.form("task_form", clear_on_submit=True):
                title = st.text_input("Titulo")
                owner = st.text_input("Responsable")
                status = st.selectbox("Estado", STATUSES)
                priority = st.selectbox("Prioridad", PRIORITIES, index=1)
                due_date = st.date_input("Fecha limite", value=date.today())
                description = st.text_area("Descripcion", height=120)
                submitted = st.form_submit_button("Guardar tarea", use_container_width=True)

            if submitted:
                if not title.strip():
                    st.warning("El titulo es obligatorio.")
                else:
                    payload = {
                        "title": title.strip(),
                        "owner": owner.strip(),
                        "status": status,
                        "priority": priority,
                        "due_date": str(due_date),
                        "description": description.strip(),
                    }
                    try:
                        create_task(supabase, payload)
                        log_event(mongo_db, config.mongo_events_collection, "crear_tarea", f"Tarea creada: {title.strip()}")
                        st.success("Tarea guardada.")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"No se pudo guardar la tarea: {exc}")

        with list_col:
            st.subheader("Tablero")
            status_filter = st.multiselect("Filtrar por estado", STATUSES, default=STATUSES)
            priority_filter = st.multiselect("Filtrar por prioridad", PRIORITIES, default=PRIORITIES)
            filtered_tasks = [
                task
                for task in tasks
                if task["status"] in status_filter and task["priority"] in priority_filter
            ]

            if filtered_tasks:
                st.dataframe(build_task_dataframe(filtered_tasks), use_container_width=True, hide_index=True)
            else:
                st.warning("No hay tareas con esos filtros.")

            if tasks:
                selected_task = st.selectbox("Editar estado", tasks, format_func=task_label)
                next_status = st.selectbox("Nuevo estado", STATUSES, index=STATUSES.index(selected_task["status"]))
                action_cols = st.columns(2)

                if action_cols[0].button("Actualizar estado", use_container_width=True):
                    try:
                        update_task_status(supabase, selected_task["id"], next_status)
                        log_event(
                            mongo_db,
                            config.mongo_events_collection,
                            "actualizar_estado",
                            f"{selected_task['title']} -> {next_status}",
                        )
                        st.success("Estado actualizado.")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"No se pudo actualizar la tarea: {exc}")

                if action_cols[1].button("Eliminar tarea", use_container_width=True):
                    try:
                        delete_task(supabase, selected_task["id"])
                        log_event(
                            mongo_db,
                            config.mongo_events_collection,
                            "eliminar_tarea",
                            f"Tarea eliminada: {selected_task['title']}",
                        )
                        st.success("Tarea eliminada.")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"No se pudo eliminar la tarea: {exc}")

    with comment_tab:
        st.subheader("Comentarios por tarea")
        if not tasks:
            st.warning("Crea una tarea antes de agregar comentarios.")
        else:
            selected_task = st.selectbox("Tarea", tasks, format_func=task_label, key="comment_task")
            comment_author = st.text_input("Autor", value="Equipo")
            comment_body = st.text_area("Comentario", height=110)

            if st.button("Guardar comentario", use_container_width=True):
                if not comment_body.strip():
                    st.warning("El comentario no puede estar vacio.")
                else:
                    try:
                        add_comment(
                            mongo_db,
                            config.mongo_comments_collection,
                            selected_task["id"],
                            comment_author.strip() or "Equipo",
                            comment_body.strip(),
                        )
                        log_event(
                            mongo_db,
                            config.mongo_events_collection,
                            "crear_comentario",
                            f"Comentario agregado a {selected_task['title']}",
                        )
                        st.success("Comentario guardado.")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"No se pudo guardar el comentario: {exc}")

            st.divider()
            comments = fetch_comments(mongo_db, config.mongo_comments_collection, selected_task["id"])
            if comments:
                for comment in comments:
                    st.markdown(f"**{comment.get('author', 'Equipo')}**")
                    st.caption(comment.get("created_at", ""))
                    st.write(comment.get("body", ""))
                    st.divider()
            else:
                st.info("Esta tarea todavia no tiene comentarios.")

        st.subheader("Ultimos eventos")
        events = fetch_events(mongo_db, config.mongo_events_collection)
        if events:
            st.dataframe(pd.DataFrame(events), use_container_width=True, hide_index=True)
        else:
            st.info("Aun no hay eventos registrados.")

    with config_tab:
        st.subheader("Configuracion para entrega")
        st.write("1. Ejecuta `supabase_schema.sql` en el SQL Editor de Supabase.")
        st.write("2. Crea un cluster en MongoDB Atlas y copia el connection string.")
        st.write("3. Sube este repositorio a GitHub.")
        st.write("4. En Streamlit Cloud, crea una app nueva con `app.py` como archivo principal.")
        st.write("5. Copia el contenido de `.streamlit/secrets.toml.example` en los secretos de Streamlit Cloud.")
        st.warning("No subas un archivo real `.streamlit/secrets.toml` al repositorio.")


if __name__ == "__main__":
    main()
