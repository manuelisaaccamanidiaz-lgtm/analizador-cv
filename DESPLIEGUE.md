# 🚀 Guía de despliegue — Analizador de CV

Esta guía explica cómo **publicar** la aplicación para que otras personas la usen con un enlace. No es necesaria para la entrega del taller: es el paso siguiente.

## 🧠 La idea en 30 segundos

En desarrollo, la app corre en **tu** computador: tú lanzas Streamlit a mano, el código se monta desde tu carpeta y las claves están en tu `.env`. **Desplegar** significa llevarla a un servidor que esté encendido siempre, con estas diferencias:

| | Desarrollo (hoy) | Producción (desplegada) |
| --- | --- | --- |
| Código | Montado desde tu carpeta (`.:/app`) | **Copiado dentro de la imagen** |
| Arranque | `sleep infinity` + `streamlit run` a mano | Streamlit arranca **solo** al iniciar el contenedor |
| Claves | `cv_analyzer/.env` en tu PC | Variables de entorno o *secrets* del servidor (nunca en el repositorio) |
| Base de datos | PostgreSQL con contraseña por defecto | Contraseña fuerte, respaldos y sin exponer el puerto |
| Acceso | Solo tú (`localhost`) | Cualquiera con el enlace → hay que pensar en **seguridad** |

> 🏠 **Analogía:** desarrollar es cocinar en tu casa; desplegar es abrir un restaurante. La receta es la misma, pero ahora necesitas horario fijo, cerradura, inventario y respaldo por si algo se daña.

---

## 🧭 Elegir una opción

| Opción | Ideal para | PostgreSQL | Ollama | Dificultad |
| --- | --- | --- | --- | --- |
| **A. Servidor propio con Docker Compose** | Usar el proyecto tal como está (app + base de datos) | ✅ Incluida en el compose | ✅ Si el servidor tiene Ollama | Media |
| **B. Streamlit Community Cloud** | Una demo rápida para mostrar | ⚠️ Necesitas una base PostgreSQL externa | ❌ No (no hay Ollama en la nube) | Baja |

---

## 🅰️ Opción A: servidor propio con Docker Compose

Sirve para cualquier servidor Linux con Docker: una máquina virtual en la nube, un servidor de la empresa o un computador que quede encendido.

### 1. Imagen de producción

La documentación oficial de Streamlit para Docker recomienda `python:3.12-slim`, una carpeta de trabajo (`/app`), exponer el puerto 8501, un `HEALTHCHECK` contra `/_stcore/health` y arrancar con `--server.address=0.0.0.0`. Aplicado a este proyecto, un `Dockerfile.prod` en la raíz quedaría así:

```dockerfile
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# 1) Dependencias primero: Docker reutiliza esta capa si solo cambia el código
COPY cv_analyzer/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 2) El código se COPIA dentro de la imagen (en desarrollo se montaba)
COPY cv_analyzer/ .

# 3) No ejecutar como root
RUN useradd --create-home appuser && chown -R appuser /app
USER appuser

EXPOSE 8501

# 4) Docker comprueba que la app responda (endpoint de salud de Streamlit)
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')"

# 5) Streamlit arranca solo
ENTRYPOINT ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
```

**¿Por qué cada línea?**
- `COPY` del código en vez de montarlo: el servidor no tiene tu carpeta, así que todo debe viajar dentro de la imagen.
- `.dockerignore` ya excluye `**/.env`: las claves **nunca** quedan dentro de la imagen.
- `USER appuser`: si alguien encontrara una falla en la app, no tendría permisos de administrador dentro del contenedor.
- El `HEALTHCHECK` usa Python en lugar de `curl` porque la imagen `slim` no trae `curl`.

### 2. Compose de producción

Un `docker-compose.prod.yml` en la raíz:

```yaml
services:
  app:
    build:
      context: .
      dockerfile: Dockerfile.prod
    restart: unless-stopped              # si el servidor se reinicia, la app vuelve sola
    ports:
      - "8501:8501"
    env_file:
      - cv_analyzer/.env                 # claves de la IA (el archivo vive SOLO en el servidor)
    environment:
      DATABASE_URL: postgresql+psycopg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB}
    depends_on:
      db:
        condition: service_healthy

  db:
    image: postgres:17-alpine
    restart: unless-stopped
    environment:
      POSTGRES_USER: ${POSTGRES_USER:?Define POSTGRES_USER en .env}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?Define POSTGRES_PASSWORD en .env}
      POSTGRES_DB: ${POSTGRES_DB:?Define POSTGRES_DB en .env}
    volumes:
      - datos_postgres:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U $${POSTGRES_USER} -d $${POSTGRES_DB}"]
      interval: 5s
      timeout: 5s
      retries: 10
    # Sin "ports": la base de datos solo es accesible desde la app

volumes:
  datos_postgres:
```

Diferencias con el compose de desarrollo:
- **Sin** `volumes: .:/app` ni `sleep infinity`: el código está en la imagen y Streamlit arranca solo.
- `${VARIABLE:?mensaje}` hace que Compose **se niegue a arrancar** si falta la contraseña, en vez de usar una por defecto.
- `restart: unless-stopped` mantiene los servicios encendidos.

### 3. Pasos en el servidor

