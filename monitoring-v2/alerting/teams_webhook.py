"""
Teams Webhook Receiver for Grafana / Prometheus Alertmanager
------------------------------------------------------------
Alertmanager POSTs to this service; it forwards the alert as an HTML
message to the configured Microsoft Teams channel via the Graph API.

Usage:
    python teams_webhook.py          # runs on port 9099

Environment variables (loaded from .env):
    TEAMS_CLIENT_ID
    TEAMS_CLIENT_SECRET
    TEAMS_TENANT_ID
    TEAMS_USERNAME
    TEAMS_PASSWORD
    TEAMS_TEAM_ID
    TEAMS_CHANNEL_ID
"""

import os
import json
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import quote
from urllib.request import urlopen, Request
from urllib.error import URLError

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
CLIENT_ID     = os.environ.get('TEAMS_CLIENT_ID', '')
CLIENT_SECRET = os.environ.get('TEAMS_CLIENT_SECRET', '')
TENANT_ID     = os.environ.get('TEAMS_TENANT_ID', '')
USERNAME      = os.environ.get('TEAMS_USERNAME', '')
PASSWORD      = os.environ.get('TEAMS_PASSWORD', '')
TEAM_ID       = os.environ.get('TEAMS_TEAM_ID', '')
CHANNEL_ID    = os.environ.get('TEAMS_CHANNEL_ID', '')
PORT          = int(os.environ.get('TEAMS_WEBHOOK_PORT', 9099))

SEVERITY_COLOR = {
    'critical': '#D32F2F',
    'warning':  '#F57C00',
    'info':     '#1976D2',
}

# ---------------------------------------------------------------------------
# Graph API helpers
# ---------------------------------------------------------------------------

def get_token():
    """Get a fresh OAuth2 bearer token via ROPC flow."""
    from urllib.parse import urlencode
    token_url = f'https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token'
    body = urlencode({
        'grant_type': 'password',
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'username': USERNAME,
        'password': PASSWORD,
        'scope': 'https://graph.microsoft.com/.default',
    }).encode()
    req = Request(token_url, data=body, method='POST')
    with urlopen(req) as resp:
        return json.load(resp)['access_token']


def send_teams_message(html_content):
    """POST an HTML message to the configured Teams channel."""
    token = get_token()
    encoded_ch = quote(CHANNEL_ID, safe='')
    url = f'https://graph.microsoft.com/v1.0/teams/{TEAM_ID}/channels/{encoded_ch}/messages'
    payload = json.dumps({'body': {'contentType': 'html', 'content': html_content}}).encode()
    req = Request(url, data=payload, method='POST', headers={
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
    })
    with urlopen(req) as resp:
        return json.load(resp)

# ---------------------------------------------------------------------------
# Alert formatting
# ---------------------------------------------------------------------------

def format_alert(alert):
    """Convert a single Alertmanager alert dict to an HTML Teams message."""
    labels      = alert.get('labels', {})
    annotations = alert.get('annotations', {})
    status      = alert.get('status', 'firing')
    severity    = labels.get('severity', 'info').lower()
    color       = SEVERITY_COLOR.get(severity, '#607D8B')

    name        = labels.get('alertname', 'Alert')
    summary     = annotations.get('summary', name)
    description = annotations.get('description', '')
    instance    = labels.get('instance', labels.get('job', ''))
    module      = labels.get('module', 'PediatricLegLength')

    html = (
        f'<b>BLL Pipeline Alert - {name}</b><br>'
        f'<b>Status:</b> <span style="color:{color}">{status.upper()}</span><br>'
        f'<b>Severity:</b> {severity}<br>'
    )
    if instance:
        html += f'<b>Instance:</b> {instance}<br>'
    html += f'<b>Summary:</b> {summary}<br>'
    if description:
        html += f'<b>Details:</b> {description}<br>'
    html += f'<b>Server:</b> psrplamradgpu01 | <b>Module:</b> {module}'
    return html


# ---------------------------------------------------------------------------
# HTTP request handler
# ---------------------------------------------------------------------------

class AlertHandler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        logger.info(fmt % args)

    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        body   = self.rfile.read(length)

        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            logger.error('Invalid JSON payload')
            self._respond(400)
            return

        alerts = payload.get('alerts', [])
        logger.info(f'Received {len(alerts)} alert(s), status={payload.get("status")}')

        for alert in alerts:
            try:
                html = format_alert(alert)
                result = send_teams_message(html)
                logger.info(f'Sent alert to Teams: {result.get("id")}')
            except URLError as exc:
                logger.error(f'Teams API error: {exc}')
            except Exception as exc:
                logger.error(f'Unexpected error: {exc}')

        self._respond(200)

    def do_GET(self):
        # Health check
        self._respond(200, b'OK')

    def _respond(self, code, body=b''):
        self.send_response(code)
        self.end_headers()
        self.wfile.write(body)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    server = HTTPServer(('0.0.0.0', PORT), AlertHandler)
    logger.info(f'Teams webhook receiver listening on :{PORT}')
    server.serve_forever()
