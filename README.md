🧠 DevGenie

DevGenie is an AI-powered multi-language code explainer, analyzer, and assistant built with Streamlit and Google Gemini Flash 2.5. It intelligently explains, debugs, refactors, optimizes, and reviews the security of code across various programming languages in real time. The app features an intuitive UI and supports code input, file uploads, output translation, and follow-up questions.

Features:

📚 Explain Code – Understand your code line-by-line.

🐛 Debug Code – Identify potential bugs and errors.

🔧 Refactor – Improve readability and structure.

⚡ Optimize – Enhance performance and efficiency.

🔒 Security Review – Detect vulnerabilities and unsafe patterns.

🌍 Multi-language Support – Works with Python, JavaScript, Java, C++, HTML, CSS, PHP.

🌐 Translate Output – Output available in multiple languages (English, Hindi, Spanish, etc.).

📁 File Upload – Upload and analyze .py, .js, .cpp, .html, .css, .php files.

💬 Follow-up Questions – Ask questions about previous analysis sessions.

Installation Instructions:

Make sure Python 3.8 or higher is installed.

Install required packages:

pip install -r requirements.txt

Create a folder named .streamlit in your project directory.

Inside .streamlit, create a file named secrets.toml with the following content:

GEMINI_API_KEY = "your-gemini-api-key-here"

Run the app using:

streamlit run your_app_file.py
(replace your_app_file.py with the actual filename)

Deployment (Render):

Upload your project to GitHub.

Create a new Web Service on https://render.com.

In the "Environment Variables" section, add:

Key: GEMINI_API_KEY

Value: your Gemini API key

Use the start command:
streamlit run your_app_file.py --server.port $PORT
