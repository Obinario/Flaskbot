import os
# Suppress TensorFlow oneDNN messages
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'
# Suppress TensorFlow warnings
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_cors import CORS
import pandas as pd
from database_recommender import DatabaseCourseRecommender
from ai_chatbot import AIChatbot
import mysql.connector
from mysql.connector import Error
import warnings
import logging

# Suppress specific warnings
warnings.filterwarnings('ignore', category=FutureWarning)
warnings.filterwarnings('ignore', category=UserWarning)
warnings.filterwarnings('ignore', message='.*tf.losses.sparse_softmax_cross_entropy.*')
warnings.filterwarnings('ignore', message='.*deprecated.*')

# Suppress TensorFlow logging
logging.getLogger('tensorflow').setLevel(logging.ERROR)
logging.getLogger('tf_keras').setLevel(logging.ERROR)

# More aggressive TensorFlow warning suppression
try:
    import tensorflow as tf
    tf.get_logger().setLevel('ERROR')
except ImportError:
    pass

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": ["http://localhost", "http://127.0.0.1"], "supports_credentials": True}})
app.secret_key = 'your-secret-key'  # Required for flash messages

# Database configuration
db_config = {
    'host': os.environ.get('DB_HOST', 'localhost'),
    'user': os.environ.get('DB_USER', 'root'),
    'password': os.environ.get('DB_PASSWORD', ''),
    'database': os.environ.get('DB_NAME', 'psau_admission')
}

# Initialize the recommender and chatbot with error handling
try:
    recommender = DatabaseCourseRecommender()
    print("✅ Recommender initialized successfully")
except Exception as e:
    print(f"⚠️  Warning: Could not initialize recommender: {e}")
    recommender = None

try:
    chatbot = AIChatbot(db_config)
    print("✅ Chatbot initialized successfully")
except Exception as e:
    print(f"⚠️  Warning: Could not initialize chatbot: {e}")
    chatbot = None

def get_db_connection():
    try:
        connection = mysql.connector.connect(**db_config)
        return connection
    except Error as e:
        print(f"❌ Error connecting to database: {e}")
        return None

def get_faqs_from_db():
    """Fetch FAQs from database with proper error handling"""
    connection = get_db_connection()
    faqs = []
    
    if connection:
        try:
            cursor = connection.cursor(dictionary=True)
            # Updated query to match the actual table structure
            cursor.execute("SELECT id, question, answer FROM faqs WHERE is_active = 1 ORDER BY sort_order, id")
            faqs = cursor.fetchall()
            cursor.close()
            print(f"✅ Successfully fetched {len(faqs)} FAQs from database")
        except Error as e:
            print(f"❌ Error fetching FAQs: {e}")
        finally:
            connection.close()
    else:
        print("❌ Could not connect to database")
    
    return faqs

@app.route('/health', methods=['GET'])
def health():
    """Basic health endpoint to verify the Flask app is running"""
    return jsonify({
        'status': 'ok',
        'service': 'psau-ai',
        'endpoints': ['/faqs', '/ask_question', '/api/recommend', '/api/save_ratings', '/db_check']
    })

@app.route('/db_check', methods=['GET'])
def db_check():
    """Check database connectivity and basic table counts"""
    try:
        connection = get_db_connection()
        if not connection:
            return jsonify({'ok': False, 'error': 'cannot connect to database'}), 500
        cursor = connection.cursor()
        cursor.execute('SELECT COUNT(*) FROM faqs')
        faqs_count = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM courses')
        courses_count = cursor.fetchone()[0]
        cursor.close()
        connection.close()
        return jsonify({'ok': True, 'faqs': faqs_count, 'courses': courses_count})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/recommender')
def recommender_page():
    return render_template('recommender.html')

@app.route('/chatbot')
def chatbot_page():
    # Fetch FAQs from database
    faqs = get_faqs_from_db()
    return render_template('chatbot.html', faqs=faqs)

@app.route('/faqs', methods=['GET'])
def faqs_api():
    faqs = get_faqs_from_db()
    return jsonify({
        'faqs': faqs
    })

@app.route('/ask_question', methods=['POST'])
def ask_question():
    if chatbot is None:
        return jsonify({
            'answer': 'Sorry, the AI chatbot is not available at the moment. Please try again later.',
            'confidence': 0.0,
            'suggested_questions': []
        })
    
    data = request.get_json()
    question = data.get('question', '')
    
    if not question.strip():
        return jsonify({
            'answer': 'Please enter a question.',
            'confidence': 0.0,
            'suggested_questions': []
        })
    
    # Get answer using AI chatbot
    answer, confidence = chatbot.find_best_match(question)
    
    # Get suggested questions
    suggested_questions = chatbot.get_suggested_questions(question)
    
    return jsonify({
        'answer': answer,
        'confidence': float(confidence),
        'suggested_questions': suggested_questions
    })

