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

    # Insertar classpath justo después de la línea del kotlin-gradle-plugin
    content = re.sub(
        r"(classpath\s+[\"']org\.jetbrains\.kotlin:kotlin-gradle-plugin:[^\"']+[\"'])",
        r"\1\n        classpath 'com.google.gms:google-services:4.4.2'",
        content,
        count=1,
    )
    path.write_text(content, encoding="utf-8")
    print("✓ Root build.gradle — classpath google-services agregado")


def patch_signing() -> None:
    """Configura firma de release con maxfixture-upload.keystore."""
    path = ANDROID_DIR / "app" / "build.gradle"
    if not path.exists():
        return
    content = path.read_text(encoding="utf-8")
    if "signingConfigs" in content and "release {" in content and "storeFile" in content:
        print("✓ App build.gradle — signing ya configurado, sin cambios")
        return

    keystore_path = PROJECT_ROOT / "maxfixture-upload.keystore"
    keystore_str = str(keystore_path).replace("\\", "/")

    signing_block = f"""    signingConfigs {{
        release {{
            storeFile file("{keystore_str}")
            storePassword "eitanloana09"
            keyAlias "maxfixture"
            keyPassword "eitanloana09"
        }}
    }}

"""
    content = content.replace(
        "// flet: android_signing \n\n    buildTypes {",
        signing_block + "    buildTypes {",
        1,
    )
    content = content.replace(
        "// flet: android_signing \n            signingConfig signingConfigs.debug\n// flet: end of android_signing ",
        "            signingConfig signingConfigs.release",
        1,
    )
    path.write_text(content, encoding="utf-8")
    print("✓ App build.gradle — firma de release configurada")


def patch_application_id() -> None:
    """Corrige el applicationId generado por Flet para que coincida con Firebase (com.mrojas.maxfixture)."""
    path = ANDROID_DIR / "app" / "build.gradle"
    if not path.exists():
        return
    content = path.read_text(encoding="utf-8")
    if "com.mrojas.fixture_mundial" not in content:
        print("✓ App build.gradle — applicationId ya es com.mrojas.maxfixture, sin cambios")
    else:
        content = content.replace("com.mrojas.fixture_mundial", "com.mrojas.maxfixture")
        path.write_text(content, encoding="utf-8")
        print("✓ App build.gradle — applicationId corregido a com.mrojas.maxfixture")
    patch_main_activity()


def patch_main_activity() -> None:
    """Crea MainActivity.kt con el paquete correcto (com.mrojas.maxfixture).

    Flet genera el archivo bajo com/mrojas/fixture_mundial/ (o com/flet/fixture_mundial/),
    pero el namespace en build.gradle es com.mrojas.maxfixture, por lo que Android busca
    com.mrojas.maxfixture.MainActivity y no lo encuentra → crash en startup.
    """
    kotlin_dir = ANDROID_DIR / "app" / "src" / "main" / "kotlin"
    correct_dir = kotlin_dir / "com" / "mrojas" / "maxfixture"
    correct_file = correct_dir / "MainActivity.kt"

    if correct_file.exists():
        print("✓ MainActivity.kt — ya está en com/mrojas/maxfixture/, sin cambios")
        return

    correct_dir.mkdir(parents=True, exist_ok=True)
    correct_file.write_text(
        "package com.mrojas.maxfixture\n\n"
        "import io.flutter.embedding.android.FlutterActivity\n\n"
        "class MainActivity: FlutterActivity() {\n}\n",
        encoding="utf-8",
    )
    print("✓ MainActivity.kt — creado en com/mrojas/maxfixture/")


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


def patch_pubspec_deps() -> None:
    """Agrega firebase_core, firebase_messaging y flutter_local_notifications al pubspec generado."""
    path = FLUTTER_DIR / "pubspec.yaml"
    if not path.exists():
        print(f"No encontré {path}", file=sys.stderr)
        sys.exit(1)

    content = path.read_text(encoding="utf-8")
    if "firebase_core" in content:
        print("✓ pubspec.yaml — deps Firebase ya presentes, sin cambios")
        return

    content = content.replace(
        "  url_strategy: ^0.2.0",
        "  url_strategy: ^0.2.0\n  firebase_core: ^3.0.0\n  firebase_messaging: ^15.0.0\n  flutter_local_notifications: ^17.0.0\n  shared_preferences: ^2.3.2\n  url_launcher: ^6.3.0",
        1,
    )
    # Pin versions compatible with current Gradle setup
    if "shared_preferences_android:" not in content:
        content = content.replace(
            "  flet: 0.28.3",
            "  flet: 0.28.3\n  shared_preferences_android: 2.4.13\n  url_launcher_android: 6.3.20",
            1,
        )
    path.write_text(content, encoding="utf-8")
    print("✓ pubspec.yaml — firebase_core, firebase_messaging, flutter_local_notifications, shared_preferences, url_launcher agregados")


