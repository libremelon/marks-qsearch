# Marks QSearch

A Python-based **Question Search App** built with **PyQt6** for UI and **asyncio** for efficient asynchronous querying. This project retrieves and displays matching questions from the GetMarks API.
<img src="https://github.com/user-attachments/assets/35a505c4-d559-452b-852e-e0c40accceb4">

## Features
- **Subject Selection:** Choose from Physics, Chemistry, and Maths (Mains/Advanced).
- **Keyword-Based Search:** Find questions using keywords.
- **Asynchronous Fetching:** Uses `asyncio` and `aiohttp` for efficient querying.
- **Cache Management:** Automatic cache backup and restoration.
- **GUI with PyQt6:** Intuitive interface for easy search.

## Installation

### Prerequisites
- Python 3.x
- `pip` package manager

### Steps
1. **Clone the Repository**
   ```sh
   git clone https://github.com/libremelon/marks-qsearch.git
   cd marks-qsearch
   ```

2. **Create & Activate Virtual Environment**
   ```sh
   python -m venv venv
   source venv/bin/activate  # macOS/Linux
   venv\Scripts\activate     # Windows
   ```

3. **Install Dependencies**
   ```sh
   pip install -r requirements.txt
   ```

4. **Set Up Environment Variables**
   Create a `.env` file and add:
   ```sh
   MARKS_APP_API_KEY=your_api_key_here
   ```

## Usage
Run the application:
```sh
python main.py
```

## Project Structure
```plaintext
question-search-app/
│── data/                  # Stores cache & matching questions
│── main.py                # GUI application
│── logic.py               # Backend logic and API requests
│── requirements.txt       # Python dependencies
│── .env                   # API key storage
│── README.md              # Project documentation
```

## Dependencies
- `PyQt6` - GUI framework
- `asyncio` - Asynchronous processing
- `aiohttp` - API requests
- `aiofiles` - Async file operations
- `dotenv` - Environment variable management
- `fasteners` - File locking
