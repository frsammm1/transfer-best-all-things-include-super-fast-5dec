import os
import mimetypes
from telethon.tl.types import MessageMediaWebPage

def human_readable_size(size):
    """Convert bytes to human readable format"""
    if not size: return "0B"
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0: return f"{size:.2f}{unit}"
        size /= 1024.0
    return f"{size:.2f}TB"

def time_formatter(seconds):
    """Convert seconds to formatted time string"""
    if seconds is None or seconds < 0: return "..."
    minutes, seconds = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    if hours > 0: return f"{hours}h {minutes}m {seconds}s"
    return f"{minutes}m {seconds}s"

def get_target_info(message):
    """
    Smart format detection and conversion
    Video -> MP4, Image -> JPG, Doc -> PDF
    """
    original_name = "Unknown_File"
    target_mime = "application/octet-stream"
    force_video = False
    
    if isinstance(message.media, MessageMediaWebPage):
        return None, None, False

    if message.file:
        original_mime = message.file.mime_type
        if message.file.name:
            original_name = message.file.name
        else:
            ext = mimetypes.guess_extension(original_mime) or ""
            original_name = f"File_{message.id}{ext}"
    else:
        original_mime = "image/jpeg"
        original_name = f"Image_{message.id}.jpg"

    base_name = os.path.splitext(original_name)[0]
    
    # VIDEO FORMATS
    if "video" in original_mime or original_name.lower().endswith(
        ('.mkv', '.avi', '.webm', '.mov', '.flv', '.wmv', '.m4v', '.3gp')
    ):
        final_name = base_name + ".mp4"
        target_mime = "video/mp4"
        force_video = True
        
    # IMAGE FORMATS
    elif "image" in original_mime:
        final_name = base_name + ".jpg"
        target_mime = "image/jpeg"
        force_video = False
        
    # PDF
    elif "pdf" in original_mime or original_name.lower().endswith('.pdf'):
        final_name = base_name + ".pdf"
        target_mime = "application/pdf"
        force_video = False
        
    # ALL OTHER FILES (txt, html, zip, etc.)
    else:
        final_name = original_name
        target_mime = original_mime
        force_video = False
        
    return final_name, target_mime, force_video

def apply_filename_manipulations(filename, settings):
    """Apply find/replace operations on filename"""
    if not settings:
        return filename
    
    # Find and Replace in filename
    if settings.get('find_name') and settings.get('replace_name'):
        filename = filename.replace(
            settings['find_name'], 
            settings['replace_name']
        )
    
    return filename

def apply_caption_manipulations(original_caption, settings):
    """Apply caption manipulations"""
    if not settings:
        return original_caption or ""
    
    caption = original_caption or ""
    
    # Find and Replace in caption
    if settings.get('find_cap') and settings.get('replace_cap'):
        caption = caption.replace(
            settings['find_cap'], 
            settings['replace_cap']
        )
    
    # Add extra caption
    if settings.get('extra_cap'):
        if caption:
            caption = f"{caption}\n\n{settings['extra_cap']}"
        else:
            caption = settings['extra_cap']
    
    return caption

def sanitize_filename(filename):
    """Remove invalid characters from filename"""
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    return filename
