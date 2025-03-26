# # import sqlite3

# # # Connect to the database
# # conn = sqlite3.connect('books.db')
# # cursor = conn.cursor()

# # # Check if the 'email' column already exists to avoid errors
# # cursor.execute("PRAGMA table_info(users);")
# # columns = [column[1] for column in cursor.fetchall()]

# # if 'email' not in columns:
# #     # Add the 'email' column to the 'users' table
# #     cursor.execute("ALTER TABLE users ADD COLUMN email TEXT;")
# #     conn.commit()
# #     print("Column 'email' added successfully.")
# # else:
# #     print("Column 'email' already exists.")

# # # Close the connection
# # conn.close()




# import sqlite3

# # Connect to your SQLite database (it will create the database if it doesn't exist)
# conn = sqlite3.connect('books.db')
# cursor = conn.cursor()

# # Create the users table
# cursor.execute('''
#     CREATE TABLE IF NOT EXISTS users (
#         id INTEGER PRIMARY KEY,
#         email TEXT NOT NULL,
#         password TEXT NOT NULL
#     );
# ''')

# # Commit the changes and close the connection
# conn.commit()
# conn.close()

# print("Users table created successfully.")


# import jwt

# token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VybmFtZSI6ImFsaTIzNCJ9.BfJjHzHfLPX2Wkad12AGwvtTwyE8ANWyjwk-EghZMxA"
# secret_key = "74564568847kfshjhgfbfsbkdjfhg"

# # Try decoding the token with your secret key
# decoded_token = jwt.decode(token, secret_key, algorithms=["HS256"])
# print(decoded_token)

import jwt
from fastapi import HTTPException

SECRET_KEY = "74564568847kfshjhgfbfsbkdjfhg"  # Use the same SECRET_KEY you used when generating the token
ALGORITHM = "HS256"

def get_current_user(token: str):
    try:
        # Decode the token
        decoded_token = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        print(f"Decoded Token: {decoded_token}")  # This should print the decoded user data
        return decoded_token.get("username")  # Extract username or user info from the decoded token
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")
