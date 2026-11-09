from pathlib import Path
from fastapi.testclient import TestClient
import app as project
from drive_sync import folder_id_from_url


def test_folder_id_parsing():
    assert folder_id_from_url('https://drive.google.com/drive/folders/abcdefghij123?usp=sharing') == 'abcdefghij123'
    assert folder_id_from_url('abcdefghij123') == 'abcdefghij123'
    assert folder_id_from_url('') == ''


def test_invalid_drive_folder():
    try:
        folder_id_from_url('https://evil.example/drive/folders/abc')
        assert False, 'should reject non-Drive host'
    except ValueError:
        pass


def test_api(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(project, 'STATE', tmp_path / 'state.json')
    monkeypatch.setattr(project, 'CACHE', tmp_path / 'cache')
    local = tmp_path / 'photos'
    local.mkdir()
    (local / 'sample.jpg').write_bytes(b'jpg')
    (local / 'video.mp4').write_bytes(b'mp4')
    (local / 'ignore.txt').write_text('no')
    with project.state_lock:
        project.config = {**project.DEFAULT_CONFIG, 'local_folder': str(local)}
    with TestClient(project.app) as client:
        result = client.get('/api/media')
        assert result.status_code == 200
        assert result.json()['total'] == 2
        for item in result.json()['items']:
            assert client.get(item['url']).status_code == 200
        assert client.get('/api/media/../../etc/passwd').status_code in (404, 422)
        assert client.patch('/api/config', json={'interval': 3, 'capacity': 12}).status_code == 200
        assert client.patch('/api/config', json={'interval': 0}).status_code == 422
        assert client.get('/display').status_code == 200
