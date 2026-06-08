#!/usr/bin/env python3
"""
Parchea el proyecto Flutter generado por `flet build` para agregar Firebase.

Correr DESPUÉS de `flet build apk` (o aab) y ANTES de compilar manualmente:

    python server/setup_firebase_build.py
    cd build/flutter && flutter build appbundle

Qué hace:
  1. Agrega classpath google-services al android/build.gradle raíz
  2. Aplica el plugin en android/app/build.gradle
  3. Copia google-services.json a android/app/
"""

import re
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
FLUTTER_DIR  = PROJECT_ROOT / "build" / "flutter"
ANDROID_DIR  = FLUTTER_DIR / "android"


def patch_root_gradle() -> None:
    path = ANDROID_DIR / "build.gradle"
    if not path.exists():
        print(f"No encontré {path}", file=sys.stderr)
        sys.exit(1)

    content = path.read_text(encoding="utf-8")
    if "com.google.gms:google-services" in content:
        print("✓ Root build.gradle — ya tiene google-services, sin cambios")
        return

    content = re.sub(
        r"(buildscript\s*\{[^}]*?dependencies\s*\{)",
        r"\1\n        classpath 'com.google.gms:google-services:4.4.2'",
        content,
        count=1,
        flags=re.DOTALL,
    )
    path.write_text(content, encoding="utf-8")
    print("✓ Root build.gradle — classpath google-services agregado")


def patch_app_gradle() -> None:
    path = ANDROID_DIR / "app" / "build.gradle"
    if not path.exists():
        print(f"No encontré {path}", file=sys.stderr)
        sys.exit(1)

    content = path.read_text(encoding="utf-8")
    if "com.google.gms.google-services" in content:
        print("✓ App build.gradle — plugin ya aplicado, sin cambios")
        return

    content += "\napply plugin: 'com.google.gms.google-services'\n"
    path.write_text(content, encoding="utf-8")
    print("✓ App build.gradle — plugin google-services aplicado")


def copy_google_services() -> None:
    src = PROJECT_ROOT / "google-services.json"
    dst = ANDROID_DIR / "app" / "google-services.json"

    if not src.exists():
        print()
        print("⚠️  FALTA google-services.json")
        print("   Pasos para obtenerlo:")
        print("   1. Abrí https://console.firebase.google.com/")
        print(f"   2. Proyecto: fixture-mundial-prode")
        print("   3. Engranaje → Configuración del proyecto → Tus apps")
        print("   4. Si no hay app Android, agregá una con paquete: com.mrojas.maxfixture")
        print("   5. Descargá google-services.json y colocalo en la raíz del proyecto")
        print()
        sys.exit(1)

    shutil.copy(src, dst)
    print(f"✓ google-services.json copiado → {dst}")


def patch_firebase_messaging_init() -> None:
    """Agrega FCMHandler.init() al main.dart generado por Flet."""
    path = FLUTTER_DIR / "lib" / "main.dart"
    if not path.exists():
        return

    content = path.read_text(encoding="utf-8")
    if "FCMHandler" in content:
        print("✓ main.dart — FCMHandler ya integrado, sin cambios")
        return

    # Agregar import
    content = content.replace(
        "import 'package:flet/flet.dart';",
        "import 'package:flet/flet.dart';\nimport 'fcm_handler.dart';",
        1,
    )
    # Agregar init antes de runApp (o dentro del main)
    content = content.replace(
        "void main() {",
        "void main() async {\n  WidgetsFlutterBinding.ensureInitialized();\n  await FCMHandler.init();",
        1,
    )
    # Corregir posible duplicado de async si ya estaba
    content = content.replace("async {\n  WidgetsFlutterBinding", "async {\n  WidgetsFlutterBinding")
    path.write_text(content, encoding="utf-8")
    print("✓ main.dart — FCMHandler.init() integrado")


if __name__ == "__main__":
    if not FLUTTER_DIR.exists():
        print("Error: build/flutter/ no existe.")
        print("Primero corrí:  flet build apk")
        sys.exit(1)

    print("Configurando Firebase en el proyecto Flutter generado...\n")
    patch_root_gradle()
    patch_app_gradle()
    copy_google_services()
    patch_firebase_messaging_init()

    print()
    print("✅ Listo! Ahora para compilar el bundle final:")
    print("   cd build/flutter")
    print("   flutter build appbundle --release")
