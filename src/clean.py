import os
import re

def remove_build_files(directory="."):
    """Removes common build artifacts and temporary files."""
    patterns = [
        r"__pycache__",
        r"\.pyc$",
        r"\.pyd$",
        r"\.so$",
        r"\.o$",
        r"\.obj$",
        r"compile_commands\.json$",
        r"bindings\.pyi$",
        r"bindings\.cpython-\d+-\w+\.so$",  # Linux bindings
        r"bindings\.cp\d+-\w+\.pyd$",      # Windows bindings
        r"\.tar\.gz$",
        r"\.bin$",
        r"client\.dist",
        r"server\.dist",
        r"sdl-wrapper",
    ]

    for root, dirs, files in os.walk(directory, topdown=False):
        # Remove directories that match the pattern
        dirs[:] = [d for d in dirs if not any(re.search(p, d) for p in patterns)]
        for name in files:
            filepath = os.path.join(root, name)
            if any(re.search(p, name) for p in patterns):
                try:
                    os.remove(filepath)
                    print(f"Removed: {filepath}")
                except OSError as e:
                    print(f"Error removing {filepath}: {e}")

    # Remove empty directories that might be left behind
    for root, dirs, files in os.walk(directory, topdown=False):
        for name in dirs:
            dirpath = os.path.join(root, name)
            if not os.listdir(dirpath):
                try:
                    os.rmdir(dirpath)
                    print(f"Removed empty directory: {dirpath}")
                except OSError as e:
                    print(f"Error removing directory {dirpath}: {e}")

if __name__ == "__main__":
    print("Removing build files...")
    remove_build_files()
    print("\nBuild file removal complete.")

    gitignore_content = """# Python bytecode and temporary files
__pycache__/
*.pyc
*.pyd
*.so

# Compiled object files
*.o
*.obj

# Compilation database
compile_commands.json

# Python type stub
bindings.pyi

# Platform-specific bindings (you might want to be more specific if only targeting one platform)
bindings.cpython-*
bindings.cp*

# Distribution archives
*.tar.gz
*.bin

# Distribution directories
client.dist/
server.dist/
sdl-wrapper/
"""

    with open(".gitignore", "w") as f:
        f.write(gitignore_content)
    print("\nGenerated .gitignore file.")
    print("\nContents of .gitignore:")
    print(gitignore_content)