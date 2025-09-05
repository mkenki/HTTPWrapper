# HTTPWrapper

A modern, resilient HTTP client wrapper with advanced retry mechanisms and circuit breaker pattern implementation.

## Features

- Advanced retry with exponential backoff and jitter
- Circuit breaker pattern for fault tolerance
- Configurable HTTP client settings
- Comprehensive logging and metrics
- Async/await support
- Type hints and modern Python practices
- Extensive test coverage
- Docker containerization support

## Installation

```bash
pip install httpwrapper
```

## Quick Start

```python
from httpwrapper import HTTPClient

client = HTTPClient(
    retry_config=RetryConfig(
        max_attempts=3,
        backoff_factor=0.3,
        jitter=True
    ),
    circuit_breaker_config=CircuitBreakerConfig(
        failure_threshold=5,
        recovery_timeout=60,
        expected_exception=ConnectionError
    )
)

response = client.get('https://api.example.com/data')
```

## Architecture

### Core Components

1. **HTTPClient**: Main wrapper class extending base HTTP client
2. **RetryManager**: Handles retry logic with backoff strategies
3. **CircuitBreaker**: Implements circuit breaker state management
4. **MetricsCollector**: Tracks request metrics and health
5. **Configuration**: Centralized configuration management

### Patterns Implemented

- **Retry Pattern**: Automatic retry with configurable backoff
- **Circuit Breaker**: Fail-fast protection for failing services
- **Observer Pattern**: Event-driven metric collection
- **Factory Pattern**: Configuration-driven object creation

## Development Roadmap

### Phase 1 - Core Implementation
- [x] Project structure setup
- [x] Base HTTP client implementation
- [x] Basic retry mechanism
- [x] Initial circuit breaker
- [x] Configuration system
- [x] Basic logging and metrics

### Phase 2 - Advanced Features
- [x] Exponential backoff with jitter
- [x] Custom retry conditions
- [x] Circuit breaker states (Closed, Open, Half-Open)
- [x] Async support
- [x] Connection pooling (implemented in async client)
- [x] Response caching

### Phase 3 - Production Readiness
- [x] Comprehensive test suite (circuit breaker tests done)
- [ ] Performance benchmarks
- [ ] Docker containerization
- [ ] CI/CD pipeline
- [ ] Documentation
- [ ] Health checks
- [ ] Metrics dashboard

### Phase 4 - Extensions
- [ ] Plugin system
- [ ] Multiple HTTP client backends
- [ ] Rate limiting
- [ ] Request/response interceptors
- [ ] Custom metrics exporters

## Contributing

Please read [CONTRIBUTING.md](CONTRIBUTING.md) for details on our code of conduct and the process for submitting pull requests.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
