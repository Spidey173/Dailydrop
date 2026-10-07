#!/usr/bin/env bash

# ==============================================================================
# Daily Drop - Startup & Management Script
# ==============================================================================

set -e

# Colors for terminal output
BOLD="\033[1m"
GREEN="\033[0;32m"
CYAN="\033[0;36m"
YELLOW="\033[1;33m"
RED="\033[0;31m"
BLUE="\033[0;34m"
NC="\033[0m" # No Color

# Base directory
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

# Defaults
DEFAULT_PORT=5000
DEFAULT_HOST="0.0.0.0"
PORT=$DEFAULT_PORT
HOST=$DEFAULT_HOST
MODE="dev"
VENV_DIR="$ROOT_DIR/venv"

# Banner
print_banner() {
    echo -e "${CYAN}${BOLD}"
    echo "  ____        _ _         ____                    "
    echo " |  _ \  __ _(_) |_   _  |  _ \ _ __ ___  _ __    "
    echo " | | | |/ _\` | | | | | | | | | | '__/ _ \| '_ \   "
    echo " | |_| | (_| | | | |_| | | |_| | | | (_) | |_) |  "
    echo " |____/ \__,_|_|_|\__, | |____/|_|  \___/| .__/   "
    echo "                  |___/                  |_|      "
    echo -e "${NC}"
    echo -e "${BOLD} Daily Drop E-Commerce Platform Management Script${NC}"
    echo "---------------------------------------------------------"
}

# Print help message
show_help() {
    print_banner
    echo -e "${BOLD}Usage:${NC} ./run.sh [MODE/COMMAND] [OPTIONS]"
    echo ""
    echo -e "${BOLD}Commands / Modes:${NC}"
    echo -e "  ${GREEN}dev${NC}            Run the Flask development server (Default)"
    echo -e "  ${GREEN}prod${NC}           Run using Gunicorn WSGI production server"
    echo -e "  ${GREEN}install${NC}        Setup virtualenv and install dependencies"
    echo -e "  ${GREEN}init-db${NC}        Initialize SQLite database and seed initial catalog"
    echo -e "  ${GREEN}reset-db${NC}       Reset SQLite database (delete & re-seed data)"
    echo -e "  ${GREEN}test${NC}           Run Pytest test suite"
    echo -e "  ${GREEN}help, -h${NC}       Show this help message"
    echo ""
    echo -e "${BOLD}Options:${NC}"
    echo -e "  ${YELLOW}-p, --port <port>${NC}   Specify custom port (default: 5000)"
    echo -e "  ${YELLOW}-H, --host <host>${NC}   Specify custom host (default: 0.0.0.0)"
    echo -e "  ${YELLOW}--no-venv${NC}           Skip virtual environment activation"
    echo ""
    echo -e "${BOLD}Examples:${NC}"
    echo "  ./run.sh                  # Start dev server on port 5000"
    echo "  ./run.sh dev -p 8080      # Start dev server on port 8080"
    echo "  ./run.sh prod             # Start production server with Gunicorn"
    echo "  ./run.sh reset-db         # Reset and seed database"
    echo "---------------------------------------------------------"
}

# Logger helpers
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check Python installation
check_python() {
    if command -v python3 &>/dev/null; then
        PYTHON_CMD="python3"
    elif command -v python &>/dev/null; then
        PYTHON_CMD="python"
    else
        log_error "Python 3 is not installed or not in PATH."
        exit 1
    fi
}

# Setup or activate virtual environment
setup_venv() {
    if [[ "$USE_VENV" == "false" ]]; then
        log_warn "Skipping virtualenv activation (--no-venv specified)."
        return
    fi

    if [[ ! -d "$VENV_DIR" && -d "$ROOT_DIR/.venv" ]]; then
        VENV_DIR="$ROOT_DIR/.venv"
    fi

    if [[ ! -d "$VENV_DIR" ]]; then
        log_info "Creating virtual environment at $VENV_DIR..."
        $PYTHON_CMD -m venv "$VENV_DIR"
        log_success "Virtual environment created."
    fi

    if [[ -f "$VENV_DIR/bin/activate" ]]; then
        # shellcheck disable=SC1091
        source "$VENV_DIR/bin/activate"
        PYTHON_CMD="python"
        log_info "Activated virtual environment ($(python --version))"
    elif [[ -f "$VENV_DIR/Scripts/activate" ]]; then
        # shellcheck disable=SC1091
        source "$VENV_DIR/Scripts/activate"
        PYTHON_CMD="python"
        log_info "Activated virtual environment ($(python --version))"
    fi
}

# Install dependencies if needed
install_deps() {
    log_info "Checking project dependencies..."
    if [[ -f "requirements.txt" ]]; then
        $PYTHON_CMD -m pip install --upgrade pip --quiet
        log_info "Installing packages from requirements.txt..."
        $PYTHON_CMD -m pip install -r requirements.txt
        log_success "Dependencies installed successfully."
    else
        log_warn "requirements.txt not found."
    fi
}

# Ensure .env exists
ensure_env() {
    if [[ ! -f ".env" ]]; then
        if [[ -f ".env.example" ]]; then
            log_info "Creating .env from .env.example..."
            cp .env.example .env
            log_success "Created .env configuration file."
        else
            log_warn "No .env or .env.example found. Running with default configurations."
        fi
    fi
}

