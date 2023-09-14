from flask import Flask, render_template, url_for
from forms import RegistrationForm, LoginForm
app = Flask(__name__)
app.config['SECRET_KEY'] = '622bf6829e152f0f86a46ad7f682852a'

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

@app.route("/")
@app.route("/home")
def home():
    return render_template('home.html', posts=posts)

@app.route("/about")
def about():
    return render_template('about.html', title='About')

@app.route("/register")
def register():
    form = RegistrationForm()
    return render_template('register.html', title='Register', form=form)

@app.route("/login")
def login():
    form = LoginForm()
    return render_template('login.html', title='Login', form=form)

if __name__ == "__main__":
    app.run(debug=True)