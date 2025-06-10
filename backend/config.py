# backend/config.py
import os
from datetime import timedelta

class Config:
    """Configuration de base pour l'application"""
    
    # Clés de sécurité
    SECRET_KEY = os.environ.get('SECRET_KEY')
    if not SECRET_KEY:
        raise ValueError("SECRET_KEY doit être définie dans les variables d'environnement")
    
    # Configuration de la base de données
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URI', 'sqlite:///roadonifri.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
    }
    
    # Configuration JWT
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY')
    if not JWT_SECRET_KEY:
        raise ValueError("JWT_SECRET_KEY doit être définie dans les variables d'environnement")
    
    JWT_TOKEN_LOCATION = ["cookies"]
    JWT_ACCESS_COOKIE_NAME = "access_token_cookie"
    JWT_REFRESH_COOKIE_NAME = "refresh_token_cookie"
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
    
    # Sécurité des cookies
    JWT_COOKIE_SECURE = os.environ.get('JWT_COOKIE_SECURE', 'False').lower() == 'true'
    JWT_COOKIE_CSRF_PROTECT = os.environ.get('JWT_COOKIE_CSRF_PROTECT', 'True').lower() == 'true'
    JWT_COOKIE_SAMESITE = 'Strict'
    
    # Configuration générale
    DEBUG = False
    TESTING = False
    
    # Configuration CORS
    CORS_ORIGINS = os.environ.get('CORS_ORIGINS', 'http://localhost:3000').split(',')
    
    # Limites de taux
    RATELIMIT_STORAGE_URL = os.environ.get('REDIS_URL', 'memory://')
    
    # Logging
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    
    # Upload de fichiers
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', 'uploads')


class DevelopmentConfig(Config):
    """Configuration pour l'environnement de développement"""
    
    DEBUG = True
    JWT_COOKIE_SECURE = False
    JWT_COOKIE_CSRF_PROTECT = False
    
    # Clés par défaut pour le développement uniquement
    if not os.environ.get('SECRET_KEY'):
        SECRET_KEY = 'dev_secret_key_change_in_production'
    
    if not os.environ.get('JWT_SECRET_KEY'):
        JWT_SECRET_KEY = 'dev_jwt_secret_key_change_in_production'


class ProductionConfig(Config):
    """Configuration pour l'environnement de production"""
    
    # Sécurité renforcée en production
    JWT_COOKIE_SECURE = True
    JWT_COOKIE_CSRF_PROTECT = True
    
    # Base de données PostgreSQL recommandée en production
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URI')
    if not SQLALCHEMY_DATABASE_URI or SQLALCHEMY_DATABASE_URI.startswith('sqlite'):
        raise ValueError("Une base de données PostgreSQL est requise en production")
    
    # Configuration SSL pour la base de données
    SQLALCHEMY_ENGINE_OPTIONS = {
        **Config.SQLALCHEMY_ENGINE_OPTIONS,
        'connect_args': {'sslmode': 'require'}
    }


class TestingConfig(Config):
    """Configuration pour les tests"""
    
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    JWT_COOKIE_CSRF_PROTECT = False
    
    # Clés de test
    SECRET_KEY = 'test_secret_key'
    JWT_SECRET_KEY = 'test_jwt_secret_key'


# Dictionnaire des configurations
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}


def get_config():
    """Retourne la configuration basée sur la variable d'environnement FLASK_ENV"""
    env = os.environ.get('FLASK_ENV', 'development')
    return config.get(env, config['default'])
