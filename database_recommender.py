import pandas as pd
import numpy as np
from sklearn.neighbors import KNeighborsClassifier
from sklearn.preprocessing import LabelEncoder, StandardScaler
import joblib
import mysql.connector
from mysql.connector import Error
import json

class DatabaseCourseRecommender:
    def __init__(self):
        self.model = None
        self.label_encoders = {}
        self.scaler = StandardScaler()
        self.db_config = {
            'host': 'localhost',
            'user': 'root',
            'password': '',
            'database': 'psau_admission'
        }
        self.train_model()
    
    def get_db_connection(self):
        try:
            connection = mysql.connector.connect(**self.db_config)
            return connection
        except Error as e:
            print(f"Error connecting to database: {e}")
            return None

    def save_student_data(self, stanine, gwa, strand, course, rating, hobbies=None):
        """Save student feedback by incrementing count for the same (course, stanine, gwa, strand, rating).
        Uses INSERT ... ON DUPLICATE KEY UPDATE to avoid duplicate rows and prevent DB overflow.
        """
        try:
            connection = self.get_db_connection()
            if connection:
                cursor = connection.cursor()
                # Rely on unique index (course, stanine, gwa, strand, rating)
                insert_upsert_query = """
                    INSERT INTO student_feedback_counts (course, stanine, gwa, strand, rating, hobbies, count)
                    VALUES (%s, %s, %s, %s, %s, %s, 1)
                    ON DUPLICATE KEY UPDATE
                        count = count + 1,
                        hobbies = VALUES(hobbies)
                """
                cursor.execute(insert_upsert_query, (course, stanine, gwa, strand, rating, hobbies))
                connection.commit()
                cursor.close()
                connection.close()
                return True
        except Error as e:
            print(f"Error saving student feedback: {e}")
            return False

    def get_courses_from_db(self):
        """Fetch available courses from the database"""
        try:
            connection = self.get_db_connection()
            if connection:
                cursor = connection.cursor()
                query = "SELECT course_code, course_name FROM courses"
                cursor.execute(query)
                courses = cursor.fetchall()
                cursor.close()
                connection.close()
                return {code: name for code, name in courses}
        except Error as e:
            print(f"Error fetching courses: {e}")
            return {}

    def get_training_data(self):
        """Fetch training data from the student_feedback_counts table"""
        try:
            connection = self.get_db_connection()
            if connection:
                cursor = connection.cursor()
                query = """
                    SELECT stanine, gwa, strand, course, rating, hobbies, count
                    FROM student_feedback_counts
                """
                cursor.execute(query)
                data = cursor.fetchall()
                cursor.close()
                connection.close()
                # Repeat rows according to count for compatibility with training
                rows = []
                for row in data:
                    stanine, gwa, strand, course, rating, hobbies, count = row
                    for _ in range(count):
                        rows.append((stanine, gwa, strand, course, rating, hobbies))
                return pd.DataFrame(rows, columns=['stanine', 'gwa', 'strand', 'course', 'rating', 'hobbies'])
        except Error as e:
            print(f"Error fetching training data: {e}")
            return pd.DataFrame()

    def train_model(self):
        """Train the recommendation model using the training data"""
        try:
            training_data = self.get_training_data()
            
            if training_data.empty:
                print("No training data available - using default recommendations")
                return
            
            # Prepare features (hobbies required)
            feature_columns = ['stanine', 'gwa', 'strand', 'hobbies']
            
            # Create feature matrix
            X = training_data[feature_columns].copy()
            y = training_data['course']
            
            # Handle categorical variables
            categorical_columns = ['strand', 'hobbies']
            
            # Refit encoders every training to incorporate new categories
            for col in categorical_columns:
                if col in X.columns:
                    X[col] = X[col].fillna('unknown')
                    self.label_encoders[col] = LabelEncoder()
                    X[col] = self.label_encoders[col].fit_transform(X[col])
            
            # Scale numerical features
            numerical_columns = ['stanine', 'gwa']
            if not X[numerical_columns].empty:
                X[numerical_columns] = self.scaler.fit_transform(X[numerical_columns])
            
            # Train KNN model
            self.model = KNeighborsClassifier(n_neighbors=3, weights='distance')
            self.model.fit(X, y)
            
            print("✅ Model trained successfully (hobbies required and encoded)")
            
        except Exception as e:
            print(f"Error training model: {e}")
            self.model = None

    def get_default_recommendations(self, stanine, gwa, strand):
        """Provide default recommendations based on basic rules when no training data is available"""
        courses = self.get_courses_from_db()
        recommendations = []
        
        # Basic rules for recommendations
        if strand == 'STEM':
            if stanine >= 8 and gwa >= 90:
                priority_courses = ['BSCS', 'BSIT']
            else:
                priority_courses = ['BSIT', 'BSCS']
        elif strand == 'ABM':
            priority_courses = ['BSBA']
        elif strand == 'HUMSS':
            priority_courses = ['BSED']
        else:
            priority_courses = list(courses.keys())
        
        # Add courses with default probabilities
        for i, course in enumerate(priority_courses[:2]):  # Only take top 2
            if course in courses:
                recommendations.append({
                    'code': course,
                    'name': courses[course],
                    'probability': 1.0 - (i * 0.2)  # Decreasing probability for each course
                })
        
        return recommendations

    def recommend_courses(self, stanine, gwa, strand, hobbies=None, top_n=5):
        """Recommend courses based on student profile (hobbies required)"""
        try:
            if self.model is None:
                return self.get_default_recommendations(stanine, gwa, strand)
            
            # Prepare input features
            input_data = pd.DataFrame([{
                'stanine': stanine,
                'gwa': gwa,
                'strand': strand,
                'hobbies': (hobbies or '').strip()
            }])
            # Validate hobbies
            if not input_data['hobbies'].iloc[0]:
                raise ValueError('hobbies is required for recommendations')
            
            # Encode categorical variables
            for col in ['strand', 'hobbies']:
                if col in input_data.columns and col in self.label_encoders:
                    value = input_data[col].iloc[0]
                    if value not in self.label_encoders[col].classes_:
                        # Extend encoder classes to include unseen value at inference
                        self.label_encoders[col].classes_ = np.append(self.label_encoders[col].classes_, value)
                    input_data[col] = self.label_encoders[col].transform(input_data[col])
            
            # Scale numerical features
            numerical_columns = ['stanine', 'gwa']
            if not input_data[numerical_columns].empty:
                input_data[numerical_columns] = self.scaler.transform(input_data[numerical_columns])
            
            # Get predictions
            predictions = self.model.predict_proba(input_data)
            courses = self.model.classes_
            
            # Get top recommendations
            top_indices = np.argsort(predictions[0])[-top_n:][::-1]
            recommendations = []
            
            course_map = self.get_courses_from_db()
            for idx in top_indices:
                code = courses[idx]
                confidence = predictions[0][idx]
                recommendations.append({
                    'code': code,
                    'name': course_map.get(code, code),
                    'rating': round(confidence * 100, 1)
                })
            
            return recommendations
            
        except Exception as e:
            print(f"Error recommending courses: {e}")
            return self.get_default_recommendations(stanine, gwa, strand)

    def _get_recommendation_reason(self, course, stanine, gwa, strand, hobbies, interests, personality_type, learning_style, career_goals):
        """Generate personalized reason for recommendation"""
        reasons = []
        
        # Academic performance reasons
        if stanine >= 8:
            reasons.append("Excellent academic performance")
        elif stanine >= 6:
            reasons.append("Good academic foundation")
        
        if gwa >= 85:
            reasons.append("High academic achievement")
        elif gwa >= 80:
            reasons.append("Strong academic record")
        
        # Strand alignment
        if strand == "STEM" and course in ["BSCS", "BSIT", "BSArch", "BSIE", "BSN"]:
            reasons.append("Perfect match with your STEM background")
        elif strand == "ABM" and course in ["BSBA", "BSA"]:
            reasons.append("Excellent alignment with your ABM strand")
        elif strand == "HUMSS" and course in ["BSED", "BSPsych"]:
            reasons.append("Great fit with your HUMSS background")
        
        # Hobbies and interests alignment
        if hobbies and any(hobby in hobbies.lower() for hobby in ["gaming", "programming", "technology", "computers"]):
            if course in ["BSCS", "BSIT"]:
                reasons.append("Matches your technology interests")
        
        if hobbies and any(hobby in hobbies.lower() for hobby in ["business", "leadership", "management"]):
            if course in ["BSBA", "BSA"]:
                reasons.append("Aligns with your business interests")
        
        if hobbies and any(hobby in hobbies.lower() for hobby in ["helping", "teaching", "caring"]):
            if course in ["BSED", "BSN", "BSPsych"]:
                reasons.append("Perfect for your helping nature")
        
        # Personality type alignment
        if personality_type == "introvert" and course in ["BSCS", "BSA", "BSArch"]:
            reasons.append("Suits your introverted personality")
        elif personality_type == "extrovert" and course in ["BSBA", "BSED", "BSHM"]:
            reasons.append("Great for your outgoing personality")
        
        # Learning style alignment
        if learning_style == "hands-on" and course in ["BSIT", "BSHM", "BSAgri"]:
            reasons.append("Matches your hands-on learning preference")
        elif learning_style == "visual" and course in ["BSArch", "BSCS"]:
            reasons.append("Perfect for your visual learning style")
        
        # Career goals alignment
        if career_goals and any(goal in career_goals.lower() for goal in ["developer", "programmer", "software"]):
            if course in ["BSCS", "BSIT"]:
                reasons.append("Direct path to your career goals")
        
        if career_goals and any(goal in career_goals.lower() for goal in ["business", "entrepreneur", "manager"]):
            if course in ["BSBA", "BSA"]:
                reasons.append("Direct path to your business goals")
        
        # Default reason if no specific matches
        if not reasons:
            reasons.append("Good academic and personal fit")
        
        return " • ".join(reasons[:3])  # Limit to top 3 reasons

    def save_model(self, model_path='course_recommender_model.joblib'):
        """Save the trained model"""
        if self.model is None:
            raise Exception("No model to save!")
            
        model_data = {
            'model': self.model,
            'scaler': self.scaler,
            'label_encoders': self.label_encoders
        }
        joblib.dump(model_data, model_path)
    
    def load_model(self, model_path='course_recommender_model.joblib'):
        """Load a trained model"""
        model_data = joblib.load(model_path)
        self.model = model_data['model']
        self.scaler = model_data['scaler']
        self.label_encoders = model_data['label_encoders']

# Example usage
if __name__ == "__main__":
    recommender = DatabaseCourseRecommender()
    
    # Example recommendation
    recommendations = recommender.recommend_courses(
        stanine=8,
        gwa=1.3,
        strand='STEM'
    )
    print("Recommended courses:", json.dumps(recommendations, indent=2)) 