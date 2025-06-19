import streamlit as st
import google.generativeai as genai
import os
import logging
from pygments.lexers import guess_lexer
from pygments.util import ClassNotFound
from datetime import datetime
import io
import tempfile
import zipfile
from typing import Optional, Tuple
import time
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Hardcoded Gemini API Key
# (Replace with your actual API key)
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]


# Page configuration
st.set_page_config(
    page_title="🧠 DevGenie",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'Get Help': 'https://github.com/your-repo',
        'Report a bug': "https://github.com/your-repo/issues",
        'About': "# AI Code Explainer\nIntelligent code analysis powered by AI"
    }
)

# Custom CSS for professional styling
st.markdown("""
<style>
    .main > div {
        padding-top: 2rem;
    }
    .block-container {
  background-color: #e0e4ea;
}



    .stAlert {
        border-radius: 10px;
        border-left: 4px solid #2563eb;
    }

    .success-alert {
        border-left: 4px solid #059669 !important;
        background-color: #ecfdf5;
    }

    .error-alert {
        border-left: 4px solid #dc2626 !important;
        background-color: #fef2f2;
    }

    .info-alert {
        border-left: 4px solid #2563eb !important;
        background-color: #eff6ff;
    }

    .metric-container {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin: 0.5rem 0;
    }

    .code-container {
        background-color: #1e1e1e;
        border-radius: 10px;
        padding: 1rem;
        margin: 1rem 0;
    }

    .feature-card {
        background: white;
        padding: 1.5rem;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        margin: 1rem 0;
        border-left: 4px solid #2563eb;
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 2px;
    }

    .stTabs [data-baseweb="tab"] {
        height: 50px;
        background-color: #f0f2f6;
        border-radius: 5px 5px 0 0;
        color: #262730;
        font-weight: 500;
    }

    .stTabs [aria-selected="true"] {
        background-color: #2563eb;
        color: white;
    }

    .analysis-header {
        background: linear-gradient(90deg, #2563eb, #7c3aed);
        color: white;
        padding: 1rem;
        border-radius: 10px;
        margin-bottom: 1rem;
        text-align: center;
    }

    .sidebar-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 1rem;
        border-radius: 10px;
        text-align: center;
        margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)

# Configuration
ALLOWED_EXTENSIONS = {'.py', '.js', '.cpp', '.java', '.html', '.css', '.php', }
MAX_FILE_SIZE = 1024 * 1024  # 1MB
MAX_CODE_LENGTH = 50000  # 50K characters


class CodeAnalyzer:
    def __init__(self):
        self.model = None
        self.initialize_gemini()

    def initialize_gemini(self):
        """Initialize Gemini client"""
        try:
            # Configure Gemini with the hardcoded API key
            genai.configure(api_key=GEMINI_API_KEY)

            # Initialize the model (using Gemini Flash 2.5)
            self.model = genai.GenerativeModel('gemini-2.0-flash-exp')

            logger.info("Gemini Flash 2.5 client initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize Gemini client: {e}")
            st.error(f"Gemini initialization failed: {e}")
            return False

    def detect_language(self, code: str) -> str:
        """Detect programming language from code"""
        try:
            lexer = guess_lexer(code)
            language_map = {
                'python': 'python',
                'javascript': 'javascript',
                'c++': 'cpp',
                'java': 'java',
                'html': 'html',
                'css': 'css',
                'php': 'php',

            }
            detected = lexer.name.lower()
            return language_map.get(detected, detected)
        except ClassNotFound:
            logger.warning("Could not detect language, defaulting to python")
            return "python"

    def validate_code_input(self, code: str) -> Tuple[bool, str]:
        """Validate code input"""
        if not code or not code.strip():
            return False, "Code cannot be empty"

        if len(code) > MAX_CODE_LENGTH:
            return False, f"Code is too long. Maximum {MAX_CODE_LENGTH:,} characters allowed."

        # Basic security check
        suspicious_patterns = ['eval(', 'exec(', '__import__', 'subprocess', 'os.system']
        if any(pattern in code.lower() for pattern in suspicious_patterns):
            logger.warning(f"Suspicious code pattern detected")
            st.warning("⚠️ Potentially suspicious code patterns detected. Proceed with caution.")

        return True, "Valid"

    def get_system_prompt(self, lang: str, mode: str) -> str:
        """Generate system prompt based on language and mode"""
        base_prompts = {
            'explain': f"You are an expert {lang} programmer and teacher. Explain code clearly and comprehensively, breaking down complex concepts into understandable parts. Focus on what the code does, how it works, and why it's structured that way. Use markdown formatting for better readability.",
            'refactor': f"You are a senior {lang} developer specializing in code optimization and best practices. Refactor the provided code to improve readability, performance, and maintainability while preserving functionality. Explain your changes using markdown formatting.",
            'debug': f"You are an expert {lang} debugger. Analyze the code for potential bugs, errors, or issues. Provide specific suggestions for fixes and improvements. Use markdown formatting.",
            'optimize': f"You are a {lang} performance optimization expert. Analyze the code for performance improvements, memory usage optimization, and efficiency gains. Provide optimized code with explanations.",
            'security': f"You are a {lang} security expert. Analyze the code for security vulnerabilities, potential exploits, and security best practices. Provide secure alternatives where needed.",
            'followup': f"You are a knowledgeable {lang} programming expert. Answer the specific question about the provided code with accuracy and clarity using markdown formatting."
        }
        return base_prompts.get(mode, base_prompts['explain'])

    def process_code(self, code: str, mode: str, lang: str, translate_to: Optional[str] = None,
                     followup_question: Optional[str] = None) -> str:
        """Process code with Gemini API"""
        try:
            if not self.model:
                return "❌ Error: Gemini client not initialized. Please check your API key."

            # Validate input
            is_valid, error_msg = self.validate_code_input(code)
            if not is_valid:
                return f"❌ Error: {error_msg}"

            # Prepare prompt based on mode
            system_prompt = self.get_system_prompt(lang, mode)

            if mode == "refactor":
                user_prompt = f"Refactor this {lang} code for better readability, performance, and best practices:\n\n```{lang}\n{code}\n```"
            elif mode == "debug":
                user_prompt = f"Debug this {lang} code and identify potential issues:\n\n```{lang}\n{code}\n```"
            elif mode == "optimize":
                user_prompt = f"Optimize this {lang} code for better performance:\n\n```{lang}\n{code}\n```"
            elif mode == "security":
                user_prompt = f"Analyze this {lang} code for security vulnerabilities:\n\n```{lang}\n{code}\n```"
            elif mode == "followup" and followup_question:
                user_prompt = f"Here's the {lang} code:\n\n```{lang}\n{code}\n```\n\nQuestion: {followup_question}"
            else:
                user_prompt = f"Explain this {lang} code step by step, including what it does, how it works, and any important concepts:\n\n```{lang}\n{code}\n```"

            # Add translation request if specified
            if translate_to and translate_to != "none":
                language_names = {
                    'en': 'English',
                    'es': 'Spanish',
                    'hi': 'Hindi',
                    'fr': 'French',
                    'de': 'German',
                    'zh': 'Chinese',
                    'ja': 'Japanese'
                }
                lang_name = language_names.get(translate_to, translate_to)
                user_prompt += f"\n\nPlease provide your response in {lang_name}."

            # Combine system and user prompts for Gemini
            full_prompt = f"{system_prompt}\n\n{user_prompt}"

            # Make API call with updated configuration for Flash 2.5
            with st.spinner("🔄 Analyzing code"):
                response = self.model.generate_content(
                    full_prompt,
                    generation_config=genai.types.GenerationConfig(
                        max_output_tokens=8192,  # Increased for Flash 2.5
                        temperature=0.7,
                        top_p=0.95,
                        top_k=40
                    )
                )

            result = response.text.strip()
            logger.info(f"API call successful - Mode: {mode}, Language: {lang}, Model: Flash 2.5")
            return result

        except Exception as e:
            logger.error(f"Error in process_code: {str(e)}")
            if "quota" in str(e).lower() or "rate limit" in str(e).lower():
                return "❌ Error: API rate limit exceeded. Please try again later."
            elif "api key" in str(e).lower() or "authentication" in str(e).lower():
                return "❌ Error: API authentication failed. Please check your API key."
            elif "safety" in str(e).lower():
                return "❌ Error: Content was blocked by safety filters. Please try with different code."
            else:
                return f"❌ Error: {str(e)}"


def initialize_session_state():
    """Initialize session state variables"""
    if "analyzer" not in st.session_state:
        st.session_state.analyzer = CodeAnalyzer()
    if "analysis_history" not in st.session_state:
        st.session_state.analysis_history = []
    if "code_snippets" not in st.session_state:
        st.session_state.code_snippets = {}


def is_allowed_file(filename: str) -> bool:
    """Check if file extension is allowed"""
    return any(filename.lower().endswith(ext) for ext in ALLOWED_EXTENSIONS)


def main():
    """Main application"""
    initialize_session_state()

    # Header
    st.markdown("""
    <div style="text-align: center; padding: 2rem 0;">
        <h1 style="color: #2563eb; font-size: 3rem; margin-bottom: 0.5rem;">🧠 DevGenie</h1>
        <p style="font-size: 1.2rem; color: #64748b; max-width: 800px; margin: 0 auto;">
            Intelligent code analysis, explanation, and optimization powered by Google Gemini Flash 2.5 AI. 
            Support for multiple programming languages with real-time analysis capabilities.
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Sidebar Configuration
    with st.sidebar:
        st.markdown("""
        <div class="sidebar-header">
            <h2>⚙️ Configuration</h2>
            <p>Customize your analysis preferences</p>
        </div>
        """, unsafe_allow_html=True)

        # API Status

        st.divider()

        # Analysis Configuration
        st.subheader("📊 Analysis Settings")

        analysis_mode = st.selectbox(
            "Analysis Mode",
            ["explain", "refactor", "debug", "optimize", "security"],
            format_func=lambda x: {
                "explain": "📚 Explain Code",
                "refactor": "🔧 Refactor Code",
                "debug": "🐛 Debug Code",
                "optimize": "⚡ Optimize Performance",
                "security": "🔒 Security Analysis"
            }[x]
        )

        language = st.selectbox(
            "Programming Language",
            ["auto", "python", "javascript", "cpp", "java", "html", "css", "php"],
            format_func=lambda x: {
                "auto": "🤖 Auto-Detect",
                "python": "🐍 Python",
                "javascript": "⚡ JavaScript",
                "cpp": "⚙️ C++",
                "java": "☕ Java",
                "html": "🌐 HTML",
                "css": "🎨 CSS",
                "php": "🔷 PHP",

            }[x]
        )

        translation = st.selectbox(
            "Output Language",
            ["none", "en", "es", "hi", "fr", "de", "zh", "ja"],
            format_func=lambda x: {
                "none": "🌍 Original",
                "en": "🇺🇸 English",
                "es": "🇪🇸 Spanish",
                "hi": "🇮🇳 Hindi",
                "fr": "🇫🇷 French",
                "de": "🇩🇪 German",
                "zh": "🇨🇳 Chinese",
                "ja": "🇯🇵 Japanese"
            }[x]
        )

        st.divider()

        # Statistics

    # Main Content Tabs
    tab1, tab2, tab3 = st.tabs(["📝 Code Analysis", "📁 File Upload", "💬 Follow-up Questions"])

    with tab1:
        st.markdown("### Code Input")

        # Code input area
        code_input = st.text_area(
            "Paste your code here:",
            height=300,
            placeholder="# Enter your code here...\nprint('Hello, World!')",
            help="Paste or type your code for analysis"
        )

        # Analysis button (removed example button and column layout)
        analyze_btn = st.button("🚀 Analyze Code", type="primary", use_container_width=True)

        # Perform analysis
        if analyze_btn and code_input.strip():
            # Detect language if auto-detect is selected
            detected_lang = language
            if language == "auto":
                detected_lang = st.session_state.analyzer.detect_language(code_input)

            # Save snippet if requested

            # Perform analysis
            result = st.session_state.analyzer.process_code(
                code_input, analysis_mode, detected_lang, translation
            )

            # Display results
            if not result.startswith("❌"):
                st.markdown("""
                <div class="analysis-header">
                    <h3>💡 Analysis Result</h3>
                    <p>AI-powered code analysis complete</p>
                </div>
                """, unsafe_allow_html=True)

                st.markdown(result)

                # Save to history
                st.session_state.analysis_history.append({
                    "timestamp": datetime.now().isoformat(),
                    "mode": analysis_mode,
                    "language": detected_lang,
                    "code": code_input[:200] + "..." if len(code_input) > 200 else code_input,
                    "result": result
                })

                # Download option
                col1, col2 = st.columns(2)
                with col1:
                    st.download_button(
                        "📥 Download Analysis",
                        data=f"# Code Analysis Report\n\n## Code:\n```{detected_lang}\n{code_input}\n```\n\n## Analysis:\n{result}",
                        file_name=f"analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
                        mime="text/markdown"
                    )
                with col2:
                    if st.button("🔄 Analyze Again"):
                        st.rerun()
            else:
                st.error(result)

        elif analyze_btn:
            st.warning("⚠️ Please enter some code to analyze.")

    with tab2:
        st.markdown("### File Upload")
        st.info("📁 Upload code files for analysis. Supported formats: " + ", ".join(ALLOWED_EXTENSIONS))

        uploaded_files = st.file_uploader(
            "Choose code files",
            accept_multiple_files=True,
            type=list(ext.replace('.', '') for ext in ALLOWED_EXTENSIONS)
        )

        if uploaded_files:
            for uploaded_file in uploaded_files:
                if uploaded_file.size > MAX_FILE_SIZE:
                    st.error(f"❌ File '{uploaded_file.name}' is too large (max {MAX_FILE_SIZE // 1024 // 1024}MB)")
                    continue

                try:
                    file_content = uploaded_file.read().decode('utf-8')

                    with st.expander(f"📄 {uploaded_file.name}", expanded=True):
                        # Display file info
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("File Size", f"{uploaded_file.size:,} bytes")
                        with col2:
                            st.metric("Lines", len(file_content.split('\n')))
                        with col3:
                            detected_lang = st.session_state.analyzer.detect_language(file_content)
                            st.metric("Language", detected_lang.upper())

                        # Show code preview
                        st.code(file_content[:1000] + "..." if len(file_content) > 1000 else file_content,
                                language=detected_lang)

                        # Analysis button for file
                        if st.button(f"🚀 Analyze {uploaded_file.name}", key=f"analyze_{uploaded_file.name}"):
                            result = st.session_state.analyzer.process_code(
                                file_content, analysis_mode, detected_lang, translation
                            )

                            if not result.startswith("❌"):
                                st.success("✅ Analysis complete!")
                                st.markdown(result)

                                # Save to history
                                st.session_state.analysis_history.append({
                                    "timestamp": datetime.now().isoformat(),
                                    "mode": analysis_mode,
                                    "language": detected_lang,
                                    "file": uploaded_file.name,
                                    "code": file_content[:200] + "...",
                                    "result": result
                                })
                            else:
                                st.error(result)

                except UnicodeDecodeError:
                    st.error(
                        f"❌ Could not read '{uploaded_file.name}'. Please ensure it's a text file with UTF-8 encoding.")

    with tab3:
        st.markdown("### Follow-up Questions")

        if not st.session_state.analysis_history:
            st.info("📝 Perform a code analysis first to ask follow-up questions.")
        else:
            # Select previous analysis
            analysis_options = [
                f"{item['timestamp'][:16]} - {item['mode']} ({item.get('language', 'unknown')})"
                for item in reversed(st.session_state.analysis_history[-10:])  # Last 10 analyses
            ]

            selected_analysis = st.selectbox(
                "Select previous analysis:",
                range(len(analysis_options)),
                format_func=lambda x: analysis_options[x]
            )

            if selected_analysis is not None:
                analysis_item = list(reversed(st.session_state.analysis_history[-10:]))[selected_analysis]

                # Show code context
                with st.expander("📋 Code Context", expanded=False):
                    st.code(analysis_item.get('code', 'Code not available'),
                            language=analysis_item.get('language', 'text'))

                # Follow-up question input
                followup_question = st.text_area(
                    "Your question:",
                    placeholder="e.g., How can I optimize this code for better performance?\nWhat are the potential security issues?\nCan you explain the algorithm used?",
                    height=100
                )

                if st.button("💬 Ask Question", type="primary") and followup_question.strip():
                    # Get original code from history or snippets
                    original_code = analysis_item.get('code', '')

                    result = st.session_state.analyzer.process_code(
                        original_code,
                        "followup",
                        analysis_item.get('language', 'python'),
                        translation,
                        followup_question
                    )

                    if not result.startswith("❌"):
                        st.markdown("### 💡 Answer")
                        st.markdown(result)

                        # Save follow-up to history
                        st.session_state.analysis_history.append({
                            "timestamp": datetime.now().isoformat(),
                            "mode": "followup",
                            "language": analysis_item.get('language', 'python'),
                            "question": followup_question,
                            "code": original_code,
                            "result": result
                        })
                    else:
                        st.error(result)


if __name__ == "__main__":
    main()

