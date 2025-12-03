# ML Converter

Aplicación web en Python para procesar archivos Excel, convirtiendo automáticamente valores numéricos almacenados como texto al formato numérico apropiado.  
Especialmente útil para resúmenes de Mercado Pago.

## Características

- **Detección y Conversión Inteligente de Números**: Identifica columnas con valores numéricos en formato texto (ej: "$1,234.56", "1.234,56", "(123.45)") y los convierte a números reales, manejando formatos internacionales, símbolos de moneda y negativos en paréntesis.
- **Preserva Datos de Texto**: Columnas de texto (nombres, categorías, fechas) permanecen sin cambios.
- **Interfaz Web Simple**: UI responsiva en español, con soporte drag & drop, mensajes claros de éxito/error y resumen de totales, ingresos y egresos tras el procesamiento.
- **Manejo Seguro de Archivos**: Almacenamiento temporal en `/tmp/ml-converter/` y limpieza automática tras 30 minutos.
- **Validación Real de Archivos**: Verifica que el archivo subido sea realmente Excel, no solo por extensión.
- **Soporte de Formatos**: Acepta `.xlsx` y `.xls` (máx. 16MB).
- **Pruebas Automáticas**: Incluye tests para endpoints y validaciones.
- **Headers de Seguridad**: Cabeceras HTTP adicionales (HSTS, CSP, etc).

## Tech Stack

- **Backend**: Flask (Python), pandas, openpyxl
- **Frontend**: HTML5, Tailwind CSS, Jinja2
- **File Cleanup**: APScheduler
- **Containerización**: Docker Compose

## Configuración del Entorno

1. **Copia y edita el archivo de entorno:**

   ```bash
   cp env.example .env
   nvim .env
   ```

2. **Genera un SECRET_KEY seguro:**

   ```bash
   python3 -c "import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(32))"
   ```

   Actualiza `SECRET_KEY` y `DOMAIN` en `.env`.

3. **Variables importantes:**
   - `FLASK_ENV`: 'production' para producción
   - `MAX_CONTENT_LENGTH`: Tamaño máximo de archivo (por defecto: 16MB)

## Quick Start

### Opción 1: Entorno Virtual Python

```bash
./run.sh
```

O manualmente:

```bash
cd ml-converter
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python src/app.py
```

Visita [http://localhost:5000](http://localhost:5000)

### Opción 2: Docker

```bash
docker-compose up --build
```

Visita [http://localhost:5000](http://localhost:5000)

## Flujo de Uso

1. **Subi** tu archivo Excel (.xlsx/.xls) arrastrando o seleccionando.
2. **Procesa**: Haz clic en "Procesar Archivo". Las columnas numéricas en texto se convierten automáticamente.
3. **Descarga** el archivo procesado.
4. **Limpieza**: Los archivos temporales se eliminan automáticamente tras 30 minutos.

## API Endpoints

- `GET /` – Página principal de carga
- `POST /upload` – Subida y procesamiento de archivos
- `GET /download/<filename>` – Descarga del archivo procesado

## Despliegue en Producción

### Gunicorn

```bash
gunicorn -w 4 -b 0.0.0.0:5000 src.app:app
```

### Docker

```bash
docker compose up -d
```

## Estructura de Archivos

```
ml-converter/
├── src/
│   ├── app.py              # Aplicación principal Flask
│   ├── converters.py       # Helpers
│   └── templates/
│       ├── index.html      # Página de carga
│       └── download.html   # Página de descarga
├── tests/                  # Tests automáticos
├── requirements.txt        # Dependencias
├── Dockerfile
├── compose.yml
└── README.md
```

## Seguridad

- **Nombres de archivo seguros** (`secure_filename`)
- **Validación de tipo de archivo** (.xlsx/.xls y firma interna)
- **Límites de tamaño** (16MB)
- **Limpieza automática** (30 minutos)
- **Nombres de archivo únicos** (UUIDs para prevenir conflictos)
