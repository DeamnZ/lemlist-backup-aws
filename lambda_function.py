"""
Lemlist → AWS S3 Weekly Backup (AWS Lambda) — Multi-cliente
Punto de entrada: lambda_handler

Configuración por evento (lo que envía EventBridge):
{
    "client_name": "cloudpiles",          # nombre que aparecerá en la carpeta de S3
    "api_key_env_var": "API_KEY_CLOUDPILES"  # nombre de la variable de entorno con la API key
}
"""

import os
import boto3
import requests
import logging
import time
from io import StringIO
import csv
from datetime import datetime

# --- Configuración global ---
S3_BUCKET = os.environ["S3_BUCKET_NAME"]
S3_PREFIX = os.environ.get("S3_PREFIX", "lemlist-backups")

LEMLIST_BASE_URL = "https://api.lemlist.com/api"

# --- Logging ---
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# --- Cliente S3 (rol IAM de Lambda) ---
s3 = boto3.client("s3")


def get_campaigns(api_key):
    url = f"{LEMLIST_BASE_URL}/campaigns"
    resp = requests.get(url, auth=("", api_key), timeout=30)
    resp.raise_for_status()
    return resp.json()


def get_campaign_leads_csv(campaign_id, api_key, max_retries=5):
    """Obtiene CSV de leads con reintentos exponenciales si Lemlist rate-limita."""
    url = f"{LEMLIST_BASE_URL}/campaigns/{campaign_id}/export/leads"

    for intento in range(max_retries):
        resp = requests.get(url, auth=("", api_key), timeout=60)

        if resp.status_code == 404:
            logger.warning(f"Campaña {campaign_id}: sin leads exportables.")
            return ""

        if resp.status_code == 429:
            espera = 2 ** (intento + 1)
            logger.warning(f"Rate limit (429). Reintento {intento+1}/{max_retries} en {espera}s...")
            time.sleep(espera)
            continue

        resp.raise_for_status()
        return resp.text

    logger.error(f"Campaña {campaign_id}: rate limit persistente tras {max_retries} reintentos.")
    return ""


def campaigns_to_csv(campaigns):
    if not campaigns:
        return ""
    output = StringIO()
    campos = sorted({k for camp in campaigns for k in camp.keys()})
    writer = csv.DictWriter(output, fieldnames=campos, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(campaigns)
    return output.getvalue()


def upload_to_s3(content, s3_key):
    s3.put_object(
        Bucket=S3_BUCKET,
        Key=s3_key,
        Body=content.encode("utf-8"),
        ContentType="text/csv; charset=utf-8"
    )
    logger.info(f"Subido: s3://{S3_BUCKET}/{s3_key}")


def lambda_handler(event, context):
    # Sacar configuración del evento
    client_name = event.get("client_name")
    api_key_var = event.get("api_key_env_var")

    if not client_name or not api_key_var:
        msg = "Faltan 'client_name' o 'api_key_env_var' en el evento."
        logger.error(msg)
        return {"statusCode": 400, "error": msg}

    api_key = os.environ.get(api_key_var)
    if not api_key:
        msg = f"Variable de entorno '{api_key_var}' no encontrada en Lambda."
        logger.error(msg)
        return {"statusCode": 500, "error": msg}

    logger.info(f"=== Iniciando backup de cliente: {client_name} ===")
    fecha = datetime.now().strftime("%Y-%m-%d")
    subidos = 0

    # 1. Lista de campañas
    all_campaigns = get_campaigns(api_key)
    campaigns = [c for c in all_campaigns if not c.get("archived", False)]
    logger.info(
        f"[{client_name}] Campañas totales: {len(all_campaigns)} · "
        f"Activas: {len(campaigns)} · "
        f"Archivadas (omitidas): {len(all_campaigns) - len(campaigns)}"
    )

    # 2. Resumen general
    csv_campañas = campaigns_to_csv(campaigns)
    if csv_campañas:
        s3_key = f"{S3_PREFIX}/{client_name}/{fecha}/campañas_resumen.csv"
        upload_to_s3(csv_campañas, s3_key)
        subidos += 1

    # 3. Leads por campaña
    for camp in campaigns:
        camp_id   = camp.get("_id") or camp.get("id")
        camp_name = camp.get("name", camp_id)
        safe_name = "".join(c if c.isalnum() or c in "-_ " else "_" for c in camp_name)

        logger.info(f"[{client_name}] Exportando leads de: {camp_name}")
        csv_leads = get_campaign_leads_csv(camp_id, api_key)

        if csv_leads.strip():
            s3_key = f"{S3_PREFIX}/{client_name}/{fecha}/leads_{safe_name}.csv"
            upload_to_s3(csv_leads, s3_key)
            subidos += 1
        else:
            logger.info(f"  → Sin leads para {camp_name}, se omite.")

        time.sleep(0.5)

    logger.info(f"=== Backup completado para {client_name}: {subidos} ficheros subidos ===")
    return {
        "statusCode": 200,
        "client": client_name,
        "subidos": subidos,
        "campañas_activas": len(campaigns),
        "fecha": fecha
    }
