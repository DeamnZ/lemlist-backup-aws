# Lemlist → AWS S3 Weekly Backup

Sistema serverless multi-cliente que hace backup semanal de campañas y leads de Lemlist a Amazon S3.

Desplegado en producción durante mis prácticas de ASIR en **2Leap** (mayo 2026).

---

## Stack

- **AWS Lambda** (Python 3.14) — ejecución serverless del backup
- **AWS EventBridge Scheduler** — programación cron semanal
- **AWS S3** — almacenamiento de los CSVs
- **AWS IAM** — gestión de permisos con principio de mínimo privilegio
- **AWS CloudWatch** — logs y monitorización
- **API REST de Lemlist** — origen de los datos

---

## Arquitectura

```
┌──────────────────────────────────────────────────────────────────┐
│                AWS LAMBDA: lemlist-backup-weekly                 │
│   (Función única multi-cliente, lee la API key del evento)       │
└──────────────────────────────────────────────────────────────────┘
                              ▲
                              │ invoca
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
   EventBridge            EventBridge            EventBridge
   Cliente A              Cliente B              Cliente C
   Lun 01:00 UTC          Lun 01:15 UTC          Lun 01:30 UTC
        │                     │                     │
        ▼                     ▼                     ▼
        ┌─────────────────────────────────────────────────────┐
        │                  S3 (organizado por cliente)        │
        └─────────────────────────────────────────────────────┘
```

---

## Características

- **Multi-cliente**: una sola función Lambda procesa N clientes distintos. Cada uno con su propia API key y carpeta en S3.
- **Rate limiting inteligente**: reintentos con backoff exponencial (2s, 4s, 8s, 16s, 32s) cuando Lemlist devuelve 429.
- **Programaciones escalonadas**: cada cliente se ejecuta con 15 minutos de diferencia para no saturar la API.
- **Solo campañas activas**: filtra automáticamente las archivadas.
- **Sin credenciales en código**: API keys en variables de entorno de Lambda, AWS gestionado vía rol IAM.
- **Documentación completa**: manual de usuario para no técnicos y documentación técnica para mantenimiento.

---

## Estructura del repo

| Archivo | Descripción |
|---------|-------------|
| `lambda_function.py` | Código de la Lambda |
| `requirements.txt` | Dependencias Python (solo `requests`, `boto3` viene preinstalado en Lambda) |
| `.env.example` | Plantilla de configuración para pruebas en local |
| `MANUAL_USUARIO.md` | Guía para usuarios no técnicos: cómo descargar campañas de S3 |
| `DOCUMENTACION_TECNICA.md` | Arquitectura completa, troubleshooting, mantenimiento |

---

## Despliegue

Pasos resumidos (detalle completo en `DOCUMENTACION_TECNICA.md`):

1. Crear bucket S3 (región `eu-west-1`)
2. Crear función Lambda en Python 3.12+, subir el código empaquetado con dependencias
3. Configurar variables de entorno: `S3_BUCKET_NAME`, `S3_PREFIX`, una `API_KEY_*` por cliente
4. Aumentar timeout a 5 min y memoria a 512 MB
5. Adjuntar política `AmazonS3FullAccess` al rol de Lambda
6. Crear una programación EventBridge por cada cliente con el payload correspondiente

---

## Coste

Prácticamente **0 €** con AWS Free Tier. Estimación sin créditos: < 0,05 € al mes.

---

## Mejoras futuras

- Notificaciones por SNS/Slack si una Lambda falla
- Lifecycle policy en S3 para mover backups antiguos a Glacier
- Política IAM custom más restrictiva (solo `PutObject` en el bucket concreto)
- Informe semanal de cambios (campañas nuevas / archivadas)

---

## Autor

**David Meléndez Pérez** — Técnico ASIR
Madrid · 2026

[LinkedIn](https://www.linkedin.com/in/david-meléndez-pérez/)
