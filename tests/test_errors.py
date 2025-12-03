import io
import pandas as pd
import pytest
from src.app import app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_upload_no_file(client):
    response = client.post('/upload', data={}, follow_redirects=True)
    assert response.status_code == 200
    assert b"Archivo" in response.data or b"Subir Archivo" in response.data

def test_upload_invalid_extension(client):
    response = client.post('/upload', data={
        'file': (io.BytesIO(b"fake data"), 'test.txt')
    }, content_type='multipart/form-data', follow_redirects=True)
    assert response.status_code == 200
    assert b"Archivo" in response.data or b"Subir Archivo" in response.data

def test_upload_empty_file(client):
    response = client.post('/upload', data={
        'file': (io.BytesIO(), '')
    }, content_type='multipart/form-data', follow_redirects=True)
    assert response.status_code == 200
    assert b"Archivo" in response.data or b"Subir Archivo" in response.data
