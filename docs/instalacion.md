# Instalación desde cero

Guía para instalar Popepo-Bet en una PC nueva y dejarlo funcionando solo. Se probó en Linux (CachyOS, de la familia Arch). En otras distribuciones cambian los nombres de los paquetes. En macOS debería funcionar con Homebrew, pero no se ha probado. En Windows, usa WSL.

## 1. Requisitos

| Qué | Versión | Para qué |
|---|---|---|
| Git | cualquiera | descargar el código |
| Python | 3.12 o superior (probado con 3.14) | todo el sistema |
| PostgreSQL | 18 (solo los programas: `initdb`, `pg_ctl`, `psql`) | base de datos; el proyecto crea su propio cluster sin tocar el del sistema |
| Node.js y npm | 20.9 o superior | panel web |
| Claude Code (CLI `claude`) con tu sesión iniciada | opcional | leer capturas en el panel y usar el MCP desde la terminal |

En Arch o CachyOS:

```bash
sudo pacman -S --needed git python postgresql nodejs npm
```

Si PostgreSQL ya estaba instalado como dependencia de otro paquete, márcalo como instalado a propósito: `sudo pacman -D --asexplicit postgresql`. Si no, una limpieza de paquetes huérfanos lo desinstala, y la base de datos deja de arrancar.

En Debian o Ubuntu: `sudo apt install git python3 python3-venv postgresql nodejs npm`. Los programas de PostgreSQL quedan en `/usr/lib/postgresql/<versión>/bin`, así que añade esa carpeta al `PATH`.

**Espacio en disco:** unos 2 GB. Se reparten así:
- base de datos con 3 temporadas de historial: ~0.5 GB;
- entorno de Python: ~0.8 GB;
- dependencias del panel: ~0.5 GB;
- caché de descargas: ~0.1 GB.

## 2. Código y entorno de Python

```bash
git clone https://github.com/Renindstone/Popepo-Bet.git
```

```bash
cd Popepo-Bet && python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
```

## 3. Base de datos

```bash
scripts/db.sh init
```

Crea un PostgreSQL propio del proyecto en `~/.local/share/apuestas/pgdata`, que escucha solo en `127.0.0.1:5433`. También genera una contraseña aleatoria y escribe el archivo `.env`, que no se sube a Git. Después crea las tablas:

```bash
.venv/bin/alembic upgrade head
```

## 4. Datos y modelos

```bash
.venv/bin/apuestas ingest all --seasons 3 --backfill 8000
```

Descarga 3 temporadas de historial más la actual: resultados, estadísticas, alineaciones, árbitros y cuotas de football-data.co.uk, FotMob y Understat.
- **La primera vez tarda 3 o 4 horas**, porque las peticiones van despacio a propósito para no saturar las fuentes.
- Si se corta, vuelve a lanzarlo: lo ya descargado está en caché (`var/cache`) y no se repite.

Luego entrena los modelos (unos minutos):

```bash
.venv/bin/apuestas train
```

Comprueba que todo está bien:

```bash
.venv/bin/apuestas status
```

```bash
.venv/bin/apuestas picks
```

Y los tests:

```bash
.venv/bin/pytest -q
```

## 5. Servicios: que todo funcione solo

```bash
scripts/install-services.sh --with-web
```

Instala y arranca estos servicios de systemd de usuario (no necesitan sudo):

| Servicio | Qué hace |
|---|---|
| `apuestas-db` | Arranca la base de datos |
| `apuestas-worker` | Tareas programadas en hora de Lima: resultados y reentrenamiento (05:30), previa de los partidos (08:30), apuesta del día (09:00), alineaciones cada 20 min, cuotas cada 3 h, historial atrasado (02:00) y archivo de temporadas (lunes). Solo funciona de 05:00 a 20:00: a las 20:00 lo apaga `apuestas-worker-stop.timer` y a las 05:00 lo enciende `apuestas-worker-start.timer`; fuera de ese horario no arranca ni al encender el PC (desde el 2026-10-26). |
| `apuestas-api` | API REST en `127.0.0.1:8000`; también procesa las capturas |
| `apuestas-web` | Panel en **http://localhost:3000**. Se compila al arrancar, así que el primer arranque tarda un poco |

Opciones del script:
- Con `--with-bot` instala también el bot de Telegram (ver el README).
- Sin opciones instala solo la base de datos y el worker.
- Puedes volver a ejecutarlo cuando quieras: reescribe los servicios y los reinicia.

Por defecto, los servicios arrancan al iniciar sesión y se detienen al cerrarla. Si quieres que sigan funcionando sin tener la sesión abierta (por ejemplo, la apuesta del día de las 09:00 con la PC encendida pero sin sesión):

