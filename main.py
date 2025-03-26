import os
import openai
import json
import jwt
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import re
import requests
from bs4 import BeautifulSoup
from bson import ObjectId
from langdetect import detect
from dotenv import load_dotenv
import aiohttp
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional

# Load environment variables from a .env file
load_dotenv()

# Initialize FastAPI app
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust this for security in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load environment variables
MONGO_URI = os.getenv("MONGO_URI")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")

# Check if SECRET_KEY is loaded correctly
if not SECRET_KEY:
    raise HTTPException(status_code=500, detail="SECRET_KEY not found in environment variables")




async def fetch_gutenberg_book(book_id: str):
    # Construct URLs for book content and metadata
    content_url = f"https://www.gutenberg.org/files/{book_id}/{book_id}-0.txt"
    metadata_url = f"https://www.gutenberg.org/ebooks/{book_id}"

    try:
        async with aiohttp.ClientSession() as session:
            # Fetch book content
            async with session.get(content_url) as content_response:
                # Check if content was found
                if content_response.status != 200:
                    raise HTTPException(status_code=content_response.status, detail="Book content not found")
                content = await content_response.text()

            # Fetch book metadata
            async with session.get(metadata_url) as metadata_response:
                # Check if metadata was found
                if metadata_response.status != 200:
                    raise HTTPException(status_code=metadata_response.status, detail="Book metadata not found")
                metadata = {
                    "book_id": book_id,
                    "url": metadata_url,
                    "title": f"Book {book_id}",
                }

            return content, metadata

    except aiohttp.ClientError as e:
        # Handle network-related errors
        raise HTTPException(status_code=500, detail=f"Network error: {str(e)}")
    except Exception as e:
        # Handle any other exceptions
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")
# MongoDB Setup
client = MongoClient(MONGO_URI)
db = client["book_database"]
users_collection = db["users"]
books_collection = db["books"]

# Pydantic models
class User(BaseModel):
    username: str
    password: str

class BookRequest(BaseModel):
    book_id: int

class AnalyzeRequest(BaseModel):
    text: str



def openai_analyze_text(text):
    prompts = {
        "sentiment": "Analyze the sentiment of this text:",
        "summary": "Summarize this text:",
        "ner": "Extract named entities from this text:",
        "characters": "Identify the key characters in this text:",
        "plot_summary": "Summarize the plot of this book:",
    }

    # Initialize response dictionary
    results = {}

    # Perform each analysis
    for analysis_type, prompt in prompts.items():
        prompt_text = f"{prompt} \n{text}"
        
        # Make the OpenAI API request
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "system", "content": prompt_text}],
            api_key=OPENAI_API_KEY
        )

        # Extract and store the result for each analysis type
        analysis_result = response["choices"][0]["message"]["content"].strip()
        results[analysis_type] = analysis_result
    
    # Return all results in a structured JSON format
    return {
        "analysis_result": results
    }
# Helper function to extract the user from the token
def get_current_user(token: str):
    try:
        decoded_token = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return decoded_token.get("user_id")  # Use user_id instead of username
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")

# Function to authenticate user and generate JWT token
async def authenticate_user(username, password):
    user = users_collection.find_one({"username": username})
    if user and check_password_hash(user["password"], password):
        token = jwt.encode({"user_id": str(user["_id"]), "username": username}, SECRET_KEY, algorithm="HS256")
        return token
    return None

# Route for user signup
@app.post("/signup")
async def signup(user: User):
    username = user.username
    password = user.password
    
    if not username or not password:
        raise HTTPException(status_code=400, detail="Username and password are required")
    
    if users_collection.find_one({"username": username}):
        raise HTTPException(status_code=400, detail="Username already exists")
    
    hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
    user_data = {
        "username": username,
        "password": hashed_password,
        "created_at": datetime.utcnow()
    }
    user_record = users_collection.insert_one(user_data)
    return JSONResponse(content={"message": "User created successfully", "user_id": str(user_record.inserted_id)}, status_code=201)

# Route for user login
@app.post("/login")
async def login(user: User):
    username = user.username
    password = user.password
    
    if not username or not password:
        raise HTTPException(status_code=400, detail="Username and password are required")
    
    token = await authenticate_user(username, password)
    if token:
        return JSONResponse(content={"message": "Login successful", "token": token})
    else:
        raise HTTPException(status_code=401, detail="Invalid username or password")

# Route to fetch and display the book
@app.post("/fetch_book")
async def fetch_book_endpoint(book: BookRequest):
    book_id = book.book_id
    content, metadata = await fetch_gutenberg_book(str(book_id))
    
    # Return the book content and metadata
    return {"content": content, "metadata": metadata}

# Route to perform text analysis (sentiment, summary, NER, character identification, plot summary)
@app.post("/analyze")
async def analyze(analysis_request: AnalyzeRequest):
    text = analysis_request.text
    result = openai_analyze_text(text)

    # ✅ Returning the structured JSON response directly
    return {
        "status": "success",
        "data": result
    }

# Route to save the book and its metadata to the database
@app.post("/save_book")
async def save_book(request: Request, book: BookRequest):
    # Extract the token from the request header
    token = request.headers.get("Authorization")
    if token is None:
        raise HTTPException(status_code=401, detail="Authorization token missing")

    # Extract the user_id from the token
    user_id = get_current_user(token.replace("Bearer ", ""))  # Remove 'Bearer ' prefix if present
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid user token")

    # Save the book to the database
    book_data = {
        "user_id": user_id,
        "book_id": book.book_id,
        "created_at": datetime.utcnow()
    }
    books_collection.insert_one(book_data)
    
    return JSONResponse(content={"message": "Book saved successfully"}, status_code=201)

# Route to fetch books for the current user
@app.get("/books")
async def get_books(request: Request):
    # Extract the token from the request header
    token = request.headers.get("Authorization")
    if token is None:
        raise HTTPException(status_code=401, detail="Authorization token missing")

    # Extract the user_id from the token
    user_id = get_current_user(token.replace("Bearer ", ""))  # Remove 'Bearer ' prefix if present
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid user token")

    # Fetch the user's books from the database
    books = list(books_collection.find({"user_id": user_id}))
    for book in books:
        book["_id"] = str(book["_id"])  # Convert ObjectId to string for JSON response
    return {"books": books}

# Route to fetch a single book by its ID
@app.get("/book/{book_id}")
async def fetch_book(book_id: str, request: Request):
    # Extract the token from the request header
    token = request.headers.get("Authorization")
    user_id = get_current_user(token)
    
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid user token")
    
    # Convert book_id to ObjectId if it is a valid ObjectId
    try:
        book_id_obj = ObjectId(book_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid book ID format")
    
    book = books_collection.find_one({"_id": book_id_obj, "user_id": user_id})
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    
    return JSONResponse(content={"title": book["metadata"]["title"], "content": book["text"]})

@app.options("/{full_path:path}")
async def preflight_handler():
    return JSONResponse(content=None, status_code=200)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