```bash
# 1. Traer el código
git clone https://github.com/<tu-usuario>/<tu-repo>.git
cd <tu-repo>

# 2. Crear los secretos (NO vienen en el repositorio)
cp .env.example .env                           # POSTGRES_USER, POSTGRES_PASSWORD (fuerte), POSTGRES_DB
cp cv_analyzer/.env.example cv_analyzer/.env   # claves y modelos de la IA

# 3. Construir y arrancar
docker compose -f docker-compose.prod.yml up -d --build

# 4. Verificar
docker compose -f docker-compose.prod.yml ps    # ambos servicios "healthy"
docker compose -f docker-compose.prod.yml logs -f app
```

La app queda en `http://IP-DEL-SERVIDOR:8501`.

### 4. Actualizar a una nueva versión

```bash
git pull
docker compose -f docker-compose.prod.yml up -d --build   # reconstruye la app; la base y sus datos se conservan
```

### 5. Respaldos de la base de datos 💾

```bash
# Crear un respaldo
docker compose -f docker-compose.prod.yml exec db pg_dump -U <usuario> <base> > respaldo_$(date +%F).sql

# Restaurar un respaldo
docker compose -f docker-compose.prod.yml exec -T db psql -U <usuario> <base> < respaldo_2026-11-12.sql
```

⚠️ `docker compose down -v` **borra el volumen** con todos los análisis. En producción no se usa `-v` salvo que de verdad quieras empezar de cero.

### 6. HTTPS y dominio

Streamlit sirve HTTP en el puerto 8501. Para un enlace público con candado (`https://`) se pone delante un **proxy inverso** (Nginx, Caddy o el balanceador de tu proveedor de nube) que reciba el tráfico en el puerto 443 y lo reenvíe a la app. La configuración depende de la herramienta que elijas: sigue su documentación oficial.

---

## 🅱️ Opción B: Streamlit Community Cloud

Es el servicio gratuito de Streamlit para publicar apps desde un repositorio de GitHub.

### Pasos

1. Sube el proyecto a GitHub (sin `.env`: el `.gitignore` ya lo impide).
2. En Community Cloud, crea una app desde tu repositorio e indica como archivo principal **`cv_analyzer/app.py`**.
3. Las dependencias se instalan desde `cv_analyzer/requirements.txt`.
4. En **Advanced settings → Secrets**, pega tus variables en formato TOML:

```toml
GOOGLE_API_KEY = "tu_clave"
GEMINI_MODEL = "nombre_del_modelo"
GEMINI_EMBEDDING_MODEL = "nombre_del_modelo_de_embeddings"
DATABASE_URL = "postgresql+psycopg://usuario:contrasena@servidor:5432/base"
```

**¿Por qué funciona sin cambiar el código?** La documentación de Streamlit indica que los *secrets* de nivel raíz también quedan disponibles como **variables de entorno**, y la app los lee con `os.getenv`, igual que el `.env`.

### Limitaciones de esta opción

| Tema | Qué pasa |
| --- | --- |
| PostgreSQL | No hay Docker: necesitas una base PostgreSQL **administrada** en otro servicio y poner su URL en `DATABASE_URL`. Sin ella, la app usaría SQLite, que se **pierde** cuando la plataforma reinicia la app |
| Ollama | No disponible: usa Gemini u OpenAI |
| Chroma | Funciona en memoria, igual que en local (el índice se recrea por CV) |
| Recursos | La plataforma tiene límites de memoria y uso: revisa la página «Status and limitations» de su documentación |

---

## 🔐 Seguridad antes de publicar

Esta app maneja **datos personales** (hojas de vida). Antes de compartir el enlace:

- [ ] **Autenticación.** La app no tiene inicio de sesión: cualquiera con el enlace podría ver el **historial**. Agrega un login (Streamlit ofrece `st.login` con proveedores OpenID Connect; revisa su documentación) o publícala solo en una red privada.
- [ ] **Secretos fuera del repositorio:** `.env` y `secrets.toml` nunca se suben. Si una clave se filtró alguna vez, **revócala** en el proveedor; borrarla del repositorio no basta.
- [ ] **Contraseña fuerte** de PostgreSQL y puerto **no expuesto**.
- [ ] **Límite de subida:** `cv_analyzer/.streamlit/config.toml` ya limita los archivos a 10 MB.
- [ ] **Costos de la API:** cada análisis gasta tokens. La caché ayuda, pero configura límites de gasto en tu proveedor de IA.
- [ ] **Aviso de privacidad:** informa a los usuarios que el texto del CV se envía a un proveedor de IA.
- [ ] **Respaldos** periódicos de la base de datos.

## ✅ Lista final

- [ ] `python -m pytest -q` pasa sin errores.
- [ ] Las versiones de `requirements.txt` están fijadas (`==`).
- [ ] Probaste la imagen de producción en tu PC: `docker compose -f docker-compose.prod.yml up --build`.
- [ ] `docker compose ps` muestra ambos servicios `healthy`.
- [ ] El historial sobrevive a un reinicio del servidor.

## 📚 Fuentes oficiales

- [Streamlit — Deploy Streamlit using Docker](https://docs.streamlit.io/deploy/tutorials/docker)
- [Streamlit — Secrets management](https://docs.streamlit.io/develop/concepts/connections/secrets-management)
- [Streamlit Community Cloud — Secrets management](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management)
- [Streamlit Community Cloud — Deploy your app](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy)
- [Streamlit Community Cloud — App dependencies](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/app-dependencies)
