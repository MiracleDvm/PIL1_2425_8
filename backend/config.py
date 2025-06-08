# backend/config.py
import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'mon_secret_development')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URI', 'sqlite:///roadonifri.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'jwt_secret_key_development')
    JWT_TOKEN_LOCATION = ["cookies"]
    JWT_ACCESS_COOKIE_NAME = "access_token_cookie"
    JWT_COOKIE_SECURE = False  # True en production avec HTTPS
    JWT_COOKIE_CSRF_PROTECT = False  # Pour simplifier les tests locaux
