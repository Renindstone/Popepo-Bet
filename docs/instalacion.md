# Installation

**English** · [Español](es/instalacion.md)

Popepo-Bet installs in three steps on any system:

1. **Install the programs** it needs (this depends on the system).
2. **Download Popepo-Bet and run the installer** (the same everywhere).
3. **Start it** (on Linux and Windows it keeps running on its own; on a Mac, from a terminal).

On **Windows** there are two paths: inside WSL, which is an Ubuntu inside Windows (the steps are Ubuntu's and it keeps running on its own), or **without WSL**, with Git Bash (the steps are the Mac's: you start it from a terminal). Where this guide just says "Windows", it means with WSL.

It has been tested on CachyOS (Arch family), on Fedora (10-11-2026, with Python 3.15 and Node.js 22: the scripts work unchanged) and on Windows 11 without WSL (15-11-2026, with Python 3.14, PostgreSQL 18 and Node.js 26). The steps for Debian, Ubuntu, Mac and Windows with WSL use the same scripts, but haven't been tested on those machines yet: if something fails, see [Common problems](#6-common-problems).

The installer and the command-line interface print their messages in Spanish; this guide quotes them as they appear, with a translation.

**What it needs:**
- about 2 GB of disk (the database takes ~0.5 GB, the Python environment ~0.8 GB, the dashboard ~0.5 GB and the download cache ~0.1 GB);
- internet;
- time: the first download of the history takes **3 or 4 hours**.

## 1. Install the programs

You need Git, Python 3.12 or later, PostgreSQL (tested with 18) and Node.js 20.9 or later. Popepo-Bet creates its own database and doesn't touch any the system may already have.

### Arch and CachyOS

```bash
sudo pacman -S --needed git python postgresql nodejs npm
```

```bash
sudo pacman -D --asexplicit postgresql
```

The second command marks PostgreSQL as explicitly installed. Otherwise, a cleanup of orphan packages could uninstall it and the database would stop starting.

### Fedora

```bash
sudo dnf install git python3 postgresql-server nodejs npm
```

### Debian, Ubuntu and Windows

**On Windows only**, first: open PowerShell as administrator, run this and restart the computer.

```powershell
wsl --install -d Ubuntu
```

Then open **Ubuntu** from the Start menu, choose a username and a password, and type everything that follows in that window.

**On Debian, Ubuntu and Windows:**

```bash
sudo apt update && sudo apt install -y git python3 python3-venv postgresql nodejs npm
```

Check the Node.js version:

```bash
node --version
```

If it's lower than `v20.9` (Ubuntu 24.04 ships 18), install the latest stable version:

```bash
sudo npm install -g n && sudo n lts && hash -r
```

You need Debian 13 or Ubuntu 24.04, or newer: earlier versions ship a Python that's too old.

The `postgresql` package also starts a system database that Popepo-Bet doesn't use. If you want to save resources, you can turn it off (optional):

```bash
sudo systemctl disable --now postgresql
```

### Mac

If you don't have [Homebrew](https://brew.sh), install it from the Terminal app:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

When it finishes, Homebrew shows two commands under "Next steps" to add itself to the `PATH`: run them. Then:

```bash
brew install git python postgresql@18 node
```

### Windows without WSL

