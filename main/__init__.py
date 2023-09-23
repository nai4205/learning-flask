import os
from flask import Flask, make_response
from flask_mail import Mail
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager
from urllib.parse import urlencode
api_key = os.environ.get('API')


app = Flask(__name__)
app.config['SECRET_KEY'] = '622bf6829e152f0f86a46ad7f682852a'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'
from main import routes