#!/bin/bash

# LightRAG with Qwen 3 Setup Script
# This script helps you manage the LightRAG Docker Compose setup

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
COMPOSE_FILE="docker-compose.yml"
COMPOSE_FILE_REDIS="docker-compose.redis-vectors.yml"
COMPOSE_FILE_REDIS_FULL="docker-compose-redis-full.yml"

print_header() {
    echo -e "${BLUE}================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}================================${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

check_dependencies() {
    print_header "Checking Dependencies"
    
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed"
        echo "Please install Docker: https://docs.docker.com/get-docker/"
        exit 1
    fi
    print_success "Docker is installed"
    
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        print_error "Docker Compose is not installed"
        echo "Please install Docker Compose: https://docs.docker.com/compose/install/"
        exit 1
    fi
    print_success "Docker Compose is installed"
    
    # Check Docker is running
    if ! docker info &> /dev/null; then
        print_error "Docker daemon is not running"
        echo "Please start Docker"
        exit 1
    fi
    print_success "Docker daemon is running"
}

start_services() {
    print_header "Starting LightRAG Services"
    
    local compose_file=$1
    if [ -z "$compose_file" ]; then
        compose_file=$COMPOSE_FILE
    fi
    
    if [ ! -f "$compose_file" ]; then
        print_error "Compose file not found: $compose_file"
        exit 1
    fi
    
    echo "Using compose file: $compose_file"
    echo ""
    
    print_warning "This will download ~10GB of data (models + images)"
    read -p "Continue? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_warning "Cancelled"
        exit 0
    fi
    
    docker-compose -f "$compose_file" up -d
    
    print_success "Services starting..."
    echo ""
    echo "Monitoring model download progress..."
    echo "This may take 10-30 minutes depending on your internet speed"
    echo ""
    
    # Wait for ollama-setup to complete
    docker-compose -f "$compose_file" logs -f ollama-setup &
    LOG_PID=$!
    
    # Wait for the setup container to finish
    while docker ps -a | grep -q lightrag-ollama-setup; do
        if docker ps -a | grep lightrag-ollama-setup | grep -q "Exited"; then
            kill $LOG_PID 2>/dev/null || true
            break
        fi
        sleep 5
    done
    
    echo ""
    print_success "Models downloaded successfully!"
    
    # Wait for LightRAG to be healthy
    echo ""
    echo "Waiting for LightRAG service to be ready..."
    max_attempts=30
    attempt=0
    
    while [ $attempt -lt $max_attempts ]; do
        if curl -sf http://localhost:9621/health &> /dev/null; then
            print_success "LightRAG is ready!"
            break
        fi
        attempt=$((attempt + 1))
        echo -n "."
        sleep 2
    done
    
    echo ""
    
    if [ $attempt -eq $max_attempts ]; then
        print_warning "LightRAG is taking longer than expected to start"
        print_warning "Check logs: docker-compose logs lightrag"
    fi
    
    show_status
}

start_redis_full() {
    print_header "Starting LightRAG with Full Redis Storage"

    if [ ! -f "$COMPOSE_FILE_REDIS_FULL" ]; then
        print_error "Compose file not found: $COMPOSE_FILE_REDIS_FULL"
        exit 1
    fi

    echo ""
    echo -e "${YELLOW}Architecture:${NC}"
    echo "  - KV Storage:      Redis (DB 0)"
    echo "  - DocStatus:       Redis (DB 1)"
    echo "  - Vector Storage:  Redis (DB 2) with HNSW (4096 dim)"
    echo "  - Graph Storage:   NetworkX (file-based)"
    echo "  - LLM:             Qwen3-Next-80B-A3B-Thinking (External API)"
    echo "  - Embedding:       Qwen3-Embedding-8B (4096 dim)"
    echo ""
    echo -e "${YELLOW}Image:${NC} ghcr.io/piotrpawluk/lightrag:latest"
    echo -e "${YELLOW}Note:${NC} Using external APIs - no model downloads needed"
    echo ""

    read -p "Continue? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_warning "Cancelled"
        exit 0
    fi

    docker-compose -f "$COMPOSE_FILE_REDIS_FULL" up -d

    print_success "Services starting..."
    echo ""
    echo "Waiting for LightRAG service to be ready..."
    max_attempts=30
    attempt=0

    while [ $attempt -lt $max_attempts ]; do
        if curl -sf http://localhost:9621/health &> /dev/null; then
            print_success "LightRAG is ready!"
            break
        fi
        attempt=$((attempt + 1))
        echo -n "."
        sleep 2
    done

    echo ""

    if [ $attempt -eq $max_attempts ]; then
        print_warning "LightRAG is taking longer than expected to start"
        print_warning "Check logs: docker-compose -f $COMPOSE_FILE_REDIS_FULL logs lightrag"
    fi

    # Show status with Redis-specific info
    echo ""
    print_header "Service Status"
    docker-compose -f "$COMPOSE_FILE_REDIS_FULL" ps

    echo ""
    echo -e "${BLUE}Service URLs:${NC}"
    echo "  LightRAG API: http://localhost:9621"
    echo "  Redis Stack:  redis://localhost:6379"
    echo ""
    echo -e "${BLUE}External APIs:${NC}"
    echo "  LLM Endpoint:       ml-llm-v-srv-v45-cp1-tst-node1.ai.warta.pl"
    echo "  Embedding Endpoint: ml-ssm-l-srv-v16-cp2-tst-node5-llm-apps-tst.apps.ml.warta.pl"
    echo ""
    echo -e "${BLUE}Health Checks:${NC}"

    # Check LightRAG health
    if curl -sf http://localhost:9621/health &> /dev/null; then
        print_success "LightRAG is responding"
    else
        print_error "LightRAG is not responding"
    fi

    # Check Redis health
    if docker exec lightrag-redis redis-cli ping &> /dev/null; then
        print_success "Redis Stack is responding"
    else
        print_error "Redis Stack is not responding"
    fi

    echo ""
    echo -e "${BLUE}Storage Configuration:${NC}"
    echo "  KV Storage:     RedisKVStorage (DB 0)"
    echo "  DocStatus:      RedisDocStatusStorage (DB 1)"
    echo "  Vector Storage: RedisVectorStorage (DB 2, 4096 dim)"
    echo "  Graph Storage:  NetworkXStorage (file-based)"
    echo ""
    echo -e "${GREEN}Full Redis storage with external APIs setup complete!${NC}"
    echo ""
    echo "Next steps:"
    echo "  - Test insertion: curl -X POST http://localhost:9621/insert -H 'Content-Type: application/json' -d '{\"text\": \"Your document\"}'"
    echo "  - Test query: curl -X POST http://localhost:9621/query -H 'Content-Type: application/json' -d '{\"query\": \"Your question\", \"mode\": \"hybrid\"}'"
    echo "  - Check Redis: docker exec lightrag-redis redis-cli INFO"
    echo "  - View logs: $0 logs"
}

stop_services() {
    print_header "Stopping LightRAG Services"
    
    docker-compose -f "$COMPOSE_FILE" down
    print_success "Services stopped"
}

restart_services() {
    print_header "Restarting LightRAG Services"
    
    docker-compose -f "$COMPOSE_FILE" restart
    print_success "Services restarted"
}

show_status() {
    print_header "Service Status"
    
    docker-compose -f "$COMPOSE_FILE" ps
    
    echo ""
    echo -e "${BLUE}Service URLs:${NC}"
    echo "  LightRAG API: http://localhost:9621"
    echo "  Ollama API:   http://localhost:11434"
    echo "  Redis:        redis://localhost:6379"
    echo ""
    echo -e "${BLUE}Health Checks:${NC}"
    
    if curl -sf http://localhost:9621/health &> /dev/null; then
        echo -e "  LightRAG: ${GREEN}✓ Healthy${NC}"
    else
        echo -e "  LightRAG: ${RED}✗ Unhealthy${NC}"
    fi
    
    if curl -sf http://localhost:11434/api/tags &> /dev/null; then
        echo -e "  Ollama:   ${GREEN}✓ Healthy${NC}"
    else
        echo -e "  Ollama:   ${RED}✗ Unhealthy${NC}"
    fi
    
    if docker exec lightrag-redis redis-cli ping &> /dev/null; then
        echo -e "  Redis:    ${GREEN}✓ Healthy${NC}"
    else
        echo -e "  Redis:    ${RED}✗ Unhealthy${NC}"
    fi
}

show_logs() {
    print_header "Service Logs"
    
    local service=$1
    
    if [ -z "$service" ]; then
        docker-compose -f "$COMPOSE_FILE" logs -f
    else
        docker-compose -f "$COMPOSE_FILE" logs -f "$service"
    fi
}

run_demo() {
    print_header "Running Demo Script"
    
    if [ ! -f "lightrag_demo.py" ]; then
        print_error "Demo script not found: lightrag_demo.py"
        exit 1
    fi
    
    # Check if Python is available
    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 is not installed"
        exit 1
    fi
    
    # Install requirements if needed
    if ! python3 -c "import requests" 2>/dev/null; then
        print_warning "Installing Python dependencies..."
        pip3 install -r requirements.txt
    fi
    
    python3 lightrag_demo.py
}

cleanup() {
    print_header "Cleanup"
    
    print_warning "This will remove all containers, volumes, and downloaded models"
    read -p "Are you sure? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_warning "Cancelled"
        exit 0
    fi
    
    docker-compose -f "$COMPOSE_FILE" down -v
    print_success "Cleanup complete"
}

test_connection() {
    print_header "Testing Connections"
    
    echo "Testing LightRAG..."
    if curl -sf http://localhost:9621/health; then
        echo ""
        print_success "LightRAG is responding"
    else
        print_error "LightRAG is not responding"
    fi
    
    echo ""
    echo "Testing Ollama..."
    if curl -sf http://localhost:11434/api/tags; then
        echo ""
        print_success "Ollama is responding"
    else
        print_error "Ollama is not responding"
    fi
    
    echo ""
    echo "Testing Redis..."
    if docker exec lightrag-redis redis-cli ping &> /dev/null; then
        print_success "Redis is responding"
    else
        print_error "Redis is not responding"
    fi
    
    echo ""
    echo "Checking models..."
    docker exec lightrag-ollama ollama list
}

show_help() {
    cat << EOF
${BLUE}LightRAG with Qwen 3 - Management Script${NC}

Usage: $0 [command] [options]

Commands:
  ${GREEN}start${NC}               Start all services (default: NanoVectorDB)
  ${GREEN}start-redis${NC}         Start with Redis vectors (partial Redis)
  ${GREEN}start-redis-full${NC}    Start with full Redis storage (KV+Vec+Doc)
  ${GREEN}stop${NC}                Stop all services
  ${GREEN}restart${NC}             Restart all services
  ${GREEN}status${NC}              Show service status
  ${GREEN}logs${NC} [service]      Show logs (optionally for specific service)
  ${GREEN}demo${NC}                Run the Python demo script
  ${GREEN}test${NC}                Test all connections
  ${GREEN}cleanup${NC}             Remove all containers and volumes
  ${GREEN}help${NC}                Show this help message

Examples:
  $0 start               # Start with default configuration
  $0 start-redis         # Start with Redis for vectors
  $0 start-redis-full    # Start with full Redis storage (NEW!)
  $0 logs lightrag       # Show LightRAG logs
  $0 logs                # Show all logs
  $0 demo                # Run demo script

EOF
}

# Main script
case "${1:-}" in
    start)
        check_dependencies
        start_services "$COMPOSE_FILE"
        ;;
    start-redis)
        check_dependencies
        start_services "$COMPOSE_FILE_REDIS"
        ;;
    start-redis-full)
        check_dependencies
        start_redis_full
        ;;
    stop)
        stop_services
        ;;
    restart)
        restart_services
        ;;
    status)
        show_status
        ;;
    logs)
        show_logs "${2:-}"
        ;;
    demo)
        run_demo
        ;;
    test)
        test_connection
        ;;
    cleanup)
        cleanup
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        show_help
        exit 1
        ;;
esac
