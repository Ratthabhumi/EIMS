"""Synthetic uploads only; rejected requests must not reach persistence/search."""
import asyncio
from io import BytesIO
import pytest
from fastapi import HTTPException, UploadFile
from backend.domain.analyzer.services.upload_validation import validate_evidence_upload
from backend.domain.analyzer.services.bundle import validate_bundle, BUNDLE_MAX_FILE_BYTES
from backend.api.routers.analyzer.analyze import submit_analysis

@pytest.mark.parametrize('name,body',[
    ('report.exe',b'not a log'),('log.txt:stream.log',b'failed'),
    ('bad\x00name.txt',b'failed'),('binary.log',b'header\x00payload'),
    ('fake.evtx',b'not an event file'),('empty.txt',b''),('bad.log',b'\xff\xfe')])
def test_untrusted_names_and_content_rejected(name,body):
    with pytest.raises(ValueError):validate_evidence_upload(name,body)

def test_client_path_is_display_basename_only():
    assert validate_evidence_upload(r'C:\fakepath\synthetic.log',b'Error: test')=='synthetic.log'

def test_json_evidence_supported_consistently():
    assert validate_bundle([('synthetic.json',b'{"level":"error"}')])[0][0]=='synthetic.json'

@pytest.mark.parametrize('name,body,code',[
    ('report.exe',b'not a log',400),('binary.txt',b'\x00',400),
    ('large.log',b'x'*(BUNDLE_MAX_FILE_BYTES+1),413)],ids=['unsupported-type','binary-content','oversize-file'])
def test_rejected_single_upload_has_actionable_4xx_without_db(name,body,code):
    file=UploadFile(filename=name,file=BytesIO(body))
    with pytest.raises(HTTPException) as exc:
        asyncio.run(submit_analysis(text=None,file=file,language='en',db=None,_user='synthetic',x_gemini_api_key=None))
    assert exc.value.status_code==code

def test_oversize_paste_rejected_without_db():
    with pytest.raises(HTTPException) as exc:
        asyncio.run(submit_analysis(text='x'*(BUNDLE_MAX_FILE_BYTES+1),file=None,language='en',db=None,_user='synthetic',x_gemini_api_key=None))
    assert exc.value.status_code==413

def test_image_extension_cannot_disguise_text():
    with pytest.raises(ValueError):validate_evidence_upload('fake.png',b'not an image',allow_images=True)


def test_ocr_upscale_keeps_pixel_budget_and_sets_timeout(monkeypatch):
    from PIL import Image
    from backend.api.routers.analyzer import analyze
    image=Image.new('RGB',(1,8000));payload=BytesIO();image.save(payload,format='PNG')
    requested=[];calls=[]
    def resize_without_allocating(self,size,*a,**kw):
        requested.append(size)
        return self
    monkeypatch.setattr(Image.Image,'resize',resize_without_allocating)
    monkeypatch.setattr(analyze.pytesseract,'image_to_string',lambda *a,**kw: calls.append(kw) or 'Synthetic OCR evidence')
    text,_=analyze._process_upload(payload.getvalue(),'synthetic-tall.png','image/png')
    assert text=='Synthetic OCR evidence'
    assert requested and all(w*h<=8_000_000 for w,h in requested)
    assert all(call.get('timeout')==30 for call in calls)
