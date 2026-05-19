# Sistema de Backups de Lemlist — Documentación Técnica

**Autor**: David Meléndez Pérez
**Fecha de despliegue**: Mayo 2026
**Stack**: AWS Lambda (Python 3.14) · EventBridge Scheduler · S3 · IAM · CloudWatch · API Lemlist

---

## 1. Arquitectura

```
┌──────────────────────────────────────────────────────────────────┐
│                    AWS LAMBDA: lemlist-backup-weekly             │
│   (Función única multi-cliente, lee la API key del evento)       │
└──────────────────────────────────────────────────────────────────┘
                              ▲
                              │ invoca
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
   EventBridge            EventBridge            EventBridge
   cloudpiles               2leap            senioradvisorm
   Lun 01:00 UTC          Lun 01:15 UTC      Lun 01:30 UTC
        │                     │                     │
        ▼                     ▼                     ▼
        ┌─────────────────────────────────────────────────────┐
        │           S3: 2leap-lemlist-backup                  │
        │  ├── lemlist-backups/                               │
        │  │   ├── cloudpiles/AAAA-MM-DD/                     │
        │  │   ├── 2leap/AAAA-MM-DD/                          │
        │  │   └── senior-advisor-m/AAAA-MM-DD/               │
        └─────────────────────────────────────────────────────┘
                              ▲
                              │ logs
                       CloudWatch Logs
                /aws/lambda/lemlist-backup-weekly
```

### Flujo de ejecución

1. **EventBridge** dispara la Lambda los lunes a una hora concreta enviando un evento JSON con el cliente a procesar.
2. **Lambda** lee la API key correspondiente desde sus variables de entorno.
3. Llama a la **API de Lemlist** para obtener:
   - Lista de campañas activas (filtra archivadas)
   - CSV de leads de cada campaña (endpoint `/export/leads`)
4. Sube cada CSV a **S3** organizado por cliente y fecha.
5. Todos los logs van automáticamente a **CloudWatch**.

---

## 2. Componentes de AWS

### 2.1 Lambda: `lemlist-backup-weekly`

- **Región**: `eu-west-1` (Irlanda)
- **Runtime**: Python 3.14
- **Memoria**: 512 MB
- **Timeout**: 5 minutos
- **Rol IAM**: `lemlist-backup-weekly-role-XXXX` (con política `AmazonS3FullAccess`)

**Variables de entorno:**

| Clave | Valor | Descripción |
|-------|-------|-------------|
| `S3_BUCKET_NAME` | `2leap-lemlist-backup` | Bucket de destino |
| `S3_PREFIX` | `lemlist-backups` | Carpeta raíz dentro del bucket |
| `API_KEY_CLOUDPILES` | *(secret)* | API key del team Cloudpiles |
| `API_KEY_2LEAP` | *(secret)* | API key del team 2Leap |
| `API_KEY_SENIORADVISORM` | *(secret)* | API key de la cuenta Senior Advisor M |

### 2.2 EventBridge Schedules

| Nombre | Cron | Payload |
|--------|------|---------|
| `lemlist-backup-cloudpiles-schedule` | `0 1 ? * MON *` | `{"client_name":"cloudpiles","api_key_env_var":"API_KEY_CLOUDPILES"}` |
| `lemlist-backup-2leap-schedule` | `15 1 ? * MON *` | `{"client_name":"2leap","api_key_env_var":"API_KEY_2LEAP"}` |
| `lemlist-backup-senioradvisorm-schedule` | `30 1 ? * MON *` | `{"client_name":"senior-advisor-m","api_key_env_var":"API_KEY_SENIORADVISORM"}` |

Zonas horarias en UTC. España: invierno +1h, verano +2h.

Las ejecuciones están **escalonadas a 15 minutos** para evitar saturación del rate limit de Lemlist en clientes de la misma cuenta.

### 2.3 S3: `2leap-lemlist-backup`

- **Región**: `eu-west-1`
- **Versionado**: desactivado
- **Estructura**:

```
lemlist-backups/
├── <client_name>/
│   └── <YYYY-MM-DD>/
│       ├── campañas_resumen.csv
│       └── leads_<NombreCampaña>.csv
```

### 2.4 IAM

- **Usuario `lemlist-backup-bot`**: usado solo para el script local original. Tiene `AmazonS3FullAccess`. **No usado actualmente por la Lambda** (Lambda usa su propio rol de ejecución).
- **Rol Lambda**: `lemlist-backup-weekly-role-XXXX`, política `AmazonS3FullAccess` adjunta.

---

## 3. El código (`lambda_function.py`)

### Punto de entrada

```python
def lambda_handler(event, context):
    client_name = event.get("client_name")
    api_key_var = event.get("api_key_env_var")
    api_key = os.environ.get(api_key_var)
    ...
```

El handler espera un evento con dos campos: nombre del cliente y nombre de la variable de entorno donde está su API key.

### Funciones clave

| Función | Qué hace |
|---------|----------|
| `get_campaigns(api_key)` | Llama a `/api/campaigns` y devuelve la lista en JSON. |
| `get_campaign_leads_csv(camp_id, api_key)` | Llama a `/api/campaigns/{id}/export/leads`. Maneja **rate limiting (429)** con reintentos exponenciales (2s, 4s, 8s, 16s, 32s) hasta 5 intentos. |
| `campaigns_to_csv(campaigns)` | Convierte el JSON de campañas a CSV en memoria. Recoge todos los campos posibles (algunas campañas tienen claves extra como `archived`). |
| `upload_to_s3(content, s3_key)` | Sube el contenido como CSV con encoding UTF-8. |

