#! ../venv/bin/python
# pylint: disable=C0111

from flask import Flask

from .api import api
from .models import db
from .models import ma


def create_app(object_name):
    """
    An flask application factory, as explained here:
    http://flask.pocoo.org/docs/patterns/appfactories/
    Arguments:
        object_name: the python path of the config object,
                     e.g. appname.settings.ProdConfig
    """

    app = Flask(__name__)

    app.config.from_object(object_name)

    # initialize SQLAlchemy
    db.init_app(app)

    # initialize Marshmallow
    ma.init_app(app)

    # register our blueprints
    app.register_blueprint(api)

    return app
