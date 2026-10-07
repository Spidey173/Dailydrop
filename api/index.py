import sys
import os

# Ensure the project root directory is on the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app import create_app

app = create_app(os.getenv('FLASK_ENV', 'production'))
