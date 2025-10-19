from flask import Flask, render_template, request, jsonify
from gradio_client import Client
import os

app = Flask(__name__)

# Initialize the Gradio client
client = Client("markobinario/flaskbot")

@app.route('/')
def home():
    """Render the home page"""
    return render_template('home.html')

@app.route('/chatbot')
def chatbot():
    """Render the chatbot page"""
    return render_template('chatbot.html')

@app.route('/recommendations')
def recommendations():
    """Render the recommendations page"""
    return render_template('recommendations.html')

@app.route('/chat', methods=['POST'])
def chat():
    """Handle chat messages and return bot responses"""
    try:
        # Get the message from the request
        data = request.get_json()
        message = data.get('message', '').strip()
        
        if not message:
            return jsonify({'error': 'No message provided'}), 400
        
        # Call the Gradio API
        result = client.predict(
            message=message,
            api_name="/chat"
        )
        
        # Return the bot's response
        return jsonify({
            'response': result,
            'status': 'success'
        })
        
    except Exception as e:
        print(f"Error calling Gradio API: {str(e)}")
        return jsonify({
            'error': 'Failed to get response from chatbot',
            'status': 'error'
        }), 500

@app.route('/course_recommendations', methods=['POST'])
def course_recommendations():
    """Get course recommendations based on student profile"""
    try:
        # Get the data from the request
        data = request.get_json()
        stanine = data.get('stanine', '')
        gwa = data.get('gwa', '')
        strand = data.get('strand', '')
        hobbies = data.get('hobbies', '')
        
        # Validate required fields
        if not all([stanine, gwa, strand, hobbies]):
            return jsonify({
                'error': 'Missing required fields: stanine, gwa, strand, and hobbies are required',
                'status': 'error'
            }), 400
        
        # Call the Gradio API for course recommendations
        result = client.predict(
            stanine=stanine,
            gwa=gwa,
            strand=strand,
            hobbies=hobbies,
            api_name="/get_course_recommendations"
        )
        
        # Return the course recommendations
        return jsonify({
            'recommendations': result,
            'status': 'success'
        })
        
    except Exception as e:
        print(f"Error calling course recommendations API: {str(e)}")
        return jsonify({
            'error': 'Failed to get course recommendations',
            'status': 'error'
        }), 500

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({'status': 'healthy'})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
