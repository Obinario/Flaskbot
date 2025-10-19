from sentence_transformers import SentenceTransformer
import numpy as np
from typing import List, Dict, Tuple
import mysql.connector
from mysql.connector import Error
import re

class AIChatbot:
    def __init__(self, db_config: Dict[str, str]):
        self.db_config = db_config
        # Load the pre-trained model (can use a smaller model for more speed)
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        # Warm up the model to avoid first-request slowness
        _ = self.model.encode(["Hello, world!"])
        self.faq_embeddings = None
        self.faqs = None
        self.load_faqs()
    
    def get_db_connection(self):
        try:
            connection = mysql.connector.connect(**self.db_config)
            return connection
        except Error as e:
            print(f"Error connecting to database: {e}")
            return None
    
    def load_faqs(self):
        """Load active FAQs from database and compute their normalized embeddings"""
        connection = self.get_db_connection()
        if connection:
            try:
                cursor = connection.cursor(dictionary=True)
                cursor.execute("SELECT id, question, answer FROM faqs WHERE is_active = 1 ORDER BY sort_order, id")
                self.faqs = cursor.fetchall()
                cursor.close()
                
                if self.faqs:
                    # Compute and normalize embeddings for all questions
                    questions = [faq['question'] for faq in self.faqs]
                    embeddings = self.model.encode(questions, normalize_embeddings=True)
                    self.faq_embeddings = np.array(embeddings)
            except Error as e:
                print(f"Error loading FAQs: {e}")
            finally:
                connection.close()
    
    def save_unanswered_question(self, question):
        print(f"Saving unanswered question: {question}")  # Debug print
        try:
            connection = self.get_db_connection()
            if connection:
                cursor = connection.cursor()
                query = "INSERT INTO unanswered_questions (question) VALUES (%s)"
                cursor.execute(query, (question,))
                connection.commit()
                cursor.close()
                connection.close()
        except Error as e:
            print(f"Error saving unanswered question: {e}")

    def _tokenize(self, text: str):
        if not text:
            return []
        return [t for t in re.findall(r"[a-z0-9]+", text.lower()) if len(t) > 2]

    def _overlap_ratio(self, q_tokens, faq_tokens):
        if not q_tokens or not faq_tokens:
            return 0.0
        q_set = set(q_tokens)
        f_set = set(faq_tokens)
        inter = len(q_set & f_set)
        denom = max(len(q_set), 1)
        return inter / denom

    def _wh_class(self, text: str) -> str:
        if not text:
            return ''
        s = text.strip().lower()
        # simple heuristic classification by leading wh-word
        for key in ['who', 'where', 'when', 'what', 'how', 'why', 'which']:
            if s.startswith(key + ' ') or s.startswith(key + "?"):
                return key
        # also check presence if not leading
        for key in ['who', 'where', 'when', 'what', 'how', 'why', 'which']:
            if f' {key} ' in f' {s} ':
                return key
        return ''

    def find_best_match(self, question: str, threshold: float = 0.7) -> Tuple[str, float]:
        print(f"find_best_match called with: {question}")  # Debug print
        if not self.faqs or self.faq_embeddings is None:
            return "I'm sorry, I couldn't find any FAQs in the database.", 0.0

        # Compute and normalize embedding for the input question
        question_embedding = self.model.encode([question], normalize_embeddings=True)[0]
        similarities = np.dot(self.faq_embeddings, question_embedding)

        # Compute keyword overlap with each FAQ question
        q_tokens = self._tokenize(question)
        overlap_scores = []
        for faq in self.faqs:
            overlap_scores.append(self._overlap_ratio(q_tokens, self._tokenize(faq['question'])))

        similarities = np.array(similarities)
        overlap_scores = np.array(overlap_scores)

        # Combined score to reduce false positives
        combined = 0.7 * similarities + 0.3 * overlap_scores
        
        # Apply WH-word intent consistency penalty
        q_wh = self._wh_class(question)
        if q_wh:
            for i, faq in enumerate(self.faqs):
                f_wh = self._wh_class(faq['question'])
                if f_wh and f_wh != q_wh:
                    combined[i] *= 0.6  # penalize mismatched intent significantly
        best_idx = int(np.argmax(combined))
        best_semantic = float(similarities[best_idx])
        best_overlap = float(overlap_scores[best_idx])
        best_combined = float(combined[best_idx])
        best_wh = self._wh_class(self.faqs[best_idx]['question'])

        # Acceptance criteria: require good semantic OR strong combined with overlap
        accept = (
            best_semantic >= max(0.7, threshold)
            or (best_combined >= threshold and best_overlap >= 0.3)
        )
        # Enforce WH intent match when present
        if accept and q_wh and best_wh and q_wh != best_wh:
            accept = False

        if accept:
            return self.faqs[best_idx]['answer'], best_combined
        else:
            # Log as unanswered so admins can curate (ignore errors)
            try:
                self.save_unanswered_question(question)
            except Exception:
                pass
            fallback = (
                "Sorry, I don’t have the knowledge to answer that yet.\n"
                "I’ll notify an admin about your question and we’ll add the answer soon.\n"
                "Please come back in a while."
            )
            return (fallback, best_combined)
    
    def get_suggested_questions(self, question: str, num_suggestions: int = 3) -> List[str]:
        """Get suggested questions based on the input question"""
        if not self.faqs or self.faq_embeddings is None:
            return []
        
        # Compute and normalize embedding for the input question
        question_embedding = self.model.encode([question], normalize_embeddings=True)[0]
        
        # Calculate cosine similarity
        similarities = np.dot(self.faq_embeddings, question_embedding)
        
        # Get top N similar questions
        top_indices = np.argsort(similarities)[-num_suggestions:][::-1]
        return [self.faqs[idx]['question'] for idx in top_indices if similarities[idx] > 0.3]
    
    def add_faq(self, question: str, answer: str) -> bool:
        """Add a new FAQ to the database"""
        connection = self.get_db_connection()
        if connection:
            try:
                cursor = connection.cursor()
                query = "INSERT INTO faqs (question, answer) VALUES (%s, %s)"
                cursor.execute(query, (question, answer))
                connection.commit()
                cursor.close()
                
                # Reload FAQs to update embeddings
                self.load_faqs()
                return True
            except Error as e:
                print(f"Error adding FAQ: {e}")
                return False
            finally:
                connection.close()
        return False 