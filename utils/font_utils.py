import os
import os.path as osp
import sys
from typing import Set, List, Iterable, Optional, Tuple, Dict

from qtpy.QtGui import QFontDatabase, QFont, QRawFont
from qtpy.QtCore import QStandardPaths

from utils.logger import logger as LOGGER
from utils import shared

# Cache for language support results: (family, target_lang) -> bool
_FONT_LANG_CACHE: Dict[Tuple[str, str], bool] = {}

# Set of already loaded font file paths to avoid redundant addApplicationFont calls
LOADED_FONT_PATHS: Set[str] = set()

FONT_EXTS = ('.ttf', '.otf', '.ttc', '.woff', '.woff2')

# Known legacy Windows bitmap / raster fonts that cause DirectWrite errors
BITMAP_FONT_FAMILIES = {
    'terminal', 'fixedsys', 'system', 'modern', 'roman', 'script',
    'courier', 'ms serif', 'ms sans serif', 'small fonts', 'wts vga',
    'marlett', 'app850', 'vga850', 'vgafix'
}


def is_scalable_font(family: str) -> bool:
    """Check if a font family is scalable (vector outline font) and safe for DirectWrite."""
    if not family:
        return False
    clean = family.strip().lower()
    if clean in BITMAP_FONT_FAMILIES:
        return False
    if clean.startswith('@') and clean[1:] in BITMAP_FONT_FAMILIES:
        return False
    try:
        return QFontDatabase.isScalable(family)
    except Exception:
        return False

