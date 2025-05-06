from flask import Flask, render_template

# Initialize Flask application
app = Flask(__name__)

# Define routes
@app.route('/')
def hello_world():
    """
    Route handler for the home page.
    Returns a simple Hello World page.
    """
    return render_template('index.html')

# Run the application
if __name__ == '__main__':
    app.run(debug=True) 