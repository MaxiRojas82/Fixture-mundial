import 'package:flutter/services.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';

/// Canal de comunicación Python → Flutter para notificaciones del sistema.
/// Flet llama a este método vía page.invoke_method("showNotification", {...}).
class NotificationsHelper {
  static const _channel = MethodChannel('flet/method');
  static final _plugin = FlutterLocalNotificationsPlugin();
  static bool _initialized = false;

  /// Inicializar una sola vez al arrancar la app Flutter.
  static Future<void> init() async {
    if (_initialized) return;
    _initialized = true;

    const androidSettings = AndroidInitializationSettings('@mipmap/ic_launcher');
    const initSettings = InitializationSettings(android: androidSettings);

    await _plugin.initialize(
      initSettings,
      onDidReceiveNotificationResponse: _onNotificationTap,
    );

    // Pedir permiso de notificaciones (Android 13+)
    final androidImpl = _plugin
        .resolvePlatformSpecificImplementation<AndroidFlutterLocalNotificationsPlugin>();
    await androidImpl?.requestNotificationsPermission();

    // Escuchar llamadas desde Python (page.invoke_method)
    _channel.setMethodCallHandler((call) async {
      if (call.method == 'showNotification') {
        final args = Map<String, String>.from(call.arguments as Map);
        await _show(
          title: args['title'] ?? '',
          body: args['body'] ?? '',
          matchId: args['matchId'] ?? '',
        );
      }
      return null;
    });
  }

  static Future<void> _show({
    required String title,
    required String body,
    required String matchId,
  }) async {
    const androidDetails = AndroidNotificationDetails(
      'maxfixture_goals',
      'Goles y eventos',
      channelDescription: 'Alertas de goles, tarjetas e inicio de partido',
      importance: Importance.high,
      priority: Priority.high,
      playSound: true,
      enableVibration: true,
      icon: '@mipmap/ic_launcher',
    );
    await _plugin.show(
      matchId.hashCode,
      title,
      body,
      const NotificationDetails(android: androidDetails),
      payload: matchId,
    );
  }

  /// Cuando el usuario toca la notificación → navegar al partido.
  static void _onNotificationTap(NotificationResponse response) {
    final matchId = response.payload;
    if (matchId != null && matchId.isNotEmpty) {
      // Enviar el route al lado Python vía el mismo canal
      _channel.invokeMethod('navigateTo', {'route': '/match/$matchId'});
    }
  }
}
