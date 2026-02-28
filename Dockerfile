# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin/:$PATH"

# Copy the project files
COPY . .

# Install dependencies using uv
RUN uv sync --frozen

# Install Playwright browsers and their system dependencies
# This command will install the necessary system packages for Chromium
RUN uv run playwright install --with-deps chromium

# Expose Streamlit port
EXPOSE 8888

# Set environment variables for Streamlit
ENV STREAMLIT_SERVER_PORT=8888
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0

# Run the application
CMD ["uv", "run", "streamlit", "run", "onemg/app_1mg.py"]
