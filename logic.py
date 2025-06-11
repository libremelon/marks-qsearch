import os
import sys
import json
import shutil
import traceback
import aiohttp
import asyncio
from aiofiles import open as aio_open
from dotenv import load_dotenv
from fasteners import InterProcessLock  # For file locking
from threading import Lock

CACHE_FILE = "data/cache.json"
BACKUP_FILE = "data/cache.bak"
BASE_URL = "https://web.getmarks.app/api/v3/cpyqb"
MATCHING_QUESTIONS_FOLDER = "data/matching_questions"

cache_lock = Lock()  # Thread-safe lock for cache modifications

# Load environment variables
load_dotenv(".env")
API_KEY = os.getenv("MARKS_APP_API_KEY")
HEADERS = {"Authorization": f"Bearer {API_KEY}"}

# Check if stdout is available (CLI mode)
is_cli_mode = sys.stdout and sys.stdout.write

# Load the cache with fallback to backup
def load_cache_with_fallback(cache_file, backup_file):
    try:
        print(f"Loading cache from file: {cache_file}")
        with open(cache_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        print(f"Cache file {cache_file} is invalid or missing. Attempting to load backup...")
        try:
            with open(backup_file, "r", encoding="utf-8") as f:
                print("Loaded backup cache successfully.")
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            print(f"Backup file {backup_file} is invalid or missing. Starting with a new cache.")
            return {}

# Save the cache atomically to prevent corruption
def save_cache_atomic(cache, cache_file):
    cache_copy = json.loads(json.dumps(cache))  # Deep copy to prevent changes during iteration
    temp_file = f"{cache_file}.tmp"
    os.makedirs(os.path.dirname(temp_file), exist_ok=True)

    lock = InterProcessLock(f"{cache_file}.lock")  # Lock file
    try:
        lock.acquire(timeout=10)  # Wait for up to 10 seconds
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(cache_copy, f, indent=2)
        os.replace(temp_file, cache_file)
        print(f"Cache saved atomically at {cache_file}")
    finally:
        lock.release()

# Save the cache with a backup
def save_cache_with_backup(cache, cache_file, backup_file):
    with cache_lock:  # Ensure thread-safe access
        if os.path.exists(cache_file):
            shutil.copy(cache_file, backup_file)  # Backup the old cache
            print(f"Backup created at {backup_file}")
        save_cache_atomic(cache, cache_file)

# Retry mechanism for API calls
async def fetch_with_retries(url, headers, method="GET", data=None, initial_delay=1, max_delay=60):
    delay = initial_delay
    while True:
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as session:
                if method == "POST":
                    async with session.post(url, json=data, headers=headers) as response:
                        if response.status == 429:
                            print("HTTP Error 429: Rate-limited. Retrying after delay...")
                            await asyncio.sleep(delay)
                            delay = min(delay * 2, max_delay)
                            continue
                        response.raise_for_status()
                        return await response.json()
                else:
                    async with session.get(url, headers=headers) as response:
                        if response.status == 429:
                            print("HTTP Error 429: Rate-limited. Retrying after delay...")
                            await asyncio.sleep(delay)
                            delay = min(delay * 2, max_delay)
                            continue
                        response.raise_for_status()
                        return await response.json()
        except aiohttp.ClientResponseError as e:
            print(f"HTTP Error {e.status}: {e.message}, URL: {url}")
            if e.status == 429:
                print("Encountered 429 error again. Retrying after delay...")
                await asyncio.sleep(delay)
                delay = min(delay * 2, max_delay)
                continue
            else:
                print(f"Non-429 error encountered: {e}")
                return None
        except aiohttp.ClientError as e:
            print(f"Client error: {e}, URL: {url}")
            return None

# Fetch details for a specific question
async def fetch_question_details(question_id, cache):  
    cache_key = f"question_{question_id}"
    question_details = cache.get(cache_key)

    if question_details:
        return question_details

    print(f"Fetching details for question ID {question_id}")
    url = f"https://web.getmarks.app/api/v2/questions/{question_id}"
    question_details = await fetch_with_retries(url, HEADERS, method="POST")

    if question_details:
        with cache_lock:  # Ensure thread-safe cache modification
            cache[cache_key] = question_details
        save_cache_with_backup(cache, CACHE_FILE, BACKUP_FILE)  # Save with backup
    else:
        print(f"Failed to fetch details for question ID {question_id}")

    return question_details

# Fetch and cache chapters
async def list_chapters(subject_id, cache, cache_key):
    if cache_key in cache:
        return cache[cache_key]

    url = f"{BASE_URL}/subjects/{subject_id}/chapters?limit=1000"
    chapters = await fetch_with_retries(url, HEADERS)
    if chapters:
        with cache_lock:  # Ensure thread-safe cache modification
            cache[cache_key] = chapters.get("data", [])
        save_cache_with_backup(cache, CACHE_FILE, BACKUP_FILE)  # Save with backup
    return cache.get(cache_key, [])

# Search for questions
async def search_questions(subject_id, keywords, cache, cache_key, progress_callback=None):
    chapters = await list_chapters(subject_id, cache, cache_key)
    if not chapters:
        print(f"No chapters found for subject: {subject_id}")
        return []

    os.makedirs(MATCHING_QUESTIONS_FOLDER, exist_ok=True)
    semaphore = asyncio.Semaphore(5)
    matching_questions = []

    total_questions = sum(len(chapter.get("questions", [])) for chapter in chapters)
    print(f"Total questions to process: {total_questions}")

    # Initialize progress bar only in CLI mode
    if is_cli_mode:
        from tqdm import tqdm
        progress_bar = tqdm(total=total_questions, desc="Processing Questions", unit="question", ncols=80)
    else:
        print("Running in GUI mode; progress bar disabled.")
        progress_bar = None  # No progress bar in GUI mode

    async def process_chapter(chapter):
        async with semaphore:
            chapter_id = chapter["_id"]
            chapter_title = chapter["title"]
            url = f"{BASE_URL}/chapters/{chapter_id}/details"
            response = await fetch_with_retries(url, HEADERS)

            if response:
                questions = response.get("data", {}).get("questions", [])
                for question_id in questions:
                    question_details = await fetch_question_details(question_id, cache)
                    if question_details:
                        question_text = question_details.get("data", {}).get("question", {}).get("text", "")
                        if keywords.lower() in question_text.lower():
                            matching_questions.append(question_details)
                            filename = os.path.join(
                                MATCHING_QUESTIONS_FOLDER,
                                f"matching_questions_{subject_id}_{chapter_title}.json".replace(" ", "_")
                            )
                            async with aio_open(filename, "w", encoding="utf-8") as f:
                                await f.write(json.dumps(question_details, indent=2))
                            print(f"Matching question saved to {filename}")

                    if progress_callback:
                        progress_callback(1)

                    if progress_bar:
                        progress_bar.update(1)

    try:
        await asyncio.gather(*(process_chapter(chapter) for chapter in chapters))
    except Exception as e:
        print(f"An error occurred while processing chapters: {e}")
        traceback.print_exc()

    if progress_bar:
        progress_bar.close()
    return matching_questions
