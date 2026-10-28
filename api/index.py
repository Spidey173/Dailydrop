import sys
import os

# Ensure the project root directory is on the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from flask import Flask, render_template_string, jsonify

def _init_serverless_app():
    # Secure serverless initialization: DATABASE_URL is injected via Vercel Environment Variables
    import hashlib
    import secrets
    from config import INSECURE_SECRET_KEYS, Config, ProductionConfig

    current_key = os.getenv('SECRET_KEY', '')
    if not current_key or len(current_key) < 16 or current_key in INSECURE_SECRET_KEYS:
        # If SECRET_KEY is not explicitly defined in Vercel settings (or is an insecure placeholder),
        # derive a strong, deployment-specific persistent key from the deployment's private DATABASE_URL
        # so all serverless lambdas share the same key without dropping sessions or exposing secrets.
        db_url = os.getenv('DATABASE_URL', '')
        if db_url:
            os.environ['SECRET_KEY'] = hashlib.sha256((db_url + ':dailydrop-app-secret-salt-2026').encode('utf-8')).hexdigest()
        else:
            os.environ['SECRET_KEY'] = secrets.token_hex(32)
    
    if os.getenv('SECRET_KEY'):
        Config.SECRET_KEY = os.environ['SECRET_KEY']
        ProductionConfig.SECRET_KEY = os.environ['SECRET_KEY']

    os.environ['DISABLE_FILE_UPLOADS'] = 'true'
    os.environ['VERCEL'] = '1'

    # Auto-sanitize REDIS_URL in environment if present
    if os.getenv('REDIS_URL'):
        from config import sanitize_redis_url
        clean_redis = sanitize_redis_url(os.environ['REDIS_URL'])
        os.environ['REDIS_URL'] = clean_redis
        Config.REDIS_URL = clean_redis
        ProductionConfig.REDIS_URL = clean_redis

    try:
        from app import create_app
        return create_app(os.getenv('FLASK_ENV', 'production'))
    except Exception as exc:
        # If environment variables (DATABASE_URL / SECRET_KEY) are not yet configured on Vercel,
        # serve an informative diagnostic Flask app instead of crashing the serverless runtime with FUNCTION_INVOCATION_FAILED
        init_err_msg = str(exc)
        fallback_app = Flask(__name__)

        @fallback_app.route('/healthz')
        @fallback_app.route('/api/v1/health')
        def serverless_health():
            return jsonify({
                "status": "degraded",
                "message": "DailyDrop serverless runtime active; configuration pending",
                "diagnostic": init_err_msg,
                "environment": os.getenv('FLASK_ENV', 'production')
            }), 503

        @fallback_app.route('/', defaults={'path': ''})
        @fallback_app.route('/<path:path>')
        def configuration_required(path):
            return render_template_string('''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>DailyDrop — Configuration Required</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0b0f19; color: #f3f4f6; margin: 0; padding: 40px 20px; display: flex; justify-content: center; align-items: center; min-height: 100vh; box-sizing: border-box; }
    .card { background: #111827; border: 1px solid #1f2937; border-radius: 12px; padding: 36px; max-width: 640px; width: 100%; box-shadow: 0 20px 40px rgba(0,0,0,0.4); }
    h1 { color: #10b981; font-size: 26px; margin: 0 0 12px 0; display: flex; align-items: center; gap: 8px; }
    p { color: #9ca3af; line-height: 1.6; margin: 0 0 16px 0; }
    .badge { display: inline-block; background: #1e3a8a; color: #93c5fd; padding: 4px 10px; border-radius: 6px; font-size: 13px; font-weight: 600; margin-bottom: 20px; }
    .diagnostic { background: #1f2937; border-left: 4px solid #f59e0b; padding: 14px 16px; border-radius: 4px; font-family: monospace; font-size: 13px; color: #fbbf24; margin-bottom: 24px; word-break: break-word; }
    h3 { color: #e5e7eb; font-size: 16px; margin: 20px 0 10px 0; }
    ul { margin: 0; padding-left: 20px; color: #d1d5db; line-height: 1.8; }
    code { background: #1f2937; padding: 2px 6px; border-radius: 4px; color: #34d399; font-size: 13px; font-family: monospace; }
    .footer { margin-top: 28px; padding-top: 16px; border-top: 1px solid #1f2937; font-size: 13px; color: #6b7280; text-align: center; }
  </style>
</head>
<body>
  <div class="card">
    <div class="badge">Vercel Serverless WSGI Active</div>
    <h1>DailyDrop 🛒</h1>
    <p>The application server is successfully running on Vercel, but required database credentials have not been configured in your hosting environment variables yet.</p>
    <div class="diagnostic">
      <strong>Startup Notice:</strong> {{ diagnostic }}
    </div>
    <h3>Next Steps to Activate Live Storefront:</h3>
    <p>Add the following environment variables in your <strong>Vercel Dashboard &rarr; Project Settings &rarr; Environment Variables</strong>:</p>
    <ul>
      <li><code>DATABASE_URL</code> &mdash; Your Neon PostgreSQL connection string</li>
      <li><code>SECRET_KEY</code> &mdash; A unique 32-byte secret key</li>
      <li><code>DISABLE_FILE_UPLOADS</code> &mdash; Set to <code>true</code> (required for Vercel serverless)</li>
    </ul>
    <div class="footer">
      DailyDrop E-Commerce &bull; Flask &bull; PostgreSQL &bull; Pytest Verified
    </div>
  </div>
</body>
</html>''', diagnostic=init_err_msg), 503

        return fallback_app

# Top-level ASGI/WSGI entrypoint instances recognized by Vercel's Python runtime
app = _init_serverless_app()
application = app
handler = app
