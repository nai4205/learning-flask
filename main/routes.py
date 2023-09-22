import secrets
import os
from PIL import Image
from flask import render_template, url_for, flash, redirect, request, abort, session, make_response
from main.forms import RegistrationForm, LoginForm, UpdateAccountForm, PostForm, SearchForm, RequestResetForm, ResetPasswordForm
from main.models import User, Post, SavePost
from main import app, bcrypt, db, api_key
import requests
from bs4 import BeautifulSoup
from flask_login import login_user, current_user, logout_user, login_required
from sqlalchemy import func
from flask_mail import Message


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
    
    db.session.delete(saved_post)
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
    
@app.route("/search_ingredients/save_post/<title>/<content>/<ingredients>", methods=['GET', 'POST'])
@login_required
def save_post_from_search(title, content, ingredients):
    ingredients_string = '\n'.join(ingredient.strip() for ingredient in str(ingredients).replace('[','').replace(']','').replace('\'','').split(','))


    new_post = Post(title=title, content=content, ingredients=ingredients_string, author=current_user, display=False)
    db.session.add(new_post)    
    db.session.commit()
    
    save_post = SavePost(user_id=current_user.id, post_id=new_post.id)
    db.session.add(save_post)
    db.session.commit()

    
    return redirect(url_for('search_ingredients'))

@app.route("/search_ingredients", methods=['GET', 'POST'])
def search_ingredients():
    form = SearchForm()
    class RecipeScraper:
        def __init__(self, url):
            self.url = url
            self.page = requests.get(self.url)
            self.soup = BeautifulSoup(self.page.content, "html.parser")
            self.results = self.soup.find(class_="layout-md-rail__primary")  # List of all recipes
            self.recipe_elements = self.results.find_all("div", class_="card__section card__content")  # Content of individual recipe (just preview)

        def get_recipe_links(self):
            links_list = []
            for recipe_element in self.recipe_elements:
                links = recipe_element.find_all("a")
                for link in links:
                    link_url = link["href"]
                    links_list.append(link_url)
            links_list.pop(0)
            return links_list

        def get_matching_ingredient_count(self, ingredients, search_terms):
            count = 0
            for term in search_terms:
                for ingredient in ingredients:
                    if term.lower() in ingredient.lower():
                        count += 1
            return count

        def get_ingredients_with_search(self, search_terms):
            recipe_info = []  # List to store recipe information tuples
            for link in self.get_recipe_links():
                #GET INGREDIENTS
                recipe_page = requests.get("https://www.bbcgoodfood.com" + link)
                new_soup = BeautifulSoup(recipe_page.content, "html.parser")
                recipe_name = new_soup.find("h1").text.strip()
                ingredients_and_recipe_section = new_soup.find("div", class_="row recipe__instructions")
                ingredients_section = ingredients_and_recipe_section.find(class_="recipe__ingredients col-12 mt-md col-lg-6")
                ingredients_list = ingredients_section.find_all("li")
                ingredients = [ingredient.get_text() for ingredient in ingredients_list]

                #GET METHOD
                method_section = ingredients_and_recipe_section.find(class_="recipe__method-steps mb-lg col-12 col-lg-6")
                method_list = method_section.find_all("li")
                method = [method.get_text() for method in method_list]

                matching_count = self.get_matching_ingredient_count(ingredients, search_terms)
                matching_terms = [term for term in search_terms if any(term.lower() in ingredient.lower() for ingredient in ingredients)]

                if matching_count > 0:
                    recipe_info.append((recipe_name, ingredients, method))

            
            sorted_results = sorted(recipe_info, key=lambda x: x[1], reverse=True) #Sorts the list by element 1 (matching_count) then reverses the order to get
                                                                                #a descending list 
            return sorted_results

    if form.validate_on_submit():
        # Example usage
        try:
            scraper = RecipeScraper("https://www.bbcgoodfood.com/recipes/collection/"+"lunch".lower()+"-recipes")
        except:
            flash("Error: No recipes with that search term", "danger")
            return redirect(url_for('search_ingredients'))
        search_terms = form.ingredients.data.split('\n')
        matching_ingredient_results = scraper.get_ingredients_with_search(search_terms)

        recipe_dict = {
                'title': [],
                'content': [],
                'ingredients': [],
                'already_saved': []
            }
        for recipe_name, ingredients, method in matching_ingredient_results:
            recipe_dict['title'].append(recipe_name)
            recipe_dict['ingredients'].append(ingredients)
            recipe_dict['content'].append(method)

            post = Post.query.filter(Post.title == recipe_name).first()
            if post:
                if post.display == False and current_user == post.author:
                    recipe_dict['already_saved'].append(True)
            else:
                recipe_dict['already_saved'].append(False)
                
        
        return render_template('search_ingredients.html', form=form, posts=recipe_dict)
    return render_template('search_ingredients.html', form=form, searching=False)

def send_reset_email(user):
    token = user.get_reset_token()
    requests.post(
		"https://api.mailgun.net/v3/sandboxc269e18fa0754823849aac86d667cab3.mailgun.org/messages",
		auth=("api", api_key),
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


    