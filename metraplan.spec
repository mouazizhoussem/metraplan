# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec file for Métraplan 4

import sys
from pathlib import Path

block_cipher = None

# Répertoire racine du projet
ROOT = Path(SPECPATH)

a = Analysis(
    ['main.py'],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        # Assets de l'application
        ('assets/images',       'assets/images'),
        ('assets/icons',        'assets/icons'),
        ('assets/style',        'assets/style'),
        # Bibliothèque BPU (CRITIQUE : utilisée par core/devis_manager.py)
        ('data',                'data'),
        # Icônes racine (référencées par core/canvas.py via chemin relatif)
        ('icons',               'icons'),
        # Fichier de configuration
        ('config.ini',          '.'),
        # Version
        ('version.py',          '.'),
    ],
    hiddenimports=[
        # PyQt5 plugins souvent non détectés
        'PyQt5.sip',
        'PyQt5.QtPrintSupport',
        'PyQt5.QtSvg',
        # PyMuPDF
        'fitz',
        # openpyxl
        'openpyxl',
        'openpyxl.styles',
        'openpyxl.utils',
        # Modules internes
        'core.app_logger',
        'core.license_manager',
        'core.formula_engine',
        'ui.activation_dialog',
        'ui.main_window',
        'ui.report_panel',
        'ui.toolbar_factory',
        'ui.assignments_panel',
        'ui.legend_widget',
        'ui.report_generator',
        'ui.context_menu_manager',
        'ui.excel_exporter',
        'ui.property_dialog',
        'entities',
        'models',
        'services',
        'tools',
        'utils',
        # Outils chargés dynamiquement par tools/tool_manager.py via importlib
        # (PyInstaller ne peut pas détecter ces imports par f-string) :
        'tools.scale_tool',
        'tools.surface_tool',
        'tools.distance_tool',
        'tools.counter_tool',
        'tools.perimeter_tool',
        'tools.opening_tool',
        'tools.marker_tool',
        'tools.note_tool',
        # Crypto / hash (pour machine_id)
        'hashlib',
        'uuid',
        # Réseau (licence)
        'urllib.request',
        'urllib.parse',
        'urllib.error',
        # JWT
        'base64',
        'hmac',
        # Registre Windows
        'winreg',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclure le serveur de licences (non nécessaire dans l'exe client)
        'license_server',
        # Exclure les outils de dev
        'pytest',
        'ipython',
        'notebook',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='Metraplan',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,                          # Pas de fenêtre console
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icons/metraplan.ico',      # Icône Windows
    version_file=None,
)
