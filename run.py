"""
AutoApply — entry point.

Local dev:  python run.py
Production: gunicorn run:app   (Render uses the CMD in Dockerfile)
"""
import os
from autoapply.app import create_app

app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    debug = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug, use_reloader=False)
