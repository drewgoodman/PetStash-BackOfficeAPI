from flask import Flask, render_template, flash, redirect, url_for, session, request, jsonify
from flask_cors import CORS
from flask_mysqldb import MySQL
from wtforms import Form, StringField, TextAreaField, SelectField, PasswordField, DecimalField, IntegerField, FieldList, FormField, validators
from passlib.hash import sha256_crypt
from functools import wraps
import os

app = Flask(__name__)
CORS(app)


app.config['MYSQL_HOST'] = os.environ.get('API_HOST')
app.config['MYSQL_USER'] = os.environ.get('API_USER')
app.config['MYSQL_PASSWORD'] = os.environ.get('API_PASSWORD')
app.config['MYSQL_DB'] = os.environ.get('API_DB')
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'
app.config['SECRET_KEY'] = os.environ.get('API_SECRET_KEY')


mysql = MySQL(app)

PRODUCT_ORDER_DEFAULT = " shop_product_category_id, shop_product_name"


def is_admin_logged_in(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if 'admin_logged_in' in session:
            return f(*args, **kwargs)
        else:
            flash("Unauthorized, please login", "danger")
            return redirect(url_for("admin_login"))
    return wrap


@app.route('/')
def home():
    cur = mysql.connection.cursor()
    result = cur.execute("SELECT * FROM admin_updatelog")
    updates = cur.fetchall()
    return render_template('home.html', updates=updates)
    cur.close()


class AdminRegisterForm(Form):
    valid_id = ['123456','654321']
    firstname = StringField('First Name', [validators.Length(min=1, max=45)])
    lastname = StringField('Last Name', [validators.Length(min=1, max=45)])
    employee_id = StringField('Employee ID', [validators.AnyOf(valid_id, message="Must use a valid employee ID")])
    username = StringField('Username', [validators.Length(min=4, max=25)])
    password = PasswordField('Password', [
        validators.DataRequired(),
        validators.EqualTo('confirm', message="Passwords do not match.")
    ])
    confirm = PasswordField('Confirm Password')


@app.route('/register', methods=['GET', 'POST'])
def admin_register():
    form = AdminRegisterForm(request.form)
    cur = mysql.connection.cursor()
    result = cur.execute("SELECT * FROM admin_user")
    current_users = cur.fetchall()
    current_user_list = []

    for user in current_users:
        current_user_list.append(user["admin_user_username"])

    if request.method == 'POST' and form.username.data in current_user_list:
        flash('That username has already been taken.', 'danger')
    elif request.method == 'POST' and form.validate():

        firstname = form.firstname.data
        lastname = form.lastname.data
        username = form.username.data
        employee_id = form.employee_id.data
        password = sha256_crypt.hash(str(form.password.data))
        cur = mysql.connection.cursor() 
        cur.execute("""INSERT INTO admin_user(
                            admin_user_firstname,
                            admin_user_lastname, 
                            admin_user_employee_id, 
                            admin_user_username, 
                            admin_user_password
                            ) VALUES(%s, %s, %s, %s, %s)""", (firstname, lastname, employee_id, username, password))
        mysql.connection.commit()

        result = cur.execute("SELECT * FROM admin_user WHERE admin_user_username = %s", [username])
        data = cur.fetchone()
        admin_id = data['admin_user_id']
        log_message = f"Registered {username} (Employee #{employee_id}) in PetStash Back Office."
        cur.execute("INSERT INTO admin_updatelog(admin_updatelog_log, admin_updatelog_admin_id, admin_updatelog_admin) VALUES(%s, %s, %s)", (log_message, admin_id, username))

        mysql.connection.commit()
        cur.close()
        flash('You are now registered and can log in', 'success')
        return redirect(url_for('home'))
    return render_template('register.html', form=form)


@app.route('/login', methods=["GET","POST"])
def admin_login():
    if request.method == "POST":
        username = request.form['username']
        password_input = request.form['password']
        cur = mysql.connection.cursor()
        result = cur.execute("SELECT * FROM admin_user WHERE admin_user_username = %s", [username])
        if result > 0:
            user = cur.fetchone()
            password = user["admin_user_password"]
            if sha256_crypt.verify(password_input, password):
                session['admin_logged_in'] = True
                session['admin_username'] = username
                session['admin_lastname'] = user["admin_user_lastname"]
                session['admin_id'] = user["admin_user_id"]
                flash("You are now logged in.","success")
                return redirect(url_for('home'))
        
        else:
            flash('Username not found.', 'danger')
            return render_template('login.html')
    else:
        return render_template('login.html')


@app.route('/categories')
def categories():
    cur = mysql.connection.cursor()
    result = cur.execute("SELECT * FROM shop_categories")
    categories = cur.fetchall()
    return render_template('categories.html', categories=categories)


class CategoryForm(Form):
    name = StringField('Category Name', [validators.Length(min=2, max=45)])
    route = StringField('Category Displayed Route', [validators.Length(min=2, max=19)])
    dropdown_list = [("1",'Active'),("0",'Hidden')]
    display = SelectField('Display Status', choices=dropdown_list)
    icon_url = StringField('Category Icon URL', [validators.Length(max=100)])
    banner_url = StringField('Banner URL', [validators.Length(max=100)])
    banner_display = SelectField('Banner Carousel Display', choices=dropdown_list, default=0)
    banner_button = StringField('Banner Button Text', [validators.Length(max=45)])
    banner_caption = StringField('Banner Caption Text', [validators.Length(max=150)])


@app.route('/category-add', methods=["GET","POST"])
@is_admin_logged_in
def category_add():
    form = CategoryForm(request.form)
    if request.method == "POST" and form.validate():
        name = form.name.data
        display = int(form.display.data)
        route = form.route.data
        icon_url = form.icon_url.data
        banner_url = form.banner_url.data
        banner_display = form.banner_display.data
        banner_button = form.banner_button.data
        banner_caption = form.banner_caption.data
        cur = mysql.connection.cursor()
        cur.execute("""INSERT INTO shop_categories(
                        shop_category_name, 
                        shop_category_display, 
                        shop_category_route, 
                        shop_category_icon_url, 
                        shop_category_banner_url, 
                        shop_category_banner_display, 
                        shop_category_banner_button, 
                        shop_category_banner_caption
                        ) VALUES(%s, %s, %s, %s, %s, %s, %s, %s)""",
                        (name, display, route, icon_url, banner_url, banner_display, banner_button, banner_caption))
        mysql.connection.commit()
        log_message = f"Created new product category: {name}."
        cur.execute("INSERT INTO admin_updatelog(admin_updatelog_log, admin_updatelog_admin_id, admin_updatelog_admin) VALUES(%s, %s, %s)", (log_message, session['admin_id'], session['admin_username']))
        mysql.connection.commit()
        cur.close()
        flash("Category Successfully Added", 'success')
        return redirect(url_for("categories"))
    return render_template('category_add.html', form=form)


@app.route('/category-edit/<string:id>', methods=["GET","POST"])
@is_admin_logged_in
def category_edit(id):
    cur = mysql.connection.cursor()
    result = cur.execute("SELECT * FROM shop_categories WHERE shop_category_id = %s", [id])
    category = cur.fetchone()
    form = CategoryForm(request.form)
    form.name.data = category["shop_category_name"]
    form.display.data = str(category["shop_category_display"])
    form.route.data =  category["shop_category_route"]
    form.icon_url.data = category["shop_category_icon_url"]
    form.banner_url.data = category["shop_category_banner_url"]
    form.banner_display.data = str(category["shop_category_banner_display"])
    form.banner_button.data = category["shop_category_banner_button"]
    form.banner_caption.data = category["shop_category_banner_caption"]
    if request.method == "POST" and form.validate():
        name = request.form['name']
        display = int(request.form['display'])
        route = request.form['route']
        icon_url = request.form['icon_url']
        banner_url = request.form['banner_url']
        banner_display = request.form['banner_display']
        banner_button = request.form['banner_button']
        banner_caption = request.form['banner_caption']
        cur.execute("""UPDATE shop_categories
                        SET shop_category_name = %s,
                        shop_category_display = %s,
                        shop_category_route = %s,
                        shop_category_icon_url = %s,
                        shop_category_banner_url = %s,
                        shop_category_banner_display = %s,
                        shop_category_banner_button = %s,
                        shop_category_banner_caption = %s
                        WHERE shop_category_id = %s""", (name, display, route, icon_url, banner_url, banner_display, banner_button, banner_caption, id))
        mysql.connection.commit()
        log_message = f"Updated product category: {name}."
        cur.execute("INSERT INTO admin_updatelog(admin_updatelog_log, admin_updatelog_admin_id, admin_updatelog_admin) VALUES(%s, %s, %s)", (log_message, session['admin_id'], session['admin_username']))
        mysql.connection.commit()
        cur.close()
        flash("Category Successfully Added", 'success')
        return redirect(url_for("categories"))
    return render_template("category_edit.html", form=form)


@app.route("/products")
def products():
    cur = mysql.connection.cursor()
    result = cur.execute("""SELECT p.id, p.shop_product_name, p.shop_product_brand, p.shop_product_price, p.shop_product_display, p.shop_product_onhand, c.shop_category_name
                            FROM shop_products p
                            LEFT JOIN shop_categories c
                            ON c.shop_category_id = p.shop_product_category_id
                            ORDER BY """ + PRODUCT_ORDER_DEFAULT)
    products = cur.fetchall()
    return render_template('products.html', products=products)



class ProductForm(Form):
    name = StringField('Product Name', [validators.Length(min=2, max=100)])
    brand = StringField('Product Brand', [validators.Length(min=2, max=45)])
    price = DecimalField('Retail Price', [validators.NumberRange(min=0, max=10000)], places=2)
    image_url = StringField('Product Image URL', [validators.Length(max=100)])
    description = TextAreaField('Product Description', [validators.Length(max=255)])
    dropdown_list = [("1",'Active'),("0",'Hidden')]
    display = SelectField('Display Status', choices=dropdown_list)
    category = SelectField('Primary Category', choices=[], coerce=int)


def product_category_options():
    # populates the dropdown menu for primary category choices
    cur = mysql.connection.cursor()
    result = cur.execute("SELECT * FROM shop_categories")
    categories = cur.fetchall()
    category_list = []
    if result == 0:
        category_list = [(-1,"None")]
    else:
        for category in categories:
            category_list.append((category["shop_category_id"], category["shop_category_name"]))
    cur.close()
    return category_list

def product_category_parse(category_data):
    # for return a Null value if no primary category is set, just to catch errors before categories are created.
    if category_data == -1:
        return None
    else:
        return int(category_data)


@app.route('/product-add', methods=["GET","POST"])
@is_admin_logged_in
def product_add():
    form = ProductForm(request.form)
    form.category.choices = product_category_options()
    if request.method == "POST" and form.validate():
        name = form.name.data
        price = form.price.data
        brand = form.brand.data
        image_url = form.image_url.data
        description = form.description.data
        category = product_category_parse(form.category.data)
        display = int(form.display.data)
        cur = mysql.connection.cursor()
        cur.execute("""INSERT INTO shop_products(
                        shop_product_name,
                        shop_product_brand, 
                        shop_product_price, 
                        shop_product_image_url, 
                        shop_product_description, 
                        shop_product_category_id, 
                        shop_product_display
                        ) VALUES(%s, %s, %s, %s, %s, %s, %s)""",
                        (name, brand, price, image_url, description, category, display))
        mysql.connection.commit()
        log_message = f"Successfully added new product: {name} by {brand}."
        cur.execute("INSERT INTO admin_updatelog(admin_updatelog_log, admin_updatelog_admin_id, admin_updatelog_admin) VALUES(%s, %s, %s)", (log_message, session['admin_id'], session['admin_username']))
        mysql.connection.commit()
        cur.close()
        flash("Product Successfully Added", 'success')
        return redirect(url_for("products"))
    return render_template('product_add.html', form=form)


@app.route('/product-edit/<string:id>', methods=["GET","POST"])
@is_admin_logged_in
def product_edit(id):
    cur = mysql.connection.cursor()
    result = cur.execute("SELECT * FROM shop_products WHERE id = %s", [id])
    product = cur.fetchone()
    form = ProductForm(request.form)
    form.category.choices = product_category_options()
    form.name.data = product["shop_product_name"]
    form.price.data =  product["shop_product_price"]
    form.brand.data =  product["shop_product_brand"]
    form.image_url.data = product["shop_product_image_url"]
    form.description.data = product["shop_product_description"]
    if product["shop_product_category_id"]:
        form.category.data = product_category_parse(product["shop_product_category_id"])
    form.display.data = str(product["shop_product_display"])
    if request.method == "POST" and form.validate():
        name = request.form['name']
        price = request.form['price']
        brand = request.form['brand']
        image_url = request.form['image_url']
        description = request.form['description']
        category = product_category_parse(request.form['category'])
        display = int(request.form['display'])
        cur = mysql.connection.cursor()
        cur.execute("""UPDATE shop_products
                    SET shop_product_name = %s,
                    shop_product_brand = %s,
                    shop_product_price = %s,
                    shop_product_image_url = %s,
                    shop_product_description = %s,
                    shop_product_category_id = %s,
                    shop_product_display = %s
                    WHERE id = %s""",
                    (name, brand, price, image_url, description, category, display, id))
        mysql.connection.commit()

        log_message = f"Successfully updated product: {name} by {brand}."
        cur.execute("INSERT INTO admin_updatelog(admin_updatelog_log, admin_updatelog_admin_id, admin_updatelog_admin) VALUES(%s, %s, %s)", (log_message, session['admin_id'], session['admin_username']))
        mysql.connection.commit()
        cur.close()
        flash("Product Successfully Updated", 'success')
        return redirect(url_for("products"))
    return render_template("product_edit.html", form=form)


class InventoryEntryForm(Form):
    product_name = StringField('name')
    product_id = IntegerField('product_id')
    onhand = IntegerField('Update Onhand', [validators.NumberRange(min=0)])

class InventoryListForm(Form):
    inventory_list = FieldList(FormField(InventoryEntryForm))


@app.route('/inventory', methods=["GET","POST"])
@is_admin_logged_in
def receive_order():
    cur = mysql.connection.cursor()
    result = cur.execute("SELECT shop_product_name, id, shop_product_onhand FROM shop_products ORDER BY " + PRODUCT_ORDER_DEFAULT)
    products = cur.fetchall()
    inventory_form = InventoryListForm(request.form)
    if request.method == "POST" and inventory_form.validate():
        for update in inventory_form.inventory_list:
            product_id = update.product_id.data
            onhand = update.onhand.data
            print(update.product_name.data,product_id,onhand)
            cur.execute("""UPDATE shop_products
                        SET shop_product_onhand = %s
                        WHERE id = %s""", (onhand, product_id))
            mysql.connection.commit()
        flash("Inventory successfully updated","success")
        return redirect(url_for("home"))
    elif request.method == "POST":
        flash("Can only accept numeric edits above 0.","danger")
        return redirect(url_for("receive_order"))
    if result > 0:
        for product in products:
            product_form = InventoryEntryForm()
            product_form.product_name = product['shop_product_name']
            product_form.product_id = product['id']
            product_form.onhand = product['shop_product_onhand']
            inventory_form.inventory_list.append_entry(product_form)
        return render_template("inventory.html", form=inventory_form)
    else:
        flash("No products found", "danger")
        return redirect(url_for("home"))





@app.route('/logout')
@is_admin_logged_in
def logout():
    session.clear()
    flash('You are now logged out.',"success")
    return redirect(url_for('home'))


if __name__ == "__main__":
    app.run(debug=True)