"""Script to check PostgreSQL database location and connection info."""

import sys
import subprocess
import os


def find_postgres_data_dir_windows():
    """Find PostgreSQL data directory on Windows."""
    common_paths = [
        r"C:\Program Files\PostgreSQL",
        r"C:\Program Files (x86)\PostgreSQL",
    ]
    
    for base_path in common_paths:
        if os.path.exists(base_path):
            # Look for version subdirectories
            for item in os.listdir(base_path):
                version_path = os.path.join(base_path, item)
                data_path = os.path.join(version_path, "data")
                if os.path.isdir(data_path):
                    return data_path
    
    return None


def get_postgres_config(connection_string=None):
    """Get PostgreSQL configuration information."""
    print("=== PostgreSQL Database Location ===\n")
    
    # Try to get data directory from PostgreSQL
    try:
        if connection_string:
            # Extract connection info
            print(f"Connection: {connection_string}")
        
        # Try to query PostgreSQL for data directory
        cmd = ['psql', '--version']
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"PostgreSQL Version: {result.stdout.strip()}\n")
        
        # Try to get data directory via SQL
        if connection_string:
            # This would require parsing connection string and running SQL
            # For now, just show common locations
            pass
    except FileNotFoundError:
        print("psql command not found in PATH\n")
    
    # Show platform-specific defaults
    import platform
    system = platform.system()
    
    print(f"Platform: {system}\n")
    
    if system == "Windows":
        print("Windows Default Locations:")
        print("  C:\\Program Files\\PostgreSQL\\<version>\\data\\")
        print("  C:\\Program Files (x86)\\PostgreSQL\\<version>\\data\\\n")
        
        found = find_postgres_data_dir_windows()
        if found:
            print(f"Found PostgreSQL data directory: {found}\n")
        else:
            print("Could not automatically find PostgreSQL data directory.\n")
            print("To find it manually:")
            print("  1. Check where PostgreSQL is installed")
            print("  2. Look for the 'data' subdirectory")
            print("  3. Or run: SELECT setting FROM pg_settings WHERE name = 'data_directory';")
    elif system == "Darwin":  # macOS
        print("macOS Default Locations:")
        print("  Homebrew: /opt/homebrew/var/postgresql@<version>/")
        print("  Postgres.app: ~/Library/Application Support/Postgres/var-<version>/")
        print("  Official: /Library/PostgreSQL/<version>/data/\n")
    else:  # Linux
        print("Linux Default Locations:")
        print("  Debian/Ubuntu: /var/lib/postgresql/<version>/main/")
        print("  RHEL/CentOS: /var/lib/pgsql/<version>/data/\n")
    
    print("=== To Find Your Data Directory ===\n")
    print("Option 1: Query PostgreSQL directly")
    print("  psql -U postgres -c \"SELECT setting FROM pg_settings WHERE name = 'data_directory';\"")
    print("\nOption 2: Check PostgreSQL config file")
    print("  Windows: Look in data directory for postgresql.conf")
    print("  macOS/Linux: Usually in /etc/postgresql/<version>/main/")
    print("\nOption 3: Check running processes")
    print("  Windows: Task Manager → Details → Look for postgres.exe")
    print("  macOS/Linux: ps aux | grep postgres")


if __name__ == "__main__":
    connection_string = sys.argv[1] if len(sys.argv) > 1 else None
    get_postgres_config(connection_string)

