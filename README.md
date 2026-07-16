# Saerix Finance 7B RAG

Local 7B LLM + RAG pipeline for BIST/US equity analysis. Runs entirely on your machine — no API keys required for inference.

## Features

- **7B Finance LLM** (Saerix Finance 7B, GGUF quantized)
- **RAG Pipeline** — FAISS + sentence-transformers + Ollama
- **BIST Analysis** — 15-year CAGR from Excel + live yfinance data
- **US Stocks** — AAPL, MSFT, NVDA, etc. via yfinance
- **Macro Context** — EVDS data (USD/TRY, rates, inflation, credit)
- **Structured JSON Output** — Pydantic-validated, post-filled by Python
- **CLI** — `build`, `analyze`, `top-performers` commands

## Quick Start

```bash
# 1. Clone & install
git clone https://github.com/ChallengerBey/Saerix-Finance-7b-Rag.git
cd Saerix-Finance-7b-Rag
pip install -r requirements.txt

# 2. Download data (from HF Dataset)
python scripts/download_data.py

# 3. Pull model (GGUF via Ollama)
ollama pull hf.co/Saerix/saerix-finance-7b:Q4_K_M

# 4. Build FAISS index
python src/rag_pipeline.py build

# 5. Analyze
python src/rag_pipeline.py "THYAO analiz"
python src/rag_pipeline.py "AAPL analiz"
python src/rag_pipeline.py top 10 --live --tr
python src/rag_pipeline.py top 5 --live --us
```

## Commands

| Command | Description |
|---------|-------------|
| `python src/rag_pipeline.py build` | Build FAISS index from data/ |
| `python src/rag_pipeline.py "THYAO analiz"` | Single stock analysis |
| `python src/rag_pipeline.py "AAPL analiz"` | US stock analysis |
| `python src/rag_pipeline.py top 10 --live --tr` | Top 10 BIST by CAGR + live + LLM |
| `python src/rag_pipeline.py top 5 --live --us` | Top 5 US large cap + live + LLM |

## Output Format

```json
{
  "sirket": "THYAO (Türk Hava Yollari Anonim Ortakligi)",
  "guncel_fiyat": 326.0,
  "guncel_fk": 33.23,
  "guncel_piyasa_degeri": "9.51 Milyar USD",
  "temettu_verimi": 2.11,
  "uzun_vade_donem": "2010-2025",
  "uzun_vade_toplam_getiri_pct": 34806.25,
  "uzun_vade_cagr_pct": 47.75,
  "teknik_yorum": "Fiyat SMA20/SMA50 karisik; 1a %0.08 | 3a %2.03.",
  "temel_yorum": "15y CAGR %47.8 ile guclu uzun vade performansi...",
  "riskler": "Borc/EBITDA 6.23x, yuksek piyasa degeri...",
  "veri_eksik": false
}
```

## Data Sources

| Source | Purpose | Location |
|--------|---------|----------|
| `bist30_yillik_fiyatlar_2010_2025.xlsx` | 20 hisse, 15yr yearly close → CAGR | HF Dataset `Saerix/saerix-finance-data` |
| `EVDS_<date>.xlsx` | Macro: USD/TRY, rates, inflation, credit | HF Dataset `Saerix/saerix-finance-data` |
| yfinance | Live price, PE, PB, margins, ROE, divs, SMA | Runtime (cached in FAISS) |

## Model

**Saerix Finance 7B** — Fine-tuned for Turkish financial analysis.

- HF Repo: [`Saerix/saerix-finance-7b`](https://huggingface.co/ChallengerBey/saerix-finance-7b-GGUF)
- GGUF Quants: `Q4_K_M`, `Q5_K_M`, `Q8_0`
- Context: 8192 tokens
- License: MIT

```bash
ollama pull hf.co/Saerix/saerix-finance-7b:Q4_K_M
```

## Configuration

`configs/config.yaml`:
```yaml
inference:
  ollama_model: "saerix-finance-7b"
  temperature: 0.1
  top_p: 0.5
  num_predict: 400
rag:
  embedding_model: "all-MiniLM-L6-v2"
  vector_db_path: "data/processed/faiss_index"
```

## Requirements

- Python 3.10+
- Ollama installed & running
- 8GB+ RAM (for 7B Q4_K_M)
- ~2GB disk for FAISS index

## License

MIT — see [LICENSE](LICENSE).

## Disclaimer

This tool is for **research & education only**. Not financial advice. Verify all data independently before making investment decisions.
