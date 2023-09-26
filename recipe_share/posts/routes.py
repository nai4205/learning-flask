from flask import Blueprint
from flask import render_template, request, Blueprint, flash, redirect, url_for, abort, session, jsonify
from flask_login import current_user, login_required
from recipe_share import db
from recipe_share.models import Post, SavePost, fromSearch
from recipe_share.posts.forms import PostForm, SearchForm
from sqlalchemy import func
import asyncio
import aiohttp
from concurrent.futures import ThreadPoolExecutor
from bs4 import BeautifulSoup
import json
import jinja2


posts = Blueprint('posts', __name__)

@posts.route("/saved_posts")
@login_required 
def saved_posts():
    page = request.args.get('page', 1, type=int)
    posts = SavePost.query.filter_by(user_id=current_user.id).order_by(SavePost.id.desc()).paginate(per_page=5, page=page)
    if posts:
        post = [Post.query.get_or_404(post.post_id) for post in posts.items]
        return render_template('saved_posts.html', posts=post, drop_title="Saved recipes")
    else:
        flash("You haven't saved any posts!", "danger")
        return redirect(url_for('main_routes.home'))
    
@posts.route("/post/new", methods=['GET', 'POST'])
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
        return redirect(url_for('main.home'))
    return render_template('create_post.html', title='New', form=form, legend='New Recipe')


@posts.route("/post/<int:post_id>")
def post(post_id): 
    post = Post.query.get_or_404(post_id)
    return render_template('post.html', title=post.title, post=post)


@posts.route("/post/<int:post_id>/update", methods=['GET', 'POST'])
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
        return redirect(url_for('posts.post', post_id=post.id))
    elif request.method == 'GET':
        ingredients_list = post.ingredients.split('\n')
        form.ingredients.data = post.ingredients
        form.title.data = post.title
        form.content.data = post.content
        session['ingredients_len'] = len(post.ingredients.split('\n'))
    return render_template('create_post.html', title='Update', form=form, legend='Update Recipe', post=post)

@posts.route("/post/<int:post_id>/delete", methods=['POST', 'GET'])
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
    return redirect(url_for('main.home'))


@posts.route("/handle_search")
def handle_search():
    query = request.args['search']
    all_post_titles_public = [post.title for post in Post.query.filter_by(private=False).all()]
    post = Post.query.filter(func.lower(Post.title) == func.lower(query)).first()
    if post and query and post.private != True:  
        flash(f'Found result for {post.title}', 'success')
        return redirect(url_for('posts.post', post_id=post.id))
    elif post and post.private == True:
        if current_user == post.author:
            flash(f'Found result for {post.title}', 'success')
            return redirect(url_for('posts.post', post_id=post.id))
        else:
            flash(f'No result for {query}', 'danger')
            return redirect(url_for('main.home'))
    elif query:
        flash(f'No result for {query}', 'danger')
    else:
        flash('Please enter search query', 'danger')
    return render_template('layout.html', post_titles = all_post_titles_public)

@posts.route('/search_predictions')
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



@posts.route("/save_post/<int:post_id>")
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
    
@posts.route("/search_ingredients/<title>", methods=['GET', 'POST'])
@login_required
def save_post_from_search(title):
    form=SearchForm()
    recipe = fromSearch.query.filter_by(title=title).first()
    content=recipe.content
    ingredients=recipe.ingredients
    ingredients = json.loads(ingredients)
    ingredients = '\n'.join(ingredient.strip() for ingredient in str(ingredients).replace('[','').replace(']','').replace('\'','').split(','))
    new_post = Post(title=title, content=content, ingredients=ingredients, author=current_user, display=False)
    db.session.add(new_post)    
    db.session.commit()
    save_post = SavePost(user_id=current_user.id, post_id=new_post.id)
    db.session.add(save_post)
    db.session.commit()

    recipe.already_saved = True
    db.session.commit()

    posts = fromSearch.query.all()
    return render_template('search_ingredients.html', posts=posts, form=form, searching=True)



@posts.route("/search_ingredients/delete/<title>", methods=['GET', 'POST'])
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
        
    current_post = fromSearch.query.filter_by(title=title).first()
    current_post.already_saved = False
    db.session.commit()
    posts = fromSearch.query.all()
    return render_template('search_ingredients.html', posts=posts, form=form, searching=True)


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
                        unique_count += 2
                
        print(unique_count, non_unique_count)
        print("total", unique_count + non_unique_count)

        
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






@posts.route("/search_ingredients", methods=['GET', 'POST'])
def search_ingredients():
    form = SearchForm()
    currentPosts = fromSearch.query.all()
    if currentPosts:
        for post in currentPosts:
            db.session.delete(post)
            db.session.commit()

    if form.validate_on_submit():
        search_terms = form.ingredients.data.split('\n')
        recipe_info = asyncio.run(get_ingredients_with_search(search_terms))
        if not recipe_info:
            flash("No results found", "danger")
            return render_template('search_ingredients.html', form=form, posts=recipe_dict, searching=False)

        # Create a list of tuples with all information
        recipe_tuples = [(name, ing, meth, cnt) for name, ing, meth, cnt in recipe_info if cnt > 0]

        # Sort the list based on the desired criteria
        sorted_results = sorted(
            recipe_tuples,
            key=lambda x: (x[3], len(set(search_terms) & set(' '.join(x[2]).lower().split())), str(x[0])),
            reverse=True
        )

        for recipe_name, ingredients, method, count in sorted_results:
            method = ''.join(method).replace('[','').replace(']','').replace('\'','').replace('%25', '%')
            ingredients = json.dumps(ingredients)
            print(ingredients)
            currentRecipes = fromSearch.query.filter_by(title=str(recipe_name)).first()
            if not currentRecipes:
                tempRecipes = fromSearch(title=str(recipe_name), ingredients=ingredients, content=str(method))
                post = Post.query.filter_by(title=str(recipe_name)).first()
                is_saved = False
                if post:
                    is_saved = SavePost.query.filter_by(user_id=current_user.id, post_id=post.id).first()
                if is_saved:
                    tempRecipes.already_saved = True
                db.session.add(tempRecipes)

        db.session.commit()
        posts = fromSearch.query.all()
        return render_template('search_ingredients.html', form=form, posts=posts)


    return render_template('search_ingredients.html', form=form, searching=False)