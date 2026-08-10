import uuid
import pytest
from fastapi.testclient import TestClient

from backend.domain.asset_registry.models import OCRRegistrationRecord
from backend.infrastructure.object_store import StubObjectStorage
import backend.infrastructure.object_store

from unittest.mock import patch

@pytest.fixture(autouse=True)
def override_object_storage():
    """Inject hermetic StubObjectStorage for testing into the controller namespace."""
    stub = StubObjectStorage()
    with patch("backend.domain.asset_registry.controller.object_storage", stub):
        yield stub

def test_ocr_upload_success_pipeline(client: TestClient, stub_repo):
    # Prepare dummy image payload mimicking Sticker_OCR upload
    files = {'file': ('bios_sticker.png', b'dummy_image_data_bytes', 'image/png')}
    headers = {'x-client-cert-fingerprint': 'test_agent_fingerprint_sha256'}

    # 1. Trigger API Upload
    response = client.post('/api/v1/assets/ocr-upload', files=files, headers=headers)
    
    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "success"
    assert data["extraction_status"] == "Pending"
    assert "task_id" in data
    assert "minio_uri" in data
    assert data["minio_uri"].startswith("s3://stub-bucket/stub-")

    # 2. Verify Repository Persistence (Offline testing via stub_repo)
    task_id = uuid.UUID(data["task_id"])
    record = stub_repo.ocr_storage.get(task_id)
    
    assert record is not None
    assert record.extraction_status == "Pending"
    assert record.minio_object_uri == data["minio_uri"]
    assert record.parsed_raw_text == {}

def test_ocr_upload_invalid_mime_type(client: TestClient):
    # Attempt to upload an invalid file type (e.g. text file instead of image/pdf)
    files = {'file': ('malicious.txt', b'hacker_code', 'text/plain')}
    headers = {'x-client-cert-fingerprint': 'test_agent_fingerprint_sha256'}

    response = client.post('/api/v1/assets/ocr-upload', files=files, headers=headers)
    
    # Core Law 5 RFC 7807 Exception expects strict HTTP code
    assert response.status_code == 415
    data = response.json()
    assert "Unsupported Media Type" in data["detail"]
