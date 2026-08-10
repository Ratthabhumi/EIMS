import requests
import json
import io
import time
from PIL import Image, ImageDraw, ImageFont

BASE_URL = "https://log-analyst-backend.onrender.com/api/v1"

def login():
    resp = requests.post(f"{BASE_URL}/auth/login", json={"username": "admin", "password": "P@ssw0rd"})
    if resp.status_code == 200:
        return {"Authorization": f"Bearer {resp.json()['access_token']}"}
    raise Exception(f"Login failed: {resp.text}")

def create_dummy_image(text):
    # Create a simple image with text for OCR
    img = Image.new('RGB', (800, 200), color=(255, 255, 255))
    d = ImageDraw.Draw(img)
    # Use default font
    d.text((10,10), text, fill=(0,0,0))
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='PNG')
    return img_byte_arr.getvalue()

def run_accuracy_tests():
    headers = login()
    results = []

    # Test 1: Text - Event ID 41 (Kernel-Power)
    print("Running Test 1: Event ID 41 (Text)...")
    text_41 = "Log Name: System\nSource: Microsoft-Windows-Kernel-Power\nEvent ID: 41\nLevel: Critical\nDescription: The system has rebooted without cleanly shutting down first. This error could be caused if the system stopped responding, crashed, or lost power unexpectedly."
    resp = requests.post(f"{BASE_URL}/analyze/", data={"text": text_41, "language": "th"}, headers=headers)
    results.append({"name": "Test 1: Event 41 (Text)", "data": resp.json()})
    time.sleep(2)

    # Test 2: XML - Event ID 10016 (DistributedCOM)
    print("Running Test 2: Event ID 10016 (XML)...")
    xml_10016 = """<Event xmlns="http://schemas.microsoft.com/win/2004/08/events/event">
      <System>
        <Provider Name="Microsoft-Windows-DistributedCOM" Guid="{1B562E86-B7AA-4131-BADC-B6F3A001407E}" EventSourceName="DCOM" />
        <EventID Qualifiers="0">10016</EventID>
        <Level>2</Level>
        <Task>0</Task>
        <Keywords>0x8080000000000000</Keywords>
        <TimeCreated SystemTime="2024-01-01T12:00:00.000Z" />
        <EventRecordID>12345</EventRecordID>
        <Channel>System</Channel>
        <Computer>MyPC</Computer>
        <Security UserID="S-1-5-19" />
      </System>
      <EventData>
        <Data Name="param1">application-specific</Data>
        <Data Name="param2">Local</Data>
        <Data Name="param3">Activation</Data>
      </EventData>
    </Event>"""
    resp = requests.post(f"{BASE_URL}/analyze/", data={"language": "th"}, files={"file": ("event.xml", xml_10016, "text/xml")}, headers=headers)
    results.append({"name": "Test 2: Event 10016 (XML)", "data": resp.json()})
    time.sleep(2)

    # Test 3: Image - Event ID 7034 (Service Control Manager)
    print("Running Test 3: Event ID 7034 (Image)...")
    # For OCR to work properly, we need a clear image
    img_text = "Event ID: 7034\nSource: Service Control Manager\nDescription: The Application Experience service terminated unexpectedly.  It has done this 1 time(s)."
    img_data = create_dummy_image(img_text)
    resp = requests.post(f"{BASE_URL}/analyze/", data={"language": "th"}, files={"file": ("error.png", img_data, "image/png")}, headers=headers)
    results.append({"name": "Test 3: Event 7034 (Image OCR)", "data": resp.json()})

    with open("accuracy_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print("Accuracy tests completed. Results saved to accuracy_results.json.")

if __name__ == "__main__":
    run_accuracy_tests()
