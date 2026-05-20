# SpillVision

Satellite-based **oil spill detection**, risk analysis, Arabic/English reports, and an intelligent assistant — built with DeepLabV3+, FastAPI, React, and Qwen2.5 (LoRA).

This repository contains **source code only**. Large datasets, trained weights, database dumps, and runtime uploads are **not** on GitHub; download them from Hugging Face (below).

For full project structure and setup, see [PROJECT_DOCUMENTATION.md](PROJECT_DOCUMENTATION.md).

## Quick start

**Backend**
```bash
cd backend-rana-clean
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# Configure .env (DB paths, model paths, API keys)
uvicorn main:app --reload --port 8000
```

**Frontend**
```bash
cd oil-spill-app
npm install
npm run dev
```

## Hugging Face resources

Trained models and the tokenized dataset are hosted on Hugging Face under [@ra-hk1](https://huggingface.co/ra-hk1).

### Models

| Resource | Description | Link |
|---|---|---|
| SpillVision DeepLabV3+ Keras Models | Semantic segmentation for oil spill detection from satellite imagery | [spillvision-deeplab-keras](https://huggingface.co/ra-hk1/spillvision-deeplab-keras) |
| SpillVision Qwen Oil LoRA Adapter | Fine-tuned LoRA adapter for oil spill report generation | [spillvision-qwen-oil-lora](https://huggingface.co/ra-hk1/spillvision-qwen-oil-lora) |
| Qwen2.5 0.5B Instruct (local base) | Base model used with the SpillVision LoRA adapter | [spillvision-qwen2.5-0.5b-instruct-local](https://huggingface.co/ra-hk1/spillvision-qwen2.5-0.5b-instruct-local) |

### Dataset

| Resource | Description | Link |
|---|---|---|
| Oil Spill Tokenized Dataset | Tokenized dataset for fine-tuning and NLP tasks | [oil-spill-tokenized-dataset](https://huggingface.co/datasets/ra-hk1/oil-spill-tokenized-dataset) |

### Download example

```bash
pip install huggingface_hub

# DeepLab weights (example)
huggingface-cli download ra-hk1/spillvision-deeplab-keras --local-dir ./models/deeplab

# Qwen base + LoRA (example)
huggingface-cli download ra-hk1/spillvision-qwen2.5-0.5b-instruct-local --local-dir ./oil_llm_reporter/models/Qwen2.5-0.5B-Instruct
huggingface-cli download ra-hk1/spillvision-qwen-oil-lora --local-dir ./oil_llm_reporter/oil_qwen_lora_adapter
```

Point your `.env` / backend config to the downloaded paths (see `PROJECT_DOCUMENTATION.md`).

## What is not in this repo

- Satellite imagery (`Oil/`), user uploads, generated reports
- `full_database.sql` and local vector DBs
- `.env` secrets

These stay local or on Hugging Face; see `.gitignore`.
