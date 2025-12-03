import atexit
import logging
import os
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from threading import Lock

import pandas as pd
from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, flash, redirect, render_template, request, send_file, url_for
from werkzeug.utils import secure_filename

try:
    from src.converters import (
        convert_text_columns_to_numbers,
        find_columns_with_keywords,
        normalize_column_name,
    )
except ModuleNotFoundError as exc:
    if exc.name == "src":
        from converters import (
            convert_text_columns_to_numbers,
            find_columns_with_keywords,
            normalize_column_name,
        )
    else:
        raise

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-key-change-in-production")

# Logging setup
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.dirname(__file__)), "tmp")
ALLOWED_EXTENSIONS = {"xlsx", "xls"}
MAX_CONTENT_LENGTH_DEFAULT = 16 * 1024 * 1024  # 16MB max file size
MAX_CONTENT_LENGTH = int(
    os.environ.get("MAX_CONTENT_LENGTH", str(MAX_CONTENT_LENGTH_DEFAULT))
)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH

# Ensure upload directory exists for all entrypoints (app import, gunicorn workers, tests)
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

HSTS_POLICY = "max-age=31536000; includeSubDomains"
CSP_POLICY = (
    "default-src 'self'; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "script-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; "
    "font-src 'self' data:; "
    "connect-src 'self'; "
    "form-action 'self'; "
    "frame-ancestors 'none'; "
    "base-uri 'self'"
)
PERMISSIONS_POLICY = "geolocation=(), microphone=(), camera=()"


@app.after_request
def apply_security_headers(response):
    """Apply modern security headers to every response."""
    response.headers["Strict-Transport-Security"] = HSTS_POLICY
    response.headers["Content-Security-Policy"] = CSP_POLICY
    response.headers["Permissions-Policy"] = PERMISSIONS_POLICY
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def is_valid_excel_file(file_path):
    """
    Validate that the file is actually an Excel file by checking file signature (magic bytes)
    and attempting to read it with pandas.
    """
    try:
        file_size = os.path.getsize(file_path)
        if file_size == 0:
            logger.warning(f"Empty file rejected: {file_path}")
            return False

        if file_size > MAX_CONTENT_LENGTH:
            logger.warning(f"File too large rejected: {file_path} ({file_size} bytes)")
            return False

        # Check file signature (magic bytes)
        with open(file_path, "rb") as f:
            header = f.read(8)

        # Excel file signatures
        # .xlsx files start with PK (ZIP format)
        # .xls files start with specific OLE signatures
        xlsx_signature = (
            header.startswith(b"PK\x03\x04")
            or header.startswith(b"PK\x05\x06")
            or header.startswith(b"PK\x07\x08")
        )
        xls_signature = header.startswith(
            b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
        )  # OLE2 signature

        if not (xlsx_signature or xls_signature):
            logger.warning(f"Invalid file signature for {file_path}: {header.hex()}")
            return False

        # Try to read with pandas as additional validation
        # Use nrows=1 to minimize resource usage and prevent potential DoS
        df = pd.read_excel(file_path, nrows=1)

        if df is None:
            return False

        return True

    except Exception as e:
        logger.warning(f"File validation failed for {file_path}: {str(e)}")
        return False


def cleanup_old_files():
    """Remove files older than 1 hour from the temp directory."""
    try:
        current_time = datetime.now()
        for filename in os.listdir(UPLOAD_FOLDER):
            file_path = os.path.join(UPLOAD_FOLDER, filename)
            if os.path.isfile(file_path):
                file_time = datetime.fromtimestamp(os.path.getctime(file_path))
                if current_time - file_time > timedelta(minutes=30):
                    os.remove(file_path)
                    logger.info("Deleted old file: %s", filename)
    except Exception as e:
        logger.exception("Error during cleanup: %s", e)


_scheduler_lock = Lock()
_scheduler = None
_scheduler_shutdown_registered = False


def _shutdown_scheduler():
    global _scheduler
    with _scheduler_lock:
        if _scheduler and _scheduler.running:
            logger.info("Shutting down cleanup scheduler")
            _scheduler.shutdown()


