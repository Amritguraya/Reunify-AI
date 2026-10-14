"""Prompt for a staff password and print a Werkzeug hash for deployment."""

from getpass import getpass

from werkzeug.security import generate_password_hash


def main() -> None:
    password = getpass("Staff password: ")
    confirmation = getpass("Confirm password: ")
    if len(password) < 14:
        raise SystemExit("Use a password with at least 14 characters.")
    if password != confirmation:
        raise SystemExit("Passwords do not match.")
    print("Set STAFF_PASSWORD_HASH to this value in the hosting dashboard:")
    print(generate_password_hash(password, method="scrypt"))


if __name__ == "__main__":
    main()
