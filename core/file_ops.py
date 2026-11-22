"""Pure OS and filesystem operations: directory scanning, collision-safe moving, Recycle Bin, Explorer."""

import ctypes
from ctypes import wintypes
from datetime import datetime
import os
import re
import subprocess
import time

from media.formats import readable_image_extensions

_NATURAL_SPLIT = re.compile(r"(\d+)")


class _SHFILEOPSTRUCTW(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("wFunc", wintypes.UINT),
        ("pFrom", wintypes.LPCWSTR),
        ("pTo", wintypes.LPCWSTR),
        ("fFlags", wintypes.WORD),
        ("fAnyOperationsAborted", wintypes.BOOL),
        ("hNameMappings", wintypes.LPVOID),
        ("lpszProgressTitle", wintypes.LPCWSTR),
    ]


def send_to_recycle_bin(file_path: str) -> bool:
    """Move a file safely to the Windows Recycle Bin (FOF_ALLOWUNDO)."""
    abs_path = os.path.abspath(file_path)
    if not os.path.exists(abs_path):
        return False
    op = _SHFILEOPSTRUCTW()
    op.wFunc = 3  # FO_DELETE
    op.pFrom = abs_path + "\0\0"
    op.fFlags = 0x0040 | 0x0010 | 0x0004 | 0x0400
    rc = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op))
    return rc == 0 and not op.fAnyOperationsAborted


def reveal_in_file_explorer(file_path: str) -> bool:
    """Highlight file in Windows File Explorer without blocking the caller."""
    norm = os.path.normpath(file_path)
    try:
        subprocess.Popen(["explorer", f"/select,{norm}"])
        return True
    except OSError:
        return False


def natural_sort_key(path: str):
    """Natural Explorer-style key so IMG_2 sorts before IMG_10."""
    name = os.path.basename(path).lower()
    return [int(part) if part.isdigit() else part for part in _NATURAL_SPLIT.split(name)]


def get_unique_destination(dest_folder: str, filename: str) -> str:
    """Return a non-colliding destination path ('photo (1).jpg', etc.), never overwriting files."""
    base, ext = os.path.splitext(filename)
    candidate = os.path.join(dest_folder, filename)
    counter = 1
    while os.path.lexists(candidate):
        candidate = os.path.join(dest_folder, f"{base} ({counter}){ext}")
        counter += 1
    return candidate


def format_auto_rename_filename(
    pattern: str,
    orig_path: str,
    folder_name: str,
    index: int = 1,
) -> str:
    """Format target filename using user template pattern, preserving file extension and escaping invalid OS chars."""
    orig_stem, orig_ext = os.path.splitext(os.path.basename(orig_path))
    date_str = datetime.now().strftime("%Y%m%d")
    clean_folder = re.sub(r'[\\/*?:"<>|]', "_", str(folder_name or "Folder").strip())
    clean_stem = re.sub(r'[\\/*?:"<>|]', "_", str(orig_stem or "media").strip())

    template = (pattern or "").strip() or "{folder}_{index:04d}"
    try:
        formatted = template.format(
            folder=clean_folder,
            name=clean_stem,
            date=date_str,
            index=index,
            ext=orig_ext,
        )
    except (ValueError, KeyError, IndexError):
        formatted = (
            template.replace("{folder}", clean_folder)
            .replace("{name}", clean_stem)
            .replace("{date}", date_str)
            .replace("{index}", f"{index:04d}")
            .replace("{ext}", orig_ext)
        )

    if not formatted.lower().endswith(orig_ext.lower()):
        formatted = f"{formatted}{orig_ext}"

    base_name = os.path.basename(formatted)
    clean_name = re.sub(r'[\\/*?:"<>|]', "_", base_name).strip()
    return clean_name or f"{clean_stem}{orig_ext}"


