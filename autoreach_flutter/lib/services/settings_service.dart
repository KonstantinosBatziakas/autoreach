import 'package:flutter_secure_storage/flutter_secure_storage.dart';

/// All sensitive credentials are stored in the OS keystore via flutter_secure_storage.
/// On Android this uses the Android Keystore; on iOS the Keychain.
/// Non-sensitive UI preferences (e.g. logged_in flag) remain in SharedPreferences.
class SettingsService {
  static const _storage = FlutterSecureStorage(
    aOptions: AndroidOptions(encryptedSharedPreferences: true),
  );

  // ── Google Maps API key ──────────────────────────────────────────────────
  static Future<String> getGoogleApiKey() async =>
      await _storage.read(key: 'google_api_key') ?? '';
  static Future<void> setGoogleApiKey(String v) async =>
      _storage.write(key: 'google_api_key', value: v);

  // ── Resend credentials ───────────────────────────────────────────────────
  static Future<String> getResendApiKey() async =>
      await _storage.read(key: 'resend_api_key') ?? '';
  static Future<void> setResendApiKey(String v) async =>
      _storage.write(key: 'resend_api_key', value: v);

  static Future<String> getFromEmail() async =>
      await _storage.read(key: 'from_email') ?? '';
  static Future<void> setFromEmail(String v) async =>
      _storage.write(key: 'from_email', value: v);

  // ── Groq API key ─────────────────────────────────────────────────────────
  static Future<String> getGroqApiKey() async =>
      await _storage.read(key: 'groq_api_key') ?? '';
  static Future<void> setGroqApiKey(String v) async =>
      _storage.write(key: 'groq_api_key', value: v);

  // ── Display name (non-sensitive, but kept here for API consistency) ───────
  static Future<String> getSenderName() async =>
      await _storage.read(key: 'sender_name') ?? 'AutoReach';
  static Future<void> setSenderName(String v) async =>
      _storage.write(key: 'sender_name', value: v);
}
