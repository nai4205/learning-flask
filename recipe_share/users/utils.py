import os
import secrets
from PIL import Image
from flask import url_for
from flask_mail import Message
from recipe_share import app, mail
import requests
from flask_login import current_user

def save_picture(form_picture):
    if current_user.image_file != 'default.jpg':
        os.remove(os.path.join(app.root_path, 'static/profile_pics', current_user.image_file))
    random_hex = secrets.token_hex(8)
    _, f_ext = os.path.splitext(form_picture.filename)
    picture_filename = random_hex + f_ext
    picture_path = os.path.join(app.root_path, 'static/profile_pics', picture_filename)
    output_size = (125, 125)
    i = Image.open(form_picture)
    i.thumbnail(output_size)
    i.save(picture_path)
    return picture_filename

def send_reset_email(user):
    token = user.get_reset_token()
    requests.post(
		"https://api.mailgun.net/v3/sandboxf6184cbbc9604db58f5ee2ac78568fea/messages",
		auth=("api", "ca076204e3a43096776bc428bb92d012-4b98b89f-0237474a"),
		data={"from": "noreply@gmail.com",
			"to": user.email,
			"subject": "Password Reset Request",
			"text": f'''To reset your password, visit the following link: {url_for('users.reset_token', token=token, _external=True)}

If you did not make this request, please ignore this email.
    '''})