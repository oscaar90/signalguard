# signalguard

`signalguard` es una herramienta local de observabilidad/SRE que lee métricas desde Netdata, dispara reglas deterministas y genera una hipótesis breve para acelerar el análisis inicial.

No intenta ser una plataforma, ni un dashboard, ni un sistema de AIOps. Hace una sola cosa: combinar unas pocas señales útiles y producir un diagnóstico claro por consola o JSON.

## Qué hace

- Consulta métricas actuales desde la API local de Netdata.
- Resume señales base: CPU, load average, memoria, swap, disk I/O y red opcional.
- Aplica reglas explícitas y transparentes.
- Muestra diagnóstico estructurado en CLI.
- Puede pedir una explicación breve a un LLM, pero la detección sigue siendo determinista.

## Qué no hace

- No expone API REST.
- No usa base de datos.
- No monta frontend ni dashboard.
- No hace detección estadística avanzada ni ML.
- No reemplaza la observabilidad existente; añade una capa de triage rápido.

## Estructura

```text
signalguard/
  cli.py
  netdata_client.py
  rules.py
  analyzer.py
  llm.py
  models.py
tests/
README.md
pyproject.toml
```

## Requisitos

- Python 3.12+
- Netdata accesible en `http://127.0.0.1:19999` por defecto

## Configuración del proyecto

El proyecto usa un único fichero `.env` como configuración externa.

Ejemplo:

```env
SIGNALGUARD_NETDATA_URL=http://127.0.0.1:19999
SIGNALGUARD_LLM_PROVIDER=openrouter
SIGNALGUARD_LLM_MODEL=google/gemini-2.5-flash-lite
OPENROUTER_API_KEY=tu_api_key
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
```

Puedes elegir entre:

- `SIGNALGUARD_LLM_PROVIDER=ollama`
- `SIGNALGUARD_LLM_PROVIDER=openrouter`
- `SIGNALGUARD_LLM_PROVIDER=none`

## Instalación

```bash
cd /home/oscar/IA/Proyectos/signalguard
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

## Por qué es útil para observabilidad/SRE

Netdata ya sirve para ver métricas. `signalguard` añade una capa de triage:

- combina señales concretas en reglas explícitas
- devuelve una hipótesis breve y accionable
- permite salida estable en JSON para automatización local
- mantiene la lógica de detección fuera del LLM

La idea no es sustituir Netdata, sino acelerar el primer análisis cuando aparecen síntomas mezclados.

## Cómo arrancar Netdata localmente

Si no tienes Netdata instalado, la vía más simple en Linux suele ser:

```bash
bash <(curl -Ss https://my-netdata.io/kickstart.sh)
```

Luego confirma que responde:

```bash
curl http://127.0.0.1:19999/api/v1/info
```

## Uso

Chequeo local sin LLM:

```bash
signalguard check
```

Salida JSON:

```bash
signalguard check --json
```

Explicación con modo local basado en reglas:

```bash
signalguard explain --no-llm
```

Explicación con LLM:

```bash
signalguard explain
```

Si Netdata está en otra URL:

```bash
signalguard check --netdata-url http://host:19999
```

Ejecución continua:

```bash
signalguard watch --no-llm --interval 30
```

## Qué señales evalúa

- CPU %
- load average a 1 minuto
- memoria usada
- swap usada si Netdata la expone
- disk I/O agregado
- tráfico de red básico para correlación

Además de las métricas crudas, `signalguard` construye una lectura de señales con nivel `ok`, `warning` o `critical` antes de disparar reglas.

## Configuración LLM

La ruta recomendada ahora es usar OpenRouter con `google/gemini-2.5-flash-lite`, que ha sido la opción cloud más estable en las pruebas.

La aplicación carga `.env` automáticamente si existe:

```bash
cp .env.example .env
# edita .env
signalguard explain
```

Si quieres usar Ollama como alternativa local:

```bash
cp .env.example .env
# cambia SIGNALGUARD_LLM_PROVIDER=ollama
# cambia SIGNALGUARD_LLM_MODEL=gemma4:latest
signalguard explain
```

Variables soportadas en `.env`:

- `SIGNALGUARD_NETDATA_URL`
- `SIGNALGUARD_LLM_PROVIDER` con valores `ollama`, `openrouter` o `none`
- `SIGNALGUARD_LLM_MODEL`
- `OLLAMA_BASE_URL` opcional, por defecto `http://127.0.0.1:11434/v1`
- `OPENROUTER_API_KEY`
- `OPENROUTER_BASE_URL` opcional, por defecto `https://openrouter.ai/api/v1`
- `SIGNALGUARD_APP_NAME`
- `SIGNALGUARD_APP_URL`

Para despliegue con Docker o uso local, parte de [`.env.example`](/home/oscar/IA/Proyectos/signalguard/.env.example) y no subas `.env` al repositorio.

## Reglas implementadas

- CPU alta + load alto: posible saturación general de CPU o procesos intensivos.
- Disk I/O alto + load alto: posible cuello de botella de disco.
- Memoria alta + swap alta: posible presión de memoria.
- CPU baja + load alto + I/O alto: posible espera por disco o iowait indirecto.

Los umbrales están en [`signalguard/rules.py`](/home/oscar/IA/Proyectos/signalguard/signalguard/rules.py).

## Ejemplo de salida

```text
estado general: critical

reglas disparadas:
- CPU alta con load alto
- Disk I/O alto con load alto

hipótesis:
Posible cuello de botella de disco o ráfaga de escrituras/lecturas.

siguiente paso:
Inspeccionar procesos con más I/O y latencia de disco antes de escalar.
```

## Tests

```bash
pytest
```

Los tests cubren las reglas mínimas para asegurar que la detección siga siendo simple, explícita y estable.

## Docker opcional

Si no quieres instalar Netdata en el host, el repo incluye una ruta de empaquetado simple:

```bash
docker compose up --build
```

Eso levanta `netdata` y `signalguard` juntos. El despliegue con Docker es opcional; la herramienta sigue pensada como CLI local pequeña.

Si quieres que el contenedor use Ollama del host, cambia `SIGNALGUARD_LLM_PROVIDER=ollama`. El `compose` ya apunta a `host.docker.internal:11434`.

## Archivos de despliegue

- [Dockerfile](/home/oscar/IA/Proyectos/signalguard/Dockerfile)
- [docker-compose.yml](/home/oscar/IA/Proyectos/signalguard/docker-compose.yml)
- [.env.example](/home/oscar/IA/Proyectos/signalguard/.env.example)
