# Backups de Lemlist — Manual de usuario

Este sistema guarda automáticamente todas las campañas de Lemlist cada semana en AWS S3.
**No tienes que hacer nada para que funcione**: se ejecuta solo cada lunes de madrugada.

Este documento explica únicamente **cómo acceder a las campañas guardadas** cuando las necesites.

---

## Cuándo usarás este sistema

- Si alguna campaña se borra por error en Lemlist y quieres recuperar los datos.
- Si quieres consultar el estado de las campañas de una fecha pasada.
- Si quieres descargar leads de una campaña concreta.

---

## Cómo acceder a los backups (paso a paso)

### 1. Entra en AWS

Ve a [console.aws.amazon.com](https://console.aws.amazon.com) e inicia sesión con la cuenta de AWS de 2Leap.

### 2. Abre S3

En el buscador de arriba escribe **S3** y entra al servicio.

### 3. Abre el bucket de backups

Verás una lista de "buckets" (carpetas principales). Haz clic en:

**`2leap-lemlist-backup`**

### 4. Entra en la carpeta `lemlist-backups`

Dentro encontrarás tres subcarpetas, una por cada cliente:

| Carpeta | Qué contiene |
|---------|--------------|
| `cloudpiles/` | Campañas del team Cloudpiles |
| `2leap/` | Campañas del team 2Leap |
| `senior-advisor-m/` | Campañas de Senior Advisor M |

### 5. Elige la fecha del backup que quieres

Dentro de cada cliente verás carpetas con fechas (formato `AAAA-MM-DD`).
Cada carpeta es el backup de **ese lunes**.

Por ejemplo:
```
cloudpiles/
├── 2026-05-19/   ← backup del lunes 19 de mayo
├── 2026-05-26/   ← backup del lunes 26 de mayo
└── 2026-06-02/   ← backup del lunes 2 de junio
```

### 6. Descarga lo que necesites

Dentro de cada fecha encontrarás:

- **`campañas_resumen.csv`** → resumen de TODAS las campañas activas (estado, fechas, número de leads...)
- **`leads_NombreCampaña.csv`** → un fichero por cada campaña, con todos sus leads

Para descargar un fichero:
1. Haz clic en su nombre
2. Botón **Descargar**

El CSV se abre directamente con Excel.

---

## Preguntas frecuentes

### ¿Cuándo se hace el backup?
Cada **lunes** entre las **02:00 y las 03:30 de la madrugada** (hora España). Por la mañana ya está todo listo.

### ¿Se borran los backups antiguos?
**No.** Todos los backups se conservan para siempre. Si en un año necesitas las campañas de hace 8 meses, ahí seguirán.

### ¿Por qué algunas campañas no aparecen?
El sistema solo guarda **campañas activas** (no archivadas). Si una campaña fue archivada en Lemlist, deja de incluirse en los backups nuevos, pero los backups anteriores siguen teniéndola.

### Una campaña tiene caracteres raros en el nombre
Algunos caracteres no se pueden usar en nombres de fichero (como `/` o `?`). Se sustituyen por `_` automáticamente. El contenido del fichero es el correcto.

### ¿Cuánto cuesta esto?
Prácticamente **0 €**. AWS factura por almacenamiento y por cada ejecución. Con los créditos de AWS Initiate concedidos no hay coste real.

---

## Si algo no funciona

Si una semana el backup no aparece o falta una carpeta, contacta con quien lleve la parte técnica.

Hay **documentación técnica separada** (`DOCUMENTACION_TECNICA.md`) preparada para que cualquier técnico pueda revisar y mantener el sistema sin necesidad de empezar de cero.