# Language support definitions with WritingSystems and fallback sample glyphs
LANG_SUPPORT_SPEC: Dict[str, dict] = {
    # Korean
    '한국어': {
        'writing_systems': [QFontDatabase.WritingSystem.Korean],
        'sample_chars': ['가', '한', '글']
    },
    'korean': {
        'writing_systems': [QFontDatabase.WritingSystem.Korean],
        'sample_chars': ['가', '한', '글']
    },
    'ko': {
        'writing_systems': [QFontDatabase.WritingSystem.Korean],
        'sample_chars': ['가', '한', '글']
    },

    # Japanese
    '日本語': {
        'writing_systems': [QFontDatabase.WritingSystem.Japanese],
        'sample_chars': ['あ', 'カ', '日']
    },
    'japanese': {
        'writing_systems': [QFontDatabase.WritingSystem.Japanese],
        'sample_chars': ['あ', 'カ', '日']
    },
    'ja': {
        'writing_systems': [QFontDatabase.WritingSystem.Japanese],
        'sample_chars': ['あ', 'カ', '日']
    },

    # Simplified Chinese
    '简体中文': {
        'writing_systems': [QFontDatabase.WritingSystem.SimplifiedChinese],
        'sample_chars': ['国', '们', '中']
    },
    'simplified chinese': {
        'writing_systems': [QFontDatabase.WritingSystem.SimplifiedChinese],
        'sample_chars': ['国', '们', '中']
    },
    'zh-cn': {
        'writing_systems': [QFontDatabase.WritingSystem.SimplifiedChinese],
        'sample_chars': ['国', '们', '中']
    },
    'zh': {
        'writing_systems': [QFontDatabase.WritingSystem.SimplifiedChinese],
        'sample_chars': ['国', '们', '中']
    },

    # Traditional Chinese
    '繁體中文': {
        'writing_systems': [QFontDatabase.WritingSystem.TraditionalChinese],
        'sample_chars': ['國', '們', '繁']
    },
    'traditional chinese': {
        'writing_systems': [QFontDatabase.WritingSystem.TraditionalChinese],
        'sample_chars': ['國', '們', '繁']
    },
    'zh-tw': {
        'writing_systems': [QFontDatabase.WritingSystem.TraditionalChinese],
        'sample_chars': ['國', '們', '繁']
    },

    # Russian / Ukrainian / Cyrillic
    'русский язык': {
        'writing_systems': [QFontDatabase.WritingSystem.Cyrillic],
        'sample_chars': ['я', 'ж', 'Д']
    },
    'russian': {
        'writing_systems': [QFontDatabase.WritingSystem.Cyrillic],
        'sample_chars': ['я', 'ж', 'Д']
    },
    'ru': {
        'writing_systems': [QFontDatabase.WritingSystem.Cyrillic],
        'sample_chars': ['я', 'ж', 'Д']
    },
    'украї́нська мо́ва': {
        'writing_systems': [QFontDatabase.WritingSystem.Cyrillic],
        'sample_chars': ['ї', 'є', 'ґ']
    },
    'ukrainian': {
        'writing_systems': [QFontDatabase.WritingSystem.Cyrillic],
        'sample_chars': ['ї', 'є', 'ґ']
    },
    'uk': {
        'writing_systems': [QFontDatabase.WritingSystem.Cyrillic],
        'sample_chars': ['ї', 'є', 'ґ']
    },

    # Vietnamese
    'tiếng việt': {
        'writing_systems': [QFontDatabase.WritingSystem.Vietnamese, QFontDatabase.WritingSystem.Latin],
        'sample_chars': ['ế', 'ơ', 'à']
    },
    'vietnamese': {
        'writing_systems': [QFontDatabase.WritingSystem.Vietnamese, QFontDatabase.WritingSystem.Latin],
        'sample_chars': ['ế', 'ơ', 'à']
    },
    'vi': {
        'writing_systems': [QFontDatabase.WritingSystem.Vietnamese, QFontDatabase.WritingSystem.Latin],
        'sample_chars': ['ế', 'ơ', 'à']
    },

    # Thai
    'thai': {
        'writing_systems': [QFontDatabase.WritingSystem.Thai],
        'sample_chars': ['ก', 'ข']
    },
    'th': {
        'writing_systems': [QFontDatabase.WritingSystem.Thai],
        'sample_chars': ['ก', 'ข']
    },

    # Arabic
    'arabic': {
        'writing_systems': [QFontDatabase.WritingSystem.Arabic],
        'sample_chars': ['ع', 'ب']
    },
    'ar': {
        'writing_systems': [QFontDatabase.WritingSystem.Arabic],
        'sample_chars': ['ع', 'ب']
    },

    # Hindi
    'hindi': {
        'writing_systems': [QFontDatabase.WritingSystem.Devanagari],
        'sample_chars': ['क', 'ख']
    },
    'hi': {
        'writing_systems': [QFontDatabase.WritingSystem.Devanagari],
        'sample_chars': ['क', 'ख']
    },

    # Greek
    'greek': {
        'writing_systems': [QFontDatabase.WritingSystem.Greek],
        'sample_chars': ['α', 'Ω']
    },
    'el': {
        'writing_systems': [QFontDatabase.WritingSystem.Greek],
        'sample_chars': ['α', 'Ω']
    },

    # Hebrew
    'hebrew': {
        'writing_systems': [QFontDatabase.WritingSystem.Hebrew],
        'sample_chars': ['א', 'ב']
    },
    'he': {
        'writing_systems': [QFontDatabase.WritingSystem.Hebrew],
        'sample_chars': ['א', 'ב']
    },

    # Latin languages (English, German, French, Spanish, etc.)
    'latin': {
        'writing_systems': [QFontDatabase.WritingSystem.Latin],
        'sample_chars': ['A', 'e']
    },
    'english': {
        'writing_systems': [QFontDatabase.WritingSystem.Latin],
        'sample_chars': ['A', 'e']
    },
    'en': {
        'writing_systems': [QFontDatabase.WritingSystem.Latin],
        'sample_chars': ['A', 'e']
    },
    'français': {
        'writing_systems': [QFontDatabase.WritingSystem.Latin],
        'sample_chars': ['é', 'à']
    },
    'french': {
        'writing_systems': [QFontDatabase.WritingSystem.Latin],
        'sample_chars': ['é', 'à']
    },
    'deutsch': {
        'writing_systems': [QFontDatabase.WritingSystem.Latin],
        'sample_chars': ['ä', 'ö', 'ü']
    },
    'german': {
        'writing_systems': [QFontDatabase.WritingSystem.Latin],
        'sample_chars': ['ä', 'ö', 'ü']
    },
    'español': {
        'writing_systems': [QFontDatabase.WritingSystem.Latin],
        'sample_chars': ['ñ', 'á']
    },
    'spanish': {
        'writing_systems': [QFontDatabase.WritingSystem.Latin],
        'sample_chars': ['ñ', 'á']
    },
    'italiano': {
        'writing_systems': [QFontDatabase.WritingSystem.Latin],
        'sample_chars': ['a', 'e']
    },
    'italian': {
        'writing_systems': [QFontDatabase.WritingSystem.Latin],
        'sample_chars': ['a', 'e']
    },
    'polski': {
        'writing_systems': [QFontDatabase.WritingSystem.Latin],
        'sample_chars': ['ą', 'ę']
    },
    'polish': {
        'writing_systems': [QFontDatabase.WritingSystem.Latin],
        'sample_chars': ['ą', 'ę']
    },
    'português': {
        'writing_systems': [QFontDatabase.WritingSystem.Latin],
        'sample_chars': ['ã', 'õ']
    },
    'portuguese': {
        'writing_systems': [QFontDatabase.WritingSystem.Latin],
        'sample_chars': ['ã', 'õ']
    },
    'brazilian portuguese': {
        'writing_systems': [QFontDatabase.WritingSystem.Latin],
        'sample_chars': ['ã', 'õ']
    },
    'nederlands': {
        'writing_systems': [QFontDatabase.WritingSystem.Latin],
        'sample_chars': ['a', 'e']
    },
    'dutch': {
        'writing_systems': [QFontDatabase.WritingSystem.Latin],
        'sample_chars': ['a', 'e']
    },
    'čeština': {
        'writing_systems': [QFontDatabase.WritingSystem.Latin],
        'sample_chars': ['č', 'š']
    },
    'czech': {
        'writing_systems': [QFontDatabase.WritingSystem.Latin],
        'sample_chars': ['č', 'š']
    },
    'limba română': {
        'writing_systems': [QFontDatabase.WritingSystem.Latin],
        'sample_chars': ['ă', 'â']
    },
    'romanian': {
        'writing_systems': [QFontDatabase.WritingSystem.Latin],
        'sample_chars': ['ă', 'â']
    },
    'türk dili': {
        'writing_systems': [QFontDatabase.WritingSystem.Latin],
        'sample_chars': ['ğ', 'ş']
    },
    'turkish': {
        'writing_systems': [QFontDatabase.WritingSystem.Latin],
        'sample_chars': ['ğ', 'ş']
    },
    'magyar nyelv': {
        'writing_systems': [QFontDatabase.WritingSystem.Latin],
        'sample_chars': ['ő', 'ű']
    },
    'hungarian': {
        'writing_systems': [QFontDatabase.WritingSystem.Latin],
        'sample_chars': ['ő', 'ű']
    },
}


