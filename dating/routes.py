import os
from datetime import datetime
import secrets
from PIL import Image
from flask import render_template, url_for, flash, redirect, request, abort
from dating import app, db, bcrypt, mail
from dating.forms import RegistrationForm, LoginForm, UpdateAccountForm, MessageForm, RequestResetForm, ResetPasswordForm
from dating.models import User, Message as m
from dating.functions import profile_img
from flask_login import login_user, current_user, logout_user, login_required
from flask_mail import Message


@app.before_request
def before_request():
	if current_user.is_authenticated:
		current_user.last_seen = datetime.utcnow()
		db.session.commit()


@app.route('/')
@app.route('/home', methods=['GET', 'POST'])
def home():
	if current_user.is_authenticated:
		users = User.query.all()

		match_with = set()
		for user in users:
			if not current_user.is_following(user) and current_user.gender != user.gender:
				match_with.add(user)

		hour = datetime.now().hour
		year = datetime.now().year
		greeting = "Good morning" if 5<=hour<12 else "Good afternoon" if hour<18 else "Good evening"
		return render_template('swipe.html', title="Match with friends", match_with=match_with, greeting=greeting, year=year, users=users)
	else:
		return render_template('intro.html', title="Intro")


@app.route('/discover')
@login_required
def discover():
	users = User.query.all()
	liked_people = set()
	for user in users:
		if user != current_user and not current_user.is_following(user) and user.is_following(current_user) and user.gender != current_user.gender:
			liked_people.add(user)
	hour = datetime.now().hour
	year = datetime.now().year
	greeting = "Good morning" if 5<=hour<12 else "Good afternoon" if hour<18 else "Good evening"
	return render_template('discover.html', users=users, liked_people=liked_people, greeting=greeting, year=year, title='See who likes you')


@app.route('/messages')
@login_required
def messages():
	current_user.last_message_read_time = datetime.utcnow()
	db.session.commit()
	messages_received = current_user.messages_received.order_by(m.timestamp.desc())
	messages_sent = current_user.messages_sent.order_by(m.timestamp.desc())

	#recent chats
	recent_chats = list()
	for message in messages_received:
		recent_chats.append(message.author)
	for message in messages_sent:
		recent_chats.append(message.recipient)
	recent_chats = list(dict.fromkeys(recent_chats))

	users = User.query.all()
	hour = datetime.now().hour
	greeting = "Good morning" if 5<=hour<12 else "Good afternoon" if hour<18 else "Good evening"
	return render_template('messages.html', title="Messages", users=users, greeting=greeting, recent_chats=recent_chats, messages_sent=messages_sent, messages_received=messages_received)

@app.route('/m/<recipient>', methods=['GET', 'POST'])
@login_required
def message(recipient):
	current_user.last_message_read_time = datetime.utcnow()
	db.session.commit()
	recipient = recipient.lower()
	user = User.query.filter_by(username=recipient).first_or_404()
	current_user.last_message_read_time = datetime.utcnow()
	db.session.commit()
	#if user == current_user:
		#return redirect(url_for('messages'))
	form = MessageForm()
	if form.validate_on_submit():
		msg = m(author=current_user, recipient=user, body=form.message.data)
		db.session.add(msg)
		db.session.commit()
		flash('Your message has been sent.', 'success')
		return redirect(url_for('message', recipient=recipient))
	sent = current_user.messages_sent.filter_by(recipient_id=user.id)
	received = current_user.messages_received.filter_by(sender_id=user.id)
	messages = sent.union(received).order_by(m.timestamp.asc())

	#adding all names of people who texted me to recent chats
	messages_received = current_user.messages_received.order_by(m.timestamp.desc())
	messages_sent = current_user.messages_sent.order_by(m.timestamp.desc())
	recent_chats = list()
	for message in messages_received:
		recent_chats.append(message.author)
	for message in messages_sent:
		recent_chats.append(message.recipient)
	recent_chats = list(dict.fromkeys(recent_chats))

	return render_template('send_message.html', recipient=recipient, title="Chat with " + recipient.title() , user=user, form=form, messages=messages, recent_chats=recent_chats)



@app.route('/register', methods=['GET', 'POST'])
def register():
	if current_user.is_authenticated:
		return redirect(url_for('home'))
	form = RegistrationForm()
	if form.validate_on_submit():
		hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
		user = User(username=form.username.data.lower(), department=form.department.data,\
			gender=form.gender.data, age=form.age.data, password=hashed_password)
		db.session.add(user)
		db.session.commit()
		flash(f'Account Created for {form.username.data}! You can now log in', 'success')
		return redirect(url_for('login'))
	return render_template('register.html', title="Register", form=form)


@app.route('/login', methods=['GET', 'POST'])
def login():
	if current_user.is_authenticated:
		return redirect(url_for('home'))
	form = LoginForm()
	if form.validate_on_submit():
		user = User.query.filter_by(username=form.username.data.lower()).first()
		if user and bcrypt.check_password_hash(user.password, form.password.data):
			login_user(user, remember=form.remember.data)
			next_page = request.args.get('next')
			return redirect(next_page) if next_page else redirect(url_for('home'))
		else:
			flash(f'Login Unsuccesful! Please try again.', 'danger')
	return render_template('login.html', title="Login", form=form)


@app.route('/logout')
def logout():
	logout_user()
	return redirect('home')


