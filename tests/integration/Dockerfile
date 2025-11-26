FROM python:3.12-slim

# Install test dependencies once
RUN pip install --no-cache-dir \
    pytest \
    pytest-asyncio \
    pytest-homeassistant-custom-component

WORKDIR /app

# Default command
CMD ["pytest", "tests/integration/", "-v"]
