# Scripts Directory Index

This directory contains the Excel-to-LightRAG Query Processor and related utilities.

## 📁 Directory Structure

```
scripts/
├── INDEX.md                    # This file - directory overview
├── README.md                   # Full documentation
├── QUICKSTART.md              # Quick start guide
├── IMPLEMENTATION.md          # Technical implementation details
├── excel_lightrag_query.py    # Main script (executable)
├── process_excel.sh           # Wrapper script (executable)
├── create_test_excel.py       # Test file generator (executable)
└── test_data.xlsx            # Sample Excel file for testing
```

## 🚀 Quick Start

### 1. Install Dependencies
```bash
uv pip install openpyxl tqdm
```

### 2. Run the Script
```bash
# Using the Python script directly
python scripts/excel_lightrag_query.py --excel-file your_file.xlsx --backup

# Or using the wrapper script
./scripts/process_excel.sh your_file.xlsx --backup
```

### 3. View Results
Open your Excel file - column U will contain the LightRAG responses.

## 📚 Documentation Files

### [README.md](README.md)
**Comprehensive documentation covering:**
- Features and capabilities
- Installation instructions
- Complete command-line arguments reference
- Excel file format requirements
- API configuration details
- Error handling strategies
- Performance considerations
- Troubleshooting guide
- Usage examples

**Read this for**: Complete reference documentation

### [QUICKSTART.md](QUICKSTART.md)
**Step-by-step beginner guide:**
- Prerequisites checklist
- Installation walkthrough
- Excel file preparation
- Starting LightRAG server
- Running the processor
- Common usage patterns
- Tips for best results

**Read this for**: Getting started quickly

### [IMPLEMENTATION.md](IMPLEMENTATION.md)
**Technical implementation details:**
- Architecture overview
- Code structure and classes
- Concurrency control implementation
- Retry logic details
- API configuration
- Testing results
- Performance characteristics
- Known limitations

**Read this for**: Understanding the implementation

## 🛠️ Executable Files

### [excel_lightrag_query.py](excel_lightrag_query.py)
**Main Python script - 430 lines**

**Core functionality:**
- Reads prompts from Excel column B
- Queries LightRAG API with parallel processing (max 3 concurrent)
- Writes responses to column U
- Automatic retry with exponential backoff (3 attempts)
- Progress tracking with tqdm
- Comprehensive error handling
- Optional timestamped backups

**Usage:**
```bash
python scripts/excel_lightrag_query.py --excel-file data.xlsx [options]
```