@app.route('/recommend', methods=['POST'])
def recommend():
    if recommender is None:
        flash('The recommendation system is not available at the moment. Please try again later.', 'error')
        return redirect(url_for('recommender_page'))
    
    try:
        # Get form data
        stanine = int(request.form['stanine'])
        gwa = float(request.form['gwa'])
        strand = request.form['strand']
        hobbies = request.form.get('hobbies', '').strip()
        
        # Validate inputs
        if not (1 <= stanine <= 9):
            flash('Stanine score must be between 1 and 9', 'error')
            return redirect(url_for('recommender_page'))
        
        if not (75 <= gwa <= 100):
            flash('GWA must be between 75 and 100', 'error')
            return redirect(url_for('recommender_page'))
        
        if not strand:
            flash('Please select a strand', 'error')
            return redirect(url_for('recommender_page'))
        
        if not hobbies:
            flash('Please enter your hobbies/interests. This field is required for better recommendations.', 'error')
            return redirect(url_for('recommender_page'))
        
        # Get recommendations (only pass hobbies as extra context)
        recommendations = recommender.recommend_courses(
            stanine=stanine,
            gwa=gwa,
            strand=strand,
            hobbies=hobbies
        )
        
        return render_template('recommendations.html',
                             recommendations=recommendations,
                             stanine=stanine,
                             gwa=gwa,
                             strand=strand,
                             hobbies=hobbies)
    
    except Exception as e:
        flash(f'An error occurred: {str(e)}', 'error')
        return redirect(url_for('recommender_page'))

@app.route('/api/recommend', methods=['POST'])
def api_recommend():
    if recommender is None:
        return jsonify({'error': 'Recommender unavailable'}), 503
    try:
        data = request.get_json(force=True) or {}
        stanine = int(data.get('stanine'))
        gwa = float(data.get('gwa'))
        strand = str(data.get('strand') or '').strip()
        hobbies = str(data.get('hobbies') or '').strip()
        if not (1 <= stanine <= 9):
            return jsonify({'error': 'stanine must be between 1 and 9'}), 400
        if not (75 <= gwa <= 100):
            return jsonify({'error': 'gwa must be between 75 and 100'}), 400
        if not strand:
            return jsonify({'error': 'strand is required'}), 400
        if not hobbies:
            return jsonify({'error': 'hobbies is required'}), 400
        recs = recommender.recommend_courses(stanine=stanine, gwa=gwa, strand=strand, hobbies=hobbies)
        return jsonify({'recommendations': recs})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/save_ratings', methods=['POST'])
def api_save_ratings():
    if recommender is None:
        return jsonify({'error': 'Recommender unavailable'}), 503
    try:
        data = request.get_json(force=True) or {}
        stanine = int(data.get('stanine'))
        gwa = float(data.get('gwa'))
        strand = str(data.get('strand') or '').strip()
        hobbies = str(data.get('hobbies') or '').strip() or None
        ratings = data.get('ratings') or {}
        if not isinstance(ratings, dict):
            return jsonify({'error': 'ratings must be an object'}), 400
        saved = 0
        for course, rating in ratings.items():
            ok = recommender.save_student_data(stanine=stanine, gwa=gwa, strand=strand, course=course, rating=rating, hobbies=hobbies)
            if ok:
                saved += 1
        # retrain after feedback
        try:
            recommender.train_model()
        except Exception:
            pass
        return jsonify({'saved': saved})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/save_ratings', methods=['POST'])
def save_ratings():
    if recommender is None:
        flash('The recommendation system is not available at the moment. Please try again later.', 'error')
        return redirect(url_for('recommender_page'))
    
    try:
        # Get form data
        stanine = int(request.form['stanine'])
        gwa = float(request.form['gwa'])
        strand = request.form['strand']
        hobbies = request.form.get('hobbies', '').strip()
        
        # Get ratings
        ratings = {}
        for key, value in request.form.items():
            if key.startswith('rating_'):
                course = key.replace('rating_', '')
                if value != 'skip':  # Only save non-skip ratings
                    ratings[course] = value
        
        if ratings:  # Only save if there are actual ratings
            # Save each rating to database
            for course, rating in ratings.items():
                success = recommender.save_student_data(
                    stanine=stanine,
                    gwa=gwa,
                    strand=strand,
                    course=course,
                    rating=rating,
                    hobbies=hobbies if hobbies else None
                )
                if not success:
                    flash(f'Error saving rating for {course}', 'error')
                    continue
            
            # Retrain the model with new data
            recommender.train_model()
            
            flash('Thank you for your feedback! Your ratings have been saved.', 'success')
        else:
            flash('No feedback was provided. You can try again later.', 'info')
            
        return redirect(url_for('recommender_page'))
    
    except Exception as e:
        flash(f'An error occurred while saving ratings: {str(e)}', 'error')
        return redirect(url_for('recommender_page'))

if __name__ == '__main__':
    print("🚀 Starting PSAU Admission System...")
    print("📊 Database status:")
    
    # Test database connection
    faqs = get_faqs_from_db()
    if faqs:
        print(f"   ✅ FAQs loaded: {len(faqs)} questions available")
    else:
        print("   ⚠️  No FAQs loaded - chatbot will have limited functionality")
    
    # Get port from environment variable (for Render)
    port = int(os.environ.get('PORT', 5000))
    debug_mode = os.environ.get('FLASK_ENV') == 'development'
    
    print(f"🌐 Access the application at: http://localhost:{port}")
    app.run(debug=debug_mode, host='0.0.0.0', port=port) 
