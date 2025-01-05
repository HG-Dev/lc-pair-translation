from typing import Iterator, Optional

def is_empty_or_whitespace(p: str) -> bool:
    #p = re.sub(r'\u2028|\u2029|\u00A0', ' ', p)
    return p.strip() == ''

def truncate(p: str, length: int, ellipse: Optional[str] = None) -> str:
    """ Truncate a string to a maximum length. """
    if len(p) <= length:
        return p
    return p[:length] + (ellipse or "")

def truncate_multi(ps: Iterator[str], length: int, ellipse: Optional[str] = None) -> str:
    """ Aggregate multiple strings into one string and truncate this result to a maximum length. """
    current_length = 0
    output = ""
    for p in ps:
        p_len = len(p)
        if (current_length + p_len) < (length - 1):
            current_length += p_len + 1
            output += p + '\n'
            continue
        # Approaching maximum length
        output += truncate(p, length - current_length, ellipse)
        break

    return output

def wrap_with_xml_tag(content: str, tag: str):
    wbreak = '\n' if '\n' in content else ""
    return f"<{tag}>{wbreak}{content}{wbreak}</{tag}>"