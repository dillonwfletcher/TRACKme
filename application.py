import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import login_required

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///tracker.db")

@app.route("/")
@login_required
def index():

    recents = db.execute("SELECT location, nickname, visited FROM places WHERE user_id=:user_id ORDER BY visited DESC LIMIT 5", user_id=session['user_id'])

    return render_template("index.html", recents=recents)

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            fail = 1;
            return render_template("login.html", fail=fail, msg="Must provide a username")

        # Ensure password was submitted
        elif not request.form.get("password"):
            fail = 1;
            return render_template("login.html", fail=fail, msg="Must provide a password")

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            fail = 1;
            return render_template("login.html", fail=fail, msg="Invalid username and/or password")

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            fail = 1
            return render_template("register.html", fail=fail, msg="Please enter a username")

        # Ensure password was submitted
        elif not request.form.get("password") or not request.form.get("confirmation"):
            fail = 1
            return render_template("register.html", fail=fail, msg="Please enter a password")

        elif request.form.get("password") != request.form.get("confirmation"):
            fail = 1
            return render_template("register.html", fail=fail, msg="Passwords did not match")

        # Query database for username to ensure that username does not already exist
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        if len(rows) != 0:
            fail = 1
            return render_template("register.html", fail=fail, msg="Username already exists")

        # new user registration successful: hash password and insert new user into database
        db.execute("INSERT INTO users (username, hash) VALUES (:username, :hashed_password)",
                    username=request.form.get("username"), hashed_password=generate_password_hash(request.form.get("password")))

        # Redirect user to home page
        return render_template("login.html", msg="Registration successful! Please log in")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")

@app.route("/track", methods=["GET", "POST"])
def track():

    if request.method == "POST":

        location = request.form.get("location")
        nickname = request.form.get("nickname")
        timestamp = request.form.get("timestamp")

        # select nickname associated with location if exists
        rows = db.execute("SELECT nickname FROM places WHERE user_id = :user_id AND location = :location AND nickname IS NOT NULL",
                           user_id=session['user_id'], location=location)

        # if no nickname
        if not nickname:
            # if a nickname already exists for location
            if len(rows) != 0:
                # set nickname to nickname already assigned to location
                nickname = rows[0]['nickname']
                msg = "We noticed that the location you just tracked is saved as " + nickname + ", so we updated your track to show this!"
            else:
                msg = "Location successfully tracked!"
                nickname = None

        # if nickname given,
        else:
            # if a nickname already exists for location
            if len(rows) != 0:
                # set nickname to nickname already assigned to location
                old_nickname = nickname
                nickname = rows[0]['nickname']
                msg = "You just tried to track a location as " + old_nickname + ", but this location was already saved as " + nickname + ". Don't worry! We updated your track to show this."
            else:
                msg = nickname + " successfully tracked!"

            # check to see if user is trying to give two different locations same nickname
            # select all locations that have a nickname similar to inputted nickname
            rows = db.execute("SELECT location FROM places WHERE user_id = :user_id AND location <> :location AND nickname LIKE :nickname",
                                   user_id=session['user_id'], location=location, nickname=nickname + "%")
            # if nickname already assigned to another location current track a new nickname
            if len(rows) != 0:
                old_nickname = nickname
                nickname = nickname + str(len(rows))
                msg = old_nickname + " already exists as one of your places, so we took the liberty of renaming your last track to " + nickname + ". Feel free to change this nickname at any time!"

        # add location to tracked locations
        db.execute("INSERT INTO places ('user_id', 'location', 'nickname', 'visited') VALUES (:user_id, :location, :nickname, :timestamp)",
                    user_id=session['user_id'], location=location, nickname=nickname, timestamp=timestamp)

        recents = db.execute("SELECT location, nickname, visited FROM places WHERE user_id=:user_id ORDER BY visited DESC LIMIT 5", user_id=session['user_id'])

        return render_template("index.html", msg=msg, recents=recents)

    else:
        return render_template("track.html")

@app.route("/places")
def places():

    rows = db.execute("SELECT DISTINCT nickname, location FROM places WHERE user_id = :user_id AND nickname IS NOT NULL ORDER BY visited DESC", user_id=session['user_id'])
    last = {}
    for r in rows:
        last_track = db.execute("SELECT visited FROM places ORDER BY visited DESC LIMIT 1")
        last[r['nickname']] = last_track[0]['visited']


    return render_template("places.html", places=rows, last=last)

@app.route("/history")
def history():

    rows = db.execute("SELECT location, nickname, visited FROM places WHERE user_id = :user_id ORDER BY visited DESC", user_id=session['user_id'])

    return render_template("history.html", history=rows)


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return render_template("error.html")


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
