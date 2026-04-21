import os

class Config:
    def __init__(self):
        self.SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-me")
        self.SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///app.db")
        self.SQLALCHEMY_TRACK_MODIFICATIONS = False
        self.UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", "app/static/uploads")
        self.AVATAR_FOLDER = os.getenv("AVATAR_FOLDER", "app/static/avatars")
        self.MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", str(100 * 1024 * 1024))) # Default 100MB so optional step videos can post without extra env setup.
        self.FILE_STORAGE_API_BASE_URL = os.getenv("FILE_STORAGE_API_BASE_URL", "").rstrip("/")
        self.FILE_STORAGE_API_TOKEN = os.getenv("FILE_STORAGE_API_TOKEN", "")
        self.FILE_STORAGE_TIMEOUT_SECONDS = float(os.getenv("FILE_STORAGE_TIMEOUT_SECONDS", "10"))
        self.RECIPES_PER_PAGE = 9
        self.WTF_CSRF_TIME_LIMIT = None
        self.SEND_FILE_MAX_AGE_DEFAULT = 3600
