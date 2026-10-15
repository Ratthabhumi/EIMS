"""Content checks for untrusted evidence, independent of storage or execution."""
import ntpath

TEXT_EXTENSIONS = frozenset({'.txt', '.log', '.xml', '.csv', '.html', '.htm', '.json'})
IMAGE_EXTENSIONS = frozenset({'.png', '.jpg', '.jpeg'})


def validate_evidence_upload(filename: str, content: bytes, *, allow_images: bool = False) -> str:
    if any(ord(c) < 32 or ord(c) == 127 for c in (filename or '')):
        raise ValueError('Filename contains invalid control characters.')
    base = ntpath.basename((filename or '').replace('/', '\\')).strip()
    if not base or ':' in base or len(base) > 255:
        raise ValueError('Provide a valid evidence filename without alternate streams.')
    ext = ntpath.splitext(base)[1].lower()
    allowed = TEXT_EXTENSIONS | {'.evtx'} | (IMAGE_EXTENSIONS if allow_images else set())
    if ext not in allowed:
        raise ValueError('Unsupported evidence file type. Allowed: ' + ', '.join(sorted(allowed)))
    if not content:
        raise ValueError('The evidence file is empty.')
    if ext == '.evtx':
        if not content.startswith(b'ElfFile\x00'):
            raise ValueError('The file does not have a Windows EVTX signature.')
    elif ext in IMAGE_EXTENSIONS:
        import io
        from PIL import Image
        try:
            with Image.open(io.BytesIO(content)) as image:
                expected = 'PNG' if ext == '.png' else 'JPEG'
                if image.format != expected or image.width * image.height > 8_000_000:
                    raise ValueError('Image format does not match its extension or exceeds 8 million pixels.')
                image.verify()
        except (OSError, SyntaxError, Image.DecompressionBombError) as exc:
            raise ValueError('Invalid or oversized evidence image.') from exc
    else:
        try:
            text = content.decode('utf-8-sig')
        except UnicodeDecodeError as exc:
            raise ValueError('Text evidence must be UTF-8 encoded.') from exc
        if '\x00' in text:
            raise ValueError('Binary content is not supported as text evidence.')
    return base