def generate_session_summary(
    source_folder: str,
    all_files: list,
    history_records: list,
    flagged_paths: set,
    slot_names: list,
    slot_paths: list,
) -> dict:
    """Compute complete statistical summary of sorting activity in current session."""
    total_files = len(all_files)
    flagged_count = len(flagged_paths or set())

    norm_slot_map = {}
    for name, p in zip(slot_names or [], slot_paths or []):
        if p:
            norm_slot_map[os.path.normcase(os.path.normpath(os.path.abspath(p)))] = name

    folder_counts = {name: 0 for name in (slot_names or [])}
    other_moved_count = 0

    known_src_norms = {os.path.normcase(os.path.normpath(f)) for f in (all_files or [])}

    for src, dst in (history_records or []):
        norm_src = os.path.normcase(os.path.normpath(src))
        if norm_src not in known_src_norms:
            continue
        dst_dir = os.path.normcase(os.path.normpath(os.path.abspath(os.path.dirname(dst))))
        matched_slot = None
        for s_dir, s_name in norm_slot_map.items():
            if dst_dir == s_dir or dst_dir.startswith(s_dir + os.sep):
                matched_slot = s_name
                break
        if matched_slot:
            folder_counts[matched_slot] = folder_counts.get(matched_slot, 0) + 1
        else:
            other_moved_count += 1

    total_moved = sum(folder_counts.values()) + other_moved_count
    remaining = max(0, total_files - total_moved)

    return {
        "source_folder": source_folder or "No folder loaded",
        "total_files": total_files,
        "total_moved": total_moved,
        "folder_counts": folder_counts,
        "other_moved_count": other_moved_count,
        "flagged_count": flagged_count,
        "remaining_unmoved": remaining,
    }


def norm_path_key(path: str) -> str:
    """Normalized case-insensitive comparison key for paths."""
    return os.path.normcase(os.path.normpath(os.path.abspath(path)))


def scan_image_files(
    folder_path: str,
    extensions=None,
    should_cancel=None,
    on_progress=None,
    include_subfolders: bool = False,
    excluded_dirs=None,
):
    """Single-pass iterative os.scandir directory scanner supporting optional subfolder recursion."""
    extensions = extensions or readable_image_extensions()
    files = []
    last_report = time.monotonic()
    excluded = set()
    if excluded_dirs:
        for ex in excluded_dirs:
            if ex:
                excluded.add(norm_path_key(ex))

    root_norm = norm_path_key(folder_path)
    stack = [folder_path]
    visited_dirs = set()
    while stack:
        current_dir = stack.pop()
        if should_cancel is not None and should_cancel():
            return None
        norm_cur = norm_path_key(current_dir)
        if norm_cur in visited_dirs:
            continue
        visited_dirs.add(norm_cur)
        if norm_cur != root_norm and norm_cur in excluded:
            continue
        try:
            with os.scandir(current_dir) as entries:
                subdirs = []
                for entry in entries:
                    if should_cancel is not None and should_cancel():
                        return None
                    name = entry.name
                    try:
                        if include_subfolders and entry.is_dir(follow_symlinks=False):
                            if (
                                not name.startswith(".")
                                and name not in ("__pycache__", "$RECYCLE.BIN", "System Volume Information")
                            ):
                                sub_norm = norm_path_key(entry.path)
                                if sub_norm not in excluded:
                                    subdirs.append(entry.path)
                            continue
                        dot = name.rfind(".")
                        if dot <= 0 or name[dot:].lower() not in extensions:
                            continue
                        if not entry.is_file():
                            continue
                    except OSError:
                        continue
                    files.append(entry.path)
                    if on_progress is not None and len(files) % 500 == 0:
                        now = time.monotonic()
                        if now - last_report >= 0.15:
                            last_report = now
                            on_progress(len(files))
                if subdirs:
                    subdirs.sort(key=natural_sort_key, reverse=True)
                    stack.extend(subdirs)
        except OSError:
            if current_dir == folder_path:
                raise
            continue
    files.sort(key=natural_sort_key)
    return files
