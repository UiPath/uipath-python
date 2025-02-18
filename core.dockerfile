FROM python:3.12

WORKDIR /app

# Copy project files
COPY . .

WORKDIR /app/sdk/core

RUN pip install --no-cache-dir poetry 
RUN poetry install
RUN poetry run pip install pytest

CMD ["poetry", "run", "pytest", "--junitxml=test-results.xml"]