@app.route('/account', methods=['GET', 'POST'])
@login_required
def account():
	form = UpdateAccountForm()
	if form.validate_on_submit():
		if form.picture.data:
			pic = profile_img(form.picture.data)
			current_user.dp = pic
		if form.picture2.data:
			pic2 = profile_img(form.picture2.data)
			current_user.dp2 = pic2
		if form.picture3.data:
			pic3 = profile_img(form.picture3.data)
			current_user.dp3 = pic3
		current_user.username = form.username.data.lower()
		current_user.bio = form.bio.data
		current_user.email = form.email.data
		current_user.department = form.department.data
		current_user.student_number = form.student_number.data
		current_user.country = form.country.data
		current_user.age = form.age.data
		current_user.snapchat = form.snapchat.data
		current_user.instagram = form.instagram.data
		db.session.commit()
		flash('Your Account has been updated', 'success')
		return redirect(url_for('account'))
	elif request.method == 'GET':
		form.username.data = current_user.username
		form.bio.data = current_user.bio
		form.email.data = current_user.email
		form.department.data = current_user.department
		form.student_number.data = current_user.student_number
		form.country.data = current_user.country
		form.age.data = current_user.age
		form.snapchat.data = current_user.snapchat
		form.instagram.data = current_user.instagram
	dp = url_for('static', filename='profile_pics/' + current_user.dp)
	return render_template('account.html', title='Account', dp=dp, form=form)

@app.route("/<string:username>", methods=['GET', 'POST'])
@login_required
def user_posts(username):
	username = username.lower()
	if current_user.is_authenticated:
		form = UpdateAccountForm()
		if form.validate_on_submit():
			if form.picture.data:
				pic = profile_img(form.picture.data)
				current_user.dp = pic
			if form.picture2.data:
				pic2 = profile_img(form.picture2.data)
				current_user.dp2 = pic2
			if form.picture3.data:
				pic3 = profile_img(form.picture3.data)
				current_user.dp3 = pic3
			current_user.username = form.username.data.lower()
			if form.email.data:
				current_user.email = form.email.data
			current_user.snapchat = form.snapchat.data
			current_user.instagram = form.instagram.data
			current_user.department = form.department.data
			if form.student_number.data:
				current_user.student_number = form.student_number.data
			current_user.country = form.country.data
			current_user.age = form.age.data
			current_user.bio = form.bio.data
			current_user.private = form.private.data
			db.session.commit()
			flash('Your Account has been updated', 'success')
			return redirect(url_for('user_posts', username=current_user.username))
		elif request.method == 'GET':
			form.username.data = current_user.username
			form.email.data = current_user.email
			form.snapchat.data = current_user.snapchat
			form.instagram.data = current_user.instagram
			form.department.data = current_user.department
			form.student_number.data = current_user.student_number
			form.country.data = current_user.country
			form.age.data = current_user.age
			form.bio.data = current_user.bio
			form.private.data = current_user.private
		dp = url_for('static', filename='profile_pics/' + current_user.dp)
		user = User.query.filter_by(username=username).first_or_404()
		users = User.query.all()
		mutual = 0
		for person in user.followers:
			if user.is_following(person):
				mutual += 1
		return render_template('user_posts.html', user=user, users=users, mutual=mutual, title=user.username.title(), dp=dp, form=form)
	user = User.query.filter_by(username=username).first_or_404()
	return render_template('user_posts.html', user=user, title=user.username.title())

@app.route('/follow/<username>')
@login_required
def follow(username):
	username = username.lower()
	user = User.query.filter_by(username=username).first()
	if user is None:
		flash('User {} not found.'.format(username))
		return redirect(url_for('index'))
	if user == current_user:
		flash('You cannot follow yourself!', 'danger')
		return redirect(request.referrer)
	current_user.follow(user)
	db.session.commit()
	flash('💛 You are following {}!'.format(username.title()), 'success')
	return redirect(request.referrer)


@app.route('/unfollow/<username>')
@login_required
def unfollow(username):
	username = username.lower()
	user = User.query.filter_by(username=username).first()
	if user is None:
		flash('User {} not found.'.format(username))
		return redirect(url_for('index'))
	if user == current_user:
		flash('You cannot unfollow yourself!', 'danger')
		return redirect(url_for('user_posts', username=username))
	current_user.unfollow(user)
	db.session.commit()
	flash('💔 You are not following {}.'.format(username.title()), 'info')
	return redirect(url_for('user_posts', username=username))


def send_reset_email(user):
	token = user.get_reset_token()
	msg = Message('Password Reset Request', sender="BAMBI", recipients=[user.email])
	msg.body = f"""To reset your Bambi Password, visit the following link:

	{url_for('reset_token', token=token, _external=True)}

	If you did not make this request, simply ignore this email and no changes will be made.
	"""
	mail.send(msg)


@app.route('/reset_password', methods=['GET', 'POST'])
def reset_request():
	if current_user.is_authenticated:
		return redirect(url_for('home'))
	form = RequestResetForm()
	if form.validate_on_submit():
		user = User.query.filter_by(email=form.email.data).first()
		send_reset_email(user)
		flash('An email has been set with instructions to reset your password','info')
		return redirect(url_for('login'))
	return render_template('reset_request.html', title='Reset Password', form=form)

@app.route("/reset_password/<token>", methods=['GET', 'POST'])
def reset_token(token):
	if current_user.is_authenticated:
		return redirect(url_for('home'))
	user = User.verify_reset_token(token)
	if user is None:
		flash('That is an invalid or expired token', 'danger')
		return redirect(url_for('reset_request'))
	form = ResetPasswordForm()
	if form.validate_on_submit():
		hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
		user.password = hashed_password
		db.session.commit()
		flash('Your password has been updated! You are now able to log in', 'success')
		return redirect(url_for('login'))
	return render_template('reset_token.html', title='Reset Password', form=form)


#Error Handlers
@app.errorhandler(404)
def not_found_error(error):
	return render_template('404.html'), 404

@app.errorhandler(403)
def forbidden_route_error(error):
	return render_template('403.html'), 403

@app.errorhandler(500)
def internal_error(error):
	db.session.rollback()
	return render_template('500.html'), 500
