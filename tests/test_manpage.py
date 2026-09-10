from pathlib import Path
import re


def test_manpage_exists():
    manpage_path = Path(__file__).parent.parent / "model-constellation.1"
    assert manpage_path.exists(), "model-constellation.1 man page file does not exist"


def test_manpage_content_sections():
    manpage_path = Path(__file__).parent.parent / "model-constellation.1"
    content = manpage_path.read_text(encoding="utf-8")

    assert content.startswith(".\\\"") or ".TH MODEL-CONSTELLATION" in content
    assert ".TH MODEL-CONSTELLATION 1" in content
    assert ".SH NAME" in content
    assert "model-constellation" in content
    assert ".SH SYNOPSIS" in content
    assert ".SH DESCRIPTION" in content
    assert ".SH COMMANDS" in content
    assert ".SH GLOBAL OPTIONS" in content
    assert ".SH ENVIRONMENT VARIABLES" in content
    assert ".SH FILES" in content
    assert ".SH EXAMPLES" in content
    assert ".SH SEE ALSO" in content
    assert ".SH AUTHOR" in content


def test_setup_py_contains_manpage_data_files():
    setup_path = Path(__file__).parent.parent / "setup.py"
    assert setup_path.exists(), "setup.py file does not exist"
    content = setup_path.read_text(encoding="utf-8")

    assert "data_files" in content
    assert "share/man/man1" in content
    assert "model-constellation.1" in content


def test_install_sh_references_manpage():
    install_path = Path(__file__).parent.parent / "install.sh"
    assert install_path.exists(), "install.sh file does not exist"
    content = install_path.read_text(encoding="utf-8")

    assert "model-constellation.1" in content
