from flask import Flask, render_template, request, redirect, url_for, flash, session
import os
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression
import sqlite3

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
            return redirect(url_for('login_page'))
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
    predictions_df = pd.DataFrame({
        'Product ID': X_test.idxmax(axis=1),
        'Predicted Sales': predictions
    })
    csv_output_path = os.path.join('static', 'predicted_sales.csv')
    predictions_df.to_csv(csv_output_path, index=False)

    # Aggregate sales data by product
    product_sales = data.groupby(['product_id', 'product_name'])['sales'].sum().reset_index()
    median_sales = product_sales['sales'].median()
    product_sales['category'] = product_sales['sales'].apply(
        lambda x: 'Fast-Moving' if x >= median_sales else 'Slow-Moving'
    )

    # Plot the total sales by product
    plt.figure(figsize=(10, 6))
    colors = ['green' if category == 'Fast-Moving' else 'red' for category in product_sales['category']]
    plt.bar(product_sales['product_name'], product_sales['sales'], color=colors)

    # Create legend handles manually
    from matplotlib.patches import Patch
    fast_moving_patch = Patch(color='green', label='Fast-Moving products')
    slow_moving_patch = Patch(color='red', label='Slow-Moving products')
    
    # Add legend
    plt.legend(handles=[fast_moving_patch, slow_moving_patch], title="Category")

    plt.xlabel('Product Name')
    plt.ylabel('Total Sales')
    plt.title('Total Sales by Product Name')
    plt.xticks(rotation=45)
    plt.tight_layout()

    # Save the chart as PNG
    png_output_path = os.path.join('static', 'total_sales_by_product_name.png')
    plt.savefig(png_output_path)
    plt.close()

# Route to show the results
@app.route('/results')
def results_page():
    return render_template('results.html')  # Render the results page

# Route to delete the uploaded file
@app.route('/delete', methods=['POST'])
def delete_file():
    file_path = os.path.join('static', 'uploaded_file.csv')  # Adjust the path as necessary
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            flash('File deleted successfully!')
        else:
            flash('No file to delete.')
    except Exception as e:
        flash(f'Error deleting file: {str(e)}')
    return redirect(url_for('upload_page'))

@app.route('/logout', methods=['GET', 'POST'])
def logout():
    session.pop('username', None)
    flash('You have been logged out.')
    return redirect(url_for('index'))


if __name__ == '__main__': 
    app.run(debug=True)