### Manejo de errores

- **404** (campaña sin leads): se ignora silenciosamente.
- **429** (rate limit): reintento con backoff exponencial.
- **Otros errores HTTP**: lanzan excepción → Lambda registra el fallo en CloudWatch y devuelve `statusCode: 500`.
- **Pausa de 0.5s entre campañas**: evita saturar la API.

---

## 4. Mantenimiento

### 4.1 Añadir un nuevo cliente

1. Generar la API key en Lemlist (Settings → Integrations → API)
2. Lambda → Configuración → Variables de entorno → añadir: `API_KEY_NUEVOCLIENTE`
3. EventBridge → Crear nueva programación:
   - Nombre: `lemlist-backup-nuevocliente-schedule`
   - Cron: `45 1 ? * MON *` (escoger hora que no choque con las otras)
   - Destino: Lambda `lemlist-backup-weekly`
   - Payload:
     ```json
     {
       "client_name": "nuevo-cliente",
       "api_key_env_var": "API_KEY_NUEVOCLIENTE"
     }
     ```

**No hay que tocar el código de la Lambda.**

### 4.2 Cambiar la API key de un cliente

Si caduca o se regenera una API key en Lemlist:

1. Lambda → Configuración → Variables de entorno → Editar
2. Sustituir el valor de la variable correspondiente
3. Guardar

El cambio aplica inmediatamente sin redeploy.

### 4.3 Cambiar la frecuencia

EventBridge → Programaciones → seleccionar la programación → Editar → modificar la expresión cron.

Referencia rápida de cron:
- `0 1 ? * MON *` → lunes a las 01:00 UTC
- `0 1 1 * ? *` → día 1 de cada mes a las 01:00 UTC
- `0 1 ? * MON,THU *` → lunes y jueves a las 01:00 UTC

### 4.4 Probar manualmente

Lambda → Probar → crear/editar evento → poner el JSON del cliente → **Probar**.

### 4.5 Ver logs

CloudWatch → Log groups → `/aws/lambda/lemlist-backup-weekly` → seleccionar el log stream más reciente.

---

## 5. Resolución de problemas

| Síntoma | Causa probable | Solución |
|---------|---------------|----------|
| Lambda devuelve `400` con "Faltan client_name…" | Payload del evento mal configurado | Revisar el JSON de la programación en EventBridge |
| Lambda devuelve `500` con "Variable de entorno '…' no encontrada" | Nombre de variable mal escrito en el payload o falta la variable en Lambda | Comprobar que `api_key_env_var` del payload coincide con el nombre real de la variable |
| Error `401 Unauthorized` en logs | API key inválida o revocada en Lemlist | Generar nueva key en Lemlist y actualizar variable de entorno |
| Error `429` persistente | Lemlist está rate-limitando agresivamente | Aumentar `max_retries` o `time.sleep` entre campañas. Considerar separar más las programaciones |
| Lambda timeout (5 min) | Cliente tiene muchísimas campañas | Aumentar timeout en Configuración general (máximo 15 min). O paginar la lista de campañas |
| No aparece carpeta en S3 | La Lambda falló o no se disparó | Revisar CloudWatch Logs de esa fecha. Revisar que la programación esté **Habilitada** en EventBridge |
| `AccessDenied` al subir a S3 | Rol IAM sin permisos | Revisar que el rol de la Lambda tiene `AmazonS3FullAccess` |

---

## 6. Costes esperados

Con créditos AWS Initiate concedidos: **prácticamente 0 €**.

Sin créditos (estimación mensual):

| Servicio | Uso | Coste |
|----------|-----|-------|
| Lambda | 12 ejecuciones/mes × ~2 min × 512 MB | < 0,01 € (free tier de 1M ejecuciones/mes) |
| S3 | Almacenamiento (~ 100-500 MB/mes acumulado) | < 0,02 €/mes |
| EventBridge | 12 disparos/mes | Gratis (free tier 14M eventos/mes) |
| CloudWatch | < 1 GB de logs/mes | Gratis (free tier 5 GB) |
| **Total estimado** | | **< 0,05 € / mes** |

---

## 7. Seguridad y buenas prácticas implementadas

- **Sin credenciales en código**: todas las API keys están en variables de entorno de Lambda, cifradas en reposo por AWS.
- **Lambda usa rol IAM** en lugar de credenciales AWS hardcodeadas (principio de mínimo privilegio).
- **Rate limiting con backoff exponencial**: respeta los límites de la API de Lemlist.
- **Logging centralizado en CloudWatch**: trazabilidad completa de cada ejecución.
- **Programaciones escalonadas**: evitan saturar APIs externas.
- **Filtrado de campañas archivadas**: el backup solo conserva campañas activas, reduciendo ruido y coste.

---

## 8. Mejoras posibles

Para futuras iteraciones (no implementadas):

- **Notificaciones por email/Slack si falla la Lambda** → SNS topic + alarma de CloudWatch
- **Lifecycle policy en S3** → mover backups de más de 90 días a S3 Glacier (más barato)
- **Política IAM más restrictiva** → en vez de `AmazonS3FullAccess`, crear política custom que solo permita `PutObject` en el bucket concreto
- **Comparativa semana vs semana** → script que genere un informe de cambios (campañas nuevas, archivadas, etc.)
- **Backup incremental** → solo guardar campañas que han cambiado desde el último backup

---

## 9. Contacto inicial

Sistema desplegado por David Meléndez Pérez durante las prácticas de ASIR en 2Leap (mayo 2026).

Repositorio con el código fuente: https://github.com/DeamnZ/lemlist-backup-aws
