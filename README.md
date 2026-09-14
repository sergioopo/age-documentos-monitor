# AGE Documentos Monitor

Monitor automático de todos los documentos descargables publicados en la página del Cuerpo General Administrativo de la Administración del Estado, ingreso libre, convocatoria 2025.

Cada cinco minutos:

1. Consulta directamente la página oficial del INAP.
2. Detecta enlaces nuevos a PDF, documentos Office, hojas de cálculo, archivos comprimidos y otros enlaces de descarga.
3. Descarga cada archivo nuevo.
4. Lo envía como archivo adjunto a Telegram.
5. Guarda su identificador en `state.json` para no repetirlo.

Al activar por primera vez este alcance ampliado, el monitor guarda como inventario los documentos que ya existen y no los envía. A partir de la siguiente comprobación, sí enviará cualquier documento nuevo detectado.

## Ejecución automática

El workflow admite ejecución manual y llamadas mediante la API de GitHub. cron-job.org actúa como disparador externo gratuito cada cinco minutos.

Consulta [CRON_SETUP.md](CRON_SETUP.md) para configurarlo cada cinco minutos y verificar la respuesta HTTP.

## Secretos necesarios

En **Settings → Secrets and variables → Actions**, deben existir:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

Puedes abrir **Actions → Monitor documentos AGE → Run workflow** y activar `send_test` para comprobar el envío a Telegram.
