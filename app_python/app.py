import os
import time
import socket
import platform
import logging
import json
import threading
from datetime import datetime, timezone
from flask import Flask, jsonify, request, Response
from pythonjsonlogger import jsonlogger
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST

app = Flask(__name__)

HOST = os.getenv('HOST', '0.0.0.0')
PORT = int(os.getenv('PORT', 5000))
DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'
DATA_DIR = os.getenv('DATA_DIR', '/data')
CONFIG_PATH = os.getenv('CONFIG_PATH', '/config/config.json')
VISITS_FILE = os.path.join(DATA_DIR, 'visits')

handler = logging.StreamHandler()
handler.setFormatter(jsonlogger.JsonFormatter(
    fmt='%(asctime)s %(name)s %(levelname)s %(message)s',
    rename_fields={'asctime': 'timestamp', 'name': 'logger', 'levelname': 'level'},
))
root_logger = logging.getLogger()
root_logger.handlers = [handler]
root_logger.setLevel(logging.INFO)
logger = logging.getLogger(__name__)

START_TIME = datetime.now(timezone.utc)
_visits_lock = threading.Lock()

http_requests_total = Counter(
    'http_requests_total',
    'Total number of HTTP requests',
    ['method', 'endpoint', 'status']
)

http_request_duration_seconds = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint'],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0]
)

http_requests_in_progress = Gauge(
    'http_requests_in_progress',
    'Number of HTTP requests currently being processed'
)

devops_info_endpoint_calls = Counter(
    'devops_info_endpoint_calls_total',
    'Total calls to each devops info endpoint',
    ['endpoint']
)

system_info_collection_seconds = Histogram(
    'devops_info_system_collection_seconds',
    'Time spent collecting system info in seconds',
    buckets=[0.0001, 0.0005, 0.001, 0.005, 0.01, 0.05, 0.1]
)

visits_counter_gauge = Gauge(
    'devops_info_visits_total',
    'Total visits to the root endpoint (persisted)'
)


def _read_visits():
    try:
        with open(VISITS_FILE, 'r') as f:
            return int((f.read() or '0').strip())
    except (FileNotFoundError, ValueError):
        return 0


def _write_visits(value):
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = VISITS_FILE + '.tmp'
    with open(tmp, 'w') as f:
        f.write(str(value))
    os.replace(tmp, VISITS_FILE)


def increment_visits():
    with _visits_lock:
        current = _read_visits() + 1
        try:
            _write_visits(current)
        except OSError as e:
            logger.warning("Visits file not writable", extra={'path': VISITS_FILE, 'error': str(e)})
        visits_counter_gauge.set(current)
        return current


def load_config():
    try:
        with open(CONFIG_PATH, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.warning("Config file not loaded", extra={'path': CONFIG_PATH, 'error': str(e)})
        return {}


def _normalize_path(path):
    known = {'/', '/health', '/metrics', '/visits', '/config'}
    return path if path in known else path


def get_uptime():
    delta = datetime.now(timezone.utc) - START_TIME
    seconds = int(delta.total_seconds())
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    return {
        'seconds': seconds,
        'human': f"{hours} hour{'s' if hours != 1 else ''}, {minutes} minute{'s' if minutes != 1 else ''}"
    }


def get_system_info():
    t0 = time.time()
    info = {
        'hostname': socket.gethostname(),
        'platform': platform.system(),
        'platform_version': platform.platform(),
        'architecture': platform.machine(),
        'cpu_count': os.cpu_count() or 1,
        'python_version': platform.python_version()
    }
    system_info_collection_seconds.observe(time.time() - t0)
    return info


@app.before_request
def before_request_metrics():
    request._start_time = time.time()
    http_requests_in_progress.inc()


@app.after_request
def after_request_metrics(response):
    duration = time.time() - getattr(request, '_start_time', time.time())
    path = _normalize_path(request.path)

    http_requests_total.labels(
        method=request.method,
        endpoint=path,
        status=str(response.status_code)
    ).inc()

    http_request_duration_seconds.labels(
        method=request.method,
        endpoint=path
    ).observe(duration)

    http_requests_in_progress.dec()
    return response


@app.before_request
def log_request():
    logger.info("HTTP request received", extra={
        'method': request.method,
        'path': request.path,
        'client_ip': request.remote_addr,
        'user_agent': request.headers.get('User-Agent', 'Unknown'),
    })


@app.after_request
def log_response(response):
    logger.info("HTTP response sent", extra={
        'method': request.method,
        'path': request.path,
        'status_code': response.status_code,
        'client_ip': request.remote_addr,
    })
    return response


@app.route('/metrics')
def metrics():
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)