In PowerShell (it doesn't need to be as administrator; the PostgreSQL installer asks for permission):

```powershell
winget install -e --id Git.Git
```

```powershell
winget install -e --id Python.Python.3.14 --scope user
```

```powershell
winget install -e --id PostgreSQL.PostgreSQL.18
```

```powershell
winget install -e --id OpenJS.NodeJS.LTS
```

Use Python 3.14 even if you have a newer one: with 3.15 some libraries don't have a Windows build yet and the installation fails asking for *Microsoft Visual C++*. The installer picks 3.14 by itself with the `py` launcher. PostgreSQL also leaves a Windows service (`postgresql-x64-18`, port 5432) that Popepo-Bet doesn't use. Everything that follows is typed in **Git Bash** (Start menu).

## 2. Download and install (Arch, Fedora, Debian, Ubuntu, Mac and Windows)

It's the same on every system. On a Mac, use the Terminal app; on Windows, the Ubuntu window (or Git Bash, without WSL).

```bash
git clone https://github.com/Renindstone/Popepo-Bet.git && cd Popepo-Bet
```

```bash
scripts/instalar.sh
```

The installer does everything else:
- creates the Python environment;
- creates the project's own database (in `~/.local/share/apuestas/`, only reachable from your PC on port 5433), with a random password saved in `.env`;
- creates the tables and installs the dashboard's dependencies;
- the first time, downloads 3 seasons of history plus the current one from football-data and FotMob, and trains the models.

**The first time it takes 3 or 4 hours**, because the downloads are slow on purpose so as not to overload the sources. If it gets interrupted, run `scripts/instalar.sh` again: what was already downloaded is cached and it carries on where it was. When it finishes it tells you the command for step 3.

It uses no OddsPapi requests: Betano odds are only downloaded if you put your key in `.env` (see the [README](../README.md#betano-optional)).

## 3. Start it

### Arch, Fedora, Debian, Ubuntu and Windows

```bash
scripts/install-services.sh --with-web
```

```bash
loginctl enable-linger "$USER"
```

The first command installs the services and starts them. The second keeps them running even when you're not logged in. Open the dashboard at **http://localhost:3000**; on Windows, open it in the Windows browser.

| Service | What it does |
|---|---|
| `apuestas-db` | Starts the database |
| `apuestas-worker` | Scheduled tasks in Lima time: results and retraining (05:30), match previews (08:30), bet of the day (09:00), line-ups every 20 min, odds every 3 h, backlog history and season archive. It only runs from 05:00 to 20:00: at 20:00 it stops and at 05:00 it starts again. Outside those hours it doesn't start even when the PC is switched on. If the PC was off, it catches up the day's tasks on start |
| `apuestas-api` | REST API at `127.0.0.1:8000`; it also processes the screenshots |
| `apuestas-web` | Dashboard at http://localhost:3000. It's built on start, so it takes a minute or two |

**On Windows:** Ubuntu shuts down a while after its last window is closed, and Popepo-Bet with it. While you want to use it, leave the Ubuntu window open (it can be minimised).

`install-services.sh` options:
- `--with-bot` also installs the Telegram bot (see the README).
- With no options it only installs the database and the worker.
- You can run it again whenever you want: it rewrites the services and restarts them.

Useful commands:

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

It starts the database, the API, the scheduled tasks and the dashboard in that same terminal. Open **http://localhost:3000** as soon as it finishes building (a minute or two). Leave the terminal open while you use it; **Ctrl+C** stops everything.

Every time you switch on the Mac, open Terminal and run:

```bash
cd Popepo-Bet && scripts/arrancar.sh
```

On a Mac the scheduled tasks run while the terminal is open, at any hour (the 05:00 to 20:00 schedule only applies to the Linux and Windows services). If the Mac was off, they catch up the day's tasks on start.

### Windows without WSL

The same as on a Mac, with `scripts/arrancar.sh` in Git Bash. Nothing keeps running on its own: every time you switch on the PC, open Git Bash and run:

```bash
cd ~/Proyectos/Popepo-Bet && scripts/arrancar.sh
```

(change the folder to wherever you cloned it). From PowerShell, `& 'C:\Program Files\Git\bin\bash.exe' scripts/arrancar.sh` inside the project folder also works. The scheduled tasks run while that window is open, at any hour, and catch up the day's tasks on start.

## 4. Connect Claude (Arch, Fedora, Debian, Ubuntu, Mac and Windows)

- **Claude Code**: open Claude Code in the project folder. The `.mcp.json` file registers the `apuestas` server (started by `scripts/mcp.mjs` with Node.js, on any system); accept "Use this MCP server" the first time.
- **Reading screenshots with Claude** (the dashboard's "Read with Claude" button): it needs the `claude` program logged in. To check, run `claude` once in a terminal; if it asks you to log in, use `/login`. It uses your subscription and only processes your user's screenshots automatically (`APUESTAS_DEFAULT_USER` in `.env`).
- **Other users on your installation**: each one connects their own agent to the MCP server with their key. See "Several users" in the [README](../README.md).

### Local AI for screenshots (optional)

By default, screenshots are read by a vision model on your own PC, with [Ollama](https://ollama.com). It needs a graphics card with about 8 GB of memory or more; without one it runs on the processor, but much more slowly.

**Arch and CachyOS** (with an AMD card; with NVIDIA use `ollama-cuda` and with no card, `ollama`):

```bash
sudo pacman -S ollama-rocm && sudo systemctl enable --now ollama
```

**Fedora, Debian, Ubuntu and Windows** (on Windows it only uses NVIDIA cards):

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

**Mac:**

```bash
brew install ollama && brew services start ollama
```

**On all of them**, then download the model (about 6 GB):

```bash
ollama pull qwen2.5vl:7b
```

If you're not going to use Ollama, add `APUESTAS_CAPTURES_ENGINE=claude_code` to `.env` so that Claude reads the screenshots. Other `.env` options: `APUESTAS_CAPTURES_ENGINE` (`local`, `claude_code`, `api` or `none`), `APUESTAS_CAPTURES_LOCAL_MODEL`, `APUESTAS_OLLAMA_URL` and `APUESTAS_CAPTURES_FALLBACK_ENGINE` (the engine behind the "Read with Claude" button; empty to remove it).

## 5. Update to a new version

The same installer is used to update: it installs whatever changed and brings the tables up to date, without downloading the history again.

### Arch, Fedora, Debian, Ubuntu and Windows

```bash
git pull && scripts/instalar.sh && systemctl --user restart apuestas-worker apuestas-api apuestas-web
```

### Mac and Windows without WSL

Stop Popepo-Bet with **Ctrl+C** in its terminal and then:

```bash
git pull && scripts/instalar.sh && scripts/arrancar.sh
```

What changed in each version is in the [CHANGELOG](../CHANGELOG.md).

## 6. Common problems

| Symptom | Systems | Cause and fix |
|---|---|---|
| The installer says *Falta Python 3.12*, *Falta Node.js 20.9* or *Falta PostgreSQL* ("missing …") | All | A program from step 1 is missing or too old: go over step 1 for your system |
| The installer failed at «Base de datos» (database) and when repeated it says *El cluster ya existe* ("the cluster already exists"), but then gives connection errors | All | The database was half created. Delete it with `rm -rf ~/.local/share/apuestas/pgdata` and run `scripts/instalar.sh` again |
| The dashboard says "No connection to the API" | Arch, Fedora, Debian, Ubuntu and Windows | The API isn't running: `systemctl --user status apuestas-api` and check the log with `journalctl --user -u apuestas-api` |
| The dashboard says "No connection to the API" | Mac and Windows without WSL | `scripts/arrancar.sh` isn't open in any terminal: start it |
| The installer fails with *Microsoft Visual C++ 14.0 or greater is required* | Windows without WSL | The environment was created with Python 3.15. Install Python 3.14 (step 1), delete the `.venv` folder and run `scripts/instalar.sh` again |
| *WinError 32 … apuestas.exe* when installing or updating | Windows without WSL | The API or the worker are still open: stop them with **Ctrl+C** and repeat |
| *address already in use* on start | All | Another program is using port 3000, 8000 or 5433; for example, another copy of Popepo-Bet or an `npm run dev`. Close it and start again |
| Warnings about a source show up during installation (for example, *www.football-data.co.uk no devolvió datos (¿está en mantenimiento?)*, "returned no data (under maintenance?)") | All | It's normal if that source is down or under maintenance: it's skipped and the installation carries on. When it comes back, the worker recovers its data by itself |
| The installation prints nothing for a long time | All | It's downloading the details of thousands of FotMob matches, slowly on purpose. It reports every 100 matches (*Detalles de FotMob: 100 de 8000 partidos jugados*); several minutes can pass between reports |
| "Models not trained yet" | All | The installer didn't reach the end: run `scripts/instalar.sh` again |
| A screenshot stays in "Error" with *No encuentro el CLI de Claude Code* ("can't find the Claude Code CLI") | All | Install Claude Code or set `APUESTAS_CLAUDE_BIN` in `.env` |
| A screenshot stays in "Error" with an authentication message | All | Your Claude session expired: run `claude` in a terminal, do `/login` and press "Retry" on the screenshot |
| Database connection errors | Arch, Fedora, Debian, Ubuntu and Windows | `scripts/db.sh status`; if it's stopped, `systemctl --user restart apuestas-db` |
| *Falta PostgreSQL* or the database doesn't start after a system update | Arch and CachyOS | PostgreSQL was uninstalled in an orphan cleanup. Reinstall it with `sudo pacman -S postgresql`; no data is lost |
| Popepo-Bet stops responding when Ubuntu is closed | Windows | Ubuntu shuts down when its last window closes: leave it open (minimised) |
| You want to see what the worker did | Arch, Fedora, Debian, Ubuntu and Windows | `journalctl --user -u apuestas-worker --since today`, or `.venv/bin/apuestas status` to see when each source was updated |

## 7. Uninstall

### Arch, Fedora, Debian, Ubuntu and Windows

```bash
systemctl --user disable --now apuestas-web apuestas-api apuestas-worker apuestas-db apuestas-worker-stop.timer apuestas-worker-start.timer
```

```bash
rm ~/.config/systemd/user/apuestas-* && systemctl --user daemon-reload
```

### Mac and Windows without WSL

It doesn't install services: just don't run `scripts/arrancar.sh` again.

### On all of them

The data stays in `~/.local/share/apuestas/` (database) and in `var/` inside the project folder (cache, models, screenshots and season archive). If you no longer need them, delete those two folders and the `Popepo-Bet` folder.
