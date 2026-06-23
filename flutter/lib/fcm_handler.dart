import 'dart:convert';
import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:shared_preferences/shared_preferences.dart';

const _favKey = 'notif_favorites';
const _notifChannel = 'maxfixture_goals';

// Top-level: puede correr en el isolate de background de FCM.
Future<bool> _shouldNotify(String homeName, String awayName) async {
  final prefs = await SharedPreferences.getInstance();
  final favsJson = prefs.getString(_favKey);
  if (favsJson == null || favsJson.isEmpty) return true;
  final favsList = List<String>.from(jsonDecode(favsJson) as List);
  if (favsList.isEmpty) return true;
  return favsList.contains(homeName) || favsList.contains(awayName);
}

Future<void> _showNotif(String title, String body, String matchId) async {
  final plugin = FlutterLocalNotificationsPlugin();
  const androidSettings = AndroidInitializationSettings('@drawable/ic_stat_notify');
  await plugin.initialize(const InitializationSettings(android: androidSettings));
  await plugin.show(
    matchId.hashCode,
    title,
    body,
    const NotificationDetails(
      android: AndroidNotificationDetails(
        _notifChannel,
        'Goles y eventos',
        channelDescription: 'Alertas de goles y eventos del Mundial',
        importance: Importance.high,
        priority: Priority.high,
        icon: '@drawable/ic_stat_notify',
      ),
    ),
    payload: matchId,
  );
}

@pragma('vm:entry-point')
Future<void> _backgroundHandler(RemoteMessage message) async {
  await Firebase.initializeApp();
  final data = message.data;
  final home = data['homeName'] ?? '';
  final away = data['awayName'] ?? '';
  if (!await _shouldNotify(home, away)) return;
  await _showNotif(
    data['title'] ?? '',
    data['body'] ?? '',
    data['matchId'] ?? '',
  );
}

class FCMHandler {
  FCMHandler._();

  static const _topic = 'maxfixture_events';
  static final _localNotifs = FlutterLocalNotificationsPlugin();

  static Future<void> init() async {
    await Firebase.initializeApp();

    FirebaseMessaging.onBackgroundMessage(_backgroundHandler);

    const androidSettings = AndroidInitializationSettings('@drawable/ic_stat_notify');
    await _localNotifs.initialize(
      const InitializationSettings(android: androidSettings),
    );

    await FirebaseMessaging.instance.requestPermission(
      alert: true,
      badge: true,
      sound: true,
    );

    try {
      await FirebaseMessaging.instance.subscribeToTopic(_topic);
      debugPrint('FCM: suscripto al tema $_topic');
    } catch (e) {
      debugPrint('FCM: error al suscribirse a $_topic: $e');
    }

    // Foreground: filtrar por favoritos antes de mostrar
    FirebaseMessaging.onMessage.listen((message) async {
      final data = message.data;
      final home = data['homeName'] ?? '';
      final away = data['awayName'] ?? '';
      if (!await _shouldNotify(home, away)) return;
      await _showNotif(
        data['title'] ?? '',
        data['body'] ?? '',
        data['matchId'] ?? '',
      );
    });

    final token = await FirebaseMessaging.instance.getToken();
    debugPrint('FCM Token: $token');
  }
}
