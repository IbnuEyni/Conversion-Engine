#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "=== Conversion Engine Setup ==="

# 1. Dependencies via uv
echo "[1/5] Installing dependencies..."
uv sync --extra dev --quiet

# 2. Crunchbase ODM sample
echo "[2/5] Crunchbase ODM data..."
mkdir -p data/crunchbase
if [ ! -f "data/crunchbase/crunchbase_sample.json" ]; then
    curl -sfL "https://raw.githubusercontent.com/luminati-io/Crunchbase-dataset-samples/main/Crunchbase_dataset_sample.json" \
        -o data/crunchbase/crunchbase_sample.json || \
    curl -sfL "https://raw.githubusercontent.com/luminati-io/Crunchbase-dataset-samples/main/crunchbase_companies_sample.json" \
        -o data/crunchbase/crunchbase_sample.json || \
    { echo "[]" > data/crunchbase/crunchbase_sample.json; echo "  WARN: download failed, empty placeholder created"; }
    echo "  $(wc -c < data/crunchbase/crunchbase_sample.json) bytes"
else
    echo "  already present"
fi

# 3. Layoffs.fyi
echo "[3/5] Layoffs.fyi data..."
mkdir -p data/layoffs
if [ ! -f "data/layoffs/layoffs.csv" ]; then
    curl -sfL "https://huggingface.co/datasets/thedevastator/tech-layoffs-2022-2024/resolve/main/layoffs.csv" \
        -o data/layoffs/layoffs.csv || \
    { echo "company,date,laid_off,percentage,source" > data/layoffs/layoffs.csv; echo "  WARN: download failed, empty placeholder created"; }
    echo "  $(wc -l < data/layoffs/layoffs.csv) rows"
else
    echo "  already present"
fi

# 4. Output directories
echo "[4/5] Creating output directories..."
mkdir -p data/{briefs,outbound_sink/emails,outbound_sink/sms,outbound_sink/bookings,conversations,job_posts}

# 5. .env
echo "[5/5] Environment config..."
if [ ! -f ".env" ]; then
    cp .env.template .env
    echo "  created .env from template — edit with your API keys"
else
    echo "  .env already exists"
fi

echo ""
echo "=== Setup Complete ==="
echo "  uv run python scripts/test_pipeline.py     # validate pipeline (no API keys needed)"
echo "  uv run python scripts/test_pipeline.py --with-llm  # full test (needs OPENROUTER_API_KEY)"
echo "  uv run python -m agent.main                # start server"