@app.route('/')
def index():
    devops_info_endpoint_calls.labels(endpoint='/').inc()
    visits = increment_visits()
    uptime = get_uptime()
    system_info = get_system_info()
    cfg = load_config()
    response = {
        'service': {
            'name': 'devops-info-service',
            'version': '1.0.0',
            'description': 'DevOps course info service',
            'framework': 'Flask'
        },
        'system': system_info,
        'runtime': {
            'uptime_seconds': uptime['seconds'],
            'uptime_human': uptime['human'],
            'current_time': datetime.now(timezone.utc).isoformat(),
            'timezone': 'UTC'
        },
        'request': {
            'client_ip': request.remote_addr,
            'user_agent': request.headers.get('User-Agent', 'Unknown'),
            'method': request.method,
            'path': request.path
        },
        'visits': visits,
        'config': {
            'app_env': os.getenv('APP_ENV', 'unknown'),
            'log_level': os.getenv('LOG_LEVEL', 'INFO'),
            'feature_greeting': cfg.get('features', {}).get('greeting', False),
        },
        'endpoints': [
            {'path': '/', 'method': 'GET', 'description': 'Service information (increments visits)'},
            {'path': '/health', 'method': 'GET', 'description': 'Health check'},
            {'path': '/visits', 'method': 'GET', 'description': 'Current visits counter'},
            {'path': '/config', 'method': 'GET', 'description': 'Loaded configuration'},
            {'path': '/metrics', 'method': 'GET', 'description': 'Prometheus metrics'}
        ]
    }
    return jsonify(response)


@app.route('/health')
def health():
    devops_info_endpoint_calls.labels(endpoint='/health').inc()
    uptime = get_uptime()
    response = {
        'status': 'healthy',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'uptime_seconds': uptime['seconds']
    }
    return jsonify(response)


@app.route('/visits')
def visits():
    devops_info_endpoint_calls.labels(endpoint='/visits').inc()
    with _visits_lock:
        count = _read_visits()
    return jsonify({'visits': count, 'source': VISITS_FILE})


@app.route('/config')
def config_endpoint():
    devops_info_endpoint_calls.labels(endpoint='/config').inc()
    cfg = load_config()
    return jsonify({
        'file': CONFIG_PATH,
        'loaded': bool(cfg),
        'content': cfg,
        'env': {
            'APP_ENV': os.getenv('APP_ENV'),
            'LOG_LEVEL': os.getenv('LOG_LEVEL'),
            'FEATURE_FLAG_BETA': os.getenv('FEATURE_FLAG_BETA'),
        }
    })


@app.errorhandler(404)
def not_found(error):
    logger.warning("Endpoint not found", extra={'path': request.path})
    return jsonify({
        'error': 'Not Found',
        'message': 'Endpoint does not exist'
    }), 404


@app.errorhandler(500)
def internal_error(error):
    logger.error("Internal server error", extra={'error': str(error)}, exc_info=True)
    return jsonify({
        'error': 'Internal Server Error',
        'message': 'An unexpected error occurred'
    }), 500


if __name__ == '__main__':
    visits_counter_gauge.set(_read_visits())
    logger.info("Starting DevOps Info Service", extra={'host': HOST, 'port': PORT, 'data_dir': DATA_DIR})
    app.run(host=HOST, port=PORT, debug=DEBUG)
