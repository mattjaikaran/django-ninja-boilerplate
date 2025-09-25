#!/bin/bash

# Database setup and management script for Django Ninja Boilerplate

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if Docker services are running
check_services() {
    if ! docker-compose ps | grep -q "Up"; then
        print_error "Docker services are not running. Please start them with 'make up'"
        exit 1
    fi
}

# Function to run migrations
run_migrations() {
    print_info "Running database migrations..."
    docker-compose exec django python manage.py migrate
    print_success "Migrations completed!"
}

# Function to create migrations
create_migrations() {
    print_info "Creating new migrations..."
    docker-compose exec django python manage.py makemigrations
    print_success "Migrations created!"
}

# Function to reset database (DANGEROUS!)
reset_database() {
    print_warning "This will DELETE ALL DATA in the database!"
    read -p "Are you absolutely sure? Type 'YES' to continue: " confirm
    
    if [ "$confirm" != "YES" ]; then
        print_info "Operation cancelled."
        exit 0
    fi
    
    print_info "Stopping services..."
    docker-compose down
    
    print_info "Removing database volume..."
    docker volume rm django-ninja-boilerplate_postgres_data 2>/dev/null || true
    
    print_info "Starting services..."
    docker-compose up -d
    
    print_info "Waiting for database to be ready..."
    sleep 10
    
    print_info "Running migrations..."
    docker-compose exec django python manage.py migrate
    
    print_info "Generating core data..."
    docker-compose exec django python manage.py generate_core_data
    
    print_success "Database reset complete!"
}

# Function to backup database
backup_database() {
    local backup_file="backup_$(date +%Y%m%d_%H%M%S).sql"
    
    print_info "Creating database backup: $backup_file"
    docker-compose exec db pg_dump -U postgres boilerplate_db > "$backup_file"
    print_success "Database backup created: $backup_file"
}

# Function to restore database
restore_database() {
    local backup_file="$1"
    
    if [ -z "$backup_file" ]; then
        print_error "Please specify a backup file to restore"
        echo "Usage: $0 restore <backup_file.sql>"
        exit 1
    fi
    
    if [ ! -f "$backup_file" ]; then
        print_error "Backup file not found: $backup_file"
        exit 1
    fi
    
    print_warning "This will REPLACE ALL DATA in the database!"
    read -p "Are you sure? Type 'YES' to continue: " confirm
    
    if [ "$confirm" != "YES" ]; then
        print_info "Operation cancelled."
        exit 0
    fi
    
    print_info "Restoring database from: $backup_file"
    docker-compose exec -T db psql -U postgres -d boilerplate_db < "$backup_file"
    print_success "Database restore complete!"
}

# Function to open database shell
database_shell() {
    print_info "Opening database shell..."
    docker-compose exec db psql -U postgres -d boilerplate_db
}

# Function to show database info
show_info() {
    print_info "Database Information:"
    echo ""
    echo "Connection Details:"
    echo "  Host: localhost"
    echo "  Port: 5432"
    echo "  Database: boilerplate_db"
    echo "  Username: postgres"
    echo ""
    
    print_info "Getting database stats..."
    docker-compose exec db psql -U postgres -d boilerplate_db -c "
        SELECT 
            schemaname,
            tablename,
            n_tup_ins as inserts,
            n_tup_upd as updates,
            n_tup_del as deletes
        FROM pg_stat_user_tables
        ORDER BY schemaname, tablename;
    "
}

# Function to seed test data
seed_data() {
    print_info "Seeding test data..."
    docker-compose exec django python manage.py generate_core_data
    print_success "Test data seeded!"
}

# Function to show usage
show_usage() {
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  migrate           - Run database migrations"
    echo "  makemigrations    - Create new migrations"
    echo "  reset             - Reset database (DANGEROUS!)"
    echo "  backup            - Create database backup"
    echo "  restore <file>    - Restore from backup file"
    echo "  shell             - Open database shell"
    echo "  info              - Show database information"
    echo "  seed              - Seed test data"
    echo ""
    echo "Examples:"
    echo "  $0 migrate                    # Run migrations"
    echo "  $0 backup                     # Create backup"
    echo "  $0 restore backup_file.sql    # Restore from backup"
    echo "  $0 reset                      # Reset database"
}

# Main execution
main() {
    local command="$1"
    
    if [ -z "$command" ]; then
        show_usage
        exit 1
    fi
    
    # Check if services are running for most commands
    case $command in
        reset)
            # Don't check services for reset as we'll restart them
            ;;
        *)
            check_services
            ;;
    esac
    
    case $command in
        migrate)
            run_migrations
            ;;
        makemigrations)
            create_migrations
            ;;
        reset)
            reset_database
            ;;
        backup)
            backup_database
            ;;
        restore)
            restore_database "$2"
            ;;
        shell)
            database_shell
            ;;
        info)
            show_info
            ;;
        seed)
            seed_data
            ;;
        help|--help|-h)
            show_usage
            ;;
        *)
            print_error "Unknown command: $command"
            show_usage
            exit 1
            ;;
    esac
}

# Run main function
main "$@"