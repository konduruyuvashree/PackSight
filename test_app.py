import sys
import os
import io
from PIL import Image, ImageDraw

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)
os.chdir(current_dir)

from fastapi.testclient import TestClient
from main import app, get_db
import models
from database import Base, engine, SessionLocal

Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)

client = TestClient(app)

def create_dummy_image_bytes(text: str = 'TEST') -> bytes:
    img = Image.new('RGB', (400, 150), color=(255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((10, 10), text, fill=(0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()

def test_root():
    response = client.get('/')
    assert response.status_code == 200
    assert response.json()['service'] == 'PackSight API'
    print('[PASS] Root endpoint test passed')

def test_auth_and_scans():
    signup_payload = {
        'user_id': 'auditor1',
        'full_name': 'Auditor One',
        'password': 'securepassword123'
    }
    signup_resp = client.post('/auth/signup', json=signup_payload)
    assert signup_resp.status_code == 200, signup_resp.text
    token_data = signup_resp.json()
    assert 'access_token' in token_data
    assert token_data['user_id'] == 'auditor1'
    token = token_data['access_token']
    headers = {'Authorization': f'Bearer {token}'}
    print('[PASS] Auth signup test passed')

    dup_resp = client.post('/auth/signup', json=signup_payload)
    assert dup_resp.status_code == 400
    print('[PASS] Auth duplicate prevention test passed')

    login_resp = client.post('/auth/login', json={
        'user_id': 'auditor1',
        'password': 'securepassword123'
    })
    assert login_resp.status_code == 200
    assert 'access_token' in login_resp.json()
    print('[PASS] Auth login test passed')

    bad_login = client.post('/auth/login', json={
        'user_id': 'auditor1',
        'password': 'wrongpassword'
    })
    assert bad_login.status_code == 401
    print('[PASS] Auth wrong credentials check passed')

    img_bytes = create_dummy_image_bytes('MFG BY ACME FOODS NET WT 500g MRP RS 120 INCLUSIVE OF ALL TAXES')
    files = {'image': ('label.png', img_bytes, 'image/png')}
    data = {'product_name': 'Acme Biscuits 500g'}

    scan_resp = client.post('/scans', headers=headers, files=files, data=data)
    assert scan_resp.status_code == 200, scan_resp.text
    scan_data = scan_resp.json()
    assert scan_data['product_name'] == 'Acme Biscuits 500g'
    assert 'score' in scan_data
    assert 'fields' in scan_data
    assert len(scan_data['fields']) == 8
    scan_id = scan_data['id']
    print('[PASS] Single scan test passed')

    img1 = create_dummy_image_bytes('MFG BY PackSight Corp PKD 10/2026')
    img2 = create_dummy_image_bytes('NET WT 250g MRP RS 99 INCLUSIVE OF ALL TAXES CONSUMER CARE 1800123456')
    multi_files = [
        ('images', ('front.png', img1, 'image/png')),
        ('images', ('back.png', img2, 'image/png')),
    ]
    multi_resp = client.post('/scans/multi', headers=headers, files=multi_files, data={'product_name': 'Premium Tea'})
    assert multi_resp.status_code == 200, multi_resp.text
    multi_data = multi_resp.json()
    assert multi_data['product_name'] == 'Premium Tea'
    print('[PASS] Multi-panel scan test passed')

    list_resp = client.get('/scans', headers=headers)
    assert list_resp.status_code == 200
    scans_list = list_resp.json()
    assert len(scans_list) == 2
    print('[PASS] List scans test passed')

    stats_resp = client.get('/stats', headers=headers)
    assert stats_resp.status_code == 200
    stats = stats_resp.json()
    assert stats['total'] == 2
    assert 'compliant' in stats
    assert 'violations' in stats
    assert 'avg_score' in stats
    print('[PASS] Stats test passed')

    pdf_resp = client.get(f'/scans/{scan_id}/pdf', headers=headers)
    assert pdf_resp.status_code == 200
    assert pdf_resp.headers['content-type'] == 'application/pdf'
    assert pdf_resp.content.startswith(b'%PDF')
    print(f'[PASS] PDF report test passed (size: {len(pdf_resp.content)} bytes)')

if __name__ == '__main__':
    test_root()
    test_auth_and_scans()
    print('\nALL TESTS PASSED SUCCESSFULLY!')
