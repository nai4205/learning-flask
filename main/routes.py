import secrets
import os
from PIL import Image
from flask import render_template, url_for, flash, redirect, request, abort, session
from main.forms import RegistrationForm, LoginForm, UpdateAccountForm, PostForm
from main.models import User, Post, SavePost
from main import app, bcrypt, db
from flask_login import login_user, current_user, logout_user, login_required
from sqlalchemy import func

@app.route("/")
@app.route("/home")
def home():
    page = request.args.get('page', 1, type=int)
    saved_post_id = [post.post_id for post in SavePost.query.filter_by(user_id=current_user.id).all()]
    posts = Post.query.order_by(Post.date_posted.desc()).paginate(per_page=5, page=page)
    return render_template('home.html', posts=posts, drop_title="All recipes", saved_post_id=saved_post_id)

@app.route("/personal_home")
@login_required
def personal_home():
    page = request.args.get('page', 1, type=int)
    saved_post_id = [post.post_id for post in SavePost.query.filter_by(user_id=current_user.id).all()]
    posts = Post.query.filter_by(author=current_user).order_by(Post.date_posted.desc()).paginate(per_page=5 , page=page)
    if posts:
        return render_template('home.html', posts=posts, drop_title="Your recipes", saved_post_id=saved_post_id)
    else:
        flash("You haven't posted anything!", "danger")
        return redirect(url_for('home'))
    
@app.route("/saved_posts")
@login_required
def saved_posts():
    page = request.args.get('page', 1, type=int)
    posts = SavePost.query.filter_by(user_id=current_user.id).order_by(SavePost.id.desc()).paginate(per_page=5, page=page)
    if posts:
        post = [Post.query.get_or_404(post.post_id) for post in posts.items]
        return render_template('saved_posts.html', posts=post, drop_title="Saved recipes")
    else:
        flash("You haven't saved any posts!", "danger")
        return redirect(url_for('home'))
    
@app.route("/user/<string:username>")
def user_posts(username):
    page = request.args.get('page', 1, type=int)
    saved_post_id = [post.post_id for post in SavePost.query.filter_by(user_id=current_user.id).all()]
    user = User.query.filter_by(username=username).first_or_404()
    posts = Post.query.filter_by(author=user).order_by(Post.date_posted.desc()).paginate(per_page=5, page=page)
    return render_template('user_posts.html', posts=posts, user=user, searching=True, saved_post_id=saved_post_id)

@app.route("/about")
def about():
    return render_template('about.html', title='About')


@app.route("/register", methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = RegistrationForm()
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        user = User(username=form.username.data, email=form.email.data, password=hashed_password)
        db.session.add(user)
        db.session.commit()
        flash('Account successfully created', 'success')
        return redirect(url_for('login'))
        
    return render_template('register.html', title='Register', form=form)

@app.route("/login", methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and bcrypt.check_password_hash(user.password, form.password.data):
            login_user(user, remember=form.remember.data)
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            else:
                return redirect(url_for('home'))
        else:
            flash('Incorrect login details', 'danger')
    return render_template('login.html', title='Login', form=form)

@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for('home'))

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

@app.route("/account", methods=['GET',  'POST'])
@login_required
def account():
    form = UpdateAccountForm()
    if form.validate_on_submit():
        if form.picture.data:
            picture_filename = save_picture(form_picture=form.picture.data)
            current_user.image_file = picture_filename
        current_user.username = form.username.data
        current_user.email = form.email.data
        db.session.commit()
        flash('Account Updated', 'success')
        return redirect(url_for('account'))
    elif request.method == 'GET':
        form.username.data = current_user.username
        form.email.data = current_user.email
    image_file = url_for('static', filename='profile_pics/' + current_user.image_file)
    return render_template('account.html', title='Account', image_file=image_file, form=form)


@app.route("/post/new", methods=['GET', 'POST'])
@login_required
def new_post():
    form = PostForm()
    if form.validate_on_submit():
        post = Post(
        title=form.title.data,
        content=form.content.data,
        author=current_user
        )
        submit_type = request.form['submit_type']
        if submit_type == 'private':
            post.private = True
        elif submit_type == 'public':
            post.private = False
        
        
        # Split the ingredients by line breaks and format them with bullet points
        ingredients_list = form.ingredients.data.split('\n')
        ingredients = '\n'.join(f'{ingredient.strip()}' for ingredient in ingredients_list if ingredient.strip())
        post.ingredients = ingredients
        db.session.add(post)
        db.session.commit()
        flash('Post has been created', 'success')
        return redirect(url_for('home'))
    return render_template('create_post.html', title='New', form=form, legend='New Recipe')


@app.route("/post/<int:post_id>")
def post(post_id): 
    post = Post.query.get_or_404(post_id)
    return render_template('post.html', title=post.title, post=post)


@app.route("/post/<int:post_id>/update", methods=['GET', 'POST'])
@login_required
def update_post(post_id):
    post = Post.query.get_or_404(post_id)
    if post.author != current_user:
        abort(403)
    form = PostForm()
    if form.validate_on_submit():
        post.title = form.title.data
        post.content = form.content.data
        ingredients_list = form.ingredients.data.split('\n')
        ingredients = '\n'.join(f'{ingredient.strip()}' for ingredient in ingredients_list if ingredient.strip())
        post.ingredients = ingredients
        submit_type = request.form['submit_type']
        if submit_type == 'private':
            post.private = True
        elif submit_type == 'public':
            post.private = False
        db.session.commit()

        flash('Post Updated', 'success')
        return redirect(url_for('post', post_id=post.id))
    elif request.method == 'GET':
        ingredients_list = post.ingredients.split('\n')
        form.ingredients.data = post.ingredients
        form.title.data = post.title
        form.content.data = post.content
        session['ingredients_len'] = len(post.ingredients.split('\n'))
    return render_template('create_post.html', title='Update', form=form, legend='Update Recipe', post=post)

@app.route("/post/<int:post_id>/delete", methods=['POST', 'GET'])
@login_required
def delete_post(post_id):
    post = Post.query.get_or_404(post_id)
    if post.author != current_user:
        abort(403)
    db.session.delete(post)
    db.session.commit()
    flash("Post Deleted", 'success')
    return redirect(url_for('home'))

@app.route("/handle_search")
def handle_search():
    query = request.args['search']
    post = Post.query.filter(func.lower(Post.title) == func.lower(query)).first()
    if post and query and post.private != True:  
        flash(f'Found result for {post.title}', 'success')
        return redirect(url_for('post', post_id=post.id))
    elif post.private == True:
        if current_user == post.author:
            flash(f'Found result for {post.title}', 'success')
            return redirect(url_for('post', post_id=post.id))
        else:
            flash('This recipe is private', 'danger')
    elif query:
        flash(f'No result for {query}', 'danger')
    else:
        flash('Please enter search query', 'danger')
    return redirect(url_for('home'))




@app.route("/save_post/<int:post_id>")
@login_required
def save_post(post_id):
    post = Post.query.get_or_404(post_id)
    save_post = SavePost(user_id=current_user.id, post_id=post_id)
    if SavePost.query.filter_by(user_id=current_user.id, post_id=post_id).first():
        db.session.delete(SavePost.query.filter_by(user_id=current_user.id, post_id=post_id).first())
        db.session.commit() 
        return redirect(request.referrer)
    else:
        db.session.add(save_post)
        db.session.commit()
        return redirect(request.referrer)


