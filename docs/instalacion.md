# Instalación

Popepo-Bet se instala en tres pasos en cualquier sistema:

1. **Instalar los programas** que necesita (cambia según el sistema).
2. **Descargar Popepo-Bet y ejecutar el instalador** (igual en todos).
3. **Arrancarlo** (en Linux y Windows queda funcionando solo; en Mac, desde una terminal).

En **Windows** funciona dentro de WSL, que es un Ubuntu dentro de Windows: primero se instala WSL y después los pasos son los mismos que en Ubuntu.

Se probó en CachyOS (de la familia Arch). Los pasos de Fedora, Debian, Ubuntu, Mac y Windows usan los mismos scripts, pero aún no se han probado en esas máquinas: si algo falla, mira [Problemas frecuentes](#6-problemas-frecuentes).

**Qué necesita:**
- unos 2 GB de disco (la base de datos ocupa ~0,5 GB, el entorno de Python ~0,8 GB, el panel ~0,5 GB y la caché de descargas ~0,1 GB);
- internet;
- tiempo: la primera descarga del historial tarda **3 o 4 horas**.

## 1. Instalar los programas

Hacen falta Git, Python 3.12 o superior, PostgreSQL (probado con la 18) y Node.js 20.9 o superior. Popepo-Bet crea su propia base de datos y no toca la que pueda tener el sistema.

### Arch y CachyOS

```bash
sudo pacman -S --needed git python postgresql nodejs npm
```

```bash
sudo pacman -D --asexplicit postgresql
```

El segundo comando marca PostgreSQL como instalado a propósito. Si no, una limpieza de paquetes huérfanos podría desinstalarlo y la base de datos dejaría de arrancar.

### Fedora

```bash
sudo dnf install git python3 postgresql-server nodejs npm
```

### Debian, Ubuntu y Windows

**Solo en Windows**, antes: abre PowerShell como administrador, ejecuta esto y reinicia el equipo.

```powershell
wsl --install -d Ubuntu
```

Después abre **Ubuntu** desde el menú Inicio, elige un usuario y una contraseña, y escribe todo lo que sigue en esa ventana.

**En Debian, Ubuntu y Windows:**

```bash
sudo apt update && sudo apt install -y git python3 python3-venv postgresql nodejs npm
```

Comprueba la versión de Node.js:

```bash
node --version
```

Si sale menor que `v20.9` (Ubuntu 24.04 trae la 18), instala la versión estable más reciente:

```bash
sudo npm install -g n && sudo n lts && hash -r
```

Necesitas Debian 13 o Ubuntu 24.04, o más nuevos: las versiones anteriores traen un Python demasiado viejo.

El paquete `postgresql` arranca además una base de datos del sistema que Popepo-Bet no usa. Si quieres ahorrar recursos, puedes apagarla (opcional):

```bash
sudo systemctl disable --now postgresql
```

### Mac

Si no tienes [Homebrew](https://brew.sh), instálalo desde la app Terminal:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

Al terminar, Homebrew muestra dos comandos en "Next steps" para añadirse al `PATH`: ejecútalos. Luego:

```bash
brew install git python postgresql@18 node
```

## 2. Descargar e instalar (Arch, Fedora, Debian, Ubuntu, Mac y Windows)

Es igual en todos los sistemas. En Mac, usa la app Terminal; en Windows, la ventana de Ubuntu.

```bash
git clone https://github.com/Renindstone/Popepo-Bet.git && cd Popepo-Bet
```

```bash
scripts/instalar.sh
```

El instalador hace todo lo demás:
- crea el entorno de Python;
- crea la base de datos propia del proyecto (en `~/.local/share/apuestas/`, solo accesible desde tu PC por el puerto 5433), con una contraseña aleatoria guardada en `.env`;
- crea las tablas e instala las dependencias del panel;
- la primera vez, descarga 3 temporadas de historial más la actual de football-data, FotMob y Understat, y entrena los modelos.

**La primera vez tarda 3 o 4 horas**, porque las descargas van despacio a propósito para no saturar las fuentes. Si se corta, vuelve a ejecutar `scripts/instalar.sh`: lo ya descargado está en caché y sigue donde iba. Al terminar te dice el comando del paso 3.

No gasta peticiones de OddsPapi: las cuotas de Betano solo se descargan si pones tu clave en `.env` (ver el [README](../README.md#betano-opcional)).

## 3. Arrancarlo

### Arch, Fedora, Debian, Ubuntu y Windows

```bash
scripts/install-services.sh --with-web
```

```bash
loginctl enable-linger "$USER"
```

El primer comando instala los servicios y los arranca. El segundo hace que sigan funcionando aunque no tengas la sesión abierta. Abre el panel en **http://localhost:3000**; en Windows, ábrelo en el navegador de Windows.

| Servicio | Qué hace |
|---|---|
| `apuestas-db` | Arranca la base de datos |
| `apuestas-worker` | Tareas programadas en hora de Lima: resultados y reentrenamiento (05:30), previa de los partidos (08:30), apuesta del día (09:00), alineaciones cada 20 min, cuotas cada 3 h, historial atrasado y archivo de temporadas. Solo funciona de 05:00 a 20:00: a las 20:00 se apaga y a las 05:00 vuelve a encenderse. Fuera de ese horario no arranca ni al encender el PC. Si el PC estuvo apagado, al arrancar recupera las tareas del día |
| `apuestas-api` | API REST en `127.0.0.1:8000`; también procesa las capturas |
| `apuestas-web` | Panel en http://localhost:3000. Se compila al arrancar, así que tarda uno o dos minutos |

**En Windows:** Ubuntu se apaga un rato después de cerrar su última ventana, y con él Popepo-Bet. Mientras quieras usarlo, deja la ventana de Ubuntu abierta (puede estar minimizada).

Opciones de `install-services.sh`:
- `--with-bot` instala también el bot de Telegram (ver el README).
- Sin opciones instala solo la base de datos y el worker.
- Puedes volver a ejecutarlo cuando quieras: reescribe los servicios y los reinicia.

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

### Mac

```bash
scripts/arrancar.sh
```

Arranca la base de datos, la API, las tareas programadas y el panel en esa misma terminal. Abre **http://localhost:3000** en cuanto termine de compilar (uno o dos minutos). Deja la terminal abierta mientras lo uses; **Ctrl+C** lo para todo.

Cada vez que enciendas el Mac, abre Terminal y ejecuta:

```bash
cd Popepo-Bet && scripts/arrancar.sh
```

En Mac las tareas programadas funcionan mientras la terminal esté abierta, a cualquier hora (el horario de 05:00 a 20:00 es solo de los servicios de Linux y Windows). Si el Mac estuvo apagado, al arrancar recuperan las tareas del día.

## 4. Conectar Claude (Arch, Fedora, Debian, Ubuntu, Mac y Windows)

- **Claude Code**: abre Claude Code en la carpeta del proyecto. El archivo `.mcp.json` registra el servidor `apuestas`; acepta "Use this MCP server" la primera vez.
- **Leer capturas con Claude** (el botón «Leer con Claude» del panel): necesita el programa `claude` con tu sesión iniciada. Para comprobarlo, ejecuta `claude` una vez en una terminal; si pide iniciar sesión, usa `/login`. Usa tu suscripción y solo procesa automáticamente las capturas de tu usuario (`APUESTAS_DEFAULT_USER` en `.env`).
- **Otros usuarios en tu instalación**: cada uno conecta su propio agente al MCP con su clave. Ver "Varios usuarios" en el [README](../README.md).

### IA local para las capturas (opcional)

Por defecto, las capturas las lee un modelo de visión en tu propio PC, con [Ollama](https://ollama.com). Hace falta una tarjeta gráfica con unos 8 GB de memoria o más; sin ella funciona con el procesador, pero mucho más lento.

**Arch y CachyOS** (con tarjeta AMD; con NVIDIA usa `ollama-cuda` y sin tarjeta, `ollama`):

```bash
sudo pacman -S ollama-rocm && sudo systemctl enable --now ollama
```

**Fedora, Debian, Ubuntu y Windows** (en Windows solo aprovecha tarjetas NVIDIA):

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

**Mac:**

```bash
brew install ollama && brew services start ollama
```

**En todos**, descarga después el modelo (unos 6 GB):

```bash
ollama pull qwen2.5vl:7b
```

Si no vas a usar Ollama, añade `APUESTAS_CAPTURES_ENGINE=claude_code` a `.env` para que las capturas las lea Claude. Otras opciones de `.env`: `APUESTAS_CAPTURES_ENGINE` (`local`, `claude_code`, `api` o `none`), `APUESTAS_CAPTURES_LOCAL_MODEL`, `APUESTAS_OLLAMA_URL` y `APUESTAS_CAPTURES_FALLBACK_ENGINE` (el motor del botón «Leer con Claude»; vacío para quitarlo).

## 5. Actualizar a una versión nueva

El mismo instalador sirve para actualizar: instala lo que haya cambiado y pone al día las tablas, sin volver a descargar el historial.

### Arch, Fedora, Debian, Ubuntu y Windows

```bash
git pull && scripts/instalar.sh && systemctl --user restart apuestas-worker apuestas-api apuestas-web
```

### Mac

Para Popepo-Bet con **Ctrl+C** en su terminal y luego:

```bash
git pull && scripts/instalar.sh && scripts/arrancar.sh
```

## 6. Problemas frecuentes

| Síntoma | Sistemas | Causa y solución |
|---|---|---|
| El instalador dice *Falta Python 3.12*, *Falta Node.js 20.9* o *Falta PostgreSQL* | Todos | Falta un programa del paso 1 o es demasiado viejo: repasa el paso 1 de tu sistema |
| El instalador falló en «Base de datos» y al repetirlo dice *El cluster ya existe*, pero luego da errores de conexión | Todos | La base de datos se creó a medias. Bórrala con `rm -rf ~/.local/share/apuestas/pgdata` y vuelve a ejecutar `scripts/instalar.sh` |
| El panel dice "No hay conexión con la API" | Arch, Fedora, Debian, Ubuntu y Windows | La API no está corriendo: `systemctl --user status apuestas-api` y revisa el registro con `journalctl --user -u apuestas-api` |
| El panel dice "No hay conexión con la API" | Mac | `scripts/arrancar.sh` no está abierto en ninguna terminal: arráncalo |
| *address already in use* al arrancar | Todos | Otro programa usa el puerto 3000, 8000 o 5433; por ejemplo, otra copia de Popepo-Bet o un `npm run dev`. Ciérralo y vuelve a arrancar |
| "Modelos no entrenados todavía" | Todos | El instalador no llegó al final: vuelve a ejecutar `scripts/instalar.sh` |
| Una captura queda en "Error" con *No encuentro el CLI de Claude Code* | Todos | Instala Claude Code o ajusta `APUESTAS_CLAUDE_BIN` en `.env` |
| Una captura queda en "Error" con un mensaje de autenticación | Todos | Tu sesión de Claude caducó: ejecuta `claude` en una terminal, haz `/login` y pulsa "Reintentar" en la captura |
| Errores de conexión a la base de datos | Arch, Fedora, Debian, Ubuntu y Windows | `scripts/db.sh status`; si está parada, `systemctl --user restart apuestas-db` |
| *Falta PostgreSQL* o la base de datos no arranca tras actualizar el sistema | Arch y CachyOS | Se desinstaló PostgreSQL en una limpieza de huérfanos. Reinstálalo con `sudo pacman -S postgresql`; los datos no se pierden |
| Popepo-Bet deja de responder al cerrar Ubuntu | Windows | Ubuntu se apaga al cerrar su última ventana: déjala abierta (minimizada) |
| Quieres ver qué hizo el worker | Arch, Fedora, Debian, Ubuntu y Windows | `journalctl --user -u apuestas-worker --since today`, o `.venv/bin/apuestas status` para ver cuándo se actualizó cada fuente |

## 7. Desinstalar

### Arch, Fedora, Debian, Ubuntu y Windows

```bash
systemctl --user disable --now apuestas-web apuestas-api apuestas-worker apuestas-db apuestas-worker-stop.timer apuestas-worker-start.timer
```

```bash
rm ~/.config/systemd/user/apuestas-* && systemctl --user daemon-reload
```

### Mac

No instala servicios: basta con no volver a ejecutar `scripts/arrancar.sh`.

### En todos

Los datos quedan en `~/.local/share/apuestas/` (base de datos) y en `var/` dentro de la carpeta del proyecto (caché, modelos, capturas y archivo de temporadas). Si ya no los necesitas, borra esas dos carpetas y la carpeta `Popepo-Bet`.
