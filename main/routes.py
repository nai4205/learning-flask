import secrets
import os
from PIL import Image
from flask import render_template, url_for, flash, redirect, request, abort, session, jsonify, make_response
from main.forms import RegistrationForm, LoginForm, UpdateAccountForm, PostForm, SearchForm, RequestResetForm, ResetPasswordForm
from main.models import User, Post, SavePost
from main import app, bcrypt, db, api_key
import requests
from bs4 import BeautifulSoup
from flask_login import login_user, current_user, logout_user, login_required
from sqlalchemy import func
from flask_mail import Message
import concurrent.futures
from flask_paginate import Pagination, get_page_args
from flask_caching import Cache
import asyncio
import aiohttp
from concurrent.futures import ThreadPoolExecutor



@app.route("/")
@app.route("/home")
def home():
    saved_post_id = []
    page = request.args.get('page', 1, type=int)
    if current_user.is_authenticated:
        saved_post_id = [post.post_id for post in SavePost.query.filter_by(user_id=current_user.id).all()]
    posts = Post.query.order_by(Post.date_posted.desc()).filter_by(display=True).paginate(per_page=5, page=page)
    return render_template('home.html', posts=posts, drop_title="All recipes", saved_post_id=saved_post_id)

@app.route("/personal_home")
@login_required
def personal_home():
    page = request.args.get('page', 1, type=int)
    saved_post_id = [post.post_id for post in SavePost.query.filter_by(user_id=current_user.id).all()]
    posts = Post.query.filter_by(author=current_user).filter_by(display=True).order_by(Post.date_posted.desc()).paginate(per_page=5 , page=page)
    if posts:
        return render_template('personal_home.html', posts=posts, drop_title="Your recipes", saved_post_id=saved_post_id)
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
    saved_post = SavePost.query.filter_by(user_id=current_user.id, post_id=post_id).first()
    if post.author != current_user:
        abort(403)
    
    if post:
        if saved_post:
            db.session.delete(saved_post)
        db.session.delete(post)
    db.session.commit()
    flash("Post Deleted", 'success')
    return redirect(url_for('home'))

@app.route("/handle_search")
def handle_search():
    query = request.args['search']
    all_post_titles_public = [post.title for post in Post.query.filter_by(private=False).all()]
    post = Post.query.filter(func.lower(Post.title) == func.lower(query)).first()
    if post and query and post.private != True:  
        flash(f'Found result for {post.title}', 'success')
        return redirect(url_for('post', post_id=post.id))
    elif post and post.private == True:
        if current_user == post.author:
            flash(f'Found result for {post.title}', 'success')
            return redirect(url_for('post', post_id=post.id))
        else:
            flash(f'No result for {query}', 'danger')
            return redirect(url_for('home'))
    elif query:
        flash(f'No result for {query}', 'danger')
    else:
        flash('Please enter search query', 'danger')
    return render_template('layout.html', post_titles = all_post_titles_public)

@app.route('/search_predictions')
def search_predictions():
    all_post_titles = [post.title for post in Post.query.all()]
    query = request.args.get('query', '').lower()

    if current_user.is_authenticated:
        recipe_titles= [post.title for post in Post.query.filter_by(private=False).all()] + [post.title for post in Post.query.filter_by(author=current_user).all()]
    else:
        recipe_titles = [post.title for post in Post.query.filter_by(private=False).all()]

    unique_predictions = set()

    for title in recipe_titles:
        if query in title.lower():
            unique_predictions.add(title)

    max_predictions = 5
    predictions = list(unique_predictions)[:max_predictions]

    return jsonify(predictions)