def clear_font_lang_cache():
    """Clear cached font language support results."""
    _FONT_LANG_CACHE.clear()


def get_font_writing_systems(family: str):
    """Retrieve supported writing systems for a font family."""
    if shared.FLAG_QT6:
        return QFontDatabase.writingSystems(family)
    else:
        try:
            return QFontDatabase.writingSystems(family)
        except TypeError:
            return QFontDatabase().writingSystems(family)


def get_all_font_families(only_scalable: bool = True) -> List[str]:
    """Retrieve font families registered in QFontDatabase, filtering out bitmap fonts by default."""
    if shared.FLAG_QT6:
        families = list(QFontDatabase.families())
    else:
        try:
            families = list(QFontDatabase.families())
        except TypeError:
            families = list(QFontDatabase().families())
    if only_scalable:
        families = [f for f in families if is_scalable_font(f)]
    return families


def is_font_supporting_language(family: str, target_lang: Optional[str]) -> bool:
    """
    Check if the given font family supports the target language.
    Uses QFontDatabase.writingSystems first, then falls back to QRawFont character support.
    Safely rejects non-scalable bitmap fonts to prevent DirectWrite errors.
    """
    if not family:
        return False

    # Never allow bitmap/raster fonts (like Terminal, Fixedsys, etc.)
    if not is_scalable_font(family):
        return False

    if not target_lang:
        return True

    lang_lower = target_lang.strip().lower()
    if lang_lower in ('', 'auto', 'none', 'any'):
        return True

    cache_key = (family, lang_lower)
    if cache_key in _FONT_LANG_CACHE:
        return _FONT_LANG_CACHE[cache_key]

    spec = LANG_SUPPORT_SPEC.get(lang_lower)
    if not spec:
        # Try substring match
        for key, val in LANG_SUPPORT_SPEC.items():
            if key in lang_lower or lang_lower in key:
                spec = val
                break

    if not spec:
        # Unknown target language, do not filter out
        _FONT_LANG_CACHE[cache_key] = True
        return True

    # 1. Primary check: QFontDatabase.writingSystems
    try:
        font_ws = get_font_writing_systems(family)
        for req_ws in spec['writing_systems']:
            if req_ws in font_ws:
                _FONT_LANG_CACHE[cache_key] = True
                return True
    except Exception as e:
        LOGGER.debug(f'Failed writingSystems check for font {family}: {e}')

    # 2. Fallback check: QRawFont character support (strictly for scalable fonts to avoid DirectWrite errors)
    try:
        if is_scalable_font(family):
            rf = QRawFont.fromFont(QFont(family))
            sample_chars = spec.get('sample_chars', [])
            if sample_chars and all(rf.supportsCharacter(c) for c in sample_chars):
                _FONT_LANG_CACHE[cache_key] = True
                return True
    except Exception as e:
        LOGGER.debug(f'Fallback glyph check failed for font {family}: {e}')

    _FONT_LANG_CACHE[cache_key] = False
    return False


