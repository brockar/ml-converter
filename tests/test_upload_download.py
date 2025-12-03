import io
import os
import pandas as pd
import pytest
from src.app import app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_index_page(client):
    response = client.get('/')
    assert response.status_code == 200
    assert b"ML Converter" in response.data or b"Subir Archivo" in response.data

def test_upload_and_download(client):
    # Create a simple Excel file in memory
    df = pd.DataFrame({'words': ['one', 'two', 'three']})
    excel_file = io.BytesIO()
    df.to_excel(excel_file, index=False)
    excel_file.seek(0)

    # Upload the file
    response = client.post('/upload', data={
        'file': (excel_file, 'test.xlsx')
    }, content_type='multipart/form-data', follow_redirects=True)
    assert response.status_code == 200
    assert b"Descargar Archivo Procesado" in response.data or b"Procesamiento Completado" in response.data

def test_download_normalizes_and_confines_filename(client, tmp_path, monkeypatch):
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    monkeypatch.setitem(app.config, 'UPLOAD_FOLDER', str(upload_dir))

    safe_name = '123_processed_test.xlsx'
    file_path = upload_dir / safe_name
    file_path.write_bytes(b'dummy excel bytes')

    response = client.get(f"/download/..%5C{safe_name}")
    assert response.status_code == 200
    assert b'dummy excel bytes' in response.data
    content_disposition = response.headers.get('Content-Disposition', '')
    assert "attachment;" in content_disposition
    assert "convertido_test.xlsx" in content_disposition

def test_download_rejects_symlink_escape(client, tmp_path, monkeypatch):
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    outside_file = tmp_path / "outside.txt"
    outside_file.write_text("secret")
    monkeypatch.setitem(app.config, 'UPLOAD_FOLDER', str(upload_dir))

    symlink_path = upload_dir / "escape"
    os.symlink(outside_file, symlink_path)

    response = client.get("/download/escape", follow_redirects=False)
    # Should redirect back to index instead of serving the symlink target
    assert response.status_code == 302
