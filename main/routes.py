from flask import render_template, url_for, flash, redirect
from main.forms import RegistrationForm, LoginForm
from main.models import User, Post
from main import app


@app.route("/")
@app.route("/home")
def home():
    return render_template('home.html', posts=posts)

@app.route("/about")
def about():
    return render_template('about.html', title='About')

@app.route("/register", methods=['GET', 'POST'])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        flash(f'Account created for {form.username.data}', 'success')
        return redirect(url_for('home'))
        
    return render_template('register.html', title='Register', form=form)

@app.route("/login", methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        if form.email.data == 'admin@blog.com' and form.password.data == 'password':
            flash('You have been logged in!', 'success')
            return redirect(url_for('home'))
        else:
            flash('Incorrect login details', 'danger')
    return render_template('login.html', title='Login', form=form)

posts = [
    {
        'author' : 'Nai korn',
        'title' : 'Blog post 1',
        'content' : 'First post',
        'date_posted' : 'July 2, 2017'
    },
    {
        'author' : 'Aneurin korn',
        'title' : 'Blog post 2',
        'content' : 'Second post',
        'date_posted' : 'July 4, 2017'
    }    
]
