import typer
from database import databset_init, add_link
from rich import print
from rich.console import Console
from rich.table import Table

console = Console()

def main_tutorial(name: str, lastname: str = '', formal: bool = False):
    """Say hi to NAME, optionally with a --lastname.

    If --formal is used, say hi very formally.
    """
    if formal:
        print(f"Good day Ms. {name} {lastname}.")
    else:
        print(f"Hello {name} {lastname}")

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

if __name__ == "__main__":
    typer.run(main)