from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_csv_export_download():
    r = client.get('/reports/export.csv?hours=24')
    assert r.status_code == 200
    assert 'attachment' in r.headers.get('content-disposition', '')
    assert 'text/csv' in r.headers.get('content-type', '')
    assert r.content.startswith(b'\xef\xbb\xbf')

def test_pdf_export_download():
    r = client.get('/reports/export.pdf?hours=24')
    assert r.status_code == 200
    assert 'attachment' in r.headers.get('content-disposition', '')
    assert 'application/pdf' in r.headers.get('content-type', '')
    assert r.content.startswith(b'%PDF')
