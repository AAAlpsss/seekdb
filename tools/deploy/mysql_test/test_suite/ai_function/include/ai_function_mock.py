#!/usr/bin/env python3
"""Deterministic local HTTP fixture for the AI function regression suite."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.request import urlopen


def response_for(path, body):
    if path.endswith('/chat/completions'):
        return {'choices': [{'message': {'role': 'assistant', 'content': 'mock:' + body['messages'][-1]['content']}}]}
    if path == '/api/generate':
        if body.get('stream') is not False:
            raise ValueError('Ollama requests must disable streaming')
        return {'response': 'mock:' + body['prompt'], 'done': True}
    if path.endswith('/embeddings') or path == '/api/embed':
        inputs = body['input']
        if isinstance(inputs, str):
            inputs = [inputs]
        dimension = body.get('dimensions', 768)
        if not isinstance(dimension, int) or not 1 <= dimension <= 4096:
            raise ValueError('invalid dimensions')
        embeddings = [[float(i + 1)] * dimension for i in range(len(inputs))]
        if path == '/api/embed':
            return {'embeddings': embeddings}
        return {'data': [{'index': i, 'embedding': embedding} for i, embedding in enumerate(embeddings)]}
    if path.endswith('/rerank'):
        return {'results': [{'index': i, 'relevance_score': 1.0 / (i + 1)} for i in range(len(body['documents']))]}
    raise ValueError('unsupported path: ' + path)


def state_dir(port):
    return Path('/tmp/seekdb_ai_function_mock_%d' % port)


def stop(port):
    pid_file = state_dir(port) / 'pid'
    if not pid_file.exists():
        return
    pid = int(pid_file.read_text())
    try:
        command = Path('/proc/%d/cmdline' % pid).read_bytes()
        if b'ai_function_mock.py' not in command or b'serve' not in command:
            raise RuntimeError('refusing to stop an unrelated process')
        os.kill(pid, signal.SIGTERM)
        for _ in range(100):
            if not Path('/proc/%d' % pid).exists():
                break
            time.sleep(0.01)
    except (FileNotFoundError, ProcessLookupError):
        pass
    pid_file.unlink(missing_ok=True)


def start(port):
    directory = state_dir(port)
    directory.mkdir(exist_ok=True)
    stop(port)
    with (directory / 'server.log').open('w') as output:
        process = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), 'serve', str(port)],
                                   stdin=subprocess.DEVNULL, stdout=output, stderr=output, start_new_session=True)
    (directory / 'pid').write_text(str(process.pid))
    for _ in range(100):
        if process.poll() is not None:
            break
        try:
            with urlopen('http://127.0.0.1:%d/health' % port, timeout=0.1) as request:
                if request.read() == b'seekdb-ai-function-mock':
                    return
        except OSError:
            time.sleep(0.02)
    stop(port)
    raise RuntimeError('AI function mock failed to start; see ' + str(directory / 'server.log'))


def serve(port):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            payload = b'seekdb-ai-function-mock'
            self.send_response(200)
            self.send_header('Content-Length', str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def do_POST(self):
            try:
                body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                payload = json.dumps(response_for(self.path, body), ensure_ascii=False).encode('utf-8')
                status = 200
            except (ValueError, KeyError, TypeError) as exc:
                status = 400
                payload = json.dumps({'error': str(exc)}).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    ThreadingHTTPServer(('127.0.0.1', port), Handler).serve_forever()


if __name__ == '__main__':
    {'start': start, 'stop': stop, 'serve': serve}[sys.argv[1]](int(sys.argv[2]))
