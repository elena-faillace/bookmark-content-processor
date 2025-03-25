# Functions to handle the database
import sqlite3
import typer
from rich import print

def databset_init():
    """
    Function to initialize the database, or just check it is initialised.
    Database: 'bookmarks.db'. 
    Tables: 'links'. 
    """
    try:
        # Connect to DB and create a cursor
        db_connection = sqlite3.connect('bookmarks.db')
        cur = db_connection.cursor()

        # Create a table if does not exists
        cur.execute('''
            CREATE TABLE IF NOT EXISTS links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                URL TEXT
            )
        ''')
        
        # Close the cursor
        cur.close()

    except sqlite3.Error as error:
        print('Error occurred - ', error)
    finally:
        if db_connection:
            db_connection.close()
    return None

def add_link(url: str):
    """Given an URL add the link to the database."""
    try:
        # Create connection and cursor
        conn = sqlite3.connect('bookmarks.db')
        cur = conn.cursor()
        # Insert the URL
        cur.execute('''
            INSERT INTO links (URL)
            VALUES (?)
        ''', (url,))
        conn.commit()
        cur.close()
        print("[sea_green1 bold]URL added successfully![/]")
    except sqlite3.Error as error:
        print("[red bold]Error occurred - [/]", error)
    finally:
        if conn:
            conn.close()
    return None


