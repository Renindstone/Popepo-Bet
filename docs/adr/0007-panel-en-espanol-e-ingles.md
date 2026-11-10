# ADR 0007: Panel en español e inglés

**Estado**: aceptada (2026-10-31). Reconstruida el 10-11-2026 con lo que contó el dueño, el commit `6dc31b6`,
`api/i18n.py` y `docs/arquitectura.md`: el original solo vivía en su PC y se perdió.

## Contexto
El dueño quiere que el proyecto llegue a más gente en GitHub, también a quien habla inglés. El mismo día el
repositorio pasó a tener licencia MIT y un README con sección en inglés, pero el panel estaba solo en español.
Pidió traducir **todo** lo que se ve, también los textos que arma el servidor: razones, avisos, notas y errores.

Todo el programa está escrito en español (servicios, base de datos, bot, MCP y los textos que generan), y
reescribirlo en dos idiomas tocaría casi todos los módulos.

## Decisión
- **Selector ES / EN** en la cabecera del panel. Se recuerda en el navegador y, sin elegir, sigue al idioma del
  navegador (si no es español ni inglés, español).
- **Textos del panel**: cada texto lleva sus dos versiones donde se usa (`tr("Hoy", "Today")`,
  `web/src/lib/i18n.tsx`), sin archivos de traducción aparte. Al cambiar de idioma se vuelve a montar el panel.
- **Textos de la API**: el panel manda `Accept-Language` en cada petición y, si es inglés, un middleware
  (`api/i18n.py`) traduce la respuesta JSON con un catálogo de frases fijas y plantillas. Lo que no está en el
  catálogo sale como está.
- **Lo que no cambia**: los servicios, la BD, el bot de Telegram y el MCP siguen en español. Los valores que el
  panel usa como clave («APOSTAR», «con valor», «racha», los niveles de dificultad…) no se traducen en la API sino
  en el panel, para no romper las comparaciones.
- Mercados con los nombres de Betano en inglés («Asian Handicap», «Both Teams To Score»), fechas en inglés
  británico y el dinero siempre en soles.

## Consecuencias
- El resto del código no se toca: traducir es una capa encima de la API.
- Cada texto nuevo del servidor que se vea en el panel necesita su frase o plantilla en `api/i18n.py`; si falta,
  sale en español (`tests/test_i18n.py` comprueba el catálogo).
- Siguen en español: el título de la pestaña del navegador (se fija al compilar), las explicaciones de Claude y los
  resúmenes de capturas (se guardan ya escritos), los errores técnicos de la ingesta y lo que llega tal cual de las
  fuentes. Lista al día en `docs/estado.md`.
