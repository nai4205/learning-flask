from flask import render_template, request, Blueprint, flash, redirect, url_for
from recipe_share.models import Post, SavePost
from flask_login import current_user, login_required

main = Blueprint('main', __name__)

@main.route("/")
@main.route("/home")
def home():
    saved_post_id = []
    page = request.args.get('page', 1, type=int)
    if current_user.is_authenticated:
        saved_post_id = [post.post_id for post in SavePost.query.filter_by(user_id=current_user.id).all()]
    posts = Post.query.order_by(Post.date_posted.desc()).filter_by(display=True).paginate(per_page=5, page=page)
    return render_template('home.html', posts=posts, drop_title="All recipes", saved_post_id=saved_post_id)

@main.route("/personal_home")
@login_required
def personal_home():
    page = request.args.get('page', 1, type=int)
    saved_post_id = [post.post_id for post in SavePost.query.filter_by(user_id=current_user.id).all()]
    posts = Post.query.filter_by(author=current_user).filter_by(display=True).order_by(Post.date_posted.desc()).paginate(per_page=5 , page=page)
    if posts:
        return render_template('personal_home.html', posts=posts, drop_title="Your recipes", saved_post_id=saved_post_id)
    else:
        flash("You haven't posted anything!", "danger")
        return redirect(url_for('main.home'))
    

    


@main.route("/about")
def about():
    return render_template('about.html', title='About')