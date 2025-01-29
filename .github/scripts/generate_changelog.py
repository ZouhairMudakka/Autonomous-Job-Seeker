import subprocess
import os

def generate_changelog():
    """Generate CHANGELOG.md from git commits."""
    try:
        # Generate the changelog
        subprocess.run([
            'conventional-changelog',
            '-p', 'angular',  # Use Angular commit convention
            '-i', 'CHANGELOG.md',  # Input/output file
            '-s',  # Same file
            '-r', '0'  # Release count (0 for all)
        ], check=True)
        print("Changelog generated successfully!")
    except subprocess.CalledProcessError as e:
        print(f"Error generating changelog: {e}")
        raise

if __name__ == '__main__':
    generate_changelog() 