def get_filtered_font_list(
    only_custom: bool = False,
    filter_by_lang: bool = False,
    target_lang: Optional[str] = None,
    current_font: Optional[str] = None
) -> List[str]:
    """
    Return a sorted list of font family names filtered by:
    - only_custom: whether to only show custom fonts from the fonts folder
    - filter_by_lang: whether to hide fonts that do not support target_lang
    - target_lang: the language to test support for
    - current_font: preserve current_font in the list even if filtered out
    """
    if only_custom:
        base_fonts = list(shared.CUSTOM_FONTS)
    else:
        base_fonts = list(shared.FONT_FAMILIES) if shared.FONT_FAMILIES else get_all_font_families()

    if filter_by_lang and target_lang:
        filtered = [f for f in base_fonts if is_font_supporting_language(f, target_lang)]
        # If filtering produces an empty list, fallback to base_fonts so user is not left with nothing
        if filtered:
            base_fonts = filtered

    # Sort case-insensitively, placing vertical '@' fonts at the end
    sorted_fonts = sorted(
        base_fonts,
        key=lambda x: (x.startswith('@'), x.lower())
    )

    # Ensure current_font is included if specified
    if current_font and current_font not in sorted_fonts:
        sorted_fonts.insert(0, current_font)

    return sorted_fonts


def find_font_files_recursive(dir_path: str) -> List[str]:
    """Recursively find all font files with supported extensions in dir_path."""
    font_files = []
    if not osp.exists(dir_path):
        return font_files

    for root, _, files in os.walk(dir_path):
        for file in files:
            if file.lower().endswith(FONT_EXTS):
                font_files.append(osp.join(root, file))
    return font_files


def reload_fonts(extra_dirs: Optional[List[str]] = None) -> Tuple[int, int]:
    """
    Scans project fonts directory, user font directories, and system font locations.
    Loads any newly found fonts into QFontDatabase and updates shared.CUSTOM_FONTS and shared.FONT_FAMILIES.

    Returns:
        (new_fonts_count, total_family_count)
    """
    global LOADED_FONT_PATHS
    search_dirs = []

    # 1. Project fonts folder
    project_fonts_dir = osp.abspath('fonts')
    if osp.exists(project_fonts_dir):
        search_dirs.append((project_fonts_dir, True))  # (path, is_custom)

    if extra_dirs:
        for ed in extra_dirs:
            if osp.exists(ed):
                search_dirs.append((osp.abspath(ed), True))

    # 2. Windows specific font directories (user-installed fonts without admin rights)
    if sys.platform == 'win32':
        user_fonts = os.path.expandvars(r'%LOCALAPPDATA%\Microsoft\Windows\Fonts')
        if osp.exists(user_fonts):
            search_dirs.append((osp.abspath(user_fonts), True))

    # 3. macOS / Linux specific font directories
    elif sys.platform == 'darwin':
        mac_dirs = [
            osp.expanduser('~/Library/Fonts'),
            '/Library/Fonts',
            '/System/Library/Fonts'
        ]
        for md in mac_dirs:
            if osp.exists(md):
                search_dirs.append((osp.abspath(md), False))
    else:
        linux_dirs = [
            osp.expanduser('~/.fonts'),
            osp.expanduser('~/.local/share/fonts'),
            '/usr/share/fonts',
            '/usr/local/share/fonts'
        ]
        for ld in linux_dirs:
            if osp.exists(ld):
                search_dirs.append((osp.abspath(ld), False))

    # Scan and load fonts
    new_fonts_loaded = 0
    custom_fonts_set = set(f for f in shared.CUSTOM_FONTS if is_scalable_font(f))

    for dir_path, is_custom in search_dirs:
        for fp in find_font_files_recursive(dir_path):
            norm_fp = osp.normcase(osp.abspath(fp))
            if norm_fp in LOADED_FONT_PATHS:
                continue

            fnt_idx = QFontDatabase.addApplicationFont(norm_fp)
            if fnt_idx >= 0:
                LOADED_FONT_PATHS.add(norm_fp)
                new_fonts_loaded += 1
                font_families = QFontDatabase.applicationFontFamilies(fnt_idx)
                if is_custom:
                    for ff in font_families:
                        if is_scalable_font(ff):
                            custom_fonts_set.add(ff)

    # Update shared variables (strictly scalable fonts only)
    shared.CUSTOM_FONTS = sorted(list(custom_fonts_set), key=lambda x: (x.startswith('@'), x.lower()))
    shared.FONT_FAMILIES = set(get_all_font_families(only_scalable=True))

    # Clear language cache so any new fonts are evaluated fresh
    clear_font_lang_cache()

    LOGGER.info(f'Fonts reloaded. Added {new_fonts_loaded} new font files. Total families: {len(shared.FONT_FAMILIES)}')
    return new_fonts_loaded, len(shared.FONT_FAMILIES)
