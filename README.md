# AGE Documentos Monitor

Monitor automático del listado provisional de aprobados del Cuerpo General Administrativo de la Administración del Estado, convocatoria 2025.

Cada cinco minutos:

1. Consulta la página oficial del INAP.
2. Detecta documentos nuevos del turno general y del cupo de discapacidad.
3. Descarga el documento.
4. Lo envía como archivo adjunto a Telegram.
5. Guarda su identificador en `state.json` para no repetirlo.

## Secretos necesarios

En **Settings → Secrets and variables → Actions**, crea:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

Después abre **Actions → Monitor documentos AGE → Run workflow** para realizar la primera prueba.
