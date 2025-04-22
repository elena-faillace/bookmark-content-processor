import logging
from io import StringIO

import typer
from database import databset_init, add_link, quality_check, get_list_links
from rich import print as rich_print
from rich.console import Console
from rich.table import Table

console = Console()
log_stream = StringIO()
logging.basicConfig(stream=log_stream, level=logging.INFO)


def main():
    """Main loop for the app menu."""
    try:
        rich_print("\nOpened the bookmarks manager app... press 'q' to quit.\n")

        # Initialise the database
        databset_init()

        while True:
            # Display the menu
            menu = Table(
                "[plum1 bold]Options[/]", "[light_pink1 bold]Commands[/]", title="[orchid2 bold]Bookmarks Manager[/]", show_header=True
            )
            menu.add_row("Add a bookmark: ", "a")
            menu.add_row("Quit the application:", "q")
            menu.add_row("Get list of bookmarks (to .txt file):", "list")
            rich_print("\n")
            console.print(menu)
            rich_print("\n")

            # Ask for a command
            choice = input("Insert a command:\n")
            if choice == "q":
                logging.info("User chose to quit the application.")
                break
            elif choice == "a":
                url = input("Insert the URL:\n")
                logging.info("User chose to add a URL: '%s'", url)
                add_link(url)
            elif choice == "list":
                logging.info("User chose to get the list of bookmarks.")
                get_list_links()
            else:
                rich_print(f"[dark_orange bold]Invalid command: [/] '{choice}'")
                logging.warning("Invalid command: '%s'", choice)

        # Before closing the app check that the URLs are valid, not duplicated and not empty
        quality_check()
        rich_print("[thistle3 bold]Goodbye![/]")
    except Exception as e:
        logging.error("An error occurred in the main loop: %s", e)
    finally:
        # Save the logged messages to a file txt
        with open("logged_messages.txt", "w", encoding="utf-8") as text_file:
            text_file.write(log_stream.getvalue())
            text_file.close()


if __name__ == "__main__":
    typer.run(main)