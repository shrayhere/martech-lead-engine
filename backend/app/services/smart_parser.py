import io
import csv
import pandas as pd
from typing import Tuple, Dict, Any

MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024  # 20 MB limit
MAX_ROW_COUNT = 100_000  # 100,000 rows limit

CANDIDATE_ENCODINGS = ["utf-8-sig", "utf-8", "latin-1", "cp1252", "iso-8859-1"]
CANDIDATE_DELIMITERS = [",", ";", "\t", "|"]

def is_binary_content(sample_bytes: bytes) -> bool:
    """Checks if raw content contains null bytes indicating a non-text binary file."""
    if b"\x00" in sample_bytes[:4096]:
        return True
    return False

def detect_encoding_and_decode(file_bytes: bytes) -> Tuple[str, str]:
    """
    Attempts decoding raw bytes using priority encodings:
    1. utf-8-sig (handles UTF-8 with BOM)
    2. utf-8
    3. latin-1 (lossless byte fallback)
    4. cp1252
    """
    if not file_bytes or len(file_bytes.strip()) == 0:
        raise ValueError("Uploaded file is empty (0 bytes).")

    if is_binary_content(file_bytes):
        raise ValueError("Uploaded file appears to be a binary file, not a valid CSV text document.")

    for enc in CANDIDATE_ENCODINGS:
        try:
            decoded_text = file_bytes.decode(enc)
            return decoded_text, enc
        except UnicodeDecodeError:
            continue

    # Fallback with replacement
    return file_bytes.decode("latin-1", errors="replace"), "latin-1"

def detect_delimiter(text_sample: str) -> str:
    """
    Sniffs delimiter from candidate set [',', ';', '\t', '|'].
    Uses csv.Sniffer with safe heuristic fallback based on candidate frequencies.
    """
    lines = [line.strip() for line in text_sample.splitlines() if line.strip()][:25]
    if not lines:
        return ","

    sample_block = "\n".join(lines)
    try:
        sniffer = csv.Sniffer()
        dialect = sniffer.sniff(sample_block, delimiters=";,|\t")
        if dialect.delimiter in CANDIDATE_DELIMITERS:
            return dialect.delimiter
    except Exception:
        pass

    # Heuristic frequency counter across the non-empty lines
    delimiter_counts = {d: 0 for d in CANDIDATE_DELIMITERS}
    for line in lines:
        for d in CANDIDATE_DELIMITERS:
            delimiter_counts[d] += line.count(d)

    best_delimiter = max(delimiter_counts, key=delimiter_counts.get)
    return best_delimiter if delimiter_counts[best_delimiter] > 0 else ","

def check_missing_headers(text: Any, delimiter: str = ",") -> bool:
    """
    Detects if the first line of CSV appears to be data rather than headers:
    e.g. contains '@' (email), digits > 5 (phone), dates (YYYY-MM-DD), numbers.
    """
    if isinstance(text, bytes):
        text = text.decode("utf-8", errors="ignore")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return False
    first_line = lines[0]
    # Simple delimiter split
    cells = [c.strip().strip('"').strip("'") for c in first_line.split(delimiter)]
    data_indicators = 0
    for cell in cells:
        if "@" in cell:
            data_indicators += 1
        elif cell.isdigit() and len(cell) >= 5:
            data_indicators += 1
        elif any(c in cell for c in ["-", "/"]) and any(ch.isdigit() for ch in cell) and len(cell) in (8, 9, 10):
            data_indicators += 1
        elif cell.replace(".", "", 1).isdigit() and len(cell) <= 4:
            # Score or company size
            data_indicators += 1

    return data_indicators >= 2


