import re
import weakref

from wappalyzer.core.matcher import parse_pattern

# A selector can only match if every tag, id, class and attribute name it
# names exists somewhere in the document, and every attribute value it tests
# occurs inside some attribute value. Checking that against data collected in
# one pass over the tree lets most selectors skip soupsieve's full-tree walk.
# Selectors this simple parser does not fully understand are always run.
_QUOTED = re.compile(r'"([^"]*)"|\'([^\']*)\'')
_ATTR = re.compile(r'\[\s*(-?[_a-zA-Z][\w\-]*)\s*(?:[~^$*|]?=\s*("\d+"|[\w\-]+)\s*(?:[iIsS]\s*)?)?\]')
_NAME = re.compile(r'([#.]?)(-?[_a-zA-Z][\w\-]*)')
_REST = re.compile(r'^[\w\s\-#.>+~*]*$')

_last = (None, None)  # (weakref to the last document, what it contains)


def _doc_tokens(soup):
    global _last
    ref, tokens = _last
    if ref is None or ref() is not soup:
        tags, ids, classes, attrs, values = set(), set(), set(), set(), []
        for el in soup.find_all(True):
            tags.add(el.name.lower())
            for name, value in el.attrs.items():
                name = name.lower()
                attrs.add(name)
                words = value if isinstance(value, list) else str(value).split()
                values.append(' '.join(value) if isinstance(value, list) else str(value))
                if name == 'id':
                    ids.add(str(value).lower())
                elif name == 'class':
                    classes.update(w.lower() for w in words)
        tokens = (tags, ids, classes, attrs, '\n'.join(values).lower())
        _last = (weakref.ref(soup), tokens)
    return tokens


def _may_match(soup, selector):
    """False only when the selector cannot match this document."""
    if '\\' in selector:
        return True
    quoted = []

    def stash(m):
        quoted.append(m.group(1) if m.group(1) is not None else m.group(2))
        return '"%d"' % (len(quoted) - 1)

    bare = _QUOTED.sub(stash, selector)
    tags, ids, classes, attrs, values = None, None, None, None, None
    for alternative in bare.split(','):
        needed = _ATTR.findall(alternative)
        rest = _ATTR.sub(' ', alternative)
        if not _REST.match(rest):
            return True
        if tags is None:
            tags, ids, classes, attrs, values = _doc_tokens(soup)
        possible = True
        for attr, value in needed:
            if value.startswith('"'):
                value = quoted[int(value[1:-1])]
            if attr.lower() not in attrs or value.lower() not in values:
                possible = False
        for prefix, name in _NAME.findall(rest):
            pool = ids if prefix == '#' else classes if prefix == '.' else tags
            if name.lower() not in pool:
                possible = False
        if possible:
            return True
    return False


def query(soup, selector):
    try:
        if not _may_match(soup, selector):
            return []
        return soup.select(selector)
    except Exception as e:
        return False

def match_dom(selectors, soup):
    if type(selectors) == str:
        clean_selector, version_type, confidence = parse_pattern(selectors)
        return query(soup, clean_selector), '', confidence
    elif type(selectors) == list:
        for selector in selectors:
            clean_selector, version_type, confidence = parse_pattern(selector)
            if query(soup, clean_selector):
                return True, '', confidence
    elif type(selectors) == dict:
        for name, selector in selectors.items():
            clean_selector, version_type, confidence = parse_pattern(selector)
            if query(soup, clean_selector):
                return True, '', confidence
    return False, '', 0