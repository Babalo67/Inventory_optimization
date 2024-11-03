from flask import Flask, render_template, request, redirect, url_for, flash, session, send_from_directory
import os
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression
import sqlite3
import plotly.express as px
import plotly.graph_objects as go

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Replace with a secure random key

# Database setup
def init_db():
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT,
            role TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# Route for the index page
@app.route('/')
def index():
    return render_template('index.html')

# Route to handle role redirection
@app.route('/role_redirect', methods=['POST'])
def role_redirect():
    role = request.form.get('role')
    
    if role == 'admin':
        return redirect(url_for('register_page'))  # Redirect to register.html
    elif role == 'manager':
        return redirect(url_for('login_page'))  # Redirect to login.html
    else:
        flash('Invalid role selection. Please try again.')
        return redirect(url_for('index'))

# Route for the registration page
@app.route('/register', methods=['GET', 'POST'])
def register_page():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        if username and password:
            conn = sqlite3.connect('users.db')
            cursor = conn.cursor()
            try:
                cursor.execute('INSERT INTO users (username, password, role) VALUES (?, ?, ?)', (username, password, 'manager'))
                conn.commit()
                flash('User registered successfully!')
            except sqlite3.IntegrityError:
                flash('Username already exists.')
            conn.close()
            return redirect(url_for('index'))
    return render_template('register.html')

# Route for the login page
@app.route('/login', methods=['GET', 'POST'])
def login_page():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE username = ? AND password = ?', (username, password))
        user = cursor.fetchone()
        conn.close()
        
        if user:
            session['username'] = username
            flash('Login successful!')
            return redirect(url_for('upload_page'))  # Redirect to upload page
        else:
            flash('Invalid credentials. Please try again.')
    return render_template('login.html')

# Route to upload a file (Upload Page)
@app.route('/upload', methods=['GET', 'POST'])
def upload_page():
    if request.method == 'POST':
        file = request.files['file']
        if file:
            file_path = os.path.join('static', file.filename)
            file.save(file_path)
            process_csv(file_path)
            return redirect(url_for('results_page'))  # Redirect to results page
    return render_template('upload.html')  # Render the upload page for GET requests

# Function to process the uploaded CSV file
def process_csv(file_path):
    # Load the sales data
    data = pd.read_csv(file_path)
    data['date'] = pd.to_datetime(data['date'])
    data['month'] = data['date'].dt.month

    # One-hot encoding for the 'product_id' column
    X = pd.get_dummies(data[['product_id', 'month']], columns=['product_id'])
    y = data['sales']

    # Split data into training and testing sets
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=0)

    # Train a linear regression model
    model = LinearRegression()
    model.fit(X_train, y_train)

    # Predicting sales
    predictions = model.predict(X_test)

    # Save predictions to CSV
   # predictions_df = pd.DataFrame({
  #      'Product ID': X_test.idxmax(axis=1),
  #      'Predicted Sales': predictions
   # })
   # csv_output_path = os.path.join('static', 'predicted_sales.csv')
   # predictions_df.to_csv(csv_output_path, index=False)

    # Aggregate sales data by product
    product_sales = data.groupby(['product_id', 'product_name'])['sales'].sum().reset_index()
    
    # Calculate median sales
    median_sales = product_sales['sales'].median()
    product_sales['category'] = product_sales['sales'].apply(
        lambda x: 'Fast-Moving' if x >= median_sales else 'Slow-Moving'
    )


    # Stock Level Adjustments: Recommend restocking amounts
    product_sales['restock_recommendation'] = product_sales['category'].apply(
        lambda x: 'Increase Stock by 20%' if x == 'Fast-Moving' else 'Reduce Stock'
    )

    # Save product sales for visualization
    product_sales.to_excel(os.path.join('static', 'product_sales_summary.xlsx'), index=False)


    # Bar chart for sales by product
    colors = ['green' if category == 'Fast-Moving' else 'red' for category in product_sales['category']]
    bar_fig = px.bar(product_sales, x='product_name', y='sales', color='category',
                     color_discrete_map={'Fast-Moving': 'green', 'Slow-Moving': 'red'},
                     title="Total Sales by Product Name")

    bar_fig.update_layout(xaxis_title='Product Name', yaxis_title='Total Sales')
    bar_fig.write_html(os.path.join('static', 'total_sales_by_product_name.html'))

    # Most and Least Selling Products
    most_selling = product_sales.nlargest(5, 'sales')
    least_selling = product_sales.nsmallest(5, 'sales')

    # Bar chart for most and least selling products
    bar_fig = px.bar(most_selling, x='product_name', y='sales', color='sales',
                     title="Most Selling Products", color_continuous_scale=px.colors.sequential.Greens)

    bar_fig.write_html(os.path.join('static', 'most_selling_products.html'))

    # Bar chart for least selling products
    bar_fig_least = px.bar(least_selling, x='product_name', y='sales', color='sales',
                            title="Least Selling Products", color_continuous_scale=px.colors.sequential.Reds)

    bar_fig_least.write_html(os.path.join('static', 'least_selling_products.html'))



@app.route('/download-product-sales')
def download_product_sales():
    # Specify the file path
    file_path = os.path.join('static', 'product_sales_summary.xlsx')
    
    # Return the file as an attachment
    return send_from_directory(directory='static', path='product_sales_summary.xlsx', as_attachment=True)

# Route to show the results
@app.route('/results')
def results_page():
    return render_template('results.html')

# Route to delete the uploaded file
@app.route('/delete', methods=['POST'])
def delete_file():
    file_paths = [
        os.path.join('static', 'sales_data.csv'),
        os.path.join('static', 'total_sales_by_product_name.html'),
        os.path.join('static', 'most_selling_products.html'),
        os.path.join('static', 'least_selling_products.html'),
        os.path.join('static', 'product_sales_summary.html')
    ]

    try:
        deleted = False
        for file_path in file_paths:
            if os.path.exists(file_path):
                os.remove(file_path)
                deleted = True
        if deleted:
            flash('File(s) deleted successfully!')
        else:
            flash('No file to delete.')
    except Exception as e:
        flash(f'Error deleting file(s): {str(e)}')
    
    return redirect(url_for('upload_page'))

@app.route('/logout', methods=['GET', 'POST'])
def logout():
    session.pop('username', None)
    flash('You have been logged out.')
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
