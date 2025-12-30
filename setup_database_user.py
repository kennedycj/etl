"""Helper script to set up database user and database."""

import sys
import getpass
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError, ProgrammingError


def setup_database(admin_url: str, db_name: str = "finance", username: str = None, password: str = None):
    """Set up database and user.
    
    Args:
        admin_url: Connection string for admin user (typically postgres)
        db_name: Name of database to create
        username: Username to create (if None, will prompt)
        password: Password for user (if None, will prompt)
    """
    if username is None:
        username = input("Enter username to create (or press Enter to skip user creation): ").strip()
        if not username:
            print("Skipping user creation, just creating database...")
            username = None
    
    if username and password is None:
        password = getpass.getpass(f"Enter password for user '{username}': ")
        password_confirm = getpass.getpass("Confirm password: ")
        if password != password_confirm:
            print("Passwords don't match!")
            return False
    
    try:
        admin_engine = create_engine(admin_url)
        
        with admin_engine.connect() as conn:
            # Commit transactions manually
            conn = conn.execution_options(autocommit=True)
            
            # Create database if it doesn't exist
            print(f"\nCreating database '{db_name}'...")
            try:
                conn.execute(text(f"CREATE DATABASE {db_name}"))
                print(f"✓ Database '{db_name}' created")
            except ProgrammingError as e:
                if "already exists" in str(e):
                    print(f"✓ Database '{db_name}' already exists")
                else:
                    raise
            
            # Create user if specified
            if username:
                print(f"\nCreating user '{username}'...")
                try:
                    conn.execute(text(f"CREATE USER {username} WITH PASSWORD '{password}'"))
                    print(f"✓ User '{username}' created")
                except ProgrammingError as e:
                    if "already exists" in str(e):
                        print(f"✓ User '{username}' already exists, updating password...")
                        conn.execute(text(f"ALTER USER {username} WITH PASSWORD '{password}'"))
                    else:
                        raise
                
                # Grant privileges
                print(f"Granting privileges to '{username}'...")
                conn.execute(text(f"GRANT ALL PRIVILEGES ON DATABASE {db_name} TO {username}"))
                
                # Connect to the database to grant schema privileges
                user_db_url = admin_url.rsplit('/', 1)[0] + f'/{db_name}'
                user_engine = create_engine(user_db_url)
                with user_engine.connect() as user_conn:
                    user_conn = user_conn.execution_options(autocommit=True)
                    user_conn.execute(text(f"GRANT ALL ON SCHEMA public TO {username}"))
                    print(f"✓ Schema privileges granted")
        
        print("\n✓ Setup complete!")
        
        if username:
            # Build connection string for new user
            # Extract host/port from admin_url
            if '@' in admin_url:
                host_part = admin_url.split('@')[1].split('/')[0]
            else:
                host_part = "localhost"
            
            new_url = f"postgresql://{username}:{password}@{host_part}/{db_name}"
            print(f"\nYou can now use this connection string:")
            print(f"  {new_url}")
            print("\n(Note: This is shown for convenience. Store securely!)")
        
        return True
        
    except OperationalError as e:
        print(f"\n✗ Connection error: {e}")
        print("\nMake sure:")
        print("  1. PostgreSQL is running")
        print("  2. Admin user credentials are correct")
        print("  3. You have permission to create databases")
        return False
    except Exception as e:
        print(f"\n✗ Error: {e}")
        return False


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python setup_database_user.py <admin_connection_string> [database_name] [username]")
        print("\nExample:")
        print("  python setup_database_user.py postgresql://postgres:mypassword@localhost")
        print("  python setup_database_user.py postgresql://postgres:mypassword@localhost finance caleb")
        print("\nThis will:")
        print("  1. Create the database (if it doesn't exist)")
        print("  2. Create the user (if provided)")
        print("  3. Grant necessary privileges")
        sys.exit(1)
    
    admin_url = sys.argv[1]
    db_name = sys.argv[2] if len(sys.argv) > 2 else "finance"
    username = sys.argv[3] if len(sys.argv) > 3 else None
    
    success = setup_database(admin_url, db_name, username)
    sys.exit(0 if success else 1)

