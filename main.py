import typer
from database import databset_init, add_link, quality_check
from rich import print
from rich.console import Console
from rich.table import Table

console = Console()

def main():
    """Main loop for the app menu."""
    print("\nOpened the bookmarks manager app... press 'q' to quit.\n")

    # Initialise the database
    databset_init()

    while True:
        # Display the menu
        menu = Table("option", "command", title="Bookmarks Manager", show_header=True)
        menu.add_row("Add a bookmark: ", "a")
        menu.add_row("Quit the application:", "q")
        print("\n")
        console.print(menu)
        print("\n")
        
        # Ask for a command
        choice = input("Insert a command:\n")
        if choice == 'q':
            break
        elif choice == 'a':
            url = input("Insert the URL:\n")
            add_link(url)
    
    # Before closing the app check that the URLs are valid, not duplicated and not empty
    quality_check()
    print("Goodbye!")

if __name__ == "__main__":
    typer.run(main)