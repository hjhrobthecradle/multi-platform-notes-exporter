import re
import os

WINDOWS_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
}

ILLEGAL_CHAR_REGEX = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def sanitize_filename(name: str, max_length: int = 120, fallback: str = "untitled") -> str:
    """
    Sanitizes a string to be safely used as a filename across Windows, macOS, and Linux.
    """
    if not name:
        return fallback

    # Replace illegal characters with an underscore
    cleaned = ILLEGAL_CHAR_REGEX.sub("_", name)
    
    # Strip leading/trailing spaces and dots
    cleaned = cleaned.strip(". ")
    
    # Check if empty after cleaning
    if not cleaned:
        cleaned = fallback

    # Check for Windows reserved names
    base_name = cleaned.split(".")[0].upper()
    if base_name in WINDOWS_RESERVED_NAMES:
        cleaned = f"_{cleaned}"

    # Truncate length if needed
    if len(cleaned) > max_length:
        # Keep extension if possible
        parts = cleaned.rsplit(".", 1)
        if len(parts) == 2 and len(parts[1]) <= 10:
            ext = parts[1]
            stem = parts[0][:max_length - len(ext) - 1].rstrip(". ")
            cleaned = f"{stem}.{ext}"
        else:
            cleaned = cleaned[:max_length].rstrip(". ")

    return cleaned or fallback


def get_unique_filepath(directory: str, filename: str) -> str:
    """
    Returns a unique file path in the directory, appending (1), (2), etc. if it already exists.
    """
    filepath = os.path.join(directory, filename)
    if not os.path.exists(filepath):
        return filepath

    stem, ext = os.path.splitext(filename)
    counter = 1
    while True:
        new_filename = f"{stem} ({counter}){ext}"
        filepath = os.path.join(directory, new_filename)
        if not os.path.exists(filepath):
            return filepath
        counter += 1
