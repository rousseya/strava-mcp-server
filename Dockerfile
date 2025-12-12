FROM python:3.11-slim

WORKDIR /app

# Install uv
RUN pip install uv

# Copy project files
COPY pyproject.toml uv.lock README.md ./
COPY src/ ./src/
COPY app.py ./

# Install dependencies
RUN uv sync --no-dev

# Expose port for HF Spaces
EXPOSE 7860

# Run the app
CMD ["uv", "run", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]