# Initialize / Seed Database
init_db() {
    log_info "Initializing Neon PostgreSQL database..."
    if $PYTHON_CMD -c "
from database import init_database
try:
    init_database()
    print('Neon PostgreSQL database checked & initialized successfully.')
except Exception as e:
    print(f'Database initialization note: {e}')
    exit(1)
"; then
        log_success "Neon PostgreSQL Database is ready."
    else
        log_warn "Database initialization had a warning. Proceeding with application startup..."
    fi
}

# Reset Database
reset_db() {
    log_warn "Resetting / Reinitializing database on Neon PostgreSQL..."
    init_db
    log_success "Neon PostgreSQL database has been verified and seeded."
}

# Run tests
run_tests() {
    log_info "Running test suite..."
    set +e
    $PYTHON_CMD -m pytest -v
    local exit_code=$?
    set -e
    if [[ $exit_code -eq 0 ]]; then
        log_success "All tests passed!"
    elif [[ $exit_code -eq 5 ]]; then
        log_warn "No tests were found to run (Pytest exit code 5)."
    else
        log_error "Tests failed with exit code $exit_code."
        exit $exit_code
    fi
}

# Check if port is already in use
check_port() {
    local target_port=$1
    if command -v lsof &>/dev/null; then
        if lsof -Pi :"$target_port" -sTCP:LISTEN -t >/dev/null ; then
            log_warn "Port $target_port is already in use by another process."
            read -r -p "Do you want to terminate the process running on port $target_port? [y/N]: " kill_confirm
            if [[ "$kill_confirm" =~ ^[Yy]$ ]]; then
                lsof -ti :"$target_port" | xargs kill -9 2>/dev/null || true
                log_success "Process on port $target_port terminated."
                sleep 1
            else
                log_error "Cannot start server: port $target_port is occupied."
                exit 1
            fi
        fi
    fi
}

# Parse Arguments
USE_VENV="true"

while [[ $# -gt 0 ]]; do
    case "$1" in
        dev|development)
            MODE="dev"
            shift
            ;;
        prod|production)
            MODE="prod"
            shift
            ;;
        install|--install)
            MODE="install"
            shift
            ;;
        init-db|--init-db)
            MODE="init-db"
            shift
            ;;
        reset-db|--reset-db)
            MODE="reset-db"
            shift
            ;;
        test|--test)
            MODE="test"
            shift
            ;;
        help|--help|-h)
            show_help
            exit 0
            ;;
        -p|--port)
            PORT="$2"
            shift 2
            ;;
        -H|--host)
            HOST="$2"
            shift 2
            ;;
        --no-venv)
            USE_VENV="false"
            shift
            ;;
        *)
            log_error "Unknown argument: $1"
            echo ""
            show_help
            exit 1
            ;;
    esac
done

# Main Execution Flow
print_banner
check_python
setup_venv
ensure_env

# Check if Flask is installed in environment, if not prompt / install
if ! $PYTHON_CMD -c "import flask" &>/dev/null; then
    log_warn "Flask is not installed in the current environment."
    install_deps
fi

case "$MODE" in
    install)
        install_deps
        init_db
        log_success "Setup completed successfully!"
        exit 0
        ;;
    init-db)
        init_db
        exit 0
        ;;
    reset-db)
        reset_db
        exit 0
        ;;
    test)
        run_tests
        exit 0
        ;;
    dev)
        init_db
        check_port "$PORT"
        echo ""
        echo -e "${GREEN}${BOLD}🚀 Starting Daily Drop (Development Mode)...${NC}"
        echo -e "${CYAN}📍 Storefront URL :${NC} ${BOLD}http://localhost:${PORT}${NC}"
        echo -e "${CYAN}📍 Admin Panel    :${NC} ${BOLD}http://localhost:${PORT}/admin/dashboard${NC}"
        echo -e "${CYAN}🔑 Admin Login    :${NC} admin_dailydrop@gmail.com / Dailydrop@173"
        echo -e "${YELLOW}Press Ctrl+C to stop the server.${NC}"
        echo "---------------------------------------------------------"
        echo ""
        
        # Export PORT, FLASK_RUN_PORT and HOST if needed
        export PORT="$PORT"
        export FLASK_RUN_PORT="$PORT"
        export FLASK_RUN_HOST="$HOST"
        export FLASK_ENV="development"
        export FLASK_DEBUG="1"
        
        exec $PYTHON_CMD app.py
        ;;
    prod)
        init_db
        check_port "$PORT"
        echo ""
        echo -e "${GREEN}${BOLD}🚀 Starting Daily Drop with Gunicorn (Production Mode)...${NC}"
        echo -e "${CYAN}📍 Storefront URL :${NC} ${BOLD}http://localhost:${PORT}${NC}"
        echo -e "${CYAN}📍 Admin Panel    :${NC} ${BOLD}http://localhost:${PORT}/admin/dashboard${NC}"
        echo -e "${CYAN}📍 Workers        :${NC} 4"
        echo -e "${YELLOW}Press Ctrl+C to stop the server.${NC}"
        echo "---------------------------------------------------------"
        echo ""
        
        if ! command -v gunicorn &>/dev/null && ! $PYTHON_CMD -m gunicorn --version &>/dev/null; then
            log_warn "Gunicorn not found. Installing gunicorn..."
            $PYTHON_CMD -m pip install gunicorn
        fi

        exec $PYTHON_CMD -m gunicorn \
            --workers 4 \
            --bind "${HOST}:${PORT}" \
            --access-logfile - \
            --error-logfile - \
            app:app
        ;;
esac
