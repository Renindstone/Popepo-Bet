// Servidor MCP `apuestas` para Claude Code (.mcp.json) en Linux, Mac y Windows: el comando del entorno de
// Python está en .venv/bin y, en Windows, en .venv/Scripts con .exe. Pasa la entrada y la salida tal cual.
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";

const bin = process.platform === "win32" ? "../.venv/Scripts/apuestas.exe" : "../.venv/bin/apuestas";
const child = spawn(fileURLToPath(new URL(bin, import.meta.url)), ["mcp"], { stdio: "inherit" });
child.on("error", (err) => {
  console.error(`No se pudo arrancar el servidor MCP (${err.message}). ¿Ejecutaste scripts/instalar.sh?`);
  process.exit(1);
});
child.on("exit", (code) => process.exit(code ?? 1));
for (const sig of ["SIGINT", "SIGTERM"]) process.on(sig, () => child.kill());
