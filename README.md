PDF (raw source)
│
│  (1) extract_pdf.py
│  - Extract tables of moves
│  - Extract raw images (JPG)
│  - Save intermediate CSV (raw_moves.csv)
│
├─> extracted/raw_moves.csv
│
│  (2) normalize_moves.py
│  - Read CSV
│  - Normalize move codes → `id`
│  - Normalize categories (enum)
│  - Normalize technical value (float → int)
│  - Normalize criteria keys
│  - Store criteria as list of {type, raw}
│  - **Add aliases** (manual mapping or derived from name)
│  - Output canonical JSON per move
│
├─> normalized/moves/F1.json
│     {
│       "id": "F1",
│       "name": "Inside Leg Hang 1",
│       "aliases": ["Inside Leg Hang", "ILH1"],
│       "technicalValue": 1,
│       "category": "flexibility",
│       "page": 26,
│       "criteria": [
│         { "type": "hold", "raw": "minimum 2 seconds" },
│         { "type": "body_position", "raw": "inverted" }
│       ]
│     }
│
│  (3) optimize_images.py
│  - Convert JPG → WebP
│  - Resize / optimize
│  - Output: normalized/images/F1.webp
│
│  (4) build_search_index.py
│  - Read all canonical JSON
│  - Generate `searchTokens` for each move:
│       - name
│       - aliases
│       - criteria types
│  - Generate lightweight index JSON for search
│
└─> normalized/moves-index.json
      [
        {
          "id": "F1",
          "name": "Inside Leg Hang 1",
          "aliases": ["Inside Leg Hang", "ILH1"],
          "category": "flexibility",
          "technicalValue": 1,
          "criteriaTypes": ["hold", "body_position"],
          "searchTokens": ["Inside", "Leg", "Hang", "1", "Inside Leg Hang", "ILH1", "hold", "body_position"]
        },
        ...
      ]
