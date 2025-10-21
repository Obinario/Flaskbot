from flask import Flask, render_template, request, jsonify
from gradio_client import Client
import mysql.connector
import os
import sys

# Fix Unicode encoding issues on Windows
if sys.platform.startswith('win'):
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.detach())
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.detach())

app = Flask(__name__)

# Initialize the Gradio client
try:
    client = Client("markobinario/flaskbot")
    print("✅ Gradio client initialized successfully")
except Exception as e:
    print(f"❌ Error initializing Gradio client: {e}")
    client = None


# === 🔹 Database connection helper ===
def get_db_connection():
    """Connect to MySQL database"""
    try:
        conn = mysql.connector.connect(
            host="shuttle.proxy.rlwy.net",       
            user="root",                         
            password="JCfNOSYEIrgNDqxwzaHBEufEJDPLQkKU",  
            database="railway",                  
            port=40148,                           
            ssl_disabled=True  
        )
        return conn
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return None


def get_answer_from_db(question):
    """Check if the question exists in the database"""
    conn = get_db_connection()
    if not conn:
        return None
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT answer FROM faqs WHERE question LIKE %s LIMIT 1", (f"%{question}%",))
    result = cursor.fetchone()
    conn.close()
    return result["answer"] if result else None


@app.route('/')
def home():
    return render_template('home.html')


@app.route('/chatbot')
def chatbot():
    return render_template('chatbot.html')


@app.route('/recommendations')
def recommendations():
    return render_template('recommendations.html')


# === 🔹 Modified /chat route ===
@app.route('/chat', methods=['POST'])
def chat():
    """Handle chat messages and return bot responses"""
    try:
        data = request.get_json()
        message = data.get('message', '').strip()
        if not message:
            return jsonify({'error': 'No message provided'}), 400

        # 1️⃣ Check database first
        db_answer = get_answer_from_db(message)
        if db_answer:
            print(f"📚 Found in database: {db_answer}")
            return jsonify({
                'response': db_answer,
                'source': 'database',
                'status': 'success'
            })

        # 2️⃣ If not found, call Hugging Face API
        if client is None:
            return jsonify({
                'error': 'Gradio client not initialized',
                'status': 'error'
            }), 500

        ai_answer = client.predict(message=message, api_name="/chat")
        print(f"🤖 Hugging Face AI response: {ai_answer}")

        return jsonify({
            'response': ai_answer,
            'source': 'huggingface',
            'status': 'success'
        })

    except Exception as e:
        print(f"❌ Error in /chat: {str(e)}")
        return jsonify({'error': str(e), 'status': 'error'}), 500


@app.route('/health')
def health():
    return jsonify({'status': 'healthy'})


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
