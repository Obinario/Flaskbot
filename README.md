# AI Chatbot with Flask and Gradio

A modern web-based chatbot application that integrates with the Gradio API to provide AI-powered conversations.

## Features

- 🎨 Modern, responsive chat interface
- 🤖 Integration with Gradio API (markobinario/flaskbot)
- 💬 Real-time messaging with typing indicators
- 📱 Mobile-friendly design
- ⚡ Fast and lightweight Flask backend

## Setup Instructions

### 1. Install Python Dependencies

First, make sure you have Python installed on your system. Then install the required packages:

```bash
pip install -r requirements.txt
```

### 2. Run the Application

Start the Flask development server:

```bash
python app.py
```

The application will be available at `http://localhost:5000`

### 3. Access the Chatbot

Open your web browser and navigate to `http://localhost:5000` to start chatting with the AI bot.

## Project Structure

```
├── app.py                 # Main Flask application
├── requirements.txt       # Python dependencies
├── README.md             # This file
└── templates/
    └── index.html        # Chat interface template
```

## API Endpoints

- `GET /` - Main chat interface
- `POST /chat` - Send message to chatbot
- `GET /health` - Health check endpoint

## Configuration

The chatbot is configured to use the `markobinario/flaskbot` Gradio space. You can modify the client initialization in `app.py` if you want to use a different model.

## Troubleshooting

1. **Connection Issues**: Make sure you have a stable internet connection as the app connects to the Gradio API.

2. **Module Not Found**: Ensure all dependencies are installed using `pip install -r requirements.txt`

3. **Port Already in Use**: If port 5000 is busy, modify the port in `app.py` or stop the conflicting service.

## License

This project is open source and available under the MIT License.
