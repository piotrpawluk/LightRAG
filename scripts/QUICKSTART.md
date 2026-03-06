# Quick Start Guide: Excel-to-LightRAG Query Processor

This guide will help you get started with processing Excel files using the LightRAG API in just a few minutes.

## Prerequisites

1. **LightRAG installed** with required dependencies
2. **Python 3.8+** with virtual environment
3. **Excel file** with prompts in column B

## Step 1: Install Dependencies

```bash
# From the LightRAG root directory
uv pip install openpyxl tqdm
```

## Step 2: Prepare Your Excel File

Your Excel file should have:
- **Column B**: Contains your questions/prompts
- **First row**: Headers (will be skipped)
- **Column U**: Will store responses (can be empty initially)

Example structure:

```
| A  | B (Pytanie)                    | ... | U (Response) |
|----|--------------------------------|-----|--------------|
| ID | Question                       | ... | [empty]      |
| 1  | What is LightRAG?              | ... | [empty]      |
| 2  | How does it work?              | ... | [empty]      |
```

Or create a test file:
```bash
python scripts/create_test_excel.py
```

## Step 3: Start LightRAG Server

In a separate terminal:

```bash
# Make sure you've indexed some documents first
lightrag-server --host 0.0.0.0 --port 9621
```

Or with authentication:
```bash
export LIGHTRAG_API_KEY=your-secure-key
lightrag-server --host 0.0.0.0 --port 9621
```

## Step 4: Run the Query Processor

### Test First (Dry Run)

```bash
python scripts/excel_lightrag_query.py \
    --excel-file your_file.xlsx \
    --dry-run
```

This will:
- ✓ Validate the Excel file structure
- ✓ Test API connectivity
- ✓ Show how many queries will be processed
- ✗ **NOT** write any results back

### Process for Real

```bash
python scripts/excel_lightrag_query.py \
    --excel-file your_file.xlsx \
    --backup
```

The `--backup` flag creates a timestamped backup before modifying your file.

## Step 5: Review Results

Open your Excel file and check column U for the responses.

## Common Usage Patterns

### Basic Processing
```bash
python scripts/excel_lightrag_query.py --excel-file data.xlsx
```

### With Authentication
```bash
python scripts/excel_lightrag_query.py \
    --excel-file data.xlsx \
    --api-key YOUR_API_KEY \
    --backup
```

### Custom Columns
```bash
# If prompts are in column C and you want responses in column V
python scripts/excel_lightrag_query.py \
    --excel-file data.xlsx \
    --prompt-column C \
    --output-column V
```

### High-Speed Processing
```bash
# Increase concurrent requests (use with caution)
python scripts/excel_lightrag_query.py \
    --excel-file data.xlsx \
    --max-concurrent 5
```

### Remote API Server
```bash
python scripts/excel_lightrag_query.py \
    --excel-file data.xlsx \
    --api-url https://lightrag.example.com:9621 \
    --api-key $LIGHTRAG_API_KEY
```

## What You'll See

### During Processing

```
============================================================
Excel-to-LightRAG Query Processor
============================================================

✓ Loaded Excel file: data.xlsx
✓ Found 50 prompts in column B
✓ Will write responses to column U
✓ API endpoint: http://localhost:9621
✓ Max concurrent requests: 3

Processing queries...

Processing queries: 100%|██████████| 50/50 [02:15<00:00,  2.70s/query]

✓ Writing results to Excel...
✓ Backup created: data.xlsx.backup.20260204_143022
✓ Results saved to: data.xlsx

============================================================
✓ Complete! Success: 48, Errors: 2
============================================================
```

### If Something Goes Wrong

**Server not running:**
```
✗ Error: Cannot connect to LightRAG server at http://localhost:9621
  Make sure the server is running with: lightrag-server
```

**File not found:**
```
✗ Error: File not found: data.xlsx
```

**No prompts found:**
```
✗ No prompts found in column B
```

## Tips for Best Results

### 1. Start Small
Test with a few prompts first before processing thousands.

### 2. Use Backup
Always use `--backup` for important files:
```bash
--backup  # Creates timestamped backup
```

### 3. Monitor Progress
The progress bar shows:
- Number of queries processed
- Processing speed (queries/second)
- Estimated time remaining

### 4. Handle Errors
Failed queries will show "ERROR (after 3 retries)" in the response column. Common causes:
- API server overloaded
- Network issues
- Timeout (query too complex)

You can increase timeout for complex queries:
```bash
--timeout 300  # 5 minutes per query
```

### 5. Concurrent Requests
Default is 3 concurrent requests, which is safe for most setups.

- **Increase** (4-5) if your server is powerful and underutilized
- **Decrease** (1-2) if you're getting timeouts or server errors

## Environment Variables

Create a `.env` file or export variables:

```bash
# Set defaults
export LIGHTRAG_API_URL=http://localhost:9621
export LIGHTRAG_API_KEY=your-secure-key-here

# Now you can run without flags
python scripts/excel_lightrag_query.py --excel-file data.xlsx
```

## Troubleshooting

### Progress Bar Not Showing

Install tqdm:
```bash
uv pip install tqdm
```

### "Module not found" Errors

Make sure you're using the virtual environment:
```bash
# Option 1: Activate venv
source .venv/bin/activate
python scripts/excel_lightrag_query.py --excel-file data.xlsx

# Option 2: Use venv python directly
.venv/bin/python scripts/excel_lightrag_query.py --excel-file data.xlsx
```

### Queries Timing Out

1. Increase timeout:
```bash
--timeout 300
```

2. Reduce concurrent requests:
```bash
--max-concurrent 2
```

3. Check LightRAG server logs for issues

### Memory Issues

For very large files (10,000+ rows):
1. Split into smaller files
2. Process in batches
3. Run on a machine with more RAM

## Advanced: Batch Processing Multiple Files

Process multiple Excel files:

```bash
#!/bin/bash
for file in data/*.xlsx; do
    echo "Processing $file..."
    python scripts/excel_lightrag_query.py \
        --excel-file "$file" \
        --backup
done
```

## Next Steps

- Read the full [README.md](README.md) for detailed documentation
- Check the [script source](excel_lightrag_query.py) for customization options
- Review LightRAG query parameters in the API documentation

## Support

For issues or questions:
1. Check this guide and README.md
2. Review error messages carefully
3. Test with `--dry-run` first
4. Open an issue on GitHub if needed

Happy querying! 🚀