def start_cleanup_scheduler():
    """Ensure the cleanup scheduler starts only once per process."""
    global _scheduler, _scheduler_shutdown_registered
    with _scheduler_lock:
        if _scheduler is None:
            _scheduler = BackgroundScheduler()
            _scheduler.add_job(
                func=cleanup_old_files,
                trigger="interval",
                minutes=10,
                id="cleanup-old-files",
                replace_existing=True,
            )
        if not _scheduler.running:
            logger.info("Starting cleanup scheduler")
            _scheduler.start()
            if not _scheduler_shutdown_registered:
                atexit.register(_shutdown_scheduler)
                _scheduler_shutdown_registered = True
    return _scheduler


start_cleanup_scheduler()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/upload", methods=["GET", "POST"])
def upload_file():
    if request.method == "GET":
        return redirect(url_for("index"))

    if "file" not in request.files:
        flash("No se seleccionó ningún archivo")
        logger.info("Upload attempted with no file in request")
        return redirect(request.url)

    file = request.files["file"]
    if file.filename == "":
        flash("No se seleccionó ningún archivo")
        logger.info("Upload attempted with empty filename")
        return redirect(request.url)

    if file and allowed_file(file.filename):
        try:
            original_filename = secure_filename(file.filename)
            unique_id = str(uuid.uuid4())
            upload_path = os.path.join(
                app.config["UPLOAD_FOLDER"], f"{unique_id}_original_{original_filename}"
            )
            file.save(upload_path)
            logger.info("File uploaded: %s -> %s", original_filename, upload_path)

            if not is_valid_excel_file(upload_path):
                os.remove(upload_path)
                flash(
                    "El archivo no es un archivo Excel válido. Por favor sube un archivo Excel real."
                )
                logger.warning("Invalid Excel file rejected: %s", original_filename)
                return redirect(url_for("index"))

            logger.info("Starting processing of %s", upload_path)
            df = pd.read_excel(upload_path)
            processed_df, converted_columns = convert_text_columns_to_numbers(df)
            date_keywords = ["fecha", "liberacion", "liberación"]
            date_cols = find_columns_with_keywords(processed_df.columns, date_keywords)

            for col in date_cols:
                processed_df[col] = pd.to_datetime(processed_df[col], errors="coerce")
                # Remove timezone info if present (Excel does not support tz-aware datetimes)
                if pd.api.types.is_datetime64_any_dtype(processed_df[col]):
                    try:
                        processed_df[col] = processed_df[col].dt.tz_localize(None)
                    except (AttributeError, TypeError):
                        pass

            sum_h = sum_h_pos = sum_h_neg = None
            if processed_df.shape[1] > 7:
                col_h = processed_df.iloc[:, 7]
                col_h_numeric = pd.to_numeric(col_h, errors="coerce")
                sum_h = col_h_numeric.sum(skipna=True)
                sum_h_pos = col_h_numeric[col_h_numeric > 0].sum(skipna=True)
                sum_h_neg = col_h_numeric[col_h_numeric < 0].sum(skipna=True)

            processed_filename = f"{unique_id}_processed_{original_filename}"
            processed_path = os.path.join(
                app.config["UPLOAD_FOLDER"], processed_filename
            )

            # Use ExcelWriter to set date, ID, and money column formats
            with pd.ExcelWriter(
                processed_path, engine="xlsxwriter", date_format="yyyy-mm-dd"
            ) as writer:
                processed_df.to_excel(writer, index=False)
                workbook = writer.book
                worksheet = writer.sheets["Sheet1"]
                date_format = workbook.add_format({"num_format": "yyyy-mm-dd"})
                id_format = workbook.add_format({"num_format": "0", "align": "left"})
                money_format = workbook.add_format({"num_format": "$ #,##0.00"})

                header_format = workbook.add_format(
                    {
                        "text_wrap": True,
                        "bold": True,
                        "align": "center",
                        "valign": "vcenter",
                    }
                )
                worksheet.set_row(0, 40)
                # Set all columns to width 20
                for col_idx in range(len(processed_df.columns)):
                    worksheet.set_column(col_idx, col_idx, 20)
                # Overwrite header row with header_format to ensure wrap
                for col_idx, value in enumerate(processed_df.columns):
                    worksheet.write(0, col_idx, value, header_format)

                # Define normalized money columns
                money_col_targets = [
                    "valor de la compra",
                    "comision mas iva",
                    "comisión más iva",
                    "monto neto de operacion",
                    "monto neto de operación",
                    "impuestos cobrados por retenciones iibb",
                ]

                # Set date columns
                for col in date_cols:
                    col_idx = processed_df.columns.get_loc(col)
                    worksheet.set_column(col_idx, col_idx, 20, date_format)
                # Set ID columns to integer format, wide enough to avoid scientific notation
                for col in processed_df.columns:
                    norm_col = normalize_column_name(col)
                    if "id" in norm_col:
                        col_idx = processed_df.columns.get_loc(col)
                        worksheet.set_column(col_idx, col_idx, 15, id_format)
                # Set money columns to currency format
                for col in processed_df.columns:
                    norm_col = normalize_column_name(col)
                    if norm_col in money_col_targets:
                        col_idx = processed_df.columns.get_loc(col)
                        worksheet.set_column(col_idx, col_idx, 15, money_format)
            logger.info("Processed file saved: %s", processed_path)

            os.remove(upload_path)
            logger.info("Removed original uploaded file: %s", upload_path)

            return render_template(
                "download.html",
                filename=processed_filename,
                original_name=original_filename,
                sum_h=sum_h,
                sum_h_pos=sum_h_pos,
                sum_h_neg=sum_h_neg,
            )

        except Exception as e:
            # Clean up uploaded file in case of any error
            try:
                if "upload_path" in locals() and os.path.exists(upload_path):
                    os.remove(upload_path)
                    logger.info("Cleaned up file after error: %s", upload_path)
            except Exception as cleanup_error:
                logger.exception("Error during cleanup: %s", cleanup_error)

            # Generic error message to avoid information disclosure
            flash(
                "Error procesando el archivo. Por favor verifica que sea un archivo Excel válido."
            )
            logger.exception(
                "File processing error for %s: %s",
                original_filename if "original_filename" in locals() else "unknown",
                str(e),
            )
            return redirect(url_for("index"))
    else:
        flash(
            "Tipo de archivo inválido. Por favor sube un archivo Excel (.xlsx o .xls)"
        )
        logger.info(
            "Rejected upload - invalid file type: %s", file.filename if file else None
        )
        return redirect(url_for("index"))


