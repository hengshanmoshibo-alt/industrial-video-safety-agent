import os


os.environ.setdefault("DATABASE_URL", "sqlite:///./test_aicoding.db")
os.environ.setdefault("STORAGE_BACKEND", "local")
os.environ.setdefault("STORAGE_LOCAL_ROOT", "./data/test-storage")
