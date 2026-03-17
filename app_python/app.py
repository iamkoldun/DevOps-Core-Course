import os
import socket
import platform
import logging
from datetime import datetime, timezone
from flask import Flask, jsonify, request
from pythonjsonlogger import jsonlogger

app = Flask(__name__)

HOST = os.getenv('HOST', '0.0.0.0')
PORT = int(os.getenv('PORT', 5000))
DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'

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
    return {
        'hostname': socket.gethostname(),
        'platform': platform.system(),
        'platform_version': platform.platform(),
        'architecture': platform.machine(),
        'cpu_count': os.cpu_count() or 1,
        'python_version': platform.python_version()
    }

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

@app.route('/')
def index():
    uptime = get_uptime()
    system_info = get_system_info()
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
        'endpoints': [
            {'path': '/', 'method': 'GET', 'description': 'Service information'},
            {'path': '/health', 'method': 'GET', 'description': 'Health check'}
        ]
    }
    return jsonify(response)

@app.route('/health')
def health():
    uptime = get_uptime()
    response = {
        'status': 'healthy',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'uptime_seconds': uptime['seconds']
    }
    return jsonify(response)

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
    logger.info("Starting DevOps Info Service", extra={'host': HOST, 'port': PORT})
    app.run(host=HOST, port=PORT, debug=DEBUG)
