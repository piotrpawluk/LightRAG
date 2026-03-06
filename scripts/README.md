# Excel-to-LightRAG Query Processor

Python script that processes Excel files by extracting prompts and querying the LightRAG API in parallel.

## Features

- **Parallel Processing**: Processes up to 3 queries concurrently for faster execution
- **Automatic Retry**: Retries failed queries up to 3 times with exponential backoff
- **Progress Tracking**: Real-time progress bar (requires `tqdm`)
- **Error Handling**: Continues processing even if individual queries fail
- **Backup Support**: Optional timestamped backup before modifying files
- **Dry Run Mode**: Test without writing to Excel

## Installation

### Required Dependencies

All core dependencies are already included in LightRAG's `pyproject.toml`:
- `openpyxl` - Excel file processing
- `aiohttp` - Async HTTP client
- `tenacity` - Retry logic

### Optional Dependencies

For progress bar support:
```bash
pip install tqdm
```

## Usage

### Basic Usage

```bash
python scripts/excel_lightrag_query.py --excel-file data.xlsx
```

### With Authentication and Backup

```bash
python scripts/excel_lightrag_query.py \
    --excel-file data.xlsx \
    --api-key YOUR_API_KEY \
    --backup
```

### Custom Configuration

```bash
python scripts/excel_lightrag_query.py \
    --excel-file data.xlsx \
    --api-url http://lightrag.example.com:9621 \
    --max-concurrent 5 \
    --output-column V \
    --prompt-column C
```

### Dry Run (Test Without Writing)

```bash
python scripts/excel_lightrag_query.py \
    --excel-file data.xlsx \
    --dry-run
```

## Command-Line Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `--excel-file` | **Required** | Path to Excel file (.xlsx) |
| `--api-url` | `http://localhost:9621` | LightRAG API base URL |
| `--api-key` | None | API key for authentication |
| `--max-concurrent` | `3` | Maximum concurrent requests |
| `--timeout` | `120` | Request timeout in seconds |
| `--output-column` | `U` | Column for writing responses |
| `--prompt-column` | `B` | Column containing prompts |
| `--backup` | `false` | Create timestamped backup |
| `--dry-run` | `false` | Process without writing |

## Environment Variables

You can set default values via environment variables:

```bash
export LIGHTRAG_API_URL=http://localhost:9621
export LIGHTRAG_API_KEY=your-secure-key-here
```

Or create a `.env` file:
```bash
LIGHTRAG_API_URL=http://localhost:9621
LIGHTRAG_API_KEY=your-secure-key-here
```

## Excel File Format

### Required Structure

- **Prompt Column**: Column B (default) contains the questions/prompts
- **Header Row**: First row contains headers (skipped during processing)
- **Output Column**: Column U (default) will store the responses

### Example Layout

| A | B (Pytanie) | ... | U (Response) |
|---|-------------|-----|--------------|
| ID | Question text | ... | *empty initially* |
| 1 | What is LightRAG? | ... | *will be filled* |
| 2 | How does it work? | ... | *will be filled* |

### Important Notes

- Empty cells in the prompt column are skipped automatically
- **Existing data in the output column is overwritten** without warning
- The script processes rows starting from row 2 (skips header)

## LightRAG API Configuration

The script queries the LightRAG API with the following parameters:

```json
{
  "mode": "mix",
  "top_k": 40,
  "chunk_top_k": 20,
  "max_entity_tokens": 3000,
  "max_relation_tokens": 4000,
  "max_total_tokens": 4000,
  "enable_rerank": true,
  "include_references": true
}
```

These values are optimized for comprehensive responses with reranking enabled.

## Error Handling

### Automatic Retry

Failed queries are automatically retried up to 3 times with exponential backoff:
- First retry: 2 seconds
- Second retry: 4 seconds
- Third retry: 8 seconds

After 3 failed attempts, an error message is written to the output column.

### Common Errors

**Cannot connect to LightRAG server**
```
✗ Error: Cannot connect to LightRAG server at http://localhost:9621
  Make sure the server is running with: lightrag-server
```
**Solution**: Start the LightRAG server:
```bash
lightrag-server --host 0.0.0.0 --port 9621
```

**File not found**
```
✗ Error: File not found: data.xlsx
```
**Solution**: Verify the file path is correct

**Invalid API key**
```
ERROR (after 3 retries): 401 Unauthorized
```
**Solution**: Check your API key configuration

## Performance

### Concurrency

The script uses a semaphore to limit concurrent requests:
- Default: 3 concurrent requests
- Recommended range: 2-5 concurrent requests
- Higher values may overwhelm the API server

### Processing Speed

Approximate processing times (with default settings):
- 10 prompts: ~30-60 seconds
- 50 prompts: ~2-5 minutes
- 100 prompts: ~5-10 minutes

Actual times depend on:
- LightRAG server response time
- Query complexity
- Network latency
- Number of concurrent requests

## Examples

### Process Polish Questions

```bash
# Excel file with "Pytanie" (Question) header in column B
python scripts/excel_lightrag_query.py \
    --excel-file pytania.xlsx \
    --backup
```

### Use Remote LightRAG Server

```bash
python scripts/excel_lightrag_query.py \
    --excel-file data.xlsx \
    --api-url https://lightrag.mycompany.com \
    --api-key $LIGHTRAG_API_KEY
```

### High-Throughput Processing

```bash
# Increase concurrency and timeout for large files
python scripts/excel_lightrag_query.py \
    --excel-file large_dataset.xlsx \
    --max-concurrent 5 \
    --timeout 180 \
    --backup
```

## Troubleshooting

### No Progress Bar

If you see:
```
Warning: tqdm not installed. Install with: pip install tqdm
Progress bar will not be available.
```

Install tqdm for progress tracking:
```bash
pip install tqdm
```

### Memory Issues with Large Files

For very large Excel files (10,000+ rows), consider:
1. Splitting the file into smaller chunks
2. Processing in batches
3. Using a more powerful machine

### Network Timeouts

If queries frequently timeout:
1. Increase timeout: `--timeout 300`
2. Reduce concurrency: `--max-concurrent 2`
3. Check network connection to API server

## Development

### Testing the Script

Create a test Excel file:
```bash
# Create test file with sample prompts
python -c "
import openpyxl
wb = openpyxl.Workbook()
ws = wb.active
ws['B1'] = 'Pytanie'
ws['B2'] = 'What is LightRAG?'
ws['B3'] = 'How does RAG work?'
ws['B4'] = 'Explain knowledge graphs'
wb.save('test_data.xlsx')
print('Created test_data.xlsx')
"
```

Run with dry-run mode:
```bash
python scripts/excel_lightrag_query.py \
    --excel-file test_data.xlsx \
    --dry-run
```

### Verifying Concurrency

Monitor concurrent connections (Linux/Mac):
```bash
# In another terminal while script runs
watch -n 1 "netstat -an | grep 9621 | grep ESTABLISHED | wc -l"
```

Should never exceed the `--max-concurrent` value.

## License

This script is part of the LightRAG project and follows the same license.

## Support

For issues or questions:
1. Check the [LightRAG documentation](https://github.com/HKUDS/LightRAG)
2. Review the examples in this README
3. Open an issue on GitHub