**Key options:**
- `--excel-file`: Excel file path (required)
- `--api-url`: LightRAG API URL (default: http://localhost:9621)
- `--api-key`: API authentication key
- `--max-concurrent`: Max parallel requests (default: 3)
- `--backup`: Create backup before modifying
- `--dry-run`: Test without writing results

### [process_excel.sh](process_excel.sh)
**Bash wrapper script - 61 lines**

Simplifies running the Python script by:
- Auto-detecting Python interpreter (.venv or system)
- Validating file existence
- Providing friendly usage examples

**Usage:**
```bash
./scripts/process_excel.sh data.xlsx [options]
```

### [create_test_excel.py](create_test_excel.py)
**Test file generator - 58 lines**

Creates a sample Excel file for testing with:
- 5 sample prompts in column B
- Proper header structure
- Empty response column U
- Category column for organization

**Usage:**
```bash
python scripts/create_test_excel.py
# Creates: scripts/test_data.xlsx
```

## 📊 Data Files

### [test_data.xlsx](test_data.xlsx)
**Sample Excel file for testing**

**Structure:**
- Column A: ID (1-5)
- Column B: Pytanie (Question) - 5 sample prompts about LightRAG
- Column C: Category (General, Technical, Concepts, Features)
- Column U: Response (empty, to be filled by script)

**Sample prompts:**
1. What is LightRAG?
2. How does retrieval-augmented generation work?
3. What are the benefits of using a knowledge graph?
4. Explain the difference between local and global query modes
5. What storage backends does LightRAG support?

## 🎯 Common Tasks

### Test the Installation
```bash
python scripts/create_test_excel.py
python scripts/excel_lightrag_query.py \
    --excel-file scripts/test_data.xlsx \
    --dry-run
```

### Process Your Excel File
```bash
# With backup (recommended)
./scripts/process_excel.sh your_file.xlsx --backup

# Or directly
python scripts/excel_lightrag_query.py \
    --excel-file your_file.xlsx \
    --backup
```

### Use Authentication
```bash
export LIGHTRAG_API_KEY=your-secure-key
./scripts/process_excel.sh your_file.xlsx
```

### Custom Configuration
```bash
python scripts/excel_lightrag_query.py \
    --excel-file your_file.xlsx \
    --api-url http://localhost:9621 \
    --max-concurrent 5 \
    --timeout 180 \
    --backup
```

## 📖 Reading Order

**For new users:**
1. Start with [QUICKSTART.md](QUICKSTART.md) - get running in 5 minutes
2. Reference [README.md](README.md) - when you need specific details
3. Check troubleshooting sections - if you encounter issues

**For developers:**
1. Review [IMPLEMENTATION.md](IMPLEMENTATION.md) - understand the code
2. Read the script source - see implementation details
3. Reference [README.md](README.md) - for API documentation

**For system administrators:**
1. Check [README.md](README.md) - installation and configuration
2. Review [IMPLEMENTATION.md](IMPLEMENTATION.md) - performance and security
3. Reference [QUICKSTART.md](QUICKSTART.md) - for user training

## 🔍 Key Features

### Parallel Processing
- **Max 3 concurrent requests** (configurable)
- Semaphore-based concurrency control
- Maintains result order
- Progress bar with real-time updates

### Error Handling
- **Automatic retry** (3 attempts)
- Exponential backoff (2s, 4s, 8s)
- Continues on individual failures
- Error messages written to output column

### User Experience
- **Clear progress indication** with tqdm
- Helpful error messages
- Dry-run mode for testing
- Optional timestamped backups
- Environment variable support

### Production Ready
- Type hints throughout
- Comprehensive docstrings
- Modular class design
- Async/await patterns
- Resource management with context managers

## 📋 Requirements

### Core Dependencies
- Python 3.8+
- aiohttp (async HTTP client)
- tenacity (retry logic)
- openpyxl (Excel file processing)

### Optional
- tqdm (progress bar - highly recommended)

### Installation
```bash
uv pip install openpyxl tqdm
```

## 🐛 Troubleshooting

### Common Issues

**"Module not found" errors:**
```bash
# Install dependencies
uv pip install openpyxl tqdm
```

**"Cannot connect to LightRAG server":**
```bash
# Start the server
lightrag-server --host 0.0.0.0 --port 9621
```

**Progress bar not showing:**
```bash
# Install tqdm
uv pip install tqdm
```

**For more troubleshooting:** See [README.md](README.md) or [QUICKSTART.md](QUICKSTART.md)

## 📝 File Statistics

| File | Lines | Size | Purpose |
|------|-------|------|---------|
| excel_lightrag_query.py | 430 | 13KB | Main script |
| README.md | 299 | 6.9KB | Full documentation |
| QUICKSTART.md | 288 | 6.3KB | Quick start guide |
| IMPLEMENTATION.md | 382 | 11KB | Technical details |
| process_excel.sh | 61 | 1.5KB | Wrapper script |
| create_test_excel.py | 58 | 1.8KB | Test generator |
| test_data.xlsx | - | 5.0KB | Sample data |

**Total:** ~1,500 lines of code and documentation

## 🔗 Related Resources

- **LightRAG Documentation**: [GitHub](https://github.com/HKUDS/LightRAG)
- **LightRAG API Server**: See `/lightrag/api/lightrag_server.py`
- **Query Endpoints**: See `/lightrag/api/routers/query_routes.py`
- **Environment Configuration**: See `/env.example`

## 📞 Support

For issues or questions:
1. Check the documentation files in this directory
2. Review error messages and troubleshooting sections
3. Test with `--dry-run` flag first
4. Open an issue on GitHub if needed

## 📄 License

This script is part of the LightRAG project and follows the same license.

---

**Last Updated**: 2026-02-04
**Version**: 1.0.0
**Status**: Production Ready ✅
