import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

from datetime import datetime


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


# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


############################
##                        ##
##         sql cmd        ##
##                        ##
############################

    # CREATE TABLE history (
    # transaction_id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    # symbol TEXT NOT NULL,
    # quote INTEGER NOT NULL,
    # shares INTEGER NOT NULL,
    # total INTEGER NOT NULL,
    # time DATETIME NOT NULL,
    # u_id INTEGER NOT NULL);

    ### in case rename
    # ALTER TABLE hitsory
    # RENAME TO history


############################
##                        ##
##        register        ##
##                        ##
############################


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":

        if not request.form.get("username"):
            return apology("Please type in your Username.")

        elif not request.form.get("password"):
            return apology("Password is required.")

        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("Passwords don't match.")

        else:
            ## INSERT the new user into users:
            ## store a hash of the password, not the password itself
            ## Hash the user’s password with generate_password_hash

            #check_username = len(db.execute("SELECT * FROM users WHERE username = {username}", username=request.form.get("username")))
            if len(db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))) != 0:
                return apology("This username already taken. Please choose another one.")
            else:
                password_hash = generate_password_hash(request.form.get("password"))
                uid = db.execute("INSERT INTO users (username, hash) VALUES(?, ?)", request.form.get("username"), password_hash)
                session["user_id"] = uid
                flash("registered successfully.")
                return redirect("/")

    return render_template("register.html")


############################
##                        ##
##         Login          ##
##                        ##
############################


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username")

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password")

        # Query database for username
        user = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(user) != 1 or not check_password_hash(user[0]["hash"],
        request.form.get("password")):
            return apology("invalid username and/or password")

        # Remember which user has logged in
        session["user_id"] = user[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


############################
##                        ##
##         logout         ##
##                        ##
############################


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


############################
##                        ##
##         Index          ##
##                        ##
############################


@app.route("/", methods=["GET"])
@login_required
def index():
    """Show portfolio of stocks"""

     ## SUM(quantity) -->> buy and sell
    portfolio = db.execute("SELECT symbol AS Symbol, SUM(shares) AS Shares FROM history WHERE u_id = (?)", session['user_id'])

    stocks = []
    value = 0

    for stock in portfolio:
        if stock.get("Shares") == 0:
            continue
        ### lookup will always return a Quote
        quote = lookup(stock.get("Symbol"))

        price = stock_quote.get("price")

        total = quote * stock.get("Shares")

        stock["quote"] = usd(price)
        stock["total"] = usd(total)

        value += round(total,2)
        stocks.append(stock)

    cash = db.execute("SELECT cash FROM users WHERE id = (?)", session['user_id'])

    balance = cash[0]["cash"]

    assets = value + balance

    return render_template("index.html", shares=stocks, balance=usd(balance), value=usd(value), assets=usd(assets))
    # return render_template("index.html")

############################
##                        ##
##         quote          ##
##                        ##
############################


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""

    if request.method == "GET":
        return render_template("quote.html")

    if request.method == "POST":
        ## HELPER Function
        ## lookup
        ## pass in a symbol (e.g., NFLX)
        ## returns a stock quote in form of a dict containing 3 keys:
        ## name, whose value is a str
        ## price, whose value is a float
        ## symbol, whose value is a str
        quote = lookup(request.form.get("symbol"))

        if quote == None:
            return apology("Company symbol not found.")
        else:
            symbol = quote.get("symbol")
            price = quote.get("price")
            return render_template("quoted.html", symbol=symbol, price=usd(price))


############################
##                        ##
##        History         ##
##                        ##
############################


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    history = db.execute("SELECT symbol AS Symbol, quantity AS Shares, quote AS Price FROM history WHERE u_id = (?)", session['user_id'])

    return render_template("history.html", history=history)


############################
##                        ##
##          Buy           ##
##                        ##
############################


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    if request.method == "GET":
        return render_template("buy.html")

    if request.method == "POST":

        if request.form.get("shares") == None:
            return apology("Enter the number of shares you want")

        ### define quote
        if not request.form.get("symbol"):
            return apology("Enter the stock name.")
        elif lookup(request.form.get("symbol")) == None:
            return apology("Stock name not found")

        ### define shares, number_of_shares, symbol
        quote = lookup(request.form.get("symbol"))

        shares = request.form.get("shares")
        symbol = request.form.get("symbol").upper()

        ### deal with
        ### :( buy handles fractional, negative, and non-numeric shares

        if not shares.isdigit():
            return apology("You cannot purchase partial shares")
        ### use "elif" to deal with fractional number
        elif int(shares) <= 0:
            return apology("Buy at least one share")

        shares = int(shares)
        # above line if put before isdigit()
        # will fail handling fractional, negative, and non-numeric shares

        ### check price

        price = quote.get("price")


        ### check balance

        cash = db.execute("SELECT cash FROM users WHERE id = ?", session['user_id'])
        balance = usd(cash[0]["cash"])


        ### add date.strftime(_format_)

        time = datetime.now().strftime('%Y-%M-%D %H:%M:%S')

        ### not enough cash: apology
        ### else: 1. buy
        ### 2. calculate new balance
        total = usd(price) * shares


        if total > balance:
            return apology("Not enough cash.")
        else:

            # CREATE TABLE history (
            # transaction_id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
            # symbol TEXT NOT NULL,
            # quote INTEGER NOT NULL,
            # shares INTEGER NOT NULL,
            # total INTEGER NOT NULL,
            # time DATETIME NOT NULL,
            # u_id INTEGER NOT NULL);

            balance -= total
            db.execute("INSERT INTO history (symbol, shares, quote, total, time, u_id) VALUES(?, ?, ?, ?, ?, ?)", symbol, shares, price, total, time, session["user_id"])
            db.execute("UPDATE users SET cash = (?) WHERE id = (?)", round(balance, 2), session["user_id"])

        ### redirect to home
        return redirect("/")


############################
##                        ##
##          Sell          ##
##                        ##
############################


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    """a select menu whose name is symbol"""


    # time = datetime.now().strftime('%Y-%M-%D %H:%M:%S')
    return apology("TODO")


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
