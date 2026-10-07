import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--out', required=True, type=Path)
parser.add_argument('--directories', nargs='+', required=True, type=Path)
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
out = args.out.resolve()
assert out.is_relative_to(root / 'build') and not out.exists()
out.mkdir()
for directory in args.directories:
    assert (directory / 'protocol.json').exists() and not (directory / 'started.json').exists()
command = json.loads((root / 'build/v20-model-command.json').read_text('utf-8'))
with socket.socket() as client:
    assert client.connect_ex(('127.0.0.1', 51320)) != 0, 'Port already in use; do not adopt another server'
record = {'started_at': datetime.now(UTC).isoformat(), 'runs': [], 'owned_process': True, 'headless': True}
shutil.copyfile(__file__, out / 'runner.py')
shutil.copyfile(root / 'build/v20-model-provenance.json', out / 'model-provenance.json')
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
with (out / 'server.stdout.log').open('wb') as stdout, (out / 'server.stderr.log').open('wb') as stderr:
    child = subprocess.Popen(command, cwd=Path(command[0]).parent, stdout=stdout, stderr=stderr,
                             creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    record['pid'] = child.pid
    try:
        deadline = time.monotonic() + 150
        while True:
            if child.poll() is not None:
                raise RuntimeError('Owned model server exited; inspect retained server logs')
            try:
                with opener.open('http://127.0.0.1:51320/health', timeout=3) as response:
                    health = json.load(response)
                if health.get('status') == 'ok':
                    break
            except (OSError, ValueError, urllib.error.HTTPError):
                pass
            if time.monotonic() > deadline:
                raise TimeoutError('Owned model server readiness deadline exceeded')
            time.sleep(1)
        record['ready_at'] = datetime.now(UTC).isoformat()
        print('Owned local model ready', flush=True)
        for directory in args.directories:
            entry = {'directory': directory.as_posix(), 'started_at': datetime.now(UTC).isoformat()}
            record['runs'].append(entry)
            for verb, extra in [('run', ['--endpoint', 'http://127.0.0.1:51320/v1/chat/completions']), ('score', [])]:
                process = subprocess.run([sys.executable, '-X', 'utf8', '-m', 'tools.evaluate_mapping_v5', verb,
                                          '--directory', str(directory), *extra], cwd=root, check=False)
                entry[verb + '_returncode'] = process.returncode
                if process.returncode:
                    raise RuntimeError(f'{verb} failed for {directory}; preserve this attempt')
            entry['completed_at'] = datetime.now(UTC).isoformat()
        record['status'] = 'completed'
    except BaseException as exc:
        record.update(status='failed', error=type(exc).__name__, message=str(exc))
        raise
    finally:
        if child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=20)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=10)
        record.update(stopped_at=datetime.now(UTC).isoformat(), returncode=child.returncode,
                      owned_process_stopped=child.poll() is not None)
        (out / 'lifecycle.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8', newline='\n')
