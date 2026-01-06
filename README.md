# NBA Player Prop Model (v2)

## Overview
This project is an end-to-end NBA player prop modeling pipeline designed to evaluate sportsbook player props using statistical features, market data, and model-based scoring. The focus of this repository is on **data engineering, feature design, and pipeline structure**, not on distributing proprietary data or betting picks.

This is the second iteration of the model, built with cleaner abstractions, improved feature engineering, and a more modular architecture.

### Disclamier
This project is provided for educational and research purposes only.No API keys are included, No raw sportsbook data is included, No betting picks or recommendations are distributed. This repository is intended to demonstrate software engineering, data processing, and modeling techniques.
It does not constitute financial, gambling, or betting advice

---

## Project Goals
- Ingest live player prop odds from a sportsbook API
- Normalize and clean prop markets
- Engineer player- and matchup-level features
- Score props using a probabilistic model
- Output ranked prop candidates with confidence scores

---

## Architecture
The pipeline follows a standard data science workflow:

1. **Odds Ingestion**  
   Fetches live player prop odds via an external API.

2. **Data Cleaning**  
   Standardizes market names, player identifiers, and odds formats.

3. **Feature Engineering**  
   Generates features based on player performance trends, matchup context, and market behavior.

4. **Model Scoring**  
   Assigns a confidence score (0–100) to each prop based on model output.

5. **Selection Layer**  
   Produces a ranked list of props for downstream analysis.

---

## Tech Stack
- Python
- pandas / numpy
- scikit-learn
- REST APIs
- Environment-based configuration

---

## Project Structure
```text
src/
├── data/
│   ├── fetch_odds.py
│   └── clean_odds.py
│
├── features/
│   └── feature_engineering.py
│
├── model/
│   ├── selection.py
│   └── pipeline.py
│
├── config.py

---

 ## Setup Instructions

### 1.Install dependencies
```bash
pip install -r requirements.txt

### 2. Create a .env file locally
ODDS_API_KEY=your_api_key_here

### 3. Run the pipeline
```python
python run_pipeline_v2.py

Optional: If you want to runner to load the .env file automatically, install dotenv once: pip install python-dotenv

---
