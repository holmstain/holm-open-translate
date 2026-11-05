Holm JSON Translator Pro

A lightweight, secure, and parallel multi-language JSON translation application built with Python, Flask, and the NVIDIA NIM API.

Features

Multi-File Processing: Upload multiple JSON files simultaneously.

Parallel Translation: Uses recursive structure traversal to translate string values while preserving keys, formatting, and variables (e.g., {name}, %s).

Session-Based Security Isolation: Ensures translation history and output archives are scoped per user session.

Automated ZIP Export: Downloads formatted translated files as a consolidated ZIP package named with target language tags (e.g., filename_tr.json).

Comprehensive Unit Tests: Built-in test suite to verify API connectivity, structure integrity, variable retention, and multi-tenant security isolation.

Project Structure

holm-translate/
├── app.py
├── test_translator.py
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md


Setup Instructions

1. Prerequisites

Ensure Python 3.10 or higher is installed along with python3-venv.

2. Virtual Environment Setup

python3 -m venv venv
source venv/bin/activate


3. Dependency Installation

pip install -r requirements.txt


4. Configuration

Copy .env.example to .env and supply your API key:

cp .env.example .env


Edit .env:

NVIDIA_API_KEY=your_nvidia_nim_api_key_here


5. Running the Application

python app.py


Access the interface at http://localhost:5000.

Running Tests

Execute the automated test suite:

python -m unittest test_translator.py


Or using pytest:

pytest test_translator.py -v


License

MIT License.