import os
from pathlib import Path
from dotenv import load_dotenv

# Base project directory
BASE_DIR = Path(__file__).resolve().parent

# Load environment variables from .env file if present
load_dotenv(BASE_DIR / '.env')


def normalize_database_url(url: str) -> str:
    """
    Ensure compatibility with SQLAlchemy 2.0+ and psycopg2/psycopg3.
    Converts legacy 'postgres://' prefixes (used by Heroku/Render/Railway) to 'postgresql://'.
    """
    if not url:
        return ''
    url = url.strip()
    if url.startswith('postgres://'):
        url = url.replace('postgres://', 'postgresql://', 1)
    return url


class Config:
    """Base configuration."""
    SECRET_KEY = os.getenv('SECRET_KEY', 'cctv-secure-dev-key-change-in-production')
    
    # Database configuration
    raw_db_url = os.getenv('DATABASE_URL')
    if raw_db_url:
        SQLALCHEMY_DATABASE_URI = normalize_database_url(raw_db_url)
    else:
        # Default fallback to SQLite in instance directory
        default_db_path = BASE_DIR / 'instance' / 'cctv_software.db'
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{default_db_path.as_posix()}"
        
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Configure production-safe connection pooling for PostgreSQL
    is_postgres = SQLALCHEMY_DATABASE_URI.startswith('postgresql')
    if is_postgres:
        SQLALCHEMY_ENGINE_OPTIONS = {
            'pool_pre_ping': True,     # Test connection liveness before checkout
            'pool_recycle': 300,       # Recycle connection after 5 minutes
            'pool_size': int(os.getenv('DB_POOL_SIZE', '10')),
            'max_overflow': int(os.getenv('DB_MAX_OVERFLOW', '20')),
            'pool_timeout': 30,
            'connect_args': {
                'keepalives': 1,
                'keepalives_idle': 30,
                'keepalives_interval': 10,
                'keepalives_count': 5,
            }
        }
    else:
        # SQLite configuration
        SQLALCHEMY_ENGINE_OPTIONS = {}

    # File Storage Paths
    UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', str(BASE_DIR / 'excel_import'))
    PDF_FOLDER = os.getenv('PDF_FOLDER', str(BASE_DIR / 'pdf'))
    MAX_CONTENT_LENGTH = int(os.getenv('MAX_CONTENT_LENGTH', 16 * 1024 * 1024))  # 16 MB max upload


class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    TESTING = False


class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    TESTING = False
    SESSION_COOKIE_SECURE = os.getenv('SESSION_COOKIE_SECURE', 'False').lower() in ('true', '1')
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'


class TestingConfig(Config):
    """Testing configuration."""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SQLALCHEMY_ENGINE_OPTIONS = {}
    WTF_CSRF_ENABLED = False



config_by_name = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': ProductionConfig if os.getenv('FLASK_ENV') == 'production' else DevelopmentConfig
}


def get_config():
    """Retrieve configuration based on FLASK_ENV or default."""
    env = os.getenv('FLASK_ENV', 'development').lower()
    return config_by_name.get(env, config_by_name['default'])