@app.route("/save_post/<int:post_id>")
@login_required
def save_post(post_id):
    post = Post.query.get_or_404(post_id)
    save_post = SavePost(user_id=current_user.id, post_id=post_id)
    if SavePost.query.filter_by(user_id=current_user.id, post_id=post_id).first():
        db.session.delete(SavePost.query.filter_by(user_id=current_user.id, post_id=post_id).first())
        if post.display == False:
            db.session.delete(post)
        db.session.commit() 
        return redirect(request.referrer)
    elif post.private == True and current_user != post.author:
        flash('This recipe is private', 'danger')
        return redirect(request.referrer)
    else:
        db.session.add(save_post)
        db.session.commit()
        return redirect(request.referrer)
    
@app.route("/search_ingredients/<title>", methods=['GET', 'POST'])
@login_required
def save_post_from_search(title):
    recipe = recipe_dict['title'].index(title)    
    content=recipe_dict['content'][recipe]
    content = ''.join(content).replace('[','').replace(']','').replace('\'','').replace('%25', '%')
    ingredients=recipe_dict['ingredients'][recipe]
    ingredients_string = '\n'.join(ingredient.strip() for ingredient in str(ingredients).replace('[','').replace(']','').replace('\'','').split(','))
    form=SearchForm()

    new_post = Post(title=title, content=content, ingredients=ingredients_string, author=current_user, display=False)
    db.session.add(new_post)    
    db.session.commit()
    save_post = SavePost(user_id=current_user.id, post_id=new_post.id)
    db.session.add(save_post)
    db.session.commit()

    recipe_dict['already_saved'][recipe_dict['title'].index(title)] = True
    return render_template('search_ingredients.html', posts=recipe_dict, form=form, searching=True)



@app.route("/search_ingredients/delete/<title>", methods=['GET', 'POST'])
@login_required
def delete_post_from_search(title):
    form=SearchForm()
    post = Post.query.filter_by(title=title).first()
    if post:
        save_post = SavePost.query.filter_by(user_id=current_user.id, post_id=post.id).first()
    if post and post.display == False and current_user == post.author and save_post:
        db.session.delete(save_post)
        db.session.delete(post)
        db.session.commit()
        
    if recipe_dict:
        recipe_dict['already_saved'][recipe_dict['title'].index(title)] = False
    return render_template('search_ingredients.html', posts=recipe_dict, form=form, searching=True)


async def scrape_recipe(session, link, search_terms):
    async with session.get(link) as response:
        html = await response.text()
        soup = BeautifulSoup(html, "html.parser")
        results = soup.find(class_="layout-md-rail__primary")
        recipe_elements = results.find_all("div", class_="card__section card__content")
        links_list = [link["href"] for recipe_element in recipe_elements for link in recipe_element.find_all("a")]
        links_list.pop(0)

        # Use asyncio.gather to fetch recipe pages concurrently
        tasks = [fetch_recipe_data(session, "https://www.bbcgoodfood.com" + link, search_terms) for link in links_list]
        recipe_data_list = await asyncio.gather(*tasks)

        return recipe_data_list

async def fetch_recipe_data(session, recipe_url, search_terms):
    async with session.get(recipe_url) as response:
        html = await response.text()
        soup = BeautifulSoup(html, "html.parser")
        recipe_name = soup.find("h1").text.strip()
        ingredients_and_recipe_section = soup.find("div", class_="row recipe__instructions")
        ingredients_section = ingredients_and_recipe_section.find(class_="recipe__ingredients col-12 mt-md col-lg-6")
        ingredients_list = ingredients_section.find_all("li")
        ingredients = [ingredient.get_text() for ingredient in ingredients_list]

        method_section = ingredients_and_recipe_section.find(class_="recipe__method-steps mb-lg col-12 col-lg-6")
        method_list = method_section.find_all("li")
        method = [method.get_text() for method in method_list]

        matching_terms = []
        non_unique_count = 0
        unique_count = 0
        search_terms = [s.replace('\r', '') for s in search_terms]
        for ingredient in ingredients:
            for term in search_terms:
                if term.lower() in ingredient.lower():
                    matching_terms.append(term.lower())
                    if term.lower() in matching_terms[:-1]:
                        non_unique_count += 1
                    else:
                        unique_count += 1
        print(unique_count, non_unique_count)


        
        return recipe_name, ingredients, method, unique_count + non_unique_count




