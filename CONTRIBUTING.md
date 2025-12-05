# Contributing to PyCognita

First off, thank you for considering contributing to PyCognita! It's people like you that make this tool better for everyone.

## Legal

All contributors must sign the [Contributor License Agreement (CLA)](CLA.md). By contributing, you agree that your contributions are your original work and that you grant the project maintainers the necessary rights to use them.

## Development Setup

### Prerequisites
- Python 3.11 or higher

### Setup
1. Fork the repository on GitHub.
2. Clone your fork locally:
   ```bash
   git clone https://github.com/YOUR_USERNAME/pycognita.git
   cd pycognita
   ```
3. Create a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```
4. Install the package in editable mode:
   ```bash
   pip install -e .
   ```

## Code Style

We use `ruff` for linting and formatting. Please ensure your code passes all checks before submitting a Pull Request.

To run checks:
```bash
pip install ruff
ruff check .
```

## Submitting Changes

1. Create a new branch for your feature or fix:
   ```bash
   git checkout -b feature/my-new-feature
   ```
2. Make your changes.
3. Run the verification scripts or add new tests if applicable.
4. Commit your changes with a clear message.
5. Push to your fork and submit a Pull Request.

## Code of Conduct

Please note that this project is released with a [Code of Conduct](CODE_OF_CONDUCT.md). By participating in this project you agree to abide by its terms.
