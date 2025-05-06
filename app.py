from flask import Flask

# Create Flask application
app = Flask(__name__)

# Define route for homepage
@app.route('/')
def hello_world():
    """
    Route handler for the homepage that returns 'Hello World!'
    """
    return '<h1>Hello World!</h1>'

# Run the application if executed directly
if __name__ == '__main__':
    app.run(debug=True) 