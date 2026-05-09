# Gestor de tareas en la nube

Aplicacion Streamlit que integra tres servicios en la nube:

- **Supabase**: guarda las tareas en una tabla relacional.
- **MongoDB Atlas**: guarda comentarios y eventos de bitacora.
- **Streamlit Cloud**: publica la interfaz web desde este repositorio.

La app funciona en modo demo si faltan credenciales. Cuando agregas los secretos reales, usa Supabase y MongoDB automaticamente.

## Ejecutar localmente

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

## Configurar Supabase

1. Crea un proyecto en Supabase.
2. Abre **SQL Editor** y ejecuta `supabase_schema.sql`.
3. Copia la URL del proyecto y una key desde **Project Settings > API**.
4. Guarda esos valores como secretos de Streamlit.

El esquema crea la tabla `tasks` con estados y prioridades controladas.

## Configurar MongoDB Atlas

1. Crea un cluster en MongoDB Atlas.
2. Crea un usuario de base de datos.
3. Habilita acceso de red para tu entorno de despliegue.
4. Copia el connection string `mongodb+srv://...`.

MongoDB usa la base `tarea_semana8` y las colecciones `comments` y `events`.

## Secretos de Streamlit

En local puedes crear `.streamlit/secrets.toml` a partir del ejemplo. No lo subas a Git.

```toml
[supabase]
url = "https://TU-PROYECTO.supabase.co"
key = "TU_SUPABASE_KEY"

[mongodb]
uri = "mongodb+srv://USUARIO:CLAVE@cluster.mongodb.net/?retryWrites=true&w=majority"
database = "tarea_semana8"
comments_collection = "comments"
events_collection = "events"
```

## Desplegar en Streamlit Cloud

1. Sube el repositorio a GitHub.
2. En Streamlit Cloud, crea una app nueva apuntando al repositorio.
3. Define `app.py` como archivo principal.
4. Agrega los secretos anteriores desde la configuracion de la app.
5. Despliega y prueba crear tareas, cambiar estados y agregar comentarios.

Documentacion oficial util:

- Streamlit Cloud: https://docs.streamlit.io/deploy/streamlit-community-cloud
- Secrets en Streamlit: https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management
- Supabase Python: https://supabase.com/docs/reference/python/introduction
- MongoDB Atlas con Python: https://www.mongodb.com/docs/languages/python/pymongo-driver/current/
