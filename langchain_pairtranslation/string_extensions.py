from typing import Iterator, Optional

def is_empty_or_whitespace(p: str) -> bool:
    #p = re.sub(r'\u2028|\u2029|\u00A0', ' ', p)
    return p.strip() == ''

def take(p: str, length: int, ellipse: Optional[str] = None) -> str:
    if len(p) <= length:
        return p
    return p[:length] + (ellipse or "")

def take_multi(ps: Iterator[str], length: int, ellipse: Optional[str] = None) -> str:
    current_length = 0
    output = ""
    for p in ps:
        p_len = len(p)
        if (current_length + p_len) < (length - 1):
            current_length += p_len + 1
            output += p + '\n'
            continue
        # Approaching maximum length
        output += take(p, length - current_length, ellipse)
        break

    return output

def wrap_with_xml_tag(content: str, tag: str):
    wbreak = '\n' if '\n' in content else ""
    return f"<{tag}>{wbreak}{content}{wbreak}</{tag}>"