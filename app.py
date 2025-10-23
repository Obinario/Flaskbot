from flask import Flask, render_template, request, jsonify
import os
import sys
import subprocess
import json

# Fix Windows console encoding issues
if sys.platform == "win32":
    import codecs
    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())
    sys.stderr = codecs.getwriter("utf-8")(sys.stderr.detach())

app = Flask(__name__)

# Initialize the Gradio client with error handling
client = None
try:
    from gradio_client import Client
    import requests
    
    # First, let's check if the space is accessible
    space_url = "https://markobinario-flaskbot.hf.space"
    try:
        response = requests.get(space_url, timeout=10)
        if response.status_code == 200:
            print("✓ Hugging Face Space is accessible")
        else:
            print(f"⚠ Space returned status code: {response.status_code}")
    except Exception as e:
        print(f"⚠ Could not reach Hugging Face Space: {e}")
    
    # Initialize client with proper error handling
    client = Client("markobinario/flaskbot")
    print("✓ Gradio client initialized successfully")
    
except Exception as e:
    print(f"Warning: Could not initialize Gradio client: {e}")
    print("The app will run with mock responses for testing.")
    client = None

@app.route('/')
def index():
    """Render the main chat page"""
    return render_template('index.html')

def get_mock_response(message):
    """Generate a mock response for testing"""
    responses = [
        f"I received your message: '{message}'. This is a mock response while we're setting up the AI connection.",
        f"Thanks for saying '{message}'! I'm currently in demo mode.",
        f"Mock AI: I understand you said '{message}'. The real AI will be connected soon!",
        f"Demo response to '{message}': The Flask app is working correctly!"
    ]
    import random
    return random.choice(responses)

def call_hf_space_api(message):
    """Call Hugging Face Space API using direct HTTP request"""
    try:
        import requests
        
        # Try direct API call to the space using the correct endpoint
        api_url = "https://markobinario-flaskbot.hf.space/api/predict"
        
        # Use the correct payload format for Gradio API
        payload = {
            "data": [message],
            "fn_index": 0  # Usually the first function is the chat function
        }
        
        headers = {
            "Content-Type": "application/json"
        }
        
        response = requests.post(api_url, json=payload, headers=headers, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            if "data" in result and len(result["data"]) > 0:
                return result["data"][0]
        
        return None
        
    except Exception as e:
        print(f"Direct API call failed: {e}")
        return None

@app.route('/chat', methods=['POST'])
def chat():
    """Handle chat messages and communicate with Hugging Face Space"""
    try:
        data = request.get_json()
        message = data.get('message', '').strip()
        
        if not message:
            return jsonify({'error': 'Message cannot be empty'}), 400
        
        result = None
        
        # Try using gradio_client first
        if client is not None:
            try:
                result = client.predict(
                    message=message,
                    api_name="/chat"
                )
            except Exception as e:
                print(f"Gradio client failed: {e}")
                result = None
        
        # If gradio_client failed, try direct API call
        if result is None:
            print("Trying direct API call...")
            result = call_hf_space_api(message)
        
        # If both methods failed, use mock response for testing
        if result is None:
            print("Using mock response for testing...")
            result = get_mock_response(message)
        
        return jsonify({
            'success': True,
            'response': result,
            'message': message
        })
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to get response from AI. Please try again.'
        }), 500

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({'status': 'healthy'})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
