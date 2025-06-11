import traceback
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QLabel, QComboBox, QLineEdit, QPushButton, QTextBrowser, QProgressBar, QMessageBox, QWidget
from PyQt6.QtCore import QThread, pyqtSignal, QTimer
from logic import load_cache_with_fallback, save_cache_with_backup, search_questions
import os
import sys
import shutil
import asyncio

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

CACHE_FILE = "data/cache.json"
BACKUP_FILE = "data/cache.bak"
MATCHING_QUESTIONS_FOLDER = "data/matching_questions"

SUBJECTS = {
    "Physics (Mains)": "615f0c729476412f48314dab",
    "Chemistry (Mains)": "615f0cf69476412f48314dac",
    "Maths (Mains)": "615f0d109476412f48314dad",
    "Physics (Advanced)": "616056cd0283de43c87e3e15",
    "Chemistry (Advanced)": "616057040283de43c87e3e16",
    "Maths (Advanced)": "6160570c0283de43c87e3e17"
}

CACHE_KEYS = {
    "Physics (Mains)": "chapters_Physics",
    "Chemistry (Mains)": "chapters_Chemistry",
    "Maths (Mains)": "chapters_Maths",
    "Physics (Advanced)": "chapters_Physics_Advanced",
    "Chemistry (Advanced)": "chapters_Chemistry_Advanced",
    "Maths (Advanced)": "chapters_Maths_Advanced"
}

class SearchThread(QThread):
    progress_signal = pyqtSignal(int)
    results_signal = pyqtSignal(str)

    def __init__(self, subject_id, cache_key, keywords, cache):
        super().__init__()
        self.subject_id = subject_id
        self.cache_key = cache_key
        self.keywords = keywords
        self.cache = cache

    def run(self):
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Initialize the global question counter
            global_counter = 1
            
            results = loop.run_until_complete(search_questions(
                self.subject_id, self.keywords, self.cache, self.cache_key,
                progress_callback=lambda increment: self.progress_signal.emit(increment)
            ))
            
            results_html = ""
            for result in results:
                question_id = result.get("data", {}).get("_id", "")
                question_text = result.get("data", {}).get("question", {}).get("text", "")
                
                # Extracting the year from `previousYearPapers`
                previous_year_papers = result.get("data", {}).get("previousYearPapers", [])
                question_year = previous_year_papers[0].get("title", "Unknown Year") if previous_year_papers else "Unknown Year"

                # Add numbering with global counter in the hyperlink and display question below
                results_html += (
                    f"<p><b><a href='https://web.getmarks.app/cpyqb/question/{question_id}' target='_blank'>{global_counter}. {question_year}</a></b><br>"
                    f"{question_text}</p>"
                )
                
                # Increment the global counter
                global_counter += 1
            
            self.results_signal.emit(results_html if results else "No matching questions found.")
        except Exception as e:
            self.results_signal.emit(f"An error occurred: {str(e)}")
            traceback.print_exc()

class QuestionSearchApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Question Search")

        layout = QVBoxLayout()
        self.subject_label = QLabel("Select Subject:")
        layout.addWidget(self.subject_label)
        self.subject_dropdown = QComboBox()
        self.subject_dropdown.addItems(SUBJECTS.keys())
        layout.addWidget(self.subject_dropdown)

        self.keywords_label = QLabel("Enter Keywords:")
        layout.addWidget(self.keywords_label)
        self.keywords_input = QLineEdit()
        self.keywords_input.setPlaceholderText("Type keywords here")
        layout.addWidget(self.keywords_input)

        self.search_button = QPushButton("Search")
        layout.addWidget(self.search_button)

        self.results_area = QTextBrowser()
        self.results_area.setOpenExternalLinks(True)
        layout.addWidget(self.results_area)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        # Load the cache with validation and fallback
        self.cache = load_cache_with_fallback(CACHE_FILE, BACKUP_FILE)
        self.prepare_results_folder()

        # Connect Buttons and "Enter" key press
        self.search_button.clicked.connect(self.run_search)
        self.keywords_input.returnPressed.connect(self.run_search)  # Trigger search on "Enter"

        num_cached_questions = len(self.cache.keys())
        print(f"Number of cached questions: {num_cached_questions}")

        # Periodic backup mechanism
        self.backup_timer = QTimer(self)
        self.backup_timer.timeout.connect(lambda: save_cache_with_backup(self.cache, CACHE_FILE, BACKUP_FILE))
        self.backup_timer.start(60000)  # Backup every 60 seconds

        # Save cache on exit
        QApplication.instance().aboutToQuit.connect(lambda: save_cache_with_backup(self.cache, CACHE_FILE, BACKUP_FILE))

    def prepare_results_folder(self):
        if os.path.exists(MATCHING_QUESTIONS_FOLDER):
            shutil.rmtree(MATCHING_QUESTIONS_FOLDER)
        os.makedirs(MATCHING_QUESTIONS_FOLDER)

    def run_search(self):
        subject_name = self.subject_dropdown.currentText()
        subject_id = SUBJECTS[subject_name]
        cache_key = CACHE_KEYS[subject_name]
        keywords = self.keywords_input.text()

        if not keywords.strip():
            self.results_area.setText("Please enter keywords to search.")
            return

        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)

        # Set the maximum value for the progress bar
        total_questions = 740  # Replace with dynamic value if available
        self.progress_bar.setMaximum(total_questions)
        self.results_area.setText("Searching...")

        self.thread = SearchThread(subject_id, cache_key, keywords, self.cache)
        self.thread.progress_signal.connect(self.update_progress_bar)
        self.thread.results_signal.connect(self.update_results_area)
        self.thread.start()

    def update_progress_bar(self, increment):
        self.progress_bar.setValue(self.progress_bar.value() + increment)

    def update_results_area(self, html):
        self.results_area.setHtml(html)

    def handle_error(self, message):
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Icon.Critical)
        msg.setText(message)
        msg.setWindowTitle("Error")
        msg.exec()

if __name__ == "__main__":
    print("Starting application...")
    app = QApplication([])
    window = QuestionSearchApp()
    window.show()
    app.exec()