```bash
loginctl enable-linger "$USER"
```

Comandos útiles:

```bash
systemctl --user status apuestas-worker apuestas-api apuestas-web
```

```bash
journalctl --user -u apuestas-api -f
```

```bash
systemctl --user restart apuestas-worker apuestas-api apuestas-web
```

```bash
systemctl --user disable --now apuestas-web
```

## 6. Conectar Claude

- **Claude Code**: abre Claude Code en la carpeta del proyecto. El archivo `.mcp.json` registra el servidor `apuestas`; acepta "Use this MCP server" la primera vez.
- **Capturas en el panel**: necesitan el CLI `claude` con tu sesión iniciada. Para comprobarlo, ejecuta `claude` una vez en una terminal; si pide iniciar sesión, usa `/login`. Las capturas usan tu suscripción y solo se procesan automáticamente las de tu usuario (`APUESTAS_DEFAULT_USER` en `.env`).
- **Otros usuarios en tu instalación**: cada uno conecta su propio agente al MCP con su clave. Ver "Varios usuarios" en el [README](../README.md).

### IA local para las capturas (opcional)

Las capturas las lee por defecto un modelo de visión en tu PC, con [Ollama](https://ollama.com). Hace falta una tarjeta gráfica con unos 8 GB de memoria o más (con menos funciona en el procesador, mucho más lento).

```bash
sudo pacman -S ollama-rocm        # AMD (en NVIDIA: ollama-cuda; sin tarjeta: ollama)
sudo systemctl enable --now ollama
ollama pull qwen2.5vl:7b          # unos 6 GB
```

Se puede cambiar en `.env`: `APUESTAS_CAPTURES_ENGINE` (`local`, `claude_code`, `api` o `none`), `APUESTAS_CAPTURES_LOCAL_MODEL`, `APUESTAS_OLLAMA_URL` y `APUESTAS_CAPTURES_FALLBACK_ENGINE` (el del botón «Leer con Claude»; vacío para quitarlo). Sin Ollama, pon `APUESTAS_CAPTURES_ENGINE=claude_code`.

## 7. Actualizar a una versión nueva

```bash
git pull && .venv/bin/pip install -e ".[dev]" && .venv/bin/alembic upgrade head
```

```bash
npm --prefix web ci
```

```bash
systemctl --user restart apuestas-worker apuestas-api apuestas-web
```

`apuestas-web` se vuelve a compilar al reiniciarse. `npm --prefix web ci` solo hace falta si cambiaron las dependencias del panel (`web/package-lock.json`).

## 8. Problemas frecuentes

| Síntoma | Causa y solución |
|---|---|
| El panel dice "No hay conexión con la API" | La API no está corriendo: `systemctl --user status apuestas-api` y revisa el log con `journalctl --user -u apuestas-api` |
| `apuestas-web` o `apuestas-api` no arrancan: *address already in use* | Otro proceso usa el puerto 3000 u 8000, por ejemplo un `npm run dev` o un `apuestas api` lanzado a mano. Ciérralo y reinicia el servicio |
| "Modelos no entrenados todavía" | Falta `.venv/bin/apuestas train`; el worker lo hace solo cada día a las 05:30 |
| Una captura queda en "Error" con *No encuentro el CLI de Claude Code* | Instala Claude Code o ajusta `APUESTAS_CLAUDE_BIN` en `.env` |
| Una captura queda en "Error" con un mensaje de autenticación | Tu sesión de Claude caducó: ejecuta `claude` en una terminal, haz `/login` y pulsa "Reintentar" en la captura |
| Errores de conexión a la base de datos | `scripts/db.sh status`; si está parada, `systemctl --user restart apuestas-db` |
| `pg_ctl` o `psql`: *orden no encontrada*, o la BD no arranca tras actualizar el sistema | Se desinstaló el paquete de PostgreSQL (suele pasar en una limpieza de huérfanos). Vuelve a instalarlo con `sudo pacman -S postgresql`; los datos no se pierden |
| Quieres ver qué hizo el worker | `journalctl --user -u apuestas-worker --since today`, o `.venv/bin/apuestas status` para la frescura de cada fuente |

## 9. Desinstalar

```bash
systemctl --user disable --now apuestas-web apuestas-api apuestas-worker apuestas-db
```

```bash
rm ~/.config/systemd/user/apuestas-*.service && systemctl --user daemon-reload
```

Los datos quedan en `~/.local/share/apuestas/` (base de datos) y en `var/` dentro del proyecto (caché, modelos, capturas y archivo de temporadas). Bórralos a mano solo si ya no los necesitas.