async def get_ingredients_with_search(search_terms):
    recipe_info = []
    async with aiohttp.ClientSession() as session:
        category_list = ["lunch", "dessert", "beef", "savoury-pie", "storecupboard-comfort-food",
                         "sausage", "chicken", "autumn-vegetarian", "gravy"]
        
        tasks = []
        for recipe_type in category_list:
            tasks.append(scrape_recipe(session, "https://www.bbcgoodfood.com/recipes/collection/"+recipe_type.lower()+"-recipes", search_terms))
        
        results = await asyncio.gather(*tasks)
        for matching_ingredient_results in results:
            recipe_info.extend(matching_ingredient_results)
    
    return recipe_info

@app.route("/search_ingredients", methods=['GET', 'POST'])
def search_ingredients():
    global recipe_dict
    recipe_dict = {}
    form = SearchForm()

    if form.validate_on_submit():
        search_terms = form.ingredients.data.split('\n')
        recipe_info = asyncio.run(get_ingredients_with_search(search_terms))

        recipe_dict = {
            'title': [],
            'content': [],
            'ingredients': [],
            'already_saved': []
        }
        

        if not recipe_info:
            flash("No results found", "danger")
            return render_template('search_ingredients.html', form=form, posts=recipe_dict, searching=False)

        print(recipe_info)
        # Create a list of tuples with all information
        recipe_tuples = [(name, ing, meth, cnt) for name, ing, meth, cnt in recipe_info if cnt > 0]

        # Sort the list based on the desired criteria
        sorted_results = sorted(
            recipe_tuples,
            key=lambda x: (x[3], len(set(search_terms) & set(' '.join(x[2]).lower().split())), str(x[0])),
            reverse=True
        )

        # Initialize recipe_dict
        recipe_dict = {
            'title': [],
            'content': [],
            'ingredients': [],
            'already_saved': []
        }

        for recipe_name, ingredients, method, count in sorted_results:
            recipe_dict['title'].append(str(recipe_name))
            recipe_dict['ingredients'].append(ingredients)
            recipe_dict['content'].append(str(method))

            post = Post.query.filter(Post.title == recipe_name).first()
            if post and not post.display and current_user == post.author:
                recipe_dict['already_saved'].append(True)
            else:
                recipe_dict['already_saved'].append(False)

        return render_template('search_ingredients.html', form=form, posts=recipe_dict)


    return render_template('search_ingredients.html', form=form, posts=recipe_dict, searching=False)



def send_reset_email(user):
    token = user.get_reset_token()
    requests.post(
		"https://api.mailgun.net/v3/sandboxf6184cbbc9604db58f5ee2ac78568fea/messages",
		auth=("api", "ca076204e3a43096776bc428bb92d012-4b98b89f-0237474a"),
		data={"from": "noreply@gmail.com",
			"to": user.email,
			"subject": "Password Reset Request",
			"text": f'''To reset your password, visit the following link: {url_for('reset_token', token=token, _external=True)}

If you did not make this request, please ignore this email.
    '''})
    

@app.route("/reset_password", methods=['GET', 'POST'])
def reset_request():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = RequestResetForm()
    if form.validate_on_submit(): 
        user = User.query.filter_by(email=form.email.data).first()
        send_reset_email(user)
        flash('Email sent', 'info')
    return render_template('reset_request.html', title='Reset Password', form=form)

@app.route("/reset_password/<token>", methods=['GET', 'POST'])
def reset_token(token):
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    
    user = User.verify_reset_token(token)
    if user is None:
        flash('That is an invalid or expired token', 'warning')
        return redirect(url_for('reset_request'))
    
    form = ResetPasswordForm()
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        user.password = hashed_password
        db.session.commit()
        flash('Password successfully changed', 'success')
        return redirect(url_for('login'))
    
    
    
    return render_template('reset_token.html', title='Reset Password', form=form)


    