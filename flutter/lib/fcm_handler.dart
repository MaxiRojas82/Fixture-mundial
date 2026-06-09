import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';

@pragma('vm:entry-point')
Future<void> _backgroundHandler(RemoteMessage message) async {
  // FCM muestra notificaciones con payload "notification" automáticamente.
  // Este handler corre en un isolate separado para mensajes data-only.
  await Firebase.initializeApp();
}

class FCMHandler {
  FCMHandler._();

  static final _localNotifs = FlutterLocalNotificationsPlugin();

  static Future<void> init() async {
    await Firebase.initializeApp();

    FirebaseMessaging.onBackgroundMessage(_backgroundHandler);

    const androidSettings = AndroidInitializationSettings('@mipmap/ic_launcher');
    await _localNotifs.initialize(
      const InitializationSettings(android: androidSettings),
    );

    await FirebaseMessaging.instance.requestPermission(
      alert: true,
      badge: true,
      sound: true,
    );

    // Mostrar notificación cuando la app está en primer plano
    FirebaseMessaging.onMessage.listen((message) {
      final n = message.notification;
      if (n == null) return;
      _localNotifs.show(
        message.messageId?.hashCode ?? n.hashCode,
        n.title,
        n.body,
        const NotificationDetails(
          android: AndroidNotificationDetails(
            'maxfixture_goals',
            'Goles y eventos',
            channelDescription: 'Alertas de goles y eventos del Mundial',
            importance: Importance.high,
            priority: Priority.high,
            icon: '@mipmap/ic_launcher',
          ),
        ),
      );
    });

    final token = await FirebaseMessaging.instance.getToken();
    debugPrint('FCM Token: $token');
  }
}
