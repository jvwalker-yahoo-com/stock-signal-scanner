# Graph Report - stock-signal-scanner  (2026-11-20)

## Corpus Check
- Corpus is ~17,631 words - fits in a single context window. You may not need a graph.

## Summary
- 160 nodes · 234 edges · 9 communities (8 shown, 1 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 19 edges (avg confidence: 0.87)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- Streamlit App & Data Fetchers
- JEV-RAG Grounding & Signal Synthesis
- Public APIs Catalog & Hub
- Phantom-Flow Transparency & Render Architecture
- Market Intel Providers & Knowledge Tooling
- MarketIntelSuite Core Module
- Render Deployment Config (render.yaml)
- AI Agent Audit & Quant Committee

## God Nodes (most connected - your core abstractions)
1. `GitHub Public-APIs Catalog & Integration Hub` - 15 edges
2. `MarketIntelSuite` - 9 edges
3. `Python Dependencies Manifest` - 9 edges
4. `Public-APIs Market Intel Suite Log` - 8 edges
5. `Phantom-Flow 3-Way Transparency Stack` - 8 edges
6. `JevProcessingGateway` - 7 edges
7. `services` - 7 edges
8. `Project Chat Archive (stock-signal-scanner)` - 7 edges
9. `JevRAGEngine` - 6 edges
10. `detect_wyckoff_structure()` - 6 edges

## Surprising Connections (you probably didn't know these)
- `finnhub-python (>=2.4.19)` --conceptually_related_to--> `Finnhub API`  [INFERRED]
  requirements.txt → docs/chats/public_apis_catalog_and_hub.md
- `Secret Redaction & Environment Variable Policy` --conceptually_related_to--> `python-dotenv (>=1.0.0)`  [INFERRED]
  docs/chats/README.md → requirements.txt
- `GitHub Public-APIs Catalog & Integration Hub` --references--> `stock-signal-scanner (Stock Analysis Tool)`  [EXTRACTED]
  docs/chats/public_apis_catalog_and_hub.md → README.md
- `Project Chat Archive (stock-signal-scanner)` --references--> `stock-signal-scanner (Stock Analysis Tool)`  [EXTRACTED]
  docs/chats/README.md → README.md
- `stock-signal-scanner (Stock Analysis Tool)` --conceptually_related_to--> `Python Dependencies Manifest`  [INFERRED]
  README.md → requirements.txt

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Market Intelligence Public APIs Suite** — docs_chats_public_apis_catalog_and_hub_coingecko, docs_chats_public_apis_catalog_and_hub_frankfurter, docs_chats_public_apis_catalog_and_hub_fred, docs_chats_public_apis_catalog_and_hub_sec_edgar, docs_chats_public_apis_catalog_and_hub_polygon_io, docs_chats_public_apis_catalog_and_hub_finnhub [EXTRACTED 1.00]
- **Stock Signal Scanner Core Python Stack** — requirements_streamlit, requirements_yfinance, requirements_pandas, requirements_numpy, requirements_plotly, requirements_finnhub_python, requirements_requests, requirements_python_dotenv [EXTRACTED 1.00]
- **Public APIs Local Hub Pipeline** — docs_chats_public_apis_catalog_and_hub_ingest_and_index, docs_chats_public_apis_catalog_and_hub_sqlite_fts5_db, docs_chats_public_apis_catalog_and_hub_api_hub_cli [INFERRED 0.85]
- **Phantom-Flow 3-Way Market Transparency Stack** — docs_chats_2026_10_08_render_deployment_feeds_and_wyckoff_finnhub_api, docs_chats_2026_10_08_render_deployment_feeds_and_wyckoff_openinsider_feed, docs_chats_2026_10_08_render_deployment_feeds_and_wyckoff_quiverquant_api, docs_chats_2026_10_08_render_deployment_feeds_and_wyckoff_phantom_flow_stack [EXTRACTED 1.00]
- **JEV + RAG Gated Signal Pipeline** — docs_chats_2026_10_09_jev_rag_integration_jev_query_router, docs_chats_2026_10_09_jev_rag_integration_jev_processing_gateway, docs_chats_2026_10_09_jev_rag_integration_sufficiency_gating, docs_chats_2026_10_09_jev_rag_integration_grounding_check, docs_chats_2026_10_09_jev_rag_integration_jev_rag_system [EXTRACTED 1.00]
- **Public Market Intelligence Data Suite** — market_intel, docs_chats_2026_10_10_public_apis_market_intel_suite_frankfurter, docs_chats_2026_10_10_public_apis_market_intel_suite_coingecko, docs_chats_2026_10_10_public_apis_market_intel_suite_fred, docs_chats_2026_10_10_public_apis_market_intel_suite_sec_edgar, docs_chats_2026_10_10_public_apis_market_intel_suite_polygon_finnhub [EXTRACTED 1.00]
- **Resilient OpenBB Decision & AI Agent Audit Pipeline** — docs_chats_2026_10_21_to_11_18_openbb_audit_and_optimization_openbb_unified_router, docs_chats_2026_10_21_to_11_18_openbb_audit_and_optimization_predict_engine, docs_chats_2026_10_21_to_11_18_openbb_audit_and_optimization_trading_agents_hub, docs_chats_2026_10_21_to_11_18_openbb_audit_and_optimization_stock_signal_scanner_app, docs_chats_2026_10_21_to_11_18_openbb_audit_and_optimization_audit_401_fix, docs_chats_2026_10_21_to_11_18_openbb_audit_and_optimization_quant_committee_fallback [INFERRED 0.85]

## Communities (9 total, 1 thin omitted)

### Community 0 - "Streamlit App & Data Fetchers"
Cohesion: 0.11
Nodes (9): analyze_daytrade(), fetch_finnhub_13f_holdings(), fetch_forex_overview(), fetch_news_radar(), fetch_openinsider_trades(), fetch_quiver_congress_trades(), get_secret(), get_watchlist_summary() (+1 more)

### Community 1 - "JEV-RAG Grounding & Signal Synthesis"
Cohesion: 0.11
Nodes (5): synthesize_multi_feed_signals(), JevHallucinationAndGroundingCheck, JevProcessingGateway, JevQueryRouter, JevRAGEngine

### Community 2 - "Public APIs Catalog & Hub"
Cohesion: 0.10
Nodes (28): api_hub.py CLI & Query Tool, GitHub Public-APIs Catalog & Integration Hub, CoinGecko API, Finnhub API, Frankfurter API, FRED API (Federal Reserve Economic Data), Hugging Face Inference API, ingest_and_index.py Ingestion Pipeline (+20 more)

### Community 3 - "Phantom-Flow Transparency & Render Architecture"
Cohesion: 0.13
Nodes (17): Autonomous Trading Cockpit, Catalyst News Radar (Tavily, SerpApi, Finnhub, Anspire), Daily Stock Analysis, Finnhub API (Quotes, 13F, SEC Filings), Multi-Factor Confluence Synthesis, OpenInsider Form 4 Feed, Phantom-Flow 3-Way Transparency Stack, QuiverQuant Congressional Trading API (+9 more)

### Community 4 - "Market Intel Providers & Knowledge Tooling"
Cohesion: 0.13
Nodes (12): CoinGecko Crypto API, Frankfurter FX API, FRED Macro Economic API, Polygon.io / Finnhub Intraday API, Public APIs Queryable Hub (public_apis.db / api_hub.py), SEC EDGAR Corporate Filings API, sotck_predict (predictive_execution), engine/federation.py Circular Import Fix (+4 more)

### Community 5 - "MarketIntelSuite Core Module"
Cohesion: 0.15
Nodes (5): fetch_crypto_overview(), fetch_edgar_filings(), fetch_macro_indicators(), fetch_polygon_finnhub_quote(), MarketIntelSuite

### Community 6 - "Render Deployment Config (render.yaml)"
Cohesion: 0.18
Nodes (10): key, sync, value, services, buildCommand, envVars, name, runtime (+2 more)

### Community 7 - "AI Agent Audit & Quant Committee"
Cohesion: 0.40
Nodes (3): stock-signal-scanner, stock-signal-scanner/app.py, TradingBot / trading-agents-hub (TradingBot/app.py)

## Knowledge Gaps
- **25 isolated node(s):** `streamlit (>=1.30.0)`, `yfinance (>=0.2.35)`, `pandas (>=2.0.0)`, `numpy (>=1.24.0)`, `plotly (>=5.18.0)` (+20 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 73 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **1 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `MarketIntelSuite` connect `MarketIntelSuite Core Module` to `Streamlit App & Data Fetchers`, `Market Intel Providers & Knowledge Tooling`?**
  _High betweenness centrality (0.070) - this node is a cross-community bridge._
- **What connects `streamlit (>=1.30.0)`, `yfinance (>=0.2.35)`, `pandas (>=2.0.0)` to the rest of the system?**
  _25 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Streamlit App & Data Fetchers` be split into smaller, more focused modules?**
  _Cohesion score 0.11264367816091954 - nodes in this community are weakly interconnected._
- **Why does `JevRAGEngine` connect `JEV-RAG Grounding & Signal Synthesis` to `Streamlit App & Data Fetchers`?**
  _High betweenness centrality (0.043) - this node is a cross-community bridge._
- **Should `JEV-RAG Grounding & Signal Synthesis` be split into smaller, more focused modules?**
  _Cohesion score 0.10837438423645321 - nodes in this community are weakly interconnected._
- **Why does `stock-signal-scanner` connect `AI Agent Audit & Quant Committee` to `Market Intel Providers & Knowledge Tooling`?**
  _High betweenness centrality (0.037) - this node is a cross-community bridge._
- **Should `Public APIs Catalog & Hub` be split into smaller, more focused modules?**
  _Cohesion score 0.09852216748768473 - nodes in this community are weakly interconnected._