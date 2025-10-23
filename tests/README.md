# MAIA Test Suite

This directory contains comprehensive unit tests for the MAIA toolkit, covering all modules in `MAIA/` and `MAIA_scripts/` directories.

## Test Structure

```
tests/
├── __init__.py                      # Test package init
├── conftest.py                      # Pytest fixtures and configuration
├── test_maia_fn.py                  # Tests for MAIA/maia_fn.py
├── test_keycloak_utils.py           # Tests for MAIA/keycloak_utils.py
├── test_kubernetes_utils.py         # Tests for MAIA/kubernetes_utils.py
├── test_dashboard_utils.py          # Tests for MAIA/dashboard_utils.py
├── test_helm_values.py              # Tests for MAIA/helm_values.py
├── test_maia_admin.py               # Tests for MAIA/maia_admin.py
├── test_maia_core.py                # Tests for MAIA/maia_core.py
├── test_deploy_helm_chart.py        # Tests for MAIA_scripts/MAIA_deploy_helm_chart.py
└── test_send_welcome_user_mail.py   # Tests for MAIA_scripts/MAIA_send_welcome_user_mail.py
```

## Running Tests

### Run all tests
```bash
pytest tests/
```

### Run tests with verbose output
```bash
pytest tests/ -v
```

### Run tests with coverage
```bash
pytest tests/ --cov=MAIA --cov=MAIA_scripts --cov-report=html
```

### Run specific test file
```bash
pytest tests/test_maia_fn.py
```

### Run specific test class or function
```bash
pytest tests/test_maia_fn.py::TestPasswordGeneration
pytest tests/test_maia_fn.py::TestPasswordGeneration::test_generate_random_password_default_length
```

### Run tests matching a pattern
```bash
pytest tests/ -k "password"
```

## Test Coverage

The test suite covers:

### MAIA/ Module Tests
- **maia_fn.py**: Password generation, username conversion, Docker registry secrets, ConfigMap creation, SSH port management
- **keycloak_utils.py**: User and group management in Keycloak, authentication and authorization
- **kubernetes_utils.py**: Kubernetes operations, namespace management, pod labeling, resource filtering
- **dashboard_utils.py**: GPU booking and verification, encryption/decryption, email sending
- **helm_values.py**: Helm values generation for various configurations
- **maia_admin.py**: Admin toolkit configuration generation (MinIO, MySQL, MLflow)
- **maia_core.py**: Core toolkit configuration (Prometheus, Loki, Tempo, Traefik, MetalLB, cert-manager)

### MAIA_scripts/ Tests
- **MAIA_deploy_helm_chart.py**: String to boolean conversion utility
- **MAIA_send_welcome_user_mail.py**: User welcome email functionality

## Test Fixtures

Common fixtures are defined in `conftest.py`:
- `temp_config_folder`: Temporary directory for test configurations
- `sample_cluster_config`: Sample cluster configuration
- `sample_user_config`: Sample user configuration
- `sample_maia_config`: Sample MAIA configuration
- `mock_kubernetes_client`: Mocked Kubernetes client
- `mock_keycloak_admin`: Mocked Keycloak admin client
- `mock_settings`: Mocked settings object

## Testing Approach

### Unit Tests
Tests use mocking extensively to avoid requiring actual Kubernetes clusters, Keycloak instances, or other external dependencies. This allows tests to run quickly and reliably in CI/CD environments.

### Mocking Strategy
- **Kubernetes API**: Mocked using `pytest-mock` and `unittest.mock`
- **Keycloak Admin**: Mocked to simulate user and group operations
- **File I/O**: Mocked where appropriate to avoid file system dependencies
- **Environment Variables**: Set via pytest fixtures for consistent test environments

## Integration Testing Limitations

Some functions in MAIA require full Kubernetes cluster access and are challenging to fully test without integration tests:
- Functions that deploy actual Helm charts
- Functions that create Kubernetes resources (namespaces, services, etc.)
- Functions that interact with MinIO, ArgoCD, or other deployed services

For these functions, tests verify:
- Function structure and return types
- Proper configuration generation
- Correct API call patterns (via mocks)

## Adding New Tests

When adding new tests:

1. **Create test file**: Follow the naming convention `test_<module_name>.py`
2. **Use fixtures**: Leverage existing fixtures in `conftest.py`
3. **Mock external dependencies**: Use `pytest-mock` or `unittest.mock`
4. **Test structure**:
   ```python
   @pytest.mark.unit
   class TestFeatureName:
       """Test description."""
       
       def test_specific_behavior(self, fixture1, fixture2):
           """Test specific behavior."""
           # Arrange
           # Act
           # Assert
   ```
5. **Document limitations**: If full testing requires integration tests, document why

## CI/CD Integration

Tests are designed to run in CI/CD pipelines. The `pytest.ini` configuration ensures:
- Tests discover automatically
- Verbose output for debugging
- Proper test markers for filtering
- Short tracebacks for readability

## Dependencies

Test dependencies:
- `pytest>=8.0`: Test framework
- `pytest-cov`: Coverage reporting
- `pytest-mock`: Mocking utilities

Install test dependencies:
```bash
pip install pytest pytest-cov pytest-mock
```

## Test Markers

Available test markers:
- `@pytest.mark.unit`: Unit tests (default)
- `@pytest.mark.integration`: Integration tests (requires external services)
- `@pytest.mark.slow`: Slow-running tests

Run only unit tests:
```bash
pytest tests/ -m unit
```

## Contributing

When contributing tests:
1. Ensure tests pass locally before submitting
2. Add tests for any new functionality
3. Update this README if adding new test files
4. Follow existing test patterns and structure
5. Mock external dependencies appropriately
