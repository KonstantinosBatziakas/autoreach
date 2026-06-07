import 'dart:convert';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;
import '../constants.dart';

const _storage = FlutterSecureStorage(
  aOptions: AndroidOptions(encryptedSharedPreferences: true),
);

const _tokenKey = 'auth_token';
const _baseUrl = kBaseUrl;

class AuthUser {
  final int id;
  final String email;
  final String name;
  const AuthUser({required this.id, required this.email, required this.name});
}

class AuthService {
  // ── Token storage ──────────────────────────────────────────────────────────
  static Future<void> saveToken(String token) =>
      _storage.write(key: _tokenKey, value: token);

  static Future<String?> getToken() => _storage.read(key: _tokenKey);

  static Future<void> clearToken() => _storage.delete(key: _tokenKey);

  /// Quick local check: is there a (non-expired) token stored?
  static Future<bool> isLoggedIn() async {
    final token = await getToken();
    if (token == null) return false;
    try {
      // JWT = header.payload.sig — decode payload without verifying signature
      // (signature is verified by the server; we just check expiry locally)
      final parts = token.split('.');
      if (parts.length != 3) return false;
      final payload = jsonDecode(
        utf8.decode(base64Url.decode(base64Url.normalize(parts[1]))),
      );
      final exp = payload['exp'] as int?;
      if (exp == null) return false;
      return DateTime.fromMillisecondsSinceEpoch(exp * 1000).isAfter(DateTime.now());
    } catch (_) {
      return false;
    }
  }

  /// Decode the stored token and return basic user info (no network call).
  static Future<AuthUser?> currentUser() async {
    final token = await getToken();
    if (token == null) return null;
    try {
      final parts = token.split('.');
      final payload = jsonDecode(
        utf8.decode(base64Url.decode(base64Url.normalize(parts[1]))),
      );
      return AuthUser(
        id: payload['sub'] as int,
        email: payload['email'] as String? ?? '',
        name: payload['name'] as String? ?? '',
      );
    } catch (_) {
      return null;
    }
  }

  // ── Email + Password ───────────────────────────────────────────────────────
  /// Returns the JWT string on success, throws on failure.
  static Future<String> emailLogin(String email, String password) async {
    final resp = await http.post(
      Uri.parse('$_baseUrl/auth/login'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'email': email, 'password': password}),
    ).timeout(const Duration(seconds: 15));

    final body = jsonDecode(resp.body);
    if (resp.statusCode == 200) return body['token'] as String;
    throw body['error'] ?? 'Login failed';
  }

  static Future<String> emailRegister(String name, String email, String password) async {
    final resp = await http.post(
      Uri.parse('$_baseUrl/auth/register'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'name': name, 'email': email, 'password': password}),
    ).timeout(const Duration(seconds: 15));

    final body = jsonDecode(resp.body);
    if (resp.statusCode == 201) return body['token'] as String;
    throw body['error'] ?? 'Registration failed';
  }

  /// Verify with the server that the token is still valid.
  /// Returns false (and clears the stored token) if the server rejects it.
  static Future<bool> verifyWithServer() async {
    final token = await getToken();
    if (token == null) return false;
    try {
      final resp = await http.get(
        Uri.parse('$_baseUrl/auth/me'),
        headers: {'Authorization': 'Bearer $token'},
      ).timeout(const Duration(seconds: 10));
      if (resp.statusCode == 401) {
        await clearToken();
        return false;
      }
      return resp.statusCode == 200;
    } catch (_) {
      // Network error — assume still logged in (offline tolerance)
      return true;
    }
  }

  // ── OAuth URLs (browser opens these; Render handles the exchange) ──────────
  static Uri githubAuthUrl()  => Uri.parse('$_baseUrl/auth/github');
  static Uri discordAuthUrl() => Uri.parse('$_baseUrl/auth/discord');
  static Uri googleAuthUrl()  => Uri.parse('$_baseUrl/auth/google');
}
