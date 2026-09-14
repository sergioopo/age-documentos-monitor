# Activación externa cada cinco minutos

GitHub Actions no ha generado eventos `schedule` en este repositorio. Para asegurar el disparo periódico, se utiliza cron-job.org para invocar el workflow mediante la API oficial de GitHub.

## 1. Crear un token de GitHub limitado

Abre:

https://github.com/settings/personal-access-tokens/new

Configura:

- **Token name:** `AGE documentos cron`
- **Resource owner:** `sergioopo`
- **Repository access:** `Only select repositories`
- **Repository:** `age-documentos-monitor`
- **Repository permissions → Actions:** `Read and write`

No añadas permisos adicionales. Copia el token cuando GitHub lo muestre.

## 2. Crear la tarea en cron-job.org

Crea una cuenta gratuita en:

https://console.cron-job.org/signup

Añade un cronjob con estos valores:

- **Title:** `AGE documentos monitor`
- **URL:** `https://api.github.com/repos/sergioopo/age-documentos-monitor/actions/workflows/age-monitor.yml/dispatches`
- **Schedule:** cada 5 minutos
- **Request method:** `POST`
- **Request body:**

```json
{"ref":"main","inputs":{"send_test":"false"}}
```

- **Headers:**

| Nombre | Valor |
|---|---|
| `Accept` | `application/vnd.github+json` |
| `Authorization` | `Bearer TU_TOKEN_DE_GITHUB` |
| `X-GitHub-Api-Version` | `2026-03-10` |
| `Content-Type` | `application/json` |
| `User-Agent` | `age-documentos-monitor` |

Sustituye `TU_TOKEN_DE_GITHUB` por el token, sin comillas. En cron-job.org, introduce el nombre y el valor de cada cabecera en campos separados. No incluyas el token en este repositorio.

## 3. Probar

Ejecuta una prueba desde cron-job.org. Con la versión actual de la API, GitHub debe responder con HTTP `200 OK` e información de la ejecución. Unos segundos después aparecerá una ejecución correcta en:

https://github.com/sergioopo/age-documentos-monitor/actions/workflows/age-monitor.yml

Las ejecuciones externas aparecerán en GitHub como `workflow_dispatch`. El historial de cron-job.org permite comprobar que el disparo se realiza cada cinco minutos.

Si GitHub sigue devolviendo `403`, abre el detalle de la ejecución en cron-job.org y revisa el cuerpo de la respuesta:

- `Resource not accessible by personal access token`: el token no tiene **Actions: Read and write** o no incluye este repositorio.
- `User-Agent Required`: falta la cabecera `User-Agent`.
- `Bad credentials`: el token está incompleto, caducado o contiene espacios/comillas.

El workflow utiliza únicamente este disparador externo para evitar ejecuciones duplicadas.
