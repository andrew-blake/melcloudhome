FROM python:3.12-slim

# Install test dependencies once
RUN pip install --no-cache-dir \
    pytest \
    pytest-asyncio \
    pytest-homeassistant-custom-component

# Set working directory to tests/integration so conftest.py is treated as root-level
WORKDIR /app/tests/integration

# Default command - pytest runs from integration directory
CMD ["pytest", ".", "-v", "-c", "pytest.ini"]