@app.route("/download/<filename>")
def download_file(filename):
    try:
        logger.info("Download requested for: %s", filename)
        normalized_filename = secure_filename(filename)

        if not normalized_filename:
            logger.warning(
                "Rejected download with empty normalized filename: %s", filename
            )
            flash("Archivo no encontrado o ha expirado")
            return redirect(url_for("index"))

        if normalized_filename != filename:
            logger.info(
                "Normalized download filename from %s to %s",
                filename,
                normalized_filename,
            )

        upload_root = Path(app.config["UPLOAD_FOLDER"]).resolve()
        requested_path = upload_root / normalized_filename

        try:
            resolved_path = requested_path.resolve(strict=True)
        except FileNotFoundError:
            logger.info("File not found or expired: %s", requested_path)
            flash("Archivo no encontrado o ha expirado")
            return redirect(url_for("index"))

        try:
            resolved_path.relative_to(upload_root)
        except ValueError:
            logger.warning(
                "Rejected download outside upload directory: %s -> %s",
                filename,
                resolved_path,
            )
            flash("Archivo no encontrado o ha expirado")
            return redirect(url_for("index"))

        if resolved_path.is_file():
            logger.info("Serving file: %s", resolved_path)
            download_name = f"convertido_{normalized_filename.split('_', 2)[-1]}"
            return send_file(
                resolved_path, as_attachment=True, download_name=download_name
            )

        logger.info("Path is not a regular file or has expired: %s", resolved_path)
        flash("Archivo no encontrado o ha expirado")
        return redirect(url_for("index"))
    except Exception as e:
        logger.exception("Error serving download: %s", e)
        flash(f"Error descargando el archivo: {str(e)}")
        return redirect(url_for("index"))


if __name__ == "__main__":
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    app.run(debug=True, host="0.0.0.0", port=5000)
