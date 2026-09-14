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
| `X-GitHub-Api-Version` | `2022-11-28` |
| `Content-Type` | `application/json` |

Sustituye `TU_TOKEN_DE_GITHUB` por el token. No incluyas el token en este repositorio.

## 3. Probar

Ejecuta una prueba desde cron-job.org. GitHub debe responder con HTTP `204 No Content`. Unos segundos después aparecerá una ejecución correcta en:

https://github.com/sergioopo/age-documentos-monitor/actions/workflows/age-monitor.yml

Las ejecuciones externas aparecerán en GitHub como `workflow_dispatch`. El historial de cron-job.org permite comprobar que el disparo se realiza cada cinco minutos.

El disparador `schedule` nativo se mantiene como respaldo.
