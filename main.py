"""Root entrypoint wrapper for the Industrial RCA System."""
import sys
from pathlib import Path

# Add industrial_rca to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from industrial_rca.main import main

if __name__ == "__main__":
    main()
