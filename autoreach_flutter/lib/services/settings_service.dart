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

  // ── In-app ARIA model settings ────────────────────────────────────────────
  // Accept any provider exposing an OpenAI-compatible chat completions API.
  static Future<String> getAriaApiBaseUrl() async =>
      await _storage.read(key: 'aria_api_base_url') ??
      'https://api.groq.com/openai/v1';
  static Future<void> setAriaApiBaseUrl(String v) async =>
      _storage.write(key: 'aria_api_base_url', value: v);

  static Future<String> getAriaModel() async =>
      await _storage.read(key: 'aria_model') ?? 'openai/gpt-oss-20b';
  static Future<void> setAriaModel(String v) async =>
      _storage.write(key: 'aria_model', value: v);

  static Future<String> getAriaApiKey() async =>
      await _storage.read(key: 'aria_api_key') ?? await getGroqApiKey();
  static Future<void> setAriaApiKey(String v) async =>
      _storage.write(key: 'aria_api_key', value: v);

  static Future<String> getAriaCustomPrompt() async =>
      await _storage.read(key: 'aria_custom_prompt') ?? '';
  static Future<void> setAriaCustomPrompt(String v) async =>
      _storage.write(key: 'aria_custom_prompt', value: v);

  // ── Display name (non-sensitive, but kept here for API consistency) ───────
  static Future<String> getSenderName() async =>
      await _storage.read(key: 'sender_name') ?? 'AutoReach';
  static Future<void> setSenderName(String v) async =>
      _storage.write(key: 'sender_name', value: v);
}