def parse_csv_file(
    file_bytes: bytes,
    filename: str = "upload.csv",
    has_no_headers: bool = False
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Robust CSV / Excel parser:
    - Enforces 20MB file size limit and 100,000 rows limit.
    - Supports CSV, TSV, and Excel (.xlsx, .xls) files.
    - Autodetects encoding (utf-8, utf-8-sig, latin-1, etc.).
    - Autodetects delimiter (comma, semicolon, tab, pipe).
    - Detects missing header rows and supports has_no_headers mode.
    - Gracefully handles quoted multiline fields, blank lines, and ragged rows without crashing.
    - Returns (DataFrame, parse_metadata).
    """
    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        raise ValueError(
            f"File size exceeds 20 MB limit (received {len(file_bytes) / (1024*1024):.2f} MB)."
        )

    lower_fn = filename.lower()
    if lower_fn.endswith(".xlsx") or lower_fn.endswith(".xls"):
        try:
            df = pd.read_excel(io.BytesIO(file_bytes), dtype=str, header=None if has_no_headers else 0)
        except Exception as e:
            raise ValueError(f"Failed to parse Excel file: {str(e)}")

        cleaned_cols = []
        seen = {}
        for i, col in enumerate(df.columns):
            c_str = str(col).strip().strip('"').strip("'")
            if not c_str or c_str.startswith("Unnamed:") or has_no_headers:
                c_str = f"column_{i+1}"
            if c_str in seen:
                seen[c_str] += 1
                c_str = f"{c_str}_{seen[c_str]}"
            else:
                seen[c_str] = 0
            cleaned_cols.append(c_str)
        df.columns = cleaned_cols

        parse_meta = {
            "filename": filename,
            "encoding": "binary-excel",
            "delimiter": "n/a",
            "total_parsed_rows": len(df),
            "total_columns": len(df.columns),
            "detected_headers": list(df.columns),
            "has_no_headers": has_no_headers
        }
        return df, parse_meta

    decoded_text, detected_encoding = detect_encoding_and_decode(file_bytes)
    
    # Strip leading/trailing blank lines
    cleaned_text = decoded_text.strip()
    if not cleaned_text:
        raise ValueError("Uploaded CSV file contains no readable text or rows.")

    detected_delim = detect_delimiter(cleaned_text[:8192])
    detected_missing_headers = check_missing_headers(cleaned_text[:4096], detected_delim)
    use_no_header = has_no_headers or detected_missing_headers

    try:
        df = pd.read_csv(
            io.StringIO(cleaned_text),
            sep=detected_delim,
            header=None if use_no_header else 0,
            dtype=str,
            on_bad_lines="skip",
            skip_blank_lines=True,
            quotechar='"',
            escapechar="\\",
            engine="python",
        )
    except Exception as e:
        try:
            df = pd.read_csv(
                io.StringIO(cleaned_text),
                sep=detected_delim,
                header=None if use_no_header else 0,
                dtype=str,
                on_bad_lines="skip",
                skip_blank_lines=True
            )
        except Exception as retry_err:
            raise ValueError(f"Failed to parse CSV file: {str(retry_err)}")

    if df.empty or len(df.columns) == 0:
        raise ValueError("Uploaded CSV file has no recognizable tabular rows or columns.")

    if len(df) > MAX_ROW_COUNT:
        raise ValueError(
            f"Uploaded file exceeds the maximum limit of 100,000 rows (received {len(df):,} rows)."
        )

    # Clean column names
    cleaned_cols = []
    seen = {}
    for i, col in enumerate(df.columns):
        if use_no_header:
            c_str = f"column_{i+1}"
        else:
            c_str = str(col).strip().strip('"').strip("'")
            if not c_str or c_str.startswith("Unnamed:"):
                c_str = f"column_{i+1}"
        if c_str in seen:
            seen[c_str] += 1
            c_str = f"{c_str}_{seen[c_str]}"
        else:
            seen[c_str] = 0
        cleaned_cols.append(c_str)
    df.columns = cleaned_cols

    parse_meta = {
        "filename": filename,
        "encoding": detected_encoding,
        "delimiter": detected_delim,
        "total_parsed_rows": len(df),
        "total_columns": len(df.columns),
        "detected_headers": list(df.columns),
        "missing_headers_detected": detected_missing_headers,
        "has_no_headers": use_no_header
    }

    return df, parse_meta
