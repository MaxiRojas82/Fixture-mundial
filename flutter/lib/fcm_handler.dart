import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/services.dart';

/// Handler de Firebase Cloud Messaging para MaxFixture.
///
/// Flujos cubiertos:
///  1. App en foreground  → muestra GoalAlert via flutter_local_notifications
///  2. App en background  → toca la notif → [onMessageOpenedApp] navega al partido
///  3. App cerrada        → toca la notif → [getInitialMessage] navega al partido
///
/// Todos los dispositivos se suscriben al topic "maxfixture_events".
/// El servidor (GitHub Actions) publica a ese topic cuando detecta un evento.

const _channel = MethodChannel('flet/method');

/// Debe estar en top-level para que el isolate background pueda accederlo.
@pragma('vm:entry-point')
Future<void> _backgroundMessageHandler(RemoteMessage message) async {
  await Firebase.initializeApp(options: _firebaseOptions);
}

/// Opciones de Firebase (no requiere google-services.json en el APK).
/// Completar con los valores de Firebase Console → Project settings → Your apps.
const _firebaseOptions = FirebaseOptions(
  apiKey:            'AIzaSyAAq9KO2lVHr0YjdoxeRi2FQgYFWPclIqc',
  appId:             '1:613565715645:android:ab864a51053e19d03c13d4',
  messagingSenderId: '613565715645',
  projectId:         'fixture-mundial-prode',
);

class FCMHandler {
  FCMHandler._();

  static Future<void> init() async {
    await Firebase.initializeApp(options: _firebaseOptions);

    FirebaseMessaging.onBackgroundMessage(_backgroundMessageHandler);

    // Pedir permiso de notificaciones (Android 13+)
    await FirebaseMessaging.instance.requestPermission(
      alert: true,
      sound: true,
      badge: false,
    );

    // Suscribir al topic global — todas las notificaciones del Mundial
    await FirebaseMessaging.instance.subscribeToTopic('maxfixture_events');

    // App en background → usuario toca la notificación
    FirebaseMessaging.onMessageOpenedApp.listen(_navigate);

    // App cerrada → usuario toca la notificación
    final initial = await FirebaseMessaging.instance.getInitialMessage();
    if (initial != null) {
      // Dar tiempo a que Flet inicialice la página antes de navegar
      await Future.delayed(const Duration(milliseconds: 800));
      _navigate(initial);
    }

    // App en foreground → la notificación del sistema no aparece por defecto;
    // flutter_local_notifications la muestra vía NotificationsHelper
    FirebaseMessaging.onMessage.listen((message) {
      final title   = message.notification?.title ?? '';
      final body    = message.notification?.body  ?? '';
      final matchId = message.data['matchId']      ?? '';
      if (title.isNotEmpty) {
        _channel.invokeMethod('showNotification', {
          'title':   title,
          'body':    body,
          'matchId': matchId,
        });
      }
    });
  }

  static void _navigate(RemoteMessage message) {
    final matchId = message.data['matchId'];
    if (matchId != null && matchId.isNotEmpty) {
      _channel.invokeMethod('navigateTo', {'route': '/match/$matchId'});
    }
  }
}
