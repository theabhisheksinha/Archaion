from pathlib import Path
from importlib.util import spec_from_file_location, module_from_spec
from dotenv import load_dotenv
import uvicorn
from fastapi.middleware.cors import CORSMiddleware
import sys

def load_app():
    repo_root = Path(__file__).resolve().parent
    handler_dir = repo_root / "amplify" / "functions" / "modernization-handler"
    handler_path = handler_dir / "handler.py"
    if not handler_path.exists():
        raise FileNotFoundError(str(handler_path))
    load_dotenv()
    sys.path.insert(0, str(handler_dir))
    spec = spec_from_file_location("modernization_handler", str(handler_path))
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    app = getattr(module, "app")
    return app

def ensure_cors(app):
    if not any(m.cls is CORSMiddleware for m in getattr(app, "user_middleware", [])):
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

if __name__ == "__main__":
    app = load_app()
    ensure_cors(app)
    uvicorn.run(app, host="127.0.0.1", port=8000)
