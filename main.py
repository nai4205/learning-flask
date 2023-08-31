from flask import Flask, render_template, url_for
app = Flask(__name__)

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

if __name__ == "__main__":
    app.run(debug=True)