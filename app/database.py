# Functions to handle the database
import sqlite3
import typer
from rich import print as rich_print
import logging


def log_database_interactions(func):
    """Decorator to wrap functions that handle database operations."""
    def wrapper(*args, **kwargs):
        if func.__name__ == "databset_init":
            logging.info("Initializing the database...")
        elif func.__name__ == "add_link":
            logging.info("Adding the link: %s to the table 'links'...", args[0])
        elif func.__name__ == "quality_check":
            logging.info("Performing quality check on the table 'links'...")
        elif func.__name__ == "get_list_links":
            logging.info("Getting the list of links from the table 'links'...")

        result = func(*args, **kwargs)

        return result
    return wrapper

@log_database_interactions
def databset_init():
    """
    Function to initialize the database, or just check it is initialized.
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
                Date DATE DEFAULT CURRENT_TIMESTAMP,
                URL TEXT
            )
        ''')
        # Close the cursor
        cur.close()
        logging.info("... database initialized successfully with table 'links'.")

    except sqlite3.Error as error:
        logging.error("Error occurred - %s", error)
        rich_print("[red]Error occurred while initializing the database.[/]")
    finally:
        if db_connection:
            db_connection.close()
    return None

@log_database_interactions
def add_link(url: str):
    """Given an URL add the link to the database."""
    try:
        # Create connection and cursor
        conn = sqlite3.connect('bookmarks.db')
        cur = conn.cursor()
        # Insert the URL
        cur.execute('''
            INSERT INTO links (Date, URL)
            VALUES (CURRENT_TIMESTAMP, ?)
        ''', (url,))
        conn.commit()
        cur.close()
        rich_print("[sea_green1 bold]URL added successfully![/]")
        logging.info("... URL added successfully to the table 'links'.")
    except sqlite3.Error as error:
        logging.error("Error occurred - %s", error)
        rich_print("[red]Error occurred while adding the URL.[/]")
    finally:
        if conn:
            conn.close()
    return None

@log_database_interactions
def quality_check():
    """Remove rows if:
    - URL is empty or NULL
    - URL is duplicated
    - URL is not a valid URL
    """
    try:
        # Create connection and cursor
        conn = sqlite3.connect('bookmarks.db')
        cur = conn.cursor()
        
        # Check for empty URLs
        res = cur.execute('''
            SELECT * FROM links
            WHERE URL IS NULL OR URL = ''
        ''').fetchall()
        if res != []:
            cur.execute('''
                DELETE FROM links
                WHERE URL IS NULL OR URL = ''
            ''')
            logging.warning("...empty URLs removed (id, URL): %s", res)
        conn.commit()

        # Check for duplicated URLs
        res = cur.execute('''
            SELECT * FROM links
            WHERE id NOT IN (
                SELECT MIN(id)
                FROM links
                GROUP BY URL
            )
        ''').fetchall()
        if res != []:
            cur.execute('''
                DELETE FROM links
                WHERE id NOT IN (
                    SELECT MIN(id)
                    FROM links
                    GROUP BY URL
                )
            ''')
            logging.warning("...duplicated URLs removed (id, URL): %s", res)
        conn.commit()

        # Check for valid URLs
        res = cur.execute('''
            SELECT * FROM links
            WHERE URL NOT LIKE 'http%'
        ''').fetchall()
        if res != []:
            cur.execute('''
                DELETE FROM links
                WHERE URL NOT LIKE 'http%'
            ''')
            logging.warning("...invalid URLs removed (id, URL): %s", res)
        conn.commit()

        cur.close()

    except sqlite3.Error as error:
        logging.error("Error occurred - %s", error)
        rich_print("[red]Error occurred while performing quality check.[/]")
    finally:
        if conn:
            conn.close()
    return None

@log_database_interactions
def get_list_links():
    """Get the list of all the saved URLs by saving it to a .txt file.
    """
    try:
        # Create connection and cursor
        conn = sqlite3.connect('bookmarks.db')
        cur = conn.cursor()
        # Get the list of URLs
        res = cur.execute('''
            SELECT URL FROM links
        ''').fetchall()
        # Save the list to a .txt file
        with open('list_bookmarks.txt', 'w', encoding='utf-8') as f:
            for row in res:
                f.write(row[0] + '\n')
        logging.info("...list of URLs saved to list_bookmarks.txt")
        rich_print("[sea_green1 bold]List of URLs saved to list_bookmarks.txt![/]")
        cur.close()
    except sqlite3.Error as error:
        logging.error("Error occurred in 'get_list_links' - %s", error)
        rich_print("[red]Error occurred while saving the list of URLs.[/]")
    finally:
        if conn:
            conn.close()
    return None