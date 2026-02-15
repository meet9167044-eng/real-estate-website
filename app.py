import mysql.connector
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

# Database configuration from environment (safer for remote deploys)
import os

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "Meet12")
DB_NAME = os.getenv("DB_NAME", "property_db")
DB_PORT = int(os.getenv("DB_PORT", 3306))


# Connect to the database. Don't let import-time failures stop the app
# from starting (Render won't start the process if import raises).
db = None
cursor = None
try:
    db = mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        port=DB_PORT
    )
    # IMPORTANT: buffered=True fixes "Unread result found"
    cursor = db.cursor(buffered=True, dictionary=True)
except Exception as e:
    app.logger.error("Database connection failed: %s", e)
    db = None
    cursor = None

# --- Create Tables (only if DB connected) ---
if cursor:
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INT AUTO_INCREMENT PRIMARY KEY,
        username VARCHAR(255) UNIQUE,
        email VARCHAR(255) UNIQUE,
        password_hash VARCHAR(255),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS wishlists (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT,
        property_id INT,
        added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE KEY unique_user_property (user_id, property_id)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS enquiries1 (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT,
        property_id INT,
        name VARCHAR(255),
        email VARCHAR(255),
        phone VARCHAR(50),
        message TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    db.commit()

# --- Login Manager Setup ---

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, id, username, email):
        self.id = id
        self.username = username
        self.email = email

@login_manager.user_loader
def load_user(user_id):
    if not cursor:
        return None
    cursor.execute("SELECT id, username, email FROM users WHERE id=%s", (user_id,))
    row = cursor.fetchone()
    return User(row['id'], row['username'], row['email']) if row else None

# --- Forms ---

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

class SignupForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Sign Up')


# At top of app.py
@app.template_filter('format_number')
def format_number(value):
    return "{:,.0f}".format(value)

# --- Routes ---

@app.route("/")
def home():
    return render_template("main.html")

@app.route("/luxury_apartments")
def luxury_apartments():
    return render_template("luxury_apartments.html")

@app.route("/spacious_3bhk")
def spacious_3bhk():
    return render_template("spacious_3bhk.html")

@app.route("/affordable_2bhk")
def affordable_2bhk():
    return render_template("affordable_2bhk.html")

@app.route("/gated_villas")
def gated_villas():
    return render_template("gated_villas.html")

@app.route("/independent_houses")
def independent_houses():
    return render_template("independent_houses.html")

@app.route("/penthouses")
def penthouses():
    return render_template("penthouses.html")

# --- Search ---

@app.route("/search")
def search():
    if not cursor:
        flash("Database unavailable. Please try again later.")
        return redirect(url_for("home"))
    params = []
    query = "SELECT * FROM properties WHERE 1=1"

    filters = ["city","locality","type","possession","furnishing","category"]
    for f in filters:
        v = request.args.get(f)
        if v:
            if f == "locality":
                query += f" AND {f} LIKE %s"
                params.append(f"%{v}%")
            else:
                query += f" AND {f} LIKE %s"
                params.append(f"%{v}%")


    bhk = request.args.get("bhk")
    if bhk:
        query += " AND bhk LIKE %s"
        params.append(f"%{bhk}%")

    min_budget = request.args.get("min_budget")
    max_budget = request.args.get("max_budget")
    min_area = request.args.get("min_area")

    if min_budget:
        query += " AND price_min >= %s"
        params.append(min_budget)

    if max_budget:
        query += " AND price_max <= %s"
        params.append(max_budget)

    if min_area:
        query += " AND area >= %s"
        params.append(min_area)

    cursor.execute(query, params)
    properties = cursor.fetchall()

    wishlist = []
    if current_user.is_authenticated:
        cursor.execute("SELECT property_id FROM wishlists WHERE user_id=%s", (current_user.id,))
        wishlist = [row['property_id'] for row in cursor.fetchall()]

    return render_template("results.html", properties=properties, wishlist=wishlist)

# --- Property Detail ---

@app.route("/property/<int:id>")
def property_detail(id):
    if not cursor:
        flash("Database unavailable. Please try again later.")
        return redirect(url_for("home"))
    cursor.execute("SELECT * FROM properties WHERE id=%s", (id,))
    property = cursor.fetchone()
    return render_template("property_detail.html", property=property)

# --- Auth ---

@app.route("/signup", methods=["GET", "POST"])
def signup():
    form = SignupForm()

    if form.validate_on_submit():
        if not cursor:
            flash("Database unavailable. Try again later.")
            return redirect(url_for("signup"))

        username = form.username.data.strip()
        email = form.email.data.strip().lower()
        password = form.password.data

        try:
            # Check existing email
            cursor.execute("SELECT id FROM users WHERE email=%s", (email,))
            if cursor.fetchone():
                flash("Email already registered.")
                return render_template("signup.html", form=form)

            hashed_password = generate_password_hash(password)

            cursor.execute(
                "INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s)",
                (username, email, hashed_password)
            )
            db.commit()

            flash("Account created successfully. Please login.")
            return redirect(url_for("login"))

        except Exception as e:
            app.logger.error(f"Signup error: {e}")
            flash("Signup failed. Try again.")

    return render_template("signup.html", form=form)


@app.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()

    if form.validate_on_submit():
        if not cursor:
            flash("Database unavailable. Try again later.")
            return redirect(url_for("login"))

        email = form.email.data.strip().lower()
        password = form.password.data

        try:
            cursor.execute(
                "SELECT id, username, email, password_hash FROM users WHERE email=%s",
                (email,)
            )
            user = cursor.fetchone()

            if user and check_password_hash(user["password_hash"], password):
                login_user(User(user["id"], user["username"], user["email"]))
                flash("Login successful.")
                return redirect(url_for("home"))
            else:
                flash("Invalid email or password.")

        except Exception as e:
            app.logger.error(f"Login error: {e}")
            flash("Login failed. Try again.")

    return render_template("login.html", form=form)


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Logged out successfully!")
    return redirect(url_for("home"))

# --- Wishlist ---

@app.route("/add_to_wishlist/<int:id>")
@login_required
def add_to_wishlist(id):
    if not cursor:
        flash("Database unavailable. Please try again later.")
        return redirect(request.referrer or url_for("home"))
    try:
        cursor.execute("INSERT INTO wishlists (user_id,property_id) VALUES (%s,%s)", (current_user.id, id))
        db.commit()
    except:
        pass
    return redirect(request.referrer)

@app.route("/wishlist")
@login_required
def wishlist():
    if not cursor:
        flash("Database unavailable. Please try again later.")
        return redirect(url_for("home"))
    cursor.execute("""
        SELECT p.* FROM properties p
        JOIN wishlists w ON p.id = w.property_id
        WHERE w.user_id=%s
    """, (current_user.id,))
    return render_template("wishlist.html", properties=cursor.fetchall())

@app.route("/remove_from_wishlist/<int:id>")
@login_required
def remove_from_wishlist(id):
    if not cursor:
        flash("Database unavailable. Please try again later.")
        return redirect(request.referrer or url_for("wishlist"))
    cursor.execute("DELETE FROM wishlists WHERE user_id=%s AND property_id=%s", (current_user.id, id))
    db.commit()
    return redirect(request.referrer or url_for("wishlist"))

# ... (rest of app.py unchanged)

@app.template_filter('format_number')
def format_number(value):
    """Jinja filter to format numbers with commas (e.g., 25000000 → 25,000,000)"""
    try:
        return "{:,.0f}".format(int(float(value)))
    except (ValueError, TypeError):
        return value

@app.route("/estimate_price", methods=["POST"])
@login_required
def estimate_price():
    if not cursor:
        flash("Database unavailable. Please try again later.")
        return redirect(url_for("dashboard"))
    city_input = request.form.get('city', '').strip()
    area_str = request.form.get('area', '').strip()

    # Get dashboard stats (unchanged)
    cursor.execute("SELECT COUNT(*) AS cnt FROM properties")
    total_properties = cursor.fetchone()['cnt']
    cursor.execute("SELECT COUNT(*) AS cnt FROM enquiries1 WHERE user_id=%s", (current_user.id,))
    total_enquiries = cursor.fetchone()['cnt']
    cursor.execute("SELECT COUNT(*) AS cnt FROM wishlists WHERE user_id=%s", (current_user.id,))
    wishlist_count = cursor.fetchone()['cnt']

    estimate_low = None
    estimate_high = None
    note = None
    matching_properties = []

    # Realistic Feb 2026 average rates per sq ft (INR) - based on PropTiger, 99acres, Housing.com reports
    market_rates = {
        'mumbai': 28000,       # MMR mid/premium weighted avg (suburban ~22-35k, south/premium higher)
        'mmr': 28000,
        'bengaluru': 9500,
        'bangalore': 9500,
        'delhi': 9200,
        'delhi ncr': 9200,
        'ncr': 9200,
        'pune': 7100,
        'hyderabad': 7400,
        'chennai': 7500,       # Good default for your Tamil Nadu location
        'ahmedabad': 4800,
        'kolkata': 5900,
    }

    city_lower = city_input.lower()
    matched_key = None
    for key in market_rates:
        if key in city_lower:
            matched_key = key
            break

    try:
        area_val = float(area_str)
        if area_val <= 0:
            note = "Area must be greater than 0 sq ft."
        else:
            base_rate = None

            if matched_key:
                base_rate = market_rates[matched_key]
                # Wider range for Mumbai due to high locality variation
                low_mult = 0.7 if 'mumbai' in city_lower or 'mmr' in city_lower else 0.85
                high_mult = 1.4 if 'mumbai' in city_lower or 'mmr' in city_lower else 1.15
                estimate_low = area_val * (base_rate * low_mult)
                estimate_high = area_val * (base_rate * high_mult)
                note = f"Based on Feb 2026 market averages (~₹{base_rate:,}/sq ft in {matched_key.capitalize()}). Actual prices vary by exact locality, project, and amenities."
            else:
                # Fallback: average from your own properties table
                cursor.execute(
                    """
                    SELECT AVG((price_min + price_max) / 2 / area) AS avg_rate
                    FROM properties
                    WHERE (city LIKE %s OR locality LIKE %s) AND area > 0
                    """,
                    (f"%{city_input}%", f"%{city_input}%")
                )
                row = cursor.fetchone()
                if row and row['avg_rate'] is not None:
                    base_rate = float(row['avg_rate'])
                    estimate_low = area_val * (base_rate * 0.85)
                    estimate_high = area_val * (base_rate * 1.15)
                    note = f"Based on properties in your database for '{city_input}' (~₹{base_rate:.0f}/sq ft average)."
                else:
                    note = "No market data or properties found for this place. Try major cities like Chennai, Mumbai, Bengaluru, Pune, etc."

            if estimate_low is not None and estimate_high is not None:
                mid_estimate = (estimate_low + estimate_high) / 2
                mid_rate = mid_estimate / area_val if area_val > 0 else 0

                # Matching properties: city/locality match + area within ±50% + price overlap
                # Note: prices in DB are in lakhs; estimate is in rupees
                estimate_low_lakhs = estimate_low / 100000
                estimate_high_lakhs = estimate_high / 100000

                cursor.execute("""
                    SELECT id, title, city, locality, bhk, area, price_min, price_max, furnishing, possession, type, category, image
                    FROM properties
                    WHERE (city LIKE %s OR locality LIKE %s)
                      AND area BETWEEN %s AND %s
                      AND (
                        (price_min <= %s AND price_max >= %s) OR
                        (price_min BETWEEN %s AND %s) OR
                        (price_max BETWEEN %s AND %s)
                      )
                    ORDER BY ABS((price_min + price_max)/2 - %s)
                    LIMIT 6
                """, (
                    f"%{city_input}%", f"%{city_input}%",
                    area_val * 0.5, area_val * 1.5,
                    estimate_high_lakhs, estimate_low_lakhs,
                    estimate_low_lakhs, estimate_high_lakhs,
                    estimate_low_lakhs, estimate_high_lakhs,
                    (estimate_low_lakhs + estimate_high_lakhs) / 2
                ))
                matching_properties = cursor.fetchall()

                if not matching_properties:
                    note += " No exact matches in current listings — prices or sizes may differ slightly."

    except ValueError:
        note = "Please enter a valid number for area (sq ft)."

    return render_template("dashboard.html",
                           total_properties=total_properties,
                           total_enquiries=total_enquiries,
                           wishlist_count=wishlist_count,
                           estimate_low=estimate_low,
                           estimate_high=estimate_high,
                           input_area=area_str,
                           input_city=city_input,
                           note=note,
                           matching_properties=matching_properties)
# --- Enquiry ---

@app.route("/enquiry", methods=["POST"])
@login_required
def enquiry():
    if not cursor:
        flash("Database unavailable. Please try again later.")
        return redirect(url_for("home"))
    data = ( current_user.id, request.form['property_id'], request.form['name'],
             request.form['email'], request.form['phone'], request.form['message'] )
    cursor.execute("INSERT INTO enquiries1 (user_id,property_id,name,email,phone,message) VALUES (%s,%s,%s,%s,%s,%s)", data)
    db.commit()
    return render_template("thank_you.html")

# --- Dashboard ---

@app.route("/dashboard")
@login_required
def dashboard():
    if not cursor:
        flash("Database unavailable. Please try again later.")
        return redirect(url_for("home"))
    # statistics for display
    cursor.execute("SELECT COUNT(*) AS cnt FROM properties")
    total_properties = cursor.fetchone()['cnt']
    cursor.execute("SELECT COUNT(*) AS cnt FROM enquiries1 WHERE user_id=%s", (current_user.id,))
    total_enquiries = cursor.fetchone()['cnt']
    cursor.execute("SELECT COUNT(*) AS cnt FROM wishlists WHERE user_id=%s", (current_user.id,))
    wishlist_count = cursor.fetchone()['cnt']

    # we no longer use enquiries data on dashboard
    return render_template("dashboard.html",
                           total_properties=total_properties,
                           total_enquiries=total_enquiries,
                           wishlist_count=wishlist_count)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

