"""
scanner/__init__.py

Marks the scanner directory as a Python package.
Each module in this package is responsible for one audit domain:

    system_info  → Hardware & OS metadata
    security     → Firewall, Defender, BitLocker, Windows Update
    services     → Windows Services status
    registry     → Registry-based security checks
    compliance   → Score aggregation engine
"""
