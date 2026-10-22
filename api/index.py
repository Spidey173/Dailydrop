import sys
import os

# Ensure the project root directory is on the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    from app import create_app
    app = create_app(os.getenv('FLASK_ENV', 'production'))
except Exception as exc:
    init_err_msg = str(exc)

    def app(environ, start_response):
        status = '503 Service Unavailable'
        error_msg = init_err_msg
        body = (
            "<!DOCTYPE html>"
            "<html><head><title>DailyDrop — Configuration Required</title>"
            "<meta name='viewport' content='width=device-width, initial-scale=1'>"
            "<style>body{font-family:system-ui,-apple-system,sans-serif;background:#0d1117;color:#c9d1d9;padding:40px;line-height:1.6;}"
            ".card{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:30px;max-width:700px;margin:40px auto;box-shadow:0 8px 24px rgba(0,0,0,0.5);}"
            "h1{color:#58a6ff;font-size:24px;margin-top:0;}code{background:#21262d;padding:3px 6px;border-radius:4px;color:#f0883e;font-size:13px;}"
            ".notice{background:#1f2937;border-left:4px solid #f59e0b;padding:12px;margin:16px 0;border-radius:4px;}"
            "ul{padding-left:20px;}li{margin-bottom:8px;}</style></head><body>"
            "<div class='card'>"
            "<h1>🚀 DailyDrop Serverless Deployment Notice</h1>"
            "<div class='notice'>"
            f"<strong>Startup Diagnostic:</strong> <code>{error_msg}</code>"
            "</div>"
            "<p>The application is deployed on Vercel, but required production environment variables have not been configured yet.</p>"
            "<p>To activate the store, navigate to your <strong>Vercel Dashboard &rarr; Settings &rarr; Environment Variables</strong> and configure:</p>"
            "<ul>"
            "<li><code>DATABASE_URL</code> &mdash; Neon PostgreSQL connection string (e.g. <code>postgresql://user:password@ep-xyz.neon.tech/neondb?sslmode=require</code>)</li>"
            "<li><code>SECRET_KEY</code> &mdash; A unique 32-byte secret key (e.g. from <code>python -c \"import secrets; print(secrets.token_hex(32))\"</code>)</li>"
            "<li><code>DISABLE_FILE_UPLOADS</code> &mdash; Set to <code>true</code> (required for Vercel's read-only serverless filesystem)</li>"
            "</ul>"
            "<p style='color:#8b949e;font-size:13px;margin-top:24px;'>Once configured, redeploy or trigger a new build on Vercel to launch the live storefront.</p>"
            "</div></body></html>"
        )
        response_headers = [
            ('Content-Type', 'text/html; charset=utf-8'),
            ('Content-Length', str(len(body.encode('utf-8'))))
        ]
        start_response(status, response_headers)
        return [body.encode('utf-8')]
