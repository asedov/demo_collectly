# pylint: disable=C0111,C0103,R0903

import tempfile

db_file = tempfile.NamedTemporaryFile()


class Config:
    SECRET_KEY = 'REPLACE ME'


class ProdConfig(Config):
    ENV = 'prod'
    SQLALCHEMY_DATABASE_URI = 'postgresql://postgres:postgres@127.0.0.1:5432/challenge'
    SQLALCHEMY_NATIVE_UNICODE = True

    CACHE_TYPE = 'simple'


class DevConfig(Config):
    ENV = 'dev'
    DEBUG = True
    DEBUG_TB_INTERCEPT_REDIRECTS = False

    SQLALCHEMY_DATABASE_URI = 'postgresql://postgres:postgres@127.0.0.1:5432/challenge'
    SQLALCHEMY_NATIVE_UNICODE = True
    SQLALCHEMY_ECHO = False

    CACHE_TYPE = 'null'
    ASSETS_DEBUG = True


class TestConfig(Config):
    ENV = 'test'
    DEBUG = True
    DEBUG_TB_INTERCEPT_REDIRECTS = False

    SQLALCHEMY_DATABASE_URI = 'postgresql://postgres:postgres@127.0.0.1:5432/challenge'
    SQLALCHEMY_ECHO = True

    CACHE_TYPE = 'null'
