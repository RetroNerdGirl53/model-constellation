#!/bin/bash

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PACKAGE_NAME="model_constellation"
BINARY_NAME="model-constellation"
ENTRY_POINT="model_constellation.core:main"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_info() {
    echo -e "[INFO] $1"
}

check_python_version() {
    print_info "Checking Python version..."
    
    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 is not installed. Please install Python 3.10 or higher."
        exit 1
    fi
    
    PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
    PYTHON_MAJOR=$(python3 -c 'import sys; print(sys.version_info[0])')
    PYTHON_MINOR=$(python3 -c 'import sys; print(sys.version_info[1])')
    
    PYTHON_OK=$(python3 -c 'import sys; print(1 if sys.version_info >= (3, 10) else 0)')
    if [ "$PYTHON_OK" -eq 0 ]; then
        print_error "Python $PYTHON_VERSION is too old. Python 3.10+ is required."
        exit 1
    fi
    
    print_success "Python $PYTHON_VERSION detected"
}

check_pip() {
    print_info "Checking pip..."
    
    if ! python3 -m pip --version &> /dev/null; then
        print_error "pip is not installed. Please install pip."
        exit 1
    fi
    
    print_success "pip is available"
}

install_dependencies() {
    print_info "Installing dependencies..."
    
    cd "$SCRIPT_DIR"
    
    if [ -n "$VIRTUAL_ENV" ]; then
        print_info "Detected virtualenv, installing without --user flag"
        python3 -m pip install -e .
    elif [ "$SYSTEM_WIDE" -eq 1 ]; then
        python3 -m pip install -e . --break-system-packages 2>/dev/null || \
        python3 -m pip install -e .
    else
        python3 -m pip install -e . --user
    fi
    
    if [ $? -eq 0 ]; then
        print_success "Dependencies installed"
    else
        print_error "Failed to install dependencies"
        exit 1
    fi
}

get_man_dir() {
    if [ "$SYSTEM_WIDE" -eq 1 ]; then
        echo "/usr/share/man/man1"
    else
        echo "$HOME/.local/share/man/man1"
    fi
}

get_bin_dir() {
    if [ "$SYSTEM_WIDE" -eq 1 ]; then
        echo "/usr/local/bin"
    else
        echo "$HOME/.local/bin"
    fi
}

install_man_page() {
    print_info "Installing man page..."
    
    MAN_DIR=$(get_man_dir)
    MAN_FILE="$MAN_DIR/$BINARY_NAME.1"
    SOURCE_MAN_PAGE="$SCRIPT_DIR/model_constellation.1"
    
    mkdir -p "$MAN_DIR"
    
    if [ -f "$SOURCE_MAN_PAGE" ]; then
        cp "$SOURCE_MAN_PAGE" "$MAN_FILE"
        print_info "Copied man page from $SOURCE_MAN_PAGE"
    else
        print_warning "Man page not found at $SOURCE_MAN_PAGE, creating minimal fallback"
        
        cat > "$MAN_FILE" << 'MANPAGE'
.TH MODEL_CONSTELLATION 1 "2024" "model-constellation" "User Commands"
.SH NAME
model-constellation \- Ollama-powered CLI AI agent framework
.SH SYNOPSIS
.B model-constellation
[\fIOPTIONS\fP] [\fICOMMAND\fP]
.SH DESCRIPTION
model-constellation is a powerful CLI framework that brings AI agent capabilities to your terminal.
.SH OPTIONS
.TP
\fB\-h, \-\-help\fP
Show help message and exit
.TP
\fB\-\-version\fP
Show version information
.SH SEE ALSO
Python(1), Ollama documentation
.SH AUTHOR
model-constellation Team
.SH LICENSE
MIT
MANPAGE
    fi
    
    if command -v gzip &> /dev/null; then
        gzip -k -f "$MAN_FILE" 2>/dev/null || true
    fi
    
    print_success "Man page installed to $MAN_FILE"
}

create_wrapper_script() {
    print_info "Creating wrapper script..."
    
    BIN_DIR=$(get_bin_dir)
    WRAPPER_PATH="$BIN_DIR/$BINARY_NAME"
    
    mkdir -p "$BIN_DIR"
    
    PYTHON_PATH=$(python3 -c "import sys; print(sys.executable)")
    
    cat > "$WRAPPER_PATH" << WRAPPER
#!/bin/bash
exec -a model-constellation "$PYTHON_PATH" -m model_constellation.core "\$@"
WRAPPER
    
    chmod +x "$WRAPPER_PATH"
    
    if [ "$SYSTEM_WIDE" -eq 0 ]; then
        if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
            print_warning "User bin directory not in PATH. Add this to your shell profile:"
            echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
        fi
    fi
    
    print_success "Wrapper script created at $WRAPPER_PATH"
}

check_installation() {
    print_info "Verifying installation..."
    
    if command -v "$BINARY_NAME" &> /dev/null; then
        print_success "$BINARY_NAME is available"
        "$BINARY_NAME" --version 2>/dev/null || print_warning "Could not get version (this is normal for editable installs)"
    else
        print_warning "$BINARY_NAME not found in PATH. You may need to restart your shell."
    fi
}

usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --user         Install for current user only (default)"
    echo "  --system       Install system-wide (requires root)"
    echo "  --help         Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0              # Install for current user"
    echo "  $0 --user       # Install for current user"
    echo "  $0 --system     # Install system-wide"
}

SYSTEM_WIDE=0

while [[ $# -gt 0 ]]; do
    case $1 in
        --user)
            SYSTEM_WIDE=0
            shift
            ;;
        --system)
            SYSTEM_WIDE=1
            shift
            ;;
        --help)
            usage
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

if [ "$SYSTEM_WIDE" -eq 1 ]; then
    if [ "$(id -u)" -ne 0 ]; then
        print_error "System-wide installation requires root. Run with sudo or use --user."
        exit 1
    fi
fi

echo "=========================================="
echo "  model-constellation Installer"
echo "=========================================="
echo ""

check_python_version
check_pip
install_dependencies
install_man_page
create_wrapper_script
check_installation

echo ""
echo "=========================================="
print_success "Installation complete!"
echo "=========================================="
echo ""
echo "Run 'model-constellation --help' to get started."
echo ""
if [ "$SYSTEM_WIDE" -eq 0 ]; then
    echo "Note: If 'model-constellation' is not found, add ~/.local/bin to your PATH:"
    echo "  echo 'export PATH=\"\$HOME/.local/bin:\$PATH\"' >> ~/.bashrc"
    echo "  source ~/.bashrc"
fi