def patch_desugaring() -> None:
    """Habilita core library desugaring requerido por flutter_local_notifications."""
    path = ANDROID_DIR / "app" / "build.gradle"
    if not path.exists():
        print(f"No encontré {path}", file=sys.stderr)
        sys.exit(1)

    content = path.read_text(encoding="utf-8")
    if "coreLibraryDesugaringEnabled" in content:
        print("✓ App build.gradle — desugaring ya habilitado, sin cambios")
        return

    content = content.replace(
        "        sourceCompatibility JavaVersion.VERSION_1_8\n        targetCompatibility JavaVersion.VERSION_1_8",
        "        sourceCompatibility JavaVersion.VERSION_1_8\n        targetCompatibility JavaVersion.VERSION_1_8\n        coreLibraryDesugaringEnabled true",
        1,
    )
    content = content.replace(
        "dependencies {}",
        "dependencies {\n    coreLibraryDesugaring 'com.android.tools:desugar_jdk_libs:2.1.4'\n}",
        1,
    )
    # Si dependencies ya tenía contenido
    if "coreLibraryDesugaring" not in content:
        content = re.sub(
            r"(dependencies \{)",
            r"\1\n    coreLibraryDesugaring 'com.android.tools:desugar_jdk_libs:2.1.4'",
            content,
            count=1,
        )
    path.write_text(content, encoding="utf-8")
    print("✓ App build.gradle — core library desugaring habilitado")


def copy_notification_icon() -> None:
    """Instala el ícono monocromo de notificaciones (silueta blanca).

    Android exige siluetas blancas sobre transparente para el ícono chico
    de notificación; usar el launcher icon genera un cuadrado/bordes blancos.
    """
    src = Path(__file__).parent / "ic_stat_notify.png"
    if not src.exists():
        print("⚠ No encontré server/ic_stat_notify.png — sin ícono de notificación")
        return
    dst_dir = ANDROID_DIR / "app" / "src" / "main" / "res" / "drawable"
    dst_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(src, dst_dir / "ic_stat_notify.png")
    print("✓ ic_stat_notify.png copiado a res/drawable/")

    # Ícono por defecto para las notificaciones FCM (app en segundo plano)
    manifest = ANDROID_DIR / "app" / "src" / "main" / "AndroidManifest.xml"
    if not manifest.exists():
        return
    content = manifest.read_text(encoding="utf-8")
    if "default_notification_icon" in content:
        print("✓ AndroidManifest — meta-data de ícono ya presente, sin cambios")
        return
    meta = ('        <meta-data\n'
            '            android:name="com.google.firebase.messaging.default_notification_icon"\n'
            '            android:resource="@drawable/ic_stat_notify" />\n')
    content = content.replace("</application>", meta + "    </application>", 1)
    manifest.write_text(content, encoding="utf-8")
    print("✓ AndroidManifest — ícono de notificación FCM configurado")


def copy_fcm_handler() -> None:
    """Copia la versión canónica de fcm_handler.dart al proyecto generado.

    El build/ no está en git: sin esta copia, el handler (con la suscripción
    al tema FCM) se perdería si se regenera la carpeta.
    """
    src = Path(__file__).parent / "fcm_handler.dart"
    dst = FLUTTER_DIR / "lib" / "fcm_handler.dart"
    if not src.exists():
        print(f"⚠ No encontré {src} — se mantiene el fcm_handler.dart existente")
        return
    shutil.copy(src, dst)
    print("✓ fcm_handler.dart copiado desde server/ (con suscripción al tema)")


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
    # Agregar init al comienzo del main (antes de runApp)
    # Flet genera: void main(List<String> args) async {
    content = content.replace(
        "void main(List<String> args) async {\n  _args",
        "void main(List<String> args) async {\n  WidgetsFlutterBinding.ensureInitialized();\n  await FCMHandler.init();\n  _args",
        1,
    )
    path.write_text(content, encoding="utf-8")
    print("✓ main.dart — FCMHandler.init() integrado")


if __name__ == "__main__":
    if not FLUTTER_DIR.exists():
        print("Error: build/flutter/ no existe.")
        print("Primero corrí:  flet build apk")
        sys.exit(1)

    print("Configurando Firebase en el proyecto Flutter generado...\n")
    patch_pubspec_deps()
    patch_root_gradle()
    patch_app_gradle()
    patch_signing()
    patch_application_id()
    patch_desugaring()
    copy_google_services()
    copy_notification_icon()
    copy_fcm_handler()
    patch_firebase_messaging_init()

    print()
    print("✅ Listo! Ahora para compilar el bundle final:")
    print("   cd build/flutter")
    print("   flutter build appbundle --release")
